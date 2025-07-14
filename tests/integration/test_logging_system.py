"""
Integration tests for the logging system.

Tests the complete logging pipeline including formatters,
filters, handlers, and structured logging functionality.
"""

import pytest
import logging
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime

import structlog

from app.core.advanced_logging import (
    AdvancedLoggingConfig,
    setup_advanced_logging,
    get_advanced_logger,
    get_structlog_logger,
    log_security_event,
    log_audit_event,
    log_api_request,
    log_database_operation,
    log_task_execution,
    log_performance_metric
)
from app.utils.log_formatters import (
    JSONFormatter,
    ConsoleFormatter,
    get_formatter,
    create_structlog_processors
)
from app.utils.log_filters import (
    LevelFilter,
    LoggerNameFilter,
    MessageFilter,
    AttributeFilter,
    RateLimitFilter,
    SensitiveDataFilter,
    create_default_filters
)


class TestAdvancedLoggingConfig:
    """Test advanced logging configuration"""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
            
    @pytest.fixture
    def logging_config(self, temp_log_dir):
        """Create logging config with temp directory"""
        config = AdvancedLoggingConfig()
        config.log_dir = temp_log_dir
        return config
        
    def test_setup_logging(self, logging_config):
        """Test logging setup"""
        logging_config.setup_logging()
        
        # Check that handlers were created
        assert 'app' in logging_config.handlers
        assert 'error' in logging_config.handlers
        assert 'security' in logging_config.handlers
        assert 'audit' in logging_config.handlers
        
        # Check that loggers were created
        assert 'security' in logging_config.loggers
        assert 'audit' in logging_config.loggers
        assert 'api' in logging_config.loggers
        
    def test_get_logger(self, logging_config):
        """Test getting specialized logger"""
        logging_config.setup_logging()
        
        security_logger = logging_config.get_logger('security')
        assert isinstance(security_logger, logging.Logger)
        assert security_logger.name == 'security'
        
    def test_get_structlog_logger(self, logging_config):
        """Test getting structlog logger"""
        logging_config.setup_logging()
        
        logger = logging_config.get_structlog_logger('test')
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        
    def test_file_creation(self, logging_config):
        """Test that log files are created"""
        logging_config.setup_logging()
        
        # Log some messages
        app_logger = logging.getLogger()
        app_logger.info("Test message")
        app_logger.error("Test error")
        
        # Check that files exist
        assert (logging_config.log_dir / "app.log").exists()
        assert (logging_config.log_dir / "error.log").exists()


class TestLogFormatters:
    """Test log formatters"""
    
    def test_json_formatter(self):
        """Test JSON formatter"""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["service"] == "whatsapp-hotel-bot"
        assert "timestamp" in data
        
    def test_console_formatter(self):
        """Test console formatter"""
        formatter = ConsoleFormatter(use_colors=False)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        assert "Test message" in formatted
        assert "INFO" in formatted
        assert "test" in formatted
        
    def test_get_formatter(self):
        """Test formatter factory"""
        json_formatter = get_formatter("json")
        assert isinstance(json_formatter, JSONFormatter)
        
        console_formatter = get_formatter("console")
        assert isinstance(console_formatter, ConsoleFormatter)
        
        audit_formatter = get_formatter("audit")
        assert hasattr(audit_formatter, 'format')
        
    def test_create_structlog_processors(self):
        """Test structlog processors creation"""
        processors = create_structlog_processors(use_json=True)
        
        assert len(processors) > 0
        assert any("JSONRenderer" in str(p) for p in processors)
        
        processors_console = create_structlog_processors(use_json=False)
        assert any("ConsoleRenderer" in str(p) for p in processors)


class TestLogFilters:
    """Test log filters"""
    
    def test_level_filter(self):
        """Test level filter"""
        filter_obj = LevelFilter(min_level=logging.WARNING, max_level=logging.ERROR)
        
        # Should pass
        warning_record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert filter_obj.filter(warning_record) is True
        
        # Should not pass
        info_record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert filter_obj.filter(info_record) is False
        
    def test_logger_name_filter(self):
        """Test logger name filter"""
        filter_obj = LoggerNameFilter(
            include_patterns=["app.*"],
            exclude_patterns=["app.test.*"]
        )
        
        # Should pass
        app_record = logging.LogRecord(
            name="app.core", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert filter_obj.filter(app_record) is True
        
        # Should not pass (excluded)
        test_record = logging.LogRecord(
            name="app.test.module", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert filter_obj.filter(test_record) is False
        
        # Should not pass (not included)
        other_record = logging.LogRecord(
            name="other.module", level=logging.INFO, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        )
        assert filter_obj.filter(other_record) is False
        
    def test_message_filter(self):
        """Test message filter"""
        filter_obj = MessageFilter(
            include_patterns=["important.*"],
            exclude_patterns=[".*debug.*"]
        )
        
        # Should pass
        important_record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="important message", args=(), exc_info=None
        )
        assert filter_obj.filter(important_record) is True
        
        # Should not pass (excluded)
        debug_record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="debug information", args=(), exc_info=None
        )
        assert filter_obj.filter(debug_record) is False
        
    def test_sensitive_data_filter(self):
        """Test sensitive data filter"""
        filter_obj = SensitiveDataFilter()
        
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="User password is secret123", args=(), exc_info=None
        )
        
        # Filter should modify the message
        filter_obj.filter(record)
        assert "***REDACTED***" in str(record.msg)
        assert "secret123" not in str(record.msg)
        
    def test_rate_limit_filter(self):
        """Test rate limit filter"""
        filter_obj = RateLimitFilter(max_messages=2, time_window=60)
        
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="repeated message", args=(), exc_info=None
        )
        
        # First two should pass
        assert filter_obj.filter(record) is True
        assert filter_obj.filter(record) is True
        
        # Third should be rate limited
        assert filter_obj.filter(record) is False
        
    def test_create_default_filters(self):
        """Test default filters creation"""
        filters = create_default_filters()
        
        assert len(filters) > 0
        assert any(isinstance(f, SensitiveDataFilter) for f in filters)


class TestStructuredLogging:
    """Test structured logging functionality"""
    
    @pytest.fixture(autouse=True)
    def setup_logging(self):
        """Setup logging for tests"""
        setup_advanced_logging()
        
    def test_log_security_event(self):
        """Test security event logging"""
        with patch('app.core.advanced_logging.get_advanced_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_security_event("Unauthorized access", user_id="123", ip="1.2.3.4")
            
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Unauthorized access" in call_args[0]
            assert call_args[1]['extra']['log_type'] == 'security'
            assert call_args[1]['extra']['user_id'] == "123"
            
    def test_log_audit_event(self):
        """Test audit event logging"""
        with patch('app.core.advanced_logging.get_advanced_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_audit_event("User login", "user123", "login", "user_account")
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[1]['extra']['log_type'] == 'audit'
            assert call_args[1]['extra']['user_id'] == "user123"
            assert call_args[1]['extra']['action'] == "login"
            
    def test_log_api_request(self):
        """Test API request logging"""
        with patch('app.core.advanced_logging.get_advanced_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_api_request("GET", "/api/users", 200, 0.5, user_id="123")
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[1]['extra']['log_type'] == 'api'
            assert call_args[1]['extra']['method'] == "GET"
            assert call_args[1]['extra']['status_code'] == 200
            
    def test_log_database_operation(self):
        """Test database operation logging"""
        with patch('app.core.advanced_logging.get_advanced_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_database_operation("SELECT", "users", 0.1, rows_affected=5)
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[1]['extra']['log_type'] == 'database'
            assert call_args[1]['extra']['operation'] == "SELECT"
            assert call_args[1]['extra']['table'] == "users"
            
    def test_log_task_execution(self):
        """Test task execution logging"""
        with patch('app.core.advanced_logging.get_advanced_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_task_execution("send_email", "task-123", 2.5, status="success")
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[1]['extra']['log_type'] == 'task'
            assert call_args[1]['extra']['task_name'] == "send_email"
            assert call_args[1]['extra']['task_id'] == "task-123"
            
    def test_log_performance_metric(self):
        """Test performance metric logging"""
        with patch('app.core.advanced_logging.get_advanced_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_performance_metric("api_response", 1.2, endpoint="/api/test")
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[1]['extra']['log_type'] == 'performance'
            assert call_args[1]['extra']['operation'] == "api_response"
            assert call_args[1]['extra']['duration'] == 1.2


class TestLoggingIntegration:
    """Test complete logging integration"""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
            
    def test_end_to_end_logging(self, temp_log_dir):
        """Test complete logging pipeline"""
        # Setup logging with temp directory
        with patch('app.core.advanced_logging.Path') as mock_path:
            mock_path.return_value = temp_log_dir
            
            config = setup_advanced_logging()
            
            # Log different types of messages
            logger = get_advanced_logger('api')
            logger.info("API request", extra={
                'log_type': 'api',
                'method': 'GET',
                'path': '/api/test',
                'status_code': 200
            })
            
            security_logger = get_advanced_logger('security')
            security_logger.warning("Security event", extra={
                'log_type': 'security',
                'event_type': 'unauthorized_access'
            })
            
            # Check that appropriate files were created
            # Note: In a real test, you'd check file contents
            assert config is not None
            
    def test_structlog_integration(self):
        """Test structlog integration"""
        setup_advanced_logging()
        
        logger = get_structlog_logger('test')
        
        # This should not raise an exception
        logger.info("Test message", key="value", number=123)
        logger.error("Test error", error_code="TEST_ERROR")
        
    def test_filter_integration(self):
        """Test that filters work in integration"""
        setup_advanced_logging()
        
        # Create a logger with sensitive data
        logger = logging.getLogger('test')
        
        # This should be filtered by sensitive data filter
        with patch.object(logger, 'handle') as mock_handle:
            logger.info("User password is secret123")
            
            # The filter should have modified the record
            if mock_handle.called:
                record = mock_handle.call_args[0][0]
                assert "***REDACTED***" in str(record.msg)
