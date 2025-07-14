"""
Unit tests for JWT handler

This module tests the JWTHandler class functionality including token creation,
validation, and refresh operations.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from app.utils.jwt_handler import JWTHandler
from app.core.security import Security, TokenError, AuthenticationError


@pytest.fixture
def sample_user_data():
    """Sample user data for token creation"""
    return {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "username": "testuser",
        "role": "viewer",
        "hotel_id": None,
        "permissions": ["view_conversations", "view_analytics"]
    }


class TestJWTHandler:
    """Test cases for JWTHandler"""
    
    def test_create_user_tokens(self, sample_user_data):
        """Test user token creation"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] == 30 * 60  # 30 minutes
        assert "user" in tokens
        
        # Verify user data in response
        user_data = tokens["user"]
        assert user_data["id"] == str(sample_user_data["id"])
        assert user_data["email"] == sample_user_data["email"]
        assert user_data["username"] == sample_user_data["username"]
    
    def test_validate_access_token_success(self, sample_user_data):
        """Test successful access token validation"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        access_token = tokens["access_token"]
        
        payload = JWTHandler.validate_access_token(access_token)
        
        assert payload["sub"] == str(sample_user_data["id"])
        assert payload["email"] == sample_user_data["email"]
        assert payload["username"] == sample_user_data["username"]
        assert payload["role"] == sample_user_data["role"]
        assert payload["permissions"] == sample_user_data["permissions"]
        assert payload["type"] == "access"
        assert payload["scope"] == "user"
    
    def test_validate_access_token_invalid(self):
        """Test access token validation with invalid token"""
        with pytest.raises(TokenError, match="Invalid token"):
            JWTHandler.validate_access_token("invalid_token")
    
    def test_validate_access_token_expired(self, sample_user_data):
        """Test access token validation with expired token"""
        # Create token with past expiration
        with patch('app.core.security.datetime') as mock_datetime:
            past_time = datetime.utcnow() - timedelta(hours=1)
            mock_datetime.utcnow.return_value = past_time
            
            tokens = JWTHandler.create_user_tokens(sample_user_data)
            access_token = tokens["access_token"]
        
        # Validate with current time (token should be expired)
        with pytest.raises(TokenError, match="Token has expired"):
            JWTHandler.validate_access_token(access_token)
    
    def test_validate_refresh_token_success(self, sample_user_data):
        """Test successful refresh token validation"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        refresh_token = tokens["refresh_token"]
        
        payload = JWTHandler.validate_refresh_token(refresh_token)
        
        assert payload["sub"] == str(sample_user_data["id"])
        assert payload["type"] == "refresh"
        assert payload["scope"] == "user"
    
    def test_validate_refresh_token_invalid(self):
        """Test refresh token validation with invalid token"""
        with pytest.raises(TokenError, match="Invalid token"):
            JWTHandler.validate_refresh_token("invalid_token")
    
    def test_validate_refresh_token_wrong_type(self, sample_user_data):
        """Test refresh token validation with access token"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        access_token = tokens["access_token"]
        
        with pytest.raises(TokenError, match="Invalid token type"):
            JWTHandler.validate_refresh_token(access_token)
    
    def test_refresh_access_token_success(self, sample_user_data):
        """Test successful access token refresh"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        refresh_token = tokens["refresh_token"]
        
        new_token = JWTHandler.refresh_access_token(refresh_token, sample_user_data)
        
        assert "access_token" in new_token
        assert new_token["token_type"] == "bearer"
        assert new_token["expires_in"] == 30 * 60
        
        # Verify new token is valid
        payload = JWTHandler.validate_access_token(new_token["access_token"])
        assert payload["sub"] == str(sample_user_data["id"])
    
    def test_refresh_access_token_user_mismatch(self, sample_user_data):
        """Test access token refresh with user ID mismatch"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        refresh_token = tokens["refresh_token"]
        
        # Different user data
        different_user_data = sample_user_data.copy()
        different_user_data["id"] = uuid.uuid4()
        
        with pytest.raises(AuthenticationError, match="User ID mismatch"):
            JWTHandler.refresh_access_token(refresh_token, different_user_data)
    
    def test_refresh_access_token_invalid_token(self, sample_user_data):
        """Test access token refresh with invalid refresh token"""
        with pytest.raises(TokenError):
            JWTHandler.refresh_access_token("invalid_token", sample_user_data)
    
    def test_extract_user_id_from_token_success(self, sample_user_data):
        """Test extracting user ID from valid token"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        access_token = tokens["access_token"]
        
        user_id = JWTHandler.extract_user_id_from_token(access_token)
        
        assert user_id == sample_user_data["id"]
    
    def test_extract_user_id_from_token_invalid(self):
        """Test extracting user ID from invalid token"""
        user_id = JWTHandler.extract_user_id_from_token("invalid_token")
        
        assert user_id is None
    
    def test_get_token_expiry_success(self, sample_user_data):
        """Test getting token expiry time"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        access_token = tokens["access_token"]
        
        expiry = JWTHandler.get_token_expiry(access_token)
        
        assert expiry is not None
        assert isinstance(expiry, datetime)
        assert expiry > datetime.utcnow()
    
    def test_get_token_expiry_invalid(self):
        """Test getting expiry time from invalid token"""
        expiry = JWTHandler.get_token_expiry("invalid_token")
        
        assert expiry is None
    
    def test_is_token_expired_false(self, sample_user_data):
        """Test checking if valid token is expired"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        access_token = tokens["access_token"]
        
        is_expired = JWTHandler.is_token_expired(access_token)
        
        assert is_expired is False
    
    def test_is_token_expired_true(self):
        """Test checking if invalid token is expired"""
        is_expired = JWTHandler.is_token_expired("invalid_token")
        
        assert is_expired is True
    
    def test_is_token_expired_actually_expired(self, sample_user_data):
        """Test checking if actually expired token is expired"""
        # Create token with past expiration
        with patch('app.core.security.datetime') as mock_datetime:
            past_time = datetime.utcnow() - timedelta(hours=1)
            mock_datetime.utcnow.return_value = past_time
            
            tokens = JWTHandler.create_user_tokens(sample_user_data)
            access_token = tokens["access_token"]
        
        # Check if expired with current time
        is_expired = JWTHandler.is_token_expired(access_token)
        
        assert is_expired is True
    
    def test_token_scope_validation(self, sample_user_data):
        """Test that tokens have correct scope"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        
        # Validate access token scope
        access_payload = JWTHandler.validate_access_token(tokens["access_token"])
        assert access_payload["scope"] == "user"
        
        # Validate refresh token scope
        refresh_payload = JWTHandler.validate_refresh_token(tokens["refresh_token"])
        assert refresh_payload["scope"] == "user"
    
    def test_token_required_fields(self, sample_user_data):
        """Test that tokens contain required fields"""
        tokens = JWTHandler.create_user_tokens(sample_user_data)
        access_token = tokens["access_token"]
        
        payload = JWTHandler.validate_access_token(access_token)
        
        # Check required fields
        required_fields = ["sub", "email"]
        for field in required_fields:
            assert field in payload
        
        # Check that sub (user ID) is valid UUID
        user_id = uuid.UUID(payload["sub"])
        assert isinstance(user_id, uuid.UUID)
    
    def test_token_missing_required_fields(self):
        """Test token validation with missing required fields"""
        # Create token with missing email field
        token_data = {"sub": str(uuid.uuid4())}
        token = Security.create_access_token(token_data)
        
        with pytest.raises(TokenError, match="Token missing required field"):
            JWTHandler.validate_access_token(token)
    
    def test_refresh_token_missing_user_id(self):
        """Test refresh token validation with missing user ID"""
        # Create refresh token without sub field
        token_data = {"type": "refresh", "scope": "user"}
        token = Security.create_refresh_token(token_data)
        
        with pytest.raises(TokenError, match="Refresh token missing user ID"):
            JWTHandler.validate_refresh_token(token)
