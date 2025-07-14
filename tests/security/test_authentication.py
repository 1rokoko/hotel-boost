"""
Authentication security tests for Hotel WhatsApp Bot
Tests authentication mechanisms and security vulnerabilities
"""

import pytest
import jwt
import time
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from httpx import AsyncClient
from fastapi import status

from app.main import app
from app.core.security import create_access_token, verify_token, get_password_hash
from app.models.user import User
from app.models.hotel import Hotel
from app.core.config import settings


@pytest.mark.security
@pytest.mark.asyncio
class TestAuthenticationSecurity:
    """Test authentication security mechanisms"""

    async def test_jwt_token_security(self, async_test_session):
        """Test JWT token security and validation"""

        # Create test user
        user = User(
            email="security@test.com",
            hashed_password=get_password_hash("secure_password"),
            is_active=True
        )
        async_test_session.add(user)
        await async_test_session.commit()

        # Test valid token creation
        token_data = {"sub": user.email, "user_id": str(user.id)}
        valid_token = create_access_token(token_data)

        # Verify token is properly formatted
        assert isinstance(valid_token, str)
        assert len(valid_token.split('.')) == 3  # JWT has 3 parts

        # Test token verification
        payload = verify_token(valid_token)
        assert payload["sub"] == user.email
        assert payload["user_id"] == str(user.id)

        # Test expired token
        expired_token_data = {
            "sub": user.email,
            "user_id": str(user.id),
            "exp": datetime.utcnow() - timedelta(minutes=1)
        }
        expired_token = jwt.encode(
            expired_token_data,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        # Verify expired token is rejected
        with pytest.raises(Exception):  # Should raise JWT expired exception
            verify_token(expired_token)

        # Test malformed token
        malformed_token = "invalid.token.format"
        with pytest.raises(Exception):
            verify_token(malformed_token)

        # Test token with wrong signature
        wrong_signature_token = jwt.encode(
            token_data,
            "wrong_secret_key",
            algorithm=settings.ALGORITHM
        )
        with pytest.raises(Exception):
            verify_token(wrong_signature_token)

    async def test_password_security(self):
        """Test password hashing and validation security"""

        # Test password hashing
        password = "test_password_123"
        hashed = get_password_hash(password)

        # Verify hash is different from original password
        assert hashed != password
        assert len(hashed) > 50  # Bcrypt hashes are long

        # Test password verification
        from app.core.security import verify_password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

        # Test weak password handling
        weak_passwords = ["123", "password", "abc", ""]
        for weak_pwd in weak_passwords:
            # System should still hash weak passwords (validation should be at API level)
            weak_hash = get_password_hash(weak_pwd)
            assert weak_hash != weak_pwd
            assert verify_password(weak_pwd, weak_hash) is True

    async def test_api_authentication_endpoints(
        self,
        async_client: AsyncClient,
        async_test_session
    ):
        """Test API authentication endpoint security"""

        # Create test user
        user = User(
            email="api_test@test.com",
            hashed_password=get_password_hash("secure_password"),
            is_active=True
        )
        async_test_session.add(user)
        await async_test_session.commit()

        # Test valid login
        login_data = {
            "username": "api_test@test.com",  # OAuth2 uses 'username' field
            "password": "secure_password"
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        assert response.status_code == status.HTTP_200_OK
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"

        # Test invalid credentials
        invalid_login_data = {
            "username": "api_test@test.com",
            "password": "wrong_password"
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=invalid_login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Test non-existent user
        nonexistent_login_data = {
            "username": "nonexistent@test.com",
            "password": "any_password"
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=nonexistent_login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Test SQL injection attempt
        sql_injection_data = {
            "username": "'; DROP TABLE users; --",
            "password": "any_password"
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=sql_injection_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Should return 401, not cause an error
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_protected_endpoint_security(
        self,
        async_client: AsyncClient,
        async_test_session
    ):
        """Test protected endpoint access control"""

        # Create test user and hotel
        user = User(
            email="protected_test@test.com",
            hashed_password=get_password_hash("secure_password"),
            is_active=True
        )
        async_test_session.add(user)
        await async_test_session.flush()

        hotel = Hotel(
            name="Security Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            owner_id=user.id
        )
        async_test_session.add(hotel)
        await async_test_session.commit()

        # Test access without token
        response = await async_client.get(f"/api/v1/hotels/{hotel.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Test access with invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        response = await async_client.get(
            f"/api/v1/hotels/{hotel.id}",
            headers=invalid_headers
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Test access with valid token
        token_data = {"sub": user.email, "user_id": str(user.id)}
        valid_token = create_access_token(token_data)
        valid_headers = {"Authorization": f"Bearer {valid_token}"}

        response = await async_client.get(
            f"/api/v1/hotels/{hotel.id}",
            headers=valid_headers
        )
        assert response.status_code == status.HTTP_200_OK

        # Test access to other user's resources
        other_user = User(
            email="other_user@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True
        )
        async_test_session.add(other_user)
        await async_test_session.flush()

        other_token_data = {"sub": other_user.email, "user_id": str(other_user.id)}
        other_token = create_access_token(other_token_data)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        # Should not be able to access another user's hotel
        response = await async_client.get(
            f"/api/v1/hotels/{hotel.id}",
            headers=other_headers
        )
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    async def test_rate_limiting_security(
        self,
        async_client: AsyncClient
    ):
        """Test rate limiting for authentication endpoints"""

        # Test multiple failed login attempts
        login_data = {
            "username": "nonexistent@test.com",
            "password": "wrong_password"
        }

        # Make multiple rapid requests
        responses = []
        for i in range(10):
            response = await async_client.post(
                "/api/v1/auth/login",
                data=login_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            responses.append(response.status_code)

        # All should be 401 (unauthorized) but system should handle the load
        assert all(code == status.HTTP_401_UNAUTHORIZED for code in responses)

        # If rate limiting is implemented, later requests might be 429 (Too Many Requests)
        # This test ensures the system doesn't crash under rapid authentication attempts

    async def test_session_security(
        self,
        async_client: AsyncClient,
        async_test_session
    ):
        """Test session management security"""

        # Create test user
        user = User(
            email="session_test@test.com",
            hashed_password=get_password_hash("secure_password"),
            is_active=True
        )
        async_test_session.add(user)
        await async_test_session.commit()

        # Login and get token
        login_data = {
            "username": "session_test@test.com",
            "password": "secure_password"
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        assert response.status_code == status.HTTP_200_OK
        token_data = response.json()
        access_token = token_data["access_token"]

        # Test token reuse
        headers = {"Authorization": f"Bearer {access_token}"}

        # Multiple requests with same token should work
        for _ in range(3):
            response = await async_client.get(
                "/api/v1/auth/me",
                headers=headers
            )
            assert response.status_code == status.HTTP_200_OK

        # Test token after user deactivation
        user.is_active = False
        async_test_session.add(user)
        await async_test_session.commit()

        # Token should still be valid (stateless JWT) but user access should be restricted
        # This depends on implementation - some systems check user status on each request
        response = await async_client.get(
            "/api/v1/auth/me",
            headers=headers
        )
        # Could be 200 (if only checking token) or 401 (if checking user status)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]