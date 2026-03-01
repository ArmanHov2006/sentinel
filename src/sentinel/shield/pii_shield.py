"""PII shield that scans, blocks, redacts, or warns on detected PII."""

from dataclasses import dataclass
from enum import Enum

from sentinel.domain.models import PIIEntity
from sentinel.shield.pii_detector import PIIDetector


class PIIAction(Enum):
    """Actions to take when a PII entity is detected."""

    BLOCK = "block"
    REDACT = "redact"
    WARN = "warn"


@dataclass
class PIIResult:
    """Result of running PII shield on a request."""

    action: PIIAction
    findings: list[PIIEntity]
    processed_text: str | None = None
    should_block: bool = False


@dataclass
class PIIShield:
    """A shield for PII entities in text and messages."""

    action: PIIAction
    detector: PIIDetector | None = None

    def __post_init__(self) -> None:
        self._detector = self.detector if self.detector is not None else PIIDetector()

    def scan_text(self, text: str) -> PIIResult:
        """Scan text for PII. Returns PIIResult with findings, should_block, and processed_text=None for now."""
        findings = self._detector.detect(text)
        if not findings:
            return PIIResult(
                action=self.action,
                findings=[],
                processed_text=None,
                should_block=False,
            )
        should_block = self.action == PIIAction.BLOCK
        if self.action == PIIAction.REDACT:
            processed_text = self._redact_text(text, findings)
        else:
            processed_text = None
        return PIIResult(
            action=self.action,
            findings=findings,
            processed_text=processed_text,
            should_block=should_block,
        )

    def scan_messages(self, messages: list[dict]) -> dict[int, PIIResult]:
        """Scan messages for PII. Returns dict mapping message index to PIIResult (only indices where PII was found)."""
        out: dict[int, PIIResult] = {}
        index_to_findings = self._detector.detect_in_messages(messages)
        for i, findings in index_to_findings.items():
            should_block = self.action == PIIAction.BLOCK
            if self.action == PIIAction.REDACT:
                processed_text = self._redact_text(messages[i].get("content", ""), findings)
            else:
                processed_text = None
            out[i] = PIIResult(
                action=self.action,
                findings=findings,
                processed_text=processed_text,
                should_block=should_block,
            )
        return out

    def _redact_text(self, text: str, findings: list[PIIEntity]) -> str:
        """Redact text for PII entities."""
        replacements = []
        for finding in findings:
            replacements.append((finding.start, finding.end, finding.type.value))
        for start, end, pii_type in sorted(replacements, key=lambda x: x[0], reverse=True):
            text = text[:start] + f"[{pii_type.upper()}]" + text[end:]
        return text
