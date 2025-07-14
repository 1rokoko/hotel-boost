"""
Test configuration settings for different environments
Provides configuration for unit, integration, performance, and security tests
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database configuration for tests"""
    url: str
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600


@dataclass
class RedisConfig:
    """Redis configuration for tests"""
    url: str
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


@dataclass
class APIConfig:
    """External API configuration for tests"""
    green_api_base_url: str = "https://api.green-api.com"
    green_api_timeout: int = 30
    deepseek_api_base_url: str = "https://api.deepseek.com"
    deepseek_api_timeout: int = 30
    use_mocks: bool = True


@dataclass
class PerformanceConfig:
    """Performance test configuration"""
    max_response_time: float = 2.0
    max_memory_usage_mb: float = 512.0
    concurrent_users: int = 10
    test_duration_seconds: int = 60
    ramp_up_time_seconds: int = 10


@dataclass
class SecurityConfig:
    """Security test configuration"""
    test_jwt_secret: str = "test-jwt-secret-key-for-testing-only"
    test_encryption_key: str = "test-encryption-key-32-chars-long"
    password_min_length: int = 8
    session_timeout_minutes: int = 30


class TestSettings:
    """Centralized test settings management"""

    def __init__(self, environment: str = "test"):
        self.environment = environment
        self._load_environment_variables()

        # Core configurations
        self.database = self._get_database_config()
        self.redis = self._get_redis_config()
        self.api = self._get_api_config()
        self.performance = self._get_performance_config()
        self.security = self._get_security_config()

        # Test-specific settings
        self.test_data_cleanup = True
        self.parallel_test_execution = True
        self.test_timeout_seconds = 300
        self.coverage_threshold = 85

        # Logging configuration
        self.log_level = "INFO"
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.enable_sql_logging = False

    def _load_environment_variables(self):
        """Load environment variables for testing"""
        test_env_vars = {
            "ENVIRONMENT": self.environment,
            "SECRET_KEY": "test-secret-key-for-testing-only",
            "ALGORITHM": "HS256",
            "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
            "REFRESH_TOKEN_EXPIRE_DAYS": "7"
        }

        for key, default_value in test_env_vars.items():
            if key not in os.environ:
                os.environ[key] = default_value

    def _get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        return DatabaseConfig(
            url=os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:password@localhost:5432/hotel_bot_test"
            ),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600"))
        )

    def _get_redis_config(self) -> RedisConfig:
        """Get Redis configuration"""
        return RedisConfig(
            url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
            socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
            socket_connect_timeout=int(os.getenv("REDIS_CONNECT_TIMEOUT", "5"))
        )

    def _get_api_config(self) -> APIConfig:
        """Get API configuration"""
        return APIConfig(
            green_api_base_url=os.getenv("GREEN_API_BASE_URL", "https://api.green-api.com"),
            green_api_timeout=int(os.getenv("GREEN_API_TIMEOUT", "30")),
            deepseek_api_base_url=os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com"),
            deepseek_api_timeout=int(os.getenv("DEEPSEEK_API_TIMEOUT", "30")),
            use_mocks=os.getenv("USE_API_MOCKS", "true").lower() == "true"
        )

    def _get_performance_config(self) -> PerformanceConfig:
        """Get performance test configuration"""
        return PerformanceConfig(
            max_response_time=float(os.getenv("PERF_MAX_RESPONSE_TIME", "2.0")),
            max_memory_usage_mb=float(os.getenv("PERF_MAX_MEMORY_MB", "512.0")),
            concurrent_users=int(os.getenv("PERF_CONCURRENT_USERS", "10")),
            test_duration_seconds=int(os.getenv("PERF_TEST_DURATION", "60")),
            ramp_up_time_seconds=int(os.getenv("PERF_RAMP_UP_TIME", "10"))
        )

    def _get_security_config(self) -> SecurityConfig:
        """Get security test configuration"""
        return SecurityConfig(
            test_jwt_secret=os.getenv("TEST_JWT_SECRET", "test-jwt-secret-key-for-testing-only"),
            test_encryption_key=os.getenv("TEST_ENCRYPTION_KEY", "test-encryption-key-32-chars-long"),
            password_min_length=int(os.getenv("PASSWORD_MIN_LENGTH", "8")),
            session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
        )

    def get_test_database_url(self, test_name: Optional[str] = None) -> str:
        """Get test-specific database URL"""
        base_url = self.database.url
        if test_name:
            # Create test-specific database name
            if "hotel_bot_test" in base_url:
                return base_url.replace("hotel_bot_test", f"hotel_bot_test_{test_name}")
        return base_url

    def get_mock_config(self) -> Dict[str, Any]:
        """Get mock service configuration"""
        return {
            "green_api": {
                "enabled": self.api.use_mocks,
                "simulate_delays": True,
                "failure_rate": 0.0,
                "rate_limit_enabled": False
            },
            "deepseek": {
                "enabled": self.api.use_mocks,
                "simulate_delays": True,
                "failure_rate": 0.0,
                "rate_limit_enabled": False,
                "daily_token_limit": 100000
            }
        }

    def get_test_markers(self) -> Dict[str, str]:
        """Get pytest markers configuration"""
        return {
            "unit": "Unit tests for individual components",
            "integration": "Integration tests for database operations",
            "performance": "Performance and load tests",
            "security": "Security and authentication tests",
            "isolation": "Data isolation and tenant security tests",
            "benchmark": "Performance benchmark tests",
            "stress": "Stress testing under extreme load",
            "slow": "Slow running tests (excluded by default)",
            "smoke": "Quick smoke tests for basic functionality",
            "green_api": "Green API related tests",
            "deepseek": "DeepSeek AI related tests",
            "webhook": "Webhook related tests",
            "celery": "Celery task tests",
            "message_processing": "Message processing tests",
            "sentiment": "Sentiment analysis tests",
            "trigger": "Trigger engine tests",
            "notification": "Notification system tests",
            "api": "API endpoint tests",
            "database": "Database operation tests",
            "mock": "Tests using mock services",
            "fixture": "Tests using fixtures",
            "e2e": "End-to-end workflow tests"
        }


# Global test settings instance
test_settings = TestSettings()


# Convenience functions for common test configurations
def get_test_db_url(test_name: Optional[str] = None) -> str:
    """Get test database URL"""
    return test_settings.get_test_database_url(test_name)


def get_mock_config() -> Dict[str, Any]:
    """Get mock configuration"""
    return test_settings.get_mock_config()


def is_performance_test_enabled() -> bool:
    """Check if performance tests are enabled"""
    return os.getenv("ENABLE_PERFORMANCE_TESTS", "true").lower() == "true"


def is_stress_test_enabled() -> bool:
    """Check if stress tests are enabled"""
    return os.getenv("ENABLE_STRESS_TESTS", "false").lower() == "true"


def get_test_timeout(test_type: str = "default") -> int:
    """Get timeout for specific test type"""
    timeouts = {
        "unit": 60,
        "integration": 300,
        "performance": 900,
        "stress": 1800,
        "security": 300,
        "e2e": 1200,
        "default": 300
    }
    return timeouts.get(test_type, timeouts["default"])


# Export main components
__all__ = [
    'TestSettings',
    'DatabaseConfig',
    'RedisConfig',
    'APIConfig',
    'PerformanceConfig',
    'SecurityConfig',
    'test_settings',
    'get_test_db_url',
    'get_mock_config',
    'is_performance_test_enabled',
    'is_stress_test_enabled',
    'get_test_timeout'
]