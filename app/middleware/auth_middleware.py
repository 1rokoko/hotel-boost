"""
Authentication middleware for user authentication

This middleware handles JWT token validation and user context management
for general user authentication (separate from admin authentication).
"""

import time
import uuid
from typing import Callable, List, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.security import TokenError, AuthenticationError
from app.utils.jwt_handler import JWTHandler
from app.models.user import User
from app.database import get_db

logger = structlog.get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for user authentication and authorization
    
    Handles JWT token validation and user context management for user endpoints.
    """
    
    def __init__(
        self,
        app,
        excluded_paths: Optional[List[str]] = None,
        auth_path_prefix: str = "/api/v1",
        require_auth_paths: Optional[List[str]] = None
    ):
        """
        Initialize auth middleware
        
        Args:
            app: FastAPI application
            excluded_paths: Paths to exclude from authentication
            auth_path_prefix: Prefix for paths that may require authentication
            require_auth_paths: Specific paths that require authentication
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/password-reset",
            "/api/v1/health",
            "/api/v1/admin",
            "/api/v1/hotels",
            "/api/v1/triggers",
            "/api/v1/templates",
            "/api/v1/demo",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico"
        ]
        self.auth_path_prefix = auth_path_prefix
        self.require_auth_paths = require_auth_paths or [
            "/api/v1/auth/me",
            "/api/v1/auth/logout",
            "/api/v1/auth/password-change",
            "/api/v1/conversations",
            "/api/v1/hotels",
            "/api/v1/triggers",
            "/api/v1/templates"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through authentication middleware
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        start_time = time.time()
        
        # Check if this path requires authentication
        if not self._requires_authentication(request.url.path):
            return await call_next(request)
        
        # Check if path is excluded from authentication
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        try:
            # Extract and validate token
            user = await self._authenticate_request(request)
            
            # Add user to request state
            request.state.user = user
            request.state.user_id = user.id
            request.state.user_role = user.role
            request.state.user_permissions = user.permissions
            request.state.user_hotel_id = user.hotel_id
            
            # Process request
            response = await call_next(request)
            
            # Log successful request
            processing_time = time.time() - start_time
            await self._log_request(
                request=request,
                user=user,
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
                user=None,
                status_code=e.status_code,
                processing_time=processing_time,
                success=False,
                error=str(e.detail)
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
            await self._log_request(
                request=request,
                user=None,
                status_code=500,
                processing_time=processing_time,
                success=False,
                error=str(e)
            )
            
            logger.error("Unexpected auth middleware error", error=str(e))
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "message": "Authentication processing failed",
                    "error_code": "AUTH_ERROR"
                }
            )
    
    def _requires_authentication(self, path: str) -> bool:
        """
        Check if path requires authentication
        
        Args:
            path: Request path
            
        Returns:
            bool: True if authentication is required
        """
        # Check if path starts with auth prefix
        if not path.startswith(self.auth_path_prefix):
            return False
        
        # Check specific paths that require auth
        for auth_path in self.require_auth_paths:
            if path.startswith(auth_path):
                return True
        
        return False
    
    async def _authenticate_request(self, request: Request) -> User:
        """
        Authenticate user request
        
        Args:
            request: HTTP request
            
        Returns:
            User: Authenticated user
            
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
        
        # Validate token
        try:
            token_payload = JWTHandler.validate_access_token(token)
            user_id = uuid.UUID(token_payload["sub"])
        except TokenError as e:
            logger.warning("Token validation failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID in token"
            )
        
        # Get user from database
        try:
            # Get database session
            async for db in get_db():
                stmt = select(User).where(User.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                break
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            
            # Check if user is active
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is deactivated"
                )
            
            # Check if account is locked
            if user.is_locked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is locked"
                )
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Database error during authentication", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication failed"
            )
    
    async def _log_request(
        self,
        request: Request,
        user: Optional[User],
        status_code: int,
        processing_time: float,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Log authentication request
        
        Args:
            request: HTTP request
            user: Authenticated user (if any)
            status_code: Response status code
            processing_time: Request processing time
            success: Whether authentication was successful
            error: Error message (if any)
        """
        try:
            log_data = {
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "processing_time": round(processing_time, 3),
                "success": success,
                "user_agent": request.headers.get("User-Agent"),
                "ip_address": request.client.host if request.client else None
            }
            
            if user:
                log_data.update({
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "user_role": user.role.value if user.role else None
                })
            
            if error:
                log_data["error"] = error
            
            if success:
                logger.info("Auth request processed", **log_data)
            else:
                logger.warning("Auth request failed", **log_data)
                
        except Exception as e:
            logger.error("Failed to log auth request", error=str(e))
