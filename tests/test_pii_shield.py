"""Tests for PII shield."""

from unittest.mock import MagicMock

from sentinel.domain.models import PIIEntity, PIIType
from sentinel.shield.pii_shield import PIIAction, PIIShield


def _make_detector(findings: list[PIIEntity] | None = None):
    """Create a mock PIIDetector returning given findings."""
    detector = MagicMock()
    detector.detect.return_value = findings or []
    detector.detect_in_messages.return_value = {}
    return detector


class TestPIIShield:
    def test_scan_clean_text(self):
        shield = PIIShield(action=PIIAction.WARN, detector=_make_detector([]))
        result = shield.scan_text("Hello world")
        assert not result.findings
        assert result.should_block is False

    def test_scan_detects_email(self):
        findings = [PIIEntity(PIIType.EMAIL, "test@example.com", 0, 16, 0.95)]
        shield = PIIShield(action=PIIAction.WARN, detector=_make_detector(findings))
        result = shield.scan_text("test@example.com")
        assert len(result.findings) == 1
        assert result.findings[0].type == PIIType.EMAIL

    def test_block_mode(self):
        findings = [PIIEntity(PIIType.SSN, "123-45-6789", 0, 11, 0.99)]
        shield = PIIShield(action=PIIAction.BLOCK, detector=_make_detector(findings))
        result = shield.scan_text("123-45-6789")
        assert result.should_block is True

    def test_redact_mode(self):
        text = "Call me at 555-1234"
        findings = [PIIEntity(PIIType.PHONE, "555-1234", 11, 19, 0.9)]
        shield = PIIShield(action=PIIAction.REDACT, detector=_make_detector(findings))
        result = shield.scan_text(text)
        assert result.processed_text is not None
        assert "[PHONE]" in result.processed_text
        assert "555-1234" not in result.processed_text

    def test_scan_messages(self):
        findings = [PIIEntity(PIIType.NAME, "John", 0, 4, 0.8)]
        detector = _make_detector()
        detector.detect_in_messages.return_value = {0: findings}
        shield = PIIShield(action=PIIAction.WARN, detector=detector)
        results = shield.scan_messages([{"role": "user", "content": "John says hi"}])
        assert 0 in results
        assert results[0].findings[0].type == PIIType.NAME

    def test_warn_does_not_block(self):
        findings = [PIIEntity(PIIType.EMAIL, "a@b.com", 0, 7, 0.9)]
        shield = PIIShield(action=PIIAction.WARN, detector=_make_detector(findings))
        result = shield.scan_text("a@b.com")
        assert result.should_block is False
        assert result.processed_text is None
