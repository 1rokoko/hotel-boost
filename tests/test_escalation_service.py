"""
Unit tests for escalation service
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.escalation_service import (
    EscalationService, EscalationType, EscalationPriority, EscalationResult
)
from app.models.message import Conversation, ConversationState, ConversationStatus
from app.models.notification import StaffNotification


class TestEscalationService:
    """Test cases for EscalationService"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def escalation_service(self, mock_db):
        """Create escalation service with mocked dependencies"""
        service = EscalationService(mock_db)
        service.notification_service = Mock()
        service.notification_service.send_notification = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_conversation(self):
        """Create mock conversation"""
        conversation = Mock(spec=Conversation)
        conversation.id = uuid4()
        conversation.hotel_id = uuid4()
        conversation.guest_id = uuid4()
        conversation.current_state = ConversationState.GREETING
        conversation.status = ConversationStatus.ACTIVE
        conversation.last_message_at = datetime.utcnow()
        conversation.created_at = datetime.utcnow() - timedelta(minutes=30)
        conversation.context = {}
        conversation.get_context = Mock(return_value=None)
        conversation.set_context = Mock()
        conversation.escalate_conversation = Mock()
        return conversation
    
    @pytest.mark.asyncio
    async def test_evaluate_escalation_triggers_negative_sentiment(self, escalation_service, mock_conversation):
        """Test escalation trigger evaluation for negative sentiment"""
        message_content = "This is absolutely terrible!"
        context = {
            'sentiment_score': -0.8,
            'urgency_level': 2
        }
        
        triggers = await escalation_service.evaluate_escalation_triggers(
            mock_conversation, message_content, context
        )
        
        assert EscalationType.NEGATIVE_SENTIMENT in triggers
        assert EscalationType.COMPLAINT_KEYWORDS in triggers
    
    @pytest.mark.asyncio
    async def test_evaluate_escalation_triggers_emergency(self, escalation_service, mock_conversation):
        """Test escalation trigger evaluation for emergency"""
        message_content = "EMERGENCY! There's a fire in my room!"
        context = {
            'sentiment_score': -0.3,
            'urgency_level': 5
        }
        
        triggers = await escalation_service.evaluate_escalation_triggers(
            mock_conversation, message_content, context
        )
        
        assert EscalationType.EMERGENCY in triggers
        assert EscalationType.HIGH_URGENCY in triggers
    
    @pytest.mark.asyncio
    async def test_evaluate_escalation_triggers_repeated_requests(self, escalation_service, mock_conversation):
        """Test escalation trigger evaluation for repeated requests"""
        mock_conversation.get_context.return_value = 5  # repeat_count
        
        message_content = "I still need help with this"
        context = {
            'sentiment_score': 0.0,
            'urgency_level': 2
        }
        
        triggers = await escalation_service.evaluate_escalation_triggers(
            mock_conversation, message_content, context
        )
        
        assert EscalationType.REPEATED_REQUESTS in triggers
    
    @pytest.mark.asyncio
    async def test_evaluate_escalation_triggers_timeout(self, escalation_service, mock_conversation):
        """Test escalation trigger evaluation for timeout"""
        # Set last message time to 25 hours ago
        mock_conversation.last_message_at = datetime.utcnow() - timedelta(hours=25)
        
        message_content = "Hello, anyone there?"
        context = {
            'sentiment_score': 0.0,
            'urgency_level': 1
        }
        
        triggers = await escalation_service.evaluate_escalation_triggers(
            mock_conversation, message_content, context
        )
        
        assert EscalationType.TIMEOUT in triggers
    
    @pytest.mark.asyncio
    async def test_escalate_conversation_success(self, escalation_service, mock_conversation):
        """Test successful conversation escalation"""
        escalation_service.notification_service.send_notification.return_value = {
            'success': True,
            'channels_sent': ['email', 'webhook']
        }
        
        with patch.object(escalation_service, '_create_staff_notification') as mock_create_notification:
            mock_notification = Mock()
            mock_notification.id = uuid4()
            mock_create_notification.return_value = mock_notification
            
            result = await escalation_service.escalate_conversation(
                conversation=mock_conversation,
                escalation_type=EscalationType.NEGATIVE_SENTIMENT,
                reason="Very negative sentiment detected",
                context={'sentiment_score': -0.8}
            )
            
            assert isinstance(result, EscalationResult)
            assert result.success is True
            assert result.escalation_type == EscalationType.NEGATIVE_SENTIMENT
            assert result.priority == EscalationPriority.HIGH
            assert 'email' in result.notifications_sent
            assert 'webhook' in result.notifications_sent
            
            # Verify conversation was escalated
            mock_conversation.escalate_conversation.assert_called_once()
            mock_conversation.set_context.assert_called()
    
    @pytest.mark.asyncio
    async def test_escalate_conversation_with_manual_priority(self, escalation_service, mock_conversation):
        """Test escalation with manual priority override"""
        escalation_service.notification_service.send_notification.return_value = {
            'success': True,
            'channels_sent': ['email']
        }
        
        with patch.object(escalation_service, '_create_staff_notification') as mock_create_notification:
            mock_notification = Mock()
            mock_notification.id = uuid4()
            mock_create_notification.return_value = mock_notification
            
            result = await escalation_service.escalate_conversation(
                conversation=mock_conversation,
                escalation_type=EscalationType.MANUAL,
                reason="Manual escalation by staff",
                manual_priority=EscalationPriority.CRITICAL
            )
            
            assert result.success is True
            assert result.priority == EscalationPriority.CRITICAL
    
    @pytest.mark.asyncio
    async def test_escalate_conversation_failure(self, escalation_service, mock_conversation):
        """Test escalation failure handling"""
        # Mock exception during escalation
        mock_conversation.escalate_conversation.side_effect = Exception("Database error")
        
        result = await escalation_service.escalate_conversation(
            conversation=mock_conversation,
            escalation_type=EscalationType.EMERGENCY,
            reason="Emergency situation"
        )
        
        assert result.success is False
        assert "Database error" in result.error_message
    
    @pytest.mark.asyncio
    async def test_auto_escalate_if_needed_triggers_escalation(self, escalation_service, mock_conversation):
        """Test auto escalation when triggers are met"""
        message_content = "This is absolutely terrible! I want a refund!"
        context = {
            'sentiment_score': -0.9,
            'urgency_level': 4
        }
        
        with patch.object(escalation_service, 'escalate_conversation') as mock_escalate:
            mock_escalate.return_value = EscalationResult(
                success=True,
                escalation_type=EscalationType.NEGATIVE_SENTIMENT
            )
            
            result = await escalation_service.auto_escalate_if_needed(
                mock_conversation, message_content, context
            )
            
            assert result is not None
            assert result.success is True
            mock_escalate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_auto_escalate_if_needed_no_triggers(self, escalation_service, mock_conversation):
        """Test auto escalation when no triggers are met"""
        message_content = "Thank you for your help!"
        context = {
            'sentiment_score': 0.8,
            'urgency_level': 1
        }
        
        result = await escalation_service.auto_escalate_if_needed(
            mock_conversation, message_content, context
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_auto_escalate_if_needed_already_escalated(self, escalation_service, mock_conversation):
        """Test auto escalation skips already escalated conversations"""
        mock_conversation.status = ConversationStatus.ESCALATED
        
        message_content = "This is terrible!"
        context = {'sentiment_score': -0.9}
        
        result = await escalation_service.auto_escalate_if_needed(
            mock_conversation, message_content, context
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_auto_escalate_if_needed_disabled(self, escalation_service, mock_conversation):
        """Test auto escalation when disabled in config"""
        escalation_service.escalation_config['auto_escalation_enabled'] = False
        
        message_content = "This is terrible!"
        context = {'sentiment_score': -0.9}
        
        result = await escalation_service.auto_escalate_if_needed(
            mock_conversation, message_content, context
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create_staff_notification(self, escalation_service, mock_conversation):
        """Test staff notification creation"""
        escalation_service.db.add = Mock()
        escalation_service.db.flush = Mock()
        
        notification = await escalation_service._create_staff_notification(
            conversation=mock_conversation,
            escalation_type=EscalationType.COMPLAINT_KEYWORDS,
            priority=EscalationPriority.HIGH,
            reason="Complaint keywords detected",
            context={'sentiment_score': -0.6}
        )
        
        assert isinstance(notification, StaffNotification)
        assert notification.hotel_id == mock_conversation.hotel_id
        assert notification.guest_id == mock_conversation.guest_id
        assert notification.conversation_id == mock_conversation.id
        assert notification.notification_type == 'escalation'
        assert notification.urgency_level == 4  # HIGH priority maps to 4
        
        escalation_service.db.add.assert_called_once_with(notification)
        escalation_service.db.flush.assert_called_once()
    
    def test_check_timeout_escalation_true(self, escalation_service, mock_conversation):
        """Test timeout escalation check returns True"""
        # Set last message time to 25 hours ago
        mock_conversation.last_message_at = datetime.utcnow() - timedelta(hours=25)
        mock_conversation.status = ConversationStatus.ACTIVE
        
        result = escalation_service._check_timeout_escalation(mock_conversation)
        assert result is True
    
    def test_check_timeout_escalation_false(self, escalation_service, mock_conversation):
        """Test timeout escalation check returns False"""
        # Set last message time to 1 hour ago
        mock_conversation.last_message_at = datetime.utcnow() - timedelta(hours=1)
        mock_conversation.status = ConversationStatus.ACTIVE
        
        result = escalation_service._check_timeout_escalation(mock_conversation)
        assert result is False
    
    def test_get_highest_priority_escalation(self, escalation_service):
        """Test getting highest priority escalation type"""
        escalations = [
            EscalationType.REPEATED_REQUESTS,
            EscalationType.EMERGENCY,
            EscalationType.NEGATIVE_SENTIMENT
        ]
        
        highest = escalation_service._get_highest_priority_escalation(escalations)
        assert highest == EscalationType.EMERGENCY
    
    def test_generate_escalation_reason(self, escalation_service):
        """Test escalation reason generation"""
        test_cases = [
            (EscalationType.NEGATIVE_SENTIMENT, {'sentiment_score': -0.8}, "Negative sentiment detected (score: -0.8)"),
            (EscalationType.COMPLAINT_KEYWORDS, {}, "Complaint keywords detected in message"),
            (EscalationType.EMERGENCY, {}, "Emergency keywords detected"),
            (EscalationType.REPEATED_REQUESTS, {'repeat_count': 5}, "Repeated requests (5 times)"),
            (EscalationType.TIMEOUT, {}, "Conversation timeout exceeded"),
            (EscalationType.HIGH_URGENCY, {'urgency_level': 5}, "High urgency level (5)"),
            (EscalationType.MANUAL, {}, "Manual escalation requested")
        ]
        
        for escalation_type, context, expected_reason in test_cases:
            reason = escalation_service._generate_escalation_reason(escalation_type, context)
            assert reason == expected_reason
    
    def test_build_notification_message(self, escalation_service, mock_conversation):
        """Test notification message building"""
        # Mock related objects
        mock_guest = Mock()
        mock_guest.name = "John Doe"
        mock_hotel = Mock()
        mock_hotel.name = "Grand Hotel"
        
        mock_conversation.guest = mock_guest
        mock_conversation.hotel = mock_hotel
        mock_conversation.last_message_at = datetime(2024, 1, 15, 14, 30, 0)
        
        message = escalation_service._build_notification_message(
            conversation=mock_conversation,
            escalation_type=EscalationType.COMPLAINT_KEYWORDS,
            reason="Complaint keywords detected",
            context={}
        )
        
        assert "🚨 CONVERSATION ESCALATION ALERT" in message
        assert "Grand Hotel" in message
        assert "John Doe" in message
        assert str(mock_conversation.id) in message
        assert "Complaint Keywords" in message
        assert "Complaint keywords detected" in message
        assert "2024-01-15 14:30:00" in message
    
    def test_priority_to_urgency_mapping(self, escalation_service):
        """Test priority to urgency level mapping"""
        test_cases = [
            (EscalationPriority.LOW, 1),
            (EscalationPriority.MEDIUM, 2),
            (EscalationPriority.HIGH, 4),
            (EscalationPriority.CRITICAL, 5),
            (EscalationPriority.EMERGENCY, 5)
        ]
        
        for priority, expected_urgency in test_cases:
            urgency = escalation_service._priority_to_urgency(priority)
            assert urgency == expected_urgency


class TestEscalationResult:
    """Test cases for EscalationResult"""
    
    def test_escalation_result_success(self):
        """Test successful escalation result"""
        result = EscalationResult(
            success=True,
            escalation_id=uuid4(),
            escalation_type=EscalationType.EMERGENCY,
            priority=EscalationPriority.CRITICAL,
            notifications_sent=['email', 'sms']
        )
        
        assert result.success is True
        assert result.escalation_type == EscalationType.EMERGENCY
        assert result.priority == EscalationPriority.CRITICAL
        assert result.notifications_sent == ['email', 'sms']
        assert result.error_message is None
        assert result.timestamp is not None
    
    def test_escalation_result_failure(self):
        """Test failed escalation result"""
        result = EscalationResult(
            success=False,
            error_message="Escalation failed"
        )
        
        assert result.success is False
        assert result.escalation_id is None
        assert result.escalation_type is None
        assert result.priority is None
        assert result.notifications_sent == []
        assert result.error_message == "Escalation failed"
        assert result.timestamp is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
