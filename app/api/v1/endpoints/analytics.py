"""
Analytics API endpoints for Admin Dashboard
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.api.v1.endpoints.admin_auth import get_current_admin_user
from app.schemas.analytics import (
    DashboardOverviewResponse,
    MessageStatisticsResponse,
    AnalyticsTimeRange,
    HotelAnalyticsResponse,
    SystemMetricsResponse
)
from app.services.analytics_service import (
    AnalyticsService,
    get_analytics_service
)
from app.models.admin_user import AdminPermission
from app.core.admin_security import AdminSecurity, AdminAuthorizationError

logger = structlog.get_logger(__name__)

router = APIRouter()


def require_permission(permission: AdminPermission):
    """Dependency to require specific permission"""
    def check_permission(
        current_user = Depends(get_current_admin_user)
    ):
        try:
            analytics_service = AnalyticsService(db)
            AdminSecurity.validate_admin_access(current_user, permission)
            return current_user
        except AdminAuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
    return check_permission


@router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    hotel_id: Optional[uuid.UUID] = Query(None, description="Hotel ID for hotel-specific overview"),
    time_range: AnalyticsTimeRange = Query(AnalyticsTimeRange.LAST_30_DAYS, description="Time range for analytics"),
    current_user = Depends(require_permission(AdminPermission.VIEW_ANALYTICS)),
    db: Session = Depends(get_db)
):
    """
    Get dashboard overview statistics
    
    Returns comprehensive overview data for the admin dashboard including:
    - Total messages, conversations, hotels
    - Active conversations and response times
    - Sentiment analysis summary
    - System health metrics
    """
    try:
        # Validate hotel access if hotel_id is provided
        if hotel_id and not current_user.can_access_hotel(hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        # Get overview data
        overview_data = await analytics_service.get_dashboard_overview(
            hotel_id=hotel_id,
            time_range=time_range,
            user_role=current_user.role
        )
        
        logger.info(
            "Dashboard overview retrieved",
            user_id=str(current_user.id),
            hotel_id=str(hotel_id) if hotel_id else "all",
            time_range=time_range.value
        )
        
        return overview_data
        
    except Exception as e:
        logger.error("Failed to get dashboard overview", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard overview"
        )


@router.get("/messages/stats", response_model=MessageStatisticsResponse)
def get_message_statistics(
    hotel_id: Optional[uuid.UUID] = Query(None, description="Hotel ID for hotel-specific stats"),
    time_range: AnalyticsTimeRange = Query(AnalyticsTimeRange.LAST_7_DAYS, description="Time range for statistics"),
    include_sentiment: bool = Query(True, description="Include sentiment analysis in statistics"),
    current_user = Depends(require_permission(AdminPermission.VIEW_ANALYTICS)),
    db: Session = Depends(get_db)
):
    """
    Get detailed message statistics
    
    Returns comprehensive message analytics including:
    - Message volume trends
    - Response time metrics
    - Sentiment distribution
    - Popular message types
    - Peak activity hours
    """
    try:
        # Validate hotel access if hotel_id is provided
        if hotel_id and not current_user.can_access_hotel(hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        # Get message statistics
        message_stats = await analytics_service.get_message_statistics(
            hotel_id=hotel_id,
            time_range=time_range,
            include_sentiment=include_sentiment
        )
        
        logger.info(
            "Message statistics retrieved",
            user_id=str(current_user.id),
            hotel_id=str(hotel_id) if hotel_id else "all",
            time_range=time_range.value
        )
        
        return message_stats
        
    except Exception as e:
        logger.error("Failed to get message statistics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve message statistics"
        )


@router.get("/hotels/{hotel_id}/analytics", response_model=HotelAnalyticsResponse)
async def get_hotel_analytics(
    hotel_id: uuid.UUID,
    time_range: AnalyticsTimeRange = Query(AnalyticsTimeRange.LAST_30_DAYS, description="Time range for analytics"),
    include_comparisons: bool = Query(False, description="Include period-over-period comparisons"),
    current_user = Depends(require_permission(AdminPermission.VIEW_HOTEL_ANALYTICS)),
    db: Session = Depends(get_db)
):
    """
    Get detailed analytics for a specific hotel
    
    Returns comprehensive hotel-specific analytics including:
    - Guest engagement metrics
    - Conversation flow analysis
    - Trigger performance
    - Staff response metrics
    - Guest satisfaction scores
    """
    try:
        # Validate hotel access
        if not current_user.can_access_hotel(hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        # Get hotel analytics
        hotel_analytics = await analytics_service.get_hotel_analytics(
            hotel_id=hotel_id,
            time_range=time_range,
            include_comparisons=include_comparisons
        )
        
        logger.info(
            "Hotel analytics retrieved",
            user_id=str(current_user.id),
            hotel_id=str(hotel_id),
            time_range=time_range.value
        )
        
        return hotel_analytics
        
    except Exception as e:
        logger.error("Failed to get hotel analytics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hotel analytics"
        )


@router.get("/system/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics(
    time_range: AnalyticsTimeRange = Query(AnalyticsTimeRange.LAST_24_HOURS, description="Time range for metrics"),
    include_performance: bool = Query(True, description="Include performance metrics"),
    current_user = Depends(require_permission(AdminPermission.VIEW_SYSTEM_METRICS)),
    db: Session = Depends(get_db)
):
    """
    Get system-wide metrics and performance data
    
    Returns system health and performance metrics including:
    - API response times
    - Database performance
    - External service status
    - Error rates and patterns
    - Resource utilization
    """
    try:
        # Get system metrics
        system_metrics = await analytics_service.get_system_metrics(
            time_range=time_range,
            include_performance=include_performance
        )
        
        logger.info(
            "System metrics retrieved",
            user_id=str(current_user.id),
            time_range=time_range.value
        )
        
        return system_metrics
        
    except Exception as e:
        logger.error("Failed to get system metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system metrics"
        )


@router.get("/trends/sentiment")
async def get_sentiment_trends(
    hotel_id: Optional[uuid.UUID] = Query(None, description="Hotel ID for hotel-specific trends"),
    time_range: AnalyticsTimeRange = Query(AnalyticsTimeRange.LAST_30_DAYS, description="Time range for trends"),
    granularity: str = Query("daily", regex="^(hourly|daily|weekly)$", description="Data granularity"),
    current_user = Depends(require_permission(AdminPermission.VIEW_ANALYTICS)),
    db: Session = Depends(get_db)
):
    """
    Get sentiment analysis trends over time
    
    Returns sentiment trends with configurable granularity.
    """
    try:
        # Validate hotel access if hotel_id is provided
        if hotel_id and not current_user.can_access_hotel(hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        # Get sentiment trends
        sentiment_trends = await analytics_service.get_sentiment_trends(
            hotel_id=hotel_id,
            time_range=time_range,
            granularity=granularity
        )
        
        logger.info(
            "Sentiment trends retrieved",
            user_id=str(current_user.id),
            hotel_id=str(hotel_id) if hotel_id else "all",
            time_range=time_range.value,
            granularity=granularity
        )
        
        return sentiment_trends
        
    except Exception as e:
        logger.error("Failed to get sentiment trends", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sentiment trends"
        )


@router.get("/performance/response-times")
async def get_response_time_analytics(
    hotel_id: Optional[uuid.UUID] = Query(None, description="Hotel ID for hotel-specific data"),
    time_range: AnalyticsTimeRange = Query(AnalyticsTimeRange.LAST_7_DAYS, description="Time range for analysis"),
    current_user = Depends(require_permission(AdminPermission.VIEW_ANALYTICS)),
    db: Session = Depends(get_db)
):
    """
    Get response time analytics
    
    Returns detailed response time metrics including:
    - Average response times
    - Response time distribution
    - Peak response time periods
    - Staff performance metrics
    """
    try:
        # Validate hotel access if hotel_id is provided
        if hotel_id and not current_user.can_access_hotel(hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        # Get response time analytics
        response_analytics = await analytics_service.get_response_time_analytics(
            hotel_id=hotel_id,
            time_range=time_range
        )
        
        logger.info(
            "Response time analytics retrieved",
            user_id=str(current_user.id),
            hotel_id=str(hotel_id) if hotel_id else "all",
            time_range=time_range.value
        )
        
        return response_analytics
        
    except Exception as e:
        logger.error("Failed to get response time analytics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve response time analytics"
        )
