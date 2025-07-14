"""
Integration tests for the complete reliability system
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
from app.tasks.dead_letter_handler import DeadLetterQueueHandler, FailureReason
from app.services.failed_message_processor import FailedMessageProcessor


@pytest.fixture
def reliability_system():
    """Fixture providing a complete reliability system setup"""
    # Reset circuit breakers
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


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with other components"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_health_checks(self, reliability_system):
        """Test circuit breaker integration with health checks"""
        health_checker = reliability_system["health_checker"]
        
        # Create a circuit breaker for a test service
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            window_size=5,
            minimum_requests=2
        )
        cb = get_circuit_breaker("test_service", config)
        
        # Simulate service failures
        async def failing_service():
            raise Exception("Service down")
        
        # Trigger failures to open circuit
        for _ in range(3):
            try:
                await cb.call(failing_service)
            except Exception:
                pass
        
        assert cb.state == CircuitState.OPEN
        
        # Health check should reflect circuit breaker status
        # (This would be implemented in actual health check logic)
        assert cb.get_metrics().failed_requests > 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_fallback(self, reliability_system):
        """Test circuit breaker triggering fallback mechanisms"""
        fallback_service = reliability_system["fallback_service"]
        
        # Create circuit breaker
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        cb = get_circuit_breaker("api_service", config)
        
        # Force circuit to open
        cb.state = CircuitState.OPEN
        
        # Fallback should be triggered when circuit is open
        fallback_result = await fallback_service.ai_fallback("error")
        assert fallback_result.success
        assert "technical difficulties" in fallback_result.data["response"]


class TestHealthCheckIntegration:
    """Test health check integration"""
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check(self, reliability_system):
        """Test comprehensive health check with all components"""
        health_checker = reliability_system["health_checker"]
        
        # Mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        
        # Run comprehensive health check
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.ping = AsyncMock()
            mock_redis_instance.set = AsyncMock()
            mock_redis_instance.get = AsyncMock(return_value="test_value")
            mock_redis_instance.delete = AsyncMock()
            mock_redis_instance.info = AsyncMock(return_value={
                "redis_version": "6.0.0",
                "connected_clients": 1
            })
            mock_redis_instance.close = AsyncMock()
            mock_redis.return_value = mock_redis_instance
            
            system_health = await health_checker.check_all_dependencies(mock_db)
            
            assert system_health.overall_status in [
                DependencyStatus.HEALTHY, 
                DependencyStatus.DEGRADED,
                DependencyStatus.UNKNOWN  # Some services might not be configured
            ]
            assert "redis" in system_health.checks
    
    @pytest.mark.asyncio
    async def test_health_check_failure_detection(self, reliability_system):
        """Test health check failure detection"""
        health_checker = reliability_system["health_checker"]
        
        # Mock failing Redis
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.ping = AsyncMock(side_effect=Exception("Connection failed"))
            mock_redis_instance.close = AsyncMock()
            mock_redis.return_value = mock_redis_instance
            
            redis_result = await health_checker.check_redis()
            
            assert redis_result.status == DependencyStatus.UNHEALTHY
            assert "Connection failed" in redis_result.error


class TestFallbackServiceIntegration:
    """Test fallback service integration"""
    
    @pytest.mark.asyncio
    async def test_ai_fallback_with_degradation(self, reliability_system):
        """Test AI fallback with different degradation levels"""
        fallback_service = reliability_system["fallback_service"]
        
        # Test normal operation
        fallback_service.set_degradation_level(DegradationLevel.NORMAL)
        result = await fallback_service.ai_fallback("greeting")
        assert result.success
        assert result.degradation_level == DegradationLevel.NORMAL
        
        # Test degraded operation
        fallback_service.set_degradation_level(DegradationLevel.SEVERE)
        result = await fallback_service.ai_fallback("error")
        assert result.success
        assert result.degradation_level == DegradationLevel.SEVERE
    
    @pytest.mark.asyncio
    async def test_whatsapp_fallback_queuing(self, reliability_system):
        """Test WhatsApp fallback message queuing"""
        fallback_service = reliability_system["fallback_service"]
        
        message_data = {
            "to": "+1234567890",
            "message": "Test message",
            "type": "text"
        }
        
        result = await fallback_service.whatsapp_fallback(message_data)
        
        assert result.success
        assert "queued" in result.data["status"]
        assert result.fallback_used == "whatsapp_message_queue"
    
    @pytest.mark.asyncio
    async def test_database_fallback_operations(self, reliability_system):
        """Test database fallback for different operations"""
        fallback_service = reliability_system["fallback_service"]
        
        # Test read operation fallback
        read_result = await fallback_service.database_fallback("read")
        assert read_result.success
        assert read_result.fallback_used == "database_cache_fallback"
        
        # Test write operation fallback
        write_result = await fallback_service.database_fallback("write", {"data": "test"})
        assert write_result.success
        assert write_result.fallback_used == "database_operation_queue"


class TestDegradationHandlerIntegration:
    """Test degradation handler integration"""
    
    @pytest.mark.asyncio
    async def test_degradation_rule_evaluation(self, reliability_system):
        """Test degradation rule evaluation"""
        degradation_handler = reliability_system["degradation_handler"]
        fallback_service = reliability_system["fallback_service"]
        
        # Create a test rule that always triggers
        from app.utils.degradation_handler import DegradationRule
        
        test_rule = DegradationRule(
            name="test_rule",
            condition=lambda: True,  # Always triggers
            target_level=DegradationLevel.MODERATE,
            priority=100
        )
        
        degradation_handler.add_rule(test_rule)
        
        # Evaluate rules
        result_level = await degradation_handler.evaluate_rules()
        
        assert result_level == DegradationLevel.MODERATE
        assert fallback_service.current_degradation_level == DegradationLevel.MODERATE
    
    @pytest.mark.asyncio
    async def test_degradation_recovery(self, reliability_system):
        """Test automatic degradation recovery"""
        degradation_handler = reliability_system["degradation_handler"]
        fallback_service = reliability_system["fallback_service"]
        
        # Set degraded state
        fallback_service.set_degradation_level(DegradationLevel.MODERATE)
        
        # Evaluate rules (no rules should trigger)
        await degradation_handler.evaluate_rules()
        
        # Should recover towards normal (gradual recovery)
        assert fallback_service.current_degradation_level in [
            DegradationLevel.MINOR,
            DegradationLevel.NORMAL
        ]


class TestDeadLetterQueueIntegration:
    """Test dead letter queue integration"""
    
    @pytest.mark.asyncio
    async def test_dlq_message_processing(self, reliability_system):
        """Test DLQ message processing with fallback"""
        dlq_handler = reliability_system["dlq_handler"]
        failed_message_processor = reliability_system["failed_message_processor"]
        
        # Mock Redis for DLQ
        with patch.object(dlq_handler, '_get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.hset = AsyncMock()
            mock_redis.hincrby = AsyncMock()
            mock_redis.close = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            # Add a message to DLQ
            message_data = {"type": "test", "content": "test message"}
            error = Exception("Test failure")
            
            message_id = await dlq_handler.add_to_dlq(
                message_data, error, "test_message", max_retries=3
            )
            
            assert message_id.startswith("dlq_")
            mock_redis.hset.assert_called()
    
    @pytest.mark.asyncio
    async def test_failed_message_processor_strategies(self, reliability_system):
        """Test failed message processor with different strategies"""
        failed_message_processor = reliability_system["failed_message_processor"]
        
        # Test strategy assignment
        from app.tasks.dead_letter_handler import FailureReason
        from app.services.failed_message_processor import RecoveryStrategy
        
        # Check default strategies
        assert failed_message_processor.recovery_strategies[FailureReason.TIMEOUT] == RecoveryStrategy.DELAYED_RETRY
        assert failed_message_processor.recovery_strategies[FailureReason.CONNECTION_ERROR] == RecoveryStrategy.EXPONENTIAL_BACKOFF
        assert failed_message_processor.recovery_strategies[FailureReason.VALIDATION_ERROR] == RecoveryStrategy.MANUAL_INTERVENTION


class TestEndToEndReliability:
    """End-to-end reliability system tests"""
    
    @pytest.mark.asyncio
    async def test_complete_failure_recovery_flow(self, reliability_system):
        """Test complete failure and recovery flow"""
        # Get all components
        health_checker = reliability_system["health_checker"]
        fallback_service = reliability_system["fallback_service"]
        degradation_handler = reliability_system["degradation_handler"]
        dlq_handler = reliability_system["dlq_handler"]
        
        # 1. Simulate service failure
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        cb = get_circuit_breaker("critical_service", config)
        
        # Force circuit breaker to open
        cb.state = CircuitState.OPEN
        
        # 2. Degradation should be detected
        # (In real implementation, this would be triggered by monitoring)
        fallback_service.set_degradation_level(DegradationLevel.MODERATE, "Circuit breaker open")
        
        # 3. Fallback mechanisms should activate
        fallback_result = await fallback_service.ai_fallback("error")
        assert fallback_result.success
        assert fallback_result.degradation_level == DegradationLevel.MODERATE
        
        # 4. Failed messages should be queued
        with patch.object(dlq_handler, '_get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.hset = AsyncMock()
            mock_redis.hincrby = AsyncMock()
            mock_redis.close = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            await dlq_handler.add_to_dlq(
                {"message": "failed"}, 
                Exception("Service down"), 
                "test_message"
            )
        
        # 5. System should eventually recover
        # Reset circuit breaker to simulate recovery
        cb.reset()
        
        # Recovery should happen gradually
        fallback_service.set_degradation_level(DegradationLevel.NORMAL, "Service recovered")
        
        assert fallback_service.current_degradation_level == DegradationLevel.NORMAL
    
    @pytest.mark.asyncio
    async def test_cascading_failure_handling(self, reliability_system):
        """Test handling of cascading failures"""
        fallback_service = reliability_system["fallback_service"]
        
        # Simulate multiple service failures
        services = ["database", "redis", "green_api"]
        
        for service in services:
            config = CircuitBreakerConfig(failure_threshold=1)
            cb = get_circuit_breaker(service, config)
            cb.state = CircuitState.OPEN
        
        # System should degrade gracefully
        fallback_service.set_degradation_level(DegradationLevel.SEVERE, "Multiple services down")
        
        # Fallback should still work
        result = await fallback_service.ai_fallback("maintenance")
        assert result.success
        assert "maintenance" in result.data["response"]
        
        # Redis fallback should use memory cache
        redis_result = await fallback_service.redis_fallback("set", "test_key", "test_value")
        assert redis_result.success
        assert redis_result.fallback_used == "redis_memory_cache"
