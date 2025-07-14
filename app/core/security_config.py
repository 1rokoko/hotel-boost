"""
Comprehensive security configuration for the application

This module provides centralized security configuration including
headers, CORS, authentication, and monitoring settings.
"""

import time
from typing import Dict, List, Set, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class SecurityLevel(str, Enum):
    """Security levels for different environments"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityHeadersConfig(BaseModel):
    """Configuration for security headers"""
    
    # Content Security Policy
    content_security_policy: str = Field(
        default=(
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        ),
        description="Content Security Policy header value"
    )
    
    # Strict Transport Security
    strict_transport_security: str = Field(
        default="max-age=31536000; includeSubDomains; preload",
        description="HSTS header value"
    )
    
    # X-Frame-Options
    x_frame_options: str = Field(
        default="DENY",
        description="X-Frame-Options header value"
    )
    
    # X-Content-Type-Options
    x_content_type_options: str = Field(
        default="nosniff",
        description="X-Content-Type-Options header value"
    )
    
    # X-XSS-Protection
    x_xss_protection: str = Field(
        default="1; mode=block",
        description="X-XSS-Protection header value"
    )
    
    # Referrer Policy
    referrer_policy: str = Field(
        default="strict-origin-when-cross-origin",
        description="Referrer-Policy header value"
    )
    
    # Permissions Policy
    permissions_policy: str = Field(
        default=(
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "speaker=()"
        ),
        description="Permissions-Policy header value"
    )
    
    # Cross-Origin Embedder Policy
    cross_origin_embedder_policy: str = Field(
        default="require-corp",
        description="Cross-Origin-Embedder-Policy header value"
    )
    
    # Cross-Origin Opener Policy
    cross_origin_opener_policy: str = Field(
        default="same-origin",
        description="Cross-Origin-Opener-Policy header value"
    )
    
    # Cross-Origin Resource Policy
    cross_origin_resource_policy: str = Field(
        default="same-origin",
        description="Cross-Origin-Resource-Policy header value"
    )
    
    # Custom headers
    custom_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom security headers"
    )


class CORSConfig(BaseModel):
    """Enhanced CORS configuration"""
    
    allow_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"],
        description="Allowed origins for CORS"
    )
    
    allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests"
    )
    
    allow_methods: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        description="Allowed HTTP methods"
    )
    
    allow_headers: List[str] = Field(
        default_factory=lambda: [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-Hotel-ID",
            "X-API-Key"
        ],
        description="Allowed headers"
    )
    
    expose_headers: List[str] = Field(
        default_factory=lambda: [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Request-ID"
        ],
        description="Headers to expose to the client"
    )
    
    max_age: int = Field(
        default=86400,  # 24 hours
        description="Maximum age for preflight cache"
    )


class AuthenticationConfig(BaseModel):
    """Authentication and authorization configuration"""
    
    # JWT settings
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_access_token_expire_minutes: int = Field(default=30, description="Access token expiration")
    jwt_refresh_token_expire_days: int = Field(default=7, description="Refresh token expiration")
    
    # Password requirements
    min_password_length: int = Field(default=8, description="Minimum password length")
    require_uppercase: bool = Field(default=True, description="Require uppercase letters")
    require_lowercase: bool = Field(default=True, description="Require lowercase letters")
    require_numbers: bool = Field(default=True, description="Require numbers")
    require_special_chars: bool = Field(default=True, description="Require special characters")
    
    # Account security
    max_login_attempts: int = Field(default=5, description="Maximum login attempts before lockout")
    lockout_duration_minutes: int = Field(default=15, description="Account lockout duration")
    
    # Session management
    session_timeout_minutes: int = Field(default=60, description="Session timeout")
    concurrent_sessions_limit: int = Field(default=3, description="Maximum concurrent sessions")
    
    # Two-factor authentication
    enable_2fa: bool = Field(default=False, description="Enable two-factor authentication")
    totp_issuer: str = Field(default="WhatsApp Hotel Bot", description="TOTP issuer name")


class SecurityMonitoringConfig(BaseModel):
    """Security monitoring and alerting configuration"""
    
    # Logging
    log_security_events: bool = Field(default=True, description="Log security events")
    log_failed_auth_attempts: bool = Field(default=True, description="Log failed authentication")
    log_rate_limit_violations: bool = Field(default=True, description="Log rate limit violations")
    log_input_validation_failures: bool = Field(default=True, description="Log input validation failures")
    
    # Alerting
    enable_security_alerts: bool = Field(default=True, description="Enable security alerts")
    alert_on_brute_force: bool = Field(default=True, description="Alert on brute force attacks")
    alert_on_injection_attempts: bool = Field(default=True, description="Alert on injection attempts")
    alert_on_suspicious_activity: bool = Field(default=True, description="Alert on suspicious activity")
    
    # Metrics
    track_security_metrics: bool = Field(default=True, description="Track security metrics")
    metrics_retention_days: int = Field(default=90, description="Metrics retention period")
    
    # Incident response
    auto_block_suspicious_ips: bool = Field(default=False, description="Auto-block suspicious IPs")
    suspicious_activity_threshold: int = Field(default=10, description="Threshold for suspicious activity")


class ComplianceConfig(BaseModel):
    """Compliance and regulatory configuration"""
    
    # GDPR
    enable_gdpr_compliance: bool = Field(default=True, description="Enable GDPR compliance features")
    data_retention_days: int = Field(default=365, description="Data retention period")
    enable_right_to_erasure: bool = Field(default=True, description="Enable right to erasure")
    
    # PCI DSS (if handling payments)
    enable_pci_compliance: bool = Field(default=False, description="Enable PCI DSS compliance")
    mask_sensitive_data: bool = Field(default=True, description="Mask sensitive data in logs")
    
    # SOC 2
    enable_audit_logging: bool = Field(default=True, description="Enable audit logging")
    log_data_access: bool = Field(default=True, description="Log data access events")
    
    # Industry specific
    healthcare_compliance: bool = Field(default=False, description="Enable healthcare compliance (HIPAA)")
    financial_compliance: bool = Field(default=False, description="Enable financial compliance")


class SecurityConfig(BaseModel):
    """Main security configuration"""
    
    # Security level
    security_level: SecurityLevel = Field(
        default=SecurityLevel.HIGH,
        description="Overall security level"
    )
    
    # Component configurations
    headers: SecurityHeadersConfig = Field(
        default_factory=SecurityHeadersConfig,
        description="Security headers configuration"
    )
    
    cors: CORSConfig = Field(
        default_factory=CORSConfig,
        description="CORS configuration"
    )
    
    authentication: AuthenticationConfig = Field(
        default_factory=AuthenticationConfig,
        description="Authentication configuration"
    )
    
    monitoring: SecurityMonitoringConfig = Field(
        default_factory=SecurityMonitoringConfig,
        description="Security monitoring configuration"
    )
    
    compliance: ComplianceConfig = Field(
        default_factory=ComplianceConfig,
        description="Compliance configuration"
    )
    
    # Environment-specific overrides
    environment_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Environment-specific configuration overrides"
    )


# Environment-specific configurations
SECURITY_CONFIGS = {
    "development": SecurityConfig(
        security_level=SecurityLevel.MEDIUM,
        headers=SecurityHeadersConfig(
            content_security_policy=(
                "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' ws: wss: https:; "
            ),
            strict_transport_security="max-age=0"  # Disable HSTS in development
        ),
        cors=CORSConfig(
            allow_origins=["*"],  # Allow all origins in development
            allow_credentials=False
        ),
        authentication=AuthenticationConfig(
            jwt_access_token_expire_minutes=60,  # Longer tokens in development
            max_login_attempts=10,  # More lenient in development
            lockout_duration_minutes=5
        ),
        monitoring=SecurityMonitoringConfig(
            enable_security_alerts=False,  # Disable alerts in development
            auto_block_suspicious_ips=False
        )
    ),
    
    "staging": SecurityConfig(
        security_level=SecurityLevel.HIGH,
        cors=CORSConfig(
            allow_origins=[
                "https://staging.example.com",
                "https://staging-admin.example.com"
            ]
        ),
        monitoring=SecurityMonitoringConfig(
            enable_security_alerts=True,
            auto_block_suspicious_ips=False  # Manual review in staging
        )
    ),
    
    "production": SecurityConfig(
        security_level=SecurityLevel.CRITICAL,
        headers=SecurityHeadersConfig(
            strict_transport_security="max-age=63072000; includeSubDomains; preload",
            content_security_policy=(
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "upgrade-insecure-requests"
            )
        ),
        cors=CORSConfig(
            allow_origins=[
                "https://app.example.com",
                "https://admin.example.com"
            ]
        ),
        authentication=AuthenticationConfig(
            jwt_access_token_expire_minutes=15,  # Shorter tokens in production
            enable_2fa=True,
            max_login_attempts=3,
            lockout_duration_minutes=30
        ),
        monitoring=SecurityMonitoringConfig(
            enable_security_alerts=True,
            auto_block_suspicious_ips=True,
            suspicious_activity_threshold=5
        ),
        compliance=ComplianceConfig(
            enable_gdpr_compliance=True,
            enable_audit_logging=True,
            mask_sensitive_data=True
        )
    )
}


def get_security_config(environment: str = "production") -> SecurityConfig:
    """
    Get security configuration for environment
    
    Args:
        environment: Environment name
        
    Returns:
        SecurityConfig: Security configuration
    """
    config = SECURITY_CONFIGS.get(environment)
    if not config:
        logger.warning(
            "Unknown environment for security config, using production",
            environment=environment
        )
        config = SECURITY_CONFIGS["production"]
    
    # Apply environment-specific overrides
    if config.environment_overrides:
        logger.info(
            "Applying environment-specific security overrides",
            environment=environment,
            overrides=list(config.environment_overrides.keys())
        )
    
    logger.info(
        "Security configuration loaded",
        environment=environment,
        security_level=config.security_level.value
    )
    
    return config


# Global security configuration
security_config = get_security_config(settings.ENVIRONMENT)


class SecurityMonitor:
    """Security monitoring and alerting system"""

    def __init__(self, config: SecurityMonitoringConfig):
        self.config = config
        self.security_events = []
        self.blocked_ips = set()
        self.suspicious_activities = {}

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        details: Dict[str, Any],
        client_ip: Optional[str] = None
    ) -> None:
        """Log security event"""
        if not self.config.log_security_events:
            return

        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'severity': severity,
            'details': details,
            'client_ip': client_ip
        }

        self.security_events.append(event)

        logger.warning(
            "Security event detected",
            event_type=event_type,
            severity=severity,
            client_ip=client_ip,
            **details
        )

        # Check for suspicious activity
        if client_ip and self.config.auto_block_suspicious_ips:
            self._check_suspicious_activity(client_ip, event_type)

        # Send alerts if configured
        if self.config.enable_security_alerts:
            self._send_security_alert(event)

    def _check_suspicious_activity(self, client_ip: str, event_type: str) -> None:
        """Check for suspicious activity patterns"""
        if client_ip not in self.suspicious_activities:
            self.suspicious_activities[client_ip] = []

        self.suspicious_activities[client_ip].append({
            'timestamp': time.time(),
            'event_type': event_type
        })

        # Clean old events (last hour)
        cutoff = time.time() - 3600
        self.suspicious_activities[client_ip] = [
            event for event in self.suspicious_activities[client_ip]
            if event['timestamp'] > cutoff
        ]

        # Check threshold
        if len(self.suspicious_activities[client_ip]) >= self.config.suspicious_activity_threshold:
            self._block_ip(client_ip)

    def _block_ip(self, client_ip: str) -> None:
        """Block suspicious IP address"""
        self.blocked_ips.add(client_ip)

        logger.error(
            "IP address blocked due to suspicious activity",
            client_ip=client_ip,
            event_count=len(self.suspicious_activities.get(client_ip, []))
        )

        # Send high-priority alert
        self._send_security_alert({
            'event_type': 'ip_blocked',
            'severity': 'high',
            'client_ip': client_ip,
            'details': {'reason': 'suspicious_activity_threshold_exceeded'}
        })

    def _send_security_alert(self, event: Dict[str, Any]) -> None:
        """Send security alert (placeholder for actual alerting system)"""
        # In a real implementation, this would integrate with:
        # - Email notifications
        # - Slack/Teams webhooks
        # - PagerDuty/OpsGenie
        # - SIEM systems

        logger.critical(
            "SECURITY ALERT",
            alert_type=event.get('event_type'),
            severity=event.get('severity'),
            client_ip=event.get('client_ip'),
            details=event.get('details', {})
        )

    def is_ip_blocked(self, client_ip: str) -> bool:
        """Check if IP is blocked"""
        return client_ip in self.blocked_ips

    def unblock_ip(self, client_ip: str) -> bool:
        """Unblock IP address"""
        if client_ip in self.blocked_ips:
            self.blocked_ips.remove(client_ip)
            logger.info("IP address unblocked", client_ip=client_ip)
            return True
        return False


# Global security monitor
security_monitor = SecurityMonitor(security_config.monitoring)


# Export main classes and functions
__all__ = [
    'SecurityLevel',
    'SecurityHeadersConfig',
    'CORSConfig',
    'AuthenticationConfig',
    'SecurityMonitoringConfig',
    'ComplianceConfig',
    'SecurityConfig',
    'SecurityMonitor',
    'get_security_config',
    'security_config',
    'security_monitor'
]
