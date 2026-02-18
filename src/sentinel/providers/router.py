"""Router for multi-provider failover."""

import logging
from collections.abc import AsyncIterator

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
        self._logger = logging.getLogger(__name__)

    def _resolve_chain(self, model: str) -> list[LLMProvider]:
        """Get the ordered list of providers to try for a model."""
        # Check for exact model match first
        provider_names = self._fallbacks.get(model)

        # Fall back to wildcard
        if provider_names is None:
            provider_names = self._fallbacks.get("*")

        # If neither exists, try registry.get_provider_for_model as single-provider chain
        if provider_names is None:
            provider = self._registry.get_provider_for_model(model)
            if provider is not None:
                return [provider]
            return []

        # Resolve names to provider instances via registry
        providers = []
        for name in provider_names:
            provider = self._registry.get_provider(name)
            if provider is not None:
                providers.append(provider)
            else:
                self._logger.warning("Provider '%s' not found in registry", name)
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
                    "Skipping provider '%s' (circuit breaker open)",
                    provider.name,
                )
                continue

            try:
                self._logger.debug(
                    "Attempting provider '%s' for model %s",
                    provider.name,
                    request.model,
                )
                response = await provider.complete(request)
                if errors:
                    self._logger.info(
                        "Routed to '%s' after %d fallback(s)",
                        provider.name,
                        len(errors),
                    )
                return response
            except Exception as exc:
                errors.append((provider.name, exc))
                self._logger.warning(
                    "Provider '%s' failed for model %s: %s",
                    provider.name,
                    request.model,
                    exc,
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
                    "Skipping provider '%s' (circuit breaker open)",
                    provider.name,
                )
                continue

            try:
                self._logger.debug(
                    "Attempting provider '%s' for model %s",
                    provider.name,
                    request.model,
                )
                async for chunk in provider.stream(request):
                    yield chunk
                if errors:
                    self._logger.info(
                        "Streamed from '%s' after %d fallback(s)",
                        provider.name,
                        len(errors),
                    )
                return
            except Exception as exc:
                errors.append((provider.name, exc))
                self._logger.warning(
                    "Provider '%s' failed for model %s: %s",
                    provider.name,
                    request.model,
                    exc,
                )
                continue

        raise AllProvidersFailedError(errors)
