"""
Provider-agnostic domain models.

These represent the internal truth of the system.
No external dependencies - only Python standard library.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
