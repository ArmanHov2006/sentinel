from src.sentinel.providers.base import LLMProvider
from src.sentinel.domain.models import (
    ChatRequest, 
    ChatResponse, 
    Message, 
    Role, 
    FinishReason, 
    TokenUsage
)
from src.sentinel.domain.exceptions import (
    CircuitOpenError,
    ProviderError,
    ProviderUnavailableError,
    ProviderRateLimitError
)
from src.sentinel.core.circuit_breaker import CircuitBreaker
import httpx
import datetime

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.circuit_breaker = CircuitBreaker()

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

async def complete(self, request: ChatRequest) -> ChatResponse:
    if not self.circuit_breaker.can_execute():
        raise CircuitOpenError(
            message="Circuit breaker is open - provider unavailable",
            provider="openai"
        )
    try:
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
                self.circuit_breaker.record_failure()  # Provider issue!
                raise ProviderRateLimitError(
                    "Rate limit exceeded",
                    "openai",
                    429,
                    {"retry_after": response.headers.get("retry-after", "unknown")}
                )
            elif response.status_code == 503:
                self.circuit_breaker.record_failure()  # Provider issue!
                raise ProviderUnavailableError("OpenAI service unavailable", "openai", 503)
            elif response.status_code != 200:
                # 4xx errors (except 429) are usually client errors, not provider issues
                raise ProviderError(
                    f"Request failed with status {response.status_code}",
                    "openai",
                    response.status_code,
                    {"response": response.text}
                )
            data = response.json()
            choice = data["choices"][0]
            self.circuit_breaker.record_success()
            
            return ChatResponse(
                request_id=request.id,
                message=Message(
                    role=Role(choice["message"]["role"]),
                    content=choice["message"]["content"]
                ),
                model=data["model"],
                provider="openai",
                finish_reason=FinishReason(choice["finish_reason"]),
                usage=TokenUsage(
                    prompt_tokens=data["usage"]["prompt_tokens"],
                    completion_tokens=data["usage"]["completion_tokens"]
                ),
                latency_ms=0.0,
                created_at=datetime.datetime.now()
            )
    except httpx.RequestError as e:
        self.circuit_breaker.record_failure()  # Network issue = provider issue
        raise ProviderUnavailableError(f"Network error: {e}", "openai", None)
    except (ProviderUnavailableError, ProviderRateLimitError, ProviderError) as e:
        raise e