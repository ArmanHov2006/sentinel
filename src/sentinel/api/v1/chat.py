"""Chat completions endpoint with full security and resilience pipeline."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
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
from sentinel.core.context import get_request_id
from sentinel.core.metrics import metrics
from sentinel.domain.exceptions import AllProvidersFailedError, NoProviderError
from sentinel.domain.models import TokenUsage
from sentinel.services.cost_tracker import CostTracker
from sentinel.shield.pii_shield import PIIAction
from sentinel.shield.prompt_injection_detector import InjectionAction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Chat"])


async def _run_judge(evaluator, recorder, request_id: str, user_message: str, assistant_response: str) -> None:
    """Background task: evaluate the response with the judge LLM, then record the result."""
    try:
        result = await evaluator.evaluate(user_message, assistant_response)
        if recorder is not None:
            await recorder.record(request_id, result)
    except Exception:
        logger.exception("Background judge task failed for request %s", request_id)


def _schedule_judge(background_tasks, request, request_id: str, user_message: str, assistant_response: str) -> None:
    """Schedule the judge evaluation as a background task if evaluator is configured."""
    evaluator = getattr(request.app.state, "judge_evaluator", None)
    if evaluator is None:
        return
    recorder = getattr(request.app.state, "quality_recorder", None)
    background_tasks.add_task(_run_judge, evaluator, recorder, request_id, user_message, assistant_response)


async def fake_stream_response() -> AsyncIterator[str]:
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
    chat_request: ChatCompletionRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
) -> ChatCompletionResponse | StreamingResponse:
    request_id = get_request_id()
    user_message = chat_request.messages[-1].content
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter = getattr(request.app.state, "rate_limiter", None)

    if rate_limiter is not None:
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

    semantic_cache = getattr(request.app.state, "semantic_cache", None)
    if semantic_cache is not None:
        cached_response = semantic_cache.lookup(chat_request.messages[-1].content)
        if cached_response:
            api_response = ChatCompletionResponse(
                id=uuid.uuid4().hex[:12],
                object="chat.completion",
                created=int(time.time()),
                model=chat_request.model,
                choices=[
                    ChoiceSchema(
                        index=0,
                        message=ChoiceMessageSchema(
                            role="assistant",
                            content=cached_response,
                        ),
                        finish_reason="stop",
                    )
                ],
                usage=UsageSchema(
                    prompt_tokens=1,
                    completion_tokens=0,
                    total_tokens=1,
                ),
            )
            semantic_cache.store(chat_request.messages[-1].content, cached_response, chat_request.model)
            _schedule_judge(background_tasks, request, request_id, user_message, cached_response)
            return api_response

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

        async def stream_and_judge():
            collected_chunks: list[str] = []
            try:
                domain_request = to_domain_chat_request(chat_request)
                async for chunk in provider_router.stream(domain_request):
                    collected_chunks.append(chunk)
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
                return
            except AllProvidersFailedError as e:
                error_data = {
                    "error": {
                        "message": f"All providers failed: {[n for n, _ in e.errors]}",
                        "type": "server_error",
                    }
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return

            full_response = "".join(collected_chunks)
            if full_response:
                _schedule_judge(background_tasks, request, request_id, user_message, full_response)

        return StreamingResponse(
            stream_and_judge(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    cache = getattr(request.app.state, "cache", None)
    cache_key: str | None = None

    if cache is not None:
        cache_key = cache.generate_key(
            chat_request.model,
            chat_request.messages,
            chat_request.temperature,
        )
        cached_response = await cache.get(cache_key)
        if cached_response:
            api_response = ChatCompletionResponse.model_validate(cached_response)
            _schedule_judge(
                background_tasks, request, request_id, user_message,
                api_response.choices[0].message.content,
            )
            return api_response

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
        CostTracker().calculate(domain_response.usage)
        if cache is not None and cache_key is not None:
            await cache.set(cache_key, api_response.model_dump())
        _schedule_judge(
            background_tasks, request, request_id, user_message,
            domain_response.message.content,
        )
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

    if cache is not None and cache_key is not None:
        await cache.set(cache_key, api_response.model_dump())

    tracker = CostTracker()
    cost = tracker.calculate(TokenUsage(prompt_tokens=1, completion_tokens=1, model=chat_request.model, provider=""))
    logger.info("Cost: %s", cost.total_cost)
    logger.info("Prompt cost: %s", cost.prompt_cost)
    logger.info("Completion cost: %s", cost.completion_cost)
    logger.info("Usage: %s", cost.usage)

    _schedule_judge(background_tasks, request, request_id, user_message, mock_content)
    return api_response
