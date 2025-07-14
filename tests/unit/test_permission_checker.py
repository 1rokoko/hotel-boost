"""
Unit tests for permission checker

This module tests the PermissionChecker class and permission-related utilities.
"""

import pytest
import uuid
from unittest.mock import MagicMock

from app.utils.permission_checker import PermissionChecker
from app.models.user import User
from app.models.role import UserRole, UserPermission
from app.core.security import AuthorizationError


@pytest.fixture
def viewer_user():
    """User with viewer role"""
    user = User(
        id=uuid.uuid4(),
        email="viewer@example.com",
        username="viewer",
        full_name="Viewer User",
        role=UserRole.VIEWER,
        permissions=[],
        is_active=True,
        hotel_id=uuid.uuid4()
    )
    return user


@pytest.fixture
def hotel_admin_user():
    """User with hotel admin role"""
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        role=UserRole.HOTEL_ADMIN,
        permissions=[],
        is_active=True,
        hotel_id=uuid.uuid4()
    )
    return user


@pytest.fixture
def super_admin_user():
    """User with super admin role"""
    user = User(
        id=uuid.uuid4(),
        email="superadmin@example.com",
        username="superadmin",
        full_name="Super Admin User",
        role=UserRole.SUPER_ADMIN,
        permissions=[],
        is_active=True,
        hotel_id=None
    )
    return user


@pytest.fixture
def inactive_user():
    """Inactive user"""
    user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        username="inactive",
        full_name="Inactive User",
        role=UserRole.VIEWER,
        permissions=[],
        is_active=False,
        hotel_id=uuid.uuid4()
    )
    return user


class TestPermissionChecker:
    """Test cases for PermissionChecker"""
    
    def test_check_permission_super_admin(self, super_admin_user):
        """Test that super admin has all permissions"""
        # Super admin should have any permission
        has_permission = PermissionChecker.check_permission(
            user=super_admin_user,
            required_permission=UserPermission.MANAGE_SYSTEM
        )
        
        assert has_permission is True
    
    def test_check_permission_explicit_permission(self, viewer_user):
        """Test permission check with explicit permission"""
        # Add explicit permission
        viewer_user.permissions = [UserPermission.VIEW_CONVERSATIONS.value]
        
        has_permission = PermissionChecker.check_permission(
            user=viewer_user,
            required_permission=UserPermission.VIEW_CONVERSATIONS
        )
        
        assert has_permission is True
    
    def test_check_permission_no_permission(self, viewer_user):
        """Test permission check without required permission"""
        # User has no permissions
        viewer_user.permissions = []
        
        has_permission = PermissionChecker.check_permission(
            user=viewer_user,
            required_permission=UserPermission.MANAGE_SYSTEM
        )
        
        assert has_permission is False
    
    def test_check_permission_hotel_access_allowed(self, hotel_admin_user):
        """Test hotel-specific permission check with correct hotel"""
        hotel_id = hotel_admin_user.hotel_id
        hotel_admin_user.permissions = [UserPermission.MANAGE_HOTEL_SETTINGS.value]
        
        has_permission = PermissionChecker.check_permission(
            user=hotel_admin_user,
            required_permission=UserPermission.MANAGE_HOTEL_SETTINGS,
            hotel_id=hotel_id
        )
        
        assert has_permission is True
    
    def test_check_permission_hotel_access_denied(self, hotel_admin_user):
        """Test hotel-specific permission check with wrong hotel"""
        different_hotel_id = uuid.uuid4()
        hotel_admin_user.permissions = [UserPermission.MANAGE_HOTEL_SETTINGS.value]
        
        has_permission = PermissionChecker.check_permission(
            user=hotel_admin_user,
            required_permission=UserPermission.MANAGE_HOTEL_SETTINGS,
            hotel_id=different_hotel_id
        )
        
        assert has_permission is False
    
    def test_validate_user_access_success(self, hotel_admin_user):
        """Test successful user access validation"""
        hotel_admin_user.permissions = [UserPermission.VIEW_CONVERSATIONS.value]
        
        # Should not raise exception
        result = PermissionChecker.validate_user_access(
            user=hotel_admin_user,
            required_permission=UserPermission.VIEW_CONVERSATIONS
        )
        
        assert result is True
    
    def test_validate_user_access_inactive_user(self, inactive_user):
        """Test user access validation with inactive user"""
        with pytest.raises(AuthorizationError, match="Account is deactivated"):
            PermissionChecker.validate_user_access(
                user=inactive_user,
                required_permission=UserPermission.VIEW_CONVERSATIONS
            )
    
    def test_validate_user_access_locked_user(self, viewer_user):
        """Test user access validation with locked user"""
        from datetime import datetime, timedelta
        viewer_user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        with pytest.raises(AuthorizationError, match="Account is locked"):
            PermissionChecker.validate_user_access(
                user=viewer_user,
                required_permission=UserPermission.VIEW_CONVERSATIONS
            )
    
    def test_validate_user_access_insufficient_permissions(self, viewer_user):
        """Test user access validation with insufficient permissions"""
        viewer_user.permissions = []  # No permissions
        
        with pytest.raises(AuthorizationError, match="Insufficient permissions"):
            PermissionChecker.validate_user_access(
                user=viewer_user,
                required_permission=UserPermission.MANAGE_SYSTEM
            )
    
    def test_get_permission_description(self):
        """Test getting permission descriptions"""
        description = PermissionChecker.get_permission_description(
            UserPermission.MANAGE_SYSTEM
        )
        
        assert "system-wide settings" in description.lower()
        assert isinstance(description, str)
        assert len(description) > 0
    
    def test_get_role_description(self):
        """Test getting role descriptions"""
        description = PermissionChecker.get_role_description(UserRole.SUPER_ADMIN)
        
        assert "full system access" in description.lower()
        assert isinstance(description, str)
        assert len(description) > 0
    
    def test_get_user_permissions_summary(self, hotel_admin_user):
        """Test getting user permissions summary"""
        hotel_admin_user.permissions = [UserPermission.SEND_MESSAGES.value]
        
        summary = PermissionChecker.get_user_permissions_summary(hotel_admin_user)
        
        assert "user_id" in summary
        assert "role" in summary
        assert "role_description" in summary
        assert "role_permissions" in summary
        assert "explicit_permissions" in summary
        assert "all_permissions" in summary
        assert "hotel_id" in summary
        assert "is_super_admin" in summary
        assert "permission_count" in summary
        
        assert summary["user_id"] == str(hotel_admin_user.id)
        assert summary["role"] == hotel_admin_user.role.value
        assert summary["is_super_admin"] is False
        assert isinstance(summary["permission_count"], int)
    
    def test_get_user_permissions_summary_super_admin(self, super_admin_user):
        """Test permissions summary for super admin"""
        summary = PermissionChecker.get_user_permissions_summary(super_admin_user)
        
        assert summary["is_super_admin"] is True
        assert summary["role"] == UserRole.SUPER_ADMIN.value
        assert summary["hotel_id"] is None
    
    def test_permission_description_fallback(self):
        """Test permission description fallback for unknown permission"""
        # Create a mock permission that doesn't have a description
        mock_permission = MagicMock()
        mock_permission.value = "unknown_permission"
        
        description = PermissionChecker.get_permission_description(mock_permission)
        
        assert description == "unknown_permission"
    
    def test_role_description_fallback(self):
        """Test role description fallback for unknown role"""
        # Create a mock role that doesn't have a description
        mock_role = MagicMock()
        mock_role.value = "unknown_role"
        
        description = PermissionChecker.get_role_description(mock_role)
        
        assert description == "unknown_role"
    
    def test_check_permission_with_none_hotel_id(self, hotel_admin_user):
        """Test permission check with None hotel_id"""
        hotel_admin_user.permissions = [UserPermission.VIEW_ANALYTICS.value]
        
        # Should work when hotel_id is None (no hotel restriction)
        has_permission = PermissionChecker.check_permission(
            user=hotel_admin_user,
            required_permission=UserPermission.VIEW_ANALYTICS,
            hotel_id=None
        )
        
        assert has_permission is True
    
    def test_check_permission_user_no_hotel(self, super_admin_user):
        """Test permission check for user with no hotel assignment"""
        # Super admin with no hotel should access any hotel
        has_permission = PermissionChecker.check_permission(
            user=super_admin_user,
            required_permission=UserPermission.MANAGE_HOTELS,
            hotel_id=uuid.uuid4()
        )
        
        assert has_permission is True
    
    def test_validate_user_access_with_hotel_restriction(self, hotel_admin_user):
        """Test user access validation with hotel restriction"""
        hotel_admin_user.permissions = [UserPermission.MANAGE_HOTEL_SETTINGS.value]
        target_hotel_id = hotel_admin_user.hotel_id
        
        # Should succeed for same hotel
        result = PermissionChecker.validate_user_access(
            user=hotel_admin_user,
            required_permission=UserPermission.MANAGE_HOTEL_SETTINGS,
            target_hotel_id=target_hotel_id
        )
        
        assert result is True
    
    def test_validate_user_access_wrong_hotel(self, hotel_admin_user):
        """Test user access validation with wrong hotel"""
        hotel_admin_user.permissions = [UserPermission.MANAGE_HOTEL_SETTINGS.value]
        different_hotel_id = uuid.uuid4()
        
        # Should fail for different hotel
        with pytest.raises(AuthorizationError, match="Insufficient permissions"):
            PermissionChecker.validate_user_access(
                user=hotel_admin_user,
                required_permission=UserPermission.MANAGE_HOTEL_SETTINGS,
                target_hotel_id=different_hotel_id
            )
