from abc import ABC, abstractmethod

from sentinel.domain.models import ChatRequest, ChatResponse

class LLMProvider(ABC):
    @abstractmethod
    async def health_check(self) -> bool:
        pass

    @abstractmethod
    async def complete(self, request: ChatRequest) -> ChatResponse:
        pass