"""
Unit tests for authentication service

This module tests the AuthService class functionality including user authentication,
registration, and token management.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_service import AuthService
from app.models.user import User
from app.models.role import UserRole
from app.core.security import AuthenticationError
from app.utils.jwt_handler import JWTHandler


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def auth_service(mock_db):
    """Auth service instance with mocked database"""
    return AuthService(mock_db)


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        role=UserRole.VIEWER,
        is_active=True,
        is_verified=True,
        failed_login_attempts="0",
        permissions=[]
    )
    user.set_password("TestPassword123!")
    return user


class TestAuthService:
    """Test cases for AuthService"""
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service, mock_db, sample_user):
        """Test successful user authentication"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        # Test authentication
        result = await auth_service.authenticate_user("test@example.com", "TestPassword123!")
        
        assert result == sample_user
        assert mock_db.execute.called
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service, mock_db):
        """Test authentication with non-existent user"""
        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        # Test authentication
        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await auth_service.authenticate_user("nonexistent@example.com", "password")
    
    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self, auth_service, mock_db, sample_user):
        """Test authentication with inactive user"""
        sample_user.is_active = False
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        # Test authentication
        with pytest.raises(AuthenticationError, match="Account is deactivated"):
            await auth_service.authenticate_user("test@example.com", "TestPassword123!")
    
    @pytest.mark.asyncio
    async def test_authenticate_user_locked(self, auth_service, mock_db, sample_user):
        """Test authentication with locked user"""
        sample_user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        # Test authentication
        with pytest.raises(AuthenticationError, match="Account is locked"):
            await auth_service.authenticate_user("test@example.com", "TestPassword123!")
    
    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, auth_service, mock_db, sample_user):
        """Test authentication with wrong password"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        # Test authentication
        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await auth_service.authenticate_user("test@example.com", "WrongPassword")
        
        # Verify failed login attempt was incremented
        assert sample_user.failed_login_attempts == "1"
    
    @pytest.mark.asyncio
    async def test_create_access_token(self, auth_service, sample_user):
        """Test access token creation"""
        with patch.object(JWTHandler, 'create_user_tokens') as mock_create_tokens:
            mock_tokens = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": sample_user.to_dict()
            }
            mock_create_tokens.return_value = mock_tokens
            
            result = await auth_service.create_access_token(sample_user)
            
            assert result == mock_tokens
            mock_create_tokens.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, auth_service, mock_db, sample_user):
        """Test successful token refresh"""
        refresh_token = "valid_refresh_token"
        
        with patch.object(JWTHandler, 'validate_refresh_token') as mock_validate, \
             patch.object(JWTHandler, 'refresh_access_token') as mock_refresh:
            
            # Mock token validation
            mock_validate.return_value = {"sub": str(sample_user.id)}
            
            # Mock database query
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = sample_user
            mock_db.execute.return_value = mock_result
            
            # Mock token refresh
            new_token = {
                "access_token": "new_access_token",
                "token_type": "bearer",
                "expires_in": 1800
            }
            mock_refresh.return_value = new_token
            
            result = await auth_service.refresh_token(refresh_token)
            
            assert result == new_token
            mock_validate.assert_called_once_with(refresh_token)
            mock_refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_user_success(self, auth_service, mock_db):
        """Test successful user registration"""
        # Mock database queries for existing user checks
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing user
        mock_db.execute.return_value = mock_result
        
        # Test registration
        result = await auth_service.register_user(
            email="newuser@example.com",
            password="NewPassword123!",
            username="newuser",
            full_name="New User",
            role="viewer"
        )
        
        assert isinstance(result, User)
        assert result.email == "newuser@example.com"
        assert result.username == "newuser"
        assert result.full_name == "New User"
        assert result.role == UserRole.VIEWER
        assert mock_db.add.called
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_register_user_email_exists(self, auth_service, mock_db, sample_user):
        """Test registration with existing email"""
        # Mock database query returning existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        # Test registration
        with pytest.raises(AuthenticationError, match="Email already registered"):
            await auth_service.register_user(
                email="test@example.com",
                password="NewPassword123!",
                username="newuser",
                full_name="New User"
            )
    
    @pytest.mark.asyncio
    async def test_register_user_weak_password(self, auth_service, mock_db):
        """Test registration with weak password"""
        # Mock database queries for existing user checks
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        # Test registration with weak password
        with pytest.raises(AuthenticationError, match="Password requirements not met"):
            await auth_service.register_user(
                email="newuser@example.com",
                password="weak",
                username="newuser",
                full_name="New User"
            )
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, auth_service, mock_db, sample_user):
        """Test getting user by ID"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result
        
        result = await auth_service.get_user_by_id(sample_user.id)
        
        assert result == sample_user
        assert mock_db.execute.called
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, auth_service, mock_db):
        """Test getting non-existent user by ID"""
        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        result = await auth_service.get_user_by_id(uuid.uuid4())
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_handle_failed_login(self, auth_service, mock_db, sample_user):
        """Test failed login handling"""
        # Test incrementing failed attempts
        await auth_service._handle_failed_login(sample_user)
        
        assert sample_user.failed_login_attempts == "1"
        assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_handle_failed_login_lockout(self, auth_service, mock_db, sample_user):
        """Test account lockout after multiple failed attempts"""
        sample_user.failed_login_attempts = "4"  # One more will trigger lockout
        
        await auth_service._handle_failed_login(sample_user)
        
        assert sample_user.failed_login_attempts == "5"
        assert sample_user.locked_until is not None
        assert sample_user.locked_until > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_handle_successful_login(self, auth_service, mock_db, sample_user):
        """Test successful login handling"""
        sample_user.failed_login_attempts = "3"
        sample_user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        await auth_service._handle_successful_login(sample_user)
        
        assert sample_user.failed_login_attempts == "0"
        assert sample_user.locked_until is None
        assert sample_user.last_login is not None
        assert mock_db.commit.called
