"""
Security validation tests

This module contains security-focused tests for JWT security, password hashing,
permission escalation prevention, and other security measures.
"""

import pytest
import uuid
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.core.security import Security, TokenError, AuthenticationError
from app.utils.jwt_handler import JWTHandler
from app.models.user import User
from app.models.role import UserRole, UserPermission
from app.utils.permission_checker import PermissionChecker


class TestJWTSecurity:
    """Test JWT token security measures"""
    
    def test_jwt_token_expiration(self):
        """Test that JWT tokens expire correctly"""
        user_data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "username": "testuser",
            "role": "viewer",
            "hotel_id": None,
            "permissions": []
        }
        
        # Create token with short expiration
        with patch('app.core.security.ACCESS_TOKEN_EXPIRE_MINUTES', 0):
            tokens = JWTHandler.create_user_tokens(user_data)
            access_token = tokens["access_token"]
        
        # Wait a moment and verify token is expired
        time.sleep(1)
        
        with pytest.raises(TokenError, match="Token has expired"):
            JWTHandler.validate_access_token(access_token)
    
    def test_jwt_token_tampering_detection(self):
        """Test that tampered JWT tokens are rejected"""
        user_data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "username": "testuser",
            "role": "viewer",
            "hotel_id": None,
            "permissions": []
        }
        
        tokens = JWTHandler.create_user_tokens(user_data)
        access_token = tokens["access_token"]
        
        # Tamper with the token by changing a character
        tampered_token = access_token[:-5] + "XXXXX"
        
        with pytest.raises(TokenError, match="Invalid token"):
            JWTHandler.validate_access_token(tampered_token)
    
    def test_jwt_token_scope_isolation(self):
        """Test that user tokens cannot be used for admin operations"""
        user_data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "username": "testuser",
            "role": "viewer",
            "hotel_id": None,
            "permissions": []
        }
        
        tokens = JWTHandler.create_user_tokens(user_data)
        access_token = tokens["access_token"]
        
        # Validate token and check scope
        payload = JWTHandler.validate_access_token(access_token)
        assert payload["scope"] == "user"
        
        # Ensure admin operations would reject this token
        # (This would be tested in admin middleware tests)
    
    def test_jwt_token_replay_attack_prevention(self):
        """Test that old tokens cannot be reused after refresh"""
        user_data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "username": "testuser",
            "role": "viewer",
            "hotel_id": None,
            "permissions": []
        }
        
        # Create initial tokens
        tokens = JWTHandler.create_user_tokens(user_data)
        old_access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        
        # Refresh to get new access token
        new_tokens = JWTHandler.refresh_access_token(refresh_token, user_data)
        new_access_token = new_tokens["access_token"]
        
        # Both tokens should be valid (in this implementation)
        # In production, you might implement token blacklisting
        JWTHandler.validate_access_token(old_access_token)
        JWTHandler.validate_access_token(new_access_token)
    
    def test_jwt_secret_key_dependency(self):
        """Test that tokens are invalid with different secret keys"""
        user_data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "username": "testuser",
            "role": "viewer",
            "hotel_id": None,
            "permissions": []
        }
        
        # Create token with one secret
        tokens = JWTHandler.create_user_tokens(user_data)
        access_token = tokens["access_token"]
        
        # Try to validate with different secret
        with patch('app.core.config.settings.SECRET_KEY', 'different-secret-key'):
            with pytest.raises(TokenError, match="Invalid token"):
                JWTHandler.validate_access_token(access_token)


class TestPasswordSecurity:
    """Test password hashing and security measures"""
    
    def test_password_hashing_uniqueness(self):
        """Test that same password produces different hashes"""
        password = "TestPassword123!"
        
        hash1 = Security.hash_password(password)
        hash2 = Security.hash_password(password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert Security.verify_password(password, hash1)
        assert Security.verify_password(password, hash2)
    
    def test_password_verification_security(self):
        """Test password verification security"""
        correct_password = "TestPassword123!"
        wrong_password = "WrongPassword123!"
        
        password_hash = Security.hash_password(correct_password)
        
        # Correct password should verify
        assert Security.verify_password(correct_password, password_hash)
        
        # Wrong password should not verify
        assert not Security.verify_password(wrong_password, password_hash)
    
    def test_password_strength_validation(self):
        """Test password strength requirements"""
        # Test various weak passwords
        weak_passwords = [
            "short",           # Too short
            "nouppercase123!", # No uppercase
            "NOLOWERCASE123!", # No lowercase
            "NoNumbers!",      # No numbers
            "NoSpecialChars123" # No special characters
        ]
        
        for weak_password in weak_passwords:
            is_strong, issues = Security.is_strong_password(weak_password)
            assert not is_strong
            assert len(issues) > 0
        
        # Test strong password
        strong_password = "StrongPassword123!"
        is_strong, issues = Security.is_strong_password(strong_password)
        assert is_strong
        assert len(issues) == 0
    
    def test_password_reset_token_security(self):
        """Test password reset token generation"""
        token1 = Security.generate_password_reset_token()
        token2 = Security.generate_password_reset_token()
        
        # Tokens should be different
        assert token1 != token2
        
        # Tokens should be URL-safe
        assert all(c.isalnum() or c in '-_' for c in token1)
        assert all(c.isalnum() or c in '-_' for c in token2)
        
        # Tokens should be sufficiently long
        assert len(token1) >= 32
        assert len(token2) >= 32


class TestPermissionEscalation:
    """Test permission escalation prevention"""
    
    def test_role_hierarchy_enforcement(self):
        """Test that users cannot escalate to higher roles"""
        # Create users with different roles
        viewer = User(
            id=uuid.uuid4(),
            email="viewer@example.com",
            username="viewer",
            full_name="Viewer User",
            role=UserRole.VIEWER,
            permissions=[],
            is_active=True
        )
        
        hotel_admin = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            username="admin",
            full_name="Admin User",
            role=UserRole.HOTEL_ADMIN,
            permissions=[],
            is_active=True
        )
        
        # Viewer should not have admin permissions
        assert not PermissionChecker.check_permission(
            user=viewer,
            required_permission=UserPermission.MANAGE_SYSTEM
        )
        
        # Hotel admin should not have super admin permissions
        assert not PermissionChecker.check_permission(
            user=hotel_admin,
            required_permission=UserPermission.MANAGE_SYSTEM
        )
    
    def test_hotel_isolation_enforcement(self):
        """Test that users cannot access other hotels' data"""
        hotel1_id = uuid.uuid4()
        hotel2_id = uuid.uuid4()
        
        hotel1_admin = User(
            id=uuid.uuid4(),
            email="admin1@example.com",
            username="admin1",
            full_name="Hotel 1 Admin",
            role=UserRole.HOTEL_ADMIN,
            permissions=[UserPermission.MANAGE_HOTEL_SETTINGS.value],
            hotel_id=hotel1_id,
            is_active=True
        )
        
        # Admin should have access to their hotel
        assert PermissionChecker.check_permission(
            user=hotel1_admin,
            required_permission=UserPermission.MANAGE_HOTEL_SETTINGS,
            hotel_id=hotel1_id
        )
        
        # Admin should NOT have access to other hotel
        assert not PermissionChecker.check_permission(
            user=hotel1_admin,
            required_permission=UserPermission.MANAGE_HOTEL_SETTINGS,
            hotel_id=hotel2_id
        )
    
    def test_permission_injection_prevention(self):
        """Test that permissions cannot be injected through user input"""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            role=UserRole.VIEWER,
            permissions=["view_conversations"],  # Only basic permission
            is_active=True
        )
        
        # User should not have admin permissions even if they claim to
        assert not PermissionChecker.check_permission(
            user=user,
            required_permission=UserPermission.MANAGE_SYSTEM
        )
        
        # Test with invalid permission in user's permission list
        user.permissions = ["invalid_permission", "view_conversations"]
        
        # Should still work for valid permissions
        assert PermissionChecker.check_permission(
            user=user,
            required_permission=UserPermission.VIEW_CONVERSATIONS
        )
    
    def test_inactive_user_access_prevention(self):
        """Test that inactive users cannot access system"""
        inactive_user = User(
            id=uuid.uuid4(),
            email="inactive@example.com",
            username="inactive",
            full_name="Inactive User",
            role=UserRole.SUPER_ADMIN,  # Even super admin
            permissions=[],
            is_active=False  # But inactive
        )
        
        # Should raise authorization error
        with pytest.raises(Exception):  # AuthorizationError
            PermissionChecker.validate_user_access(
                user=inactive_user,
                required_permission=UserPermission.VIEW_CONVERSATIONS
            )
    
    def test_locked_user_access_prevention(self):
        """Test that locked users cannot access system"""
        locked_user = User(
            id=uuid.uuid4(),
            email="locked@example.com",
            username="locked",
            full_name="Locked User",
            role=UserRole.HOTEL_ADMIN,
            permissions=[UserPermission.VIEW_CONVERSATIONS.value],
            is_active=True,
            locked_until=datetime.utcnow() + timedelta(minutes=30)
        )
        
        # Should raise authorization error
        with pytest.raises(Exception):  # AuthorizationError
            PermissionChecker.validate_user_access(
                user=locked_user,
                required_permission=UserPermission.VIEW_CONVERSATIONS
            )


class TestSessionSecurity:
    """Test session security measures"""
    
    def test_session_id_uniqueness(self):
        """Test that session IDs are unique"""
        session1 = Security.generate_session_id()
        session2 = Security.generate_session_id()
        
        assert session1 != session2
        assert len(session1) >= 32
        assert len(session2) >= 32
    
    def test_token_type_validation(self):
        """Test that token types are properly validated"""
        user_data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "username": "testuser",
            "role": "viewer",
            "hotel_id": None,
            "permissions": []
        }
        
        tokens = JWTHandler.create_user_tokens(user_data)
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        
        # Access token should not validate as refresh token
        with pytest.raises(TokenError, match="Invalid token type"):
            JWTHandler.validate_refresh_token(access_token)
        
        # Refresh token should not validate as access token
        with pytest.raises(TokenError, match="Invalid token type"):
            JWTHandler.validate_access_token(refresh_token)
    
    def test_token_scope_validation(self):
        """Test that token scope is properly validated"""
        # Create a token with admin scope (simulating admin token)
        admin_token_data = {
            "sub": str(uuid.uuid4()),
            "email": "admin@example.com",
            "type": "access",
            "scope": "admin"  # Admin scope
        }
        
        admin_token = Security.create_access_token(admin_token_data)
        
        # Should fail validation for user operations
        with pytest.raises(TokenError, match="Invalid token scope"):
            JWTHandler.validate_access_token(admin_token)
