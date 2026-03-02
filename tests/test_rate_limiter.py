"""Tests for sliding-window rate limiter."""

from unittest.mock import AsyncMock

import pytest
import redis.asyncio as redis_lib

from sentinel.core.rate_limiter import RateLimiter

pytestmark = pytest.mark.anyio


class TestRateLimiter:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        r.zcount.return_value = 0
        return r

    @pytest.fixture
    def limiter(self, mock_redis):
        return RateLimiter(mock_redis, max_requests=10, window_seconds=60)

    async def test_allows_under_limit(self, limiter, mock_redis):
        mock_redis.zcount.return_value = 5
        allowed = await limiter.is_allowed("user-1")
        assert allowed is True

    async def test_blocks_over_limit(self, limiter, mock_redis):
        mock_redis.zcount.return_value = 10
        allowed = await limiter.is_allowed("user-1")
        assert allowed is False

    async def test_get_remaining_under_limit(self, limiter, mock_redis):
        mock_redis.zcount.return_value = 3
        remaining = await limiter.get_remaining("user-1")
        assert remaining == 7

    async def test_get_remaining_at_limit(self, limiter, mock_redis):
        mock_redis.zcount.return_value = 10
        remaining = await limiter.get_remaining("user-1")
        assert remaining == 0

    async def test_fail_open_on_redis_error(self, limiter, mock_redis):
        mock_redis.zremrangebyscore.side_effect = redis_lib.RedisError("down")
        allowed = await limiter.is_allowed("user-1")
        assert allowed is True

    async def test_remaining_returns_max_on_redis_error(self, limiter, mock_redis):
        mock_redis.zcount.side_effect = redis_lib.RedisError("down")
        remaining = await limiter.get_remaining("user-1")
        assert remaining == 10
