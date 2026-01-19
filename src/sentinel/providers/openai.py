from sentinel.providers.base import LLMProvider
from sentinel.domain.models import (
    ChatRequest, 
    ChatResponse, 
    Message, 
    Role, 
    FinishReason, 
    TokenUsage
)
from sentinel.domain.exceptions import (
    CircuitOpenError,
    ProviderError,
    ProviderUnavailableError,
    ProviderRateLimitError
)
from sentinel.core.circuit_breaker import CircuitBreaker
import httpx
import datetime
from sentinel.core.retry import RetryPolicy

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.circuit_breaker = CircuitBreaker()
        self.retry_policy = RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=40.0)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get("/v1/models", headers={"Authorization": f"Bearer {self.api_key}"})
                if response.status_code == 503:
                    raise ProviderUnavailableError("OpenAI service unavailable", "openai", 503)
                return response.status_code == 200
        except (ProviderUnavailableError, ProviderRateLimitError):
            raise
        except Exception as e:
            raise ProviderError(f"Health check failed: {e}", "openai", None)

    async def _do_completion(self, request: ChatRequest) -> ChatResponse:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {
                "model": request.model,
                "messages": [{"role": msg.role.value, "content": msg.content} for msg in request.messages],
                "temperature": request.parameters.temperature,
            }
            if request.parameters.max_tokens:
                payload["max_tokens"] = request.parameters.max_tokens
            if request.parameters.top_p:
                payload["top_p"] = request.parameters.top_p
            if request.parameters.stop:
                payload["stop"] = request.parameters.stop

            response = await client.post("/chat/completions", json=payload, headers=headers)
            if response.status_code == 429:
                raise ProviderRateLimitError("Rate limit exceeded", "openai", 429, {"retry_after": response.headers.get("retry-after", "unknown")})
            elif response.status_code == 503:
                raise ProviderUnavailableError("OpenAI service unavailable", "openai", 503)
            elif response.status_code != 200:
                raise ProviderError(f"Request failed with status {response.status_code}", "openai", response.status_code, {"response": response.text})
            data = response.json()
            choice = data["choices"][0]
            return ChatResponse(
                request_id=request.id,
                message=Message(role=Role(choice["message"]["role"]), content=choice["message"]["content"]),
                model=data["model"],
                provider="openai",
                finish_reason=FinishReason(choice["finish_reason"]),
                usage=TokenUsage(prompt_tokens=data["usage"]["prompt_tokens"], completion_tokens=data["usage"]["completion_tokens"]),
                latency_ms=0.0,
                created_at=datetime.datetime.now()
            )

    async def complete(self, request: ChatRequest) -> ChatResponse:
        if not self.circuit_breaker.can_execute():
            raise CircuitOpenError(
                message="Circuit breaker is open - provider unavailable",
                details={"provider": "openai"}
            )
    
        async def attempt():
            return await self._do_completion(request)
 
        
        try:
            result = await self.retry_policy.execute_with_retry(attempt)
            self.circuit_breaker.record_success()
            return result
        except Exception:
            self.circuit_breaker.record_failure()
            raise   

