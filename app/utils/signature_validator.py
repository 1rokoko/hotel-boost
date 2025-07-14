"""
Enhanced signature validation utilities for webhook security

This module provides comprehensive signature validation including HMAC verification,
timestamp validation, and replay attack prevention for webhook endpoints.
"""

import hmac
import hashlib
import time
import json
from typing import Optional, Dict, Any, Tuple, Set
from datetime import datetime, timezone
import structlog
import redis
from app.core.config import settings
from app.core.webhook_config import WebhookSecurityConfig, GreenAPIWebhookConfig

logger = structlog.get_logger(__name__)


class SignatureValidationError(Exception):
    """Exception raised when signature validation fails"""
    pass


class TimestampValidationError(Exception):
    """Exception raised when timestamp validation fails"""
    pass


class ReplayAttackError(Exception):
    """Exception raised when replay attack is detected"""
    pass


class EnhancedSignatureValidator:
    """Enhanced signature validator with replay protection and timestamp validation"""
    
    def __init__(self, config: WebhookSecurityConfig):
        self.config = config
        self.redis_client = self._create_redis_client()
        self.replay_cache_prefix = "webhook_replay:"
        
    def _create_redis_client(self) -> Optional[redis.Redis]:
        """Create Redis client for replay protection"""
        if not self.config.enable_replay_protection:
            return None
            
        try:
            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            client.ping()
            logger.info("Redis connection established for webhook replay protection")
            return client
        except Exception as e:
            logger.error("Failed to connect to Redis for replay protection", error=str(e))
            return None
    
    def validate_signature(
        self,
        body: bytes,
        signature: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """
        Validate HMAC signature using constant-time comparison
        
        Args:
            body: Raw request body as bytes
            signature: Signature from header
            secret: Secret key for HMAC
            algorithm: Hash algorithm (sha1, sha256, sha512)
            
        Returns:
            bool: True if signature is valid
            
        Raises:
            SignatureValidationError: If signature validation fails
        """
        if not signature or not secret:
            raise SignatureValidationError("Missing signature or secret")
        
        try:
            # Remove prefix if present
            if signature.startswith(f"{algorithm}="):
                signature = signature[len(f"{algorithm}="):]
            
            # Get hash function
            hash_func = getattr(hashlib, algorithm)
            
            # Calculate expected signature
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                body,
                hash_func
            ).hexdigest()
            
            # Use constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if not is_valid and self.config.log_invalid_signatures:
                logger.warning(
                    "Invalid webhook signature detected",
                    algorithm=algorithm,
                    signature_length=len(signature),
                    expected_length=len(expected_signature),
                    body_size=len(body)
                )
            
            return is_valid
            
        except Exception as e:
            logger.error("Error validating signature", error=str(e), algorithm=algorithm)
            raise SignatureValidationError(f"Signature validation error: {str(e)}")
    
    def validate_timestamp(
        self,
        timestamp: Optional[int],
        tolerance_seconds: Optional[int] = None
    ) -> bool:
        """
        Validate webhook timestamp to prevent replay attacks
        
        Args:
            timestamp: Webhook timestamp in seconds since epoch
            tolerance_seconds: Maximum age tolerance (uses config default if None)
            
        Returns:
            bool: True if timestamp is within tolerance
            
        Raises:
            TimestampValidationError: If timestamp validation fails
        """
        if not self.config.require_timestamp:
            return True
            
        if timestamp is None:
            raise TimestampValidationError("Missing timestamp")
        
        tolerance = tolerance_seconds or self.config.timestamp_tolerance_seconds
        current_time = int(time.time())
        
        # Check if timestamp is too old
        if current_time - timestamp > tolerance:
            age_seconds = current_time - timestamp
            raise TimestampValidationError(
                f"Timestamp too old: {age_seconds}s (max: {tolerance}s)"
            )
        
        # Check if timestamp is in the future (with small tolerance for clock skew)
        future_tolerance = 60  # 1 minute tolerance for clock skew
        if timestamp > current_time + future_tolerance:
            future_seconds = timestamp - current_time
            raise TimestampValidationError(
                f"Timestamp in future: {future_seconds}s ahead"
            )
        
        return True
    
    def check_replay_attack(
        self,
        signature: str,
        timestamp: int,
        body: bytes
    ) -> bool:
        """
        Check for replay attacks using Redis cache
        
        Args:
            signature: Request signature
            timestamp: Request timestamp
            body: Request body
            
        Returns:
            bool: True if request is not a replay
            
        Raises:
            ReplayAttackError: If replay attack is detected
        """
        if not self.config.enable_replay_protection or not self.redis_client:
            return True
        
        try:
            # Create unique request identifier
            request_hash = hashlib.sha256(
                f"{signature}:{timestamp}:{len(body)}".encode()
            ).hexdigest()
            
            cache_key = f"{self.replay_cache_prefix}{request_hash}"
            
            # Check if request was already processed
            if self.redis_client.exists(cache_key):
                if self.config.log_replay_attempts:
                    logger.warning(
                        "Replay attack detected",
                        request_hash=request_hash,
                        timestamp=timestamp,
                        signature_prefix=signature[:16] + "..."
                    )
                raise ReplayAttackError("Duplicate request detected")
            
            # Store request identifier with TTL
            self.redis_client.setex(
                cache_key,
                self.config.replay_cache_ttl_seconds,
                json.dumps({
                    "timestamp": timestamp,
                    "processed_at": int(time.time()),
                    "signature_hash": hashlib.sha256(signature.encode()).hexdigest()
                })
            )
            
            return True
            
        except redis.RedisError as e:
            logger.error("Redis error during replay check", error=str(e))
            # In case of Redis failure, allow request but log warning
            logger.warning("Replay protection unavailable due to Redis error")
            return True
        except ReplayAttackError:
            raise
        except Exception as e:
            logger.error("Unexpected error during replay check", error=str(e))
            return True
    
    def comprehensive_validation(
        self,
        body: bytes,
        headers: Dict[str, str],
        secret: str,
        webhook_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive webhook validation
        
        Args:
            body: Raw request body
            headers: Request headers
            secret: Webhook secret
            webhook_data: Parsed webhook data (optional)
            
        Returns:
            Dict containing validation results
            
        Raises:
            SignatureValidationError: If signature validation fails
            TimestampValidationError: If timestamp validation fails
            ReplayAttackError: If replay attack is detected
        """
        results = {
            'signature_valid': False,
            'timestamp_valid': False,
            'replay_check_passed': False,
            'validation_errors': [],
            'security_warnings': []
        }
        
        try:
            # Extract signature from headers
            signature = headers.get(self.config.signature_header)
            if not signature:
                raise SignatureValidationError(f"Missing {self.config.signature_header} header")
            
            # Validate signature
            results['signature_valid'] = self.validate_signature(
                body=body,
                signature=signature,
                secret=secret,
                algorithm=self.config.signature_algorithm
            )
            
            # Extract and validate timestamp
            timestamp_str = headers.get(self.config.timestamp_header)
            timestamp = None
            
            if timestamp_str:
                try:
                    timestamp = int(timestamp_str)
                    results['timestamp_valid'] = self.validate_timestamp(timestamp)
                except ValueError:
                    raise TimestampValidationError("Invalid timestamp format")
            elif self.config.require_timestamp:
                raise TimestampValidationError(f"Missing {self.config.timestamp_header} header")
            else:
                results['timestamp_valid'] = True
            
            # Check for replay attacks
            if timestamp and results['signature_valid']:
                results['replay_check_passed'] = self.check_replay_attack(
                    signature=signature,
                    timestamp=timestamp,
                    body=body
                )
            else:
                results['replay_check_passed'] = True
            
            # Overall validation result
            results['is_valid'] = (
                results['signature_valid'] and
                results['timestamp_valid'] and
                results['replay_check_passed']
            )
            
            if results['is_valid']:
                logger.debug(
                    "Webhook validation successful",
                    signature_algorithm=self.config.signature_algorithm,
                    timestamp=timestamp,
                    body_size=len(body)
                )
            
            return results
            
        except (SignatureValidationError, TimestampValidationError, ReplayAttackError) as e:
            results['validation_errors'].append(str(e))
            results['is_valid'] = False
            
            if self.config.alert_on_security_violations:
                logger.error(
                    "Webhook security validation failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    headers=self._sanitize_headers(headers)
                )
            
            raise
        except Exception as e:
            results['validation_errors'].append(f"Unexpected validation error: {str(e)}")
            results['is_valid'] = False
            logger.error("Unexpected webhook validation error", error=str(e))
            raise SignatureValidationError(f"Validation failed: {str(e)}")
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize headers for logging (remove sensitive data)"""
        sanitized = {}
        sensitive_headers = {'authorization', 'x-api-key', 'x-secret'}
        
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                sanitized[key] = "***REDACTED***"
            elif 'signature' in key.lower():
                sanitized[key] = value[:16] + "..." if len(value) > 16 else value
            else:
                sanitized[key] = value
                
        return sanitized


# Convenience functions for backward compatibility
def validate_green_api_webhook_enhanced(
    body: bytes,
    signature: Optional[str],
    secret: str,
    timestamp: Optional[int] = None,
    config: Optional[GreenAPIWebhookConfig] = None
) -> bool:
    """
    Enhanced Green API webhook validation with replay protection
    
    Args:
        body: Raw webhook body as bytes
        signature: Webhook signature from header
        secret: Webhook secret token
        timestamp: Webhook timestamp
        config: Webhook configuration (uses default if None)
        
    Returns:
        bool: True if webhook is valid
    """
    if config is None:
        config = GreenAPIWebhookConfig()
    
    validator = EnhancedSignatureValidator(config)
    
    try:
        headers = {}
        if signature:
            headers[config.signature_header] = signature
        if timestamp:
            headers[config.timestamp_header] = str(timestamp)
        
        result = validator.comprehensive_validation(
            body=body,
            headers=headers,
            secret=secret
        )
        
        return result['is_valid']
        
    except Exception as e:
        logger.error("Enhanced webhook validation failed", error=str(e))
        return False


# Export main classes and functions
__all__ = [
    'EnhancedSignatureValidator',
    'SignatureValidationError',
    'TimestampValidationError', 
    'ReplayAttackError',
    'validate_green_api_webhook_enhanced'
]
