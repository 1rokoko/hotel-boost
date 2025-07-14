"""
Celery tasks for processing incoming messages
"""

from typing import Optional
import structlog
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app, incoming_message_task
from app.database import get_db
from app.models.message import Message
from app.models.hotel import Hotel
from app.services.message_processor import MessageProcessor

logger = structlog.get_logger(__name__)


@incoming_message_task(bind=True, max_retries=3)
def process_incoming_message_task(self, hotel_id: str, message_id: str):
    """
    Process incoming message asynchronously
    
    This task handles:
    - Sentiment analysis
    - Auto-response triggers
    - Staff notifications for negative sentiment
    - Message categorization
    """
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            # Get message and hotel
            message = db.query(Message).filter(Message.id == message_id).first()
            if not message:
                logger.error("Message not found", message_id=message_id)
                return
            
            hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
            if not hotel:
                logger.error("Hotel not found", hotel_id=hotel_id)
                return
            
            logger.info("Processing incoming message",
                       hotel_id=hotel_id,
                       message_id=message_id,
                       content_length=len(message.content))

            # Process message using MessageProcessor
            processor = MessageProcessor(db)
            result = processor.process_incoming_message(hotel, message)

            logger.info("Incoming message processed successfully",
                       hotel_id=hotel_id,
                       message_id=message_id,
                       result=result)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Error processing incoming message",
                    hotel_id=hotel_id,
                    message_id=message_id,
                    error=str(e))
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


# Export task
__all__ = ['process_incoming_message_task']
