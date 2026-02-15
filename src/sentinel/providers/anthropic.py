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


class AnthropicProvider(LLMProvider):
    """Anthropic provider."""

    def __init__(self, circuit_breaker: CircuitBreaker, retry_policy: RetryPolicy):
        super().__init__(circuit_breaker, retry_policy)
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self._api_key = settings.anthropic_api_key
        self._base_url = settings.anthropic_base_url.rstrip("/")

    def _map_finish_reason(self, stop_reason: str) -> FinishReason:
        """Map Anthropic stop_reason to internal FinishReason."""
        mapping = {
            "end_turn": FinishReason.STOP,
            "max_tokens": FinishReason.LENGTH,
            "stop_sequence": FinishReason.STOP,
        }
        return mapping.get(stop_reason, FinishReason.ERROR)

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def models(self) -> list[str]:
        return ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(base_url=self._base_url) as client:
                headers = {
                    "x-api-key": self._api_key,
                    "anthropic-version": "2025-04-14",
                    "content-type": "application/json",
                }
                payload = {
                    "model": "claude-haiku-4-20250514",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                }
                response = await client.post("/messages", json=payload, headers=headers)
                if response.status_code == 429:
                    raise ProviderRateLimitError(
                        "Rate limit exceeded",
                        "anthropic",
                        429,
                        {"retry_after": response.headers.get("retry-after", "unknown")},
                    )
                if response.status_code == 503:
                    raise ProviderUnavailableError(
                        "Anthropic service unavailable", "anthropic", 503
                    )
                if response.status_code != 200:
                    raise ProviderError(
                        f"Health check failed with status {response.status_code}: {response.text}",
                        "anthropic",
                        response.status_code,
                        {"response": response.text},
                    )
                return True
        except (ProviderUnavailableError, ProviderRateLimitError):
            raise
        except Exception as e:
            raise ProviderError(f"Health check failed: {e}", "anthropic", None) from e

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        raise NotImplementedError("Stream method not implemented")

    async def complete(self, request: ChatRequest) -> ChatResponse:
        if not self._circuit_breaker.can_execute():
            raise CircuitOpenError(
                message="Circuit breaker is open - provider unavailable",
                details={"provider": "anthropic"},
            )

        try:
            result = await self._retry_policy.execute_with_retry(
                lambda: self._do_completion(request)
            )
            self._circuit_breaker.record_success()
        except Exception:
            self._circuit_breaker.record_failure()
            raise
        return result

    def _prepare_messages(self, messages: list[Message]) -> tuple[str | None, list[dict[str, str]]]:
        """
        Separate system messages from conversation messages.

        Returns:
            tuple of (system_prompt, conversation_messages)
            - system_prompt: Combined system messages, or None if there are none
            - conversation_messages: List of {"role": ..., "content": ...} dicts
        """
        system_prompts = []
        conversation_messages = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_prompts.append(msg.content)
            else:
                conversation_messages.append({"role": msg.role.value, "content": msg.content})
        system_prompt = None if not system_prompts else "\n".join(system_prompts)
        return system_prompt, conversation_messages

    async def _do_completion(self, request: ChatRequest) -> ChatResponse:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            headers = {
                "x-api-key": self._api_key,
                "anthropic-version": "2025-04-14",
                "content-type": "application/json",
            }
            system_prompt, conversation_messages = self._prepare_messages(request.messages)

            payload = {
                "model": request.model,
                "messages": conversation_messages,
                "max_tokens": request.parameters.max_tokens or 1024,
            }
            if request.parameters.temperature is not None:
                payload["temperature"] = request.parameters.temperature

            if request.parameters.top_p is not None:
                payload["top_p"] = request.parameters.top_p

            if request.parameters.stop:
                payload["stop_sequences"] = request.parameters.stop
            if system_prompt:
                payload["system"] = system_prompt

            response = await client.post("/messages", json=payload, headers=headers)
            if response.status_code == 429:
                raise ProviderRateLimitError(
                    "Rate limit exceeded",
                    "anthropic",
                    429,
                    {"retry_after": response.headers.get("retry-after", "unknown")},
                )
            elif response.status_code == 503:
                raise ProviderUnavailableError("Anthropic service unavailable", "anthropic", 503)
            elif response.status_code != 200:
                raise ProviderError(
                    f"Request failed with status {response.status_code}",
                    "anthropic",
                    response.status_code,
                    {"response": response.text},
                )
            data = response.json()

            return ChatResponse(
                request_id=request.id,
                message=Message(
                    role=Role.ASSISTANT,
                    content=data["content"][0]["text"],
                ),
                model=data["model"],
                provider="anthropic",
                finish_reason=self._map_finish_reason(data["stop_reason"]),
                usage=TokenUsage(
                    prompt_tokens=data["usage"]["input_tokens"],
                    completion_tokens=data["usage"]["output_tokens"],
                ),
                latency_ms=0.0,
                created_at=datetime.now(UTC),
            )
