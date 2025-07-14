"""
Unit tests for configuration module
"""

import pytest
import os
from unittest.mock import patch, MagicMock

from app.core.config import Settings, validate_settings

class TestSettings:
    """Test Settings configuration class"""

    def test_settings_default_values(self):
        """Test default configuration values"""
        settings = Settings()
        
        # Test default values
        assert settings.PROJECT_NAME == "WhatsApp Hotel Bot"
        assert settings.VERSION == "1.0.0"
        assert settings.API_V1_STR == "/api/v1"
        assert settings.DEBUG == True
        assert settings.ENVIRONMENT == "development"
        
        # Test default URLs
        assert settings.GREEN_API_URL == "https://api.green-api.com"
        assert settings.DEEPSEEK_API_URL == "https://api.deepseek.com"
        assert settings.REDIS_URL == "redis://localhost:6379"

    def test_settings_from_env_file(self):
        """Test loading settings from environment variables"""
        with patch.dict(os.environ, {
            'PROJECT_NAME': 'Test Bot',
            'VERSION': '2.0.0',
            'DEBUG': 'false',
            'ENVIRONMENT': 'production',
            'SECRET_KEY': 'test-secret-key',
            'DATABASE_URL': 'postgresql://test:test@localhost/test',
            'GREEN_API_INSTANCE_ID': 'test-instance',
            'GREEN_API_TOKEN': 'test-token',
            'DEEPSEEK_API_KEY': 'test-deepseek-key'
        }):
            settings = Settings()
            
            assert settings.PROJECT_NAME == "Test Bot"
            assert settings.VERSION == "2.0.0"
            assert settings.DEBUG == False
            assert settings.ENVIRONMENT == "production"
            assert settings.SECRET_KEY == "test-secret-key"
            assert settings.DATABASE_URL == "postgresql://test:test@localhost/test"
            assert settings.GREEN_API_INSTANCE_ID == "test-instance"
            assert settings.GREEN_API_TOKEN == "test-token"
            assert settings.DEEPSEEK_API_KEY == "test-deepseek-key"

    def test_settings_type_conversion(self):
        """Test type conversion for environment variables"""
        with patch.dict(os.environ, {
            'DEBUG': 'true',
            'ACCESS_TOKEN_EXPIRE_MINUTES': '60',
            'NOTIFICATION_EMAIL_SMTP_PORT': '465',
            'PROMETHEUS_ENABLED': 'true',
            'GRAFANA_ENABLED': 'false'
        }):
            settings = Settings()
            
            assert settings.DEBUG == True
            assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
            assert settings.NOTIFICATION_EMAIL_SMTP_PORT == 465
            assert settings.PROMETHEUS_ENABLED == True
            assert settings.GRAFANA_ENABLED == False

    def test_settings_list_parsing(self):
        """Test parsing of list values from environment"""
        with patch.dict(os.environ, {
            'ALLOWED_HOSTS': '["localhost", "127.0.0.1", "example.com"]'
        }):
            settings = Settings()
            
            assert isinstance(settings.ALLOWED_HOSTS, list)
            assert "localhost" in settings.ALLOWED_HOSTS
            assert "127.0.0.1" in settings.ALLOWED_HOSTS
            assert "example.com" in settings.ALLOWED_HOSTS

    def test_settings_optional_fields(self):
        """Test optional configuration fields"""
        settings = Settings()
        
        # These should be None by default
        assert settings.GREEN_API_INSTANCE_ID is None
        assert settings.GREEN_API_TOKEN is None
        assert settings.DEEPSEEK_API_KEY is None
        assert settings.NOTIFICATION_EMAIL_SMTP_HOST is None
        assert settings.NOTIFICATION_EMAIL_USERNAME is None
        assert settings.NOTIFICATION_EMAIL_PASSWORD is None

    def test_settings_case_sensitivity(self):
        """Test that settings are case sensitive"""
        with patch.dict(os.environ, {
            'project_name': 'lowercase',  # Should not be picked up
            'PROJECT_NAME': 'UPPERCASE'   # Should be picked up
        }):
            settings = Settings()
            assert settings.PROJECT_NAME == "UPPERCASE"

class TestSettingsValidation:
    """Test settings validation functionality"""

    def test_validate_settings_development(self):
        """Test validation in development environment"""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'development',
            'SECRET_KEY': 'dev-secret-key'
        }):
            # Should not raise any errors in development
            validate_settings()

    def test_validate_settings_production_success(self):
        """Test successful validation in production"""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': 'secure-production-key',
            'GREEN_API_INSTANCE_ID': 'prod-instance',
            'GREEN_API_TOKEN': 'prod-token',
            'DEEPSEEK_API_KEY': 'prod-deepseek-key'
        }):
            # Should not raise any errors
            validate_settings()

    def test_validate_settings_production_missing_secret(self):
        """Test validation failure with missing secret key in production"""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': 'your-super-secret-key-here-change-in-production',  # Default value
            'GREEN_API_INSTANCE_ID': 'prod-instance',
            'GREEN_API_TOKEN': 'prod-token',
            'DEEPSEEK_API_KEY': 'prod-deepseek-key'
        }):
            with pytest.raises(ValueError, match="SECRET_KEY must be set in production"):
                validate_settings()

    def test_validate_settings_production_missing_api_keys(self):
        """Test validation failure with missing API keys in production"""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': 'secure-production-key'
            # Missing GREEN_API_INSTANCE_ID, GREEN_API_TOKEN, DEEPSEEK_API_KEY
        }):
            with pytest.raises(ValueError, match="GREEN_API_INSTANCE_ID is required"):
                validate_settings()

    def test_validate_settings_multiple_errors(self):
        """Test validation with multiple configuration errors"""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production'
            # Missing all required production settings
        }):
            with pytest.raises(ValueError) as exc_info:
                validate_settings()
            
            error_message = str(exc_info.value)
            assert "SECRET_KEY must be set in production" in error_message
            assert "GREEN_API_INSTANCE_ID is required" in error_message
            assert "GREEN_API_TOKEN is required" in error_message
            assert "DEEPSEEK_API_KEY is required" in error_message

class TestSettingsIntegration:
    """Test settings integration with the application"""

    def test_settings_import(self):
        """Test that settings can be imported correctly"""
        from app.core.config import settings
        
        assert hasattr(settings, 'PROJECT_NAME')
        assert hasattr(settings, 'VERSION')
        assert hasattr(settings, 'DATABASE_URL')

    def test_settings_singleton_behavior(self):
        """Test that settings behave like a singleton"""
        from app.core.config import settings as settings1
        from app.core.config import settings as settings2
        
        # Should be the same instance
        assert settings1 is settings2

    @patch('app.core.config.settings')
    def test_settings_mocking(self, mock_settings):
        """Test that settings can be mocked for testing"""
        mock_settings.DEBUG = False
        mock_settings.ENVIRONMENT = "test"
        
        assert mock_settings.DEBUG == False
        assert mock_settings.ENVIRONMENT == "test"

class TestSettingsEdgeCases:
    """Test edge cases and error conditions"""

    def test_settings_with_empty_env_vars(self):
        """Test settings with empty environment variables"""
        with patch.dict(os.environ, {
            'PROJECT_NAME': '',
            'VERSION': '',
            'SECRET_KEY': ''
        }):
            settings = Settings()
            
            # Empty strings should be used as-is
            assert settings.PROJECT_NAME == ""
            assert settings.VERSION == ""
            assert settings.SECRET_KEY == ""

    def test_settings_with_invalid_boolean(self):
        """Test settings with invalid boolean values"""
        with patch.dict(os.environ, {
            'DEBUG': 'invalid-boolean'
        }):
            # Should handle invalid boolean gracefully
            settings = Settings()
            # Pydantic should convert this to False or raise validation error

    def test_settings_with_invalid_integer(self):
        """Test settings with invalid integer values"""
        with patch.dict(os.environ, {
            'ACCESS_TOKEN_EXPIRE_MINUTES': 'not-a-number'
        }):
            # Should raise validation error
            with pytest.raises(Exception):  # Pydantic validation error
                Settings()

    def test_settings_with_very_long_values(self):
        """Test settings with very long string values"""
        long_value = "x" * 10000
        with patch.dict(os.environ, {
            'PROJECT_NAME': long_value
        }):
            settings = Settings()
            assert settings.PROJECT_NAME == long_value

class TestSettingsPerformance:
    """Test settings performance characteristics"""

    def test_settings_creation_performance(self, performance_tracker):
        """Test that settings creation is fast"""
        performance_tracker.start_timer("settings_creation")
        
        for _ in range(100):
            Settings()
        
        performance_tracker.end_timer("settings_creation")
        
        # Settings creation should be fast (under 100ms for 100 instances)
        performance_tracker.assert_duration_under("settings_creation", 100)

    def test_settings_attribute_access_performance(self, performance_tracker):
        """Test that settings attribute access is fast"""
        settings = Settings()
        
        performance_tracker.start_timer("attribute_access")
        
        for _ in range(1000):
            _ = settings.PROJECT_NAME
            _ = settings.VERSION
            _ = settings.DATABASE_URL
        
        performance_tracker.end_timer("attribute_access")
        
        # Attribute access should be very fast (under 10ms for 1000 accesses)
        performance_tracker.assert_duration_under("attribute_access", 10)
