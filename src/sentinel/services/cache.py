"""Redis-backed response cache service."""

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from sentinel.core.metrics import metrics
from sentinel.domain.models import Message

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self, client, default_ttl: int = 3600):
        self.client = client
        self.default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value by key. Returns None on miss or error."""
        try:
            value = await self.client.get(key)
        except redis.RedisError as e:
            logger.warning("Redis error getting key %s: %s", key, e)
            return None
        if value:
            metrics.increment("cache_hits")
            return json.loads(value)
        metrics.increment("cache_misses")
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            json_value = json.dumps(value, default=str)
            ttl = ttl or self.default_ttl
            await self.client.set(key, json_value, ex=ttl)
        except redis.RedisError as e:
            logger.warning("Redis error setting key %s: %s", key, e)

    async def delete(self, key: str) -> None:
        """Delete a cached value by key."""
        try:
            await self.client.delete(key)
        except redis.RedisError as e:
            logger.warning("Redis error deleting key %s: %s", key, e)

    def generate_key(
        self,
        model: str,
        messages: list[Message],
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a stable cache key for a given request.

        Supports both domain `Message` objects (role is an enum) and
        API-layer message schemas where `role` is a plain string.
        """

        def _role_value(msg) -> str:
            # msg.role might be an enum (domain) or a plain string (schema)
            role = getattr(msg, "role", None)
            if hasattr(role, "value"):
                return role.value
            return str(role)

        params = {
            "model": model,
            "messages": [{"role": _role_value(msg), "content": msg.content} for msg in messages]
            if messages
            else None,
            "temperature": temperature,
            "max_tokens": max_tokens or None,
        }
        return f"llm:{hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()}"
