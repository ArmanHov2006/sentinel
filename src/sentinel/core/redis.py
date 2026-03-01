"""Redis client factory."""

import redis.asyncio as redis

from sentinel.core.config import get_settings


def create_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        decode_responses=True,
        socket_timeout=settings.redis.socket_timeout,
    )
