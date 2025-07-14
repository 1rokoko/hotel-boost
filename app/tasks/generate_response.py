"""
Celery tasks for AI response generation
"""

from typing import Optional, Dict, Any
import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.database import get_db
from app.models.message import Message
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.services.response_generator import ResponseGenerator
from app.services.message_sender import MessageSender
from app.utils.prompt_templates import ResponseType

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def generate_response_task(
    self,
    message_id: str,
    response_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    auto_send: bool = False,
    correlation_id: Optional[str] = None
):
    """
    Generate AI response to a guest message
    
    Args:
        message_id: ID of the message to respond to
        response_type: Type of response to generate
        context: Additional context for generation
        auto_send: Whether to automatically send the response
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            logger.info("Starting response generation task",
                       message_id=message_id,
                       response_type=response_type,
                       auto_send=auto_send,
                       correlation_id=correlation_id)
            
            # Get message
            message = db.query(Message).filter(Message.id == message_id).first()
            if not message:
                logger.error("Message not found for response generation",
                           message_id=message_id,
                           correlation_id=correlation_id)
                return
            
            # Only generate responses for incoming messages
            if message.message_type.value != 'incoming':
                logger.warning("Cannot generate response for non-incoming message",
                             message_id=message_id,
                             message_type=message.message_type.value,
                             correlation_id=correlation_id)
                return
            
            # Initialize response generator
            generator = ResponseGenerator(db)
            
            # Convert response type string to enum
            response_type_enum = None
            if response_type:
                try:
                    response_type_enum = ResponseType(response_type)
                except ValueError:
                    logger.warning("Invalid response type provided",
                                 response_type=response_type,
                                 correlation_id=correlation_id)
            
            # Generate response
            result = await generator.generate_response(
                message=message,
                response_type=response_type_enum,
                context=context,
                correlation_id=correlation_id
            )
            
            # Store generated response (optional - for review/approval workflow)
            # This could be stored in a separate table for human review before sending
            
            # Auto-send if requested
            if auto_send:
                send_generated_response_task.delay(
                    message_id=message_id,
                    generated_response=result.response,
                    response_metadata={
                        'response_type': result.response_type,
                        'confidence': result.confidence,
                        'reasoning': result.reasoning,
                        'suggested_actions': result.suggested_actions
                    },
                    correlation_id=correlation_id
                )
            
            logger.info("Response generation task completed",
                       message_id=message_id,
                       response_type=result.response_type,
                       response_length=len(result.response),
                       confidence=result.confidence,
                       auto_send=auto_send,
                       correlation_id=correlation_id)
            
            return {
                'message_id': message_id,
                'response': result.response,
                'response_type': result.response_type,
                'confidence': result.confidence,
                'suggested_actions': result.suggested_actions,
                'correlation_id': correlation_id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Response generation task failed",
                    message_id=message_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=3)
def send_generated_response_task(
    self,
    message_id: str,
    generated_response: str,
    response_metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
):
    """
    Send a generated AI response to the guest
    
    Args:
        message_id: ID of the original message
        generated_response: The AI-generated response text
        response_metadata: Metadata about the response generation
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            logger.info("Starting send generated response task",
                       message_id=message_id,
                       response_length=len(generated_response),
                       correlation_id=correlation_id)
            
            # Get original message and related entities
            message = db.query(Message).filter(Message.id == message_id).first()
            if not message:
                logger.error("Message not found for sending response",
                           message_id=message_id,
                           correlation_id=correlation_id)
                return
            
            hotel = db.query(Hotel).filter(Hotel.id == message.hotel_id).first()
            guest = db.query(Guest).filter(Guest.id == message.guest_id).first()
            
            if not hotel or not guest:
                logger.error("Hotel or guest not found for sending response",
                           message_id=message_id,
                           hotel_id=str(message.hotel_id),
                           guest_id=str(message.guest_id),
                           correlation_id=correlation_id)
                return
            
            # Initialize message sender
            sender = MessageSender(db)
            
            # Send response
            send_result = await sender.send_text_message(
                hotel=hotel,
                guest=guest,
                message=generated_response,
                priority="normal",
                quoted_message_id=str(message.id)  # Quote the original message
            )
            
            if send_result.get('success'):
                logger.info("Generated response sent successfully",
                           message_id=message_id,
                           sent_message_id=send_result.get('message_id'),
                           correlation_id=correlation_id)
            else:
                logger.error("Failed to send generated response",
                           message_id=message_id,
                           error=send_result.get('error'),
                           correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Send generated response task failed",
                    message_id=message_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2)
def batch_generate_responses_task(
    self,
    message_ids: List[str],
    response_type: Optional[str] = None,
    auto_send: bool = False,
    correlation_id: Optional[str] = None
):
    """
    Generate responses for multiple messages in batch
    
    Args:
        message_ids: List of message IDs to generate responses for
        response_type: Type of response to generate for all messages
        auto_send: Whether to automatically send the responses
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        logger.info("Starting batch response generation",
                   message_count=len(message_ids),
                   response_type=response_type,
                   auto_send=auto_send,
                   correlation_id=correlation_id)
        
        # Process each message
        results = []
        for message_id in message_ids:
            try:
                # Trigger individual response generation
                result = generate_response_task.delay(
                    message_id=message_id,
                    response_type=response_type,
                    auto_send=auto_send,
                    correlation_id=correlation_id
                )
                results.append({
                    'message_id': message_id,
                    'task_id': result.id,
                    'status': 'queued'
                })
            except Exception as e:
                logger.error("Failed to trigger response generation for message",
                           message_id=message_id,
                           error=str(e),
                           correlation_id=correlation_id)
                results.append({
                    'message_id': message_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        logger.info("Batch response generation tasks triggered",
                   message_count=len(message_ids),
                   successful_count=len([r for r in results if r['status'] == 'queued']),
                   failed_count=len([r for r in results if r['status'] == 'failed']),
                   correlation_id=correlation_id)
        
        return results
        
    except Exception as e:
        logger.error("Batch response generation task failed",
                    message_count=len(message_ids),
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=30 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2)
def generate_contextual_response_task(
    self,
    message_id: str,
    conversation_context: Dict[str, Any],
    guest_preferences: Optional[Dict[str, Any]] = None,
    hotel_settings: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
):
    """
    Generate response with enhanced contextual information
    
    Args:
        message_id: ID of the message to respond to
        conversation_context: Rich conversation context
        guest_preferences: Guest preferences and history
        hotel_settings: Hotel-specific settings and branding
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Combine all context
        enhanced_context = {
            'conversation_context': conversation_context,
            'guest_preferences': guest_preferences or {},
            'hotel_settings': hotel_settings or {}
        }
        
        # Trigger enhanced response generation
        return generate_response_task.delay(
            message_id=message_id,
            context=enhanced_context,
            correlation_id=correlation_id
        )
        
    except Exception as e:
        logger.error("Contextual response generation task failed",
                    message_id=message_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=30 * (2 ** self.request.retries))


# Export main components
__all__ = [
    'generate_response_task',
    'send_generated_response_task',
    'batch_generate_responses_task',
    'generate_contextual_response_task'
]
