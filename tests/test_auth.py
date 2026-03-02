"""Tests for API key authentication."""

import json
from unittest.mock import AsyncMock

import pytest

from sentinel.core.auth import APIKeyStore, _hash_key

pytestmark = pytest.mark.anyio


class TestAPIKeyStore:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        r.get.return_value = None
        return r

    @pytest.fixture
    def store(self, mock_redis):
        return APIKeyStore(mock_redis)

    async def test_create_key_returns_prefix(self, store):
        raw_key, key_data = await store.create_key(name="dev-key", owner="test@example.com")
        assert raw_key.startswith("sk-sent-")
        assert key_data.key_prefix == raw_key[:8]
        assert key_data.name == "dev-key"
        assert key_data.owner == "test@example.com"
        assert key_data.is_active is True
        assert key_data.allowed_models == ["*"]

    async def test_validate_correct_key(self, store, mock_redis):
        raw_key, key_data = await store.create_key(name="test", owner="me")

        stored_call = mock_redis.set.call_args
        stored_json = stored_call[0][1]
        mock_redis.get.return_value = stored_json

        result = await store.validate_key(raw_key)
        assert result is not None
        assert result.name == "test"
        assert result.is_active is True

    async def test_validate_wrong_key_returns_none(self, store, mock_redis):
        mock_redis.get.return_value = None
        result = await store.validate_key("sk-sent-wrong-key-value")
        assert result is None

    async def test_validate_revoked_key_returns_none(self, store, mock_redis):
        raw_key, _ = await store.create_key(name="test", owner="me")

        stored_call = mock_redis.set.call_args
        stored_data = json.loads(stored_call[0][1])
        stored_data["is_active"] = False
        mock_redis.get.return_value = json.dumps(stored_data)

        result = await store.validate_key(raw_key)
        assert result is None

    async def test_revoke_key(self, store, mock_redis):
        raw_key, key_data = await store.create_key(name="test", owner="me")

        stored_call = mock_redis.set.call_args
        stored_json = stored_call[0][1]
        redis_key = stored_call[0][0]

        async def mock_scan(*args, **kwargs):
            yield redis_key

        mock_redis.scan_iter = mock_scan
        mock_redis.get.return_value = stored_json

        result = await store.revoke_key(key_data.key_prefix)
        assert result is True

    async def test_record_token_usage(self, store, mock_redis):
        raw_key, key_data = await store.create_key(name="test", owner="me")

        stored_call = mock_redis.set.call_args
        stored_json = stored_call[0][1]
        mock_redis.get.return_value = stored_json

        await store.record_token_usage(key_data.key_hash, 100)

        final_call = mock_redis.set.call_args
        final_data = json.loads(final_call[0][1])
        assert final_data["tokens_used_this_month"] == 100

    async def test_create_key_with_custom_models(self, store):
        raw_key, key_data = await store.create_key(
            name="limited", owner="me", allowed_models=["gpt-4o-mini"]
        )
        assert key_data.allowed_models == ["gpt-4o-mini"]

    async def test_hash_key_deterministic(self):
        h1 = _hash_key("test-key")
        h2 = _hash_key("test-key")
        assert h1 == h2

    async def test_hash_key_different_inputs(self):
        h1 = _hash_key("key-a")
        h2 = _hash_key("key-b")
        assert h1 != h2
