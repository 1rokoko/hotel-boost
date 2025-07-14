"""
Analytics service for Admin Dashboard
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.orm import selectinload
import structlog

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType
from app.models.sentiment import SentimentAnalysis
from app.models.trigger import Trigger
from app.models.admin_user import AdminRole
from app.schemas.analytics import (
    AnalyticsTimeRange,
    DashboardOverviewResponse,
    MessageStatisticsResponse,
    HotelAnalyticsResponse,
    SystemMetricsResponse,
    MetricValue
)
from app.utils.analytics_aggregator import AnalyticsAggregator
from app.database import get_db_session

logger = structlog.get_logger(__name__)


class AnalyticsService:
    """
    Service for analytics data aggregation and processing
    """
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        Initialize analytics service
        
        Args:
            db_session: Database session (optional)
        """
        self.db_session = db_session
        self.aggregator = AnalyticsAggregator()
    
    async def get_dashboard_overview(
        self,
        hotel_id: Optional[uuid.UUID] = None,
        time_range: AnalyticsTimeRange = AnalyticsTimeRange.LAST_30_DAYS,
        user_role: AdminRole = AdminRole.VIEWER
    ) -> DashboardOverviewResponse:
        """
        Get dashboard overview statistics
        
        Args:
            hotel_id: Hotel ID for hotel-specific overview
            time_range: Time range for analytics
            user_role: User role for data filtering
            
        Returns:
            DashboardOverviewResponse: Dashboard overview data
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Get time range dates
                start_date, end_date = self._get_time_range_dates(time_range)
                
                # Get summary metrics
                total_messages = await self._get_total_messages(db, hotel_id, start_date, end_date)
                total_conversations = await self._get_total_conversations(db, hotel_id, start_date, end_date)
                total_hotels = await self._get_total_hotels(db, user_role, hotel_id)
                active_conversations = await self._get_active_conversations(db, hotel_id)
                
                # Get performance metrics
                avg_response_time = await self._get_average_response_time(db, hotel_id, start_date, end_date)
                message_volume_today = await self._get_message_volume_today(db, hotel_id)
                
                # Get sentiment metrics
                sentiment_summary = await self._get_sentiment_summary(db, hotel_id, start_date, end_date)
                guest_satisfaction = await self._get_guest_satisfaction_score(db, hotel_id, start_date, end_date)
                
                # Get system health
                system_health = await self._get_system_health_score(db)
                active_alerts = await self._get_active_alerts_count(db, hotel_id)
                
                # Get recent activity
                recent_activity = await self._get_recent_activity(db, hotel_id, limit=10)
                
                return DashboardOverviewResponse(
                    total_messages=MetricValue(value=total_messages),
                    total_conversations=MetricValue(value=total_conversations),
                    total_hotels=MetricValue(value=total_hotels),
                    active_conversations=MetricValue(value=active_conversations),
                    average_response_time=MetricValue(value=avg_response_time),
                    message_volume_today=message_volume_today,
                    sentiment_summary=sentiment_summary,
                    guest_satisfaction_score=guest_satisfaction,
                    system_health_score=system_health,
                    active_alerts=active_alerts,
                    recent_activity=recent_activity,
                    time_range=time_range,
                    generated_at=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error("Error getting dashboard overview", error=str(e))
            raise
    
    async def get_message_statistics(
        self,
        hotel_id: Optional[uuid.UUID] = None,
        time_range: AnalyticsTimeRange = AnalyticsTimeRange.LAST_7_DAYS,
        include_sentiment: bool = True
    ) -> MessageStatisticsResponse:
        """
        Get detailed message statistics
        
        Args:
            hotel_id: Hotel ID for hotel-specific stats
            time_range: Time range for statistics
            include_sentiment: Include sentiment analysis
            
        Returns:
            MessageStatisticsResponse: Message statistics data
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Get time range dates
                start_date, end_date = self._get_time_range_dates(time_range)
                
                # Get volume metrics
                total_messages = await self._get_total_messages(db, hotel_id, start_date, end_date)
                incoming_messages = await self._get_incoming_messages(db, hotel_id, start_date, end_date)
                outgoing_messages = await self._get_outgoing_messages(db, hotel_id, start_date, end_date)
                automated_messages = await self._get_automated_messages(db, hotel_id, start_date, end_date)
                
                # Get timing metrics
                avg_response_time = await self._get_average_response_time(db, hotel_id, start_date, end_date)
                median_response_time = await self._get_median_response_time(db, hotel_id, start_date, end_date)
                response_time_distribution = await self._get_response_time_distribution(db, hotel_id, start_date, end_date)
                
                # Get trends
                daily_message_counts = await self._get_daily_message_counts(db, hotel_id, start_date, end_date)
                hourly_distribution = await self._get_hourly_distribution(db, hotel_id, start_date, end_date)
                
                # Get message types
                message_type_distribution = await self._get_message_type_distribution(db, hotel_id, start_date, end_date)
                popular_keywords = await self._get_popular_keywords(db, hotel_id, start_date, end_date)
                
                # Get sentiment data if requested
                sentiment_distribution = None
                sentiment_trends = None
                if include_sentiment:
                    sentiment_distribution = await self._get_sentiment_distribution(db, hotel_id, start_date, end_date)
                    sentiment_trends = await self._get_sentiment_trends(db, hotel_id, start_date, end_date)
                
                # Get performance metrics
                delivery_rate = await self._get_delivery_rate(db, hotel_id, start_date, end_date)
                error_rate = await self._get_error_rate(db, hotel_id, start_date, end_date)
                
                return MessageStatisticsResponse(
                    total_messages=total_messages,
                    incoming_messages=incoming_messages,
                    outgoing_messages=outgoing_messages,
                    automated_messages=automated_messages,
                    average_response_time=avg_response_time,
                    median_response_time=median_response_time,
                    response_time_distribution=response_time_distribution,
                    daily_message_counts=daily_message_counts,
                    hourly_distribution=hourly_distribution,
                    message_type_distribution=message_type_distribution,
                    popular_keywords=popular_keywords,
                    sentiment_distribution=sentiment_distribution,
                    sentiment_trends=sentiment_trends,
                    delivery_rate=delivery_rate,
                    error_rate=error_rate,
                    time_range=time_range,
                    hotel_id=hotel_id
                )
                
        except Exception as e:
            logger.error("Error getting message statistics", error=str(e))
            raise
    
    async def get_hotel_analytics(
        self,
        hotel_id: uuid.UUID,
        time_range: AnalyticsTimeRange = AnalyticsTimeRange.LAST_30_DAYS,
        include_comparisons: bool = False
    ) -> HotelAnalyticsResponse:
        """
        Get detailed analytics for a specific hotel
        
        Args:
            hotel_id: Hotel ID
            time_range: Time range for analytics
            include_comparisons: Include period-over-period comparisons
            
        Returns:
            HotelAnalyticsResponse: Hotel analytics data
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Get hotel info
                hotel = await self._get_hotel_info(db, hotel_id)
                if not hotel:
                    raise ValueError(f"Hotel {hotel_id} not found")
                
                # Get time range dates
                start_date, end_date = self._get_time_range_dates(time_range)
                
                # Get guest metrics
                total_guests = await self._get_total_guests(db, hotel_id, start_date, end_date)
                new_guests = await self._get_new_guests(db, hotel_id, start_date, end_date)
                returning_guests = await self._get_returning_guests(db, hotel_id, start_date, end_date)
                guest_engagement = await self._get_guest_engagement_score(db, hotel_id, start_date, end_date)
                
                # Get conversation metrics
                total_conversations = await self._get_total_conversations(db, hotel_id, start_date, end_date)
                completed_conversations = await self._get_completed_conversations(db, hotel_id, start_date, end_date)
                escalated_conversations = await self._get_escalated_conversations(db, hotel_id, start_date, end_date)
                avg_conversation_length = await self._get_average_conversation_length(db, hotel_id, start_date, end_date)
                
                # Get trigger performance
                trigger_performance = await self._get_trigger_performance(db, hotel_id, start_date, end_date)
                automation_rate = await self._get_automation_rate(db, hotel_id, start_date, end_date)
                
                # Get staff metrics
                staff_response_time = await self._get_staff_response_time(db, hotel_id, start_date, end_date)
                staff_workload = await self._get_staff_workload(db, hotel_id, start_date, end_date)
                
                # Get satisfaction metrics
                satisfaction_score = await self._get_guest_satisfaction_score(db, hotel_id, start_date, end_date)
                nps_score = await self._get_nps_score(db, hotel_id, start_date, end_date)
                sentiment_breakdown = await self._get_sentiment_breakdown(db, hotel_id, start_date, end_date)
                
                # Get comparisons if requested
                period_comparison = None
                if include_comparisons:
                    period_comparison = await self._get_period_comparison(db, hotel_id, time_range)
                
                return HotelAnalyticsResponse(
                    hotel_id=hotel_id,
                    hotel_name=hotel.name,
                    total_guests=total_guests,
                    new_guests=new_guests,
                    returning_guests=returning_guests,
                    guest_engagement_score=guest_engagement,
                    total_conversations=total_conversations,
                    completed_conversations=completed_conversations,
                    escalated_conversations=escalated_conversations,
                    average_conversation_length=avg_conversation_length,
                    trigger_performance=trigger_performance,
                    automation_rate=automation_rate,
                    staff_response_time=staff_response_time,
                    staff_workload=staff_workload,
                    satisfaction_score=satisfaction_score,
                    nps_score=nps_score,
                    sentiment_breakdown=sentiment_breakdown,
                    period_comparison=period_comparison,
                    time_range=time_range,
                    generated_at=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error("Error getting hotel analytics", error=str(e))
            raise
    
    async def get_system_metrics(
        self,
        time_range: AnalyticsTimeRange = AnalyticsTimeRange.LAST_24_HOURS,
        include_performance: bool = True
    ) -> SystemMetricsResponse:
        """
        Get system-wide metrics and performance data
        
        Args:
            time_range: Time range for metrics
            include_performance: Include performance metrics
            
        Returns:
            SystemMetricsResponse: System metrics data
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Get time range dates
                start_date, end_date = self._get_time_range_dates(time_range)
                
                # Get API performance
                api_response_times = await self._get_api_response_times(db, start_date, end_date)
                api_error_rates = await self._get_api_error_rates(db, start_date, end_date)
                total_api_requests = await self._get_total_api_requests(db, start_date, end_date)
                
                # Get database performance
                database_metrics = await self._get_database_metrics(db, start_date, end_date)
                query_performance = await self._get_query_performance(db, start_date, end_date)
                
                # Get external services status
                external_service_status = await self._get_external_service_status()
                green_api_metrics = await self._get_green_api_metrics(db, start_date, end_date)
                deepseek_metrics = await self._get_deepseek_metrics(db, start_date, end_date)
                
                # Get resource utilization
                cpu_usage = await self._get_cpu_usage()
                memory_usage = await self._get_memory_usage()
                disk_usage = await self._get_disk_usage()
                
                # Get error tracking
                error_summary = await self._get_error_summary(db, start_date, end_date)
                critical_errors = await self._get_critical_errors(db, start_date, end_date)
                
                # Get performance trends if requested
                performance_trends = None
                if include_performance:
                    performance_trends = await self._get_performance_trends(db, start_date, end_date)
                
                # Get system health
                overall_health = await self._get_overall_health_score(db)
                uptime_percentage = await self._get_uptime_percentage(start_date, end_date)
                
                return SystemMetricsResponse(
                    api_response_times=api_response_times,
                    api_error_rates=api_error_rates,
                    total_api_requests=total_api_requests,
                    database_metrics=database_metrics,
                    query_performance=query_performance,
                    external_service_status=external_service_status,
                    green_api_metrics=green_api_metrics,
                    deepseek_metrics=deepseek_metrics,
                    cpu_usage=cpu_usage,
                    memory_usage=memory_usage,
                    disk_usage=disk_usage,
                    error_summary=error_summary,
                    critical_errors=critical_errors,
                    performance_trends=performance_trends,
                    overall_health_score=overall_health,
                    uptime_percentage=uptime_percentage,
                    time_range=time_range,
                    generated_at=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error("Error getting system metrics", error=str(e))
            raise
    
    def _get_time_range_dates(self, time_range: AnalyticsTimeRange) -> Tuple[datetime, datetime]:
        """
        Get start and end dates for time range
        
        Args:
            time_range: Time range enum
            
        Returns:
            Tuple[datetime, datetime]: Start and end dates
        """
        end_date = datetime.utcnow()
        
        if time_range == AnalyticsTimeRange.LAST_24_HOURS:
            start_date = end_date - timedelta(hours=24)
        elif time_range == AnalyticsTimeRange.LAST_7_DAYS:
            start_date = end_date - timedelta(days=7)
        elif time_range == AnalyticsTimeRange.LAST_30_DAYS:
            start_date = end_date - timedelta(days=30)
        elif time_range == AnalyticsTimeRange.LAST_90_DAYS:
            start_date = end_date - timedelta(days=90)
        elif time_range == AnalyticsTimeRange.LAST_YEAR:
            start_date = end_date - timedelta(days=365)
        else:
            # Default to last 30 days
            start_date = end_date - timedelta(days=30)
        
        return start_date, end_date

    # Helper methods for database queries
    async def _get_total_messages(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> int:
        """Get total messages count"""
        stmt = select(func.count(Message.id)).where(
            and_(
                Message.created_at >= start_date,
                Message.created_at <= end_date,
                Message.hotel_id == hotel_id if hotel_id else True
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def _get_total_conversations(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> int:
        """Get total conversations count"""
        stmt = select(func.count(Conversation.id)).where(
            and_(
                Conversation.created_at >= start_date,
                Conversation.created_at <= end_date,
                Conversation.hotel_id == hotel_id if hotel_id else True
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def _get_total_hotels(self, db: AsyncSession, user_role: AdminRole, hotel_id: Optional[uuid.UUID]) -> int:
        """Get total hotels count based on user role"""
        if user_role == AdminRole.SUPER_ADMIN:
            stmt = select(func.count(Hotel.id)).where(Hotel.is_active == True)
        elif hotel_id:
            return 1  # User can only see their hotel
        else:
            return 0

        result = await db.execute(stmt)
        return result.scalar() or 0

    async def _get_active_conversations(self, db: AsyncSession, hotel_id: Optional[uuid.UUID]) -> int:
        """Get active conversations count"""
        stmt = select(func.count(Conversation.id)).where(
            and_(
                Conversation.status == "active",
                Conversation.hotel_id == hotel_id if hotel_id else True
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def _get_average_response_time(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> float:
        """Get average response time"""
        # This would need to be implemented based on your message timing logic
        return 120.0  # Placeholder: 2 minutes

    async def _get_message_volume_today(self, db: AsyncSession, hotel_id: Optional[uuid.UUID]) -> int:
        """Get message volume for today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        stmt = select(func.count(Message.id)).where(
            and_(
                Message.created_at >= today_start,
                Message.created_at < today_end,
                Message.hotel_id == hotel_id if hotel_id else True
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def _get_sentiment_summary(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get sentiment analysis summary"""
        # This would query sentiment analysis data
        return {
            "positive": 65,
            "neutral": 25,
            "negative": 10,
            "average_score": 0.75
        }

    async def _get_guest_satisfaction_score(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> float:
        """Get guest satisfaction score"""
        # This would calculate based on sentiment analysis
        return 4.2  # Placeholder: out of 5

    async def _get_system_health_score(self, db: AsyncSession) -> float:
        """Get overall system health score"""
        # This would check various system components
        return 0.95  # Placeholder: 95% healthy

    async def _get_active_alerts_count(self, db: AsyncSession, hotel_id: Optional[uuid.UUID]) -> int:
        """Get active alerts count"""
        # This would query active alerts/notifications
        return 2  # Placeholder

    async def _get_recent_activity(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent system activity"""
        # This would query recent activities/events
        return [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "message_sent",
                "description": "Message sent to guest",
                "hotel_id": str(hotel_id) if hotel_id else None
            }
        ]

    # Additional helper methods would be implemented here for other metrics
    async def _get_incoming_messages(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> int:
        """Get incoming messages count"""
        stmt = select(func.count(Message.id)).where(
            and_(
                Message.created_at >= start_date,
                Message.created_at <= end_date,
                Message.message_type == MessageType.INCOMING,
                Message.hotel_id == hotel_id if hotel_id else True
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def _get_outgoing_messages(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> int:
        """Get outgoing messages count"""
        stmt = select(func.count(Message.id)).where(
            and_(
                Message.created_at >= start_date,
                Message.created_at <= end_date,
                Message.message_type == MessageType.OUTGOING,
                Message.hotel_id == hotel_id if hotel_id else True
            )
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def _get_automated_messages(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> int:
        """Get automated messages count"""
        # This would filter for automated messages
        return 50  # Placeholder

    async def _get_median_response_time(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> float:
        """Get median response time"""
        return 90.0  # Placeholder: 1.5 minutes

    async def _get_response_time_distribution(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get response time distribution"""
        return {
            "0-30s": 20,
            "30s-1m": 35,
            "1m-5m": 30,
            "5m+": 15
        }

    async def _get_daily_message_counts(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get daily message counts"""
        # This would group messages by day
        return [
            {"date": "2024-01-01", "count": 150},
            {"date": "2024-01-02", "count": 180}
        ]

    async def _get_hourly_distribution(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get hourly message distribution"""
        return {str(i): 10 + i for i in range(24)}  # Placeholder

    async def _get_message_type_distribution(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get message type distribution"""
        return {
            "text": 80,
            "image": 15,
            "document": 5
        }

    async def _get_popular_keywords(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get popular keywords"""
        return [
            {"keyword": "booking", "count": 45},
            {"keyword": "room", "count": 38}
        ]

    async def _get_sentiment_distribution(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get sentiment distribution"""
        return {
            "positive": 65,
            "neutral": 25,
            "negative": 10
        }

    async def _get_sentiment_trends(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get sentiment trends"""
        return [
            {"date": "2024-01-01", "positive": 70, "negative": 10},
            {"date": "2024-01-02", "positive": 65, "negative": 15}
        ]

    async def _get_delivery_rate(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> float:
        """Get message delivery rate"""
        return 98.5  # Placeholder: 98.5% delivery rate

    async def _get_error_rate(self, db: AsyncSession, hotel_id: Optional[uuid.UUID], start_date: datetime, end_date: datetime) -> float:
        """Get message error rate"""
        return 1.5  # Placeholder: 1.5% error rate
