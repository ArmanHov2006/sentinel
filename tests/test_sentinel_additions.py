"""Tests for Sentinel-specific additions."""

import os
import sys
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Set required environment variable for testing
os.environ.setdefault("openai_api_key", "test-key-for-testing")

from sentinel.domain.models import (
    GuardrailAction,
    PIIType,
    PIIEntity,
    GuardrailResult,
    JudgeScore,
    StreamChunk,
    FinishReason,
)
from sentinel.domain.exceptions import (
    GuardrailError,
    ContentBlockedError,
    PIIDetectedError,
    CacheError,
    CacheConnectionError,
    CacheSerializationError,
    SentinelError,
)


# =============================================================================
# ENUM TESTS
# =============================================================================

class TestGuardrailAction:
    def test_equals_string(self):
        assert GuardrailAction.ALLOW == "allow"
        assert GuardrailAction.BLOCK == "block"
        assert GuardrailAction.REDACT == "redact"
        assert GuardrailAction.WARN == "warn"


class TestPIIType:
    def test_equals_string(self):
        assert PIIType.EMAIL == "email"
        assert PIIType.PHONE == "phone"
        assert PIIType.SSN == "ssn"
        assert PIIType.CREDIT_CARD == "credit_card"


# =============================================================================
# MODEL TESTS
# =============================================================================

class TestPIIEntity:
    def test_creation(self):
        pii = PIIEntity(
            type=PIIType.EMAIL,
            text="test@example.com",
            start=0,
            end=16,
            confidence=0.95
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


class TestGuardrailResult:
    def test_allow_action(self):
        result = GuardrailResult(action=GuardrailAction.ALLOW)
        assert result.action == GuardrailAction.ALLOW
        assert result.pii_detected == []
        assert result.banned_keywords_found == []
        assert result.processed_content is None
        assert result.reason is None
    
    def test_block_with_pii(self):
        pii = PIIEntity(
            type=PIIType.SSN,
            text="123-45-6789",
            start=10,
            end=21,
            confidence=0.99
        )
        result = GuardrailResult(
            action=GuardrailAction.BLOCK,
            pii_detected=[pii],
            reason="SSN detected"
        )
        assert result.action == GuardrailAction.BLOCK
        assert len(result.pii_detected) == 1
        assert result.pii_detected[0].type == PIIType.SSN
        assert result.reason == "SSN detected"
    
    def test_redact_with_processed_content(self):
        result = GuardrailResult(
            action=GuardrailAction.REDACT,
            pii_detected=[PIIEntity(PIIType.EMAIL, "a@b.com", 0, 7, 0.9)],
            processed_content="Contact me at [EMAIL_REDACTED]"
        )
        assert result.processed_content == "Contact me at [EMAIL_REDACTED]"
    
    def test_with_banned_keywords(self):
        result = GuardrailResult(
            action=GuardrailAction.BLOCK,
            banned_keywords_found=["ignore instructions", "jailbreak"]
        )
        assert len(result.banned_keywords_found) == 2


class TestJudgeScore:
    def test_creation_with_defaults(self):
        score = JudgeScore(request_id="req-123")
        assert score.request_id == "req-123"
        assert score.relevance == 0.0
        assert score.coherence == 0.0
        assert score.safety == 0.0
        assert score.overall_score == 0.0
        assert score.hallucination_detected is False
        assert score.toxic_content_detected is False
        assert score.judge_model == "gpt-4o-mini"
    
    def test_creation_with_values(self):
        score = JudgeScore(
            request_id="req-456",
            relevance=0.95,
            coherence=0.88,
            safety=1.0,
            overall_score=0.94,
            hallucination_detected=False,
            toxic_content_detected=False
        )
        assert score.relevance == 0.95
        assert score.overall_score == 0.94
    
    def test_hallucination_flag(self):
        score = JudgeScore(
            request_id="req-789",
            hallucination_detected=True,
            overall_score=0.3
        )
        assert score.hallucination_detected is True
    
    def test_has_timestamp(self):
        score = JudgeScore(request_id="req-abc")
        assert score.created_at is not None


class TestStreamChunk:
    def test_content_only(self):
        chunk = StreamChunk(content="Hello")
        assert chunk.content == "Hello"
        assert chunk.finish_reason is None
    
    def test_with_finish_reason(self):
        chunk = StreamChunk(content="", finish_reason=FinishReason.STOP)
        assert chunk.finish_reason == FinishReason.STOP
    
    def test_to_sse_format(self):
        chunk = StreamChunk(content="Hello")
        sse = chunk.to_sse()
        
        # Check format
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        
        # Check content
        assert '"content": "Hello"' in sse
        assert '"finish_reason": null' in sse
    
    def test_to_sse_with_finish_reason(self):
        chunk = StreamChunk(content="", finish_reason=FinishReason.STOP)
        sse = chunk.to_sse()
        assert '"finish_reason": "stop"' in sse
    
    def test_is_frozen(self):
        chunk = StreamChunk(content="test")
        with pytest.raises(Exception):
            chunk.content = "changed"


# =============================================================================
# EXCEPTION TESTS
# =============================================================================

class TestGuardrailError:
    def test_is_sentinel_error(self):
        error = GuardrailError("Blocked")
        assert isinstance(error, SentinelError)


class TestContentBlockedError:
    def test_creation(self):
        error = ContentBlockedError(
            message="Content blocked",
            reason="banned_keyword"
        )
        assert error.message == "Content blocked"
        assert error.reason == "banned_keyword"
        assert isinstance(error, GuardrailError)
    
    def test_to_dict(self):
        error = ContentBlockedError("Blocked", reason="pii")
        d = error.to_dict()
        assert "message" in d
        assert d["message"] == "Blocked"
        assert d["reason"] == "pii"


class TestPIIDetectedError:
    def test_creation(self):
        error = PIIDetectedError(
            message="PII detected in request",
            pii_types=["email", "ssn"]
        )
        assert error.pii_types == ["email", "ssn"]
        assert error.reason == "pii_detected"
    
    def test_inheritance(self):
        error = PIIDetectedError("PII found", pii_types=["phone"])
        assert isinstance(error, ContentBlockedError)
        assert isinstance(error, GuardrailError)
        assert isinstance(error, SentinelError)
    
    def test_to_dict(self):
        error = PIIDetectedError("Found PII", pii_types=["email", "name"])
        d = error.to_dict()
        assert d["pii_types"] == ["email", "name"]
        assert d["reason"] == "pii_detected"


class TestCacheError:
    def test_is_sentinel_error(self):
        error = CacheError("Redis down")
        assert isinstance(error, SentinelError)
    
    def test_cache_connection_error(self):
        error = CacheConnectionError("Connection failed")
        assert isinstance(error, CacheError)
        assert isinstance(error, SentinelError)
    
    def test_cache_serialization_error(self):
        error = CacheSerializationError("Serialize failed")
        assert isinstance(error, CacheError)
        assert isinstance(error, SentinelError)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
