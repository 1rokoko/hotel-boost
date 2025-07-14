"""
Unit tests for retry handler implementation
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock

from app.utils.retry_handler import (
    RetryHandler,
    RetryConfig,
    RetryStrategy,
    retry_async,
    retry_sync
)


class TestRetryConfig:
    """Test retry configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            strategy=RetryStrategy.LINEAR_BACKOFF
        )
        
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.strategy == RetryStrategy.LINEAR_BACKOFF


class TestRetryHandler:
    """Test retry handler functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.config = RetryConfig(
            max_retries=3,
            base_delay=0.1,  # Short delay for testing
            max_delay=1.0,
            jitter=False  # Disable jitter for predictable testing
        )
        self.retry_handler = RetryHandler(self.config)
    
    def test_should_retry_logic(self):
        """Test retry decision logic"""
        # Should retry on retryable exceptions
        assert self.retry_handler._should_retry(Exception("test"), 0)
        assert self.retry_handler._should_retry(Exception("test"), 2)
        
        # Should not retry when max retries exceeded
        assert not self.retry_handler._should_retry(Exception("test"), 3)
        
        # Should not retry on non-retryable exceptions
        config = RetryConfig(non_retryable_exceptions=(ValueError,))
        handler = RetryHandler(config)
        assert not handler._should_retry(ValueError("test"), 0)
    
    def test_calculate_delay_exponential(self):
        """Test exponential backoff delay calculation"""
        handler = RetryHandler(RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
            jitter=False
        ))
        
        assert handler._calculate_delay(0) == 1.0
        assert handler._calculate_delay(1) == 2.0
        assert handler._calculate_delay(2) == 4.0
        assert handler._calculate_delay(3) == 8.0
        assert handler._calculate_delay(4) == 10.0  # Capped at max_delay
    
    def test_calculate_delay_linear(self):
        """Test linear backoff delay calculation"""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=10.0,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            jitter=False
        )
        handler = RetryHandler(config)
        
        assert handler._calculate_delay(0) == 1.0
        assert handler._calculate_delay(1) == 2.0
        assert handler._calculate_delay(2) == 3.0
        assert handler._calculate_delay(3) == 4.0
    
    def test_calculate_delay_fixed(self):
        """Test fixed delay calculation"""
        config = RetryConfig(
            base_delay=2.0,
            strategy=RetryStrategy.FIXED_DELAY,
            jitter=False
        )
        handler = RetryHandler(config)
        
        assert handler._calculate_delay(0) == 2.0
        assert handler._calculate_delay(1) == 2.0
        assert handler._calculate_delay(2) == 2.0
    
    def test_calculate_delay_fibonacci(self):
        """Test fibonacci backoff delay calculation"""
        config = RetryConfig(
            base_delay=1.0,
            strategy=RetryStrategy.FIBONACCI_BACKOFF,
            jitter=False
        )
        handler = RetryHandler(config)
        
        assert handler._calculate_delay(0) == 1.0  # 1 * 1
        assert handler._calculate_delay(1) == 1.0  # 1 * 1
        assert handler._calculate_delay(2) == 2.0  # 1 * 2
        assert handler._calculate_delay(3) == 3.0  # 1 * 3
        assert handler._calculate_delay(4) == 5.0  # 1 * 5
    
    @pytest.mark.asyncio
    async def test_execute_async_success(self):
        """Test successful async execution"""
        async def success_func():
            return "success"
        
        result = await self.retry_handler.execute_async(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_execute_async_retry_then_success(self):
        """Test async execution with retry then success"""
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await self.retry_handler.execute_async(flaky_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_async_max_retries_exceeded(self):
        """Test async execution with max retries exceeded"""
        async def always_fail():
            raise Exception("Always fails")
        
        with pytest.raises(Exception, match="Always fails"):
            await self.retry_handler.execute_async(always_fail)
    
    def test_execute_sync_success(self):
        """Test successful sync execution"""
        def success_func():
            return "success"
        
        result = self.retry_handler.execute_sync(success_func)
        assert result == "success"
    
    def test_execute_sync_retry_then_success(self):
        """Test sync execution with retry then success"""
        call_count = 0
        
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = self.retry_handler.execute_sync(flaky_func)
        assert result == "success"
        assert call_count == 3
    
    def test_execute_sync_max_retries_exceeded(self):
        """Test sync execution with max retries exceeded"""
        def always_fail():
            raise Exception("Always fails")
        
        with pytest.raises(Exception, match="Always fails"):
            self.retry_handler.execute_sync(always_fail)
    
    @pytest.mark.asyncio
    async def test_retry_condition_callback(self):
        """Test custom retry condition"""
        def custom_retry_condition(exception):
            return "retry" in str(exception)
        
        config = RetryConfig(
            max_retries=2,
            base_delay=0.01,
            retry_condition=custom_retry_condition
        )
        handler = RetryHandler(config)
        
        # Should retry
        call_count = 0
        async def func_with_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("retry this")
            return "success"
        
        result = await handler.execute_async(func_with_retry)
        assert result == "success"
        assert call_count == 2
        
        # Should not retry
        async def func_no_retry():
            raise Exception("do not retry")
        
        with pytest.raises(Exception, match="do not retry"):
            await handler.execute_async(func_no_retry)
    
    @pytest.mark.asyncio
    async def test_callbacks(self):
        """Test retry and failure callbacks"""
        retry_calls = []
        failure_calls = []
        
        def on_retry(attempt, exception, delay):
            retry_calls.append((attempt, str(exception), delay))
        
        def on_failure(exception, total_attempts):
            failure_calls.append((str(exception), total_attempts))
        
        config = RetryConfig(
            max_retries=2,
            base_delay=0.01,
            on_retry=on_retry,
            on_failure=on_failure
        )
        handler = RetryHandler(config)
        
        async def always_fail():
            raise Exception("Test failure")
        
        with pytest.raises(Exception):
            await handler.execute_async(always_fail)
        
        # Check callbacks were called
        assert len(retry_calls) == 2
        assert len(failure_calls) == 1
        assert failure_calls[0][1] == 3  # Total attempts


class TestRetryConvenienceFunctions:
    """Test convenience retry functions"""
    
    @pytest.mark.asyncio
    async def test_retry_async_default_config(self):
        """Test retry_async with default config"""
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"
        
        result = await retry_async(flaky_func)
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_async_custom_config(self):
        """Test retry_async with custom config"""
        config = RetryConfig(max_retries=1, base_delay=0.01)
        
        call_count = 0
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        # Should fail because max_retries=1 is not enough
        with pytest.raises(Exception):
            await retry_async(flaky_func, config)
        
        assert call_count == 2  # Initial call + 1 retry
    
    def test_retry_sync_default_config(self):
        """Test retry_sync with default config"""
        call_count = 0
        
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"
        
        result = retry_sync(flaky_func)
        assert result == "success"
        assert call_count == 2


@pytest.mark.asyncio
async def test_retry_handler_integration():
    """Integration test for retry handler"""
    # Simulate a service that fails initially then recovers
    service_state = {"failures": 0, "max_failures": 3}
    
    async def unreliable_service():
        if service_state["failures"] < service_state["max_failures"]:
            service_state["failures"] += 1
            raise Exception(f"Service failure #{service_state['failures']}")
        return "Service recovered"
    
    config = RetryConfig(
        max_retries=5,
        base_delay=0.01,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF
    )
    
    handler = RetryHandler(config)
    result = await handler.execute_async(unreliable_service)
    
    assert result == "Service recovered"
    assert service_state["failures"] == 3
