"""
Conversation logging service for analytics and monitoring
"""

import json
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from enum import Enum
import structlog

from app.models.message import Conversation, ConversationState, ConversationStatus, Message
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.core.logging import get_logger

logger = get_logger(__name__)


class LogEventType(str, Enum):
    """Types of conversation log events"""
    CONVERSATION_STARTED = "conversation_started"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    STATE_TRANSITION = "state_transition"
    INTENT_CLASSIFIED = "intent_classified"
    ESCALATION_TRIGGERED = "escalation_triggered"
    CONVERSATION_COMPLETED = "conversation_completed"
    CONTEXT_UPDATED = "context_updated"
    ERROR_OCCURRED = "error_occurred"


class ConversationLogEntry:
    """Represents a conversation log entry"""
    
    def __init__(
        self,
        conversation_id: UUID,
        event_type: LogEventType,
        event_data: Dict[str, Any],
        hotel_id: UUID,
        guest_id: Optional[UUID] = None,
        message_id: Optional[UUID] = None,
        correlation_id: Optional[str] = None
    ):
        self.conversation_id = conversation_id
        self.event_type = event_type
        self.event_data = event_data
        self.hotel_id = hotel_id
        self.guest_id = guest_id
        self.message_id = message_id
        self.correlation_id = correlation_id
        self.timestamp = datetime.utcnow()
        self.log_id = f"{conversation_id}_{event_type.value}_{int(self.timestamp.timestamp())}"


class ConversationLogger:
    """
    Service for logging conversation events and analytics
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.structured_logger = get_logger(__name__)
    
    def log_conversation_started(
        self,
        conversation: Conversation,
        initial_message: Optional[Message] = None,
        correlation_id: Optional[str] = None
    ):
        """Log conversation start event"""
        
        event_data = {
            'conversation_id': str(conversation.id),
            'hotel_id': str(conversation.hotel_id),
            'guest_id': str(conversation.guest_id),
            'initial_state': conversation.current_state.value,
            'status': conversation.status.value,
            'started_at': conversation.created_at.isoformat()
        }
        
        if initial_message:
            event_data['initial_message'] = {
                'id': str(initial_message.id),
                'type': initial_message.message_type.value,
                'content_length': len(initial_message.content),
                'has_media': bool(initial_message.media_url)
            }
        
        self._log_event(
            conversation_id=conversation.id,
            event_type=LogEventType.CONVERSATION_STARTED,
            event_data=event_data,
            hotel_id=conversation.hotel_id,
            guest_id=conversation.guest_id,
            message_id=initial_message.id if initial_message else None,
            correlation_id=correlation_id
        )
    
    def log_message_received(
        self,
        conversation: Conversation,
        message: Message,
        processing_result: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log incoming message event"""
        
        event_data = {
            'message_id': str(message.id),
            'message_type': message.message_type.value,
            'content_length': len(message.content),
            'has_media': bool(message.media_url),
            'conversation_state': conversation.current_state.value,
            'received_at': message.created_at.isoformat()
        }
        
        if processing_result:
            event_data['processing_result'] = {
                'intent': processing_result.get('intent'),
                'confidence': processing_result.get('confidence'),
                'sentiment_score': processing_result.get('sentiment_score'),
                'urgency_level': processing_result.get('urgency_level'),
                'entities_found': len(processing_result.get('entities', {})),
                'actions_taken': processing_result.get('actions_taken', [])
            }
        
        self._log_event(
            conversation_id=conversation.id,
            event_type=LogEventType.MESSAGE_RECEIVED,
            event_data=event_data,
            hotel_id=conversation.hotel_id,
            guest_id=conversation.guest_id,
            message_id=message.id,
            correlation_id=correlation_id
        )
    
    def log_state_transition(
        self,
        conversation: Conversation,
        from_state: ConversationState,
        to_state: ConversationState,
        trigger: str,
        reason: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        """Log state transition event"""
        
        event_data = {
            'from_state': from_state.value,
            'to_state': to_state.value,
            'trigger': trigger,
            'reason': reason,
            'transition_time': datetime.utcnow().isoformat()
        }
        
        if context:
            event_data['context'] = {
                'sentiment_score': context.get('sentiment_score'),
                'urgency_level': context.get('urgency_level'),
                'intent': context.get('intent'),
                'has_entities': bool(context.get('entities'))
            }
        
        self._log_event(
            conversation_id=conversation.id,
            event_type=LogEventType.STATE_TRANSITION,
            event_data=event_data,
            hotel_id=conversation.hotel_id,
            guest_id=conversation.guest_id,
            correlation_id=correlation_id
        )
    
    def log_intent_classification(
        self,
        conversation: Conversation,
        message: Message,
        intent: str,
        confidence: float,
        entities: Optional[Dict[str, Any]] = None,
        sentiment_score: Optional[float] = None,
        correlation_id: Optional[str] = None
    ):
        """Log intent classification event"""
        
        event_data = {
            'message_id': str(message.id),
            'intent': intent,
            'confidence': confidence,
            'sentiment_score': sentiment_score,
            'entities_count': len(entities) if entities else 0,
            'classified_at': datetime.utcnow().isoformat()
        }
        
        if entities:
            event_data['entity_types'] = list(entities.keys())
        
        self._log_event(
            conversation_id=conversation.id,
            event_type=LogEventType.INTENT_CLASSIFIED,
            event_data=event_data,
            hotel_id=conversation.hotel_id,
            guest_id=conversation.guest_id,
            message_id=message.id,
            correlation_id=correlation_id
        )
    
    def log_escalation_triggered(
        self,
        conversation: Conversation,
        escalation_type: str,
        reason: str,
        urgency_level: int,
        notification_id: Optional[UUID] = None,
        correlation_id: Optional[str] = None
    ):
        """Log escalation event"""
        
        event_data = {
            'escalation_type': escalation_type,
            'reason': reason,
            'urgency_level': urgency_level,
            'notification_id': str(notification_id) if notification_id else None,
            'escalated_at': datetime.utcnow().isoformat(),
            'conversation_duration_minutes': self._calculate_conversation_duration(conversation)
        }
        
        self._log_event(
            conversation_id=conversation.id,
            event_type=LogEventType.ESCALATION_TRIGGERED,
            event_data=event_data,
            hotel_id=conversation.hotel_id,
            guest_id=conversation.guest_id,
            correlation_id=correlation_id
        )
    
    def log_conversation_completed(
        self,
        conversation: Conversation,
        completion_reason: str,
        final_state: ConversationState,
        correlation_id: Optional[str] = None
    ):
        """Log conversation completion event"""
        
        # Calculate conversation metrics
        message_count = self.db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).count()
        
        duration_minutes = self._calculate_conversation_duration(conversation)
        
        event_data = {
            'completion_reason': completion_reason,
            'final_state': final_state.value,
            'final_status': conversation.status.value,
            'message_count': message_count,
            'duration_minutes': duration_minutes,
            'completed_at': datetime.utcnow().isoformat(),
            'started_at': conversation.created_at.isoformat()
        }
        
        # Add context summary
        if conversation.context:
            event_data['context_summary'] = {
                'context_keys': list(conversation.context.keys()),
                'has_collected_info': 'collected_info' in conversation.context,
                'has_preferences': 'guest_preferences' in conversation.context,
                'escalation_count': conversation.context.get('escalation_count', 0)
            }
        
        self._log_event(
            conversation_id=conversation.id,
            event_type=LogEventType.CONVERSATION_COMPLETED,
            event_data=event_data,
            hotel_id=conversation.hotel_id,
            guest_id=conversation.guest_id,
            correlation_id=correlation_id
        )
    
    def log_error(
        self,
        conversation_id: UUID,
        error_type: str,
        error_message: str,
        error_context: Optional[Dict[str, Any]] = None,
        hotel_id: Optional[UUID] = None,
        guest_id: Optional[UUID] = None,
        correlation_id: Optional[str] = None
    ):
        """Log error event"""
        
        event_data = {
            'error_type': error_type,
            'error_message': error_message,
            'error_context': error_context or {},
            'occurred_at': datetime.utcnow().isoformat()
        }
        
        self._log_event(
            conversation_id=conversation_id,
            event_type=LogEventType.ERROR_OCCURRED,
            event_data=event_data,
            hotel_id=hotel_id,
            guest_id=guest_id,
            correlation_id=correlation_id
        )
    
    def _log_event(
        self,
        conversation_id: UUID,
        event_type: LogEventType,
        event_data: Dict[str, Any],
        hotel_id: Optional[UUID] = None,
        guest_id: Optional[UUID] = None,
        message_id: Optional[UUID] = None,
        correlation_id: Optional[str] = None
    ):
        """Internal method to log events"""
        
        log_entry = ConversationLogEntry(
            conversation_id=conversation_id,
            event_type=event_type,
            event_data=event_data,
            hotel_id=hotel_id,
            guest_id=guest_id,
            message_id=message_id,
            correlation_id=correlation_id
        )
        
        # Log to structured logger
        self.structured_logger.info(
            "Conversation event logged",
            event_type=event_type.value,
            conversation_id=str(conversation_id),
            hotel_id=str(hotel_id) if hotel_id else None,
            guest_id=str(guest_id) if guest_id else None,
            message_id=str(message_id) if message_id else None,
            correlation_id=correlation_id,
            log_id=log_entry.log_id,
            timestamp=log_entry.timestamp.isoformat(),
            event_data=event_data
        )
    
    def _calculate_conversation_duration(self, conversation: Conversation) -> float:
        """Calculate conversation duration in minutes"""
        if conversation.last_message_at and conversation.created_at:
            duration = conversation.last_message_at - conversation.created_at
            return duration.total_seconds() / 60.0
        return 0.0
    
    def get_conversation_analytics(
        self,
        hotel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get conversation analytics for a hotel"""
        
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Get conversations in date range
        conversations = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel_id,
            Conversation.created_at >= start_date,
            Conversation.created_at <= end_date
        ).all()
        
        if not conversations:
            return {
                'total_conversations': 0,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
        
        # Calculate metrics
        total_conversations = len(conversations)
        completed_conversations = len([c for c in conversations if c.status == ConversationStatus.CLOSED])
        escalated_conversations = len([c for c in conversations if c.status == ConversationStatus.ESCALATED])
        
        # State distribution
        state_distribution = {}
        for state in ConversationState:
            count = len([c for c in conversations if c.current_state == state])
            state_distribution[state.value] = count
        
        # Calculate average duration
        durations = [self._calculate_conversation_duration(c) for c in conversations]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            'total_conversations': total_conversations,
            'completed_conversations': completed_conversations,
            'escalated_conversations': escalated_conversations,
            'completion_rate': completed_conversations / total_conversations if total_conversations > 0 else 0,
            'escalation_rate': escalated_conversations / total_conversations if total_conversations > 0 else 0,
            'avg_duration_minutes': round(avg_duration, 2),
            'state_distribution': state_distribution,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }


# Export logger
__all__ = ['ConversationLogger', 'LogEventType', 'ConversationLogEntry']
