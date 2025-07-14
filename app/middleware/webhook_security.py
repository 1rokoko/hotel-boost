"""
Webhook security middleware for validating webhook signatures and preventing attacks

This middleware provides comprehensive webhook security including signature validation,
timestamp verification, replay attack prevention, and rate limiting for webhook endpoints.
"""

import time
import json
from typing import Callable, Dict, Any, Optional, Set
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.core.webhook_config import (
    WebhookSecuritySettings,
    get_webhook_security_config,
    GreenAPIWebhookConfig
)
from app.utils.signature_validator import (
    EnhancedSignatureValidator,
    SignatureValidationError,
    TimestampValidationError,
    ReplayAttackError
)
from app.core.config import settings

logger = structlog.get_logger(__name__)


class WebhookSecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for webhook security validation
    
    Provides:
    - Signature validation with HMAC
    - Timestamp verification
    - Replay attack prevention
    - Rate limiting for webhook endpoints
    - Content validation
    """
    
    def __init__(
        self,
        app,
        webhook_paths: Optional[Set[str]] = None,
        environment: str = "production"
    ):
        super().__init__(app)
        
        # Load configuration
        self.config = get_webhook_security_config(environment)
        
        # Define webhook paths that require security validation
        self.webhook_paths = webhook_paths or {
            "/api/v1/webhooks/green-api",
            "/api/v1/webhooks/green-api/",
            "/webhooks/green-api",
            "/webhooks/green-api/"
        }
        
        # Initialize validators for different providers
        self.validators = {
            'green_api': EnhancedSignatureValidator(self.config.providers.green_api)
        }
        
        # Rate limiting storage (in production, use Redis)
        self.rate_limit_storage = {}
        self.rate_limit_window = 60  # 1 minute window
        
        logger.info(
            "Webhook security middleware initialized",
            environment=environment,
            strict_mode=self.config.strict_mode,
            webhook_paths=list(self.webhook_paths)
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through webhook security validation
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        start_time = time.time()
        
        # Check if this is a webhook endpoint
        if not self._is_webhook_path(request.url.path):
            return await call_next(request)
        
        # Skip security validation if disabled
        if not self.config.enabled:
            logger.debug("Webhook security validation disabled")
            return await call_next(request)
        
        try:
            # Apply rate limiting
            await self._check_rate_limit(request)
            
            # Validate content type and size
            await self._validate_content(request)
            
            # Determine webhook provider
            provider = self._detect_webhook_provider(request)
            
            # Get validator for provider
            validator = self.validators.get(provider)
            if not validator:
                if self.config.strict_mode:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unsupported webhook provider: {provider}"
                    )
                else:
                    logger.warning("Unknown webhook provider, skipping validation", provider=provider)
                    return await call_next(request)
            
            # Perform security validation
            await self._validate_webhook_security(request, validator, provider)
            
            # Process request
            response = await call_next(request)
            
            # Log successful validation
            processing_time = (time.time() - start_time) * 1000
            logger.info(
                "Webhook security validation successful",
                provider=provider,
                path=request.url.path,
                processing_time_ms=processing_time
            )
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Webhook security validation error",
                error=str(e),
                path=request.url.path,
                client_ip=self._get_client_ip(request)
            )
            
            if self.config.strict_mode:
                raise HTTPException(
                    status_code=500,
                    detail="Webhook security validation failed"
                )
            else:
                # In non-strict mode, allow request to proceed with warning
                logger.warning("Proceeding with webhook request despite validation error")
                return await call_next(request)
    
    def _is_webhook_path(self, path: str) -> bool:
        """Check if path is a webhook endpoint"""
        return any(webhook_path in path for webhook_path in self.webhook_paths)
    
    def _detect_webhook_provider(self, request: Request) -> str:
        """Detect webhook provider from request"""
        path = request.url.path.lower()
        
        if "green-api" in path:
            return "green_api"
        
        # Check headers for provider identification
        user_agent = request.headers.get("User-Agent", "").lower()
        if "green-api" in user_agent:
            return "green_api"
        
        # Default to green_api for now
        return "green_api"
    
    async def _check_rate_limit(self, request: Request) -> None:
        """Check rate limiting for webhook endpoints"""
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Clean old entries
        cutoff_time = current_time - self.rate_limit_window
        if client_ip in self.rate_limit_storage:
            self.rate_limit_storage[client_ip] = [
                timestamp for timestamp in self.rate_limit_storage[client_ip]
                if timestamp > cutoff_time
            ]
        else:
            self.rate_limit_storage[client_ip] = []
        
        # Check rate limit
        request_count = len(self.rate_limit_storage[client_ip])
        rate_limit = self.config.providers.green_api.webhook_rate_limit_per_minute
        
        if request_count >= rate_limit:
            logger.warning(
                "Webhook rate limit exceeded",
                client_ip=client_ip,
                request_count=request_count,
                rate_limit=rate_limit
            )
            
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for webhook endpoint",
                headers={
                    "Retry-After": str(self.rate_limit_window),
                    "X-RateLimit-Limit": str(rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(current_time + self.rate_limit_window))
                }
            )
        
        # Record this request
        self.rate_limit_storage[client_ip].append(current_time)
    
    async def _validate_content(self, request: Request) -> None:
        """Validate request content type and size"""
        # Check content type
        content_type = request.headers.get("Content-Type", "").split(";")[0].strip()
        allowed_types = self.config.providers.green_api.allowed_content_types
        
        if content_type not in allowed_types:
            logger.warning(
                "Invalid content type for webhook",
                content_type=content_type,
                allowed_types=list(allowed_types)
            )
            
            if self.config.strict_mode:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid content type: {content_type}"
                )
        
        # Check content length
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                size = int(content_length)
                max_size = self.config.providers.green_api.max_payload_size_bytes
                
                if size > max_size:
                    logger.warning(
                        "Webhook payload too large",
                        content_length=size,
                        max_size=max_size
                    )
                    
                    raise HTTPException(
                        status_code=413,
                        detail=f"Payload too large: {size} bytes (max: {max_size})"
                    )
            except ValueError:
                logger.warning("Invalid Content-Length header", content_length=content_length)
    
    async def _validate_webhook_security(
        self,
        request: Request,
        validator: EnhancedSignatureValidator,
        provider: str
    ) -> None:
        """Validate webhook security (signature, timestamp, replay protection)"""
        try:
            # Get request body
            body = await request.body()
            
            # Get headers
            headers = dict(request.headers)
            
            # For Green API, we need to get the secret from the hotel
            # This is a simplified version - in practice, you'd look up the hotel
            # based on instance ID and get the webhook token
            secret = await self._get_webhook_secret(request, provider)
            
            if not secret:
                if self.config.strict_mode:
                    raise HTTPException(
                        status_code=401,
                        detail="Webhook secret not configured"
                    )
                else:
                    logger.warning("No webhook secret configured, skipping validation")
                    return
            
            # Perform comprehensive validation
            result = validator.comprehensive_validation(
                body=body,
                headers=headers,
                secret=secret
            )
            
            if not result['is_valid']:
                error_details = "; ".join(result['validation_errors'])
                logger.error(
                    "Webhook security validation failed",
                    provider=provider,
                    errors=result['validation_errors'],
                    client_ip=self._get_client_ip(request)
                )
                
                raise HTTPException(
                    status_code=401,
                    detail=f"Webhook validation failed: {error_details}"
                )
            
        except (SignatureValidationError, TimestampValidationError, ReplayAttackError) as e:
            logger.error(
                "Webhook security error",
                error=str(e),
                error_type=type(e).__name__,
                provider=provider
            )
            
            raise HTTPException(
                status_code=401,
                detail=f"Webhook security validation failed: {str(e)}"
            )
    
    async def _get_webhook_secret(self, request: Request, provider: str) -> Optional[str]:
        """
        Get webhook secret for validation
        
        This is a simplified implementation. In practice, you would:
        1. Extract instance ID from headers or URL
        2. Look up the hotel by instance ID
        3. Return the hotel's webhook token
        """
        if provider == "green_api":
            # Extract instance ID from headers
            instance_id = request.headers.get("X-Green-Api-Instance")
            
            if not instance_id:
                # Try to extract from URL or body
                # This would need to be implemented based on your URL structure
                pass
            
            # For now, return a placeholder
            # In real implementation, look up hotel by instance_id and return webhook_token
            return "placeholder_secret"  # This should be replaced with actual lookup
        
        return None
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        if request.client:
            return request.client.host
        
        return "unknown"


# Convenience function to add webhook security middleware
def add_webhook_security_middleware(
    app,
    webhook_paths: Optional[Set[str]] = None,
    environment: str = "production"
) -> None:
    """
    Add webhook security middleware to FastAPI app
    
    Args:
        app: FastAPI application
        webhook_paths: Set of webhook paths to protect
        environment: Environment configuration to use
    """
    middleware = WebhookSecurityMiddleware(
        app=app,
        webhook_paths=webhook_paths,
        environment=environment
    )
    
    app.add_middleware(WebhookSecurityMiddleware, **{
        'webhook_paths': webhook_paths,
        'environment': environment
    })
    
    logger.info(
        "Webhook security middleware added",
        environment=environment,
        webhook_paths=list(webhook_paths) if webhook_paths else None
    )


# Export main classes and functions
__all__ = [
    'WebhookSecurityMiddleware',
    'add_webhook_security_middleware'
]
