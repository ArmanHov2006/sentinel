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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
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
    except Exception as e:
        logger.warning("Redis unreachable (%s); running without response cache", e)
        app.state.cache = None
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