"""Provider registry for routing requests to the appropriate LLM provider."""

import logging

from sentinel.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry of LLM providers for model-based routing."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._model_map: dict[str, str] = {}

    def __len__(self) -> int:
        """Return the number of registered providers."""
        return len(self._providers)

    def __contains__(self, name: str) -> bool:
        """Return True if the provider is registered."""
        return name in self._providers

    def register(self, provider: LLMProvider) -> None:
        """Register a provider."""
        if provider.name in self._providers:
            logger.warning(
                "Provider '%s' already registered, overwriting",
                provider.name,
            )
            # Remove old provider's models from model map
            for model, prov_name in list(self._model_map.items()):
                if prov_name == provider.name:
                    del self._model_map[model]

        self._providers[provider.name] = provider
        for model in provider.models:
            self._model_map[model] = provider.name

        logger.info(
            "Registered provider '%s' with %d model(s)",
            provider.name,
            len(provider.models),
        )

    def get_provider(self, name: str) -> LLMProvider | None:
        """Look up by provider name, return None if not found."""
        return self._providers.get(name)

    def get_provider_for_model(self, model: str) -> LLMProvider | None:
        """Look up which provider handles a model, return the provider instance or None."""
        prov_name = self._model_map.get(model)
        if prov_name is None:
            return None
        return self._providers.get(prov_name)

    def list_available(self) -> list[LLMProvider]:
        """Return all providers where is_available() is True."""
        return [p for p in self._providers.values() if p.is_available()]

    def list_models(self) -> list[str]:
        """Return all registered model names."""
        return list(self._model_map.keys())

    def list_providers(self) -> list[LLMProvider]:
        """Return all registered providers."""
        return list(self._providers.values())
