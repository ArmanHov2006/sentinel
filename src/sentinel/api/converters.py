"""
API ↔ Domain converters (mappers).

Goal:
- Keep FastAPI/Pydantic (API layer) types separate from domain dataclasses.
- Provide small, testable, pure functions that translate between layers.

This file intentionally contains *scaffolding only* (no final implementation),
so you can fill in the mapping logic as you build out providers/services.
"""

from __future__ import annotations

from typing import Iterable

from sentinel.api.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChoiceSchema,
    ChoiceMessageSchema,
    UsageSchema,
    MessageSchema,
)
from sentinel.domain.models import (
    ChatRequest,
    ChatResponse,
    Message,
    ModelParameters,
    Role,
)


def to_domain_role(api_role: str) -> Role:
    """Convert an API role string (e.g. 'user') into the domain Role enum.

    Think about:
    - Do you support 'tool' in the domain yet?
    - If not, do you reject it, map it, or extend Role?
    """
    match api_role:
        case "user":
            return Role.USER
        case "assistant":
            return Role.ASSISTANT
        case "system":
            return Role.SYSTEM
        case "tool":
            return Role.TOOL
        case _:
            raise ValueError(f"Invalid role: {api_role}")


def to_domain_message(api_message: MessageSchema) -> Message:
    """Convert one API MessageSchema into one domain Message."""
    role_string = api_message.role
    role = to_domain_role(role_string)
    content = api_message.content
    return Message(role=role, content=content)


def to_domain_messages(api_messages: Iterable[MessageSchema]) -> list[Message]:
    """Convert a sequence of API messages into domain messages."""
    return [to_domain_message(api_message) for api_message in api_messages]


def to_domain_parameters(api_request: ChatCompletionRequest) -> ModelParameters:
    """Convert API request fields into ModelParameters.

    Think about:
    - Right now your API schema has: temperature
    - Later you may add: max_tokens, top_p, stop, etc.
    """
    return ModelParameters(temperature=api_request.temperature)


def to_domain_chat_request(api_request: ChatCompletionRequest) -> ChatRequest:
    """Convert API ChatCompletionRequest -> domain ChatRequest.

    Think about:
    - ChatRequest has defaults for id/created_at/metadata.
    - This function should be pure and deterministic (no I/O).
    """
    model = api_request.model
    messages = to_domain_messages(api_request.messages)
    parameters = to_domain_parameters(api_request)
    return ChatRequest(model=model, messages=messages, parameters=parameters)


def to_api_chat_completion_response(domain: ChatResponse) -> ChatCompletionResponse:
    """Convert domain ChatResponse → API ChatCompletionResponse."""
    finish_reason_str = domain.finish_reason.value if domain.finish_reason else None
    usage = UsageSchema(
        prompt_tokens=domain.usage.prompt_tokens,
        completion_tokens=domain.usage.completion_tokens,
        total_tokens=domain.usage.total_tokens,
    )
    created_ts = int(domain.created_at.timestamp()) if hasattr(domain.created_at, "timestamp") else 0
    return ChatCompletionResponse(
        id=domain.request_id,
        object="chat.completion",
        created=created_ts,
        model=domain.model,
        choices=[
            ChoiceSchema(
                index=0,
                message=ChoiceMessageSchema(
                    role="assistant",
                    content=domain.message.content,
                ),
                finish_reason=finish_reason_str,
            )
        ],
        usage=usage,
    )

