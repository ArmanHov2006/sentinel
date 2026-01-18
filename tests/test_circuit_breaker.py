"""Tests for Circuit Breaker implementation."""

import os
import sys
import pytest
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sentinel.core.circuit_breaker import CircuitBreaker, CircuitBreakerState


class TestCircuitBreaker:
    """Test suite for CircuitBreaker class."""
    
    def test_initial_state(self):
        """Circuit breaker should start in Closed state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.Closed
        assert cb.failure_count == 0
        assert cb.can_execute() is True
    
    def test_custom_parameters(self):
        """Circuit breaker should accept custom failure threshold and recovery timeout."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0
    
    def test_record_success_resets_counter(self):
        """Recording success should reset failure count and state to Closed."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.Closed
    
    def test_record_failure_increments_counter(self):
        """Recording failure should increment failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.failure_count == 1
        cb.record_failure()
        assert cb.failure_count == 2
    
    def test_opens_after_threshold(self):
        """Circuit breaker should open after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        
        # Record failures up to threshold
        cb.record_failure()
        assert cb.state == CircuitBreakerState.Closed
        cb.record_failure()
        assert cb.state == CircuitBreakerState.Closed
        cb.record_failure()
        
        # Should now be open
        assert cb.state == CircuitBreakerState.Open
        assert cb.failure_count == 3
    
    def test_cannot_execute_when_open(self):
        """Circuit breaker should not allow execution when in Open state."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        
        assert cb.state == CircuitBreakerState.Open
        assert cb.can_execute() is False
    
    def test_half_open_after_recovery_timeout(self):
        """Circuit breaker should transition to HalfOpen after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.Open
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Should now be HalfOpen and allow execution
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HalfOpen
    
    def test_stays_closed_until_threshold(self):
        """Circuit breaker should stay closed until threshold is reached."""
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_failure()
        assert cb.state == CircuitBreakerState.Closed
        assert cb.can_execute() is True
        
        cb.record_failure()
        assert cb.state == CircuitBreakerState.Closed
        assert cb.can_execute() is True
        
        # One more failure should open it
        cb.record_failure()
        assert cb.state == CircuitBreakerState.Open
    
    def test_success_after_half_open_closes_circuit(self):
        """Recording success in HalfOpen state should close the circuit."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        
        # Wait for recovery
        time.sleep(0.15)
        cb.can_execute()  # This transitions to HalfOpen
        
        # Record success
        cb.record_success()
        assert cb.state == CircuitBreakerState.Closed
        assert cb.failure_count == 0
    
    def test_failure_in_half_open_opens_again(self):
        """Recording failure in HalfOpen state should open the circuit again."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        
        # Wait for recovery
        time.sleep(0.15)
        cb.can_execute()  # Transitions to HalfOpen
        
        # Record another failure
        cb.record_failure()
        assert cb.state == CircuitBreakerState.Open
        assert cb.failure_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
