"""Live integration test for AnthropicProvider."""
import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sentinel.providers.anthropic import AnthropicProvider
from sentinel.core.circuit_breaker import CircuitBreaker
from sentinel.core.retry import RetryPolicy
from sentinel.domain.models import ChatRequest, Message, Role, ModelParameters


async def main():
    print("=== Anthropic Provider Live Test ===\n")
    
    # 1. Create provider
    try:
        provider = AnthropicProvider(
            circuit_breaker=CircuitBreaker(),
            retry_policy=RetryPolicy(),
        )
        print("[OK] Provider created:", provider.name)
        print("   Models:", provider.models, "\n")
    except ValueError as e:
        print("[FAIL] Failed to create provider:", e)
        print("   Make sure ANTHROPIC_API_KEY is set!")
        return

    # 2. Health check
    print("Running health check...")
    try:
        healthy = await provider.health_check()
        print("[OK] Health check:", "healthy" if healthy else "unhealthy", "\n")
    except Exception as e:
        print("[FAIL] Health check failed:", e, "\n")
        return

    # 3. Simple completion
    print("Testing completion...")
    request = ChatRequest(
        model="claude-haiku-4-20250514",
        messages=[
            Message(role=Role.SYSTEM, content="You are a helpful assistant. Be concise."),
            Message(role=Role.USER, content="What is 2 + 2? Reply with just the number."),
        ],
        parameters=ModelParameters(max_tokens=50, temperature=0.0),
    )

    try:
        response = await provider.complete(request)
        print("[OK] Completion successful!")
        print("   Model:", response.model)
        print("   Response:", response.message.content)
        print("   Finish reason:", response.finish_reason)
        print("   Tokens:", response.usage.prompt_tokens, "in,", response.usage.completion_tokens, "out")
    except Exception as e:
        print("[FAIL] Completion failed:", e)
        return

    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    asyncio.run(main())
