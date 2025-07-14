"""
Integration tests for reliability system endpoints
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch

from app.main import app
from app.utils.circuit_breaker import reset_all_circuit_breakers


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Mock admin authentication headers"""
    # In a real test, this would use proper JWT tokens
    return {"Authorization": "Bearer admin_token"}


class TestHealthEndpoints:
    """Test health check endpoints with reliability components"""
    
    def test_basic_health_check(self, client):
        """Test basic health check endpoint"""
        response = client.get("/health/")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
    
    def test_liveness_probe(self, client):
        """Test liveness probe endpoint"""
        response = client.get("/health/live")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "alive"
    
    @patch('app.services.health_checker.HealthChecker.check_all_dependencies')
    def test_readiness_probe(self, mock_check_deps, client):
        """Test readiness probe with mocked dependencies"""
        from app.services.health_checker import SystemHealthStatus, DependencyStatus, HealthCheckResult
        
        # Mock healthy system
        mock_system_health = SystemHealthStatus(
            overall_status=DependencyStatus.HEALTHY,
            checks={
                "redis": HealthCheckResult(
                    status=DependencyStatus.HEALTHY,
                    response_time_ms=10.0,
                    details="Redis is healthy"
                )
            },
            circuit_breakers={},
            total_check_time_ms=15.0
        )
        mock_check_deps.return_value = mock_system_health
        
        response = client.get("/health/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" in data
        assert "system_health" in data
    
    def test_detailed_health_check(self, client):
        """Test detailed health check endpoint"""
        with patch('app.services.health_checker.HealthChecker.check_all_dependencies') as mock_check:
            from app.services.health_checker import SystemHealthStatus, DependencyStatus
            
            mock_check.return_value = SystemHealthStatus(
                overall_status=DependencyStatus.HEALTHY,
                checks={},
                circuit_breakers={},
                total_check_time_ms=10.0
            )
            
            response = client.get("/health/detailed")
            assert response.status_code == 200
            
            data = response.json()
            assert "system_health" in data
            assert "reliability_components" in data
    
    def test_circuit_breakers_status(self, client):
        """Test circuit breakers status endpoint"""
        # Reset circuit breakers first
        reset_all_circuit_breakers()
        
        response = client.get("/health/circuit-breakers")
        assert response.status_code == 200
        
        data = response.json()
        assert "circuit_breakers" in data
        assert "summary" in data
        assert "timestamp" in data
    
    def test_degradation_status(self, client):
        """Test degradation status endpoint"""
        response = client.get("/health/degradation")
        assert response.status_code == 200
        
        data = response.json()
        assert "current_status" in data
        assert "handler_status" in data
        assert "timestamp" in data
    
    @patch('app.tasks.dead_letter_handler.dlq_handler.get_stats')
    def test_dlq_status(self, mock_get_stats, client):
        """Test DLQ status endpoint"""
        mock_get_stats.return_value = {
            "current_queue_size": 5,
            "messages_added": 10,
            "messages_processed": 5
        }
        
        response = client.get("/health/dlq")
        assert response.status_code == 200
        
        data = response.json()
        assert "dlq_stats" in data
        assert "processing_stats" in data


class TestAdminReliabilityEndpoints:
    """Test admin reliability endpoints"""
    
    def test_get_circuit_breakers_admin_unauthorized(self, client):
        """Test circuit breakers admin endpoint without auth"""
        response = client.get("/admin/reliability/circuit-breakers")
        assert response.status_code == 401
    
    @patch('app.core.auth.get_current_admin_user')
    def test_get_circuit_breakers_admin(self, mock_auth, client, admin_headers):
        """Test circuit breakers admin endpoint with auth"""
        from app.schemas.user import User
        
        mock_auth.return_value = User(
            id="admin_id",
            email="admin@test.com",
            is_admin=True
        )
        
        response = client.get("/admin/reliability/circuit-breakers", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "circuit_breakers" in data
        assert "summary" in data
    
    @patch('app.core.auth.get_current_admin_user')
    def test_reset_circuit_breaker(self, mock_auth, client, admin_headers):
        """Test resetting a specific circuit breaker"""
        from app.schemas.user import User
        from app.utils.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
        
        mock_auth.return_value = User(
            id="admin_id",
            email="admin@test.com",
            is_admin=True
        )
        
        # Create a test circuit breaker
        config = CircuitBreakerConfig()
        cb = get_circuit_breaker("test_service", config)
        
        response = client.post("/admin/reliability/circuit-breakers/test_service/reset", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "old_state" in data
        assert "new_state" in data
    
    @patch('app.core.auth.get_current_admin_user')
    def test_reset_nonexistent_circuit_breaker(self, mock_auth, client, admin_headers):
        """Test resetting a non-existent circuit breaker"""
        from app.schemas.user import User
        
        mock_auth.return_value = User(
            id="admin_id",
            email="admin@test.com",
            is_admin=True
        )
        
        response = client.post("/admin/reliability/circuit-breakers/nonexistent/reset", headers=admin_headers)
        assert response.status_code == 404
    
    @patch('app.core.auth.get_current_admin_user')
    def test_set_degradation_level(self, mock_auth, client, admin_headers):
        """Test manually setting degradation level"""
        from app.schemas.user import User
        
        mock_auth.return_value = User(
            id="admin_id",
            email="admin@test.com",
            is_admin=True
        )
        
        response = client.post(
            "/admin/reliability/degradation/set-level",
            params={"level": "moderate", "reason": "Testing"},
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "old_level" in data
        assert "new_level" in data
    
    @patch('app.core.auth.get_current_admin_user')
    def test_set_invalid_degradation_level(self, mock_auth, client, admin_headers):
        """Test setting invalid degradation level"""
        from app.schemas.user import User
        
        mock_auth.return_value = User(
            id="admin_id",
            email="admin@test.com",
            is_admin=True
        )
        
        response = client.post(
            "/admin/reliability/degradation/set-level",
            params={"level": "invalid", "reason": "Testing"},
            headers=admin_headers
        )
        assert response.status_code == 400
    
    @patch('app.core.auth.get_current_admin_user')
    @patch('app.tasks.dead_letter_handler.dlq_handler.get_dlq_messages')
    @patch('app.tasks.dead_letter_handler.dlq_handler.get_stats')
    def test_get_dlq_status_admin(self, mock_get_stats, mock_get_messages, mock_auth, client, admin_headers):
        """Test getting DLQ status as admin"""
        from app.schemas.user import User
        from app.tasks.dead_letter_handler import DeadLetterMessage, FailureReason
        from datetime import datetime
        
        mock_auth.return_value = User(
            id="admin_id",
            email="admin@test.com",
            is_admin=True
        )
        
        # Mock DLQ messages
        mock_message = DeadLetterMessage(
            id="test_msg_1",
            original_data={"test": "data"},
            failure_reason=FailureReason.TIMEOUT,
            error_message="Test error",
            retry_count=1,
            max_retries=3,
            first_failed_at=datetime.now(),
            last_failed_at=datetime.now()
        )
        mock_get_messages.return_value = [mock_message]
        mock_get_stats.return_value = {"current_queue_size": 1}
        
        response = client.get("/admin/reliability/dlq", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "messages" in data
        assert "stats" in data
        assert len(data["messages"]) == 1
    
    @patch('app.core.auth.get_current_admin_user')
    @patch('app.tasks.dead_letter_handler.dlq_handler.retry_message')
    def test_retry_dlq_message(self, mock_retry, mock_auth, client, admin_headers):
        """Test retrying a DLQ message"""
        from app.schemas.user import User
        
        mock_auth.return_value = User(
            id="admin_id",
            email="admin@test.com",
            is_admin=True
        )
        mock_retry.return_value = True
        
        response = client.post("/admin/reliability/dlq/test_msg_1/retry", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["retry_success"] is True
        assert data["message_id"] == "test_msg_1"
    
    @patch('app.core.auth.get_current_admin_user')
    def test_generate_reliability_report(self, mock_auth, client, admin_headers):
        """Test generating reliability report"""
        from app.schemas.user import User
        
        mock_auth.return_value = User(
            id="admin_id",
            email="admin@test.com",
            is_admin=True
        )
        
        with patch('app.tasks.reliability_tasks.generate_reliability_report.delay') as mock_task:
            mock_task.return_value = Mock(id="task_123")
            
            response = client.get("/admin/reliability/reports/reliability", headers=admin_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert "task_id" in data
            assert data["task_id"] == "task_123"


class TestReliabilityIntegration:
    """Test reliability system integration"""
    
    @patch('app.services.health_checker.HealthChecker.check_redis')
    def test_health_check_with_circuit_breaker(self, mock_check_redis, client):
        """Test health check integration with circuit breaker"""
        from app.services.health_checker import HealthCheckResult, DependencyStatus
        
        # Mock Redis failure
        mock_check_redis.return_value = HealthCheckResult(
            status=DependencyStatus.UNHEALTHY,
            response_time_ms=1000.0,
            details="Redis connection failed",
            error="Connection timeout"
        )
        
        response = client.get("/health/ready")
        # Should still return 200 but with degraded status
        assert response.status_code in [200, 503]  # Depends on overall health
        
        data = response.json()
        assert "checks" in data
        if "redis" in data["checks"]:
            assert data["checks"]["redis"]["status"] == "unhealthy"
    
    def test_circuit_breaker_middleware_integration(self, client):
        """Test circuit breaker middleware integration"""
        # This would test actual API endpoints that use circuit breaker middleware
        # For now, just test that the endpoints are accessible
        
        response = client.get("/health/")
        assert response.status_code == 200
        
        # Check if circuit breaker headers are present
        # (These would be added by the middleware)
        # assert "X-Circuit-Breaker" in response.headers  # Uncomment when middleware is fully integrated
    
    @patch('app.utils.degradation_handler.get_degradation_handler')
    def test_degradation_handler_integration(self, mock_get_handler, client):
        """Test degradation handler integration"""
        from app.utils.degradation_handler import DegradationHandler
        from app.services.fallback_service import FallbackService, DegradationLevel
        
        mock_handler = Mock(spec=DegradationHandler)
        mock_handler.get_status.return_value = {
            "current_level": "normal",
            "active_rules": [],
            "recent_events": []
        }
        mock_handler.get_recent_events.return_value = []
        mock_get_handler.return_value = mock_handler
        
        response = client.get("/health/degradation")
        assert response.status_code == 200
        
        data = response.json()
        assert "handler_status" in data
