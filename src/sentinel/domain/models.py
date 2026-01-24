"""
Provider-agnostic domain models.

These represent the internal truth of the system.
No external dependencies - only Python standard library.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class Role(str, Enum):
    """Message roles in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(str, Enum):
    """Why the model stopped generating."""
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


@dataclass(frozen=True)
class Message:
    """A single message. Frozen to prevent modification after creation."""
    role: Role
    content: str


@dataclass(frozen=True)
class ModelParameters:
    """Generation parameters. Frozen for consistency."""
    temperature: float = 1.0
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None


@dataclass
class ChatRequest:
    """Internal representation of a chat request."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[Message] = field(default_factory=list)
    model: str = ""
    parameters: ModelParameters = field(default_factory=ModelParameters)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenUsage:
    """Token consumption for a request."""
    prompt_tokens: int
    completion_tokens: int
    
    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ChatResponse:
    """Internal representation of a chat response."""
    request_id: str
    message: Message
    model: str
    provider: str
    finish_reason: FinishReason
    usage: TokenUsage
    latency_ms: float
    created_at: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# GUARDRAIL MODELS
# =============================================================================

class GuardrailAction(str, Enum):
    """What to do when guardrail triggers."""
    ALLOW = "allow"       # Let it through
    BLOCK = "block"       # Stop the request
    REDACT = "redact"     # Remove sensitive content
    WARN = "warn"         # Allow but log warning


class PIIType(str, Enum):
    """Types of PII we detect."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    ADDRESS = "address"
    IP_ADDRESS = "ip_address"
    OTHER = "other"


@dataclass(frozen=True)
class PIIEntity:
    """A detected PII entity in text."""
    type: PIIType
    text: str
    start: int
    end: int
    confidence: float


@dataclass
class GuardrailResult:
    """Result of running guardrails on a request."""
    action: GuardrailAction
    pii_detected: list[PIIEntity] = field(default_factory=list)
    banned_keywords_found: list[str] = field(default_factory=list)
    processed_content: str | None = None
    reason: str | None = None


# =============================================================================
# JUDGE & STREAMING MODELS
# =============================================================================

def _utc_now() -> datetime:
    """Helper function for UTC now."""
    return datetime.now(timezone.utc)


@dataclass
class JudgeScore:
    """
    Evaluation score from the Judge model.
    Runs async after response is sent to user.
    """
    request_id: str
    
    # Scores (0.0 to 1.0)
    relevance: float = 0.0
    coherence: float = 0.0
    safety: float = 0.0
    overall_score: float = 0.0
    
    # Flags
    hallucination_detected: bool = False
    toxic_content_detected: bool = False
    
    # Metadata
    judge_model: str = "gpt-4o-mini"
    latency_ms: float = 0.0
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class StreamChunk:
    """A single chunk in a streaming response."""
    content: str
    finish_reason: FinishReason | None = None
    
    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        import json
        data = {
            "choices": [{
                "delta": {"content": self.content},
                "finish_reason": self.finish_reason.value if self.finish_reason else None
            }]
        }
        return f"data: {json.dumps(data)}\n\n"