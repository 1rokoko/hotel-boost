"""
Unit tests for error handling system.

Tests custom exceptions, error formatters, exception handlers,
and error tracking functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions.custom_exceptions import (
    BaseCustomException,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ConflictError,
    RateLimitError,
    ExternalAPIError,
    GreenAPIError,
    DeepSeekAPIError,
    DatabaseError,
    TenantError,
    ConfigurationError,
    BusinessLogicError,
    TaskExecutionError,
    WebhookError,
    to_http_exception
)
from app.utils.error_formatter import ErrorFormatter, ErrorSummary
from app.core.exception_handlers import (
    base_custom_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    general_exception_handler
)
from app.utils.error_tracker import ErrorTracker, ErrorAnalyzer
from app.models.error_log import ErrorLog


class TestCustomExceptions:
    """Test custom exception classes"""
    
    def test_base_custom_exception(self):
        """Test BaseCustomException"""
        exc = BaseCustomException(
            message="Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
            status_code=400
        )
        
        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details == {"key": "value"}
        assert exc.status_code == 400
        assert str(exc) == "Test error"
        
    def test_validation_error(self):
        """Test ValidationError"""
        exc = ValidationError(
            message="Invalid field",
            field="email",
            value="invalid-email"
        )
        
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.status_code == 400
        assert exc.details["field"] == "email"
        assert exc.details["value"] == "invalid-email"
        
    def test_authentication_error(self):
        """Test AuthenticationError"""
        exc = AuthenticationError()
        
        assert exc.error_code == "AUTHENTICATION_ERROR"
        assert exc.status_code == 401
        assert exc.message == "Authentication failed"
        
    def test_authorization_error(self):
        """Test AuthorizationError"""
        exc = AuthorizationError(required_permission="admin")
        
        assert exc.error_code == "AUTHORIZATION_ERROR"
        assert exc.status_code == 403
        assert exc.details["required_permission"] == "admin"
        
    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError"""
        exc = ResourceNotFoundError("User", "123")
        
        assert exc.error_code == "RESOURCE_NOT_FOUND"
        assert exc.status_code == 404
        assert "User not found (ID: 123)" in exc.message
        assert exc.details["resource_type"] == "User"
        assert exc.details["resource_id"] == "123"
        
    def test_external_api_error(self):
        """Test ExternalAPIError"""
        exc = ExternalAPIError(
            api_name="TestAPI",
            message="API failed",
            api_error_code="API_ERROR",
            api_response={"error": "test"}
        )
        
        assert exc.error_code == "EXTERNAL_API_ERROR"
        assert exc.status_code == 502
        assert "TestAPI: API failed" in exc.message
        assert exc.details["api_name"] == "TestAPI"
        assert exc.details["api_error_code"] == "API_ERROR"
        
    def test_green_api_error(self):
        """Test GreenAPIError"""
        exc = GreenAPIError(message="Green API failed")
        
        assert exc.error_code == "EXTERNAL_API_ERROR"
        assert exc.details["api_name"] == "Green API"
        
    def test_deepseek_api_error(self):
        """Test DeepSeekAPIError"""
        exc = DeepSeekAPIError(message="DeepSeek failed")
        
        assert exc.error_code == "EXTERNAL_API_ERROR"
        assert exc.details["api_name"] == "DeepSeek API"
        
    def test_to_http_exception(self):
        """Test conversion to HTTPException"""
        exc = ValidationError("Test validation error")
        http_exc = to_http_exception(exc)
        
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == 400
        assert http_exc.detail["error"] == "VALIDATION_ERROR"
        assert http_exc.detail["message"] == "Test validation error"


class TestErrorFormatter:
    """Test error formatting utilities"""
    
    def test_format_error_response_custom_exception(self):
        """Test formatting custom exception"""
        exc = ValidationError("Test error", field="email")
        response = ErrorFormatter.format_error_response(exc, "req-123")
        
        assert response["error"] is True
        assert response["request_id"] == "req-123"
        assert response["error_code"] == "VALIDATION_ERROR"
        assert response["message"] == "Test error"
        assert response["status_code"] == 400
        assert "timestamp" in response
        assert "service" in response
        
    def test_format_error_response_standard_exception(self):
        """Test formatting standard exception"""
        exc = ValueError("Standard error")
        response = ErrorFormatter.format_error_response(exc)
        
        assert response["error"] is True
        assert response["error_code"] == "INTERNAL_ERROR"
        assert response["status_code"] == 500
        assert response["details"]["error_type"] == "ValueError"
        
    def test_format_validation_errors(self):
        """Test formatting validation errors"""
        errors = [
            {
                "loc": ["field1"],
                "msg": "Field is required",
                "type": "value_error.missing"
            },
            {
                "loc": ["field2", "subfield"],
                "msg": "Invalid value",
                "type": "value_error.invalid",
                "input": "bad_value"
            }
        ]
        
        response = ErrorFormatter.format_validation_errors(errors)
        
        assert response["error"] is True
        assert response["error_code"] == "VALIDATION_ERROR"
        assert response["status_code"] == 422
        assert len(response["details"]["validation_errors"]) == 2
        assert response["details"]["error_count"] == 2
        
    def test_format_log_error(self):
        """Test formatting error for logging"""
        exc = ValidationError("Test error")
        context = {"user_id": "123", "password": "secret"}
        
        log_data = ErrorFormatter.format_log_error(exc, context, sanitize_sensitive=True)
        
        assert log_data["error_type"] == "ValidationError"
        assert log_data["error_code"] == "VALIDATION_ERROR"
        assert log_data["context"]["user_id"] == "123"
        assert log_data["context"]["password"] == "***REDACTED***"
        
    def test_sanitize_context(self):
        """Test context sanitization"""
        context = {
            "user_id": "123",
            "password": "secret",
            "api_key": "key123",
            "normal_field": "value",
            "long_text": "a" * 150
        }
        
        sanitized = ErrorFormatter._sanitize_context(context)
        
        assert sanitized["user_id"] == "123"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["api_key"] == "***REDACTED***"
        assert sanitized["normal_field"] == "value"
        assert len(sanitized["long_text"]) == 103  # 100 + "..."
        
    def test_format_external_api_error(self):
        """Test formatting external API error"""
        error_data = ErrorFormatter.format_external_api_error(
            api_name="TestAPI",
            status_code=500,
            response_data={"error": "Internal error"},
            request_data={"token": "secret", "data": "test"}
        )
        
        assert error_data["error_type"] == "external_api_error"
        assert error_data["api_name"] == "TestAPI"
        assert error_data["status_code"] == 500
        assert error_data["api_response"]["error"] == "Internal error"
        assert error_data["api_request"]["token"] == "***REDACTED***"
        assert error_data["api_request"]["data"] == "test"


class TestErrorTracker:
    """Test error tracking functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
        
    @pytest.fixture
    def error_tracker(self, mock_db_session):
        """Create error tracker instance"""
        return ErrorTracker(mock_db_session)
        
    def test_track_error_new(self, error_tracker, mock_db_session):
        """Test tracking new error"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        error = ValidationError("Test error")
        
        result = error_tracker.track_error(
            error=error,
            request_id="req-123",
            user_id="user-456",
            hotel_id="hotel-789"
        )
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
    def test_track_error_existing(self, error_tracker, mock_db_session):
        """Test tracking existing error"""
        existing_error = Mock()
        existing_error.count = 1
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_error
        
        error = ValidationError("Test error")
        
        result = error_tracker.track_error(error=error)
        
        assert existing_error.count == 2
        mock_db_session.commit.assert_called_once()
        
    def test_get_error_statistics(self, error_tracker, mock_db_session):
        """Test getting error statistics"""
        mock_errors = [
            Mock(severity="error", error_type="ValidationError", path="/api/test"),
            Mock(severity="critical", error_type="DatabaseError", path="/api/db"),
            Mock(severity="error", error_type="ValidationError", path="/api/test")
        ]
        mock_db_session.query.return_value.filter.return_value.all.return_value = mock_errors
        
        stats = error_tracker.get_error_statistics()
        
        assert stats["total_errors"] == 3
        assert stats["unique_errors"] == 2  # Based on fingerprints
        assert "error_rate" in stats
        assert "severity_breakdown" in stats
        assert "top_error_types" in stats
        
    def test_resolve_error(self, error_tracker, mock_db_session):
        """Test resolving error"""
        mock_error = Mock()
        mock_error.is_resolved = False
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_error
        
        result = error_tracker.resolve_error("error-123", "admin", "Fixed issue")
        
        assert result is True
        assert mock_error.is_resolved is True
        assert mock_error.resolved_by == "admin"
        mock_db_session.commit.assert_called_once()


class TestErrorAnalyzer:
    """Test error analysis functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
        
    @pytest.fixture
    def error_analyzer(self, mock_db_session):
        """Create error analyzer instance"""
        return ErrorAnalyzer(mock_db_session)
        
    def test_detect_error_spikes(self, error_analyzer, mock_db_session):
        """Test error spike detection"""
        # Mock hourly counts: [5, 5, 5, 20, 5] - spike at hour 4
        mock_counts = [
            Mock(hour=datetime(2023, 1, 1, 1), count=5),
            Mock(hour=datetime(2023, 1, 1, 2), count=5),
            Mock(hour=datetime(2023, 1, 1, 3), count=5),
            Mock(hour=datetime(2023, 1, 1, 4), count=20),
            Mock(hour=datetime(2023, 1, 1, 5), count=5)
        ]
        mock_db_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_counts
        
        spikes = error_analyzer.detect_error_spikes(threshold_multiplier=2.0)
        
        assert len(spikes) == 1
        assert spikes[0]["error_count"] == 20
        assert spikes[0]["spike_ratio"] > 2.0


@pytest.mark.asyncio
class TestExceptionHandlers:
    """Test FastAPI exception handlers"""
    
    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"
        request.headers = {"X-Request-ID": "req-123"}
        return request
        
    async def test_base_custom_exception_handler(self, mock_request):
        """Test custom exception handler"""
        exc = ValidationError("Test error")
        
        response = await base_custom_exception_handler(mock_request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
    async def test_http_exception_handler(self, mock_request):
        """Test HTTP exception handler"""
        exc = HTTPException(status_code=404, detail="Not found")
        
        response = await http_exception_handler(mock_request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        
    async def test_sqlalchemy_exception_handler(self, mock_request):
        """Test SQLAlchemy exception handler"""
        exc = SQLAlchemyError("Database error")
        
        response = await sqlalchemy_exception_handler(mock_request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        
    async def test_general_exception_handler(self, mock_request):
        """Test general exception handler"""
        exc = ValueError("Unexpected error")
        
        response = await general_exception_handler(mock_request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
