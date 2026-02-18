import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx

from sentinel.core.circuit_breaker import CircuitBreaker
from sentinel.core.config import get_settings
from sentinel.core.retry import RetryPolicy
from sentinel.domain.exceptions import (
    CircuitOpenError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from sentinel.domain.models import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    Message,
    Role,
    TokenUsage,
)
from sentinel.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI provider."""

    def __init__(self, circuit_breaker: CircuitBreaker, retry_policy: RetryPolicy):
        super().__init__(circuit_breaker, retry_policy)
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        self._api_key = settings.openai_api_key
        self._base_url = settings.openai_base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "openai"

    @property
    def models(self) -> list[str]:
        return ["gpt-4", "gpt-4o", "gpt-4o-mini"]

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream a chat completion from OpenAI with circuit breaker protection."""
        if not self._circuit_breaker.can_execute():
            raise CircuitOpenError(
                message="Circuit breaker is open - provider unavailable",
                details={"provider": "openai"},
            )

        try:
            async for chunk in self._do_stream(request):
                yield chunk
            self._circuit_breaker.record_success()
        except Exception:
            self._circuit_breaker.record_failure()
            raise

    async def _do_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Execute the streaming HTTP call to OpenAI."""
        payload = {
            "model": request.model,
            "messages": [
                {"role": msg.role.value, "content": msg.content} for msg in request.messages
            ],
            "stream": True,
        }
        if request.parameters.temperature is not None:
            payload["temperature"] = request.parameters.temperature
        if request.parameters.max_tokens:
            payload["max_tokens"] = request.parameters.max_tokens
        if request.parameters.top_p:
            payload["top_p"] = request.parameters.top_p
        if request.parameters.stop:
            payload["stop"] = request.parameters.stop

        async with httpx.AsyncClient(base_url=self._base_url) as client:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with client.stream(
                "POST", "/chat/completions", json=payload, headers=headers
            ) as resp:
                if resp.status_code == 429:
                    raise ProviderRateLimitError(
                        "Rate limit exceeded",
                        "openai",
                        429,
                        {"retry_after": resp.headers.get("retry-after", "unknown")},
                    )
                elif resp.status_code == 503:
                    raise ProviderUnavailableError(
                        "OpenAI service unavailable", "openai", 503
                    )
                elif resp.status_code != 200:
                    await resp.aread()
                    raise ProviderError(
                        f"Request failed with status {resp.status_code}",
                        "openai",
                        resp.status_code,
                        {"response": resp.text},
                    )

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(base_url=self._base_url) as client:
                response = await client.get(
                    "/models", headers={"Authorization": f"Bearer {self._api_key}"}
                )
                if response.status_code == 503:
                    raise ProviderUnavailableError("OpenAI service unavailable", "openai", 503)
                return response.status_code == 200
        except (ProviderUnavailableError, ProviderRateLimitError):
            raise
        except Exception as e:
            raise ProviderError(f"Health check failed: {e}", "openai", None) from e

    async def _do_completion(self, request: ChatRequest) -> ChatResponse:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            payload = {
                "model": request.model,
                "messages": [
                    {"role": msg.role.value, "content": msg.content} for msg in request.messages
                ],
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
                raise ProviderRateLimitError(
                    "Rate limit exceeded",
                    "openai",
                    429,
                    {"retry_after": response.headers.get("retry-after", "unknown")},
                )
            elif response.status_code == 503:
                raise ProviderUnavailableError("OpenAI service unavailable", "openai", 503)
            elif response.status_code != 200:
                raise ProviderError(
                    f"Request failed with status {response.status_code}",
                    "openai",
                    response.status_code,
                    {"response": response.text},
                )
            data = response.json()
            choice = data["choices"][0]
            return ChatResponse(
                request_id=request.id,
                message=Message(
                    role=Role(choice["message"]["role"]), content=choice["message"]["content"]
                ),
                model=data["model"],
                provider="openai",
                finish_reason=FinishReason(choice["finish_reason"]),
                usage=TokenUsage(
                    prompt_tokens=data["usage"]["prompt_tokens"],
                    completion_tokens=data["usage"]["completion_tokens"],
                ),
                latency_ms=0.0,
                created_at=datetime.now(UTC),
            )

    async def complete(self, request: ChatRequest) -> ChatResponse:
        if not self._circuit_breaker.can_execute():
            raise CircuitOpenError(
                message="Circuit breaker is open - provider unavailable",
                details={"provider": "openai"},
            )

        try:
            result = await self._retry_policy.execute_with_retry(
                lambda: self._do_completion(request)
            )
            self._circuit_breaker.record_success()
            return result
        except Exception:
            self._circuit_breaker.record_failure()
            raise
