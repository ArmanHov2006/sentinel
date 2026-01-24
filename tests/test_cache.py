"""Tests for CacheService implementation."""

import os
import sys
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sentinel.services.cache import CacheService
from sentinel.api.schemas.chat import MessageSchema


class TestCacheService:
    """Test suite for CacheService class."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def cache_service(self, mock_redis_client):
        """Create a CacheService with mock Redis."""
        return CacheService(mock_redis_client, default_ttl=3600)

    @pytest.mark.anyio
    async def test_get_returns_none_for_missing_key(self, cache_service, mock_redis_client):
        """Should return None when key doesn't exist."""
        mock_redis_client.get.return_value = None

        result = await cache_service.get("nonexistent_key")

        assert result is None
        mock_redis_client.get.assert_called_once_with("nonexistent_key")

    @pytest.mark.anyio
    async def test_set_and_get_roundtrip(self, cache_service, mock_redis_client):
        """Should be able to set a value and retrieve it."""
        test_data = {"model": "gpt-4", "response": "Hello world"}

        # Setup mock to return the set value
        mock_redis_client.get.return_value = json.dumps(test_data)

        # Set the value
        await cache_service.set("test_key", test_data)

        # Verify set was called correctly
        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[0][0] == "test_key"
        assert json.loads(call_args[0][1]) == test_data
        assert call_args[1]["ex"] == 3600

        # Get the value
        result = await cache_service.get("test_key")

        assert result == test_data

    @pytest.mark.anyio
    async def test_set_with_custom_ttl(self, cache_service, mock_redis_client):
        """Should use custom TTL when provided."""
        test_data = {"key": "value"}

        await cache_service.set("test_key", test_data, ttl=7200)

        call_args = mock_redis_client.set.call_args
        assert call_args[1]["ex"] == 7200

    def test_generate_key_deterministic(self, cache_service):
        """Same inputs should produce same cache key."""
        messages = [
            MessageSchema(role="user", content="Hello"),
            MessageSchema(role="assistant", content="Hi there"),
        ]

        key1 = cache_service.generate_key("gpt-4", messages, 0.7)
        key2 = cache_service.generate_key("gpt-4", messages, 0.7)

        assert key1 == key2
        assert key1.startswith("llm:")

    def test_generate_key_different_for_different_inputs(self, cache_service):
        """Different inputs should produce different cache keys."""
        messages1 = [MessageSchema(role="user", content="Hello")]
        messages2 = [MessageSchema(role="user", content="Goodbye")]

        key1 = cache_service.generate_key("gpt-4", messages1, 0.7)
        key2 = cache_service.generate_key("gpt-4", messages2, 0.7)
        key3 = cache_service.generate_key("gpt-3.5", messages1, 0.7)
        key4 = cache_service.generate_key("gpt-4", messages1, 0.5)

        # All keys should be different
        keys = [key1, key2, key3, key4]
        assert len(set(keys)) == 4

    def test_generate_key_different_models(self, cache_service):
        """Different models should produce different cache keys."""
        messages = [MessageSchema(role="user", content="Hello")]

        key1 = cache_service.generate_key("gpt-4", messages, 0.7)
        key2 = cache_service.generate_key("gpt-3.5-turbo", messages, 0.7)

        assert key1 != key2

    def test_generate_key_different_temperatures(self, cache_service):
        """Different temperatures should produce different cache keys."""
        messages = [MessageSchema(role="user", content="Hello")]

        key1 = cache_service.generate_key("gpt-4", messages, 0.7)
        key2 = cache_service.generate_key("gpt-4", messages, 1.0)

        assert key1 != key2

    @pytest.mark.anyio
    async def test_get_handles_redis_error_gracefully(self, cache_service, mock_redis_client):
        """Should return None and not crash when Redis errors occur on get."""
        mock_redis_client.get.side_effect = redis.RedisError("Connection refused")

        result = await cache_service.get("some_key")

        assert result is None

    @pytest.mark.anyio
    async def test_set_handles_redis_error_gracefully(self, cache_service, mock_redis_client):
        """Should not crash when Redis errors occur on set."""
        mock_redis_client.set.side_effect = redis.RedisError("Connection refused")

        # Should not raise exception
        await cache_service.set("some_key", {"data": "value"})

    @pytest.mark.anyio
    async def test_delete_handles_redis_error_gracefully(self, cache_service, mock_redis_client):
        """Should not crash when Redis errors occur on delete."""
        mock_redis_client.delete.side_effect = redis.RedisError("Connection refused")

        # Should not raise exception
        await cache_service.delete("some_key")

    @pytest.mark.anyio
    async def test_delete_calls_redis_delete(self, cache_service, mock_redis_client):
        """Delete should call Redis delete with correct key."""
        await cache_service.delete("test_key")

        mock_redis_client.delete.assert_called_once_with("test_key")

    def test_generate_key_with_empty_messages(self, cache_service):
        """Should handle empty message list."""
        key = cache_service.generate_key("gpt-4", [], 0.7)

        assert key.startswith("llm:")

    def test_generate_key_with_max_tokens(self, cache_service):
        """Should include max_tokens in key generation."""
        messages = [MessageSchema(role="user", content="Hello")]

        key1 = cache_service.generate_key("gpt-4", messages, 0.7, max_tokens=100)
        key2 = cache_service.generate_key("gpt-4", messages, 0.7, max_tokens=200)
        key3 = cache_service.generate_key("gpt-4", messages, 0.7, max_tokens=None)

        assert key1 != key2
        assert key1 != key3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
