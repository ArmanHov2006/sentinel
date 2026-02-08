import asyncio
import random
from collections.abc import Callable
from typing import Any


class RetryPolicy:
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 40.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    def calculate_backoff_time(self, attempt: int) -> float:
        """
        Calculate the backoff time for a retry attempt.
        """
        return min(
            self.max_delay, self.base_delay * (2**attempt) + random.uniform(0, self.base_delay)
        )

    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception:
                if attempt == self.max_attempts:
                    raise
                backoff_time = self.calculate_backoff_time(attempt)
                await asyncio.sleep(backoff_time)
