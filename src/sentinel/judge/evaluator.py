"""LLM-as-judge evaluator — calls a cheap model, returns a structured JudgeResult."""

import json
import logging

from openai import AsyncOpenAI

from sentinel.judge.models import JudgeDimension, JudgeResult
from sentinel.judge.prompt_builder import build_judge_prompt

logger = logging.getLogger(__name__)

_DIMENSION_KEYS = {d.value for d in JudgeDimension}
_SAFE_DEFAULT_SCORE = 6.0


def _safe_default() -> JudgeResult:
    """Middle-of-the-road result returned when the judge call fails for any reason."""
    return JudgeResult(
        dimensions={d: _SAFE_DEFAULT_SCORE for d in JudgeDimension},
        flags=["judge_error"],
        reasoning="Evaluation failed; scores are defaults and should not be trusted.",
    )


def _parse_judge_response(raw: str) -> JudgeResult:
    """Parse raw JSON from the judge model into a JudgeResult.

    Raises ValueError/KeyError/TypeError on malformed output so the
    caller can fall back to _safe_default().
    """
    data = json.loads(raw)

    dimensions: dict[JudgeDimension, float] = {}
    for key in _DIMENSION_KEYS:
        score = float(data[key])
        if not 0.0 <= score <= 10.0:
            raise ValueError(f"Score for '{key}' out of range: {score}")
        dimensions[JudgeDimension(key)] = score

    flags = data.get("flags", [])
    if not isinstance(flags, list):
        raise TypeError(f"Expected list for 'flags', got {type(flags).__name__}")
    flags = [str(f) for f in flags]

    reasoning = str(data.get("reasoning", ""))

    return JudgeResult(
        dimensions=dimensions,
        flags=flags,
        reasoning=reasoning,
    )


class JudgeEvaluator:
    """Evaluates an assistant response by sending it to a judge LLM."""

    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4o-mini") -> None:
        self._client = client
        self._model = model

    async def evaluate(self, user_message: str, assistant_response: str) -> JudgeResult:
        """Score an assistant response. Never raises — returns a safe default on any failure."""
        try:
            system_prompt, user_prompt = build_judge_prompt(user_message, assistant_response)

            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )

            raw = completion.choices[0].message.content or ""
            return _parse_judge_response(raw)

        except Exception:
            logger.exception("Judge evaluation failed")
            return _safe_default()
