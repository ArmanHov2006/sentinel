from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

async def generate_words():
    """Generator that yields words one at a time."""
    words = ["Hello", " ", "world", "!"]
    for word in words:
        # SSE format: each chunk must start with "data: " and end with "\n\n"
        yield f"data: {word}\n\n"
        await asyncio.sleep(0.3)  # Simulate delay
    yield "data: [DONE]\n\n"

@app.get("/stream")
async def stream_response():
    return StreamingResponse(
        generate_words(),
        media_type="text/event-stream"
    )
