"""
Unit tests for webhook processor
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.webhook_processor import WebhookProcessor
from app.schemas.green_api import (
    IncomingMessageWebhook, OutgoingMessageStatusWebhook,
    StateInstanceWebhook, WebhookType, MessageType, MessageStatus,
    WebhookMessageData, WebhookSenderData
)
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType as DBMessageType
from app.models.notification import StaffNotification


class TestWebhookProcessor:
    """Test webhook processor functionality"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def processor(self, mock_db):
        """Create webhook processor instance"""
        return WebhookProcessor(mock_db)
    
    @pytest.fixture
    def mock_hotel(self):
        """Create mock hotel"""
        hotel = Mock(spec=Hotel)
        hotel.id = "hotel-123"
        hotel.name = "Test Hotel"
        return hotel
    
    @pytest.fixture
    def mock_guest(self):
        """Create mock guest"""
        guest = Mock(spec=Guest)
        guest.id = "guest-123"
        guest.phone_number = "+1234567890"
        guest.name = "Test Guest"
        return guest
    
    @pytest.fixture
    def mock_conversation(self, mock_guest):
        """Create mock conversation"""
        conversation = Mock(spec=Conversation)
        conversation.id = "conv-123"
        conversation.guest_id = mock_guest.id
        conversation.guest = mock_guest
        conversation.status = "active"
        return conversation
    
    @pytest.fixture
    def incoming_message_webhook(self):
        """Create incoming message webhook data"""
        return IncomingMessageWebhook(
            typeWebhook=WebhookType.INCOMING_MESSAGE,
            instanceData={"idInstance": "1234567890"},
            timestamp=1640995200,  # 2022-01-01 00:00:00
            idMessage="msg-123",
            senderData=WebhookSenderData(
                chatId="1234567890@c.us",
                chatName="Test Guest",
                sender="1234567890@c.us",
                senderName="Test Guest"
            ),
            messageData=WebhookMessageData(
                typeMessage=MessageType.TEXT,
                textMessageData={"textMessage": "Hello, I need help!"}
            )
        )
    
    @pytest.fixture
    def message_status_webhook(self):
        """Create message status webhook data"""
        return OutgoingMessageStatusWebhook(
            typeWebhook=WebhookType.MESSAGE_STATUS,
            instanceData={"idInstance": "1234567890"},
            timestamp=1640995200,
            idMessage="msg-456",
            status=MessageStatus.DELIVERED,
            chatId="1234567890@c.us"
        )
    
    @pytest.fixture
    def state_instance_webhook(self):
        """Create state instance webhook data"""
        return StateInstanceWebhook(
            typeWebhook=WebhookType.STATE_INSTANCE,
            instanceData={"idInstance": "1234567890"},
            timestamp=1640995200,
            stateInstance="authorized"
        )
    
    @pytest.mark.asyncio
    async def test_process_webhook_routing(self, processor, mock_hotel):
        """Test webhook routing to appropriate handlers"""
        # Test incoming message routing
        incoming_webhook = Mock()
        incoming_webhook.typeWebhook = WebhookType.INCOMING_MESSAGE
        incoming_webhook.timestamp = 1640995200
        
        with patch.object(processor, '_process_incoming_message', new_callable=AsyncMock) as mock_incoming:
            await processor.process_webhook(mock_hotel, incoming_webhook)
            mock_incoming.assert_called_once_with(mock_hotel, incoming_webhook)
        
        # Test message status routing
        status_webhook = Mock()
        status_webhook.typeWebhook = WebhookType.MESSAGE_STATUS
        status_webhook.timestamp = 1640995200
        
        with patch.object(processor, '_process_message_status', new_callable=AsyncMock) as mock_status:
            await processor.process_webhook(mock_hotel, status_webhook)
            mock_status.assert_called_once_with(mock_hotel, status_webhook)
    
    @pytest.mark.asyncio
    async def test_process_incoming_message_new_guest(
        self, 
        processor, 
        mock_hotel, 
        incoming_message_webhook
    ):
        """Test processing incoming message from new guest"""
        # Mock database queries
        processor.db.query.return_value.filter.return_value.first.return_value = None  # No existing guest
        processor.db.add = Mock()
        processor.db.flush = Mock()
        processor.db.commit = Mock()
        
        # Mock guest and conversation creation
        mock_guest = Mock(spec=Guest)
        mock_guest.id = "new-guest-123"
        mock_guest.phone_number = "1234567890"
        
        mock_conversation = Mock(spec=Conversation)
        mock_conversation.id = "new-conv-123"
        mock_conversation.guest_id = mock_guest.id
        mock_conversation.guest = mock_guest
        
        with patch.object(processor, '_get_or_create_guest', return_value=mock_guest):
            with patch.object(processor, '_get_or_create_conversation', return_value=mock_conversation):
                with patch('app.tasks.process_incoming.process_incoming_message_task') as mock_task:
                    mock_task.delay = Mock()
                    
                    await processor._process_incoming_message(mock_hotel, incoming_message_webhook)
                    
                    # Verify message was created
                    processor.db.add.assert_called()
                    processor.db.commit.assert_called()
                    
                    # Verify async task was queued
                    mock_task.delay.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_incoming_message_existing_guest(
        self,
        processor,
        mock_hotel,
        mock_guest,
        mock_conversation,
        incoming_message_webhook
    ):
        """Test processing incoming message from existing guest"""
        processor.db.add = Mock()
        processor.db.commit = Mock()
        
        with patch.object(processor, '_get_or_create_guest', return_value=mock_guest):
            with patch.object(processor, '_get_or_create_conversation', return_value=mock_conversation):
                with patch('app.tasks.process_incoming.process_incoming_message_task') as mock_task:
                    mock_task.delay = Mock()
                    
                    await processor._process_incoming_message(mock_hotel, incoming_message_webhook)
                    
                    # Verify message was created and committed
                    processor.db.add.assert_called()
                    processor.db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_message_status_existing_message(
        self,
        processor,
        mock_hotel,
        message_status_webhook
    ):
        """Test processing message status for existing message"""
        # Mock existing message
        mock_message = Mock(spec=Message)
        mock_message.id = "msg-456"
        mock_message.hotel_id = mock_hotel.id
        mock_message.set_metadata = Mock()
        
        processor.db.query.return_value.filter.return_value.first.return_value = mock_message
        processor.db.commit = Mock()
        
        with patch('app.tasks.send_message.update_message_status_task') as mock_task:
            mock_task.delay = Mock()
            
            await processor._process_message_status(mock_hotel, message_status_webhook)
            
            # Verify message metadata was updated
            assert mock_message.set_metadata.call_count == 2  # status and timestamp
            processor.db.commit.assert_called()
            
            # Verify async task was queued
            mock_task.delay.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_message_status_missing_message(
        self,
        processor,
        mock_hotel,
        message_status_webhook
    ):
        """Test processing message status for non-existent message"""
        # Mock no existing message
        processor.db.query.return_value.filter.return_value.first.return_value = None
        
        # Should not raise exception, just log warning
        await processor._process_message_status(mock_hotel, message_status_webhook)
    
    @pytest.mark.asyncio
    async def test_process_state_change_normal(
        self,
        processor,
        mock_hotel,
        state_instance_webhook
    ):
        """Test processing normal state change"""
        mock_hotel.set_setting = Mock()
        processor.db.commit = Mock()
        
        await processor._process_state_change(mock_hotel, state_instance_webhook)
        
        # Verify hotel settings were updated
        assert mock_hotel.set_setting.call_count == 2  # state and timestamp
        processor.db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_state_change_critical(
        self,
        processor,
        mock_hotel
    ):
        """Test processing critical state change"""
        # Create webhook with critical state
        critical_webhook = StateInstanceWebhook(
            typeWebhook=WebhookType.STATE_INSTANCE,
            instanceData={"idInstance": "1234567890"},
            timestamp=1640995200,
            stateInstance="notAuthorized"
        )
        
        mock_hotel.set_setting = Mock()
        processor.db.add = Mock()
        processor.db.commit = Mock()
        
        await processor._process_state_change(mock_hotel, critical_webhook)
        
        # Verify notification was created for critical state
        processor.db.add.assert_called()
        processor.db.commit.assert_called()
    
    def test_get_or_create_guest_existing(self, processor):
        """Test getting existing guest"""
        mock_guest = Mock(spec=Guest)
        mock_guest.id = "existing-guest"
        
        processor.db.query.return_value.filter.return_value.first.return_value = mock_guest
        
        mock_hotel = Mock()
        mock_sender_data = Mock()
        mock_sender_data.chatId = "1234567890@c.us"
        mock_sender_data.senderName = "Test Guest"
        
        result = processor._get_or_create_guest(mock_hotel, "1234567890", mock_sender_data)
        
        assert result == mock_guest
        processor.db.add.assert_not_called()
    
    def test_get_or_create_guest_new(self, processor):
        """Test creating new guest"""
        # Mock no existing guest
        processor.db.query.return_value.filter.return_value.first.return_value = None
        processor.db.add = Mock()
        processor.db.flush = Mock()
        
        mock_hotel = Mock()
        mock_hotel.id = "hotel-123"
        
        mock_sender_data = Mock()
        mock_sender_data.chatId = "1234567890@c.us"
        mock_sender_data.senderName = "Test Guest"
        
        result = processor._get_or_create_guest(mock_hotel, "1234567890", mock_sender_data)
        
        # Verify new guest was created
        processor.db.add.assert_called()
        processor.db.flush.assert_called()
        assert result.phone_number == "1234567890"
        assert result.hotel_id == mock_hotel.id
    
    def test_get_or_create_conversation_existing(self, processor, mock_hotel, mock_guest):
        """Test getting existing conversation"""
        mock_conversation = Mock(spec=Conversation)
        
        processor.db.query.return_value.filter.return_value.first.return_value = mock_conversation
        
        result = processor._get_or_create_conversation(mock_hotel, mock_guest)
        
        assert result == mock_conversation
        processor.db.add.assert_not_called()
    
    def test_get_or_create_conversation_new(self, processor, mock_hotel, mock_guest):
        """Test creating new conversation"""
        # Mock no existing conversation
        processor.db.query.return_value.filter.return_value.first.return_value = None
        processor.db.add = Mock()
        processor.db.flush = Mock()
        
        result = processor._get_or_create_conversation(mock_hotel, mock_guest)
        
        # Verify new conversation was created
        processor.db.add.assert_called()
        processor.db.flush.assert_called()
        assert result.hotel_id == mock_hotel.id
        assert result.guest_id == mock_guest.id
        assert result.status == 'active'


if __name__ == "__main__":
    pytest.main([__file__])
