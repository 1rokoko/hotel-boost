"""
Tenant context middleware for multi-tenant Row Level Security
"""

import uuid
from typing import Optional, Callable, Dict, Any
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

from app.core.tenant import TenantContext, TenantManager
from app.core.logging import get_logger
from app.database import get_db_session

logger = get_logger(__name__)

class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to set tenant context for Row Level Security
    
    This middleware extracts the tenant ID from the request and sets it
    in the context for use by the database session.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        tenant_header: str = "X-Tenant-ID",
        require_tenant: bool = True,
        excluded_paths: Optional[list] = None
    ):
        """
        Initialize tenant context middleware
        
        Args:
            app: ASGI application
            tenant_header: Header name containing tenant ID
            require_tenant: Whether tenant ID is required for all requests
            excluded_paths: List of paths that don't require tenant context
        """
        super().__init__(app)
        self.tenant_header = tenant_header
        self.require_tenant = require_tenant
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and set tenant context
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        # Check if path is excluded from tenant requirements
        if self._is_excluded_path(request.url.path):
            return await call_next(request)
        
        # Extract tenant ID from request
        tenant_id = self._extract_tenant_id(request)
        
        # Validate tenant ID if required
        if self.require_tenant and not tenant_id:
            return self._create_error_response(
                "Tenant ID is required",
                status.HTTP_400_BAD_REQUEST
            )
        
        # Set tenant context if tenant ID is provided
        if tenant_id:
            try:
                # Validate tenant ID format
                tenant_uuid = uuid.UUID(tenant_id)
                
                # Set tenant context
                TenantContext.set_tenant_id(tenant_uuid)
                
                # Add tenant ID to request state for access in handlers
                request.state.tenant_id = tenant_uuid
                
                logger.debug(f"Tenant context set for request: {tenant_uuid}")
                
            except ValueError:
                return self._create_error_response(
                    "Invalid tenant ID format",
                    status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Failed to set tenant context: {str(e)}")
                return self._create_error_response(
                    "Failed to set tenant context",
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        try:
            # Process request
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Request processing failed: {str(e)}")
            raise
            
        finally:
            # Clear tenant context after request
            if tenant_id:
                TenantContext.clear_tenant_id()
                logger.debug("Tenant context cleared")
    
    def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """
        Extract tenant ID from request
        
        Args:
            request: HTTP request
            
        Returns:
            Optional[str]: Tenant ID or None
        """
        # Try header first
        tenant_id = request.headers.get(self.tenant_header)
        
        # Try query parameter as fallback
        if not tenant_id:
            tenant_id = request.query_params.get("tenant_id")
        
        # Try path parameter as fallback (for REST APIs)
        if not tenant_id and hasattr(request, "path_params"):
            tenant_id = request.path_params.get("tenant_id")
        
        return tenant_id
    
    def _is_excluded_path(self, path: str) -> bool:
        """
        Check if path is excluded from tenant requirements
        
        Args:
            path: Request path
            
        Returns:
            bool: True if path is excluded
        """
        return any(path.startswith(excluded) for excluded in self.excluded_paths)
    
    def _create_error_response(self, message: str, status_code: int) -> JSONResponse:
        """
        Create error response
        
        Args:
            message: Error message
            status_code: HTTP status code
            
        Returns:
            JSONResponse: Error response
        """
        return JSONResponse(
            status_code=status_code,
            content={
                "error": "Tenant Context Error",
                "message": message,
                "status_code": status_code
            }
        )

class DatabaseTenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to set tenant context in database sessions
    
    This middleware ensures that database sessions have the correct
    tenant context set for Row Level Security.
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize database tenant middleware
        
        Args:
            app: ASGI application
        """
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and set database tenant context
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        # Get tenant ID from request state (set by TenantContextMiddleware)
        tenant_id = getattr(request.state, 'tenant_id', None)
        
        if tenant_id:
            # Set database session tenant context
            try:
                async with get_db_session() as session:
                    await TenantManager.set_session_tenant(session, tenant_id)
                    
                    # Store session in request state for use in handlers
                    request.state.db_session = session
                    
                    try:
                        response = await call_next(request)
                        return response
                    finally:
                        # Clear session tenant context
                        await TenantManager.clear_session_tenant(session)
                        
            except Exception as e:
                logger.error(f"Database tenant context error: {str(e)}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": "Database Tenant Error",
                        "message": "Failed to set database tenant context"
                    }
                )
        else:
            # No tenant context, proceed normally
            return await call_next(request)

def get_current_tenant_id(request: Request) -> Optional[uuid.UUID]:
    """
    Get current tenant ID from request
    
    Args:
        request: HTTP request
        
    Returns:
        Optional[uuid.UUID]: Current tenant ID or None
    """
    return getattr(request.state, 'tenant_id', None)

def require_tenant_context(request: Request) -> uuid.UUID:
    """
    Require tenant context and return tenant ID
    
    Args:
        request: HTTP request
        
    Returns:
        uuid.UUID: Current tenant ID
        
    Raises:
        HTTPException: If no tenant context is set
    """
    tenant_id = get_current_tenant_id(request)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context is required for this operation"
        )
    return tenant_id

class TenantValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate tenant access and permissions
    
    This middleware validates that the tenant exists and is active.
    """
    
    def __init__(self, app: ASGIApp, validate_tenant: bool = True):
        """
        Initialize tenant validation middleware
        
        Args:
            app: ASGI application
            validate_tenant: Whether to validate tenant existence
        """
        super().__init__(app)
        self.validate_tenant = validate_tenant
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and validate tenant
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        tenant_id = getattr(request.state, 'tenant_id', None)
        
        if tenant_id and self.validate_tenant:
            try:
                # Validate tenant exists and is active
                async with get_db_session() as session:
                    from app.models.hotel import Hotel
                    
                    # Query hotel to validate tenant
                    result = await session.execute(
                        "SELECT id, is_active FROM hotels WHERE id = $1",
                        [tenant_id]
                    )
                    hotel = result.fetchone()
                    
                    if not hotel:
                        return JSONResponse(
                            status_code=status.HTTP_404_NOT_FOUND,
                            content={
                                "error": "Tenant Not Found",
                                "message": f"Tenant {tenant_id} does not exist"
                            }
                        )
                    
                    if not hotel.is_active:
                        return JSONResponse(
                            status_code=status.HTTP_403_FORBIDDEN,
                            content={
                                "error": "Tenant Inactive",
                                "message": f"Tenant {tenant_id} is not active"
                            }
                        )
                    
                    # Store hotel info in request state
                    request.state.hotel = hotel
                    
            except Exception as e:
                logger.error(f"Tenant validation error: {str(e)}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": "Tenant Validation Error",
                        "message": "Failed to validate tenant"
                    }
                )
        
        return await call_next(request)

# Convenience function to add all tenant middlewares
def add_tenant_middlewares(app: ASGIApp, **kwargs) -> ASGIApp:
    """
    Add all tenant-related middlewares to the application
    
    Args:
        app: ASGI application
        **kwargs: Additional configuration for middlewares
        
    Returns:
        ASGIApp: Application with tenant middlewares added
    """
    # Add middlewares in reverse order (they are applied in LIFO order)
    app.add_middleware(TenantValidationMiddleware, **kwargs.get('validation', {}))
    app.add_middleware(DatabaseTenantMiddleware)
    app.add_middleware(TenantContextMiddleware, **kwargs.get('context', {}))
    
    return app
