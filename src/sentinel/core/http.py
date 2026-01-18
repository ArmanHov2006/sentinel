from functools import lru_cache
import httpx
from src.sentinel.core.config import get_settings

@lru_cache
def get_http_client():
    settings = get_settings()
    timeout = httpx.Timeout(connect=5.0, read = settings.request_timeout_seconds, write = 10.0, pool = 5.0)
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30.0)
    client = httpx.AsyncClient(timeout=timeout, limits=limits)
    return client

