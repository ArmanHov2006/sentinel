import time
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    
    def __init__(self, client, max_requests: int, window_seconds: int):
        self.client = client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    def _build_key(self, identifier: str) -> str:
        return f"rate:{identifier}"

    async def is_allowed(self, identifier: str) -> bool:
        try:
            key = self._build_key(identifier)
            now = time.time()
            window_start = now - self.window_seconds
            await self.client.zremrangebyscore(key, 0, window_start)
            count = await self.client.zcount(key, window_start, now)
            if count >= self.max_requests:
                return False
            await self.client.zadd(key, {now: now})
            await self.client.expire(key, self.window_seconds)
            return True
        except Exception as e:
            logger.error(f"Error checking rate limit for {identifier}: {e}")
            return True
    
    async def get_remaining(self, identifier: str) -> int:
        try:
            key = self._build_key(identifier)
            now = time.time()
            window_start = now - self.window_seconds
            count = await self.client.zcount(key, window_start, now)
            return max(0, self.max_requests - count)
        except Exception as e:
            logger.error(f"Error getting remaining requests for {identifier}: {e}")
            return self.max_requests