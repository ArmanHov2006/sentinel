from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
from sentinel.api.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChoiceSchema,
    ChoiceMessageSchema,
    UsageSchema
)
import time
import uuid
import json

router = APIRouter(prefix="/v1")

async def fake_stream_response():
    words = ["Hello", " ", "world"," ","this"," ","is"," ","a"," ","test"," ","message",".","!"]
    for word in words:
        chunk = {"choices": [{"delta": {"content": word}}]} 
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.3)
    yield "data: [DONE]\n\n"

@router.post("/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    if request.stream:
        return StreamingResponse(fake_stream_response(), media_type="text/event-stream",
         headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
    else:
        last_message = request.messages[-1]
        user_said = last_message.content

        mock_content = f"You said: {user_said}"

        unique_id = f"sentinel-{uuid.uuid4().hex[:12]}"
        timestamp = int(time.time())

        return ChatCompletionResponse(
            id=unique_id,
            object="chat.completion",
            created=timestamp,
            model=request.model,
            choices=[
                ChoiceSchema(
                    index=0,
                    message=ChoiceMessageSchema(
                        role="assistant",
                        content=mock_content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=UsageSchema(
                prompt_tokens=10,
                completion_tokens=len(mock_content.split()),
                total_tokens=10 + len(mock_content.split())
            )
        )