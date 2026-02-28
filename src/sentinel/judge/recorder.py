import json
import logging

import redis.asyncio as redis

from sentinel.judge.models import JudgeResult

logger = logging.getLogger(__name__)

KEY_RESULT_PREFIX = "judge:result:"
KEY_TOTAL_EVALUATIONS = "judge:total_evaluations"
KEY_FAILED_EVALUATIONS = "judge:failed_evaluations"


class QualityRecorder:
    """Records quality evaluation results using Redis."""

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 7 * 24 * 3600) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    async def record(self, request_id: str, result: JudgeResult) -> None:
        """Record the quality evaluation result for a given request."""
        try:
            result_dict = result.to_dict()
            passed = result_dict.get("passed", False)
            result_json = json.dumps(result_dict)

            result_key = f"{KEY_RESULT_PREFIX}{request_id}"
            await self._redis.set(result_key, result_json, ex=self._ttl)

            await self._redis.incr(KEY_TOTAL_EVALUATIONS)
            if not passed:
                await self._redis.incr(KEY_FAILED_EVALUATIONS)
        except redis.RedisError as e:
            logger.warning("QualityRecorder: failed to record evaluation for %s: %s", request_id, e)
