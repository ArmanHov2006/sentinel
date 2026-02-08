"""
Prompt injection detector.

Scans user messages for common prompt injection patterns using
weighted regex rules. Returns a risk score and recommendation.

Design decisions:
- Rules compile at module load (once), not per-request
- Detector is a regular class (not dataclass) because it's a service, not data
- ScanResult is a dataclass because it IS data
- Ordering: dependencies defined before things that use them
- Fail-open: if scanning crashes, request is allowed through
"""

import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum


# ── 1. Enum ──────────────────────────────────────────────────────────────────
# First because ScanResult and Detector both reference it.
# (str, Enum) so values work naturally in JSON, logging, string comparisons.

class InjectionAction(str, Enum):
    """Possible outcomes of an injection scan."""

    BLOCK = "BLOCK"
    WARN = "WARN"
    PASS = "PASS"


# ── 2. Rule ──────────────────────────────────────────────────────────────────
# Second because DEFAULT_RULES and Detector reference it.
# Dataclass is correct here — Rule IS a data container.

@dataclass
class Rule:
    """A single detection rule with a compiled regex and risk weight."""

    name: str
    pattern: re.Pattern
    weight: float  # 0.0 to 1.0


# ── 3. Default rules ────────────────────────────────────────────────────────
# Third because the Detector's __init__ uses it as a default.
# Compiled at module load time — re.compile() runs once, not per request.

DEFAULT_RULES: list[Rule] = [
    # Direct instruction override — highest risk, very specific phrase
    Rule(
        name="ignore_instructions",
        pattern=re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+"
            r"(instructions|prompts|rules|context)",
            re.IGNORECASE,
        ),
        weight=0.95,
    ),
    # Role reassignment — moderate risk, common in jailbreaks
    Rule(
        name="role_override",
        pattern=re.compile(
            r"you\s+are\s+now\s+(a|an|the|my)\s+\w+|"
            r"act\s+as\s+(a|an|the|if)\s+\w+|"
            r"pretend\s+(you\s+are|to\s+be)\s+",
            re.IGNORECASE,
        ),
        weight=0.7,
    ),
    # System prompt extraction — high risk, trying to leak instructions
    Rule(
        name="system_prompt_leak",
        pattern=re.compile(
            r"(reveal|show|print|display|repeat|output|tell\s+me|what\s+is|what\s+are)\s+"
            r"(me\s+)?(your|the)\s+(system\s*)?(prompt|instructions|rules|context|message)",
            re.IGNORECASE,
        ),
        weight=0.9,
    ),
    # DAN / jailbreak — highest risk, well-known attack names
    Rule(
        name="jailbreak_dan",
        pattern=re.compile(
            r"\bDAN\b|do\s+anything\s+now|jailbreak|bypass\s+(filter|safety|restriction)",
            re.IGNORECASE,
        ),
        weight=0.95,
    ),
    # Delimiter injection — high risk, faking system/assistant boundaries
    Rule(
        name="delimiter_injection",
        pattern=re.compile(
            r"<\|?(system|assistant|im_start|im_end)\|?>|"
            r"\[INST\]|\[/INST\]|"
            r"###\s*(system|assistant|instruction)",
            re.IGNORECASE,
        ),
        weight=0.85,
    ),
    # Encoding evasion — high risk, trying to hide the real payload
    Rule(
        name="encoding_evasion",
        pattern=re.compile(
            r"base64\s*(decode|encode)|"
            r"rot13|"
            r"translate\s+from\s+(hex|binary|morse|base64)",
            re.IGNORECASE,
        ),
        weight=0.8,
    ),
    # Forget/disregard — high risk, same intent as "ignore instructions"
    Rule(
        name="forget_instructions",
        pattern=re.compile(
            r"(forget|disregard|dismiss|override|reset)\s+"
            r"(everything|all|your|the|any)\s+"
            r"(previous|prior|above|earlier|original)?\s*"
            r"(instructions|rules|context|prompts)?",
            re.IGNORECASE,
        ),
        weight=0.9,
    ),
    # New instructions — high risk, trying to replace the system prompt
    Rule(
        name="new_instructions",
        pattern=re.compile(
            r"(new|updated|real|actual|true)\s+(instructions|rules|prompt|task)\s*(:|are|follow)",
            re.IGNORECASE,
        ),
        weight=0.85,
    ),
]


# ── 4. ScanResult ────────────────────────────────────────────────────────────
# Fourth because the Detector's scan() method returns it.
# Dataclass because it IS data — just holds results.
# safe() classmethod avoids duplicating the "clean result" construction.

@dataclass
class ScanResult:
    """Result of scanning messages for prompt injection."""

    is_suspicious: bool
    risk_score: float
    matched_rules: list[str] = field(default_factory=list)
    action: InjectionAction = InjectionAction.PASS

    @classmethod
    def safe(cls) -> "ScanResult":
        """Factory for a clean no-threat result.

        Used for: no user messages, no matches, or when scanning fails.
        Single source of truth for what a "clean" result looks like.
        """
        return cls(is_suspicious=False, risk_score=0.0)


# ── 5. Detector ──────────────────────────────────────────────────────────────
# Last because it depends on everything above.
# Regular class (NOT dataclass) because:
#   - It's a service, not a data container
#   - It has private state (_thresholds, _logger) that shouldn't be exposed
#   - It's created once at startup and reused for every request
#   - Matches the pattern of every other service in the pipeline

class PromptInjectionDetector:
    """Scans messages for prompt injection attacks.

    Created once during app startup. The scan() method is called per-request
    with the message list. Only user-role messages are inspected.
    """

    def __init__(
        self,
        block_threshold: float = 0.7,
        warn_threshold: float = 0.3,
        rules: list[Rule] | None = None,
    ) -> None:
        self._block_threshold = block_threshold
        self._warn_threshold = warn_threshold
        self._rules = rules or DEFAULT_RULES
        self._logger = logging.getLogger(__name__)

    def scan(self, messages: list[dict]) -> ScanResult:
        """Scan a message list for injection attempts.

        Extracts user-role messages, concatenates them (to catch attacks
        split across messages), and runs all rules against the combined text.

        Fails open: if anything unexpected happens, returns ScanResult.safe()
        so the request continues rather than crashing the pipeline.
        """
        try:
            # Extract only user content — system and assistant messages are trusted
            user_texts = [
                msg["content"]
                for msg in messages
                if msg.get("role") == "user" and msg.get("content")
            ]

            # Nothing to scan → clean result
            if not user_texts:
                return ScanResult.safe()

            # Concatenate with space to catch attacks split across messages
            # e.g. message 1: "ignore all previous" + message 2: "instructions"
            combined = " ".join(user_texts)

            # Run pattern matching
            matched = self._scan_text(combined)

            # No patterns matched → clean result
            if not matched:
                return ScanResult.safe()

            # Score and classify
            weights = [rule.weight for rule in matched]
            names = [rule.name for rule in matched]
            score = self._combine_scores(weights)
            action = self._get_action(score)

            # Log suspicious findings (includes trace ID automatically
            # via the logging filter set up in logging_config.py)
            self._logger.warning(
                "Prompt injection detected: score=%.3f action=%s patterns=%s",
                score,
                action.value,
                names,
            )

            return ScanResult(
                is_suspicious=True,
                risk_score=score,
                matched_rules=names,
                action=action,
            )

        except Exception as exc:
            # Fail open — don't crash the pipeline because of a scanning bug
            self._logger.warning(
                "Injection scan failed: %s — allowing request through", exc
            )
            return ScanResult.safe()

    def _scan_text(self, text: str) -> list[Rule]:
        """Return all Rule objects whose pattern matches the text."""
        return [rule for rule in self._rules if rule.pattern.search(text)]

    def _combine_scores(self, weights: list[float]) -> float:
        """Combine weights into a single 0.0–1.0 risk score.

        Uses complement product: 1 - prod(1 - w_i).
        - Single 0.95 match → 0.95
        - Two weak matches (0.3, 0.3) → 0.51
        - Never exceeds 1.0
        """
        if not weights:
            return 0.0
        return round(1.0 - math.prod(1 - w for w in weights), 4)

    def _get_action(self, score: float) -> InjectionAction:
        """Map risk score to action using configured thresholds."""
        if score >= self._block_threshold:
            return InjectionAction.BLOCK
        if score >= self._warn_threshold:
            return InjectionAction.WARN
        return InjectionAction.PASS