"""Chat completion request and response schemas (OpenAI-compatible)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageSchema(BaseModel):
    """A single message in a conversation."""

    role: Literal["system", "user", "assistant", "tool"] = Field(
        description="The role of the message author.",
        examples=["user"],
    )
    content: str = Field(
        description="The content of the message.",
        examples=["Hello, how are you?"],
    )


class ChatCompletionRequest(BaseModel):
    """Request body for chat completions. Compatible with the OpenAI API format."""

    model: str = Field(
        description="The model to use for completion.",
        examples=["gpt-4"],
    )
    messages: list[MessageSchema] = Field(
        description="A list of messages comprising the conversation.",
    )
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature between 0 and 2. Lower values are more deterministic.",
        examples=[0.7],
    )
    stream: bool = Field(
        default=False,
        description="If true, returns a stream of Server-Sent Events.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Hello, how are you?"},
                    ],
                    "temperature": 0.7,
                    "stream": False,
                }
            ]
        }
    )


class ChoiceMessageSchema(BaseModel):
    """The assistant's response message."""

    role: Literal["assistant"]
    content: str


class ChoiceSchema(BaseModel):
    """A single completion choice."""

    index: int = Field(default=0)
    message: ChoiceMessageSchema
    finish_reason: str | None = None


class UsageSchema(BaseModel):
    """Token usage statistics for the request."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Response from a chat completion request. Matches the OpenAI API format."""

    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: list[ChoiceSchema]
    usage: UsageSchema

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "sentinel-a1b2c3d4e5f6",
                    "object": "chat.completion",
                    "created": 1706745600,
                    "model": "gpt-4",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Hello! I'm doing well, thank you for asking.",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 24,
                        "completion_tokens": 12,
                        "total_tokens": 36,
                    },
                }
            ]
        }
    )
