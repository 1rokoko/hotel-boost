"""
Integration tests for API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

class TestAPIEndpoints:
    """Integration tests for all API endpoints"""

    def test_root_endpoint_integration(self, client: TestClient):
        """Test root endpoint with full integration"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "version" in data
        assert "status" in data
        
        # Verify response values
        assert data["message"] == "WhatsApp Hotel Bot API"
        assert data["status"] == "running"
        assert isinstance(data["version"], str)

    def test_health_endpoint_integration(self, client: TestClient):
        """Test health endpoint with full integration"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        required_fields = ["status", "service", "version"]
        for field in required_fields:
            assert field in data
        
        # Verify response values
        assert data["status"] == "healthy"
        assert data["service"] == "whatsapp-hotel-bot"

    def test_api_v1_health_endpoint_integration(self, client: TestClient):
        """Test API v1 health endpoint with full integration"""
        response = client.get("/api/v1/health/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        required_fields = ["status", "service", "version", "timestamp", "environment"]
        for field in required_fields:
            assert field in data
        
        # Verify response values
        assert data["status"] == "healthy"
        assert data["service"] == "whatsapp-hotel-bot"
        assert data["environment"] in ["development", "test", "production"]
        
        # Verify timestamp format (ISO 8601)
        import datetime
        timestamp = datetime.datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
        assert isinstance(timestamp, datetime.datetime)

    def test_api_v1_detailed_health_endpoint_integration(self, client: TestClient):
        """Test API v1 detailed health endpoint with full integration"""
        response = client.get("/api/v1/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        required_fields = ["status", "service", "version", "timestamp", "environment", "dependencies"]
        for field in required_fields:
            assert field in data
        
        # Verify dependencies structure
        dependencies = data["dependencies"]
        required_deps = ["database", "redis", "green_api", "deepseek_api"]
        for dep in required_deps:
            assert dep in dependencies

    def test_cors_headers_integration(self, client: TestClient):
        """Test CORS headers are properly set"""
        # Test preflight request
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # CORS should be handled by middleware
        assert response.status_code in [200, 405]  # Some implementations return 405 for OPTIONS

    def test_nonexistent_endpoint_integration(self, client: TestClient):
        """Test that nonexistent endpoints return proper 404"""
        response = client.get("/nonexistent/endpoint")
        assert response.status_code == 404

    def test_api_documentation_accessibility(self, client: TestClient):
        """Test that API documentation is accessible"""
        # Test Swagger UI
        response = client.get("/docs")
        # Should either be accessible or not available (depending on DEBUG setting)
        assert response.status_code in [200, 404]
        
        # Test ReDoc
        response = client.get("/redoc")
        assert response.status_code in [200, 404]

    def test_api_endpoint_performance(self, client: TestClient, performance_tracker):
        """Test API endpoint performance"""
        endpoints = [
            "/",
            "/health",
            "/api/v1/health/",
            "/api/v1/health/detailed"
        ]
        
        for endpoint in endpoints:
            performance_tracker.start_timer(f"GET {endpoint}")
            response = client.get(endpoint)
            performance_tracker.end_timer(f"GET {endpoint}")
            
            # Verify response is successful
            assert response.status_code == 200
            
            # Verify response time is reasonable (under 100ms for health checks)
            performance_tracker.assert_duration_under(f"GET {endpoint}", 100)

    def test_concurrent_requests(self, client: TestClient):
        """Test handling of concurrent requests"""
        import concurrent.futures
        import threading
        
        def make_request():
            response = client.get("/health")
            return response.status_code
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 10

    def test_error_handling_integration(self, client: TestClient):
        """Test error handling across the application"""
        # Test malformed JSON in POST request
        response = client.post(
            "/api/v1/health/",  # This endpoint doesn't accept POST
            json={"invalid": "data"},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return method not allowed
        assert response.status_code == 405

    def test_request_headers_handling(self, client: TestClient):
        """Test proper handling of various request headers"""
        headers = {
            "User-Agent": "Test Client 1.0",
            "Accept": "application/json",
            "X-Correlation-ID": "test-correlation-123",
            "X-Forwarded-For": "192.168.1.1"
        }
        
        response = client.get("/health", headers=headers)
        assert response.status_code == 200
        
        # Verify response headers
        assert "content-type" in response.headers
        assert response.headers["content-type"] == "application/json"

    def test_large_request_handling(self, client: TestClient):
        """Test handling of large requests"""
        # Create a large JSON payload
        large_data = {"data": "x" * 10000}  # 10KB of data
        
        response = client.post(
            "/api/v1/health/",  # This will return 405, but tests large payload handling
            json=large_data
        )
        
        # Should handle large payload gracefully
        assert response.status_code in [405, 413, 422]  # Method not allowed, payload too large, or unprocessable

class TestAPIErrorHandling:
    """Test error handling scenarios"""

    def test_global_exception_handler(self, client: TestClient):
        """Test global exception handler"""
        # This would require an endpoint that raises an exception
        # For now, test that the handler is configured
        response = client.get("/nonexistent")
        assert response.status_code == 404

    @patch('app.main.app')
    def test_startup_error_handling(self, mock_app, client: TestClient):
        """Test application startup error handling"""
        # This test would verify that startup errors are handled gracefully
        # Implementation depends on specific startup procedures
        pass

class TestAPIVersioning:
    """Test API versioning"""

    def test_api_v1_prefix(self, client: TestClient):
        """Test that API v1 endpoints are properly prefixed"""
        response = client.get("/api/v1/health/")
        assert response.status_code == 200

    def test_api_version_in_response(self, client: TestClient):
        """Test that API version is included in responses"""
        response = client.get("/api/v1/health/")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

class TestAPIContentTypes:
    """Test content type handling"""

    def test_json_content_type(self, client: TestClient):
        """Test JSON content type handling"""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"

    def test_accept_header_handling(self, client: TestClient):
        """Test Accept header handling"""
        response = client.get(
            "/health",
            headers={"Accept": "application/json"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
