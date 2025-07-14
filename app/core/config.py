"""
Configuration settings for WhatsApp Hotel Bot MVP
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    """Application settings"""
    
    # Project info
    PROJECT_NAME: str = "WhatsApp Hotel Bot"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/hotel_bot"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # External APIs
    GREEN_API_URL: str = "https://api.green-api.com"
    GREEN_API_INSTANCE_ID: Optional[str] = None
    GREEN_API_TOKEN: Optional[str] = None
    
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_URL: str = "https://api.deepseek.com"
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Secrets Management
    SECRETS_STORAGE_PATH: str = ".secrets"
    ENCRYPTION_KEY_FILE: str = ".encryption_key"
    ENABLE_VAULT_INTEGRATION: bool = False

    # HashiCorp Vault (optional)
    VAULT_ADDR: Optional[str] = None
    VAULT_TOKEN: Optional[str] = None
    VAULT_NAMESPACE: Optional[str] = None
    VAULT_MOUNT_POINT: str = "secret"
    VAULT_USERNAME: Optional[str] = None
    VAULT_PASSWORD: Optional[str] = None
    VAULT_ROLE_ID: Optional[str] = None
    VAULT_SECRET_ID: Optional[str] = None
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    BASE_URL: str = "http://localhost:8000"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Email notifications
    NOTIFICATION_EMAIL_SMTP_HOST: Optional[str] = None
    NOTIFICATION_EMAIL_SMTP_PORT: int = 587
    NOTIFICATION_EMAIL_USERNAME: Optional[str] = None
    NOTIFICATION_EMAIL_PASSWORD: Optional[str] = None
    
    # DeepSeek AI Configuration (additional settings)
    DEEPSEEK_MAX_TOKENS: int = Field(default=4096, env="DEEPSEEK_MAX_TOKENS")
    DEEPSEEK_TEMPERATURE: float = Field(default=0.7, env="DEEPSEEK_TEMPERATURE")
    DEEPSEEK_TIMEOUT: int = Field(default=60, env="DEEPSEEK_TIMEOUT")
    DEEPSEEK_MAX_REQUESTS_PER_MINUTE: int = Field(default=50, env="DEEPSEEK_MAX_REQUESTS_PER_MINUTE")
    DEEPSEEK_MAX_TOKENS_PER_MINUTE: int = Field(default=100000, env="DEEPSEEK_MAX_TOKENS_PER_MINUTE")
    DEEPSEEK_MAX_RETRIES: int = Field(default=3, env="DEEPSEEK_MAX_RETRIES")
    DEEPSEEK_RETRY_DELAY: float = Field(default=1.0, env="DEEPSEEK_RETRY_DELAY")
    DEEPSEEK_CACHE_ENABLED: bool = Field(default=True, env="DEEPSEEK_CACHE_ENABLED")
    DEEPSEEK_CACHE_TTL: int = Field(default=3600, env="DEEPSEEK_CACHE_TTL")

    # Sentiment Analysis Configuration
    SENTIMENT_POSITIVE_THRESHOLD: float = Field(default=0.3, env="SENTIMENT_POSITIVE_THRESHOLD")
    SENTIMENT_NEGATIVE_THRESHOLD: float = Field(default=-0.3, env="SENTIMENT_NEGATIVE_THRESHOLD")
    SENTIMENT_ATTENTION_THRESHOLD: float = Field(default=-0.7, env="SENTIMENT_ATTENTION_THRESHOLD")
    SENTIMENT_MIN_CONFIDENCE: float = Field(default=0.6, env="SENTIMENT_MIN_CONFIDENCE")
    SENTIMENT_NOTIFY_ON_NEGATIVE: bool = Field(default=True, env="SENTIMENT_NOTIFY_ON_NEGATIVE")
    SENTIMENT_NOTIFY_ON_ATTENTION: bool = Field(default=True, env="SENTIMENT_NOTIFY_ON_ATTENTION")
    SENTIMENT_DEFAULT_LANGUAGE: str = Field(default="en", env="SENTIMENT_DEFAULT_LANGUAGE")

    # Response Generation Configuration
    RESPONSE_MAX_TOKENS: int = Field(default=500, env="RESPONSE_MAX_TOKENS")
    RESPONSE_TEMPERATURE: float = Field(default=0.8, env="RESPONSE_TEMPERATURE")
    RESPONSE_MAX_CONTEXT_MESSAGES: int = Field(default=10, env="RESPONSE_MAX_CONTEXT_MESSAGES")
    RESPONSE_INCLUDE_GUEST_HISTORY: bool = Field(default=True, env="RESPONSE_INCLUDE_GUEST_HISTORY")
    RESPONSE_MIN_LENGTH: int = Field(default=10, env="RESPONSE_MIN_LENGTH")
    RESPONSE_MAX_LENGTH: int = Field(default=1000, env="RESPONSE_MAX_LENGTH")
    RESPONSE_USE_GUEST_PREFERENCES: bool = Field(default=True, env="RESPONSE_USE_GUEST_PREFERENCES")
    RESPONSE_USE_HOTEL_BRANDING: bool = Field(default=True, env="RESPONSE_USE_HOTEL_BRANDING")

    # Monitoring
    PROMETHEUS_ENABLED: bool = False
    GRAFANA_ENABLED: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Validate critical settings
def validate_settings():
    """Validate critical configuration settings"""
    errors = []
    
    if not settings.SECRET_KEY or settings.SECRET_KEY == "your-super-secret-key-here-change-in-production":
        if settings.ENVIRONMENT == "production":
            errors.append("SECRET_KEY must be set in production")
    
    if settings.ENVIRONMENT == "production":
        if not settings.GREEN_API_INSTANCE_ID:
            errors.append("GREEN_API_INSTANCE_ID is required")
        if not settings.GREEN_API_TOKEN:
            errors.append("GREEN_API_TOKEN is required")
        if not settings.DEEPSEEK_API_KEY:
            errors.append("DEEPSEEK_API_KEY is required")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

# Validate on import
if settings.ENVIRONMENT == "production":
    validate_settings()
