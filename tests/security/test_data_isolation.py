"""
Data isolation security tests for Hotel WhatsApp Bot
Tests multi-tenant data isolation and access controls
"""

import pytest
from datetime import datetime
from unittest.mock import patch
from httpx import AsyncClient
from fastapi import status
from sqlalchemy import select

from app.main import app
from app.models.user import User
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType
from app.models.trigger import Trigger, TriggerType
from app.core.security import create_access_token, get_password_hash


@pytest.mark.security
@pytest.mark.isolation
@pytest.mark.asyncio
class TestDataIsolation:
    """Test data isolation between different hotels/tenants"""

    async def test_hotel_data_isolation(
        self,
        async_client: AsyncClient,
        async_test_session
    ):
        """Test that hotels cannot access each other's data"""

        # Create two users with their hotels
        user1 = User(
            email="hotel1@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True
        )
        user2 = User(
            email="hotel2@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True
        )
        async_test_session.add_all([user1, user2])
        await async_test_session.flush()

        hotel1 = Hotel(
            name="Hotel One",
            whatsapp_number="+1111111111",
            green_api_instance_id="instance1",
            green_api_token="token1",
            owner_id=user1.id
        )
        hotel2 = Hotel(
            name="Hotel Two",
            whatsapp_number="+2222222222",
            green_api_instance_id="instance2",
            green_api_token="token2",
            owner_id=user2.id
        )
        async_test_session.add_all([hotel1, hotel2])
        await async_test_session.commit()

        # Create authentication tokens
        token1 = create_access_token({"sub": user1.email, "user_id": str(user1.id)})
        token2 = create_access_token({"sub": user2.email, "user_id": str(user2.id)})

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Test hotel access isolation
        # User1 should access hotel1
        response = await async_client.get(f"/api/v1/hotels/{hotel1.id}", headers=headers1)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Hotel One"

        # User1 should NOT access hotel2
        response = await async_client.get(f"/api/v1/hotels/{hotel2.id}", headers=headers1)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # User2 should access hotel2
        response = await async_client.get(f"/api/v1/hotels/{hotel2.id}", headers=headers2)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Hotel Two"

        # User2 should NOT access hotel1
        response = await async_client.get(f"/api/v1/hotels/{hotel1.id}", headers=headers2)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    async def test_guest_data_isolation(
        self,
        async_client: AsyncClient,
        async_test_session
    ):
        """Test that guests are isolated between hotels"""

        # Setup two hotels with users
        user1 = User(email="guest_test1@test.com", hashed_password=get_password_hash("password"), is_active=True)
        user2 = User(email="guest_test2@test.com", hashed_password=get_password_hash("password"), is_active=True)
        async_test_session.add_all([user1, user2])
        await async_test_session.flush()

        hotel1 = Hotel(name="Guest Hotel 1", whatsapp_number="+1111111111", green_api_instance_id="inst1", green_api_token="tok1", owner_id=user1.id)
        hotel2 = Hotel(name="Guest Hotel 2", whatsapp_number="+2222222222", green_api_instance_id="inst2", green_api_token="tok2", owner_id=user2.id)
        async_test_session.add_all([hotel1, hotel2])
        await async_test_session.flush()

        # Create guests for each hotel
        guest1 = Guest(hotel_id=hotel1.id, phone="+1234567890", name="Guest One")
        guest2 = Guest(hotel_id=hotel2.id, phone="+0987654321", name="Guest Two")
        async_test_session.add_all([guest1, guest2])
        await async_test_session.commit()

        # Create tokens
        token1 = create_access_token({"sub": user1.email, "user_id": str(user1.id)})
        token2 = create_access_token({"sub": user2.email, "user_id": str(user2.id)})
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Test guest access isolation
        # Hotel1 should see only its guests
        response = await async_client.get(f"/api/v1/hotels/{hotel1.id}/guests", headers=headers1)
        assert response.status_code == status.HTTP_200_OK
        guests_data = response.json()
        assert len(guests_data) == 1
        assert guests_data[0]["name"] == "Guest One"

        # Hotel2 should see only its guests
        response = await async_client.get(f"/api/v1/hotels/{hotel2.id}/guests", headers=headers2)
        assert response.status_code == status.HTTP_200_OK
        guests_data = response.json()
        assert len(guests_data) == 1
        assert guests_data[0]["name"] == "Guest Two"

        # Hotel1 should NOT access hotel2's guests endpoint
        response = await async_client.get(f"/api/v1/hotels/{hotel2.id}/guests", headers=headers1)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # Direct guest access should be isolated
        response = await async_client.get(f"/api/v1/guests/{guest2.id}", headers=headers1)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    async def test_conversation_data_isolation(
        self,
        async_client: AsyncClient,
        async_test_session
    ):
        """Test that conversations are isolated between hotels"""

        # Setup hotels and guests
        user1 = User(email="conv_test1@test.com", hashed_password=get_password_hash("password"), is_active=True)
        user2 = User(email="conv_test2@test.com", hashed_password=get_password_hash("password"), is_active=True)
        async_test_session.add_all([user1, user2])
        await async_test_session.flush()

        hotel1 = Hotel(name="Conv Hotel 1", whatsapp_number="+1111111111", green_api_instance_id="conv1", green_api_token="tok1", owner_id=user1.id)
        hotel2 = Hotel(name="Conv Hotel 2", whatsapp_number="+2222222222", green_api_instance_id="conv2", green_api_token="tok2", owner_id=user2.id)
        async_test_session.add_all([hotel1, hotel2])
        await async_test_session.flush()

        guest1 = Guest(hotel_id=hotel1.id, phone="+1111111111", name="Conv Guest 1")
        guest2 = Guest(hotel_id=hotel2.id, phone="+2222222222", name="Conv Guest 2")
        async_test_session.add_all([guest1, guest2])
        await async_test_session.flush()

        # Create conversations
        conv1 = Conversation(hotel_id=hotel1.id, guest_id=guest1.id, started_at=datetime.utcnow())
        conv2 = Conversation(hotel_id=hotel2.id, guest_id=guest2.id, started_at=datetime.utcnow())
        async_test_session.add_all([conv1, conv2])
        await async_test_session.flush()

        # Create messages
        msg1 = Message(conversation_id=conv1.id, guest_id=guest1.id, content="Hotel 1 message", message_type=MessageType.INCOMING)
        msg2 = Message(conversation_id=conv2.id, guest_id=guest2.id, content="Hotel 2 message", message_type=MessageType.INCOMING)
        async_test_session.add_all([msg1, msg2])
        await async_test_session.commit()

        # Create tokens
        token1 = create_access_token({"sub": user1.email, "user_id": str(user1.id)})
        token2 = create_access_token({"sub": user2.email, "user_id": str(user2.id)})
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Test conversation isolation
        # Hotel1 should see only its conversations
        response = await async_client.get(f"/api/v1/hotels/{hotel1.id}/conversations", headers=headers1)
        assert response.status_code == status.HTTP_200_OK
        conversations = response.json()
        assert len(conversations) == 1

        # Hotel1 should NOT access hotel2's conversations
        response = await async_client.get(f"/api/v1/hotels/{hotel2.id}/conversations", headers=headers1)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # Direct conversation access should be isolated
        response = await async_client.get(f"/api/v1/conversations/{conv2.id}", headers=headers1)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # Message access should be isolated
        response = await async_client.get(f"/api/v1/conversations/{conv2.id}/messages", headers=headers1)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    async def test_trigger_data_isolation(
        self,
        async_client: AsyncClient,
        async_test_session
    ):
        """Test that triggers are isolated between hotels"""

        # Setup hotels
        user1 = User(email="trigger_test1@test.com", hashed_password=get_password_hash("password"), is_active=True)
        user2 = User(email="trigger_test2@test.com", hashed_password=get_password_hash("password"), is_active=True)
        async_test_session.add_all([user1, user2])
        await async_test_session.flush()

        hotel1 = Hotel(name="Trigger Hotel 1", whatsapp_number="+1111111111", green_api_instance_id="trig1", green_api_token="tok1", owner_id=user1.id)
        hotel2 = Hotel(name="Trigger Hotel 2", whatsapp_number="+2222222222", green_api_instance_id="trig2", green_api_token="tok2", owner_id=user2.id)
        async_test_session.add_all([hotel1, hotel2])
        await async_test_session.flush()

        # Create triggers for each hotel
        trigger1 = Trigger(
            hotel_id=hotel1.id,
            trigger_type=TriggerType.FIRST_MESSAGE,
            name="Hotel 1 Welcome",
            conditions={"is_first_message": True},
            message_template="Welcome to Hotel 1!",
            is_active=True
        )
        trigger2 = Trigger(
            hotel_id=hotel2.id,
            trigger_type=TriggerType.FIRST_MESSAGE,
            name="Hotel 2 Welcome",
            conditions={"is_first_message": True},
            message_template="Welcome to Hotel 2!",
            is_active=True
        )
        async_test_session.add_all([trigger1, trigger2])
        await async_test_session.commit()

        # Create tokens
        token1 = create_access_token({"sub": user1.email, "user_id": str(user1.id)})
        token2 = create_access_token({"sub": user2.email, "user_id": str(user2.id)})
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Test trigger isolation
        # Hotel1 should see only its triggers
        response = await async_client.get(f"/api/v1/hotels/{hotel1.id}/triggers", headers=headers1)
        assert response.status_code == status.HTTP_200_OK
        triggers = response.json()
        assert len(triggers) == 1
        assert triggers[0]["name"] == "Hotel 1 Welcome"

        # Hotel1 should NOT access hotel2's triggers
        response = await async_client.get(f"/api/v1/hotels/{hotel2.id}/triggers", headers=headers1)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # Direct trigger access should be isolated
        response = await async_client.get(f"/api/v1/triggers/{trigger2.id}", headers=headers1)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]