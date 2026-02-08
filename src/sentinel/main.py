"""
Sentinel — LLM Gateway with security, routing, and evaluation.

Application entry point. Configures middleware, registers routes,
and manages the application lifespan (startup/shutdown).
"""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from sentinel.api.routes.health import router as health_router
from sentinel.api.routes.metrics import router as metrics_router
from sentinel.api.v1.chat import router as chat_router
from sentinel.core.config import get_settings
from sentinel.core.logging_config import configure_logging
from sentinel.core.rate_limiter import RateLimiter
from sentinel.core.redis import create_redis_client
from sentinel.core.retry import RetryPolicy
from sentinel.middleware.trace import TraceMiddleware
from sentinel.providers.openai import OpenAIProvider
from sentinel.services.cache import CacheService
from sentinel.shield.pii_shield import PIIShield
from sentinel.shield.prompt_injection_detector import PromptInjectionDetector

STATIC_DIR = Path(__file__).parent / "static"

# Configure logging with trace ID injection before anything else
configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    app.state.start_time = time.time()
    settings = get_settings()

    # --- PII Shield ---
    try:
        app.state.pii_shield = PIIShield(action=settings.pii.action)
    except Exception as e:
        logger.warning("Failed to initialize PII shield: %s", e)
        app.state.pii_shield = None

    # --- Injection Detector ---
    try:
        app.state.injection_detector = PromptInjectionDetector(
            block_threshold=settings.injection.block_threshold,
            warn_threshold=settings.injection.warn_threshold,
        )
    except Exception as e:
        logger.warning("Failed to initialize injection detector: %s", e)
        app.state.injection_detector = None

    # --- Retry Policy ---
    try:
        app.state.retry_policy = RetryPolicy(
            max_attempts=settings.retry.max_attempts,
            base_delay=settings.retry.base_delay,
            max_delay=settings.retry.max_delay,
        )
    except Exception as e:
        logger.warning("Failed to initialize retry policy: %s", e)
        app.state.retry_policy = None

    # --- Provider selection ---
    if settings.groq_api_key:
        api_key, base_url = settings.groq_api_key, settings.groq_base_url
    elif settings.openai_api_key:
        api_key, base_url = settings.openai_api_key, settings.openai_base_url
    else:
        api_key, base_url = None, None

    # --- Redis + Cache + Rate Limiter ---
    app.state.redis = create_redis_client()
    app.state.cache = CacheService(app.state.redis)
    try:
        await app.state.redis.ping()
        app.state.rate_limiter = RateLimiter(
            app.state.redis,
            settings.rate_limit_max_requests,
            settings.rate_limit_window_seconds,
        )
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(
            "Redis unreachable (%s); running without response cache and rate limiting",
            e,
        )
        app.state.cache = None
        app.state.rate_limiter = None

    # --- LLM Provider ---
    app.state.provider = OpenAIProvider(api_key=api_key, base_url=base_url) if api_key else None

    logger.info("Sentinel started (version 0.1.0)")
    yield

    # --- Cleanup ---
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.aclose()
    logger.info("Sentinel shutdown complete")


app = FastAPI(
    title="Sentinel LLM Gateway",
    description=(
        "Production-grade LLM gateway with security, resilience, and observability. "
        "Provides PII detection and redaction via Microsoft Presidio, circuit breakers, "
        "rate limiting, response caching, request tracing, and real-time monitoring."
    ),
    version="0.1.0",
    openapi_tags=[
        {
            "name": "Chat",
            "description": "LLM chat completions with full security and resilience pipeline.",
        },
        {
            "name": "Operations",
            "description": "Health checks, metrics, and operational monitoring.",
        },
    ],
    lifespan=lifespan,
)

# Middleware — last added = outermost (first to execute on request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TraceMiddleware)

# API routes (versioned)
app.include_router(chat_router)

# Operational routes (unversioned)
app.include_router(health_router)
app.include_router(metrics_router)


# Dashboard routes
@app.get("/dashboard")
async def dashboard() -> FileResponse:
    """Serve the monitoring dashboard."""
    return FileResponse(str(STATIC_DIR / "dashboard.html"))


@app.get("/")
async def root() -> RedirectResponse:
    """Redirect root to the monitoring dashboard."""
    return RedirectResponse(url="/dashboard")


# Static file serving (must be last — acts as a catch-all for /static/*)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
