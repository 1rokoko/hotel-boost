"""
Comprehensive rate limiting middleware with Redis-based sliding window implementation

This middleware provides advanced rate limiting with support for per-user, per-hotel,
per-endpoint limits using sliding window algorithms and distributed storage.
"""

import time
import asyncio
from typing import Callable, Dict, Any, Optional, List, Tuple
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.core.rate_limit_config import (
    RateLimitConfig,
    RateLimitRule,
    RateLimitScope,
    get_rate_limit_config
)
from app.utils.rate_limit_storage import (
    RateLimitStorage,
    create_rate_limit_storage,
    RateLimitStorageError
)
from app.core.config import settings

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    
    def __init__(self, message: str, retry_after: int, headers: Dict[str, str]):
        self.message = message
        self.retry_after = retry_after
        self.headers = headers
        super().__init__(message)


class ComprehensiveRateLimiter(BaseHTTPMiddleware):
    """
    Comprehensive rate limiting middleware
    
    Features:
    - Per-user, per-hotel, per-endpoint rate limiting
    - Sliding window algorithms
    - Redis-based distributed storage
    - Configurable rules and exemptions
    - Rate limit headers in responses
    """
    
    def __init__(
        self,
        app,
        environment: str = "production",
        storage_backend: str = "redis"
    ):
        super().__init__(app)
        
        # Load configuration
        self.config = get_rate_limit_config(environment)
        
        # Initialize storage backend
        self.storage = create_rate_limit_storage(
            backend=storage_backend,
            key_prefix=self.config.key_prefix
        )
        
        # Cache for rule lookups
        self._rule_cache: Dict[str, RateLimitRule] = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_cache_update = 0
        
        logger.info(
            "Comprehensive rate limiter initialized",
            environment=environment,
            storage_backend=storage_backend,
            enabled=self.config.enabled
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through rate limiting
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response with rate limit headers
        """
        start_time = time.time()
        
        # Skip if rate limiting is disabled
        if not self.config.enabled:
            return await call_next(request)
        
        try:
            # Extract request context
            context = await self._extract_request_context(request)
            
            # Get applicable rate limit rules
            rules = await self._get_applicable_rules(request, context)
            
            # Check rate limits
            await self._check_rate_limits(request, context, rules)
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            await self._add_rate_limit_headers(response, context, rules)
            
            # Increment counters after successful request
            await self._increment_counters(context, rules)
            
            # Log successful request
            processing_time = (time.time() - start_time) * 1000
            logger.debug(
                "Rate limit check passed",
                path=request.url.path,
                user_id=context.get("user_id"),
                hotel_id=context.get("hotel_id"),
                processing_time_ms=processing_time
            )
            
            return response
            
        except RateLimitExceeded as e:
            # Log rate limit violation
            if self.config.log_rate_limit_hits:
                logger.warning(
                    "Rate limit exceeded",
                    path=request.url.path,
                    user_id=context.get("user_id"),
                    hotel_id=context.get("hotel_id"),
                    client_ip=self._get_client_ip(request),
                    message=e.message
                )
            
            # Return rate limit error response
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": e.message,
                    "retry_after": e.retry_after
                },
                headers=e.headers
            )
            
        except Exception as e:
            logger.error(
                "Rate limiting error",
                error=str(e),
                path=request.url.path
            )
            
            # In case of error, allow request to proceed
            if not self.config.strict_mode:
                logger.warning("Allowing request due to rate limiting error")
                return await call_next(request)
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Rate limiting service unavailable"
                )
    
    async def _extract_request_context(self, request: Request) -> Dict[str, Any]:
        """Extract context information from request"""
        context = {
            "path": request.url.path,
            "method": request.method,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
            "timestamp": time.time()
        }
        
        # Extract user information from request state (set by auth middleware)
        if hasattr(request.state, "user"):
            user = request.state.user
            context.update({
                "user_id": str(user.get("id", "")),
                "user_role": user.get("role", "anonymous"),
                "hotel_id": str(user.get("hotel_id", "")) if user.get("hotel_id") else None
            })
        else:
            context.update({
                "user_id": None,
                "user_role": "anonymous",
                "hotel_id": None
            })
        
        # Extract hotel information from headers (for multi-tenant requests)
        hotel_header = request.headers.get("X-Hotel-ID")
        if hotel_header and not context["hotel_id"]:
            context["hotel_id"] = hotel_header
        
        return context
    
    async def _get_applicable_rules(
        self,
        request: Request,
        context: Dict[str, Any]
    ) -> List[RateLimitRule]:
        """Get applicable rate limit rules for request"""
        rules = []
        
        # Global default rule
        rules.append(self.config.default_global_limit)
        
        # User role-based rules
        user_role = context.get("user_role", "anonymous")
        if hasattr(self.config.user_roles, user_role):
            role_rule = getattr(self.config.user_roles, user_role)
            rules.append(role_rule)
        
        # Endpoint-specific rules
        path = context["path"]
        method = context["method"]
        
        # Check webhook endpoints
        for endpoint_path, rule in self.config.endpoints.webhook_endpoints.items():
            if self._path_matches(path, rule.paths or [endpoint_path]):
                if not rule.methods or method in rule.methods:
                    rules.append(rule)
        
        # Check auth endpoints
        for endpoint_path, rule in self.config.endpoints.auth_endpoints.items():
            if self._path_matches(path, rule.paths or [endpoint_path]):
                if not rule.methods or method in rule.methods:
                    rules.append(rule)
        
        # Check API endpoints
        for endpoint_path, rule in self.config.endpoints.api_endpoints.items():
            if self._path_matches(path, rule.paths or [endpoint_path]):
                if not rule.methods or method in rule.methods:
                    rules.append(rule)
        
        # Hotel tier-based rules (if hotel context available)
        hotel_id = context.get("hotel_id")
        if hotel_id:
            # In a real implementation, you would look up the hotel's tier
            # For now, assume standard tier
            hotel_tier = "standard"  # This should be looked up from database
            if hasattr(self.config.hotel_tiers, hotel_tier):
                tier_rule = getattr(self.config.hotel_tiers, hotel_tier)
                rules.append(tier_rule)
        
        return rules
    
    def _path_matches(self, request_path: str, rule_paths: List[str]) -> bool:
        """Check if request path matches any rule paths"""
        for rule_path in rule_paths:
            if request_path.startswith(rule_path):
                return True
        return False
    
    async def _check_rate_limits(
        self,
        request: Request,
        context: Dict[str, Any],
        rules: List[RateLimitRule]
    ) -> None:
        """Check all applicable rate limit rules"""
        current_time = context["timestamp"]
        
        for rule in rules:
            # Check exemptions
            if self._is_exempt(context, rule):
                continue
            
            # Generate rate limit key
            key = self._generate_rate_limit_key(context, rule)
            
            try:
                # Check rate limit
                allowed, metadata = await self.storage.check_rate_limit(
                    key=key,
                    rule=rule,
                    current_time=current_time
                )
                
                if not allowed:
                    # Calculate retry after time
                    retry_after = self._calculate_retry_after(metadata)
                    
                    # Generate rate limit headers
                    headers = self._generate_rate_limit_headers(metadata, rule)
                    
                    # Custom error message
                    message = rule.custom_error_message or f"Rate limit exceeded for {rule.name}"
                    
                    raise RateLimitExceeded(
                        message=message,
                        retry_after=retry_after,
                        headers=headers
                    )
                    
            except RateLimitStorageError as e:
                logger.error("Rate limit storage error", rule=rule.name, error=str(e))
                if self.config.strict_mode:
                    raise HTTPException(
                        status_code=500,
                        detail="Rate limiting service unavailable"
                    )
    
    def _is_exempt(self, context: Dict[str, Any], rule: RateLimitRule) -> bool:
        """Check if request is exempt from rate limiting"""
        # Check IP exemptions
        client_ip = context.get("client_ip")
        if client_ip and client_ip in rule.exempt_ips:
            return True
        
        # Check user exemptions
        user_id = context.get("user_id")
        if user_id and user_id in rule.exempt_users:
            return True
        
        # Check user role exemptions
        user_role = context.get("user_role")
        if rule.user_roles and user_role not in rule.user_roles:
            return True
        
        return False
    
    def _generate_rate_limit_key(self, context: Dict[str, Any], rule: RateLimitRule) -> str:
        """Generate rate limit key based on rule scope"""
        key_parts = [rule.name]
        
        if rule.scope == RateLimitScope.GLOBAL:
            key_parts.append("global")
        elif rule.scope == RateLimitScope.PER_IP:
            key_parts.append(f"ip:{context['client_ip']}")
        elif rule.scope == RateLimitScope.PER_USER:
            user_id = context.get("user_id") or context["client_ip"]
            key_parts.append(f"user:{user_id}")
        elif rule.scope == RateLimitScope.PER_HOTEL:
            hotel_id = context.get("hotel_id") or "no_hotel"
            key_parts.append(f"hotel:{hotel_id}")
        elif rule.scope == RateLimitScope.PER_ENDPOINT:
            key_parts.append(f"endpoint:{context['path']}")
        elif rule.scope == RateLimitScope.COMBINED:
            # Combine multiple identifiers
            user_id = context.get("user_id") or context["client_ip"]
            hotel_id = context.get("hotel_id") or "no_hotel"
            key_parts.extend([f"user:{user_id}", f"hotel:{hotel_id}", f"endpoint:{context['path']}"])
        
        return ":".join(key_parts)
    
    async def _increment_counters(
        self,
        context: Dict[str, Any],
        rules: List[RateLimitRule]
    ) -> None:
        """Increment rate limit counters after successful request"""
        current_time = context["timestamp"]
        
        for rule in rules:
            if self._is_exempt(context, rule):
                continue
            
            key = self._generate_rate_limit_key(context, rule)
            
            try:
                await self.storage.increment_counter(
                    key=key,
                    rule=rule,
                    current_time=current_time
                )
            except RateLimitStorageError as e:
                logger.error("Failed to increment rate limit counter", rule=rule.name, error=str(e))
    
    async def _add_rate_limit_headers(
        self,
        response: Response,
        context: Dict[str, Any],
        rules: List[RateLimitRule]
    ) -> None:
        """Add rate limit headers to response"""
        if not self.config.include_rate_limit_headers:
            return
        
        # Find the most restrictive rule for headers
        most_restrictive_rule = None
        min_remaining = float('inf')
        
        for rule in rules:
            if self._is_exempt(context, rule):
                continue
            
            key = self._generate_rate_limit_key(context, rule)
            
            try:
                allowed, metadata = await self.storage.check_rate_limit(
                    key=key,
                    rule=rule,
                    current_time=context["timestamp"]
                )
                
                # Find rule with minimum remaining requests
                for window, check_meta in metadata.get("checks", {}).items():
                    remaining = check_meta.get("remaining", 0)
                    if remaining < min_remaining:
                        min_remaining = remaining
                        most_restrictive_rule = (rule, check_meta)
                        
            except RateLimitStorageError:
                continue
        
        # Add headers based on most restrictive rule
        if most_restrictive_rule:
            rule, meta = most_restrictive_rule
            headers = self._generate_rate_limit_headers({"checks": {"current": meta}}, rule)
            
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value
    
    def _generate_rate_limit_headers(
        self,
        metadata: Dict[str, Any],
        rule: RateLimitRule
    ) -> Dict[str, str]:
        """Generate rate limit headers"""
        headers = {}
        
        # Get the first available check metadata
        checks = metadata.get("checks", {})
        if checks:
            check_meta = next(iter(checks.values()))
            
            headers[self.config.header_names["limit"]] = str(check_meta.get("limit", 0))
            headers[self.config.header_names["remaining"]] = str(check_meta.get("remaining", 0))
            headers[self.config.header_names["reset"]] = str(int(check_meta.get("reset_time", 0)))
        
        return headers
    
    def _calculate_retry_after(self, metadata: Dict[str, Any]) -> int:
        """Calculate retry after time in seconds"""
        checks = metadata.get("checks", {})
        if checks:
            # Use the shortest reset time
            reset_times = [
                check.get("reset_time", 0) - time.time()
                for check in checks.values()
                if check.get("reset_time")
            ]
            if reset_times:
                return max(1, int(min(reset_times)))
        
        return 60  # Default 1 minute
    
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


# Convenience function to add rate limiting middleware
def add_comprehensive_rate_limiting(
    app,
    environment: str = "production",
    storage_backend: str = "redis"
) -> None:
    """
    Add comprehensive rate limiting middleware to FastAPI app
    
    Args:
        app: FastAPI application
        environment: Environment configuration to use
        storage_backend: Storage backend ("redis" or "memory")
    """
    app.add_middleware(
        ComprehensiveRateLimiter,
        environment=environment,
        storage_backend=storage_backend
    )
    
    logger.info(
        "Comprehensive rate limiting middleware added",
        environment=environment,
        storage_backend=storage_backend
    )


# Export main classes and functions
__all__ = [
    'ComprehensiveRateLimiter',
    'RateLimitExceeded',
    'add_comprehensive_rate_limiting'
]
