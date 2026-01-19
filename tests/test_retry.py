"""Tests for Retry Policy implementation."""

import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sentinel.core.retry import RetryPolicy


class TestRetryPolicy:
    """Test suite for RetryPolicy class."""
    
    def test_initial_parameters(self):
        """Retry policy should initialize with default parameters."""
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 40.0
    
    def test_custom_parameters(self):
        """Retry policy should accept custom parameters."""
        policy = RetryPolicy(max_attempts=5, base_delay=2.0, max_delay=60.0)
        assert policy.max_attempts == 5
        assert policy.base_delay == 2.0
        assert policy.max_delay == 60.0
    
    def test_calculate_backoff_time(self):
        """Backoff time should increase exponentially with jitter."""
        policy = RetryPolicy(base_delay=1.0, max_delay=40.0)
        
        # Test first attempt - base_delay * 2^1 + jitter (0 to base_delay)
        delay1 = policy.calculate_backoff_time(1)
        assert 1.0 <= delay1 <= 3.0  # 2.0 + jitter up to 1.0
        
        # Test second attempt - base_delay * 2^2 + jitter
        delay2 = policy.calculate_backoff_time(2)
        assert 4.0 <= delay2 <= 5.0  # 4.0 + jitter up to 1.0
        
        # Test third attempt - base_delay * 2^3 + jitter
        delay3 = policy.calculate_backoff_time(3)
        assert 8.0 <= delay3 <= 9.0  # 8.0 + jitter up to 1.0
    
    def test_backoff_respects_max_delay(self):
        """Backoff time should not exceed max_delay."""
        policy = RetryPolicy(base_delay=1.0, max_delay=5.0)
        
        # Even with high attempt number, should cap at max_delay
        delay = policy.calculate_backoff_time(10)
        assert delay <= 5.0
    
    @pytest.mark.anyio
    async def test_execute_with_retry_success_first_attempt(self):
        """Should succeed on first attempt without retrying."""
        policy = RetryPolicy(max_attempts=3)
        
        async def success_func():
            return "success"
        
        result = await policy.execute_with_retry(success_func)
        assert result == "success"
    
    @pytest.mark.anyio
    async def test_execute_with_retry_success_after_failures(self):
        """Should retry and succeed after initial failures."""
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await policy.execute_with_retry(flaky_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.anyio
    async def test_execute_with_retry_exhausts_attempts(self):
        """Should raise exception after exhausting all attempts."""
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)
        
        call_count = 0
        
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError, match="Always fails"):
            await policy.execute_with_retry(always_fail)
        
        assert call_count == 3  # Should try all 3 attempts
    
    @pytest.mark.anyio
    async def test_execute_with_retry_with_args(self):
        """Should pass arguments correctly to the function."""
        policy = RetryPolicy(max_attempts=3)
        
        async def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"
        
        result = await policy.execute_with_retry(
            func_with_args, "arg1", "arg2", c="arg3"
        )
        assert result == "arg1-arg2-arg3"
    
    @pytest.mark.anyio
    async def test_execute_with_retry_with_kwargs(self):
        """Should pass keyword arguments correctly."""
        policy = RetryPolicy(max_attempts=3)
        
        async def func_with_kwargs(**kwargs):
            return kwargs
        
        result = await policy.execute_with_retry(
            func_with_kwargs, key1="value1", key2="value2"
        )
        assert result == {"key1": "value1", "key2": "value2"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
