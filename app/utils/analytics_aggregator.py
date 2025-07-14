"""
Analytics data aggregation utilities
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text, case
from sqlalchemy.orm import selectinload
import structlog
import asyncio
from collections import defaultdict

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType
from app.models.sentiment import SentimentAnalysis
from app.models.trigger import Trigger
from app.models.staff_alert import StaffAlert

logger = structlog.get_logger(__name__)


class AnalyticsAggregator:
    """
    Utility class for aggregating analytics data
    
    Provides methods for complex data aggregation and calculation.
    """
    
    def __init__(self):
        """Initialize analytics aggregator"""
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def aggregate_message_metrics(
        self,
        db: AsyncSession,
        hotel_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Aggregate comprehensive message metrics
        
        Args:
            db: Database session
            hotel_id: Hotel ID filter
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dict containing aggregated message metrics
        """
        try:
            # Build base query conditions
            conditions = [
                Message.created_at >= start_date,
                Message.created_at <= end_date
            ]
            
            if hotel_id:
                conditions.append(Message.hotel_id == hotel_id)
            
            # Get total message counts by type
            message_counts_stmt = select(
                Message.message_type,
                func.count(Message.id).label('count')
            ).where(and_(*conditions)).group_by(Message.message_type)
            
            message_counts_result = await db.execute(message_counts_stmt)
            message_counts = {row.message_type.value: row.count for row in message_counts_result}
            
            # Get hourly distribution
            hourly_stmt = select(
                func.extract('hour', Message.created_at).label('hour'),
                func.count(Message.id).label('count')
            ).where(and_(*conditions)).group_by(func.extract('hour', Message.created_at))
            
            hourly_result = await db.execute(hourly_stmt)
            hourly_distribution = {str(int(row.hour)): row.count for row in hourly_result}
            
            # Fill missing hours with 0
            for hour in range(24):
                if str(hour) not in hourly_distribution:
                    hourly_distribution[str(hour)] = 0
            
            # Get daily trends
            daily_stmt = select(
                func.date(Message.created_at).label('date'),
                func.count(Message.id).label('count')
            ).where(and_(*conditions)).group_by(func.date(Message.created_at)).order_by('date')
            
            daily_result = await db.execute(daily_stmt)
            daily_trends = [
                {
                    'date': row.date.isoformat(),
                    'count': row.count
                }
                for row in daily_result
            ]
            
            return {
                'message_counts': message_counts,
                'hourly_distribution': hourly_distribution,
                'daily_trends': daily_trends,
                'total_messages': sum(message_counts.values())
            }
            
        except Exception as e:
            logger.error("Error aggregating message metrics", error=str(e))
            raise
    
    async def aggregate_conversation_metrics(
        self,
        db: AsyncSession,
        hotel_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Aggregate conversation metrics
        
        Args:
            db: Database session
            hotel_id: Hotel ID filter
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dict containing conversation metrics
        """
        try:
            # Build base query conditions
            conditions = [
                Conversation.created_at >= start_date,
                Conversation.created_at <= end_date
            ]
            
            if hotel_id:
                conditions.append(Conversation.hotel_id == hotel_id)
            
            # Get conversation status distribution
            status_stmt = select(
                Conversation.status,
                func.count(Conversation.id).label('count')
            ).where(and_(*conditions)).group_by(Conversation.status)
            
            status_result = await db.execute(status_stmt)
            status_distribution = {row.status: row.count for row in status_result}
            
            # Calculate average conversation length (in messages)
            length_stmt = select(
                func.avg(
                    select(func.count(Message.id))
                    .where(Message.conversation_id == Conversation.id)
                    .scalar_subquery()
                ).label('avg_length')
            ).where(and_(*conditions))
            
            length_result = await db.execute(length_stmt)
            avg_length = length_result.scalar() or 0
            
            # Get conversation resolution times
            resolution_stmt = select(
                func.avg(
                    func.extract('epoch', Conversation.updated_at - Conversation.created_at)
                ).label('avg_resolution_time')
            ).where(
                and_(
                    *conditions,
                    Conversation.status == 'completed'
                )
            )
            
            resolution_result = await db.execute(resolution_stmt)
            avg_resolution_time = resolution_result.scalar() or 0
            
            return {
                'status_distribution': status_distribution,
                'average_length': float(avg_length),
                'average_resolution_time': float(avg_resolution_time),
                'total_conversations': sum(status_distribution.values())
            }
            
        except Exception as e:
            logger.error("Error aggregating conversation metrics", error=str(e))
            raise
    
    async def aggregate_sentiment_metrics(
        self,
        db: AsyncSession,
        hotel_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Aggregate sentiment analysis metrics
        
        Args:
            db: Database session
            hotel_id: Hotel ID filter
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dict containing sentiment metrics
        """
        try:
            # Build base query conditions
            conditions = [
                SentimentAnalysis.created_at >= start_date,
                SentimentAnalysis.created_at <= end_date
            ]
            
            if hotel_id:
                conditions.append(SentimentAnalysis.hotel_id == hotel_id)
            
            # Get sentiment distribution
            sentiment_stmt = select(
                case(
                    (SentimentAnalysis.sentiment_score >= 0.6, 'positive'),
                    (SentimentAnalysis.sentiment_score <= 0.4, 'negative'),
                    else_='neutral'
                ).label('sentiment_category'),
                func.count(SentimentAnalysis.id).label('count')
            ).where(and_(*conditions)).group_by('sentiment_category')
            
            sentiment_result = await db.execute(sentiment_stmt)
            sentiment_distribution = {row.sentiment_category: row.count for row in sentiment_result}
            
            # Calculate average sentiment score
            avg_stmt = select(
                func.avg(SentimentAnalysis.sentiment_score).label('avg_score')
            ).where(and_(*conditions))
            
            avg_result = await db.execute(avg_stmt)
            avg_sentiment = avg_result.scalar() or 0.5
            
            # Get sentiment trends (daily)
            trends_stmt = select(
                func.date(SentimentAnalysis.created_at).label('date'),
                func.avg(SentimentAnalysis.sentiment_score).label('avg_score'),
                func.count(SentimentAnalysis.id).label('count')
            ).where(and_(*conditions)).group_by(func.date(SentimentAnalysis.created_at)).order_by('date')
            
            trends_result = await db.execute(trends_stmt)
            sentiment_trends = [
                {
                    'date': row.date.isoformat(),
                    'average_score': float(row.avg_score),
                    'count': row.count
                }
                for row in trends_result
            ]
            
            return {
                'distribution': sentiment_distribution,
                'average_score': float(avg_sentiment),
                'trends': sentiment_trends,
                'total_analyses': sum(sentiment_distribution.values())
            }
            
        except Exception as e:
            logger.error("Error aggregating sentiment metrics", error=str(e))
            raise
    
    async def aggregate_guest_metrics(
        self,
        db: AsyncSession,
        hotel_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Aggregate guest engagement metrics
        
        Args:
            db: Database session
            hotel_id: Hotel ID filter
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dict containing guest metrics
        """
        try:
            # Build base query conditions
            conditions = [
                Guest.created_at >= start_date,
                Guest.created_at <= end_date
            ]
            
            if hotel_id:
                conditions.append(Guest.hotel_id == hotel_id)
            
            # Get total guests
            total_stmt = select(func.count(Guest.id)).where(and_(*conditions))
            total_result = await db.execute(total_stmt)
            total_guests = total_result.scalar() or 0
            
            # Get new vs returning guests
            new_guests_stmt = select(func.count(Guest.id)).where(
                and_(
                    *conditions,
                    Guest.created_at >= start_date
                )
            )
            new_guests_result = await db.execute(new_guests_stmt)
            new_guests = new_guests_result.scalar() or 0
            
            # Calculate engagement score based on message frequency
            engagement_stmt = select(
                func.avg(
                    select(func.count(Message.id))
                    .where(Message.guest_id == Guest.id)
                    .scalar_subquery()
                ).label('avg_messages')
            ).where(and_(*conditions))
            
            engagement_result = await db.execute(engagement_stmt)
            avg_messages = engagement_result.scalar() or 0
            
            # Simple engagement score calculation
            engagement_score = min(float(avg_messages) / 10.0, 1.0)  # Normalize to 0-1
            
            return {
                'total_guests': total_guests,
                'new_guests': new_guests,
                'returning_guests': total_guests - new_guests,
                'engagement_score': engagement_score,
                'average_messages_per_guest': float(avg_messages)
            }
            
        except Exception as e:
            logger.error("Error aggregating guest metrics", error=str(e))
            raise
    
    async def aggregate_performance_metrics(
        self,
        db: AsyncSession,
        hotel_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Aggregate system performance metrics
        
        Args:
            db: Database session
            hotel_id: Hotel ID filter
            start_date: Start date for aggregation
            end_date: End date for aggregation
            
        Returns:
            Dict containing performance metrics
        """
        try:
            # This would typically query performance logs or metrics tables
            # For now, we'll return placeholder data
            
            return {
                'api_response_times': {
                    'average': 150.0,  # ms
                    'p95': 300.0,
                    'p99': 500.0
                },
                'database_performance': {
                    'query_time_avg': 25.0,  # ms
                    'connection_pool_usage': 0.65,
                    'slow_queries': 3
                },
                'external_apis': {
                    'green_api_success_rate': 0.995,
                    'deepseek_success_rate': 0.998,
                    'average_latency': 200.0
                },
                'error_rates': {
                    'total_errors': 12,
                    'critical_errors': 1,
                    'error_rate_percentage': 0.05
                }
            }
            
        except Exception as e:
            logger.error("Error aggregating performance metrics", error=str(e))
            raise
    
    def calculate_satisfaction_score(
        self,
        sentiment_metrics: Dict[str, Any],
        conversation_metrics: Dict[str, Any]
    ) -> float:
        """
        Calculate guest satisfaction score based on multiple factors
        
        Args:
            sentiment_metrics: Sentiment analysis metrics
            conversation_metrics: Conversation metrics
            
        Returns:
            float: Satisfaction score (0-5 scale)
        """
        try:
            # Base score from sentiment
            sentiment_score = sentiment_metrics.get('average_score', 0.5)
            
            # Adjust based on conversation completion rate
            status_dist = conversation_metrics.get('status_distribution', {})
            total_conversations = sum(status_dist.values())
            
            if total_conversations > 0:
                completion_rate = status_dist.get('completed', 0) / total_conversations
                escalation_rate = status_dist.get('escalated', 0) / total_conversations
                
                # Boost score for high completion rate, reduce for high escalation
                completion_boost = completion_rate * 0.5
                escalation_penalty = escalation_rate * 0.3
                
                adjusted_score = sentiment_score + completion_boost - escalation_penalty
            else:
                adjusted_score = sentiment_score
            
            # Convert to 5-point scale
            satisfaction_score = max(0, min(5, adjusted_score * 5))
            
            return round(satisfaction_score, 1)
            
        except Exception as e:
            logger.error("Error calculating satisfaction score", error=str(e))
            return 3.0  # Default neutral score
    
    def calculate_nps_score(self, sentiment_distribution: Dict[str, int]) -> Optional[float]:
        """
        Calculate Net Promoter Score based on sentiment distribution
        
        Args:
            sentiment_distribution: Distribution of sentiment categories
            
        Returns:
            Optional[float]: NPS score (-100 to 100) or None if insufficient data
        """
        try:
            total = sum(sentiment_distribution.values())
            if total < 10:  # Need minimum responses for meaningful NPS
                return None
            
            # Map sentiment to NPS categories
            promoters = sentiment_distribution.get('positive', 0)
            detractors = sentiment_distribution.get('negative', 0)
            
            # Calculate NPS
            nps = ((promoters - detractors) / total) * 100
            
            return round(nps, 1)
            
        except Exception as e:
            logger.error("Error calculating NPS score", error=str(e))
            return None
