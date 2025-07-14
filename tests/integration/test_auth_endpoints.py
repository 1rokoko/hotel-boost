"""
Integration tests for authentication endpoints

This module tests the authentication API endpoints including login, registration,
token refresh, and permission checking.
"""

import pytest
import uuid
from httpx import AsyncClient
from fastapi import status
from unittest.mock import patch, AsyncMock

from app.main import app
from app.models.user import User
from app.models.role import UserRole, UserPermission
from app.core.security import Security
from app.utils.jwt_handler import JWTHandler


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "role": UserRole.VIEWER,
        "hotel_id": None,
        "permissions": []
    }


@pytest.fixture
def sample_user(sample_user_data):
    """Sample user instance"""
    user = User(**sample_user_data)
    user.set_password("TestPassword123!")
    return user


@pytest.fixture
def auth_headers(sample_user_data):
    """Authentication headers with valid JWT token"""
    tokens = JWTHandler.create_user_tokens(sample_user_data)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


class TestAuthEndpoints:
    """Test cases for authentication endpoints"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, sample_user):
        """Test successful login"""
        with patch('app.services.auth_service.AuthService.authenticate_user') as mock_auth, \
             patch('app.services.auth_service.AuthService.create_access_token') as mock_token:
            
            # Mock authentication
            mock_auth.return_value = sample_user
            mock_token.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": sample_user.to_dict(),
                "session_id": "test_session_id"
            }
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "test@example.com",
                        "password": "TestPassword123!"
                    }
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"
            assert "user" in data
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        with patch('app.services.auth_service.AuthService.authenticate_user') as mock_auth:
            from app.core.security import AuthenticationError
            mock_auth.side_effect = AuthenticationError("Invalid email or password")
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "test@example.com",
                        "password": "wrongpassword"
                    }
                )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            data = response.json()
            assert "Invalid email or password" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_register_success(self):
        """Test successful user registration"""
        with patch('app.services.auth_service.AuthService.register_user') as mock_register:
            new_user = User(
                id=uuid.uuid4(),
                email="newuser@example.com",
                username="newuser",
                full_name="New User",
                role=UserRole.VIEWER
            )
            mock_register.return_value = new_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": "newuser@example.com",
                        "username": "newuser",
                        "full_name": "New User",
                        "password": "NewPassword123!",
                        "role": "viewer"
                    }
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["message"] == "User registered successfully"
            assert "user" in data
    
    @pytest.mark.asyncio
    async def test_register_weak_password(self):
        """Test registration with weak password"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "newuser@example.com",
                    "username": "newuser",
                    "full_name": "New User",
                    "password": "weak",
                    "role": "viewer"
                }
            )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "validation error" in str(data).lower()
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh"""
        with patch('app.services.auth_service.AuthService.refresh_token') as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new_access_token",
                "token_type": "bearer",
                "expires_in": 1800
            }
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/refresh",
                    json={
                        "refresh_token": "valid_refresh_token"
                    }
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self):
        """Test token refresh with invalid token"""
        with patch('app.services.auth_service.AuthService.refresh_token') as mock_refresh:
            from app.core.security import AuthenticationError
            mock_refresh.side_effect = AuthenticationError("Invalid refresh token")
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/refresh",
                    json={
                        "refresh_token": "invalid_refresh_token"
                    }
                )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_get_current_user_info(self, auth_headers, sample_user):
        """Test getting current user information"""
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/auth/me",
                    headers=auth_headers
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "user" in data
            assert "permissions" in data
            assert "session_info" in data
    
    @pytest.mark.asyncio
    async def test_get_current_user_info_unauthorized(self):
        """Test getting user info without authentication"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_check_permission_success(self, auth_headers, sample_user):
        """Test successful permission check"""
        sample_user.permissions = [UserPermission.VIEW_CONVERSATIONS.value]
        
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/check-permission",
                    headers=auth_headers,
                    json={
                        "permission": "view_conversations"
                    }
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["has_permission"] is True
            assert data["reason"] is None
    
    @pytest.mark.asyncio
    async def test_check_permission_denied(self, auth_headers, sample_user):
        """Test permission check with insufficient permissions"""
        sample_user.permissions = []  # No permissions
        
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/check-permission",
                    headers=auth_headers,
                    json={
                        "permission": "manage_system"
                    }
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["has_permission"] is False
            assert data["reason"] is not None
    
    @pytest.mark.asyncio
    async def test_check_permission_invalid_permission(self, auth_headers, sample_user):
        """Test permission check with invalid permission"""
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/check-permission",
                    headers=auth_headers,
                    json={
                        "permission": "invalid_permission"
                    }
                )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    @pytest.mark.asyncio
    async def test_get_user_permissions(self, auth_headers, sample_user):
        """Test getting user permissions summary"""
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/auth/permissions",
                    headers=auth_headers
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "user_id" in data
            assert "role" in data
            assert "all_permissions" in data
            assert "permission_count" in data
    
    @pytest.mark.asyncio
    async def test_validate_token_valid(self):
        """Test token validation with valid token"""
        # Create a valid token
        user_data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "username": "testuser",
            "role": "viewer",
            "hotel_id": None,
            "permissions": []
        }
        tokens = JWTHandler.create_user_tokens(user_data)
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/validate-token",
                json={
                    "token": tokens["access_token"],
                    "token_type": "access"
                }
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert "user_id" in data
        assert "expires_at" in data
    
    @pytest.mark.asyncio
    async def test_validate_token_invalid(self):
        """Test token validation with invalid token"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/validate-token",
                json={
                    "token": "invalid_token",
                    "token_type": "access"
                }
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert "reason" in data
    
    @pytest.mark.asyncio
    async def test_logout_success(self, auth_headers, sample_user):
        """Test successful logout"""
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/logout",
                    headers=auth_headers,
                    json={
                        "refresh_token": "test_refresh_token"
                    }
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["message"] == "Successfully logged out"
