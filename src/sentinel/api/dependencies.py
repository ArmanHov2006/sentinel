"""FastAPI auth dependencies."""

import structlog
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sentinel.core.auth import APIKeyData
from sentinel.core.config import get_settings

security_scheme = HTTPBearer(auto_error=False)

logger = structlog.get_logger()


async def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
) -> APIKeyData | None:
    """Validate API key from Authorization header."""
    settings = get_settings()

    if not settings.require_auth:
        return None

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_store = getattr(request.app.state, "key_store", None)
    if key_store is None:
        logger.warning("auth_store_unavailable", action="fail_open")
        return None

    key_data = await key_store.validate_key(credentials.credentials)

    if not key_data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not key_data.is_active:
        raise HTTPException(status_code=403, detail="API key has been revoked")

    if key_data.tokens_used_this_month >= key_data.monthly_token_budget:
        raise HTTPException(status_code=429, detail="Monthly token budget exceeded")

    structlog.contextvars.bind_contextvars(api_key=key_data.key_prefix)

    return key_data
