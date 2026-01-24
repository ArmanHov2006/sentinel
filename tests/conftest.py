"""Pytest configuration for Sentinel tests."""

import pytest


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"
