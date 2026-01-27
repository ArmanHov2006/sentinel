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
from sentinel.shield.pii_shield import PIIAction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


async def fake_stream_response():
    words = ["Hello", " ", "world", " ", "this", " ", "is", " ", "a", " ", "test", " ", "message", ".", "!"]
    for word in words:
        chunk = {"choices": [{"delta": {"content": word}}]}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.3)
    yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def create_chat_completion(
    chat_request: ChatCompletionRequest,
    request: Request,
    response: Response
):
    # 1. Rate limiting (FIRST — protect resources)
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter = getattr(request.app.state, "rate_limiter", None)
    
    if rate_limiter:
        allowed = await rate_limiter.is_allowed(client_ip)
        if not allowed:
            remaining = await rate_limiter.get_remaining(client_ip)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(rate_limiter.window_seconds)}
            )
        
        # Add rate limit headers
        remaining = await rate_limiter.get_remaining(client_ip)
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    

    # 2. PII shield
    pii_shield = getattr(request.app.state, "pii_shield", None)
    if pii_shield is not None:
        messages_as_dicts = [{"role": m.role, "content": m.content} for m in chat_request.messages]
        results = pii_shield.scan_messages(messages_as_dicts)
        if results:
            if any(r.should_block for r in results.values()):
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

    # 3. Streaming branch
    if chat_request.stream:
        return StreamingResponse(
            fake_stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # 4. Non-streaming branch with optional cache
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
            # Assume cached_response is the serialized dict form of ChatCompletionResponse
            return ChatCompletionResponse.model_validate(cached_response)

    # Try provider; fall back to mock if missing or on error
    provider = getattr(request.app.state, "provider", None)
    domain_response = None
    if provider is not None:
        try:
            domain_request = to_domain_chat_request(chat_request)
            domain_response = await provider.complete(domain_request)
        except Exception:
            domain_response = None
    if domain_response is not None:
        api_response = to_api_chat_completion_response(domain_response)
        if cache and cache_key:
            await cache.set(cache_key, api_response.model_dump())
        return api_response

    # Fallback mock response
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

    # Store in cache for future identical requests
    if cache and cache_key:
        await cache.set(cache_key, api_response.model_dump())

    return api_response