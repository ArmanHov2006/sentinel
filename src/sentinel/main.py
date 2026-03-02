"""
Sentinel — LLM Gateway with security, routing, and evaluation.

Application entry point. Configures middleware, registers routes,
and manages the application lifespan (startup/shutdown).
"""

import time
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app

from sentinel.api.routes.admin import router as admin_router
from sentinel.api.routes.health import router as health_router
from sentinel.api.routes.metrics import router as metrics_router
from sentinel.api.v1.chat import router as chat_router
from sentinel.core.auth import APIKeyStore
from sentinel.core.circuit_breaker import CircuitBreaker
from sentinel.core.config import get_settings
from sentinel.core.logging_config import configure_logging
from sentinel.core.rate_limiter import RateLimiter
from sentinel.core.redis import create_redis_client
from sentinel.core.retry import RetryPolicy
from sentinel.core.telemetry import configure_telemetry
from sentinel.core.utils import mask_key
from sentinel.judge.evaluator import JudgeEvaluator
from sentinel.judge.recorder import QualityRecorder
from sentinel.middleware.trace import TraceMiddleware
from sentinel.providers.anthropic import AnthropicProvider
from sentinel.providers.openai import OpenAIProvider
from sentinel.providers.registry import ProviderRegistry
from sentinel.providers.router import Router
from sentinel.services.cache import CacheService
from sentinel.services.embedding import EmbeddingService
from sentinel.services.semantic_cache import SemanticCacheService
from sentinel.shield.pii_shield import PIIShield
from sentinel.shield.prompt_injection_detector import PromptInjectionDetector

STATIC_DIR = Path(__file__).parent / "static"

settings = get_settings()
configure_logging(env=settings.sentinel_env)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    app.state.start_time = time.time()

    # --- PII Shield ---
    try:
        app.state.pii_shield = PIIShield(action=settings.pii.action)
    except Exception as e:
        logger.warning("pii_shield_init_failed", error=str(e))
        app.state.pii_shield = None

    # --- Injection Detector ---
    try:
        app.state.injection_detector = PromptInjectionDetector(
            block_threshold=settings.injection.block_threshold,
            warn_threshold=settings.injection.warn_threshold,
        )
    except Exception as e:
        logger.warning("injection_detector_init_failed", error=str(e))
        app.state.injection_detector = None

    # --- Retry Policy ---
    try:
        app.state.retry_policy = RetryPolicy(
            max_attempts=settings.retry.max_attempts,
            base_delay=settings.retry.base_delay,
            max_delay=settings.retry.max_delay,
        )
    except Exception as e:
        logger.warning("retry_policy_init_failed", error=str(e))
        app.state.retry_policy = None

    # --- Provider Registry + Router ---
    try:
        app.state.registry = ProviderRegistry()
        fallbacks: dict[str, list[str]] = {"*": ["openai", "anthropic"]}

        if settings.openai_api_key:
            cb = CircuitBreaker()
            retry = app.state.retry_policy or RetryPolicy()
            openai_provider = OpenAIProvider(circuit_breaker=cb, retry_policy=retry)
            app.state.registry.register(openai_provider)
            logger.info("openai_configured", key=mask_key(settings.openai_api_key))

        if settings.anthropic_api_key:
            cb = CircuitBreaker()
            retry = app.state.retry_policy or RetryPolicy()
            anthropic_provider = AnthropicProvider(circuit_breaker=cb, retry_policy=retry)
            app.state.registry.register(anthropic_provider)
            logger.info("anthropic_configured", key=mask_key(settings.anthropic_api_key))

        if len(app.state.registry) > 0:
            app.state.router = Router(registry=app.state.registry, fallbacks=fallbacks)
        else:
            app.state.router = None
            logger.info("no_providers_configured", action="mock_fallback")
    except Exception as e:
        logger.warning("provider_registry_init_failed", error=str(e))
        app.state.registry = None
        app.state.router = None

    # --- Semantic Cache ---
    try:
        app.state.embedding_service = EmbeddingService()
        app.state.semantic_cache = SemanticCacheService(app.state.embedding_service)
    except Exception as e:
        logger.warning("semantic_cache_init_failed", error=str(e))
        app.state.embedding_service = None
        app.state.semantic_cache = None

    # --- LLM-as-Judge ---
    if settings.enable_judge and settings.openai_api_key:
        try:
            from openai import AsyncOpenAI

            judge_client = AsyncOpenAI(api_key=settings.openai_api_key)
            app.state.judge_evaluator = JudgeEvaluator(
                client=judge_client, model=settings.judge_model
            )
            logger.info("judge_evaluator_initialized", model=settings.judge_model)
        except Exception as e:
            logger.warning("judge_evaluator_init_failed", error=str(e))
            app.state.judge_evaluator = None
    else:
        app.state.judge_evaluator = None
        if not settings.enable_judge:
            logger.info("judge_disabled", reason="ENABLE_JUDGE=false")
        elif not settings.openai_api_key:
            logger.info("judge_disabled", reason="no_openai_api_key")

    # --- Redis + Cache + Rate Limiter ---
    try:
        app.state.redis = create_redis_client()
        app.state.cache = CacheService(app.state.redis)
        await app.state.redis.ping()
        app.state.rate_limiter = RateLimiter(
            app.state.redis,
            settings.rate_limit_max_requests,
            settings.rate_limit_window_seconds,
        )
        logger.info("redis_connected")
    except Exception as e:
        logger.warning("redis_unavailable", error=str(e), action="running_without_cache")
        app.state.redis = None
        app.state.cache = None
        app.state.rate_limiter = None

    # --- API Key Store ---
    if getattr(app.state, "redis", None) is not None:
        app.state.key_store = APIKeyStore(app.state.redis)
    else:
        app.state.key_store = None

    # --- Quality Recorder (depends on Redis) ---
    if (
        getattr(app.state, "redis", None) is not None
        and getattr(app.state, "judge_evaluator", None) is not None
    ):
        app.state.quality_recorder = QualityRecorder(redis_client=app.state.redis)
    else:
        app.state.quality_recorder = None

    # --- Telemetry ---
    if settings.otel_enabled:
        configure_telemetry(
            app,
            env=settings.sentinel_env,
            otel_endpoint=settings.otel_exporter_endpoint,
            console_export=settings.otel_console_export,
        )

    logger.info("sentinel_started", version="0.1.0")
    yield

    # --- Cleanup ---
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.aclose()
    logger.info("sentinel_shutdown")


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

cors_origins = ["*"] if settings.sentinel_env == "development" else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TraceMiddleware)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if settings.sentinel_env != "development":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(chat_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(admin_router)

metrics_app = make_asgi_app()
app.mount("/prometheus", metrics_app)


@app.get("/dashboard")
async def dashboard() -> FileResponse:
    """Serve the monitoring dashboard."""
    return FileResponse(str(STATIC_DIR / "dashboard.html"))


@app.get("/")
async def root() -> RedirectResponse:
    """Redirect root to the monitoring dashboard."""
    return RedirectResponse(url="/dashboard")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
