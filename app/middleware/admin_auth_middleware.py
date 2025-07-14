"""
Admin authentication and authorization middleware
"""

import uuid
import time
from typing import Dict, Any, Optional, List, Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import structlog

from app.core.admin_security import AdminSecurity, AdminTokenError, AdminAuthorizationError
from app.models.admin_user import AdminPermission, AdminRole
from app.models.admin_audit_log import AuditAction, AuditSeverity
from app.utils.admin_audit import AdminAuditLogger

logger = structlog.get_logger(__name__)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for admin authentication and authorization
    
    Handles JWT token validation and permission checking for admin endpoints.
    """
    
    def __init__(
        self,
        app,
        excluded_paths: Optional[List[str]] = None,
        admin_path_prefix: str = "/api/v1/admin"
    ):
        """
        Initialize admin auth middleware
        
        Args:
            app: FastAPI application
            excluded_paths: Paths to exclude from authentication
            admin_path_prefix: Prefix for admin paths
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/api/v1/admin/auth/login",
            "/api/v1/admin/auth/refresh",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health"
        ]
        self.admin_path_prefix = admin_path_prefix
        self.security = HTTPBearer(auto_error=False)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through admin authentication middleware
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        start_time = time.time()
        
        # Check if this is an admin path
        if not request.url.path.startswith(self.admin_path_prefix):
            return await call_next(request)
        
        # Check if path is excluded from authentication
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        try:
            # Extract and validate token
            admin_user = await self._authenticate_request(request)
            
            # Add admin user to request state
            request.state.admin_user = admin_user
            request.state.admin_user_id = admin_user.id
            request.state.admin_role = admin_user.role
            request.state.admin_permissions = admin_user.permissions
            request.state.admin_hotel_id = admin_user.hotel_id
            
            # Process request
            response = await call_next(request)
            
            # Log successful request
            processing_time = time.time() - start_time
            await self._log_request(
                request=request,
                admin_user=admin_user,
                status_code=response.status_code,
                processing_time=processing_time,
                success=True
            )
            
            return response
            
        except HTTPException as e:
            # Log failed request
            processing_time = time.time() - start_time
            await self._log_request(
                request=request,
                admin_user=None,
                status_code=e.status_code,
                processing_time=processing_time,
                success=False,
                error_message=e.detail
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "Authentication Failed",
                    "message": e.detail,
                    "error_code": "AUTH_FAILED"
                }
            )
        except Exception as e:
            # Log unexpected error
            processing_time = time.time() - start_time
            logger.error(
                "Admin auth middleware error",
                error=str(e),
                path=request.url.path,
                method=request.method,
                processing_time=processing_time
            )
            
            await self._log_request(
                request=request,
                admin_user=None,
                status_code=500,
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "message": "Authentication middleware error",
                    "error_code": "MIDDLEWARE_ERROR"
                }
            )
    
    async def _authenticate_request(self, request: Request):
        """
        Authenticate admin request
        
        Args:
            request: HTTP request
            
        Returns:
            AdminUser: Authenticated admin user
            
        Raises:
            HTTPException: If authentication fails
        """
        # Extract authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing"
            )
        
        # Parse Bearer token
        try:
            scheme, token = authorization.split(" ", 1)
            if scheme.lower() != "bearer":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization scheme"
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format"
            )
        
        # Verify token
        try:
            token_payload = AdminSecurity.verify_token(token, "access")
            user_id = uuid.UUID(token_payload["sub"])
        except AdminTokenError as e:
            logger.warning("Token verification failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Get user from database (this would need to be injected or accessed differently)
        # For now, we'll create a mock user from token data
        from app.models.admin_user import AdminUser, AdminRole
        
        # In a real implementation, you'd fetch from database
        # This is a simplified version for demonstration
        admin_user = AdminUser(
            id=user_id,
            email=token_payload.get("email"),
            username=token_payload.get("username"),
            role=AdminRole(token_payload.get("role", "viewer")),
            permissions=token_payload.get("permissions", []),
            hotel_id=uuid.UUID(token_payload["hotel_id"]) if token_payload.get("hotel_id") else None,
            is_active=True,
            is_verified=True
        )
        
        # Validate user status
        if not admin_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )
        
        return admin_user
    
    async def _log_request(
        self,
        request: Request,
        admin_user: Optional[Any],
        status_code: int,
        processing_time: float,
        success: bool,
        error_message: Optional[str] = None
    ):
        """
        Log admin request for audit purposes
        
        Args:
            request: HTTP request
            admin_user: Admin user (if authenticated)
            status_code: Response status code
            processing_time: Request processing time
            success: Whether request was successful
            error_message: Error message if failed
        """
        try:
            # Determine audit action based on request
            action = self._determine_audit_action(request)
            
            # Determine severity
            if not success:
                severity = AuditSeverity.HIGH if status_code >= 500 else AuditSeverity.MEDIUM
            else:
                severity = AuditSeverity.LOW
            
            # Create audit log entry
            audit_logger = AdminAuditLogger()
            await audit_logger.log_action(
                admin_user_id=admin_user.id if admin_user else None,
                action=action,
                description=f"{request.method} {request.url.path}",
                severity=severity,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "status_code": status_code,
                    "processing_time_ms": round(processing_time * 1000, 2)
                },
                success=success,
                error_message=error_message
            )
            
        except Exception as e:
            logger.error("Failed to log admin request", error=str(e))
    
    def _determine_audit_action(self, request: Request) -> AuditAction:
        """
        Determine audit action based on request
        
        Args:
            request: HTTP request
            
        Returns:
            AuditAction: Appropriate audit action
        """
        path = request.url.path.lower()
        method = request.method.upper()
        
        # Authentication actions
        if "auth" in path:
            if "login" in path:
                return AuditAction.LOGIN
            elif "logout" in path:
                return AuditAction.LOGOUT
            elif "password" in path:
                return AuditAction.PASSWORD_CHANGED
        
        # User management actions
        elif "users" in path:
            if method == "POST":
                return AuditAction.USER_CREATED
            elif method in ["PUT", "PATCH"]:
                return AuditAction.USER_UPDATED
            elif method == "DELETE":
                return AuditAction.USER_DELETED
        
        # Hotel management actions
        elif "hotels" in path:
            if method == "POST":
                return AuditAction.HOTEL_CREATED
            elif method in ["PUT", "PATCH"]:
                return AuditAction.HOTEL_UPDATED
            elif method == "DELETE":
                return AuditAction.HOTEL_DELETED
        
        # System settings actions
        elif "settings" in path:
            return AuditAction.SYSTEM_SETTINGS_CHANGED
        
        # Data export actions
        elif "export" in path or "reports" in path:
            return AuditAction.DATA_EXPORTED
        
        # Default to generic action
        return AuditAction.UNAUTHORIZED_ACCESS


class AdminPermissionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for admin permission checking
    
    Validates that authenticated admin users have required permissions
    for specific endpoints.
    """
    
    def __init__(
        self,
        app,
        permission_map: Optional[Dict[str, List[AdminPermission]]] = None
    ):
        """
        Initialize admin permission middleware
        
        Args:
            app: FastAPI application
            permission_map: Map of path patterns to required permissions
        """
        super().__init__(app)
        self.permission_map = permission_map or self._default_permission_map()
    
    def _default_permission_map(self) -> Dict[str, List[AdminPermission]]:
        """Get default permission mappings"""
        return {
            "/api/v1/admin/analytics": [AdminPermission.VIEW_ANALYTICS],
            "/api/v1/admin/users": [AdminPermission.MANAGE_HOTEL_USERS],
            "/api/v1/admin/settings": [AdminPermission.MANAGE_SYSTEM],
            "/api/v1/admin/reports": [AdminPermission.GENERATE_REPORTS],
            "/api/v1/admin/monitoring": [AdminPermission.VIEW_MONITORING],
            "/api/v1/admin/hotels": [AdminPermission.MANAGE_HOTELS]
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through permission middleware
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        # Check if admin user is authenticated
        admin_user = getattr(request.state, "admin_user", None)
        if not admin_user:
            return await call_next(request)
        
        # Check permissions for the requested path
        required_permissions = self._get_required_permissions(request.url.path)
        if required_permissions:
            try:
                for permission in required_permissions:
                    AdminSecurity.validate_admin_access(
                        admin_user=admin_user,
                        required_permission=permission
                    )
            except AdminAuthorizationError as e:
                logger.warning(
                    "Admin permission denied",
                    user_id=str(admin_user.id),
                    path=request.url.path,
                    required_permissions=[p.value for p in required_permissions],
                    user_permissions=admin_user.permissions,
                    error=str(e)
                )
                
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "Permission Denied",
                        "message": str(e),
                        "error_code": "INSUFFICIENT_PERMISSIONS",
                        "required_permissions": [p.value for p in required_permissions]
                    }
                )
        
        return await call_next(request)
    
    def _get_required_permissions(self, path: str) -> List[AdminPermission]:
        """
        Get required permissions for a path
        
        Args:
            path: Request path
            
        Returns:
            List[AdminPermission]: Required permissions
        """
        for pattern, permissions in self.permission_map.items():
            if path.startswith(pattern):
                return permissions
        return []
