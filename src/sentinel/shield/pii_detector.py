from dataclasses import dataclass, field

from presidio_analyzer import AnalyzerEngine

from sentinel.domain.models import PIIEntity, PIIType

_DEFAULT_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "DATE_TIME"]

PRESIDIO_ENTITY_TO_PIITYPE = {
    "PERSON": PIIType.NAME,
    "EMAIL_ADDRESS": PIIType.EMAIL,
    "PHONE_NUMBER": PIIType.PHONE,
    "LOCATION": PIIType.ADDRESS,
    "DATE_TIME": PIIType.OTHER,
    "CREDIT_CARD": PIIType.CREDIT_CARD,
    "IP_ADDRESS": PIIType.IP_ADDRESS,
    "US_SSN": PIIType.SSN,
}


def _map_presidio_type(entity: str) -> PIIType:
    """Map a Presidio entity name to our PIIType enum, defaulting to OTHER."""
    return PRESIDIO_ENTITY_TO_PIITYPE.get(entity, PIIType.OTHER)


@dataclass
class PIIDetector:
    """A detector for PII entities in text."""

    score_threshold: float = 0.5
    entities: list[str] = field(default_factory=lambda: _DEFAULT_ENTITIES.copy())

    def __post_init__(self) -> None:
        self._analyzer = AnalyzerEngine()
        supported = set(self._analyzer.get_supported_entities())
        for entity in self.entities:
            if entity not in supported:
                raise ValueError(
                    f"Unsupported PII entity: {entity!r}. "
                    f"Supported entities include: {sorted(supported)}."
                )

    def detect(self, text: str) -> list[PIIEntity]:
        """Detect PII entities in text."""
        if text is None or len(text) == 0:
            return []
        results = self._analyzer.analyze(
            text=text,
            language="en",
            score_threshold=self.score_threshold,
            entities=self.entities,
        )
        return [
            PIIEntity(
                type=_map_presidio_type(r.entity_type),
                text=text[r.start : r.end],
                start=r.start,
                end=r.end,
                confidence=r.score,
            )
            for r in results
        ]

    def detect_in_messages(self, messages: list[dict]) -> dict[int, list[PIIEntity]]:
        """Detect PII in messages. Returns dict mapping message index to findings (only indices with non-empty findings)."""
        out: dict[int, list[PIIEntity]] = {}
        for i, msg in enumerate(messages):
            content = msg.get("content")
            if content is None or (isinstance(content, str) and not content.strip()):
                continue
            if not isinstance(content, str):
                continue
            findings = self.detect(content)
            if findings:
                out[i] = findings
        return out
