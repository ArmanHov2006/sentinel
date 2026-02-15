"""
Manual test for OpenAIProvider.stream().

Requires OPENAI_API_KEY in the environment (or in .env in project root).
Run from project root:  PYTHONPATH=src  python scripts/test_openai_stream.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sentinel.core.circuit_breaker import CircuitBreaker
from sentinel.core.retry import RetryPolicy
from sentinel.domain.models import ChatRequest, Message, ModelParameters, Role
from sentinel.providers.openai import OpenAIProvider


async def main():
    # Create provider with circuit breaker and retry policy
    circuit_breaker = CircuitBreaker()
    retry_policy = RetryPolicy()
    provider = OpenAIProvider(circuit_breaker, retry_policy)

    # Create a simple request
    request = ChatRequest(
        messages=[Message(role=Role.USER, content="Say hello in 3 different languages")],
        model="gpt-4o-mini",
        parameters=ModelParameters(temperature=0.7),
    )

    # Stream the response
    print("Streaming response:")
    async for chunk in provider.stream(request):
        print(chunk, end="", flush=True)

    print("\n\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
