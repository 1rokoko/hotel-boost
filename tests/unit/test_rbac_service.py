"""
Unit tests for RBAC service

This module tests the RBACService class functionality including role management,
permission assignment, and access control operations.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rbac_service import RBACService
from app.models.role import Role, UserRole, UserPermission
from app.models.user import User


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def rbac_service(mock_db):
    """RBAC service instance with mocked database"""
    return RBACService(mock_db)


@pytest.fixture
def sample_role():
    """Sample role for testing"""
    return Role(
        id=uuid.uuid4(),
        name="test_role",
        display_name="Test Role",
        description="Test role description",
        permissions=["view_conversations", "view_analytics"],
        is_system_role="false",
        is_active="true"
    )


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    return User(
        id=uuid.uuid4(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        role=UserRole.VIEWER,
        permissions=[],
        is_active=True
    )


class TestRBACService:
    """Test cases for RBACService"""
    
    @pytest.mark.asyncio
    async def test_create_role_success(self, rbac_service, mock_db):
        """Test successful role creation"""
        # Mock database query for existing role check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing role
        mock_db.execute.return_value = mock_result
        
        # Test role creation
        result = await rbac_service.create_role(
            name="new_role",
            display_name="New Role",
            description="New role description",
            permissions=["view_conversations"],
            is_system_role=False
        )
        
        assert isinstance(result, Role)
        assert result.name == "new_role"
        assert result.display_name == "New Role"
        assert result.permissions == ["view_conversations"]
        assert mock_db.add.called
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_create_role_already_exists(self, rbac_service, mock_db, sample_role):
        """Test role creation when role already exists"""
        # Mock database query returning existing role
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_role
        mock_db.execute.return_value = mock_result
        
        # Test role creation
        with pytest.raises(ValueError, match="Role 'test_role' already exists"):
            await rbac_service.create_role(
                name="test_role",
                display_name="Test Role",
                permissions=["view_conversations"]
            )
    
    @pytest.mark.asyncio
    async def test_create_role_invalid_permission(self, rbac_service, mock_db):
        """Test role creation with invalid permission"""
        # Mock database query for existing role check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        # Test role creation with invalid permission
        with pytest.raises(ValueError, match="Invalid permission: invalid_permission"):
            await rbac_service.create_role(
                name="new_role",
                display_name="New Role",
                permissions=["invalid_permission"]
            )
    
    @pytest.mark.asyncio
    async def test_get_role_by_id_success(self, rbac_service, mock_db, sample_role):
        """Test getting role by ID"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_role
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.get_role_by_id(sample_role.id)
        
        assert result == sample_role
        assert mock_db.execute.called
    
    @pytest.mark.asyncio
    async def test_get_role_by_id_not_found(self, rbac_service, mock_db):
        """Test getting non-existent role by ID"""
        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.get_role_by_id(uuid.uuid4())
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_role_by_name_success(self, rbac_service, mock_db, sample_role):
        """Test getting role by name"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_role
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.get_role_by_name("test_role")
        
        assert result == sample_role
        assert mock_db.execute.called
    
    @pytest.mark.asyncio
    async def test_list_roles_success(self, rbac_service, mock_db, sample_role):
        """Test listing roles"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_role]
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.list_roles()
        
        assert len(result) == 1
        assert result[0] == sample_role
        assert mock_db.execute.called
    
    @pytest.mark.asyncio
    async def test_list_roles_active_only(self, rbac_service, mock_db):
        """Test listing only active roles"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.list_roles(active_only=True)
        
        assert len(result) == 0
        assert mock_db.execute.called
    
    @pytest.mark.asyncio
    async def test_update_role_success(self, rbac_service, mock_db, sample_role):
        """Test successful role update"""
        # Mock get_role_by_id
        with pytest.mock.patch.object(rbac_service, 'get_role_by_id', return_value=sample_role):
            result = await rbac_service.update_role(
                role_id=sample_role.id,
                display_name="Updated Role",
                permissions=["view_conversations", "send_messages"]
            )
        
        assert result == sample_role
        assert sample_role.display_name == "Updated Role"
        assert sample_role.permissions == ["view_conversations", "send_messages"]
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_update_role_not_found(self, rbac_service, mock_db):
        """Test updating non-existent role"""
        # Mock get_role_by_id returning None
        with pytest.mock.patch.object(rbac_service, 'get_role_by_id', return_value=None):
            with pytest.raises(ValueError, match="Role not found"):
                await rbac_service.update_role(
                    role_id=uuid.uuid4(),
                    display_name="Updated Role"
                )
    
    @pytest.mark.asyncio
    async def test_update_system_role_forbidden(self, rbac_service, mock_db, sample_role):
        """Test updating system role is forbidden"""
        sample_role.is_system_role = "true"
        
        # Mock get_role_by_id
        with pytest.mock.patch.object(rbac_service, 'get_role_by_id', return_value=sample_role):
            with pytest.raises(ValueError, match="Cannot modify system role"):
                await rbac_service.update_role(
                    role_id=sample_role.id,
                    display_name="Updated Role"
                )
    
    @pytest.mark.asyncio
    async def test_delete_role_success(self, rbac_service, mock_db, sample_role):
        """Test successful role deletion"""
        # Mock get_role_by_id
        with pytest.mock.patch.object(rbac_service, 'get_role_by_id', return_value=sample_role):
            # Mock user query returning no users
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute.return_value = mock_result
            
            result = await rbac_service.delete_role(sample_role.id)
        
        assert result is True
        assert mock_db.delete.called
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_delete_role_in_use(self, rbac_service, mock_db, sample_role, sample_user):
        """Test deleting role that is in use"""
        # Mock get_role_by_id
        with pytest.mock.patch.object(rbac_service, 'get_role_by_id', return_value=sample_role):
            # Mock user query returning users with this role
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [sample_user]
            mock_db.execute.return_value = mock_result
            
            with pytest.raises(ValueError, match="Cannot delete role: 1 users have this role"):
                await rbac_service.delete_role(sample_role.id)
    
    @pytest.mark.asyncio
    async def test_delete_system_role_forbidden(self, rbac_service, mock_db, sample_role):
        """Test deleting system role is forbidden"""
        sample_role.is_system_role = "true"
        
        # Mock get_role_by_id
        with pytest.mock.patch.object(rbac_service, 'get_role_by_id', return_value=sample_role):
            with pytest.raises(ValueError, match="Cannot delete system role"):
                await rbac_service.delete_role(sample_role.id)
    
    @pytest.mark.asyncio
    async def test_assign_role_to_user_success(self, rbac_service, mock_db, sample_user):
        """Test successful role assignment to user"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.assign_role_to_user(
            user_id=sample_user.id,
            role=UserRole.HOTEL_ADMIN
        )
        
        assert result is True
        assert sample_user.role == UserRole.HOTEL_ADMIN
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_assign_role_to_user_not_found(self, rbac_service, mock_db):
        """Test role assignment to non-existent user"""
        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="User not found"):
            await rbac_service.assign_role_to_user(
                user_id=uuid.uuid4(),
                role=UserRole.HOTEL_ADMIN
            )
    
    @pytest.mark.asyncio
    async def test_add_permission_to_user_success(self, rbac_service, mock_db, sample_user):
        """Test adding permission to user"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.add_permission_to_user(
            user_id=sample_user.id,
            permission=UserPermission.SEND_MESSAGES
        )
        
        assert result is True
        assert UserPermission.SEND_MESSAGES.value in sample_user.permissions
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_add_permission_to_user_already_exists(self, rbac_service, mock_db, sample_user):
        """Test adding permission that user already has"""
        sample_user.permissions = [UserPermission.SEND_MESSAGES.value]
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.add_permission_to_user(
            user_id=sample_user.id,
            permission=UserPermission.SEND_MESSAGES
        )
        
        assert result is True
        # Permission should not be duplicated
        assert sample_user.permissions.count(UserPermission.SEND_MESSAGES.value) == 1
    
    @pytest.mark.asyncio
    async def test_remove_permission_from_user_success(self, rbac_service, mock_db, sample_user):
        """Test removing permission from user"""
        sample_user.permissions = [UserPermission.SEND_MESSAGES.value, UserPermission.VIEW_CONVERSATIONS.value]
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.remove_permission_from_user(
            user_id=sample_user.id,
            permission=UserPermission.SEND_MESSAGES
        )
        
        assert result is True
        assert UserPermission.SEND_MESSAGES.value not in sample_user.permissions
        assert UserPermission.VIEW_CONVERSATIONS.value in sample_user.permissions
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_remove_permission_from_user_not_exists(self, rbac_service, mock_db, sample_user):
        """Test removing permission that user doesn't have"""
        sample_user.permissions = [UserPermission.VIEW_CONVERSATIONS.value]
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        result = await rbac_service.remove_permission_from_user(
            user_id=sample_user.id,
            permission=UserPermission.SEND_MESSAGES
        )
        
        assert result is True
        # Permissions should remain unchanged
        assert sample_user.permissions == [UserPermission.VIEW_CONVERSATIONS.value]
