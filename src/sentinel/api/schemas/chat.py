from pydantic import BaseModel, Field
from typing import Literal, Optional

class MessageSchema(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[MessageSchema]
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    stream: bool = False

class ChoiceMessageSchema(BaseModel):
    role: Literal["assistant"]
    content: str

class ChoiceSchema(BaseModel):
    index: int = Field(default=0)
    message: ChoiceMessageSchema
    finish_reason: Optional[str] = None

class UsageSchema(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: list[ChoiceSchema]
    usage: UsageSchema