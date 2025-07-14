"""
Escalation service for managing conversation escalations to staff
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from enum import Enum
import structlog

from app.models.message import Conversation, ConversationState, ConversationStatus
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.notification import StaffNotification
from app.services.staff_notification import StaffNotificationService
from app.utils.escalation_rules import EscalationRuleEngine, EscalationTrigger
from app.core.logging import get_logger

logger = get_logger(__name__)


class EscalationType(str, Enum):
    """Types of escalations"""
    NEGATIVE_SENTIMENT = "negative_sentiment"
    COMPLAINT_KEYWORDS = "complaint_keywords"
    REPEATED_REQUESTS = "repeated_requests"
    EMERGENCY = "emergency"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    HIGH_URGENCY = "high_urgency"


class EscalationPriority(str, Enum):
    """Escalation priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class EscalationResult:
    """Result of escalation processing"""
    
    def __init__(
        self,
        success: bool,
        escalation_id: Optional[UUID] = None,
        escalation_type: Optional[EscalationType] = None,
        priority: Optional[EscalationPriority] = None,
        notifications_sent: List[str] = None,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.escalation_id = escalation_id
        self.escalation_type = escalation_type
        self.priority = priority
        self.notifications_sent = notifications_sent or []
        self.error_message = error_message
        self.timestamp = datetime.utcnow()


class EscalationService:
    """
    Service for managing conversation escalations with configurable rules
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.rule_engine = EscalationRuleEngine()
        self.notification_service = StaffNotificationService(db)
        self.escalation_config = self._load_escalation_config()
    
    def _load_escalation_config(self) -> Dict[str, Any]:
        """Load escalation configuration"""
        return {
            'sentiment_threshold': -0.5,
            'repeat_threshold': 3,
            'timeout_hours': 24,
            'auto_escalation_enabled': True,
            'notification_channels': ['email', 'webhook'],
            'priority_mapping': {
                EscalationType.EMERGENCY: EscalationPriority.EMERGENCY,
                EscalationType.NEGATIVE_SENTIMENT: EscalationPriority.HIGH,
                EscalationType.COMPLAINT_KEYWORDS: EscalationPriority.HIGH,
                EscalationType.REPEATED_REQUESTS: EscalationPriority.MEDIUM,
                EscalationType.TIMEOUT: EscalationPriority.MEDIUM,
                EscalationType.HIGH_URGENCY: EscalationPriority.HIGH,
                EscalationType.MANUAL: EscalationPriority.MEDIUM
            }
        }
    
    async def evaluate_escalation_triggers(
        self,
        conversation: Conversation,
        message_content: str,
        context: Dict[str, Any]
    ) -> List[EscalationType]:
        """
        Evaluate if conversation should be escalated
        
        Args:
            conversation: Conversation object
            message_content: Latest message content
            context: Message context (sentiment, intent, etc.)
            
        Returns:
            List[EscalationType]: Triggered escalation types
        """
        triggered_escalations = []
        
        try:
            # Check sentiment-based escalation
            sentiment_score = context.get('sentiment_score', 0)
            if sentiment_score < self.escalation_config['sentiment_threshold']:
                triggered_escalations.append(EscalationType.NEGATIVE_SENTIMENT)
            
            # Check for complaint keywords
            if self.rule_engine.check_complaint_keywords(message_content):
                triggered_escalations.append(EscalationType.COMPLAINT_KEYWORDS)
            
            # Check for emergency keywords
            if self.rule_engine.check_emergency_keywords(message_content):
                triggered_escalations.append(EscalationType.EMERGENCY)
            
            # Check for repeated requests
            repeat_count = conversation.get_context('repeat_count', 0)
            if repeat_count >= self.escalation_config['repeat_threshold']:
                triggered_escalations.append(EscalationType.REPEATED_REQUESTS)
            
            # Check for timeout
            if self._check_timeout_escalation(conversation):
                triggered_escalations.append(EscalationType.TIMEOUT)
            
            # Check urgency level
            urgency_level = context.get('urgency_level', 1)
            if urgency_level >= 4:
                triggered_escalations.append(EscalationType.HIGH_URGENCY)
            
            logger.debug("Escalation triggers evaluated",
                        conversation_id=conversation.id,
                        triggered_escalations=[t.value for t in triggered_escalations],
                        sentiment_score=sentiment_score,
                        urgency_level=urgency_level)
            
            return triggered_escalations
            
        except Exception as e:
            logger.error("Failed to evaluate escalation triggers",
                        conversation_id=conversation.id,
                        error=str(e))
            return []
    
    async def escalate_conversation(
        self,
        conversation: Conversation,
        escalation_type: EscalationType,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        manual_priority: Optional[EscalationPriority] = None
    ) -> EscalationResult:
        """
        Escalate conversation to staff
        
        Args:
            conversation: Conversation to escalate
            escalation_type: Type of escalation
            reason: Reason for escalation
            context: Additional context
            manual_priority: Manual priority override
            
        Returns:
            EscalationResult: Escalation result
        """
        try:
            # Determine priority
            priority = manual_priority or self.escalation_config['priority_mapping'].get(
                escalation_type, EscalationPriority.MEDIUM
            )
            
            # Update conversation state
            conversation.escalate_conversation()
            conversation.set_context('escalation_type', escalation_type.value)
            conversation.set_context('escalation_reason', reason)
            conversation.set_context('escalation_priority', priority.value)
            conversation.set_context('escalated_at', datetime.utcnow().isoformat())
            
            # Create staff notification
            notification = await self._create_staff_notification(
                conversation=conversation,
                escalation_type=escalation_type,
                priority=priority,
                reason=reason,
                context=context or {}
            )
            
            # Send notifications
            notifications_sent = await self._send_escalation_notifications(
                conversation=conversation,
                notification=notification,
                escalation_type=escalation_type,
                priority=priority
            )
            
            # Log escalation
            logger.info("Conversation escalated",
                       conversation_id=conversation.id,
                       escalation_type=escalation_type.value,
                       priority=priority.value,
                       reason=reason,
                       notifications_sent=len(notifications_sent))
            
            return EscalationResult(
                success=True,
                escalation_id=notification.id,
                escalation_type=escalation_type,
                priority=priority,
                notifications_sent=notifications_sent
            )
            
        except Exception as e:
            logger.error("Failed to escalate conversation",
                        conversation_id=conversation.id,
                        escalation_type=escalation_type.value,
                        error=str(e))
            
            return EscalationResult(
                success=False,
                error_message=str(e)
            )
    
    async def auto_escalate_if_needed(
        self,
        conversation: Conversation,
        message_content: str,
        context: Dict[str, Any]
    ) -> Optional[EscalationResult]:
        """
        Automatically escalate conversation if triggers are met
        
        Args:
            conversation: Conversation object
            message_content: Latest message content
            context: Message context
            
        Returns:
            Optional[EscalationResult]: Escalation result if escalated
        """
        if not self.escalation_config['auto_escalation_enabled']:
            return None
        
        # Skip if already escalated
        if conversation.status == ConversationStatus.ESCALATED:
            return None
        
        # Evaluate triggers
        triggered_escalations = await self.evaluate_escalation_triggers(
            conversation, message_content, context
        )
        
        if not triggered_escalations:
            return None
        
        # Use highest priority escalation type
        escalation_type = self._get_highest_priority_escalation(triggered_escalations)
        
        # Generate reason
        reason = self._generate_escalation_reason(escalation_type, context)
        
        # Escalate
        return await self.escalate_conversation(
            conversation=conversation,
            escalation_type=escalation_type,
            reason=reason,
            context=context
        )
    
    async def _create_staff_notification(
        self,
        conversation: Conversation,
        escalation_type: EscalationType,
        priority: EscalationPriority,
        reason: str,
        context: Dict[str, Any]
    ) -> StaffNotification:
        """Create staff notification for escalation"""
        
        # Build notification message
        message = self._build_notification_message(
            conversation, escalation_type, reason, context
        )
        
        # Create notification
        notification = StaffNotification(
            hotel_id=conversation.hotel_id,
            guest_id=conversation.guest_id,
            conversation_id=conversation.id,
            notification_type='escalation',
            urgency_level=self._priority_to_urgency(priority),
            message=message,
            metadata={
                'escalation_type': escalation_type.value,
                'priority': priority.value,
                'reason': reason,
                'context': context
            }
        )
        
        self.db.add(notification)
        self.db.flush()
        
        return notification
    
    async def _send_escalation_notifications(
        self,
        conversation: Conversation,
        notification: StaffNotification,
        escalation_type: EscalationType,
        priority: EscalationPriority
    ) -> List[str]:
        """Send escalation notifications through configured channels"""
        
        notifications_sent = []
        
        try:
            # Send through notification service
            result = await self.notification_service.send_notification(
                notification=notification,
                channels=self.escalation_config['notification_channels'],
                priority=priority.value
            )
            
            if result.get('success'):
                notifications_sent.extend(result.get('channels_sent', []))
            
        except Exception as e:
            logger.error("Failed to send escalation notifications",
                        notification_id=notification.id,
                        error=str(e))
        
        return notifications_sent
    
    def _check_timeout_escalation(self, conversation: Conversation) -> bool:
        """Check if conversation has timed out"""
        timeout_hours = self.escalation_config['timeout_hours']
        timeout_threshold = datetime.utcnow() - timedelta(hours=timeout_hours)
        
        return (conversation.last_message_at < timeout_threshold and 
                conversation.status == ConversationStatus.ACTIVE)
    
    def _get_highest_priority_escalation(
        self, 
        escalations: List[EscalationType]
    ) -> EscalationType:
        """Get highest priority escalation type"""
        priority_order = [
            EscalationType.EMERGENCY,
            EscalationType.NEGATIVE_SENTIMENT,
            EscalationType.COMPLAINT_KEYWORDS,
            EscalationType.HIGH_URGENCY,
            EscalationType.REPEATED_REQUESTS,
            EscalationType.TIMEOUT
        ]
        
        for escalation_type in priority_order:
            if escalation_type in escalations:
                return escalation_type
        
        return escalations[0] if escalations else EscalationType.MANUAL
    
    def _generate_escalation_reason(
        self, 
        escalation_type: EscalationType, 
        context: Dict[str, Any]
    ) -> str:
        """Generate human-readable escalation reason"""
        
        reason_templates = {
            EscalationType.NEGATIVE_SENTIMENT: f"Negative sentiment detected (score: {context.get('sentiment_score', 'unknown')})",
            EscalationType.COMPLAINT_KEYWORDS: "Complaint keywords detected in message",
            EscalationType.EMERGENCY: "Emergency keywords detected",
            EscalationType.REPEATED_REQUESTS: f"Repeated requests ({context.get('repeat_count', 'multiple')} times)",
            EscalationType.TIMEOUT: "Conversation timeout exceeded",
            EscalationType.HIGH_URGENCY: f"High urgency level ({context.get('urgency_level', 'unknown')})",
            EscalationType.MANUAL: "Manual escalation requested"
        }
        
        return reason_templates.get(escalation_type, "Escalation triggered")
    
    def _build_notification_message(
        self,
        conversation: Conversation,
        escalation_type: EscalationType,
        reason: str,
        context: Dict[str, Any]
    ) -> str:
        """Build notification message for staff"""
        
        guest_name = conversation.guest.name if conversation.guest else "Unknown Guest"
        hotel_name = conversation.hotel.name if conversation.hotel else "Unknown Hotel"
        
        message = f"""
🚨 CONVERSATION ESCALATION ALERT

Hotel: {hotel_name}
Guest: {guest_name}
Conversation ID: {conversation.id}

Escalation Type: {escalation_type.value.replace('_', ' ').title()}
Reason: {reason}

Current State: {conversation.current_state.value}
Last Message: {conversation.last_message_at.strftime('%Y-%m-%d %H:%M:%S')}

Please review and take appropriate action.
        """.strip()
        
        return message
    
    def _priority_to_urgency(self, priority: EscalationPriority) -> int:
        """Convert priority to urgency level (1-5)"""
        mapping = {
            EscalationPriority.LOW: 1,
            EscalationPriority.MEDIUM: 2,
            EscalationPriority.HIGH: 4,
            EscalationPriority.CRITICAL: 5,
            EscalationPriority.EMERGENCY: 5
        }
        return mapping.get(priority, 3)


# Export service
__all__ = ['EscalationService', 'EscalationType', 'EscalationPriority', 'EscalationResult']
