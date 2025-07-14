"""
Unit tests for message handler
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from app.services.message_handler import MessageHandler, MessageHandlingResult
from app.services.conversation_service import ConversationService
from app.services.conversation_state_machine import ConversationStateMachine
from app.services.deepseek_client import DeepSeekClient
from app.utils.intent_classifier import IntentClassifier, MessageIntent, IntentClassificationResult
from app.models.message import Message, Conversation, ConversationState, ConversationStatus, MessageType


class TestMessageHandler:
    """Test cases for MessageHandler"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def mock_deepseek_client(self):
        """Create mock DeepSeek client"""
        client = Mock(spec=DeepSeekClient)
        client.generate_response = AsyncMock()
        return client
    
    @pytest.fixture
    def message_handler(self, mock_db, mock_deepseek_client):
        """Create message handler with mocked dependencies"""
        return MessageHandler(mock_db, mock_deepseek_client)
    
    @pytest.fixture
    def mock_message(self):
        """Create mock message"""
        message = Mock(spec=Message)
        message.id = uuid4()
        message.content = "Hello, I need help with my room"
        message.message_type = MessageType.TEXT
        message.created_at = datetime.utcnow()
        return message
    
    @pytest.fixture
    def mock_conversation(self):
        """Create mock conversation"""
        conversation = Mock(spec=Conversation)
        conversation.id = uuid4()
        conversation.hotel_id = uuid4()
        conversation.guest_id = uuid4()
        conversation.current_state = ConversationState.GREETING
        conversation.status = ConversationStatus.ACTIVE
        conversation.context = {}
        conversation.update_last_message_time = Mock()
        conversation.update_context = Mock()
        conversation.escalate_conversation = Mock()
        return conversation
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_success(self, message_handler, mock_message, mock_conversation):
        """Test successful message handling"""
        hotel_id = uuid4()
        guest_id = uuid4()
        
        # Mock dependencies
        with patch.object(message_handler.conversation_service, 'get_or_create_conversation', 
                         return_value=mock_conversation) as mock_get_conv:
            with patch.object(message_handler, 'classify_intent') as mock_classify:
                with patch.object(message_handler, '_process_normal_message') as mock_process:
                    with patch.object(message_handler, '_execute_intent_actions', 
                                     return_value=['action_taken']) as mock_actions:
                        with patch.object(message_handler, '_update_conversation_context') as mock_update:
                            
                            # Setup mocks
                            intent_result = IntentClassificationResult(
                                intent=MessageIntent.REQUEST_SERVICE,
                                confidence=0.8,
                                urgency_level=2
                            )
                            mock_classify.return_value = intent_result
                            mock_process.return_value = {'transition': 'success'}
                            
                            # Execute
                            result = await message_handler.handle_incoming_message(
                                hotel_id=hotel_id,
                                guest_id=guest_id,
                                message=mock_message
                            )
                            
                            # Verify
                            assert isinstance(result, MessageHandlingResult)
                            assert result.success is True
                            assert result.conversation == mock_conversation
                            assert result.intent_result == intent_result
                            assert 'action_taken' in result.actions_taken
                            
                            # Verify method calls
                            mock_get_conv.assert_called_once_with(hotel_id=hotel_id, guest_id=guest_id)
                            mock_conversation.update_last_message_time.assert_called_once()
                            mock_classify.assert_called_once()
                            mock_process.assert_called_once()
                            mock_actions.assert_called_once()
                            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_emergency(self, message_handler, mock_message, mock_conversation):
        """Test emergency message handling"""
        hotel_id = uuid4()
        guest_id = uuid4()
        
        # Mock emergency message
        mock_message.content = "EMERGENCY! There's a fire in my room!"
        
        with patch.object(message_handler.conversation_service, 'get_or_create_conversation', 
                         return_value=mock_conversation):
            with patch.object(message_handler, 'classify_intent') as mock_classify:
                with patch.object(message_handler, '_handle_emergency') as mock_emergency:
                    with patch.object(message_handler, '_update_conversation_context'):
                        
                        # Setup mocks
                        intent_result = IntentClassificationResult(
                            intent=MessageIntent.EMERGENCY,
                            confidence=1.0,
                            urgency_level=5
                        )
                        mock_classify.return_value = intent_result
                        mock_emergency.return_value = {'emergency': True}
                        
                        # Execute
                        result = await message_handler.handle_incoming_message(
                            hotel_id=hotel_id,
                            guest_id=guest_id,
                            message=mock_message
                        )
                        
                        # Verify
                        assert result.success is True
                        assert result.intent_result.intent == MessageIntent.EMERGENCY
                        assert 'emergency_escalation' in result.actions_taken
                        mock_emergency.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_incoming_message_failure(self, message_handler, mock_message):
        """Test message handling failure"""
        hotel_id = uuid4()
        guest_id = uuid4()
        
        # Mock service failure
        with patch.object(message_handler.conversation_service, 'get_or_create_conversation', 
                         side_effect=Exception("Database error")):
            
            result = await message_handler.handle_incoming_message(
                hotel_id=hotel_id,
                guest_id=guest_id,
                message=mock_message
            )
            
            assert result.success is False
            assert "Database error" in result.error_message
    
    @pytest.mark.asyncio
    async def test_classify_intent_with_context(self, message_handler, mock_message, mock_conversation):
        """Test intent classification with conversation context"""
        # Setup conversation context
        mock_conversation.context = {'previous_intent': 'booking_inquiry'}
        
        # Mock recent messages query
        mock_recent_messages = [
            Mock(content="Hello", message_type=MessageType.TEXT),
            Mock(content="I need a room", message_type=MessageType.TEXT)
        ]
        
        with patch.object(message_handler.db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_recent_messages
            
            with patch.object(message_handler.intent_classifier, 'classify_intent') as mock_classify:
                mock_classify.return_value = IntentClassificationResult(
                    intent=MessageIntent.BOOKING_INQUIRY,
                    confidence=0.8
                )
                
                result = await message_handler.classify_intent(mock_message, mock_conversation)
                
                # Verify context was built correctly
                call_args = mock_classify.call_args
                context = call_args[1]['context']
                
                assert 'conversation_state' in context
                assert 'conversation_context' in context
                assert 'recent_messages' in context
                assert len(context['recent_messages']) == 2
    
    @pytest.mark.asyncio
    async def test_process_normal_message_with_transition(self, message_handler, mock_conversation, mock_message):
        """Test normal message processing with state transition"""
        intent_result = IntentClassificationResult(
            intent=MessageIntent.COLLECTING_INFO,
            confidence=0.8,
            sentiment_score=0.2
        )
        
        with patch.object(message_handler.state_validator, 'suggest_transition', 
                         return_value=ConversationState.PROCESSING_REQUEST) as mock_suggest:
            with patch.object(message_handler.state_machine, 'transition_to') as mock_transition:
                from app.schemas.conversation import StateTransitionResponse
                
                transition_response = Mock()
                transition_response.success = True
                transition_response.previous_state = ConversationState.GREETING
                transition_response.new_state = ConversationState.PROCESSING_REQUEST
                transition_response.message = "Transition successful"
                
                mock_transition.return_value = transition_response
                
                result = await message_handler._process_normal_message(
                    mock_conversation, mock_message, intent_result
                )
                
                assert result is not None
                assert result['success'] is True
                assert result['new_state'] == ConversationState.PROCESSING_REQUEST.value
                
                mock_suggest.assert_called_once()
                mock_transition.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_emergency_escalation(self, message_handler, mock_conversation):
        """Test emergency escalation handling"""
        intent_result = IntentClassificationResult(
            intent=MessageIntent.EMERGENCY,
            confidence=1.0,
            keywords=['fire', 'emergency']
        )
        
        with patch.object(message_handler.state_machine, 'transition_to') as mock_transition:
            transition_response = Mock()
            transition_response.success = True
            transition_response.previous_state = ConversationState.GREETING
            transition_response.new_state = ConversationState.ESCALATED
            
            mock_transition.return_value = transition_response
            
            result = await message_handler._handle_emergency(mock_conversation, intent_result)
            
            assert result['emergency'] is True
            assert result['success'] is True
            assert result['new_state'] == ConversationState.ESCALATED.value
            
            # Verify transition was called with emergency context
            call_args = mock_transition.call_args
            assert call_args[1]['target_state'] == ConversationState.ESCALATED
            assert call_args[1]['reason'] == "Emergency detected in message"
    
    @pytest.mark.asyncio
    async def test_update_conversation_context(self, message_handler, mock_conversation, mock_message):
        """Test conversation context updates"""
        intent_result = IntentClassificationResult(
            intent=MessageIntent.REQUEST_SERVICE,
            confidence=0.8,
            sentiment_score=-0.2,
            urgency_level=3,
            entities={'room_number': '205'}
        )
        
        # Mock existing context
        mock_conversation.get_context = Mock(side_effect=lambda key, default=None: {
            'message_count': 5,
            'entities': {'guest_name': 'John'},
            'intent_history': [{'intent': 'greeting', 'timestamp': '2024-01-01T10:00:00'}]
        }.get(key, default))
        
        await message_handler._update_conversation_context(
            mock_conversation, mock_message, intent_result
        )
        
        # Verify update_context was called
        mock_conversation.update_context.assert_called_once()
        
        # Check the context updates
        call_args = mock_conversation.update_context.call_args[0][0]
        
        assert call_args['last_intent'] == MessageIntent.REQUEST_SERVICE.value
        assert call_args['last_confidence'] == 0.8
        assert call_args['last_sentiment'] == -0.2
        assert call_args['last_urgency'] == 3
        assert call_args['message_count'] == 6  # Incremented
        assert 'entities' in call_args
        assert 'intent_history' in call_args
    
    @pytest.mark.asyncio
    async def test_execute_intent_actions(self, message_handler, mock_conversation):
        """Test intent action execution"""
        # Test high urgency
        intent_result = IntentClassificationResult(
            intent=MessageIntent.COMPLAINT,
            confidence=0.9,
            sentiment_score=-0.8,
            urgency_level=5
        )
        
        # Mock conversation context
        mock_conversation.get_context = Mock(return_value=2)  # repeat_count
        mock_conversation.set_context = Mock()
        
        actions = await message_handler._execute_intent_actions(mock_conversation, intent_result)
        
        assert 'high_priority_flagged' in actions
        assert 'negative_sentiment_detected' in actions
        
        # Verify repeat count was incremented
        mock_conversation.set_context.assert_called_with('repeat_count', 3)
    
    @pytest.mark.asyncio
    async def test_route_to_handler_emergency(self, message_handler, mock_conversation, mock_message):
        """Test routing to emergency handler"""
        actions = await message_handler.route_to_handler(
            MessageIntent.EMERGENCY, mock_conversation, mock_message
        )
        
        assert 'emergency_protocol_activated' in actions
        assert 'staff_notified_immediately' in actions
    
    @pytest.mark.asyncio
    async def test_route_to_handler_complaint(self, message_handler, mock_conversation, mock_message):
        """Test routing to complaint handler"""
        actions = await message_handler.route_to_handler(
            MessageIntent.COMPLAINT, mock_conversation, mock_message
        )
        
        assert 'complaint_logged' in actions
        assert 'manager_notified' in actions
    
    @pytest.mark.asyncio
    async def test_route_to_handler_service_request(self, message_handler, mock_conversation, mock_message):
        """Test routing to service request handler"""
        actions = await message_handler.route_to_handler(
            MessageIntent.REQUEST_SERVICE, mock_conversation, mock_message
        )
        
        assert 'service_request_created' in actions
        assert 'housekeeping_notified' in actions


class TestMessageHandlingResult:
    """Test cases for MessageHandlingResult"""
    
    def test_message_handling_result_success(self):
        """Test successful message handling result"""
        conversation = Mock()
        intent_result = Mock()
        
        result = MessageHandlingResult(
            success=True,
            conversation=conversation,
            intent_result=intent_result,
            actions_taken=['action1', 'action2']
        )
        
        assert result.success is True
        assert result.conversation == conversation
        assert result.intent_result == intent_result
        assert result.actions_taken == ['action1', 'action2']
        assert result.error_message is None
        assert result.timestamp is not None
    
    def test_message_handling_result_failure(self):
        """Test failed message handling result"""
        result = MessageHandlingResult(
            success=False,
            error_message="Processing failed"
        )
        
        assert result.success is False
        assert result.conversation is None
        assert result.intent_result is None
        assert result.actions_taken == []
        assert result.error_message == "Processing failed"
        assert result.timestamp is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
