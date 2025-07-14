"""
Unit tests for conversation state machine
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from uuid import uuid4

from app.services.conversation_state_machine import ConversationStateMachine
from app.models.message import Conversation, ConversationState, ConversationStatus
from app.schemas.conversation import StateTransitionResponse


class TestConversationStateMachine:
    """Test cases for ConversationStateMachine"""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine instance"""
        return ConversationStateMachine()
    
    @pytest.fixture
    def mock_conversation(self):
        """Create mock conversation"""
        conversation = Mock(spec=Conversation)
        conversation.id = uuid4()
        conversation.current_state = ConversationState.GREETING
        conversation.status = ConversationStatus.ACTIVE
        conversation.context = {}
        conversation.update_last_message_time = Mock()
        conversation.update_context = Mock()
        conversation.set_context = Mock()
        return conversation
    
    def test_get_allowed_transitions_from_greeting(self, state_machine):
        """Test allowed transitions from greeting state"""
        allowed = state_machine.get_allowed_transitions(ConversationState.GREETING)
        
        assert ConversationState.COLLECTING_INFO in allowed
        assert ConversationState.ESCALATED in allowed
        assert ConversationState.COMPLETED in allowed
    
    def test_get_allowed_transitions_from_collecting_info(self, state_machine):
        """Test allowed transitions from collecting info state"""
        allowed = state_machine.get_allowed_transitions(ConversationState.COLLECTING_INFO)
        
        assert ConversationState.PROCESSING_REQUEST in allowed
        assert ConversationState.ESCALATED in allowed
        assert ConversationState.COMPLETED in allowed
    
    def test_can_transition_valid(self, state_machine, mock_conversation):
        """Test valid transition check"""
        # Should allow greeting to collecting_info
        can_transition = state_machine.can_transition(
            mock_conversation,
            ConversationState.COLLECTING_INFO
        )
        
        assert can_transition is True
    
    def test_can_transition_invalid(self, state_machine, mock_conversation):
        """Test invalid transition check"""
        # Should not allow greeting to waiting_response directly
        can_transition = state_machine.can_transition(
            mock_conversation,
            ConversationState.WAITING_RESPONSE
        )
        
        assert can_transition is False
    
    @pytest.mark.asyncio
    async def test_transition_to_valid_state(self, state_machine, mock_conversation):
        """Test successful state transition"""
        result = await state_machine.transition_to(
            conversation=mock_conversation,
            target_state=ConversationState.COLLECTING_INFO,
            context={'test': 'data'},
            reason="Test transition"
        )
        
        assert isinstance(result, StateTransitionResponse)
        assert result.success is True
        assert result.previous_state == ConversationState.GREETING
        assert result.new_state == ConversationState.COLLECTING_INFO
        
        # Verify conversation was updated
        assert mock_conversation.current_state == ConversationState.COLLECTING_INFO
        mock_conversation.update_last_message_time.assert_called_once()
        mock_conversation.update_context.assert_called_once_with({'test': 'data'})
    
    @pytest.mark.asyncio
    async def test_transition_to_invalid_state(self, state_machine, mock_conversation):
        """Test failed state transition"""
        result = await state_machine.transition_to(
            conversation=mock_conversation,
            target_state=ConversationState.WAITING_RESPONSE,
            reason="Invalid transition"
        )
        
        assert isinstance(result, StateTransitionResponse)
        assert result.success is False
        assert result.previous_state == ConversationState.GREETING
        assert result.new_state == ConversationState.GREETING  # Should remain unchanged
        
        # Verify conversation was not updated
        assert mock_conversation.current_state == ConversationState.GREETING
        mock_conversation.update_last_message_time.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_transition_to_escalated_updates_status(self, state_machine, mock_conversation):
        """Test transition to escalated state updates conversation status"""
        result = await state_machine.transition_to(
            conversation=mock_conversation,
            target_state=ConversationState.ESCALATED,
            reason="Emergency escalation"
        )
        
        assert result.success is True
        assert mock_conversation.current_state == ConversationState.ESCALATED
        assert mock_conversation.status == ConversationStatus.ESCALATED
    
    @pytest.mark.asyncio
    async def test_transition_to_completed_updates_status(self, state_machine, mock_conversation):
        """Test transition to completed state updates conversation status"""
        result = await state_machine.transition_to(
            conversation=mock_conversation,
            target_state=ConversationState.COMPLETED,
            reason="Conversation completed"
        )
        
        assert result.success is True
        assert mock_conversation.current_state == ConversationState.COMPLETED
        assert mock_conversation.status == ConversationStatus.CLOSED
    
    def test_check_negative_sentiment_condition(self, state_machine, mock_conversation):
        """Test negative sentiment condition check"""
        context = {'sentiment_score': -0.8}
        
        result = state_machine._check_negative_sentiment(mock_conversation, context)
        assert result is True
        
        context = {'sentiment_score': 0.2}
        result = state_machine._check_negative_sentiment(mock_conversation, context)
        assert result is False
    
    def test_check_sufficient_info_condition(self, state_machine, mock_conversation):
        """Test sufficient info condition check"""
        # Mock conversation context
        mock_conversation.get_context = Mock(return_value={'field1': 'value1', 'field2': 'value2'})
        
        context = {'required_fields': ['field1', 'field2']}
        result = state_machine._check_sufficient_info(mock_conversation, context)
        assert result is True
        
        context = {'required_fields': ['field1', 'field2', 'field3']}
        result = state_machine._check_sufficient_info(mock_conversation, context)
        assert result is False
    
    def test_check_escalation_triggers_sentiment(self, state_machine, mock_conversation):
        """Test escalation triggers for negative sentiment"""
        context = {'sentiment_score': -0.8}
        
        result = state_machine._check_escalation_triggers(mock_conversation, context)
        assert result is True
    
    def test_check_escalation_triggers_keywords(self, state_machine, mock_conversation):
        """Test escalation triggers for keywords"""
        context = {'message_content': 'This is terrible, I want a refund!'}
        
        result = state_machine._check_escalation_triggers(mock_conversation, context)
        assert result is True
    
    def test_check_escalation_triggers_repeat_count(self, state_machine, mock_conversation):
        """Test escalation triggers for repeat count"""
        mock_conversation.get_context = Mock(return_value=5)
        context = {}
        
        result = state_machine._check_escalation_triggers(mock_conversation, context)
        assert result is True
    
    def test_check_request_resolved_condition(self, state_machine, mock_conversation):
        """Test request resolved condition"""
        context = {'request_resolved': True}
        result = state_machine._check_request_resolved(mock_conversation, context)
        assert result is True
        
        context = {'request_resolved': False}
        result = state_machine._check_request_resolved(mock_conversation, context)
        assert result is False
    
    def test_check_guest_satisfied_condition(self, state_machine, mock_conversation):
        """Test guest satisfied condition"""
        context = {'message_content': 'Thank you so much, this is perfect!'}
        result = state_machine._check_guest_satisfied(mock_conversation, context)
        assert result is True
        
        context = {'message_content': 'This is still not working properly'}
        result = state_machine._check_guest_satisfied(mock_conversation, context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_transition_with_exception_handling(self, state_machine, mock_conversation):
        """Test transition with exception handling"""
        # Mock an exception during transition
        mock_conversation.update_context.side_effect = Exception("Database error")
        
        result = await state_machine.transition_to(
            conversation=mock_conversation,
            target_state=ConversationState.COLLECTING_INFO,
            context={'test': 'data'},
            reason="Test transition"
        )
        
        assert result.success is False
        assert "Database error" in result.message
        assert result.previous_state == ConversationState.GREETING
        assert result.new_state == ConversationState.GREETING
    
    def test_state_machine_initialization(self, state_machine):
        """Test state machine initialization"""
        assert state_machine.transitions is not None
        assert len(state_machine.transitions) > 0
        
        # Check that all states have some transitions defined
        for state in ConversationState:
            if state in state_machine.transitions:
                assert len(state_machine.transitions[state]) > 0


class TestStateTransitionConditions:
    """Test cases for state transition conditions"""
    
    @pytest.fixture
    def state_machine(self):
        return ConversationStateMachine()
    
    @pytest.fixture
    def mock_conversation(self):
        conversation = Mock(spec=Conversation)
        conversation.id = uuid4()
        conversation.get_context = Mock(return_value=None)
        return conversation
    
    def test_negative_sentiment_threshold(self, state_machine, mock_conversation):
        """Test negative sentiment threshold values"""
        test_cases = [
            (-0.9, True),   # Very negative
            (-0.6, True),   # Negative
            (-0.4, False),  # Slightly negative
            (0.0, False),   # Neutral
            (0.5, False),   # Positive
        ]
        
        for sentiment_score, expected in test_cases:
            context = {'sentiment_score': sentiment_score}
            result = state_machine._check_negative_sentiment(mock_conversation, context)
            assert result == expected, f"Failed for sentiment score {sentiment_score}"
    
    def test_escalation_keywords_detection(self, state_machine, mock_conversation):
        """Test escalation keyword detection"""
        test_cases = [
            ("I want to speak to the manager", True),
            ("This is absolutely terrible", True),
            ("I demand a refund immediately", True),
            ("The room is nice and clean", False),
            ("Thank you for your help", False),
            ("Could you please help me", False),
        ]
        
        for message, expected in test_cases:
            context = {'message_content': message}
            result = state_machine._check_escalation_triggers(mock_conversation, context)
            assert result == expected, f"Failed for message: {message}"
    
    def test_satisfaction_keywords_detection(self, state_machine, mock_conversation):
        """Test satisfaction keyword detection"""
        test_cases = [
            ("Thank you so much!", True),
            ("This is perfect", True),
            ("Great service", True),
            ("I appreciate your help", True),
            ("This is terrible", False),
            ("Still having problems", False),
        ]
        
        for message, expected in test_cases:
            context = {'message_content': message}
            result = state_machine._check_guest_satisfied(mock_conversation, context)
            assert result == expected, f"Failed for message: {message}"


if __name__ == "__main__":
    pytest.main([__file__])
