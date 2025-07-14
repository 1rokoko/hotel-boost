"""
Real-time sentiment analysis service for WhatsApp Hotel Bot
"""

import asyncio
import time
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

import structlog
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.sentiment_analyzer import SentimentAnalyzer
from app.services.staff_notification import StaffNotificationService
from app.models.message import Message
from app.models.sentiment import SentimentAnalysis
from app.schemas.deepseek import SentimentAnalysisResult, SentimentType
from app.core.deepseek_logging import log_deepseek_operation
from app.tasks.analyze_message_sentiment import analyze_message_sentiment_task
from app.tasks.send_staff_alert import send_staff_alert_task

logger = structlog.get_logger(__name__)


class RealtimeSentimentAnalyzer:
    """Service for real-time sentiment analysis and alert triggering"""
    
    def __init__(self, db: Session):
        self.db = db
        self.sentiment_analyzer = SentimentAnalyzer(db)
        self.notification_service = StaffNotificationService(db)
    
    async def analyze_message(
        self,
        message: Message,
        conversation_id: str,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> SentimentAnalysisResult:
        """
        Analyze sentiment of a message in real-time
        
        Args:
            message: Message object to analyze
            conversation_id: ID of the conversation
            context: Additional context for analysis
            correlation_id: Correlation ID for tracking
            
        Returns:
            SentimentAnalysisResult: Analysis result
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()
        
        try:
            logger.info("Starting real-time sentiment analysis",
                       message_id=str(message.id),
                       conversation_id=conversation_id,
                       correlation_id=correlation_id)
            
            # Perform sentiment analysis
            result = await self.sentiment_analyzer.analyze_message_sentiment(
                message=message,
                context=context,
                correlation_id=correlation_id
            )
            
            # Process the result
            await self.process_sentiment_result(
                result=result,
                message=message,
                correlation_id=correlation_id
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info("Real-time sentiment analysis completed",
                       message_id=str(message.id),
                       sentiment=result.sentiment.value,
                       score=result.score,
                       requires_attention=result.requires_attention,
                       processing_time_ms=processing_time,
                       correlation_id=correlation_id)
            
            return result
            
        except Exception as e:
            logger.error("Real-time sentiment analysis failed",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def process_sentiment_result(
        self,
        result: SentimentAnalysisResult,
        message: Message,
        correlation_id: str
    ) -> None:
        """
        Process sentiment analysis result and trigger alerts if needed
        
        Args:
            result: Sentiment analysis result
            message: Original message
            correlation_id: Correlation ID for tracking
        """
        try:
            # Check if alerts need to be triggered
            if await self.should_trigger_alert(result, message):
                await self.trigger_alerts_if_needed(
                    sentiment=result,
                    message=message,
                    correlation_id=correlation_id
                )
            
            # Log the processing
            await log_deepseek_operation(
                operation_type="sentiment_analysis",
                hotel_id=str(message.hotel_id),
                input_data={
                    "message_id": str(message.id),
                    "text_length": len(message.content)
                },
                output_data={
                    "sentiment": result.sentiment.value,
                    "score": result.score,
                    "confidence": result.confidence,
                    "requires_attention": result.requires_attention
                },
                correlation_id=correlation_id
            )
            
        except Exception as e:
            logger.error("Failed to process sentiment result",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def trigger_alerts_if_needed(
        self,
        sentiment: SentimentAnalysisResult,
        message: Message,
        correlation_id: str
    ) -> None:
        """
        Trigger alerts for negative sentiment
        
        Args:
            sentiment: Sentiment analysis result
            message: Original message
            correlation_id: Correlation ID for tracking
        """
        try:
            if sentiment.requires_attention or sentiment.score < -0.3:
                # Send immediate staff alert
                send_staff_alert_task.delay(
                    message_id=str(message.id),
                    sentiment_type=sentiment.sentiment.value,
                    sentiment_score=sentiment.score,
                    urgency_level=self._calculate_urgency_level(sentiment),
                    correlation_id=correlation_id
                )
                
                logger.info("Staff alert triggered for negative sentiment",
                           message_id=str(message.id),
                           sentiment_score=sentiment.score,
                           urgency_level=self._calculate_urgency_level(sentiment),
                           correlation_id=correlation_id)
            
        except Exception as e:
            logger.error("Failed to trigger alerts",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def should_trigger_alert(
        self,
        result: SentimentAnalysisResult,
        message: Message
    ) -> bool:
        """
        Determine if an alert should be triggered based on sentiment
        
        Args:
            result: Sentiment analysis result
            message: Original message
            
        Returns:
            bool: Whether to trigger alert
        """
        # Check if requires attention flag is set
        if result.requires_attention:
            return True
        
        # Check sentiment score thresholds
        if result.score < -0.3:  # Negative sentiment threshold
            return True
        
        # Check for critical sentiment
        if result.sentiment == SentimentType.REQUIRES_ATTENTION:
            return True
        
        # Check for consecutive negative messages from same guest
        recent_negative_count = await self._count_recent_negative_messages(
            guest_id=message.guest_id,
            hotel_id=message.hotel_id
        )
        
        if recent_negative_count >= 3:  # 3 consecutive negative messages
            return True
        
        return False
    
    async def _count_recent_negative_messages(
        self,
        guest_id: str,
        hotel_id: str,
        hours: int = 24
    ) -> int:
        """
        Count recent negative messages from a guest
        
        Args:
            guest_id: Guest ID
            hotel_id: Hotel ID
            hours: Hours to look back
            
        Returns:
            int: Count of negative messages
        """
        try:
            from datetime import timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            count = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.guest_id == guest_id,
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.sentiment_score < -0.1,
                SentimentAnalysis.created_at >= cutoff_time
            ).count()
            
            return count
            
        except Exception as e:
            logger.error("Failed to count recent negative messages",
                        guest_id=guest_id,
                        error=str(e))
            return 0
    
    def _calculate_urgency_level(self, sentiment: SentimentAnalysisResult) -> int:
        """
        Calculate urgency level based on sentiment
        
        Args:
            sentiment: Sentiment analysis result
            
        Returns:
            int: Urgency level (1-5)
        """
        if sentiment.requires_attention:
            return 5  # Critical
        elif sentiment.score < -0.7:
            return 4  # High
        elif sentiment.score < -0.5:
            return 3  # Medium
        elif sentiment.score < -0.3:
            return 2  # Low
        else:
            return 1  # Minimal


def get_realtime_sentiment_analyzer(db: Session) -> RealtimeSentimentAnalyzer:
    """Get realtime sentiment analyzer instance"""
    return RealtimeSentimentAnalyzer(db)
