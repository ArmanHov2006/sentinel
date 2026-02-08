"""Tests for domain models and exceptions."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("openai_api_key", "test-key-for-testing")

from sentinel.domain.exceptions import (
    CircuitOpenError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    SentinelError,
)
from sentinel.domain.models import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    Message,
    ModelParameters,
    PIIEntity,
    PIIType,
    Role,
    TokenUsage,
)

# =============================================================================
# ENUM TESTS
# =============================================================================


class TestPIIType:
    def test_equals_string(self):
        assert PIIType.EMAIL == "email"
        assert PIIType.PHONE == "phone"
        assert PIIType.SSN == "ssn"
        assert PIIType.CREDIT_CARD == "credit_card"

    def test_all_values(self):
        assert len(PIIType) == 8


class TestRole:
    def test_equals_string(self):
        assert Role.USER == "user"
        assert Role.ASSISTANT == "assistant"
        assert Role.SYSTEM == "system"
        assert Role.TOOL == "tool"


class TestFinishReason:
    def test_equals_string(self):
        assert FinishReason.STOP == "stop"
        assert FinishReason.LENGTH == "length"
        assert FinishReason.ERROR == "error"


# =============================================================================
# MODEL TESTS
# =============================================================================


class TestMessage:
    def test_creation(self):
        msg = Message(role=Role.USER, content="Hello")
        assert msg.role == Role.USER
        assert msg.content == "Hello"

    def test_is_frozen(self):
        msg = Message(role=Role.USER, content="Hello")
        with pytest.raises(Exception):
            msg.content = "changed"


class TestPIIEntity:
    def test_creation(self):
        pii = PIIEntity(
            type=PIIType.EMAIL, text="test@example.com", start=0, end=16, confidence=0.95
        )
        assert pii.type == PIIType.EMAIL
        assert pii.text == "test@example.com"
        assert pii.start == 0
        assert pii.end == 16
        assert pii.confidence == 0.95

    def test_is_frozen(self):
        pii = PIIEntity(PIIType.EMAIL, "test@test.com", 0, 13, 0.9)
        with pytest.raises(Exception):
            pii.text = "changed"


class TestModelParameters:
    def test_defaults(self):
        params = ModelParameters()
        assert params.temperature == 1.0
        assert params.max_tokens is None

    def test_custom(self):
        params = ModelParameters(temperature=0.5, max_tokens=100, top_p=0.9)
        assert params.temperature == 0.5
        assert params.max_tokens == 100
        assert params.top_p == 0.9


class TestTokenUsage:
    def test_total_tokens(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20)
        assert usage.total_tokens == 30


class TestChatRequest:
    def test_defaults(self):
        req = ChatRequest()
        assert req.id is not None
        assert req.messages == []
        assert req.model == ""

    def test_with_values(self):
        msg = Message(role=Role.USER, content="Hi")
        req = ChatRequest(model="gpt-4", messages=[msg])
        assert req.model == "gpt-4"
        assert len(req.messages) == 1


class TestChatResponse:
    def test_creation(self):
        resp = ChatResponse(
            request_id="req-1",
            message=Message(role=Role.ASSISTANT, content="Hello"),
            model="gpt-4",
            provider="openai",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(prompt_tokens=5, completion_tokens=10),
            latency_ms=123.4,
        )
        assert resp.request_id == "req-1"
        assert resp.message.content == "Hello"
        assert resp.usage.total_tokens == 15


# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestSentinelError:
    def test_creation(self):
        error = SentinelError("Something broke")
        assert error.message == "Something broke"
        assert error.details == {}

    def test_with_details(self):
        error = SentinelError("Failed", details={"key": "value"})
        assert error.details == {"key": "value"}

    def test_to_dict(self):
        error = SentinelError("Test")
        d = error.to_dict()
        assert d["message"] == "Test"
        assert d["type"] == "SentinelError"


class TestProviderError:
    def test_creation(self):
        error = ProviderError("API failed", provider="openai", status_code=500)
        assert error.provider == "openai"
        assert error.status_code == 500
        assert isinstance(error, SentinelError)

    def test_subclasses(self):
        assert issubclass(ProviderUnavailableError, ProviderError)
        assert issubclass(ProviderRateLimitError, ProviderError)


class TestCircuitOpenError:
    def test_is_sentinel_error(self):
        error = CircuitOpenError("Circuit open")
        assert isinstance(error, SentinelError)
        assert error.message == "Circuit open"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
