import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentinel.api.v1.chat import router as chat_router
from sentinel.api.schemas.health import HealthResponse
from sentinel.core.redis import create_redis_client
from sentinel.core.config import get_settings
from sentinel.providers.openai import OpenAIProvider
from sentinel.services.cache import CacheService
from sentinel.core.rate_limiter import RateLimiter
from sentinel.shield.pii_shield import PIIShield
from sentinel.core.retry import RetryPolicy

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    try:
        app.state.pii_shield = PIIShield(action=settings.pii.action)
    except Exception as e:
        logger.warning("Failed to initialize PII shield: %s", e)
        app.state.pii_shield = None
    try:
        app.state.retry_policy = RetryPolicy(max_attempts=settings.retry.max_attempts, base_delay=settings.retry.base_delay, max_delay=settings.retry.max_delay)
    except Exception as e:
        logger.warning("Failed to initialize retry policy: %s", e)
        app.state.retry_policy = None
    if settings.groq_api_key:
        api_key, base_url = settings.groq_api_key, settings.groq_base_url
    elif settings.openai_api_key:
        api_key, base_url = settings.openai_api_key, settings.openai_base_url
    else:
        api_key, base_url = None, None
    app.state.redis = create_redis_client()
    app.state.cache = CacheService(app.state.redis)
    try:
        await app.state.redis.ping()
        app.state.rate_limiter = RateLimiter(
            app.state.redis,
            settings.rate_limit_max_requests,
            settings.rate_limit_window_seconds
        )
    except Exception as e:
        logger.warning("Redis unreachable (%s); running without response cache and rate limiting", e)
        app.state.cache = None
        app.state.rate_limiter = None
    app.state.provider = OpenAIProvider(api_key=api_key, base_url=base_url) if api_key else None
    yield
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.aclose()

app = FastAPI(
    title="Sentinel",
    description="LLM Gateway with security, routing, and evaluation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

@app.get("/health")
async def health_check():
    return HealthResponse(status="healthy", version="0.1.0")
