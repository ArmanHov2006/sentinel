"""
Judge evaluation models.

Domain types for LLM-as-judge results. No external dependencies —
only Python standard library.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

class JudgeDimension(str, Enum):
    """Evaluation dimension or criterion the judge scored."""

    RELEVANCE = "relevance"
    SAFETY = "safety"
    COHERENCE = "coherence"
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"

    
@dataclass(frozen=True)
class JudgeResult:
    """Result of an LLM-as-judge evaluation."""
    dimensions: dict[JudgeDimension, float] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    reasoning: str = ""
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    default_score_threshold: float = 6.0

    @property
    def passed(self) -> bool:
        """Whether the evaluation passed."""
        return all(score >= self.default_score_threshold for score in self.dimensions.values()) and len(self.flags) == 0

    def to_dict(self) -> dict:
        """Convert the result to a dictionary.
        Used for JSON serialization.
        """
        return {
            "dimensions": {dimension.value: score for dimension, score in self.dimensions.items()},
            "flags": self.flags,
            "passed": self.passed,
            "reasoning": self.reasoning,
            "evaluated_at": self.evaluated_at.isoformat(),
        }