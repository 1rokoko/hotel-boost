"""
Unit tests for circuit breaker implementation
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock

from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenException,
    CircuitBreakerTimeoutException,
    get_circuit_breaker,
    reset_all_circuit_breakers
)


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 3
        assert config.timeout == 30.0
        assert config.window_size == 100
        assert config.minimum_requests == 10
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
            timeout=15.0
        )
        
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 30.0
        assert config.success_threshold == 2
        assert config.timeout == 15.0


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,  # Short timeout for testing
            success_threshold=2,
            timeout=1.0,
            window_size=10,
            minimum_requests=3
        )
        self.circuit_breaker = CircuitBreaker("test_service", self.config)
    
    def test_initial_state(self):
        """Test initial circuit breaker state"""
        assert self.circuit_breaker.state == CircuitState.CLOSED
        assert self.circuit_breaker.failure_count == 0
        assert self.circuit_breaker.success_count == 0
    
    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful function call"""
        async def success_func():
            return "success"
        
        result = await self.circuit_breaker.call(success_func)
        assert result == "success"
        assert self.circuit_breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_failed_call(self):
        """Test failed function call"""
        async def fail_func():
            raise Exception("Test error")
        
        with pytest.raises(Exception, match="Test error"):
            await self.circuit_breaker.call(fail_func)
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test circuit opens after threshold failures"""
        async def fail_func():
            raise Exception("Test error")
        
        # Add minimum requests to window first
        for _ in range(self.config.minimum_requests):
            try:
                await self.circuit_breaker.call(fail_func)
            except Exception:
                pass
        
        # Circuit should be open now
        assert self.circuit_breaker.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_fails_fast_when_open(self):
        """Test circuit fails fast when open"""
        # Force circuit to open
        self.circuit_breaker.state = CircuitState.OPEN
        self.circuit_breaker.next_attempt_time = time.time() + 10  # Future time
        
        async def any_func():
            return "should not execute"
        
        with pytest.raises(CircuitBreakerOpenException):
            await self.circuit_breaker.call(any_func)
    
    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(self):
        """Test circuit transitions to half-open after timeout"""
        # Force circuit to open with past recovery time
        self.circuit_breaker.state = CircuitState.OPEN
        self.circuit_breaker.next_attempt_time = time.time() - 1  # Past time
        
        async def success_func():
            return "success"
        
        result = await self.circuit_breaker.call(success_func)
        assert result == "success"
        assert self.circuit_breaker.state == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_closes_after_successful_half_open(self):
        """Test circuit closes after successful half-open attempts"""
        # Set to half-open
        self.circuit_breaker.state = CircuitState.HALF_OPEN
        self.circuit_breaker.success_count = 0
        
        async def success_func():
            return "success"
        
        # Execute successful calls to reach success threshold
        for _ in range(self.config.success_threshold):
            await self.circuit_breaker.call(success_func)
        
        assert self.circuit_breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_reopens_on_half_open_failure(self):
        """Test circuit reopens on failure during half-open"""
        # Set to half-open
        self.circuit_breaker.state = CircuitState.HALF_OPEN
        
        async def fail_func():
            raise Exception("Test error")
        
        with pytest.raises(Exception):
            await self.circuit_breaker.call(fail_func)
        
        assert self.circuit_breaker.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling"""
        async def slow_func():
            await asyncio.sleep(2.0)  # Longer than timeout
            return "should timeout"
        
        with pytest.raises(CircuitBreakerTimeoutException):
            await self.circuit_breaker.call(slow_func)
    
    def test_metrics(self):
        """Test metrics collection"""
        metrics = self.circuit_breaker.get_metrics()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.success_rate() == 1.0
        assert metrics.failure_rate() == 0.0
    
    def test_reset(self):
        """Test circuit breaker reset"""
        # Modify state
        self.circuit_breaker.state = CircuitState.OPEN
        self.circuit_breaker.failure_count = 5
        
        # Reset
        self.circuit_breaker.reset()
        
        assert self.circuit_breaker.state == CircuitState.CLOSED
        assert self.circuit_breaker.failure_count == 0
        assert len(self.circuit_breaker.request_window) == 0


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry functions"""
    
    def setup_method(self):
        """Setup for each test"""
        reset_all_circuit_breakers()
    
    def test_get_circuit_breaker_creates_new(self):
        """Test getting circuit breaker creates new instance"""
        cb = get_circuit_breaker("test_service")
        
        assert cb.name == "test_service"
        assert isinstance(cb, CircuitBreaker)
    
    def test_get_circuit_breaker_returns_existing(self):
        """Test getting circuit breaker returns existing instance"""
        cb1 = get_circuit_breaker("test_service")
        cb2 = get_circuit_breaker("test_service")
        
        assert cb1 is cb2
    
    def test_get_circuit_breaker_with_config(self):
        """Test getting circuit breaker with custom config"""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = get_circuit_breaker("test_service", config)
        
        assert cb.config.failure_threshold == 10
    
    def test_reset_all_circuit_breakers(self):
        """Test resetting all circuit breakers"""
        # Create some circuit breakers
        cb1 = get_circuit_breaker("service1")
        cb2 = get_circuit_breaker("service2")
        
        # Modify their state
        cb1.state = CircuitState.OPEN
        cb2.state = CircuitState.HALF_OPEN
        
        # Reset all
        reset_all_circuit_breakers()
        
        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_integration():
    """Integration test for circuit breaker"""
    config = CircuitBreakerConfig(
        failure_threshold=2,
        recovery_timeout=0.1,
        success_threshold=1,
        window_size=5,
        minimum_requests=2
    )
    
    cb = CircuitBreaker("integration_test", config)
    
    # Simulate service calls
    call_count = 0
    
    async def unreliable_service():
        nonlocal call_count
        call_count += 1
        
        if call_count <= 3:
            raise Exception("Service unavailable")
        else:
            return f"Success on call {call_count}"
    
    # First few calls should fail and open circuit
    for _ in range(3):
        try:
            await cb.call(unreliable_service)
        except Exception:
            pass
    
    # Circuit should be open
    assert cb.state == CircuitState.OPEN
    
    # Wait for recovery timeout
    await asyncio.sleep(0.2)
    
    # Next call should succeed and close circuit
    result = await cb.call(unreliable_service)
    assert "Success" in result
    assert cb.state == CircuitState.CLOSED
