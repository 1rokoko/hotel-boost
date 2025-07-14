"""
Webhook flow integration tests for Hotel WhatsApp Bot
Tests webhook processing and message flow scenarios
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, Mock
from httpx import AsyncClient

from app.main import app
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType
from app.schemas.green_api import WebhookMessage, MessageType as GreenMessageType
from app.services.webhook_processor import WebhookProcessor
from app.services.message_handler import MessageHandler


@pytest.mark.integration
@pytest.mark.webhook
@pytest.mark.asyncio
class TestWebhookFlow:
    """Test webhook processing flows"""

    async def test_incoming_text_message_webhook_flow(
        self,
        async_client: AsyncClient,
        sample_hotel,
        mock_green_api_client,
        mock_deepseek_client
    ):
        """Test processing of incoming text message webhook"""

        # Mock services
        mock_green_api_client.send_text_message = AsyncMock(return_value={
            "idMessage": "auto_response_123",
            "statusMessage": "sent"
        })

        # Prepare webhook payload
        webhook_payload = {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": sample_hotel.green_api_instance_id,
                "wid": f"{sample_hotel.whatsapp_number}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(datetime.utcnow().timestamp()),
            "idMessage": "incoming_text_123",
            "senderData": {
                "chatId": "1234567890@c.us",
                "sender": "1234567890@c.us",
                "senderName": "John Doe"
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {
                    "textMessage": "Hello, I would like to make a reservation"
                }
            }
        }

        # Mock external services
        with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
            mock_get_client.return_value = mock_green_api_client

            with patch('app.services.deepseek_client.DeepSeekClient') as mock_deepseek_class:
                mock_deepseek_class.return_value = mock_deepseek_client

                # Send webhook
                response = await async_client.post(
                    f"/api/v1/webhooks/green-api/{sample_hotel.id}",
                    json=webhook_payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Token": sample_hotel.green_api_webhook_token or "test_token"
                    }
                )

        # Verify webhook processing
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["webhook_type"] == "incomingMessageReceived"
        assert "message_id" in response_data

    async def test_message_status_webhook_flow(
        self,
        async_client: AsyncClient,
        sample_hotel,
        async_test_session
    ):
        """Test processing of message status update webhook"""

        # Create a message to update
        guest = Guest(
            hotel_id=sample_hotel.id,
            phone="+1234567890",
            name="Test Guest"
        )
        async_test_session.add(guest)

        conversation = Conversation(
            hotel_id=sample_hotel.id,
            guest_id=guest.id,
            started_at=datetime.utcnow()
        )
        async_test_session.add(conversation)

        message = Message(
            conversation_id=conversation.id,
            guest_id=guest.id,
            content="Test message",
            message_type=MessageType.OUTGOING,
            green_api_message_id="status_update_123"
        )
        async_test_session.add(message)
        await async_test_session.commit()

        # Prepare status webhook payload
        status_payload = {
            "typeWebhook": "outgoingMessageStatus",
            "instanceData": {
                "idInstance": sample_hotel.green_api_instance_id,
                "wid": f"{sample_hotel.whatsapp_number}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(datetime.utcnow().timestamp()),
            "idMessage": "status_update_123",
            "status": "delivered",
            "sendByApi": True
        }

        # Send status webhook
        response = await async_client.post(
            f"/api/v1/webhooks/green-api/{sample_hotel.id}",
            json=status_payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Token": sample_hotel.green_api_webhook_token or "test_token"
            }
        )

        # Verify status update processing
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["webhook_type"] == "outgoingMessageStatus"

    async def test_media_message_webhook_flow(
        self,
        async_client: AsyncClient,
        sample_hotel,
        mock_green_api_client
    ):
        """Test processing of media message webhook"""

        # Mock media download
        mock_green_api_client.download_file = AsyncMock(return_value={
            "file_data": b"fake_image_data",
            "content_type": "image/jpeg",
            "filename": "image.jpg"
        })

        # Prepare media webhook payload
        media_payload = {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": sample_hotel.green_api_instance_id,
                "wid": f"{sample_hotel.whatsapp_number}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(datetime.utcnow().timestamp()),
            "idMessage": "media_msg_123",
            "senderData": {
                "chatId": "1234567890@c.us",
                "sender": "1234567890@c.us",
                "senderName": "Media Sender"
            },
            "messageData": {
                "typeMessage": "imageMessage",
                "fileMessageData": {
                    "downloadUrl": "https://api.green-api.com/file/download/123",
                    "caption": "Here's a photo of the issue",
                    "fileName": "issue_photo.jpg",
                    "jpegThumbnail": "/9j/4AAQSkZJRgABAQAAAQ..."
                }
            }
        }

        # Mock external services
        with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
            mock_get_client.return_value = mock_green_api_client

            with patch('app.services.media_handler.MediaHandler') as mock_media_handler:
                mock_handler_instance = Mock()
                mock_handler_instance.process_media_message = AsyncMock(return_value={
                    "media_processed": True,
                    "file_path": "/uploads/media/issue_photo.jpg"
                })
                mock_media_handler.return_value = mock_handler_instance

                # Send media webhook
                response = await async_client.post(
                    f"/api/v1/webhooks/green-api/{sample_hotel.id}",
                    json=media_payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Token": sample_hotel.green_api_webhook_token or "test_token"
                    }
                )

        # Verify media processing
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["webhook_type"] == "incomingMessageReceived"