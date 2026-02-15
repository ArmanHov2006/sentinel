"""Tests for AnthropicProvider."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sentinel.providers.anthropic import AnthropicProvider
from sentinel.core.circuit_breaker import CircuitBreaker
from sentinel.core.retry import RetryPolicy
from sentinel.domain.models import Message, Role, FinishReason


def _make_mock_settings(api_key: str = "test-key", base_url: str = "https://api.anthropic.com/v1"):
    mock = MagicMock()
    mock.anthropic_api_key = api_key
    mock.anthropic_base_url = base_url
    return mock


class TestAnthropicProvider:
    """Test suite for AnthropicProvider."""

    def test_init_requires_api_key(self):
        """Should raise ValueError if ANTHROPIC_API_KEY is not set."""
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings(api_key=None)):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not set"):
                AnthropicProvider(CircuitBreaker(), RetryPolicy())
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings(api_key="")):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not set"):
                AnthropicProvider(CircuitBreaker(), RetryPolicy())

    def test_provider_name(self):
        """Provider name should be 'anthropic'."""
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings()):
            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy())
        assert provider.name == "anthropic"

    def test_provider_models(self):
        """Provider should list Claude models."""
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings()):
            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy())
        assert "claude-sonnet-4-20250514" in provider.models
        assert "claude-haiku-4-20250514" in provider.models
        assert len(provider.models) == 2

    def test_prepare_messages_extracts_system(self):
        """System messages should be extracted to separate field."""
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings()):
            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy())
        messages = [
            Message(role=Role.SYSTEM, content="You are helpful."),
            Message(role=Role.USER, content="Hi"),
        ]
        system_prompt, conversation_messages = provider._prepare_messages(messages)
        assert system_prompt == "You are helpful."
        assert conversation_messages == [{"role": "user", "content": "Hi"}]

    def test_prepare_messages_no_system(self):
        """Should return None for system when no system messages."""
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings()):
            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy())
        messages = [Message(role=Role.USER, content="Hi")]
        system_prompt, conversation_messages = provider._prepare_messages(messages)
        assert system_prompt is None
        assert conversation_messages == [{"role": "user", "content": "Hi"}]

    def test_map_finish_reason_end_turn(self):
        """'end_turn' should map to STOP."""
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings()):
            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy())
        assert provider._map_finish_reason("end_turn") == FinishReason.STOP

    def test_map_finish_reason_max_tokens(self):
        """'max_tokens' should map to LENGTH."""
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings()):
            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy())
        assert provider._map_finish_reason("max_tokens") == FinishReason.LENGTH

    def test_map_finish_reason_unknown(self):
        """Unknown values should map to ERROR."""
        with patch("sentinel.providers.anthropic.get_settings", return_value=_make_mock_settings()):
            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy())
        assert provider._map_finish_reason("unknown_thing") == FinishReason.ERROR
