from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
from sentinel.api.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChoiceSchema,
    ChoiceMessageSchema,
    UsageSchema,
)
from sentinel.api.converters import (
    to_domain_chat_request,
    to_api_chat_completion_response,
)

import time, uuid, json

router = APIRouter(prefix="/v1")


async def fake_stream_response():
    words = ["Hello", " ", "world", " ", "this", " ", "is", " ", "a", " ", "test", " ", "message", ".", "!"]
    for word in words:
        chunk = {"choices": [{"delta": {"content": word}}]}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.3)
    yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def create_chat_completion(chat_request: ChatCompletionRequest, request: Request):
    # Streaming branch
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

    # Non-streaming branch with optional cache
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
        response = to_api_chat_completion_response(domain_response)
        if cache and cache_key:
            await cache.set(cache_key, response.model_dump())
        return response

    # Fallback mock response
    last_message = chat_request.messages[-1]
    user_said = last_message.content

    mock_content = f"You said: {user_said}"

    unique_id = f"sentinel-{uuid.uuid4().hex[:12]}"
    timestamp = int(time.time())

    response = ChatCompletionResponse(
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
        await cache.set(cache_key, response.model_dump())

    return response