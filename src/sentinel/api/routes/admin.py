"""Admin endpoints for API key management."""

from dataclasses import asdict

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from sentinel.core.config import get_settings

logger = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["Admin"])


class CreateKeyRequest(BaseModel):
    name: str = Field(description="Human-friendly name for the key")
    owner: str = Field(description="Owner email or identifier")
    allowed_models: list[str] = Field(default=["*"])
    rate_limit_rpm: int = Field(default=60)
    monthly_budget: int = Field(default=1_000_000)


def _verify_master_key(request: Request) -> None:
    """Check that the request carries the master key."""
    settings = get_settings()
    if not settings.sentinel_master_key:
        raise HTTPException(status_code=503, detail="Master key not configured")

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing master key")

    token = auth[7:]
    if token != settings.sentinel_master_key:
        raise HTTPException(status_code=403, detail="Invalid master key")


@router.post("/keys")
async def create_key(body: CreateKeyRequest, request: Request):
    """Create a new API key (returns plaintext once)."""
    _verify_master_key(request)
    key_store = getattr(request.app.state, "key_store", None)
    if key_store is None:
        raise HTTPException(status_code=503, detail="Key store unavailable (Redis required)")

    raw_key, key_data = await key_store.create_key(
        name=body.name,
        owner=body.owner,
        allowed_models=body.allowed_models,
        rate_limit_rpm=body.rate_limit_rpm,
        monthly_budget=body.monthly_budget,
    )
    logger.info("api_key_created", key_prefix=key_data.key_prefix, owner=body.owner)
    return {"key": raw_key, "metadata": asdict(key_data)}


@router.get("/keys")
async def list_keys(request: Request):
    """List all keys (metadata only, no plaintext)."""
    _verify_master_key(request)
    key_store = getattr(request.app.state, "key_store", None)
    if key_store is None:
        raise HTTPException(status_code=503, detail="Key store unavailable (Redis required)")

    keys = await key_store.list_keys()
    return {"keys": [asdict(k) for k in keys]}


@router.delete("/keys/{prefix}")
async def revoke_key(prefix: str, request: Request):
    """Revoke a key by prefix."""
    _verify_master_key(request)
    key_store = getattr(request.app.state, "key_store", None)
    if key_store is None:
        raise HTTPException(status_code=503, detail="Key store unavailable (Redis required)")

    revoked = await key_store.revoke_key(prefix)
    if not revoked:
        raise HTTPException(status_code=404, detail="Key not found")

    logger.info("api_key_revoked", key_prefix=prefix)
    return {"revoked": True, "prefix": prefix}
