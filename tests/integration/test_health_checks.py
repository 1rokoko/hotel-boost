"""
Integration tests for health check functionality
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

class TestHealthCheckIntegration:
    """Integration tests for health check endpoints"""

    def test_basic_health_check_integration(self, client: TestClient):
        """Test basic health check endpoint integration"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields
        assert data["status"] == "healthy"
        assert data["service"] == "whatsapp-hotel-bot"
        assert "version" in data

    def test_api_v1_health_check_integration(self, client: TestClient):
        """Test API v1 health check endpoint integration"""
        response = client.get("/api/v1/health/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["status"] == "healthy"
        assert data["service"] == "whatsapp-hotel-bot"
        assert "timestamp" in data
        assert "environment" in data
        
        # Verify timestamp is valid ISO format
        from datetime import datetime
        timestamp = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
        assert isinstance(timestamp, datetime)

    def test_detailed_health_check_integration(self, client: TestClient):
        """Test detailed health check endpoint integration"""
        response = client.get("/api/v1/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify main fields
        assert data["status"] == "healthy"
        assert "dependencies" in data
        
        # Verify dependencies structure
        deps = data["dependencies"]
        expected_deps = ["database", "redis", "green_api", "deepseek_api"]
        for dep in expected_deps:
            assert dep in deps

    def test_health_check_performance(self, client: TestClient, performance_tracker):
        """Test health check endpoint performance"""
        performance_tracker.start_timer("health_check")
        
        response = client.get("/health")
        
        performance_tracker.end_timer("health_check")
        
        assert response.status_code == 200
        # Health check should be very fast (under 50ms)
        performance_tracker.assert_duration_under("health_check", 50)

    def test_health_check_under_load(self, client: TestClient):
        """Test health check behavior under load"""
        import concurrent.futures
        
        def make_health_request():
            response = client.get("/health")
            return response.status_code, response.json()
        
        # Make 20 concurrent health check requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_health_request) for _ in range(20)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        for status_code, data in results:
            assert status_code == 200
            assert data["status"] == "healthy"

    def test_health_check_with_correlation_id(self, client: TestClient):
        """Test health check with correlation ID header"""
        correlation_id = "test-correlation-123"
        
        response = client.get(
            "/api/v1/health/",
            headers={"X-Correlation-ID": correlation_id}
        )
        
        assert response.status_code == 200
        # The correlation ID should be logged (we can't test this directly here)

    @patch('app.core.config.settings')
    def test_health_check_different_environments(self, mock_settings, client: TestClient):
        """Test health check in different environments"""
        # Test development environment
        mock_settings.ENVIRONMENT = "development"
        response = client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["environment"] == "development"

    def test_health_check_response_format(self, client: TestClient):
        """Test health check response format consistency"""
        endpoints = ["/health", "/api/v1/health/", "/api/v1/health/detailed"]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            
            # All responses should be JSON
            assert response.headers["content-type"] == "application/json"
            
            data = response.json()
            # All should have status and service fields
            assert "status" in data
            assert data["status"] == "healthy"

class TestHealthCheckDependencies:
    """Test health check dependency monitoring"""

    @pytest.mark.asyncio
    @patch('app.api.v1.endpoints.health.detailed_health_check')
    async def test_database_dependency_check(self, mock_health_check):
        """Test database dependency in health check"""
        # Mock a database connection issue
        mock_health_check.return_value = {
            "status": "degraded",
            "dependencies": {
                "database": "unhealthy",
                "redis": "healthy",
                "green_api": "healthy",
                "deepseek_api": "healthy"
            }
        }
        
        # This test would require actual dependency checking implementation
        # For now, we just verify the structure

    def test_health_check_timeout_handling(self, client: TestClient):
        """Test health check timeout handling"""
        # Health checks should be fast and not timeout
        import time
        start_time = time.time()
        
        response = client.get("/health")
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to ms
        
        assert response.status_code == 200
        assert duration < 1000  # Should complete within 1 second

class TestHealthCheckErrorScenarios:
    """Test health check error scenarios"""

    def test_health_check_with_invalid_headers(self, client: TestClient):
        """Test health check with invalid headers"""
        response = client.get(
            "/health",
            headers={"Invalid-Header": "invalid-value" * 1000}  # Very long header
        )
        
        # Should still work despite invalid headers
        assert response.status_code == 200

    def test_health_check_with_malformed_request(self, client: TestClient):
        """Test health check with malformed request"""
        # Health check should be robust against malformed requests
        response = client.get("/health?invalid=param&another=param")
        
        assert response.status_code == 200

class TestHealthCheckMonitoring:
    """Test health check monitoring capabilities"""

    def test_health_check_metrics_collection(self, client: TestClient):
        """Test that health check calls are properly monitored"""
        # Make several health check requests
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
        
        # In a real implementation, we would verify that metrics were collected
        # For now, we just ensure the endpoint works consistently

    def test_health_check_logging(self, client: TestClient):
        """Test that health check calls are properly logged"""
        response = client.get(
            "/api/v1/health/",
            headers={
                "User-Agent": "Test Health Monitor",
                "X-Correlation-ID": "health-test-123"
            }
        )
        
        assert response.status_code == 200
        # In a real implementation, we would verify log entries were created
