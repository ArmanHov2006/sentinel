"""Pytest configuration and shared fixtures for Sentinel tests."""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_redis():
    """Async mock Redis client that behaves like aioredis."""
    r = AsyncMock()
    r.get.return_value = None
    r.ping.return_value = True
    r.pipeline.return_value = AsyncMock()
    r.scan_iter.return_value = AsyncMock(return_value=[]).__aiter__()
    return r


@pytest.fixture
def settings():
    """Test settings with auth disabled and safe defaults."""
    with patch.dict(os.environ, {}, clear=False):
        from sentinel.core.config import Settings

        return Settings(
            openai_api_key="sk-test-fake-key",
            anthropic_api_key="test-anthropic-key",
            require_auth=False,
            sentinel_env="test",
        )


@pytest.fixture
def sample_chat_request():
    """A minimal domain ChatRequest for testing."""
    from sentinel.domain.models import ChatRequest, Message, Role

    return ChatRequest(
        messages=[Message(role=Role.USER, content="Hello, how are you?")],
        model="gpt-4o-mini",
    )
