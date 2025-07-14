"""
Security initialization and validation module

This module ensures all security components are properly initialized
and configured for the application environment.
"""

import os
import sys
from typing import Dict, List, Optional, Any
from pathlib import Path
import structlog

from app.core.config import settings
from app.core.security_config import get_security_config, security_monitor
from app.core.secrets_manager import secrets_manager
from app.core.vault_integration import vault_secrets_manager
from app.utils.encryption import key_manager

logger = structlog.get_logger(__name__)


class SecurityInitializationError(Exception):
    """Exception raised when security initialization fails"""
    pass


class SecurityValidator:
    """Validates security configuration and components"""
    
    def __init__(self):
        self.validation_results = {}
        self.critical_failures = []
        self.warnings = []
    
    def validate_encryption_setup(self) -> bool:
        """Validate encryption and key management setup"""
        try:
            # Test key manager initialization
            encryption = key_manager.get_encryption()
            
            # Test encryption/decryption
            test_data = "security_test_data"
            encrypted = encryption.encrypt_string(test_data)
            decrypted = encryption.decrypt_string(encrypted)
            
            if decrypted != test_data:
                self.critical_failures.append("Encryption/decryption test failed")
                return False
            
            logger.info("Encryption setup validation passed")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Encryption setup failed: {str(e)}")
            return False
    
    def validate_secrets_management(self) -> bool:
        """Validate secrets management system"""
        try:
            # Test local secrets manager
            test_secret_id = "test_secret"
            test_secret_value = "test_value_12345"
            
            # Store test secret
            success = secrets_manager.set_secret(
                test_secret_id,
                test_secret_value
            )
            
            if not success:
                self.critical_failures.append("Failed to store test secret")
                return False
            
            # Retrieve test secret
            retrieved_value = secrets_manager.get_secret(test_secret_id)
            
            if retrieved_value != test_secret_value:
                self.critical_failures.append("Secret retrieval test failed")
                return False
            
            # Clean up test secret
            secrets_manager.store.delete_secret(test_secret_id)
            
            logger.info("Secrets management validation passed")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Secrets management validation failed: {str(e)}")
            return False
    
    def validate_vault_integration(self) -> bool:
        """Validate Vault integration if enabled"""
        if not settings.ENABLE_VAULT_INTEGRATION:
            logger.info("Vault integration disabled, skipping validation")
            return True
        
        try:
            if not vault_secrets_manager.vault_client:
                self.warnings.append("Vault client not available despite being enabled")
                return True
            
            # Test Vault connectivity
            test_path = "test/security_validation"
            test_data = {"test_key": "test_value"}
            
            # Try to write and read test secret
            write_success = vault_secrets_manager.set_secret(test_path, test_data)
            if write_success:
                retrieved_data = vault_secrets_manager.get_secret(test_path)
                if retrieved_data:
                    logger.info("Vault integration validation passed")
                    return True
            
            self.warnings.append("Vault integration test failed")
            return True  # Non-critical for application startup
            
        except Exception as e:
            self.warnings.append(f"Vault validation error: {str(e)}")
            return True  # Non-critical for application startup
    
    def validate_security_config(self) -> bool:
        """Validate security configuration"""
        try:
            config = get_security_config(settings.ENVIRONMENT)
            
            # Validate required configuration
            if not config.headers.content_security_policy:
                self.critical_failures.append("Content Security Policy not configured")
                return False
            
            if not config.cors.allow_origins:
                self.critical_failures.append("CORS origins not configured")
                return False
            
            # Validate environment-specific settings
            if settings.ENVIRONMENT == "production":
                if config.security_level.value not in ["high", "critical"]:
                    self.warnings.append("Production environment should use high or critical security level")
                
                if "max-age=0" in config.headers.strict_transport_security:
                    self.warnings.append("HSTS disabled in production environment")
            
            logger.info(
                "Security configuration validation passed",
                environment=settings.ENVIRONMENT,
                security_level=config.security_level.value
            )
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Security configuration validation failed: {str(e)}")
            return False
    
    def validate_database_security(self) -> bool:
        """Validate database security setup"""
        try:
            from app.core.database_security import security_monitor as db_security_monitor
            
            # Test query validation
            test_query = "SELECT * FROM users WHERE id = :user_id"
            validation_result = db_security_monitor.query_builder.validate_query_string(test_query)
            
            if not validation_result:
                self.critical_failures.append("Database query validation failed")
                return False
            
            # Test injection detection
            malicious_query = "SELECT * FROM users WHERE id = 1 OR 1=1"
            try:
                db_security_monitor.query_builder.validate_query_string(malicious_query)
                self.warnings.append("SQL injection detection may not be working properly")
            except Exception:
                # Expected to fail - this is good
                pass
            
            logger.info("Database security validation passed")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Database security validation failed: {str(e)}")
            return False
    
    def validate_input_sanitization(self) -> bool:
        """Validate input sanitization"""
        try:
            from app.utils.input_sanitizer import default_sanitizer
            
            # Test XSS prevention
            xss_input = "<script>alert('xss')</script>Hello"
            sanitized = default_sanitizer.sanitize_html(xss_input)
            
            if "<script>" in sanitized:
                self.critical_failures.append("XSS sanitization failed")
                return False
            
            # Test SQL injection prevention
            sql_input = "'; DROP TABLE users; --"
            sanitized_sql = default_sanitizer.sanitize_sql_input(sql_input)
            
            if "DROP TABLE" in sanitized_sql.upper():
                self.critical_failures.append("SQL injection sanitization failed")
                return False
            
            logger.info("Input sanitization validation passed")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Input sanitization validation failed: {str(e)}")
            return False
    
    def validate_rate_limiting(self) -> bool:
        """Validate rate limiting setup"""
        try:
            from app.core.rate_limit_config import get_rate_limit_config
            
            config = get_rate_limit_config(settings.ENVIRONMENT)
            
            if not config.enabled:
                self.warnings.append("Rate limiting is disabled")
                return True
            
            # Validate configuration
            if not config.default_global_limit.requests_per_minute:
                self.critical_failures.append("Global rate limit not configured")
                return False
            
            logger.info("Rate limiting validation passed")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Rate limiting validation failed: {str(e)}")
            return False
    
    def run_full_validation(self) -> Dict[str, Any]:
        """Run complete security validation"""
        logger.info("Starting comprehensive security validation")
        
        validations = {
            "encryption_setup": self.validate_encryption_setup(),
            "secrets_management": self.validate_secrets_management(),
            "vault_integration": self.validate_vault_integration(),
            "security_config": self.validate_security_config(),
            "database_security": self.validate_database_security(),
            "input_sanitization": self.validate_input_sanitization(),
            "rate_limiting": self.validate_rate_limiting()
        }
        
        # Calculate overall status
        critical_passed = all(validations[key] for key in [
            "encryption_setup", "secrets_management", "security_config",
            "database_security", "input_sanitization", "rate_limiting"
        ])
        
        results = {
            "validations": validations,
            "critical_passed": critical_passed,
            "critical_failures": self.critical_failures,
            "warnings": self.warnings,
            "overall_status": "PASS" if critical_passed and not self.critical_failures else "FAIL"
        }
        
        # Log results
        if critical_passed and not self.critical_failures:
            logger.info(
                "Security validation completed successfully",
                warnings_count=len(self.warnings),
                validations_passed=sum(validations.values())
            )
        else:
            logger.error(
                "Security validation failed",
                critical_failures=self.critical_failures,
                warnings=self.warnings
            )
        
        return results


def initialize_security_components() -> bool:
    """
    Initialize all security components
    
    Returns:
        bool: True if initialization successful
    """
    logger.info("Initializing security components")
    
    try:
        # Initialize encryption and key management
        key_manager.load_or_create_master_key()
        logger.info("Encryption and key management initialized")
        
        # Initialize secrets management
        secrets_manager.store._load_metadata_cache()
        logger.info("Secrets management initialized")
        
        # Initialize Vault if enabled
        if settings.ENABLE_VAULT_INTEGRATION and vault_secrets_manager.vault_client:
            logger.info("Vault integration initialized")
        
        # Initialize security monitoring
        security_monitor.config.enable_security_alerts = True
        logger.info("Security monitoring initialized")
        
        return True
        
    except Exception as e:
        logger.error("Security components initialization failed", error=str(e))
        return False


def validate_security_environment() -> bool:
    """
    Validate security environment and configuration
    
    Returns:
        bool: True if validation passes
    """
    validator = SecurityValidator()
    results = validator.run_full_validation()
    
    if results["overall_status"] == "FAIL":
        logger.error(
            "Security environment validation failed",
            critical_failures=results["critical_failures"]
        )
        return False
    
    if results["warnings"]:
        logger.warning(
            "Security validation completed with warnings",
            warnings=results["warnings"]
        )
    
    return True


def setup_security_system() -> bool:
    """
    Complete security system setup and validation
    
    Returns:
        bool: True if setup successful
    """
    logger.info("Setting up security system")
    
    try:
        # Initialize components
        if not initialize_security_components():
            raise SecurityInitializationError("Failed to initialize security components")
        
        # Validate environment
        if not validate_security_environment():
            raise SecurityInitializationError("Security environment validation failed")
        
        logger.info("Security system setup completed successfully")
        return True
        
    except Exception as e:
        logger.error("Security system setup failed", error=str(e))
        return False


# Export main functions
__all__ = [
    'SecurityValidator',
    'SecurityInitializationError',
    'initialize_security_components',
    'validate_security_environment',
    'setup_security_system'
]
