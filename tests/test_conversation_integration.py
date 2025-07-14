"""
Integration tests for conversation handler system
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.message_handler import MessageHandler
from app.services.conversation_service import ConversationService
from app.services.conversation_state_machine import ConversationStateMachine
from app.services.escalation_service import EscalationService, EscalationType
from app.services.conversation_memory import ConversationMemory
from app.utils.intent_classifier import IntentClassifier, MessageIntent, IntentClassificationResult
from app.models.message import Message, Conversation, ConversationState, ConversationStatus, MessageType
from app.models.hotel import Hotel
from app.models.guest import Guest


class TestConversationIntegration:
    """Integration tests for complete conversation flows"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.flush = Mock()
        return db
    
    @pytest.fixture
    def mock_deepseek_client(self):
        """Create mock DeepSeek client"""
        client = Mock()
        client.generate_response = AsyncMock()
        return client
    
    @pytest.fixture
    def hotel_guest_setup(self):
        """Setup hotel and guest for testing"""
        hotel = Hotel(
            id=uuid4(),
            name="Test Hotel",
            phone_number="+1234567890",
            email="test@hotel.com"
        )
        
        guest = Guest(
            id=uuid4(),
            hotel_id=hotel.id,
            name="John Doe",
            phone_number="+1987654321",
            whatsapp_id="1987654321@c.us"
        )
        
        return hotel, guest
    
    @pytest.mark.asyncio
    async def test_complete_booking_inquiry_flow(self, mock_db, mock_deepseek_client, hotel_guest_setup):
        """Test complete booking inquiry conversation flow"""
        hotel, guest = hotel_guest_setup
        
        # Setup message handler
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        
        # Mock conversation creation
        conversation = Conversation(
            id=uuid4(),
            hotel_id=hotel.id,
            guest_id=guest.id,
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.GREETING,
            context={}
        )
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = conversation
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Mock AI response for booking inquiry
        mock_deepseek_client.generate_response.return_value = {
            'content': '{"intent": "booking_inquiry", "confidence": 0.9, "entities": {"dates": ["2024-01-15"]}, "sentiment_score": 0.2, "urgency_level": 2, "reasoning": "Guest asking about room availability"}'
        }
        
        # Create test message
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            hotel_id=hotel.id,
            guest_id=guest.id,
            message_type=MessageType.TEXT,
            content="Do you have any rooms available for January 15th?",
            direction="inbound"
        )
        
        # Process the message
        result = await message_handler.handle_incoming_message(
            hotel_id=hotel.id,
            guest_id=guest.id,
            message=message
        )
        
        # Verify results
        assert result.success is True
        assert result.intent_result.intent == MessageIntent.BOOKING_INQUIRY
        assert result.intent_result.confidence == 0.9
        assert 'dates' in result.intent_result.entities
        assert result.conversation is not None
    
    @pytest.mark.asyncio
    async def test_complaint_escalation_flow(self, mock_db, mock_deepseek_client, hotel_guest_setup):
        """Test complaint detection and escalation flow"""
        hotel, guest = hotel_guest_setup
        
        # Setup services
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        escalation_service = EscalationService(mock_db)
        
        # Mock conversation
        conversation = Conversation(
            id=uuid4(),
            hotel_id=hotel.id,
            guest_id=guest.id,
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.COLLECTING_INFO,
            context={'repeat_count': 2}
        )
        
        # Mock database
        mock_db.query.return_value.filter.return_value.first.return_value = conversation
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Mock AI response for complaint
        mock_deepseek_client.generate_response.return_value = {
            'content': '{"intent": "complaint", "confidence": 0.95, "sentiment_score": -0.8, "urgency_level": 4, "reasoning": "Strong negative sentiment and complaint keywords"}'
        }
        
        # Create complaint message
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            hotel_id=hotel.id,
            guest_id=guest.id,
            message_type=MessageType.TEXT,
            content="This is absolutely terrible! The room is dirty and I want a refund!",
            direction="inbound"
        )
        
        # Process the message
        result = await message_handler.handle_incoming_message(
            hotel_id=hotel.id,
            guest_id=guest.id,
            message=message
        )
        
        # Verify complaint was detected
        assert result.success is True
        assert result.intent_result.intent == MessageIntent.COMPLAINT
        assert result.intent_result.sentiment_score < -0.5
        assert result.intent_result.urgency_level >= 4
        
        # Test escalation triggers
        triggers = await escalation_service.evaluate_escalation_triggers(
            conversation, message.content, {
                'sentiment_score': result.intent_result.sentiment_score,
                'urgency_level': result.intent_result.urgency_level,
                'message_content': message.content
            }
        )
        
        assert EscalationType.NEGATIVE_SENTIMENT in triggers
        assert EscalationType.COMPLAINT_KEYWORDS in triggers
    
    @pytest.mark.asyncio
    async def test_emergency_immediate_escalation(self, mock_db, mock_deepseek_client, hotel_guest_setup):
        """Test emergency message immediate escalation"""
        hotel, guest = hotel_guest_setup
        
        # Setup message handler
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        
        # Mock conversation
        conversation = Conversation(
            id=uuid4(),
            hotel_id=hotel.id,
            guest_id=guest.id,
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.GREETING,
            context={}
        )
        
        # Mock database
        mock_db.query.return_value.filter.return_value.first.return_value = conversation
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Create emergency message
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            hotel_id=hotel.id,
            guest_id=guest.id,
            message_type=MessageType.TEXT,
            content="EMERGENCY! There's a fire in my room!",
            direction="inbound"
        )
        
        # Process the message
        result = await message_handler.handle_incoming_message(
            hotel_id=hotel.id,
            guest_id=guest.id,
            message=message
        )
        
        # Verify emergency handling
        assert result.success is True
        assert result.intent_result.intent == MessageIntent.EMERGENCY
        assert result.intent_result.urgency_level == 5
        assert 'emergency_escalation' in result.actions_taken
        
        # Verify state transition to escalated
        assert result.state_transition is not None
        assert result.state_transition.get('emergency') is True
    
    @pytest.mark.asyncio
    async def test_conversation_state_progression(self, mock_db, mock_deepseek_client, hotel_guest_setup):
        """Test conversation progressing through multiple states"""
        hotel, guest = hotel_guest_setup
        
        # Setup services
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        state_machine = ConversationStateMachine()
        
        # Create conversation
        conversation = Conversation(
            id=uuid4(),
            hotel_id=hotel.id,
            guest_id=guest.id,
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.GREETING,
            context={}
        )
        
        # Mock database
        mock_db.query.return_value.filter.return_value.first.return_value = conversation
        
        # Test progression: GREETING -> COLLECTING_INFO
        result1 = await state_machine.transition_to(
            conversation=conversation,
            target_state=ConversationState.COLLECTING_INFO,
            context={'message_content': 'I need help with my room'},
            reason="Guest responded to greeting"
        )
        
        assert result1.success is True
        assert result1.new_state == ConversationState.COLLECTING_INFO
        
        # Test progression: COLLECTING_INFO -> PROCESSING_REQUEST
        conversation.current_state = ConversationState.COLLECTING_INFO
        result2 = await state_machine.transition_to(
            conversation=conversation,
            target_state=ConversationState.PROCESSING_REQUEST,
            context={'sufficient_info': True},
            reason="Sufficient information collected"
        )
        
        assert result2.success is True
        assert result2.new_state == ConversationState.PROCESSING_REQUEST
        
        # Test progression: PROCESSING_REQUEST -> COMPLETED
        conversation.current_state = ConversationState.PROCESSING_REQUEST
        result3 = await state_machine.transition_to(
            conversation=conversation,
            target_state=ConversationState.COMPLETED,
            context={'request_resolved': True},
            reason="Request resolved successfully"
        )
        
        assert result3.success is True
        assert result3.new_state == ConversationState.COMPLETED
    
    @pytest.mark.asyncio
    async def test_context_memory_integration(self, mock_db, hotel_guest_setup):
        """Test conversation context and memory integration"""
        hotel, guest = hotel_guest_setup
        
        # Setup memory service with mock Redis
        with patch('app.services.conversation_memory.redis') as mock_redis:
            mock_redis_client = Mock()
            mock_redis_client.setex.return_value = True
            mock_redis_client.get.return_value = None
            mock_redis_client.keys.return_value = []
            mock_redis_client.delete.return_value = 1
            mock_redis_client.ping.return_value = True
            mock_redis.from_url.return_value = mock_redis_client
            
            memory_service = ConversationMemory()
            
            conversation_id = uuid4()
            
            # Test storing context
            success = await memory_service.store_context(
                conversation_id=conversation_id,
                key='guest_preferences',
                value={'language': 'en', 'room_type': 'deluxe'}
            )
            assert success is True
            
            # Test storing guest preferences
            success = await memory_service.store_guest_preferences(
                guest_id=guest.id,
                preferences={'dietary_restrictions': ['vegetarian'], 'floor_preference': 'high'}
            )
            assert success is True
            
            # Test creating conversation session
            success = await memory_service.create_conversation_session(
                conversation_id=conversation_id,
                session_data={'current_request': 'room_service', 'status': 'pending'}
            )
            assert success is True
    
    @pytest.mark.asyncio
    async def test_multi_message_conversation_flow(self, mock_db, mock_deepseek_client, hotel_guest_setup):
        """Test handling multiple messages in a conversation"""
        hotel, guest = hotel_guest_setup
        
        # Setup message handler
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        
        # Create conversation
        conversation = Conversation(
            id=uuid4(),
            hotel_id=hotel.id,
            guest_id=guest.id,
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.GREETING,
            context={'message_count': 0}
        )
        
        # Mock database
        mock_db.query.return_value.filter.return_value.first.return_value = conversation
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Message 1: Greeting
        mock_deepseek_client.generate_response.return_value = {
            'content': '{"intent": "greeting", "confidence": 0.9, "sentiment_score": 0.5, "urgency_level": 1, "reasoning": "Friendly greeting"}'
        }
        
        message1 = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            hotel_id=hotel.id,
            guest_id=guest.id,
            message_type=MessageType.TEXT,
            content="Hello! Good morning!",
            direction="inbound"
        )
        
        result1 = await message_handler.handle_incoming_message(
            hotel_id=hotel.id,
            guest_id=guest.id,
            message=message1
        )
        
        assert result1.success is True
        assert result1.intent_result.intent == MessageIntent.GREETING
        
        # Message 2: Service request
        mock_deepseek_client.generate_response.return_value = {
            'content': '{"intent": "request_service", "confidence": 0.85, "sentiment_score": 0.1, "urgency_level": 2, "reasoning": "Guest requesting room service"}'
        }
        
        message2 = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            hotel_id=hotel.id,
            guest_id=guest.id,
            message_type=MessageType.TEXT,
            content="Could I get some extra towels please?",
            direction="inbound"
        )
        
        result2 = await message_handler.handle_incoming_message(
            hotel_id=hotel.id,
            guest_id=guest.id,
            message=message2
        )
        
        assert result2.success is True
        assert result2.intent_result.intent == MessageIntent.REQUEST_SERVICE
        
        # Message 3: Satisfaction confirmation
        mock_deepseek_client.generate_response.return_value = {
            'content': '{"intent": "compliment", "confidence": 0.9, "sentiment_score": 0.8, "urgency_level": 1, "reasoning": "Guest expressing satisfaction"}'
        }
        
        message3 = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            hotel_id=hotel.id,
            guest_id=guest.id,
            message_type=MessageType.TEXT,
            content="Thank you so much! Perfect service!",
            direction="inbound"
        )
        
        result3 = await message_handler.handle_incoming_message(
            hotel_id=hotel.id,
            guest_id=guest.id,
            message=message3
        )
        
        assert result3.success is True
        assert result3.intent_result.intent == MessageIntent.COMPLIMENT
        assert result3.intent_result.sentiment_score > 0.5
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, mock_db, mock_deepseek_client, hotel_guest_setup):
        """Test error handling and recovery in conversation flow"""
        hotel, guest = hotel_guest_setup
        
        # Setup message handler
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        
        # Test AI service failure with fallback to rules
        mock_deepseek_client.generate_response.side_effect = Exception("AI service unavailable")
        
        # Mock conversation
        conversation = Conversation(
            id=uuid4(),
            hotel_id=hotel.id,
            guest_id=guest.id,
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.GREETING,
            context={}
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = conversation
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Create message that should be classified by rules
        message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            hotel_id=hotel.id,
            guest_id=guest.id,
            message_type=MessageType.TEXT,
            content="I want to book a room for next week",
            direction="inbound"
        )
        
        # Process message - should fallback to rule-based classification
        result = await message_handler.handle_incoming_message(
            hotel_id=hotel.id,
            guest_id=guest.id,
            message=message
        )
        
        # Should still succeed with rule-based classification
        assert result.success is True
        assert result.intent_result.intent == MessageIntent.BOOKING_INQUIRY
        assert result.intent_result.confidence > 0.0  # Rule-based confidence
    
    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self, mock_db, mock_deepseek_client, hotel_guest_setup):
        """Test handling concurrent messages from same conversation"""
        hotel, guest = hotel_guest_setup
        
        # Setup message handler
        message_handler = MessageHandler(mock_db, mock_deepseek_client)
        
        # Create conversation
        conversation = Conversation(
            id=uuid4(),
            hotel_id=hotel.id,
            guest_id=guest.id,
            status=ConversationStatus.ACTIVE,
            current_state=ConversationState.GREETING,
            context={}
        )
        
        # Mock database
        mock_db.query.return_value.filter.return_value.first.return_value = conversation
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Mock AI responses
        mock_deepseek_client.generate_response.return_value = {
            'content': '{"intent": "general_question", "confidence": 0.7, "sentiment_score": 0.0, "urgency_level": 1, "reasoning": "General inquiry"}'
        }
        
        # Create multiple messages
        messages = [
            Message(
                id=uuid4(),
                conversation_id=conversation.id,
                hotel_id=hotel.id,
                guest_id=guest.id,
                message_type=MessageType.TEXT,
                content=f"Message {i}",
                direction="inbound"
            )
            for i in range(3)
        ]
        
        # Process messages concurrently
        import asyncio
        tasks = [
            message_handler.handle_incoming_message(
                hotel_id=hotel.id,
                guest_id=guest.id,
                message=msg
            )
            for msg in messages
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        for result in results:
            assert not isinstance(result, Exception)
            assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
