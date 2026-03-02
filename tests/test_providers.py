"""Tests for LLM providers."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from sentinel.core.circuit_breaker import CircuitBreaker
from sentinel.core.retry import RetryPolicy
from sentinel.domain.models import ChatRequest, Message, Role

pytestmark = pytest.mark.anyio


def _mock_openai_settings():
    m = MagicMock()
    m.openai_api_key = "sk-test"
    m.openai_base_url = "https://api.openai.com/v1"
    return m


def _mock_anthropic_settings():
    m = MagicMock()
    m.anthropic_api_key = "test-key"
    m.anthropic_base_url = "https://api.anthropic.com/v1"
    return m


def _chat_request(model="gpt-4o-mini"):
    return ChatRequest(
        messages=[Message(role=Role.USER, content="Hello")],
        model=model,
    )


class TestOpenAIProvider:
    @respx.mock
    async def test_complete_success(self):
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "Hi there!"},
                            "finish_reason": "stop",
                        }
                    ],
                    "model": "gpt-4o-mini",
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                },
            )
        )

        with patch("sentinel.providers.openai.get_settings", return_value=_mock_openai_settings()):
            from sentinel.providers.openai import OpenAIProvider

            provider = OpenAIProvider(CircuitBreaker(), RetryPolicy(base_delay=0.01))

        resp = await provider.complete(_chat_request())
        assert resp.message.content == "Hi there!"
        assert resp.provider == "openai"
        assert resp.usage.prompt_tokens == 5

    @respx.mock
    async def test_complete_opens_circuit_after_failures(self):
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        cb = CircuitBreaker(failure_threshold=2)
        with patch("sentinel.providers.openai.get_settings", return_value=_mock_openai_settings()):
            from sentinel.providers.openai import OpenAIProvider

            provider = OpenAIProvider(cb, RetryPolicy(max_attempts=1, base_delay=0.01))

        for _ in range(2):
            with pytest.raises(Exception):
                await provider.complete(_chat_request())

        assert not cb.can_execute()

    @respx.mock
    async def test_complete_rate_limit_429(self):
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(429, text="Rate limited")
        )

        with patch("sentinel.providers.openai.get_settings", return_value=_mock_openai_settings()):
            from sentinel.providers.openai import OpenAIProvider

            provider = OpenAIProvider(
                CircuitBreaker(), RetryPolicy(max_attempts=1, base_delay=0.01)
            )

        from sentinel.domain.exceptions import ProviderRateLimitError

        with pytest.raises(ProviderRateLimitError):
            await provider.complete(_chat_request())


class TestAnthropicProvider:
    def test_system_message_extraction(self):
        with patch(
            "sentinel.providers.anthropic.get_settings",
            return_value=_mock_anthropic_settings(),
        ):
            from sentinel.providers.anthropic import AnthropicProvider

            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy())

        messages = [
            Message(role=Role.SYSTEM, content="Be helpful"),
            Message(role=Role.USER, content="Hi"),
        ]
        system, conv = provider._prepare_messages(messages)
        assert system == "Be helpful"
        assert conv == [{"role": "user", "content": "Hi"}]

    @respx.mock
    async def test_complete_maps_response(self):
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "Hello from Claude!"}],
                    "model": "claude-haiku-4-20250514",
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 5, "output_tokens": 4},
                },
            )
        )

        with patch(
            "sentinel.providers.anthropic.get_settings",
            return_value=_mock_anthropic_settings(),
        ):
            from sentinel.providers.anthropic import AnthropicProvider

            provider = AnthropicProvider(CircuitBreaker(), RetryPolicy(base_delay=0.01))

        resp = await provider.complete(_chat_request("claude-haiku-4-20250514"))
        assert resp.message.content == "Hello from Claude!"
        assert resp.provider == "anthropic"
