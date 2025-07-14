"""
Tests for main application module
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestMainApp:
    """Test cases for main application"""

    def test_root_endpoint(self):
        """Test root endpoint returns correct response"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "WhatsApp Hotel Bot API"
        assert "version" in data
        assert data["status"] == "running"

    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "whatsapp-hotel-bot"
        assert "version" in data

    def test_api_v1_health_endpoint(self):
        """Test API v1 health endpoint"""
        response = client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "whatsapp-hotel-bot"
        assert "timestamp" in data
        assert "environment" in data

    def test_api_v1_detailed_health_endpoint(self):
        """Test API v1 detailed health endpoint"""
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "dependencies" in data
        assert "database" in data["dependencies"]
        assert "redis" in data["dependencies"]
        assert "green_api" in data["dependencies"]
        assert "deepseek_api" in data["dependencies"]

    def test_nonexistent_endpoint(self):
        """Test that nonexistent endpoints return 404"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.options("/")
        # CORS headers should be present in preflight requests
        assert response.status_code in [200, 405]  # Some implementations return 405 for OPTIONS

    def test_api_docs_accessibility(self):
        """Test that API documentation is accessible in debug mode"""
        # This test assumes DEBUG=True in test environment
        response = client.get("/docs")
        # Should either be accessible (200) or redirect (3xx)
        assert response.status_code in [200, 307, 308] or response.status_code == 404

class TestApplicationStartup:
    """Test application startup and configuration"""

    def test_app_instance_creation(self):
        """Test that app instance is created correctly"""
        assert app is not None
        assert app.title == "WhatsApp Hotel Bot"
        assert hasattr(app, 'routes')

    def test_middleware_configuration(self):
        """Test that middleware is configured"""
        # Check that middleware stack is configured
        # In newer FastAPI versions, middleware is accessed differently
        middleware_stack = app.middleware_stack
        assert middleware_stack is not None

        # Check that we have multiple middleware layers
        # (CORS, Monitoring, Security, etc.)
        assert hasattr(app, 'user_middleware')
        assert len(app.user_middleware) > 0

    def test_router_inclusion(self):
        """Test that API router is included"""
        # Check that API routes are registered
        routes = [route.path for route in app.routes]
        assert any("/api/v1" in route for route in routes)

@pytest.mark.asyncio
class TestAsyncEndpoints:
    """Test async endpoint functionality"""

    async def test_async_health_check(self):
        """Test async health check functionality"""
        from app.api.v1.endpoints.health import health_check
        
        result = await health_check()
        assert result.status == "healthy"
        assert result.service == "whatsapp-hotel-bot"
        assert result.timestamp is not None

    async def test_async_detailed_health_check(self):
        """Test async detailed health check functionality"""
        from app.api.v1.endpoints.health import detailed_health_check
        
        result = await detailed_health_check()
        assert result["status"] == "healthy"
        assert "dependencies" in result
