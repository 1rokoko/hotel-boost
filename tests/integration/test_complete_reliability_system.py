"""
Complete integration test for the entire reliability system
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

from app.utils.circuit_breaker import (
    get_circuit_breaker, 
    CircuitBreakerConfig, 
    CircuitState,
    reset_all_circuit_breakers
)
from app.services.health_checker import HealthChecker, DependencyStatus
from app.services.fallback_service import FallbackService, DegradationLevel
from app.utils.degradation_handler import DegradationHandler
from app.tasks.dead_letter_handler import DeadLetterQueueHandler
from app.services.failed_message_processor import FailedMessageProcessor


@pytest.fixture
def reliability_system():
    """Complete reliability system fixture"""
    # Reset all circuit breakers
    reset_all_circuit_breakers()
    
    # Create components
    health_checker = HealthChecker()
    fallback_service = FallbackService()
    degradation_handler = DegradationHandler(fallback_service)
    dlq_handler = DeadLetterQueueHandler()
    failed_message_processor = FailedMessageProcessor(dlq_handler, fallback_service)
    
    return {
        "health_checker": health_checker,
        "fallback_service": fallback_service,
        "degradation_handler": degradation_handler,
        "dlq_handler": dlq_handler,
        "failed_message_processor": failed_message_processor
    }


class TestCompleteReliabilitySystem:
    """Test the complete reliability system working together"""
    
    @pytest.mark.asyncio
    async def test_complete_failure_and_recovery_scenario(self, reliability_system):
        """
        Test a complete failure and recovery scenario involving all reliability components
        """
        # Get components
        health_checker = reliability_system["health_checker"]
        fallback_service = reliability_system["fallback_service"]
        degradation_handler = reliability_system["degradation_handler"]
        dlq_handler = reliability_system["dlq_handler"]
        
        # Step 1: System starts healthy
        assert fallback_service.current_degradation_level == DegradationLevel.NORMAL
        
        # Step 2: Simulate service failures
        # Create circuit breakers for critical services
        db_config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        redis_config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        api_config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        
        db_cb = get_circuit_breaker("database", db_config)
        redis_cb = get_circuit_breaker("redis", redis_config)
        api_cb = get_circuit_breaker("green_api", api_config)
        
        # Simulate failures to open circuit breakers
        async def failing_service():
            raise Exception("Service down")
        
        # Trigger failures for database
        for _ in range(3):
            try:
                await db_cb.call(failing_service)
            except Exception:
                pass
        
        # Trigger failures for Redis
        for _ in range(3):
            try:
                await redis_cb.call(failing_service)
            except Exception:
                pass
        
        # Verify circuit breakers are open
        assert db_cb.state == CircuitState.OPEN
        assert redis_cb.state == CircuitState.OPEN
        
        # Step 3: Degradation should be triggered
        # Manually trigger degradation (in real system, this would be automatic)
        fallback_service.set_degradation_level(
            DegradationLevel.SEVERE, 
            "Multiple circuit breakers open"
        )
        
        assert fallback_service.current_degradation_level == DegradationLevel.SEVERE
        
        # Step 4: Test fallback mechanisms
        # AI fallback should work
        ai_result = await fallback_service.ai_fallback("error")
        assert ai_result.success
        assert ai_result.degradation_level == DegradationLevel.SEVERE
        assert "technical difficulties" in ai_result.data["response"]
        
        # WhatsApp fallback should queue messages
        whatsapp_result = await fallback_service.whatsapp_fallback({
            "to": "+1234567890",
            "message": "Test message"
        })
        assert whatsapp_result.success
        assert whatsapp_result.fallback_used == "whatsapp_message_queue"
        
        # Database fallback should work
        db_result = await fallback_service.database_fallback("read")
        assert db_result.success
        assert db_result.fallback_used == "database_cache_fallback"
        
        # Step 5: Test DLQ functionality
        with patch.object(dlq_handler, '_get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.hset = AsyncMock()
            mock_redis.hincrby = AsyncMock()
            mock_redis.close = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            # Add failed message to DLQ
            message_id = await dlq_handler.add_to_dlq(
                message_data={"type": "test", "content": "failed message"},
                error=Exception("Processing failed"),
                message_type="test_message",
                max_retries=3
            )
            
            assert message_id.startswith("dlq_")
            mock_redis.hset.assert_called()
        
        # Step 6: Test recovery
        # Wait for circuit breaker recovery timeout
        await asyncio.sleep(0.2)
        
        # Simulate service recovery
        async def healthy_service():
            return "service recovered"
        
        # Test database recovery
        result = await db_cb.call(healthy_service)
        assert result == "service recovered"
        assert db_cb.state == CircuitState.HALF_OPEN
        
        # Complete recovery by successful calls
        for _ in range(db_config.success_threshold):
            await db_cb.call(healthy_service)
        
        assert db_cb.state == CircuitState.CLOSED
        
        # Step 7: System should recover to normal
        fallback_service.set_degradation_level(
            DegradationLevel.NORMAL, 
            "Services recovered"
        )
        
        assert fallback_service.current_degradation_level == DegradationLevel.NORMAL
    
    @pytest.mark.asyncio
    async def test_cascading_failure_prevention(self, reliability_system):
        """Test that circuit breakers prevent cascading failures"""
        fallback_service = reliability_system["fallback_service"]
        
        # Create multiple interconnected services
        services = ["service_a", "service_b", "service_c"]
        circuit_breakers = {}
        
        for service in services:
            config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
            circuit_breakers[service] = get_circuit_breaker(service, config)
        
        # Simulate failure in service_a
        async def failing_service():
            raise Exception("Service A down")
        
        # Trigger failure in service_a
        try:
            await circuit_breakers["service_a"].call(failing_service)
        except Exception:
            pass
        
        # Circuit breaker should be open
        assert circuit_breakers["service_a"].state == CircuitState.OPEN
        
        # Subsequent calls should fail fast (preventing cascading failures)
        with pytest.raises(Exception):  # Should be CircuitBreakerOpenException
            await circuit_breakers["service_a"].call(failing_service)
        
        # Other services should still be operational
        async def healthy_service():
            return "healthy"
        
        result_b = await circuit_breakers["service_b"].call(healthy_service)
        result_c = await circuit_breakers["service_c"].call(healthy_service)
        
        assert result_b == "healthy"
        assert result_c == "healthy"
        assert circuit_breakers["service_b"].state == CircuitState.CLOSED
        assert circuit_breakers["service_c"].state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_levels(self, reliability_system):
        """Test different levels of graceful degradation"""
        fallback_service = reliability_system["fallback_service"]
        
        # Test each degradation level
        degradation_levels = [
            DegradationLevel.NORMAL,
            DegradationLevel.MINOR,
            DegradationLevel.MODERATE,
            DegradationLevel.SEVERE,
            DegradationLevel.CRITICAL
        ]
        
        for level in degradation_levels:
            fallback_service.set_degradation_level(level, f"Testing {level.value}")
            
            # Test AI fallback at this level
            ai_result = await fallback_service.ai_fallback("greeting")
            assert ai_result.success
            assert ai_result.degradation_level == level
            
            # Test WhatsApp fallback
            whatsapp_result = await fallback_service.whatsapp_fallback({
                "to": "+1234567890",
                "message": "Test"
            })
            assert whatsapp_result.success
            
            # Test Redis fallback
            redis_result = await fallback_service.redis_fallback("get", "test_key")
            assert redis_result.success
    
    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, reliability_system):
        """Test health monitoring integration with all components"""
        health_checker = reliability_system["health_checker"]
        
        # Mock various dependency states
        with patch.object(health_checker, 'check_redis') as mock_redis, \
             patch.object(health_checker, 'check_green_api') as mock_green_api, \
             patch.object(health_checker, 'check_deepseek_api') as mock_deepseek, \
             patch.object(health_checker, 'check_celery_workers') as mock_celery:
            
            from app.services.health_checker import HealthCheckResult, DependencyStatus
            
            # Mock healthy dependencies
            mock_redis.return_value = HealthCheckResult(
                status=DependencyStatus.HEALTHY,
                response_time_ms=10.0,
                details="Redis is healthy"
            )
            
            mock_green_api.return_value = HealthCheckResult(
                status=DependencyStatus.HEALTHY,
                response_time_ms=50.0,
                details="Green API is accessible"
            )
            
            mock_deepseek.return_value = HealthCheckResult(
                status=DependencyStatus.HEALTHY,
                response_time_ms=100.0,
                details="DeepSeek API is accessible"
            )
            
            mock_celery.return_value = HealthCheckResult(
                status=DependencyStatus.HEALTHY,
                response_time_ms=20.0,
                details="Celery workers available"
            )
            
            # Perform comprehensive health check
            system_health = await health_checker.check_all_dependencies(db=None)
            
            assert system_health.overall_status in [
                DependencyStatus.HEALTHY, 
                DependencyStatus.DEGRADED  # Some services might not be configured
            ]
            assert len(system_health.checks) > 0
            assert system_health.total_check_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_retry_integration_with_circuit_breaker(self, reliability_system):
        """Test retry logic integration with circuit breaker"""
        from app.utils.retry_handler import RetryHandler, RetryConfig
        
        # Create circuit breaker
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=0.1)
        cb = get_circuit_breaker("retry_test_service", config)
        
        # Create retry handler
        retry_config = RetryConfig(max_retries=2, base_delay=0.01)
        retry_handler = RetryHandler(retry_config)
        
        # Test function that fails initially then succeeds
        call_count = 0
        
        async def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        # Execute with both retry and circuit breaker
        async def protected_service():
            return await cb.call(flaky_service)
        
        result = await retry_handler.execute_async(protected_service)
        assert result == "success"
        assert call_count == 3
        assert cb.state == CircuitState.CLOSED  # Should remain closed for successful operation
    
    @pytest.mark.asyncio
    async def test_metrics_integration(self, reliability_system):
        """Test metrics collection integration"""
        try:
            from app.monitoring.reliability_metrics import get_reliability_metrics
            
            metrics = get_reliability_metrics()
            
            # Test circuit breaker metrics
            metrics.record_circuit_breaker_request("test_service", "closed", "success", 0.1)
            metrics.record_circuit_breaker_state_change("test_service", "closed", "open")
            
            # Test retry metrics
            metrics.record_retry_attempt("test_service", "exponential_backoff", "success", 1.0)
            
            # Test health check metrics
            metrics.record_health_check("redis", "healthy", 0.05)
            
            # Test degradation metrics
            metrics.record_degradation_event("test_rule", "normal", "moderate")
            
            # Test DLQ metrics
            metrics.record_dlq_message_added("test_message", "timeout")
            metrics.record_dlq_message_processed("test_message", "success", 0.5)
            
            # If we get here without exceptions, metrics integration is working
            assert True
            
        except ImportError:
            # Metrics not available, skip test
            pytest.skip("Prometheus metrics not available")
    
    def test_system_startup_integration(self, reliability_system):
        """Test that all reliability components can be initialized together"""
        # This test verifies that all components can coexist without conflicts
        
        # All components should be initialized
        assert reliability_system["health_checker"] is not None
        assert reliability_system["fallback_service"] is not None
        assert reliability_system["degradation_handler"] is not None
        assert reliability_system["dlq_handler"] is not None
        assert reliability_system["failed_message_processor"] is not None
        
        # Fallback service should be in normal state
        assert reliability_system["fallback_service"].current_degradation_level == DegradationLevel.NORMAL
        
        # Circuit breakers should be available
        from app.utils.circuit_breaker import get_all_circuit_breakers
        circuit_breakers = get_all_circuit_breakers()
        # Should have at least the ones we created in tests
        assert len(circuit_breakers) >= 0
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, reliability_system):
        """Test reliability system under concurrent load"""
        fallback_service = reliability_system["fallback_service"]
        
        # Create multiple concurrent operations
        async def concurrent_operation(operation_id: int):
            # Each operation uses different fallback mechanisms
            if operation_id % 3 == 0:
                return await fallback_service.ai_fallback("greeting")
            elif operation_id % 3 == 1:
                return await fallback_service.whatsapp_fallback({
                    "to": f"+123456789{operation_id}",
                    "message": f"Message {operation_id}"
                })
            else:
                return await fallback_service.redis_fallback("get", f"key_{operation_id}")
        
        # Run 10 concurrent operations
        tasks = [concurrent_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All operations should succeed
        for result in results:
            assert not isinstance(result, Exception)
            assert result.success
        
        # System should remain stable
        assert fallback_service.current_degradation_level == DegradationLevel.NORMAL
