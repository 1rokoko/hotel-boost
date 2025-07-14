"""
API Integration tests for Hotel WhatsApp Bot
Tests API endpoints integration with external services
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, Mock
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation
from app.schemas.green_api import SendTextMessageRequest, WebhookMessage
from app.schemas.deepseek import SentimentAnalysisResult, SentimentType
from app.services.green_api_service import GreenAPIService
from app.services.deepseek_client import DeepSeekClient


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPIIntegration:
    """Test API endpoints integration with external services"""

    async def test_webhook_endpoint_integration(
        self,
        async_client: AsyncClient,
        sample_hotel,
        mock_green_api_client,
        mock_deepseek_client
    ):
        """Test webhook endpoint processes messages correctly"""

        # Mock external services
        mock_green_api_client.send_text_message = AsyncMock(return_value={
            "idMessage": "response_123",
            "statusMessage": "sent"
        })

        mock_deepseek_client.analyze_sentiment = AsyncMock(return_value=
            SentimentAnalysisResult(
                sentiment=SentimentType.POSITIVE,
                confidence=0.8,
                requires_attention=False,
                reasoning="Positive customer inquiry"
            )
        )

        # Prepare webhook payload
        webhook_payload = {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": sample_hotel.green_api_instance_id,
                "wid": f"{sample_hotel.whatsapp_number}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(datetime.utcnow().timestamp()),
            "idMessage": "webhook_msg_123",
            "senderData": {
                "chatId": "1234567890@c.us",
                "sender": "1234567890@c.us",
                "senderName": "Test User"
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {
                    "textMessage": "Hello, I need help with my booking"
                }
            }
        }

        # Mock service dependencies
        with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
            mock_get_client.return_value = mock_green_api_client

            with patch('app.services.deepseek_client.DeepSeekClient') as mock_deepseek_class:
                mock_deepseek_class.return_value = mock_deepseek_client

                # Send webhook request
                response = await async_client.post(
                    f"/api/v1/webhooks/green-api/{sample_hotel.id}",
                    json=webhook_payload,
                    headers={"Content-Type": "application/json"}
                )

        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert "message_processed" in response_data

        # Verify external services were called
        mock_deepseek_client.analyze_sentiment.assert_called_once()

    async def test_hotel_management_api_integration(
        self,
        async_client: AsyncClient,
        async_test_session,
        auth_headers
    ):
        """Test hotel management API endpoints"""

        # Test hotel creation
        hotel_data = {
            "name": "Integration Test Hotel",
            "whatsapp_number": "+1234567890",
            "green_api_instance_id": "test_instance_123",
            "green_api_token": "test_token_456",
            "settings": {
                "welcome_message": "Welcome to our hotel!",
                "business_hours": "9:00-18:00"
            }
        }

        response = await async_client.post(
            "/api/v1/hotels/",
            json=hotel_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        created_hotel = response.json()
        assert created_hotel["name"] == hotel_data["name"]
        assert created_hotel["whatsapp_number"] == hotel_data["whatsapp_number"]
        hotel_id = created_hotel["id"]

        # Test hotel retrieval
        response = await async_client.get(
            f"/api/v1/hotels/{hotel_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        retrieved_hotel = response.json()
        assert retrieved_hotel["id"] == hotel_id
        assert retrieved_hotel["name"] == hotel_data["name"]

        # Test hotel update
        update_data = {
            "name": "Updated Hotel Name",
            "settings": {
                "welcome_message": "Updated welcome message",
                "business_hours": "8:00-20:00"
            }
        }

        response = await async_client.put(
            f"/api/v1/hotels/{hotel_id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        updated_hotel = response.json()
        assert updated_hotel["name"] == update_data["name"]
        assert updated_hotel["settings"]["welcome_message"] == update_data["settings"]["welcome_message"]

    async def test_conversation_api_integration(
        self,
        async_client: AsyncClient,
        sample_hotel,
        sample_guest,
        auth_headers
    ):
        """Test conversation management API endpoints"""

        # Test conversation listing
        response = await async_client.get(
            f"/api/v1/hotels/{sample_hotel.id}/conversations",
            headers=auth_headers
        )

        assert response.status_code == 200
        conversations = response.json()
        assert isinstance(conversations, list)

        # Test conversation creation (via message)
        message_data = {
            "guest_id": str(sample_guest.id),
            "content": "Test message for conversation",
            "message_type": "incoming"
        }

        response = await async_client.post(
            f"/api/v1/hotels/{sample_hotel.id}/messages",
            json=message_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        created_message = response.json()
        assert created_message["content"] == message_data["content"]
        conversation_id = created_message["conversation_id"]

        # Test conversation retrieval
        response = await async_client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        conversation = response.json()
        assert conversation["id"] == conversation_id
        assert conversation["guest_id"] == str(sample_guest.id)