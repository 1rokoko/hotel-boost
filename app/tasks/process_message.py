"""
Celery tasks for processing incoming messages
"""

from typing import Dict, Any, Optional
from uuid import UUID
from celery import current_app as celery_app
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.message_handler import MessageHandler
from app.services.deepseek_client import DeepSeekClient
from app.models.message import Message
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.core.logging import get_logger
from app.core.config import settings
from app.decorators.retry_decorator import retry_celery_tasks
from app.tasks.dead_letter_handler import dlq_handler
from app.utils.circuit_breaker import get_circuit_breaker
from app.core.circuit_breaker_config import get_circuit_breaker_config, CircuitBreakerNames

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
@retry_celery_tasks(max_retries=3, base_delay=60.0)
def process_incoming_message_task(
    self,
    hotel_id: str,
    guest_id: str,
    message_id: str,
    message_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process incoming message asynchronously
    
    Args:
        hotel_id: Hotel ID
        guest_id: Guest ID  
        message_id: Message ID
        message_data: Message data
        
    Returns:
        Dict with processing results
    """
    try:
        # Get database session
        db: Session = next(get_db())
        
        # Get message from database
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise ValueError(f"Message not found: {message_id}")
        
        # Initialize DeepSeek client
        deepseek_client = DeepSeekClient()
        
        # Initialize message handler
        message_handler = MessageHandler(db, deepseek_client)
        
        # Process the message
        result = await message_handler.handle_incoming_message(
            hotel_id=UUID(hotel_id),
            guest_id=UUID(guest_id),
            message=message
        )
        
        # Commit database changes
        db.commit()
        
        logger.info("Message processed successfully",
                   task_id=self.request.id,
                   message_id=message_id,
                   hotel_id=hotel_id,
                   guest_id=guest_id,
                   success=result.success)
        
        return {
            'success': result.success,
            'conversation_id': str(result.conversation.id) if result.conversation else None,
            'intent': result.intent_result.intent.value if result.intent_result else None,
            'confidence': result.intent_result.confidence if result.intent_result else None,
            'actions_taken': result.actions_taken,
            'state_transition': result.state_transition,
            'error_message': result.error_message
        }
        
    except Exception as exc:
        logger.error("Message processing failed",
                    task_id=self.request.id,
                    message_id=message_id,
                    error=str(exc),
                    retry_count=self.request.retries)

        # Add to DLQ if max retries exceeded
        if self.request.retries >= self.max_retries:
            try:
                # Add to dead letter queue for manual processing
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    loop.run_until_complete(dlq_handler.add_to_dlq(
                        message_data={
                            "hotel_id": hotel_id,
                            "guest_id": guest_id,
                            "message_id": message_id,
                            "message_data": message_data,
                            "task_id": self.request.id
                        },
                        error=exc,
                        message_type="incoming_message_processing",
                        max_retries=3
                    ))
                finally:
                    loop.close()

                logger.warning("Message added to DLQ after max retries",
                             task_id=self.request.id,
                             message_id=message_id)

            except Exception as dlq_error:
                logger.error("Failed to add message to DLQ",
                           task_id=self.request.id,
                           message_id=message_id,
                           dlq_error=str(dlq_error))

        # Retry on failure
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

        # Final failure
        return {
            'success': False,
            'error_message': str(exc),
            'final_failure': True
        }
    
    finally:
        if 'db' in locals():
            db.close()


@celery_app.task(bind=True, max_retries=2)
def classify_message_intent_task(
    self,
    message_id: str,
    message_content: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Classify message intent asynchronously
    
    Args:
        message_id: Message ID
        message_content: Message content
        context: Optional context
        
    Returns:
        Dict with classification results
    """
    try:
        # Initialize DeepSeek client
        deepseek_client = DeepSeekClient()
        
        # Initialize intent classifier
        from app.utils.intent_classifier import IntentClassifier
        classifier = IntentClassifier(deepseek_client)
        
        # Classify intent
        result = await classifier.classify_intent(
            message=message_content,
            context=context or {}
        )
        
        logger.info("Intent classified successfully",
                   task_id=self.request.id,
                   message_id=message_id,
                   intent=result.intent.value,
                   confidence=result.confidence)
        
        return {
            'success': True,
            'intent': result.intent.value,
            'confidence': result.confidence,
            'entities': result.entities,
            'sentiment_score': result.sentiment_score,
            'urgency_level': result.urgency_level,
            'reasoning': result.reasoning
        }
        
    except Exception as exc:
        logger.error("Intent classification failed",
                    task_id=self.request.id,
                    message_id=message_id,
                    error=str(exc))
        
        # Retry on failure
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        
        return {
            'success': False,
            'error_message': str(exc),
            'intent': 'unknown',
            'confidence': 0.0
        }


@celery_app.task(bind=True)
def update_conversation_state_task(
    self,
    conversation_id: str,
    target_state: str,
    context: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update conversation state asynchronously
    
    Args:
        conversation_id: Conversation ID
        target_state: Target state
        context: Optional context
        reason: Optional reason
        
    Returns:
        Dict with transition results
    """
    try:
        # Get database session
        db: Session = next(get_db())
        
        # Get conversation
        from app.models.message import Conversation, ConversationState
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Initialize state machine
        from app.services.conversation_state_machine import ConversationStateMachine
        state_machine = ConversationStateMachine()
        
        # Execute transition
        result = await state_machine.transition_to(
            conversation=conversation,
            target_state=ConversationState(target_state),
            context=context or {},
            reason=reason
        )
        
        # Commit changes
        db.commit()
        
        logger.info("Conversation state updated",
                   task_id=self.request.id,
                   conversation_id=conversation_id,
                   previous_state=result.previous_state.value,
                   new_state=result.new_state.value,
                   success=result.success)
        
        return {
            'success': result.success,
            'previous_state': result.previous_state.value,
            'new_state': result.new_state.value,
            'message': result.message,
            'timestamp': result.timestamp.isoformat()
        }
        
    except Exception as exc:
        logger.error("State transition failed",
                    task_id=self.request.id,
                    conversation_id=conversation_id,
                    error=str(exc))
        
        return {
            'success': False,
            'error_message': str(exc)
        }
    
    finally:
        if 'db' in locals():
            db.close()


@celery_app.task(bind=True)
def escalate_conversation_task(
    self,
    conversation_id: str,
    escalation_reason: str,
    urgency_level: int = 3,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Escalate conversation to staff
    
    Args:
        conversation_id: Conversation ID
        escalation_reason: Reason for escalation
        urgency_level: Urgency level (1-5)
        metadata: Optional metadata
        
    Returns:
        Dict with escalation results
    """
    try:
        # Get database session
        db: Session = next(get_db())
        
        # Get conversation
        from app.models.message import Conversation, ConversationState
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Escalate conversation
        conversation.escalate_conversation()
        
        # Create staff notification
        from app.models.notification import StaffNotification
        notification = StaffNotification(
            hotel_id=conversation.hotel_id,
            guest_id=conversation.guest_id,
            conversation_id=conversation.id,
            notification_type='escalation',
            urgency_level=urgency_level,
            message=escalation_reason,
            metadata=metadata or {}
        )
        
        db.add(notification)
        db.commit()
        
        logger.info("Conversation escalated",
                   task_id=self.request.id,
                   conversation_id=conversation_id,
                   reason=escalation_reason,
                   urgency_level=urgency_level)
        
        return {
            'success': True,
            'notification_id': str(notification.id),
            'escalation_reason': escalation_reason,
            'urgency_level': urgency_level
        }
        
    except Exception as exc:
        logger.error("Conversation escalation failed",
                    task_id=self.request.id,
                    conversation_id=conversation_id,
                    error=str(exc))
        
        return {
            'success': False,
            'error_message': str(exc)
        }
    
    finally:
        if 'db' in locals():
            db.close()


# Export tasks
__all__ = [
    'process_incoming_message_task',
    'classify_message_intent_task', 
    'update_conversation_state_task',
    'escalate_conversation_task'
]
