"""Router for multi-provider failover."""

from collections.abc import AsyncIterator

import structlog

from sentinel.domain.exceptions import AllProvidersFailedError, NoProviderError
from sentinel.domain.models import ChatRequest, ChatResponse
from sentinel.providers.base import LLMProvider
from sentinel.providers.registry import ProviderRegistry


class Router:
    """Routes chat requests to providers with failover support."""

    def __init__(
        self,
        registry: ProviderRegistry,
        fallbacks: dict[str, list[str]] | None = None,
    ) -> None:
        self._registry = registry
        self._fallbacks = fallbacks or {}
        self._logger = structlog.get_logger()

    def _resolve_chain(self, model: str) -> list[LLMProvider]:
        """Get the ordered list of providers to try for a model."""
        provider_names = self._fallbacks.get(model)

        if provider_names is None:
            provider_names = self._fallbacks.get("*")

        if provider_names is None:
            provider = self._registry.get_provider_for_model(model)
            if provider is not None:
                return [provider]
            return []

        providers = []
        for name in provider_names:
            provider = self._registry.get_provider(name)
            if provider is not None:
                providers.append(provider)
            else:
                self._logger.warning("provider_not_found", provider=name)
        return providers

    async def route(self, request: ChatRequest) -> ChatResponse:
        """Route the request through the fallback chain until success or all fail."""
        chain = self._resolve_chain(request.model)

        if not chain:
            raise NoProviderError(f"No providers for model: {request.model!r}")

        errors: list[tuple[str, Exception]] = []
        for provider in chain:
            if not provider.is_available():
                self._logger.debug(
                    "provider_skipped", provider=provider.name, reason="circuit_breaker_open"
                )
                continue

            try:
                self._logger.debug(
                    "provider_attempting", provider=provider.name, model=request.model
                )
                response = await provider.complete(request)
                if errors:
                    self._logger.info(
                        "provider_failover_succeeded",
                        provider=provider.name,
                        fallback_count=len(errors),
                    )
                return response
            except Exception as exc:
                errors.append((provider.name, exc))
                self._logger.warning(
                    "provider_failed",
                    provider=provider.name,
                    model=request.model,
                    error=str(exc),
                )
                continue

        raise AllProvidersFailedError(errors)

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream the request through the fallback chain until success or all fail."""
        chain = self._resolve_chain(request.model)

        if not chain:
            raise NoProviderError(f"No providers for model: {request.model!r}")

        errors: list[tuple[str, Exception]] = []
        for provider in chain:
            if not provider.is_available():
                self._logger.debug(
                    "provider_skipped", provider=provider.name, reason="circuit_breaker_open"
                )
                continue

            try:
                self._logger.debug(
                    "provider_attempting", provider=provider.name, model=request.model
                )
                async for chunk in provider.stream(request):
                    yield chunk
                if errors:
                    self._logger.info(
                        "provider_failover_succeeded",
                        provider=provider.name,
                        fallback_count=len(errors),
                    )
                return
            except Exception as exc:
                errors.append((provider.name, exc))
                self._logger.warning(
                    "provider_failed",
                    provider=provider.name,
                    model=request.model,
                    error=str(exc),
                )
                continue

        raise AllProvidersFailedError(errors)
