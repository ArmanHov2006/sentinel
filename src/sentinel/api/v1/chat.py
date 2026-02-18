import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from sentinel.api.converters import (
    to_api_chat_completion_response,
    to_domain_chat_request,
)
from sentinel.api.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChoiceMessageSchema,
    ChoiceSchema,
    MessageSchema,
    UsageSchema,
)
from sentinel.core.metrics import metrics
from sentinel.domain.exceptions import AllProvidersFailedError, NoProviderError
from sentinel.shield.pii_shield import PIIAction
from sentinel.shield.prompt_injection_detector import InjectionAction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Chat"])


async def fake_stream_response():
    words = [
        "Hello",
        " ",
        "world",
        " ",
        "this",
        " ",
        "is",
        " ",
        "a",
        " ",
        "test",
        " ",
        "message",
        ".",
        "!",
    ]
    for word in words:
        chunk = {"choices": [{"delta": {"content": word}}]}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.3)
    yield "data: [DONE]\n\n"


@router.post(
    "/chat/completions",
    response_model=ChatCompletionResponse,
    responses={
        200: {"description": "Successful completion"},
        400: {
            "description": "Request blocked (PII or prompt injection detected)",
            "content": {
                "application/json": {
                    "example": {"detail": "Request blocked: prompt injection detected"}
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {"application/json": {"example": {"detail": "Rate limit exceeded"}}},
        },
    },
    summary="Create chat completion",
    description="Send a chat completion request through the full Sentinel pipeline: "
    "rate limiting, PII detection, caching, circuit breaker, and retry. "
    "Compatible with the OpenAI chat completions API format.",
)
async def create_chat_completion(
    chat_request: ChatCompletionRequest, request: Request, response: Response
):
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter = getattr(request.app.state, "rate_limiter", None)

    if rate_limiter:
        allowed = await rate_limiter.is_allowed(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(rate_limiter.window_seconds)},
            )

        remaining = await rate_limiter.get_remaining(client_ip)
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

    pii_shield = getattr(request.app.state, "pii_shield", None)
    if pii_shield is not None:
        messages_as_dicts = [{"role": m.role, "content": m.content} for m in chat_request.messages]
        results = pii_shield.scan_messages(messages_as_dicts)
        if results:
            metrics.increment("pii_detections")
            if any(r.should_block for r in results.values()):
                metrics.increment("pii_blocks")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid request due to PII detected",
                )
            if pii_shield.action == PIIAction.REDACT:
                modified = []
                for i, msg in enumerate(chat_request.messages):
                    if i in results and results[i].processed_text is not None:
                        modified.append(
                            MessageSchema(role=msg.role, content=results[i].processed_text)
                        )
                    else:
                        modified.append(msg)
                chat_request.messages = modified
            if pii_shield.action == PIIAction.WARN:
                for idx, result in results.items():
                    pii_types = [f.type.value for f in result.findings]
                    logger.warning("PII detected in message %d: %s", idx, pii_types)

    injection_detector = getattr(request.app.state, "injection_detector", None)
    if injection_detector is not None:
        messages_as_dicts = [{"role": m.role, "content": m.content} for m in chat_request.messages]
        injection_result = injection_detector.scan(messages_as_dicts)
        if injection_result.is_suspicious:
            metrics.increment("injection_detections")
        if injection_result.action == InjectionAction.BLOCK:
            metrics.increment("injection_blocks")
            raise HTTPException(
                status_code=400,
                detail="Request blocked: prompt injection detected",
            )
        if injection_result.action == InjectionAction.WARN:
            logger.warning(
                "Prompt injection (WARN): score=%.3f, patterns=%s",
                injection_result.risk_score,
                injection_result.matched_rules,
            )

    if chat_request.stream:
        provider_router = getattr(request.app.state, "router", None)
        if provider_router is None:
            return StreamingResponse(
                fake_stream_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        async def stream_response():
            try:
                domain_request = to_domain_chat_request(chat_request)
                async for chunk in provider_router.stream(domain_request):
                    chunk_data = {"choices": [{"delta": {"content": chunk}}]}
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                yield "data: [DONE]\n\n"
            except NoProviderError:
                error_data = {
                    "error": {
                        "message": f"No provider configured for model: {chat_request.model}",
                        "type": "invalid_request_error",
                    }
                }
                yield f"data: {json.dumps(error_data)}\n\n"
            except AllProvidersFailedError as e:
                error_data = {
                    "error": {
                        "message": f"All providers failed: {[n for n, _ in e.errors]}",
                        "type": "server_error",
                    }
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    cache = getattr(request.app.state, "cache", None)
    cache_key: str | None = None

    if cache:
        cache_key = cache.generate_key(
            chat_request.model,
            chat_request.messages,
            chat_request.temperature,
        )
        cached_response = await cache.get(cache_key)
        if cached_response:
            return ChatCompletionResponse.model_validate(cached_response)

    provider_router = getattr(request.app.state, "router", None)
    domain_response = None
    if provider_router is not None:
        try:
            domain_request = to_domain_chat_request(chat_request)
            domain_response = await provider_router.route(domain_request)
        except NoProviderError as e:
            raise HTTPException(
                status_code=404,
                detail=f"No provider configured for model: {chat_request.model}",
            ) from e
        except AllProvidersFailedError as e:
            raise HTTPException(
                status_code=503,
                detail=f"All providers failed: {[n for n, _ in e.errors]}",
            ) from e
        except Exception:
            domain_response = None
    if domain_response is not None:
        api_response = to_api_chat_completion_response(domain_response)
        if cache and cache_key:
            await cache.set(cache_key, api_response.model_dump())
        return api_response

    last_message = chat_request.messages[-1]
    user_said = last_message.content
    mock_content = f"You said: {user_said}"
    unique_id = f"sentinel-{uuid.uuid4().hex[:12]}"
    timestamp = int(time.time())

    api_response = ChatCompletionResponse(
        id=unique_id,
        object="chat.completion",
        created=timestamp,
        model=chat_request.model,
        choices=[
            ChoiceSchema(
                index=0,
                message=ChoiceMessageSchema(
                    role="assistant",
                    content=mock_content,
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageSchema(
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
        ),
    )

    if cache and cache_key:
        await cache.set(cache_key, api_response.model_dump())

    return api_response