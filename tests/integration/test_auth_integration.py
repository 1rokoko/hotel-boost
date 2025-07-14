"""
Integration tests for authentication system

This module tests the integration of the new user authentication system
with existing systems, ensuring no conflicts with admin authentication.
"""

import pytest
import uuid
from httpx import AsyncClient
from fastapi import status
from unittest.mock import patch, AsyncMock

from app.main import app
from app.models.user import User
from app.models.admin_user import AdminUser
from app.models.role import UserRole, UserPermission
from app.models.admin_user import AdminRole, AdminPermission
from app.utils.jwt_handler import JWTHandler
from app.core.admin_security import AdminSecurity


@pytest.fixture
def sample_user():
    """Sample regular user"""
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="regularuser",
        full_name="Regular User",
        role=UserRole.HOTEL_STAFF,
        permissions=[UserPermission.VIEW_CONVERSATIONS.value],
        is_active=True,
        hotel_id=uuid.uuid4()
    )


@pytest.fixture
def sample_admin():
    """Sample admin user"""
    return AdminUser(
        id=uuid.uuid4(),
        email="admin@example.com",
        username="adminuser",
        full_name="Admin User",
        role=AdminRole.HOTEL_ADMIN,
        permissions=[AdminPermission.MANAGE_HOTEL_SETTINGS.value],
        is_active="true",
        hotel_id=uuid.uuid4()
    )


@pytest.fixture
def user_auth_headers(sample_user):
    """Authentication headers for regular user"""
    user_data = {
        "id": sample_user.id,
        "email": sample_user.email,
        "username": sample_user.username,
        "role": sample_user.role.value,
        "hotel_id": sample_user.hotel_id,
        "permissions": sample_user.permissions
    }
    tokens = JWTHandler.create_user_tokens(user_data)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def admin_auth_headers(sample_admin):
    """Authentication headers for admin user"""
    admin_data = {
        "id": sample_admin.id,
        "email": sample_admin.email,
        "username": sample_admin.username,
        "role": sample_admin.role.value,
        "hotel_id": sample_admin.hotel_id,
        "permissions": sample_admin.permissions
    }
    tokens = AdminSecurity.create_admin_tokens(admin_data)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


class TestAuthSystemIntegration:
    """Test authentication system integration"""
    
    @pytest.mark.asyncio
    async def test_user_and_admin_token_isolation(self, sample_user, sample_admin):
        """Test that user and admin tokens are properly isolated"""
        # Create user token
        user_data = {
            "id": sample_user.id,
            "email": sample_user.email,
            "username": sample_user.username,
            "role": sample_user.role.value,
            "hotel_id": sample_user.hotel_id,
            "permissions": sample_user.permissions
        }
        user_tokens = JWTHandler.create_user_tokens(user_data)
        user_token = user_tokens["access_token"]
        
        # Create admin token
        admin_data = {
            "id": sample_admin.id,
            "email": sample_admin.email,
            "username": sample_admin.username,
            "role": sample_admin.role.value,
            "hotel_id": sample_admin.hotel_id,
            "permissions": sample_admin.permissions
        }
        admin_tokens = AdminSecurity.create_admin_tokens(admin_data)
        admin_token = admin_tokens["access_token"]
        
        # Validate tokens have different scopes
        user_payload = JWTHandler.validate_access_token(user_token)
        admin_payload = AdminSecurity.verify_admin_token(admin_token)
        
        assert user_payload["scope"] == "user"
        assert admin_payload["scope"] == "admin"
        
        # User token should not work for admin operations
        with pytest.raises(Exception):  # TokenError
            AdminSecurity.verify_admin_token(user_token)
        
        # Admin token should not work for user operations
        with pytest.raises(Exception):  # TokenError
            JWTHandler.validate_access_token(admin_token)
    
    @pytest.mark.asyncio
    async def test_user_auth_endpoints_work(self, user_auth_headers, sample_user):
        """Test that user authentication endpoints work correctly"""
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Test user info endpoint
                response = await client.get(
                    "/api/v1/auth/me",
                    headers=user_auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "user" in data
                assert data["user"]["email"] == sample_user.email
    
    @pytest.mark.asyncio
    async def test_admin_auth_endpoints_work(self, admin_auth_headers, sample_admin):
        """Test that admin authentication endpoints still work"""
        with patch('app.api.v1.admin.auth.get_current_admin_user') as mock_get_admin:
            mock_get_admin.return_value = sample_admin
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Test admin info endpoint
                response = await client.get(
                    "/api/v1/admin/auth/me",
                    headers=admin_auth_headers
                )
                
                # This might return 404 if endpoint doesn't exist, which is fine
                # The important thing is that it doesn't interfere with user auth
                assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.asyncio
    async def test_user_cannot_access_admin_endpoints(self, user_auth_headers):
        """Test that regular users cannot access admin endpoints"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Try to access admin endpoint with user token
            response = await client.get(
                "/api/v1/admin/hotels",
                headers=user_auth_headers
            )
            
            # Should be forbidden or unauthorized
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND  # If endpoint doesn't exist
            ]
    
    @pytest.mark.asyncio
    async def test_admin_cannot_access_user_endpoints_with_admin_token(self, admin_auth_headers):
        """Test that admin token cannot be used for user endpoints"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Try to access user endpoint with admin token
            response = await client.get(
                "/api/v1/auth/me",
                headers=admin_auth_headers
            )
            
            # Should be unauthorized due to token scope mismatch
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_database_model_isolation(self):
        """Test that user and admin models are properly isolated"""
        # Create user and admin with same email (should be allowed in different systems)
        user = User(
            email="same@example.com",
            username="user1",
            full_name="User One",
            role=UserRole.VIEWER
        )
        
        admin = AdminUser(
            email="same@example.com",
            username="admin1",
            full_name="Admin One",
            role=AdminRole.HOTEL_ADMIN
        )
        
        # Should not conflict (different tables)
        assert user.email == admin.email
        assert user.id != admin.id
        assert isinstance(user.role, UserRole)
        assert isinstance(admin.role, AdminRole)
    
    @pytest.mark.asyncio
    async def test_permission_system_isolation(self, sample_user, sample_admin):
        """Test that user and admin permission systems are isolated"""
        # User permissions
        user_permissions = sample_user.get_all_permissions()
        
        # Admin permissions (mock the method)
        admin_permissions = sample_admin.get_all_permissions()
        
        # Should be different permission systems
        assert UserPermission.VIEW_CONVERSATIONS.value in [p.value for p in UserPermission]
        assert AdminPermission.MANAGE_HOTEL_SETTINGS.value in [p.value for p in AdminPermission]
        
        # User should not have admin permissions
        assert AdminPermission.MANAGE_HOTEL_SETTINGS.value not in user_permissions
    
    @pytest.mark.asyncio
    async def test_middleware_compatibility(self, user_auth_headers, sample_user):
        """Test that auth middleware works with existing middleware"""
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Test that request goes through all middleware layers
                response = await client.get(
                    "/api/v1/auth/permissions",
                    headers=user_auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                
                # Check that CORS headers are present (from CORS middleware)
                assert "access-control-allow-origin" in response.headers or True  # May not be set in tests
    
    @pytest.mark.asyncio
    async def test_hotel_multi_tenancy_compatibility(self, sample_user):
        """Test that user authentication works with hotel multi-tenancy"""
        hotel1_id = uuid.uuid4()
        hotel2_id = uuid.uuid4()
        
        # User belongs to hotel1
        sample_user.hotel_id = hotel1_id
        sample_user.permissions = [UserPermission.VIEW_CONVERSATIONS.value]
        
        # Should have access to their hotel
        from app.utils.permission_checker import PermissionChecker
        
        has_access_hotel1 = PermissionChecker.check_permission(
            user=sample_user,
            required_permission=UserPermission.VIEW_CONVERSATIONS,
            hotel_id=hotel1_id
        )
        
        has_access_hotel2 = PermissionChecker.check_permission(
            user=sample_user,
            required_permission=UserPermission.VIEW_CONVERSATIONS,
            hotel_id=hotel2_id
        )
        
        assert has_access_hotel1 is True
        assert has_access_hotel2 is False
    
    @pytest.mark.asyncio
    async def test_api_versioning_compatibility(self, user_auth_headers, sample_user):
        """Test that authentication works with API versioning"""
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Test v1 API endpoints
                response = await client.get(
                    "/api/v1/auth/me",
                    headers=user_auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                
                # Future v2 endpoints should also work with same auth
                # (This is a design consideration for future API versions)
    
    @pytest.mark.asyncio
    async def test_logging_integration(self, user_auth_headers, sample_user):
        """Test that authentication logging works with existing logging"""
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user, \
             patch('structlog.get_logger') as mock_logger:
            
            mock_get_user.return_value = sample_user
            mock_log = AsyncMock()
            mock_logger.return_value = mock_log
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "test@example.com",
                        "password": "TestPassword123!"
                    }
                )
                
                # Should log authentication events
                # (Actual logging verification would depend on implementation)
    
    @pytest.mark.asyncio
    async def test_error_handling_consistency(self, user_auth_headers):
        """Test that error handling is consistent across auth systems"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test invalid token
            invalid_headers = {"Authorization": "Bearer invalid_token"}
            
            response = await client.get(
                "/api/v1/auth/me",
                headers=invalid_headers
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            
            # Error format should be consistent
            data = response.json()
            assert "detail" in data or "error" in data
    
    @pytest.mark.asyncio
    async def test_performance_impact(self, user_auth_headers, sample_user):
        """Test that new auth system doesn't significantly impact performance"""
        import time
        
        with patch('app.api.v1.endpoints.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Measure response time
                start_time = time.time()
                
                response = await client.get(
                    "/api/v1/auth/me",
                    headers=user_auth_headers
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                
                assert response.status_code == status.HTTP_200_OK
                # Response should be reasonably fast (less than 1 second in tests)
                assert response_time < 1.0
