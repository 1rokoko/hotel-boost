"""
Enhanced tenant middleware for hotel operations
"""

import uuid
from typing import Optional, Callable, Dict, Any, List
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

from app.core.tenant_context import (
    HotelTenantContext,
    HotelTenantManager,
    HotelTenantFilter
)
from app.database import get_db_session
from app.models.hotel import Hotel
from app.core.logging import get_logger

logger = get_logger(__name__)


class HotelTenantMiddleware(BaseHTTPMiddleware):
    """
    Enhanced middleware for hotel tenant context management
    
    This middleware extends the basic tenant functionality with hotel-specific
    context management and permissions.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        hotel_header: str = "X-Hotel-ID",
        require_hotel: bool = True,
        excluded_paths: Optional[List[str]] = None,
        auto_load_context: bool = True
    ):
        """
        Initialize hotel tenant middleware
        
        Args:
            app: ASGI application
            hotel_header: Header name containing hotel ID
            require_hotel: Whether hotel ID is required for all requests
            excluded_paths: List of paths that don't require hotel context
            auto_load_context: Whether to automatically load hotel context from database
        """
        super().__init__(app)
        self.hotel_header = hotel_header
        self.require_hotel = require_hotel
        self.auto_load_context = auto_load_context
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/api/v1/health"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and set hotel tenant context
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        # Check if path is excluded from hotel requirements
        if self._is_excluded_path(request.url.path):
            return await call_next(request)
        
        # Extract hotel ID from request
        hotel_id = self._extract_hotel_id(request)
        
        # Validate hotel ID if required
        if self.require_hotel and not hotel_id:
            return self._create_error_response(
                "Hotel ID is required",
                status.HTTP_400_BAD_REQUEST,
                {"error_code": "HOTEL_ID_REQUIRED"}
            )
        
        # Set hotel context if hotel ID is provided
        if hotel_id:
            try:
                # Validate hotel ID format
                hotel_uuid = uuid.UUID(hotel_id)
                
                # Load hotel context if auto_load_context is enabled
                hotel_context = None
                if self.auto_load_context:
                    with get_db_session() as db:
                        hotel_context = HotelTenantManager.load_hotel_context(db, hotel_uuid)
                        
                        if not hotel_context:
                            return self._create_error_response(
                                "Hotel not found",
                                status.HTTP_404_NOT_FOUND,
                                {"error_code": "HOTEL_NOT_FOUND", "hotel_id": hotel_id}
                            )
                        
                        # Check if hotel is active
                        if not hotel_context.get("is_active", False):
                            return self._create_error_response(
                                "Hotel is not active",
                                status.HTTP_403_FORBIDDEN,
                                {"error_code": "HOTEL_INACTIVE", "hotel_id": hotel_id}
                            )
                        
                        # Set database context for RLS
                        HotelTenantManager.set_database_hotel_context(db, hotel_uuid)
                
                # Set application context
                if hotel_context:
                    HotelTenantContext.set_hotel_context(
                        hotel_id=hotel_context["hotel_id"],
                        hotel_name=hotel_context["hotel_name"],
                        is_active=hotel_context["is_active"],
                        permissions=HotelTenantManager.get_hotel_permissions(hotel_context)
                    )
                else:
                    # Minimal context if auto_load_context is disabled
                    HotelTenantContext.set_hotel_context(
                        hotel_id=hotel_uuid,
                        hotel_name="Unknown",
                        is_active=True
                    )
                
                # Add hotel context to request state for access in handlers
                request.state.hotel_id = hotel_uuid
                request.state.hotel_context = hotel_context
                
                logger.debug(
                    "Hotel context set for request",
                    hotel_id=str(hotel_uuid),
                    hotel_name=hotel_context.get("hotel_name") if hotel_context else "Unknown",
                    path=request.url.path
                )
                
            except ValueError:
                return self._create_error_response(
                    "Invalid hotel ID format",
                    status.HTTP_400_BAD_REQUEST,
                    {"error_code": "INVALID_HOTEL_ID", "hotel_id": hotel_id}
                )
            except Exception as e:
                logger.error(
                    "Failed to set hotel context",
                    hotel_id=hotel_id,
                    error=str(e)
                )
                return self._create_error_response(
                    "Failed to set hotel context",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    {"error_code": "CONTEXT_ERROR"}
                )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Add hotel context to response headers for debugging
            if hotel_id and hasattr(request.state, 'hotel_context'):
                context = request.state.hotel_context
                if context:
                    response.headers["X-Hotel-Name"] = context.get("hotel_name", "Unknown")
                    response.headers["X-Hotel-Active"] = str(context.get("is_active", False))
            
            return response
            
        except Exception as e:
            logger.error(
                "Request processing failed",
                hotel_id=hotel_id,
                path=request.url.path,
                error=str(e)
            )
            raise
            
        finally:
            # Clear hotel context after request
            if hotel_id:
                HotelTenantContext.clear_hotel_context()
                logger.debug("Hotel context cleared")
    
    def _extract_hotel_id(self, request: Request) -> Optional[str]:
        """
        Extract hotel ID from request
        
        Args:
            request: HTTP request
            
        Returns:
            Optional[str]: Hotel ID or None
        """
        # Try header first
        hotel_id = request.headers.get(self.hotel_header)
        
        # Try query parameter as fallback
        if not hotel_id:
            hotel_id = request.query_params.get("hotel_id")
        
        # Try path parameter as fallback (for REST APIs)
        if not hotel_id and hasattr(request, "path_params"):
            hotel_id = request.path_params.get("hotel_id")
        
        return hotel_id
    
    def _is_excluded_path(self, path: str) -> bool:
        """
        Check if path is excluded from hotel requirements
        
        Args:
            path: Request path
            
        Returns:
            bool: True if path is excluded
        """
        return any(path.startswith(excluded) for excluded in self.excluded_paths)
    
    def _create_error_response(
        self,
        message: str,
        status_code: int,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """
        Create error response
        
        Args:
            message: Error message
            status_code: HTTP status code
            extra_data: Additional data to include
            
        Returns:
            JSONResponse: Error response
        """
        content = {
            "error": "Hotel Tenant Error",
            "message": message,
            "status_code": status_code
        }
        
        if extra_data:
            content.update(extra_data)
        
        return JSONResponse(
            status_code=status_code,
            content=content
        )


class HotelPermissionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing hotel-specific permissions
    """
    
    def __init__(
        self,
        app: ASGIApp,
        permission_map: Optional[Dict[str, List[str]]] = None
    ):
        """
        Initialize hotel permission middleware
        
        Args:
            app: ASGI application
            permission_map: Map of path patterns to required permissions
        """
        super().__init__(app)
        self.permission_map = permission_map or {
            "/api/v1/hotels/*/messages": ["can_send_messages"],
            "/api/v1/hotels/*/settings": ["can_modify_settings"],
            "/api/v1/hotels/*/analytics": ["can_view_analytics"],
            "/api/v1/hotels/*/export": ["can_export_data"]
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and check permissions
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        # Check if permissions are required for this path
        required_permissions = self._get_required_permissions(request.url.path)
        
        if required_permissions:
            try:
                # Get hotel context
                hotel_context = HotelTenantContext.get_hotel_context()
                
                if not hotel_context:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "Permission Denied",
                            "message": "No hotel context available",
                            "error_code": "NO_HOTEL_CONTEXT"
                        }
                    )
                
                # Validate permissions
                if not HotelTenantManager.validate_hotel_access(hotel_context, required_permissions):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "Permission Denied",
                            "message": f"Hotel does not have required permissions: {required_permissions}",
                            "error_code": "INSUFFICIENT_PERMISSIONS",
                            "required_permissions": required_permissions
                        }
                    )
                
                logger.debug(
                    "Hotel permissions validated",
                    hotel_id=str(hotel_context.get("hotel_id")),
                    required_permissions=required_permissions,
                    path=request.url.path
                )
                
            except Exception as e:
                logger.error(
                    "Permission validation failed",
                    path=request.url.path,
                    required_permissions=required_permissions,
                    error=str(e)
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": "Permission Validation Error",
                        "message": "Failed to validate permissions",
                        "error_code": "PERMISSION_VALIDATION_ERROR"
                    }
                )
        
        return await call_next(request)
    
    def _get_required_permissions(self, path: str) -> List[str]:
        """
        Get required permissions for path
        
        Args:
            path: Request path
            
        Returns:
            List[str]: Required permissions
        """
        for pattern, permissions in self.permission_map.items():
            # Simple pattern matching (could be enhanced with regex)
            if self._path_matches_pattern(path, pattern):
                return permissions
        
        return []
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if path matches pattern
        
        Args:
            path: Request path
            pattern: Pattern to match
            
        Returns:
            bool: True if path matches pattern
        """
        # Simple wildcard matching
        pattern_parts = pattern.split('*')
        
        if len(pattern_parts) == 1:
            return path == pattern
        
        # Check if path starts with first part and ends with last part
        if not path.startswith(pattern_parts[0]):
            return False
        
        if pattern_parts[-1] and not path.endswith(pattern_parts[-1]):
            return False
        
        return True


# Helper functions for adding middleware to FastAPI app
def add_hotel_tenant_middlewares(
    app,
    hotel_header: str = "X-Hotel-ID",
    require_hotel: bool = True,
    excluded_paths: Optional[List[str]] = None,
    enable_permissions: bool = True,
    permission_map: Optional[Dict[str, List[str]]] = None
):
    """
    Add hotel tenant middlewares to FastAPI app
    
    Args:
        app: FastAPI application
        hotel_header: Header name containing hotel ID
        require_hotel: Whether hotel ID is required
        excluded_paths: Paths excluded from hotel requirements
        enable_permissions: Whether to enable permission middleware
        permission_map: Map of paths to required permissions
    """
    # Add permission middleware first (runs last)
    if enable_permissions:
        app.add_middleware(
            HotelPermissionMiddleware,
            permission_map=permission_map
        )
    
    # Add hotel tenant middleware
    app.add_middleware(
        HotelTenantMiddleware,
        hotel_header=hotel_header,
        require_hotel=require_hotel,
        excluded_paths=excluded_paths
    )
    
    logger.info(
        "Hotel tenant middlewares added",
        hotel_header=hotel_header,
        require_hotel=require_hotel,
        enable_permissions=enable_permissions
    )
