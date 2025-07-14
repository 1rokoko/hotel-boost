"""
Celery tasks for real-time message sentiment analysis
"""

import asyncio
import uuid
from typing import Optional, Dict, Any

import structlog
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app, high_priority_task
from app.database import get_db
from app.models.message import Message
from app.services.realtime_sentiment import get_realtime_sentiment_analyzer
from app.core.deepseek_logging import log_deepseek_operation

logger = structlog.get_logger(__name__)


@high_priority_task(bind=True, max_retries=3)
def analyze_message_sentiment_realtime_task(
    self,
    message_id: str,
    conversation_id: str,
    context: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
):
    """
    Analyze message sentiment in real-time
    
    Args:
        message_id: ID of the message to analyze
        conversation_id: ID of the conversation
        context: Additional context for analysis
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        logger.info("Starting real-time sentiment analysis task",
                   message_id=message_id,
                   conversation_id=conversation_id,
                   correlation_id=correlation_id)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get message from database
            message = db.query(Message).filter(Message.id == message_id).first()
            if not message:
                logger.error("Message not found for sentiment analysis",
                           message_id=message_id,
                           correlation_id=correlation_id)
                return
            
            # Initialize real-time sentiment analyzer
            analyzer = get_realtime_sentiment_analyzer(db)
            
            # Run async analysis in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    analyzer.analyze_message(
                        message=message,
                        conversation_id=conversation_id,
                        context=context,
                        correlation_id=correlation_id
                    )
                )
                
                logger.info("Real-time sentiment analysis task completed",
                           message_id=message_id,
                           sentiment=result.sentiment.value,
                           score=result.score,
                           requires_attention=result.requires_attention,
                           correlation_id=correlation_id)
                
            finally:
                loop.close()
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Real-time sentiment analysis task failed",
                    message_id=message_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2)
def batch_analyze_messages_task(
    self,
    message_ids: list,
    correlation_id: Optional[str] = None
):
    """
    Batch analyze multiple messages for sentiment
    
    Args:
        message_ids: List of message IDs to analyze
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        logger.info("Starting batch sentiment analysis task",
                   message_count=len(message_ids),
                   correlation_id=correlation_id)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Initialize analyzer
            analyzer = get_realtime_sentiment_analyzer(db)
            
            # Process each message
            results = []
            for message_id in message_ids:
                try:
                    # Get message
                    message = db.query(Message).filter(Message.id == message_id).first()
                    if not message:
                        logger.warning("Message not found in batch analysis",
                                     message_id=message_id,
                                     correlation_id=correlation_id)
                        continue
                    
                    # Run async analysis
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        result = loop.run_until_complete(
                            analyzer.analyze_message(
                                message=message,
                                conversation_id=str(message.conversation_id),
                                correlation_id=correlation_id
                            )
                        )
                        results.append({
                            "message_id": message_id,
                            "sentiment": result.sentiment.value,
                            "score": result.score,
                            "requires_attention": result.requires_attention
                        })
                        
                    finally:
                        loop.close()
                        
                except Exception as e:
                    logger.error("Failed to analyze message in batch",
                               message_id=message_id,
                               error=str(e),
                               correlation_id=correlation_id)
                    continue
            
            logger.info("Batch sentiment analysis completed",
                       processed_count=len(results),
                       total_count=len(message_ids),
                       correlation_id=correlation_id)
            
            return results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Batch sentiment analysis task failed",
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=120 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2)
def reanalyze_conversation_sentiment_task(
    self,
    conversation_id: str,
    correlation_id: Optional[str] = None
):
    """
    Re-analyze sentiment for all messages in a conversation
    
    Args:
        conversation_id: ID of the conversation to re-analyze
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        logger.info("Starting conversation sentiment re-analysis",
                   conversation_id=conversation_id,
                   correlation_id=correlation_id)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get all messages in conversation
            messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).all()
            
            if not messages:
                logger.warning("No messages found for conversation re-analysis",
                             conversation_id=conversation_id,
                             correlation_id=correlation_id)
                return
            
            # Extract message IDs
            message_ids = [str(msg.id) for msg in messages]
            
            # Trigger batch analysis
            batch_analyze_messages_task.delay(
                message_ids=message_ids,
                correlation_id=correlation_id
            )
            
            logger.info("Conversation sentiment re-analysis triggered",
                       conversation_id=conversation_id,
                       message_count=len(message_ids),
                       correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Conversation sentiment re-analysis failed",
                    conversation_id=conversation_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=180 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=1)
def cleanup_old_sentiment_data_task(
    self,
    days_to_keep: int = 90,
    correlation_id: Optional[str] = None
):
    """
    Clean up old sentiment analysis data
    
    Args:
        days_to_keep: Number of days of data to keep
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        from datetime import datetime, timedelta
        from app.models.sentiment import SentimentAnalysis
        
        logger.info("Starting sentiment data cleanup",
                   days_to_keep=days_to_keep,
                   correlation_id=correlation_id)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Delete old sentiment analysis records
            deleted_count = db.query(SentimentAnalysis).filter(
                SentimentAnalysis.created_at < cutoff_date
            ).delete()
            
            db.commit()
            
            logger.info("Sentiment data cleanup completed",
                       deleted_count=deleted_count,
                       cutoff_date=cutoff_date.isoformat(),
                       correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Sentiment data cleanup failed",
                    error=str(e),
                    correlation_id=correlation_id)
        raise
