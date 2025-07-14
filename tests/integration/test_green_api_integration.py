"""
Integration tests for Green API functionality
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation
from app.services.green_api_service import GreenAPIService
from app.services.webhook_processor import WebhookProcessor
from app.services.message_sender import MessageSender
from app.core.green_api_config import GreenAPIConfig


class TestGreenAPIIntegration:
    """Integration tests for Green API functionality"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        # This would typically use a test database
        # For now, we'll mock it
        return Mock(spec=Session)
    
    @pytest.fixture
    def test_hotel(self, db_session):
        """Create test hotel with Green API credentials"""
        hotel = Hotel(
            id="test-hotel-123",
            name="Test Hotel",
            green_api_instance_id="1234567890",
            green_api_token="test_token_123",
            green_api_webhook_token="webhook_secret_123"
        )
        return hotel
    
    @pytest.fixture
    def test_guest(self, test_hotel):
        """Create test guest"""
        guest = Guest(
            id="test-guest-123",
            hotel_id=test_hotel.id,
            phone_number="+1234567890",
            name="Test Guest"
        )
        return guest
    
    @pytest.fixture
    def test_conversation(self, test_hotel, test_guest):
        """Create test conversation"""
        conversation = Conversation(
            id="test-conv-123",
            hotel_id=test_hotel.id,
            guest_id=test_guest.id,
            status="active"
        )
        return conversation
    
    @pytest.mark.asyncio
    async def test_full_message_flow(self, db_session, test_hotel, test_guest, test_conversation):
        """Test complete message sending flow"""
        # Mock Green API response
        mock_response = {"idMessage": "green_api_msg_123"}
        
        with patch('app.services.green_api.GreenAPIClient') as MockClient:
            # Setup mock client
            mock_client_instance = AsyncMock()
            mock_client_instance.send_text_message.return_value = Mock(idMessage="green_api_msg_123")
            MockClient.return_value = mock_client_instance
            
            # Mock database operations
            db_session.add = Mock()
            db_session.flush = Mock()
            db_session.commit = Mock()
            
            # Create message sender
            sender = MessageSender(db_session)
            
            # Send message
            result = await sender.send_text_message(
                hotel=test_hotel,
                guest=test_guest,
                message="Hello from hotel!",
                priority="normal"
            )
            
            # Verify result
            assert result["status"] == "sent"
            assert "message_id" in result
            assert result["green_api_message_id"] == "green_api_msg_123"
            
            # Verify database operations
            db_session.add.assert_called()
            db_session.commit.assert_called()
            
            # Verify Green API client was called
            mock_client_instance.send_text_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_webhook_to_message_flow(self, db_session, test_hotel):
        """Test webhook processing to message creation flow"""
        # Mock webhook data
        webhook_data = {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {"idInstance": "1234567890"},
            "timestamp": 1640995200,
            "idMessage": "incoming_msg_123",
            "senderData": {
                "chatId": "1234567890@c.us",
                "sender": "1234567890@c.us",
                "senderName": "Test Guest"
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {"textMessage": "Hello, I need help!"}
            }
        }
        
        # Mock database operations
        db_session.query.return_value.filter.return_value.first.return_value = None  # No existing guest
        db_session.add = Mock()
        db_session.flush = Mock()
        db_session.commit = Mock()
        
        # Create webhook processor
        processor = WebhookProcessor(db_session)
        
        # Mock guest and conversation creation
        with patch.object(processor, '_get_or_create_guest') as mock_get_guest:
            with patch.object(processor, '_get_or_create_conversation') as mock_get_conv:
                mock_guest = Mock()
                mock_guest.id = "new-guest-123"
                mock_guest.phone_number = "1234567890"
                mock_get_guest.return_value = mock_guest
                
                mock_conversation = Mock()
                mock_conversation.id = "new-conv-123"
                mock_conversation.guest_id = mock_guest.id
                mock_conversation.guest = mock_guest
                mock_get_conv.return_value = mock_conversation
                
                # Mock async task
                with patch('app.tasks.process_incoming.process_incoming_message_task') as mock_task:
                    mock_task.delay = Mock()
                    
                    # Process webhook
                    from app.schemas.green_api import parse_webhook_data
                    parsed_webhook = parse_webhook_data(webhook_data["typeWebhook"], webhook_data)
                    
                    await processor._process_incoming_message(test_hotel, parsed_webhook)
                    
                    # Verify message was created
                    db_session.add.assert_called()
                    db_session.commit.assert_called()
                    
                    # Verify async processing was triggered
                    mock_task.delay.assert_called_once()
    
    def test_webhook_endpoint_integration(self, client):
        """Test webhook endpoint with full request flow"""
        # Mock database
        with patch('app.api.v1.endpoints.webhooks.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            # Mock hotel lookup
            mock_hotel = Mock()
            mock_hotel.id = "test-hotel-123"
            mock_hotel.green_api_webhook_token = "webhook_secret_123"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_hotel
            
            # Mock webhook processor
            with patch('app.api.v1.endpoints.webhooks.WebhookProcessor') as MockProcessor:
                mock_processor = Mock()
                MockProcessor.return_value = mock_processor
                
                # Mock webhook validation
                with patch('app.api.v1.endpoints.webhooks.validate_green_api_webhook', return_value=True):
                    # Mock webhook parsing
                    with patch('app.api.v1.endpoints.webhooks.parse_webhook_data') as mock_parse:
                        mock_webhook = Mock()
                        mock_parse.return_value = mock_webhook
                        
                        # Send webhook request
                        webhook_payload = {
                            "typeWebhook": "incomingMessageReceived",
                            "instanceData": {"idInstance": "1234567890"},
                            "timestamp": 1640995200,
                            "idMessage": "msg_123",
                            "senderData": {
                                "chatId": "1234567890@c.us",
                                "sender": "1234567890@c.us",
                                "senderName": "Test Guest"
                            },
                            "messageData": {
                                "typeMessage": "textMessage",
                                "textMessageData": {"textMessage": "Hello!"}
                            }
                        }
                        
                        response = client.post(
                            "/api/v1/webhooks/green-api",
                            json=webhook_payload,
                            headers={
                                "X-Green-API-Instance": "1234567890",
                                "X-Green-API-Signature": "test_signature"
                            }
                        )
                        
                        # Verify response
                        assert response.status_code == 200
                        assert response.json()["status"] == "received"
    
    @pytest.mark.asyncio
    async def test_green_api_service_integration(self, db_session, test_hotel):
        """Test Green API service integration"""
        # Mock Green API client
        with patch('app.services.green_api_service.get_green_api_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.send_text_message.return_value = Mock(idMessage="api_msg_123")
            mock_get_client.return_value = mock_client
            
            # Create service
            service = GreenAPIService(db_session)
            
            # Send message
            response = await service.send_text_message(
                hotel=test_hotel,
                phone_number="+1234567890",
                message="Test message from service"
            )
            
            # Verify response
            assert response.idMessage == "api_msg_123"
            
            # Verify client was called correctly
            mock_client.send_text_message.assert_called_once()
            call_args = mock_client.send_text_message.call_args[0][0]
            assert call_args.chatId == "1234567890@c.us"
            assert call_args.message == "Test message from service"
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, db_session, test_hotel, test_guest):
        """Test error handling in integration scenarios"""
        # Test Green API error
        with patch('app.services.green_api.GreenAPIClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.send_text_message.side_effect = httpx.HTTPStatusError(
                "API Error", request=Mock(), response=Mock(status_code=500)
            )
            MockClient.return_value = mock_client_instance
            
            # Mock database operations
            db_session.add = Mock()
            db_session.flush = Mock()
            db_session.commit = Mock()
            db_session.rollback = Mock()
            
            # Create message sender
            sender = MessageSender(db_session)
            
            # Attempt to send message (should fail)
            with pytest.raises(httpx.HTTPStatusError):
                await sender.send_text_message(
                    hotel=test_hotel,
                    guest=test_guest,
                    message="This will fail"
                )
            
            # Verify rollback was called
            db_session.rollback.assert_called()
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, db_session, test_hotel, test_guest):
        """Test rate limiting in integration scenario"""
        # Create config with very restrictive rate limits
        config = GreenAPIConfig(
            instance_id="1234567890",
            token="test_token"
        )
        config.rate_limit.requests_per_second = 1
        config.rate_limit.requests_per_minute = 2
        
        with patch('app.services.green_api_service.get_green_api_config', return_value=config):
            with patch('app.services.green_api.GreenAPIClient') as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.send_text_message.return_value = Mock(idMessage="rate_test_123")
                MockClient.return_value = mock_client_instance
                
                # Mock database operations
                db_session.add = Mock()
                db_session.flush = Mock()
                db_session.commit = Mock()
                
                # Create message sender
                sender = MessageSender(db_session)
                
                # Send multiple messages rapidly
                start_time = asyncio.get_event_loop().time()
                
                await sender.send_text_message(test_hotel, test_guest, "Message 1")
                await sender.send_text_message(test_hotel, test_guest, "Message 2")
                
                end_time = asyncio.get_event_loop().time()
                
                # Should take at least 1 second due to rate limiting
                assert end_time - start_time >= 0.9
    
    def test_conversation_api_integration(self, client):
        """Test conversation API endpoints integration"""
        with patch('app.api.v1.endpoints.conversations.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            # Mock hotel
            mock_hotel = Mock()
            mock_hotel.id = "test-hotel-123"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_hotel
            
            # Mock conversations
            mock_conversation = Mock()
            mock_conversation.id = "conv-123"
            mock_conversation.guest.id = "guest-123"
            mock_conversation.guest.name = "Test Guest"
            mock_conversation.guest.phone_number = "+1234567890"
            mock_conversation.status = "active"
            mock_conversation.created_at = "2023-01-01T00:00:00"
            mock_conversation.last_message_at = "2023-01-01T12:00:00"
            
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_conversation]
            
            # Mock last message
            mock_message = Mock()
            mock_message.content = "Hello from guest"
            mock_message.message_type.value = "incoming"
            mock_message.created_at = "2023-01-01T12:00:00"
            
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_message
            mock_db.query.return_value.filter.return_value.count.return_value = 0  # No unread messages
            
            # Test get conversations endpoint
            response = client.get("/api/v1/conversations/conversations?hotel_id=test-hotel-123")
            
            assert response.status_code == 200
            data = response.json()
            assert "conversations" in data
            assert len(data["conversations"]) == 1
            assert data["conversations"][0]["id"] == "conv-123"


if __name__ == "__main__":
    pytest.main([__file__])
