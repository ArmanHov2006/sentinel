"""API key models and Redis-backed store."""

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class APIKeyData:
    """Metadata for a virtual API key (never stores plaintext)."""

    key_hash: str
    key_prefix: str
    name: str
    owner: str
    created_at: str
    is_active: bool = True
    allowed_models: list[str] = field(default_factory=lambda: ["*"])
    rate_limit_rpm: int = 60
    monthly_token_budget: int = 1_000_000
    tokens_used_this_month: int = 0


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _redis_key(key_hash: str) -> str:
    return f"sentinel:apikey:{key_hash}"


class APIKeyStore:
    """Manages API keys in Redis."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def create_key(
        self,
        name: str,
        owner: str,
        allowed_models: list[str] | None = None,
        rate_limit_rpm: int = 60,
        monthly_budget: int = 1_000_000,
    ) -> tuple[str, APIKeyData]:
        """Create a new API key, store its hash, return (plaintext, metadata)."""
        raw_key = f"sk-sent-{secrets.token_hex(24)}"
        key_hash = _hash_key(raw_key)
        key_data = APIKeyData(
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            name=name,
            owner=owner,
            created_at=datetime.now(UTC).isoformat(),
            allowed_models=allowed_models or ["*"],
            rate_limit_rpm=rate_limit_rpm,
            monthly_token_budget=monthly_budget,
        )
        await self._redis.set(_redis_key(key_hash), json.dumps(asdict(key_data)))
        return raw_key, key_data

    async def validate_key(self, raw_key: str) -> APIKeyData | None:
        """Validate a raw API key, return metadata or None."""
        key_hash = _hash_key(raw_key)
        data = await self._redis.get(_redis_key(key_hash))
        if data is None:
            return None
        key_data = APIKeyData(**json.loads(data))
        if not key_data.is_active:
            return None
        return key_data

    async def list_keys(self) -> list[APIKeyData]:
        """List all API key metadata (never plaintext)."""
        keys: list[APIKeyData] = []
        async for redis_key in self._redis.scan_iter("sentinel:apikey:*"):
            data = await self._redis.get(redis_key)
            if data is not None:
                keys.append(APIKeyData(**json.loads(data)))
        return keys

    async def revoke_key(self, key_prefix: str) -> bool:
        """Revoke a key by its prefix."""
        async for redis_key in self._redis.scan_iter("sentinel:apikey:*"):
            data = await self._redis.get(redis_key)
            if data is None:
                continue
            parsed = json.loads(data)
            if parsed.get("key_prefix") == key_prefix:
                parsed["is_active"] = False
                await self._redis.set(redis_key, json.dumps(parsed))
                return True
        return False

    async def record_token_usage(self, key_hash: str, tokens: int) -> None:
        """Increment tokens_used_this_month for a key."""
        rk = _redis_key(key_hash)
        data = await self._redis.get(rk)
        if data is None:
            return
        parsed = json.loads(data)
        parsed["tokens_used_this_month"] = parsed.get("tokens_used_this_month", 0) + tokens
        await self._redis.set(rk, json.dumps(parsed))
