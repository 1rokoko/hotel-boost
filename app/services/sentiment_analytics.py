"""
Sentiment analytics service for generating insights and reports
"""

import uuid
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, date
from collections import defaultdict
import json

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, asc
from sqlalchemy.exc import SQLAlchemyError

from app.models.sentiment import SentimentAnalysis, SentimentSummary
from app.models.staff_alert import StaffAlert
from app.models.message import Message
from app.models.guest import Guest
from app.schemas.sentiment_analytics import (
    SentimentOverviewResponse,
    SentimentTrendsResponse,
    SentimentAlertsResponse,
    SentimentMetricsResponse,
    SentimentDistributionResponse,
    SentimentAnalyticsFilters,
    SentimentDataPoint,
    AlertSummary,
    ExportResult
)

logger = structlog.get_logger(__name__)


class SentimentAnalyticsService:
    """Service for sentiment analytics and reporting"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_sentiment_overview(
        self,
        hotel_id: str,
        period: str = "7d",
        correlation_id: Optional[str] = None
    ) -> SentimentOverviewResponse:
        """
        Get sentiment overview for a hotel
        
        Args:
            hotel_id: Hotel ID
            period: Time period (1d, 7d, 30d, 90d)
            correlation_id: Correlation ID for tracking
            
        Returns:
            Sentiment overview data
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Getting sentiment overview",
                       hotel_id=hotel_id,
                       period=period,
                       correlation_id=correlation_id)
            
            # Parse period
            days = self._parse_period(period)
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get sentiment analyses for period
            sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= start_date
            ).all()
            
            if not sentiments:
                return SentimentOverviewResponse(
                    hotel_id=hotel_id,
                    period=period,
                    total_messages=0,
                    average_sentiment_score=0.0,
                    positive_count=0,
                    negative_count=0,
                    neutral_count=0,
                    requires_attention_count=0,
                    alerts_triggered=0,
                    response_rate=0.0,
                    average_response_time_minutes=0.0
                )
            
            # Calculate metrics
            total_messages = len(sentiments)
            scores = [s.sentiment_score for s in sentiments]
            average_score = sum(scores) / len(scores)
            
            # Count by sentiment type
            positive_count = len([s for s in sentiments if s.sentiment_score > 0.1])
            negative_count = len([s for s in sentiments if s.sentiment_score < -0.1])
            neutral_count = total_messages - positive_count - negative_count
            requires_attention_count = len([s for s in sentiments if s.requires_attention])
            
            # Get alerts for period
            alerts = self.db.query(StaffAlert).filter(
                StaffAlert.hotel_id == hotel_id,
                StaffAlert.created_at >= start_date
            ).all()
            
            alerts_triggered = len(alerts)
            
            # Calculate response metrics
            responded_alerts = [a for a in alerts if a.acknowledged_at is not None]
            response_rate = len(responded_alerts) / len(alerts) * 100 if alerts else 0
            
            response_times = [a.response_time_minutes for a in responded_alerts if a.response_time_minutes]
            average_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            return SentimentOverviewResponse(
                hotel_id=hotel_id,
                period=period,
                total_messages=total_messages,
                average_sentiment_score=round(average_score, 3),
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count,
                requires_attention_count=requires_attention_count,
                alerts_triggered=alerts_triggered,
                response_rate=round(response_rate, 1),
                average_response_time_minutes=round(average_response_time, 1)
            )
            
        except Exception as e:
            logger.error("Failed to get sentiment overview",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def get_sentiment_trends(
        self,
        hotel_id: str,
        days: int = 30,
        granularity: str = "daily",
        correlation_id: Optional[str] = None
    ) -> SentimentTrendsResponse:
        """
        Get sentiment trends over time
        
        Args:
            hotel_id: Hotel ID
            days: Number of days to analyze
            granularity: Time granularity (hourly, daily, weekly)
            correlation_id: Correlation ID for tracking
            
        Returns:
            Sentiment trends data
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Getting sentiment trends",
                       hotel_id=hotel_id,
                       days=days,
                       granularity=granularity,
                       correlation_id=correlation_id)
            
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get sentiment analyses
            sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= start_date
            ).order_by(SentimentAnalysis.created_at).all()
            
            # Group by time period
            data_points = self._group_sentiments_by_time(sentiments, granularity)
            
            # Calculate trend direction
            if len(data_points) >= 2:
                recent_avg = sum(dp.average_score for dp in data_points[-3:]) / min(3, len(data_points))
                older_avg = sum(dp.average_score for dp in data_points[:3]) / min(3, len(data_points))
                
                if recent_avg > older_avg + 0.1:
                    trend_direction = "improving"
                elif recent_avg < older_avg - 0.1:
                    trend_direction = "declining"
                else:
                    trend_direction = "stable"
            else:
                trend_direction = "insufficient_data"
            
            return SentimentTrendsResponse(
                hotel_id=hotel_id,
                period_days=days,
                granularity=granularity,
                data_points=data_points,
                trend_direction=trend_direction
            )
            
        except Exception as e:
            logger.error("Failed to get sentiment trends",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def get_recent_alerts(
        self,
        hotel_id: str,
        limit: int = 50,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> SentimentAlertsResponse:
        """
        Get recent sentiment alerts
        
        Args:
            hotel_id: Hotel ID
            limit: Maximum number of alerts
            status_filter: Filter by status
            priority_filter: Filter by priority
            correlation_id: Correlation ID for tracking
            
        Returns:
            Recent alerts data
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Getting recent alerts",
                       hotel_id=hotel_id,
                       limit=limit,
                       correlation_id=correlation_id)
            
            # Build query
            query = self.db.query(StaffAlert).filter(
                StaffAlert.hotel_id == hotel_id
            )
            
            if status_filter:
                query = query.filter(StaffAlert.status == status_filter)
            
            if priority_filter:
                query = query.filter(StaffAlert.priority == priority_filter)
            
            # Get alerts
            alerts = query.order_by(desc(StaffAlert.created_at)).limit(limit).all()
            
            # Convert to response format
            alert_summaries = []
            for alert in alerts:
                alert_summaries.append(AlertSummary(
                    id=str(alert.id),
                    alert_type=alert.alert_type,
                    priority=alert.priority,
                    status=alert.status,
                    title=alert.title,
                    description=alert.description,
                    sentiment_score=alert.sentiment_score,
                    urgency_level=alert.urgency_level,
                    created_at=alert.created_at,
                    acknowledged_at=alert.acknowledged_at,
                    resolved_at=alert.resolved_at,
                    is_overdue=alert.is_overdue
                ))
            
            # Calculate summary statistics
            total_alerts = len(alerts)
            pending_alerts = len([a for a in alerts if a.status == "pending"])
            overdue_alerts = len([a for a in alerts if a.is_overdue])
            
            return SentimentAlertsResponse(
                hotel_id=hotel_id,
                total_alerts=total_alerts,
                pending_alerts=pending_alerts,
                overdue_alerts=overdue_alerts,
                alerts=alert_summaries
            )
            
        except Exception as e:
            logger.error("Failed to get recent alerts",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def get_sentiment_metrics(
        self,
        hotel_id: str,
        start_date: date,
        end_date: date,
        correlation_id: Optional[str] = None
    ) -> SentimentMetricsResponse:
        """
        Get detailed sentiment metrics
        
        Args:
            hotel_id: Hotel ID
            start_date: Start date
            end_date: End date
            correlation_id: Correlation ID for tracking
            
        Returns:
            Detailed sentiment metrics
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Getting sentiment metrics",
                       hotel_id=hotel_id,
                       start_date=start_date,
                       end_date=end_date,
                       correlation_id=correlation_id)
            
            # Convert dates to datetime
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            # Get sentiment analyses
            sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= start_datetime,
                SentimentAnalysis.created_at <= end_datetime
            ).all()
            
            if not sentiments:
                return SentimentMetricsResponse(
                    hotel_id=hotel_id,
                    start_date=start_date,
                    end_date=end_date,
                    total_analyses=0,
                    average_sentiment_score=0.0,
                    sentiment_distribution={},
                    top_negative_reasons=[],
                    guest_satisfaction_score=0.0,
                    processing_metrics={}
                )
            
            # Calculate metrics
            total_analyses = len(sentiments)
            scores = [s.sentiment_score for s in sentiments]
            average_score = sum(scores) / len(scores)
            
            # Sentiment distribution
            distribution = self._calculate_sentiment_distribution(sentiments)
            
            # Top negative reasons
            negative_sentiments = [s for s in sentiments if s.sentiment_score < -0.1]
            top_reasons = self._extract_top_negative_reasons(negative_sentiments)
            
            # Guest satisfaction score (0-100)
            satisfaction_score = max(0, min(100, (average_score + 1) * 50))
            
            # Processing metrics
            processing_times = [s.processing_time_ms for s in sentiments if s.processing_time_ms]
            processing_metrics = {
                "average_processing_time_ms": sum(processing_times) / len(processing_times) if processing_times else 0,
                "total_tokens_used": sum(getattr(s, 'tokens_used', 0) for s in sentiments),
                "ai_model_accuracy": self._calculate_model_accuracy(sentiments)
            }
            
            return SentimentMetricsResponse(
                hotel_id=hotel_id,
                start_date=start_date,
                end_date=end_date,
                total_analyses=total_analyses,
                average_sentiment_score=round(average_score, 3),
                sentiment_distribution=distribution,
                top_negative_reasons=top_reasons,
                guest_satisfaction_score=round(satisfaction_score, 1),
                processing_metrics=processing_metrics
            )
            
        except Exception as e:
            logger.error("Failed to get sentiment metrics",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    def _parse_period(self, period: str) -> int:
        """Parse period string to number of days"""
        period_map = {
            "1d": 1,
            "7d": 7,
            "30d": 30,
            "90d": 90
        }
        return period_map.get(period, 7)
    
    def _group_sentiments_by_time(
        self,
        sentiments: List[SentimentAnalysis],
        granularity: str
    ) -> List[SentimentDataPoint]:
        """Group sentiments by time granularity"""
        
        grouped = defaultdict(list)
        
        for sentiment in sentiments:
            if granularity == "hourly":
                key = sentiment.created_at.replace(minute=0, second=0, microsecond=0)
            elif granularity == "daily":
                key = sentiment.created_at.replace(hour=0, minute=0, second=0, microsecond=0)
            elif granularity == "weekly":
                # Start of week (Monday)
                days_since_monday = sentiment.created_at.weekday()
                key = sentiment.created_at.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
            else:
                key = sentiment.created_at.replace(hour=0, minute=0, second=0, microsecond=0)
            
            grouped[key].append(sentiment)
        
        # Convert to data points
        data_points = []
        for timestamp, group_sentiments in sorted(grouped.items()):
            scores = [s.sentiment_score for s in group_sentiments]
            average_score = sum(scores) / len(scores)
            
            positive_count = len([s for s in group_sentiments if s.sentiment_score > 0.1])
            negative_count = len([s for s in group_sentiments if s.sentiment_score < -0.1])
            neutral_count = len(group_sentiments) - positive_count - negative_count
            
            data_points.append(SentimentDataPoint(
                timestamp=timestamp,
                average_score=round(average_score, 3),
                message_count=len(group_sentiments),
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count
            ))
        
        return data_points
    
    def _calculate_sentiment_distribution(self, sentiments: List[SentimentAnalysis]) -> Dict[str, int]:
        """Calculate sentiment distribution"""
        distribution = {
            "very_positive": 0,
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "very_negative": 0
        }
        
        for sentiment in sentiments:
            score = sentiment.sentiment_score
            if score >= 0.5:
                distribution["very_positive"] += 1
            elif score >= 0.1:
                distribution["positive"] += 1
            elif score >= -0.1:
                distribution["neutral"] += 1
            elif score >= -0.5:
                distribution["negative"] += 1
            else:
                distribution["very_negative"] += 1
        
        return distribution
    
    def _extract_top_negative_reasons(self, negative_sentiments: List[SentimentAnalysis]) -> List[str]:
        """Extract top reasons for negative sentiment"""
        # This would analyze keywords and reasoning to find common themes
        # For now, return placeholder data
        return [
            "Service quality issues",
            "Room cleanliness concerns",
            "Staff responsiveness",
            "Facility maintenance",
            "Booking problems"
        ]
    
    def _calculate_model_accuracy(self, sentiments: List[SentimentAnalysis]) -> float:
        """Calculate AI model accuracy based on confidence scores"""
        confidence_scores = [s.confidence_score for s in sentiments if s.confidence_score]
        if not confidence_scores:
            return 0.0
        
        return sum(confidence_scores) / len(confidence_scores)


def get_sentiment_analytics_service(db: Session) -> SentimentAnalyticsService:
    """Get sentiment analytics service instance"""
    return SentimentAnalyticsService(db)
