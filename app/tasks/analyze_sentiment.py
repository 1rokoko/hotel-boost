"""
Celery tasks for sentiment analysis
"""

from typing import Optional, Dict, Any
import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app, high_priority_task
from app.database import get_db
from app.models.message import Message
from app.models.sentiment import SentimentAnalysis
from app.services.sentiment_analyzer import SentimentAnalyzer
from app.services.staff_notification import StaffNotificationService
from app.core.deepseek_config import get_global_sentiment_config

logger = structlog.get_logger(__name__)


@high_priority_task(bind=True, max_retries=3)
def analyze_message_sentiment_task(
    self,
    message_id: str,
    context: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
):
    """
    Analyze sentiment of a message asynchronously
    
    Args:
        message_id: ID of the message to analyze
        context: Additional context for analysis
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            logger.info("Starting sentiment analysis task",
                       message_id=message_id,
                       correlation_id=correlation_id)
            
            # Get message
            message = db.query(Message).filter(Message.id == message_id).first()
            if not message:
                logger.error("Message not found for sentiment analysis",
                           message_id=message_id,
                           correlation_id=correlation_id)
                return
            
            # Check if sentiment analysis already exists
            existing_sentiment = db.query(SentimentAnalysis).filter(
                SentimentAnalysis.message_id == message_id
            ).first()
            
            if existing_sentiment:
                logger.info("Sentiment analysis already exists",
                           message_id=message_id,
                           sentiment_id=str(existing_sentiment.id),
                           correlation_id=correlation_id)
                return
            
            # Initialize sentiment analyzer
            analyzer = SentimentAnalyzer(db)
            
            # Perform sentiment analysis
            result = await analyzer.analyze_message_sentiment(
                message=message,
                context=context,
                correlation_id=correlation_id
            )
            
            # Check if staff notification is needed
            if result.requires_attention:
                # Trigger staff notification task
                send_sentiment_notification_task.delay(
                    message_id=message_id,
                    sentiment_type=result.sentiment.value,
                    sentiment_score=result.score,
                    correlation_id=correlation_id
                )
            
            logger.info("Sentiment analysis task completed",
                       message_id=message_id,
                       sentiment=result.sentiment.value,
                       score=result.score,
                       requires_attention=result.requires_attention,
                       correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Sentiment analysis task failed",
                    message_id=message_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=3)
def send_sentiment_notification_task(
    self,
    message_id: str,
    sentiment_type: str,
    sentiment_score: float,
    correlation_id: Optional[str] = None
):
    """
    Send staff notification for negative sentiment
    
    Args:
        message_id: ID of the message with negative sentiment
        sentiment_type: Type of sentiment detected
        sentiment_score: Sentiment score
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            logger.info("Starting sentiment notification task",
                       message_id=message_id,
                       sentiment_type=sentiment_type,
                       sentiment_score=sentiment_score,
                       correlation_id=correlation_id)
            
            # Get message and sentiment analysis
            message = db.query(Message).filter(Message.id == message_id).first()
            if not message:
                logger.error("Message not found for notification",
                           message_id=message_id,
                           correlation_id=correlation_id)
                return
            
            sentiment_analysis = db.query(SentimentAnalysis).filter(
                SentimentAnalysis.message_id == message_id
            ).first()
            
            if not sentiment_analysis:
                logger.error("Sentiment analysis not found for notification",
                           message_id=message_id,
                           correlation_id=correlation_id)
                return
            
            # Check if notification already sent
            if sentiment_analysis.notification_sent:
                logger.info("Notification already sent for sentiment",
                           message_id=message_id,
                           sentiment_id=str(sentiment_analysis.id),
                           correlation_id=correlation_id)
                return
            
            # Initialize notification service
            notification_service = StaffNotificationService(db)
            
            # Send notification
            notification_sent = await notification_service.send_negative_sentiment_alert(
                message=message,
                sentiment_analysis=sentiment_analysis,
                correlation_id=correlation_id
            )
            
            if notification_sent:
                # Mark notification as sent
                sentiment_analysis.mark_notification_sent()
                db.commit()
                
                logger.info("Sentiment notification sent successfully",
                           message_id=message_id,
                           sentiment_id=str(sentiment_analysis.id),
                           correlation_id=correlation_id)
            else:
                logger.warning("Failed to send sentiment notification",
                             message_id=message_id,
                             sentiment_id=str(sentiment_analysis.id),
                             correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Sentiment notification task failed",
                    message_id=message_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2)
def batch_analyze_sentiment_task(
    self,
    message_ids: list[str],
    correlation_id: Optional[str] = None
):
    """
    Analyze sentiment for multiple messages in batch
    
    Args:
        message_ids: List of message IDs to analyze
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        logger.info("Starting batch sentiment analysis",
                   message_count=len(message_ids),
                   correlation_id=correlation_id)
        
        # Process each message
        for message_id in message_ids:
            try:
                # Trigger individual sentiment analysis
                analyze_message_sentiment_task.delay(
                    message_id=message_id,
                    correlation_id=correlation_id
                )
            except Exception as e:
                logger.error("Failed to trigger sentiment analysis for message",
                           message_id=message_id,
                           error=str(e),
                           correlation_id=correlation_id)
        
        logger.info("Batch sentiment analysis tasks triggered",
                   message_count=len(message_ids),
                   correlation_id=correlation_id)
        
    except Exception as e:
        logger.error("Batch sentiment analysis task failed",
                    message_count=len(message_ids),
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=30 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2)
def reanalyze_failed_sentiment_task(
    self,
    hotel_id: str,
    hours_back: int = 24,
    correlation_id: Optional[str] = None
):
    """
    Reanalyze messages that failed sentiment analysis
    
    Args:
        hotel_id: Hotel ID to reanalyze messages for
        hours_back: How many hours back to look for failed messages
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            logger.info("Starting failed sentiment reanalysis",
                       hotel_id=hotel_id,
                       hours_back=hours_back,
                       correlation_id=correlation_id)
            
            # Find messages without sentiment analysis
            from datetime import datetime, timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            messages_without_sentiment = db.query(Message).filter(
                Message.hotel_id == hotel_id,
                Message.created_at >= cutoff_time,
                ~Message.id.in_(
                    db.query(SentimentAnalysis.message_id).filter(
                        SentimentAnalysis.hotel_id == hotel_id
                    )
                )
            ).all()
            
            if not messages_without_sentiment:
                logger.info("No messages found for reanalysis",
                           hotel_id=hotel_id,
                           correlation_id=correlation_id)
                return
            
            # Trigger batch analysis
            message_ids = [str(msg.id) for msg in messages_without_sentiment]
            batch_analyze_sentiment_task.delay(
                message_ids=message_ids,
                correlation_id=correlation_id
            )
            
            logger.info("Failed sentiment reanalysis triggered",
                       hotel_id=hotel_id,
                       message_count=len(message_ids),
                       correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Failed sentiment reanalysis task failed",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


# Export main components
__all__ = [
    'analyze_message_sentiment_task',
    'send_sentiment_notification_task',
    'batch_analyze_sentiment_task',
    'reanalyze_failed_sentiment_task'
]
