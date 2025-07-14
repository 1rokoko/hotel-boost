"""
Full workflow integration tests for Hotel WhatsApp Bot
Tests complete end-to-end scenarios from message receipt to response
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from sqlalchemy import select

from app.main import app
from app.database import get_db
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType, ConversationState
from app.models.trigger import Trigger, TriggerType
from app.models.sentiment import SentimentAnalysis
from app.models.notification import StaffNotification
from app.services.green_api_service import GreenAPIService
from app.services.deepseek_client import DeepSeekClient
from app.services.message_handler import MessageHandler
from app.services.sentiment_analyzer import SentimentAnalyzer
from app.services.trigger_engine import TriggerEngine
from app.tasks.process_message import process_incoming_message_task
from app.schemas.green_api import WebhookMessage, MessageType as GreenMessageType
from app.schemas.deepseek import SentimentAnalysisResult, SentimentType


@pytest.mark.integration
@pytest.mark.asyncio
class TestFullWorkflow:
    """Test complete end-to-end workflows"""

    async def test_complete_guest_onboarding_workflow(
        self,
        async_test_session,
        sample_hotel,
        mock_green_api_client,
        mock_deepseek_client
    ):
        """Test complete guest onboarding from first message to welcome response"""

        # Setup: Create welcome trigger
        welcome_trigger = Trigger(
            hotel_id=sample_hotel.id,
            trigger_type=TriggerType.FIRST_MESSAGE,
            name="Welcome Message",
            conditions={"is_first_message": True},
            message_template="Welcome to {hotel_name}! How can we help you today?",
            is_active=True
        )
        async_test_session.add(welcome_trigger)
        await async_test_session.commit()

        # Mock Green API responses
        mock_green_api_client.send_text_message = AsyncMock(return_value={
            "idMessage": "msg_123",
            "statusMessage": "sent"
        })

        # Mock DeepSeek sentiment analysis
        mock_deepseek_client.analyze_sentiment = AsyncMock(return_value=
            SentimentAnalysisResult(
                sentiment=SentimentType.POSITIVE,
                confidence=0.8,
                requires_attention=False,
                reasoning="Friendly greeting message"
            )
        )

        # Simulate incoming webhook message
        webhook_data = WebhookMessage(
            typeWebhook="incomingMessageReceived",
            instanceData={
                "idInstance": sample_hotel.green_api_instance_id,
                "wid": f"{sample_hotel.whatsapp_number}@c.us",
                "typeInstance": "whatsapp"
            },
            timestamp=int(datetime.utcnow().timestamp()),
            idMessage="incoming_msg_123",
            senderData={
                "chatId": "1234567890@c.us",
                "sender": "1234567890@c.us",
                "senderName": "John Doe"
            },
            messageData={
                "typeMessage": GreenMessageType.TEXT_MESSAGE,
                "textMessageData": {
                    "textMessage": "Hello, I need help with my reservation"
                }
            }
        )

        # Process the workflow
        with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
            mock_get_client.return_value = mock_green_api_client

            # Process incoming message
            result = await process_incoming_message_task(
                hotel_id=str(sample_hotel.id),
                webhook_data=webhook_data.dict()
            )

        # Verify workflow completion
        assert result["status"] == "success"

        # Verify guest was created
        guest = await async_test_session.execute(
            select(Guest).where(Guest.phone == "+1234567890")
        )
        guest = guest.scalar_one_or_none()
        assert guest is not None
        assert guest.name == "John Doe"

        # Verify conversation was created
        conversation = await async_test_session.execute(
            select(Conversation).where(Conversation.guest_id == guest.id)
        )
        conversation = conversation.scalar_one_or_none()
        assert conversation is not None
        assert conversation.state == ConversationState.ACTIVE

        # Verify message was stored
        message = await async_test_session.execute(
            select(Message).where(Message.conversation_id == conversation.id)
        )
        message = message.scalar_one_or_none()
        assert message is not None
        assert message.content == "Hello, I need help with my reservation"
        assert message.message_type == MessageType.INCOMING

        # Verify sentiment analysis was performed
        sentiment = await async_test_session.execute(
            select(SentimentAnalysis).where(SentimentAnalysis.message_id == message.id)
        )
        sentiment = sentiment.scalar_one_or_none()
        assert sentiment is not None
        assert sentiment.sentiment == SentimentType.POSITIVE

        # Verify welcome message was sent
        mock_green_api_client.send_text_message.assert_called_once()
        call_args = mock_green_api_client.send_text_message.call_args
        assert "Welcome to Test Hotel" in call_args[1]["message"]

    async def test_negative_sentiment_escalation_workflow(
        self,
        async_test_session,
        sample_hotel,
        sample_guest,
        mock_green_api_client,
        mock_deepseek_client
    ):
        """Test workflow when negative sentiment triggers staff notification"""

        # Setup: Create conversation
        conversation = Conversation(
            hotel_id=sample_hotel.id,
            guest_id=sample_guest.id,
            state=ConversationState.ACTIVE,
            started_at=datetime.utcnow()
        )
        async_test_session.add(conversation)
        await async_test_session.commit()

        # Mock negative sentiment analysis
        mock_deepseek_client.analyze_sentiment = AsyncMock(return_value=
            SentimentAnalysisResult(
                sentiment=SentimentType.NEGATIVE,
                confidence=0.9,
                requires_attention=True,
                reasoning="Customer expressing frustration with service"
            )
        )

        # Mock notification sending
        with patch('app.services.staff_notification.send_staff_alert') as mock_alert:
            mock_alert.return_value = True

            # Simulate negative message
            webhook_data = WebhookMessage(
                typeWebhook="incomingMessageReceived",
                instanceData={
                    "idInstance": sample_hotel.green_api_instance_id,
                    "wid": f"{sample_hotel.whatsapp_number}@c.us",
                    "typeInstance": "whatsapp"
                },
                timestamp=int(datetime.utcnow().timestamp()),
                idMessage="negative_msg_123",
                senderData={
                    "chatId": f"{sample_guest.phone.replace('+', '')}@c.us",
                    "sender": f"{sample_guest.phone.replace('+', '')}@c.us",
                    "senderName": sample_guest.name
                },
                messageData={
                    "typeMessage": GreenMessageType.TEXT_MESSAGE,
                    "textMessageData": {
                        "textMessage": "This is terrible service! I'm very disappointed!"
                    }
                }
            )

            # Process the workflow
            with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
                mock_get_client.return_value = mock_green_api_client

                result = await process_incoming_message_task(
                    hotel_id=str(sample_hotel.id),
                    webhook_data=webhook_data.dict()
                )

        # Verify negative sentiment was detected
        assert result["status"] == "success"

        # Verify staff notification was created
        notification = await async_test_session.execute(
            select(StaffNotification).where(
                StaffNotification.hotel_id == sample_hotel.id
            )
        )
        notification = notification.scalar_one_or_none()
        assert notification is not None
        assert notification.notification_type == "negative_sentiment"

        # Verify alert was sent
        mock_alert.assert_called_once()

    async def test_trigger_based_messaging_workflow(
        self,
        async_test_session,
        sample_hotel,
        sample_guest,
        mock_green_api_client
    ):
        """Test trigger-based automated messaging workflow"""

        # Setup: Create time-based trigger
        trigger = Trigger(
            hotel_id=sample_hotel.id,
            trigger_type=TriggerType.TIME_BASED,
            name="Check-in Reminder",
            conditions={
                "hours_after_booking": 24,
                "booking_status": "confirmed"
            },
            message_template="Hi {guest_name}! Your check-in is tomorrow. Need any assistance?",
            is_active=True
        )
        async_test_session.add(trigger)

        # Create conversation
        conversation = Conversation(
            hotel_id=sample_hotel.id,
            guest_id=sample_guest.id,
            state=ConversationState.ACTIVE,
            started_at=datetime.utcnow() - timedelta(hours=25)
        )
        async_test_session.add(conversation)
        await async_test_session.commit()

        # Mock Green API response
        mock_green_api_client.send_text_message = AsyncMock(return_value={
            "idMessage": "trigger_msg_123",
            "statusMessage": "sent"
        })

        # Execute trigger
        trigger_engine = TriggerEngine(async_test_session)

        with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
            mock_get_client.return_value = mock_green_api_client

            result = await trigger_engine.execute_trigger(trigger, sample_guest)

        # Verify trigger execution
        assert result["success"] is True

        # Verify message was sent
        mock_green_api_client.send_text_message.assert_called_once()
        call_args = mock_green_api_client.send_text_message.call_args
        assert sample_guest.name in call_args[1]["message"]
        assert "check-in is tomorrow" in call_args[1]["message"]