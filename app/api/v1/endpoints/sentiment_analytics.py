"""
Sentiment analytics API endpoints
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import structlog

from app.database import get_db
from app.services.sentiment_analytics import SentimentAnalyticsService
from app.schemas.sentiment_analytics import (
    SentimentOverviewResponse,
    SentimentTrendsResponse,
    SentimentAlertsResponse,
    SentimentMetricsResponse,
    SentimentDistributionResponse,
    SentimentAnalyticsFilters
)
from app.core.tenant import require_tenant_context
from app.middleware.tenant import get_current_tenant_id

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/overview", response_model=SentimentOverviewResponse)
def get_sentiment_overview(
    hotel_id: str = Query(..., description="Hotel ID"),
    period: str = Query("7d", description="Time period (1d, 7d, 30d, 90d)"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get sentiment overview statistics for a hotel
    
    Args:
        hotel_id: Hotel ID
        period: Time period for analysis
        db: Database session
        analytics_service: Sentiment analytics service
        tenant_id: Current tenant ID
        
    Returns:
        Sentiment overview data
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        analytics_service = SentimentAnalyticsService(db)
        logger.info("Getting sentiment overview",
                   hotel_id=hotel_id,
                   period=period,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Get overview data
        overview = analytics_service.get_sentiment_overview(
            hotel_id=hotel_id,
            period=period,
            correlation_id=correlation_id
        )
        
        logger.info("Sentiment overview retrieved",
                   hotel_id=hotel_id,
                   total_messages=overview.total_messages,
                   average_score=overview.average_sentiment_score,
                   correlation_id=correlation_id)
        
        return overview
        
    except Exception as e:
        logger.error("Failed to get sentiment overview",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sentiment overview"
        )


@router.get("/trends", response_model=SentimentTrendsResponse)
def get_sentiment_trends(
    hotel_id: str = Query(..., description="Hotel ID"),
    days: int = Query(30, description="Number of days to analyze"),
    granularity: str = Query("daily", description="Granularity (hourly, daily, weekly)"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get sentiment trends over time
    
    Args:
        hotel_id: Hotel ID
        days: Number of days to analyze
        granularity: Time granularity
        db: Database session
        analytics_service: Sentiment analytics service
        tenant_id: Current tenant ID
        
    Returns:
        Sentiment trends data
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        analytics_service = SentimentAnalyticsService(db)
        logger.info("Getting sentiment trends",
                   hotel_id=hotel_id,
                   days=days,
                   granularity=granularity,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Validate parameters
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days must be between 1 and 365"
            )
        
        if granularity not in ["hourly", "daily", "weekly"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Granularity must be hourly, daily, or weekly"
            )
        
        # Get trends data
        trends = analytics_service.get_sentiment_trends(
            hotel_id=hotel_id,
            days=days,
            granularity=granularity,
            correlation_id=correlation_id
        )
        
        logger.info("Sentiment trends retrieved",
                   hotel_id=hotel_id,
                   data_points=len(trends.data_points),
                   correlation_id=correlation_id)
        
        return trends
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get sentiment trends",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sentiment trends"
        )


@router.get("/alerts", response_model=SentimentAlertsResponse)
def get_recent_alerts(
    hotel_id: str = Query(..., description="Hotel ID"),
    limit: int = Query(50, description="Maximum number of alerts to return"),
    status_filter: Optional[str] = Query(None, description="Filter by alert status"),
    priority_filter: Optional[str] = Query(None, description="Filter by priority"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get recent sentiment alerts
    
    Args:
        hotel_id: Hotel ID
        limit: Maximum number of alerts
        status_filter: Filter by alert status
        priority_filter: Filter by priority
        db: Database session
        analytics_service: Sentiment analytics service
        tenant_id: Current tenant ID
        
    Returns:
        Recent alerts data
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        analytics_service = SentimentAnalyticsService(db)
        logger.info("Getting recent alerts",
                   hotel_id=hotel_id,
                   limit=limit,
                   status_filter=status_filter,
                   priority_filter=priority_filter,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Validate parameters
        if limit < 1 or limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 1000"
            )
        
        # Get alerts data
        alerts = analytics_service.get_recent_alerts(
            hotel_id=hotel_id,
            limit=limit,
            status_filter=status_filter,
            priority_filter=priority_filter,
            correlation_id=correlation_id
        )
        
        logger.info("Recent alerts retrieved",
                   hotel_id=hotel_id,
                   alert_count=len(alerts.alerts),
                   correlation_id=correlation_id)
        
        return alerts
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get recent alerts",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recent alerts"
        )


@router.get("/metrics", response_model=SentimentMetricsResponse)
def get_sentiment_metrics(
    hotel_id: str = Query(..., description="Hotel ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get detailed sentiment metrics
    
    Args:
        hotel_id: Hotel ID
        start_date: Start date for analysis
        end_date: End date for analysis
        db: Database session
        analytics_service: Sentiment analytics service
        tenant_id: Current tenant ID
        
    Returns:
        Detailed sentiment metrics
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        analytics_service = SentimentAnalyticsService(db)
        logger.info("Getting sentiment metrics",
                   hotel_id=hotel_id,
                   start_date=start_date,
                   end_date=end_date,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Set default dates if not provided
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date"
            )
        
        if (end_date - start_date).days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 365 days"
            )
        
        # Get metrics data
        metrics = analytics_service.get_sentiment_metrics(
            hotel_id=hotel_id,
            start_date=start_date,
            end_date=end_date,
            correlation_id=correlation_id
        )
        
        logger.info("Sentiment metrics retrieved",
                   hotel_id=hotel_id,
                   date_range_days=(end_date - start_date).days,
                   correlation_id=correlation_id)
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get sentiment metrics",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sentiment metrics"
        )


@router.get("/distribution", response_model=SentimentDistributionResponse)
def get_sentiment_distribution(
    hotel_id: str = Query(..., description="Hotel ID"),
    period: str = Query("30d", description="Time period (7d, 30d, 90d)"),
    group_by: str = Query("sentiment_type", description="Group by (sentiment_type, hour, day_of_week)"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get sentiment distribution analysis
    
    Args:
        hotel_id: Hotel ID
        period: Time period for analysis
        group_by: How to group the data
        db: Database session
        analytics_service: Sentiment analytics service
        tenant_id: Current tenant ID
        
    Returns:
        Sentiment distribution data
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        analytics_service = SentimentAnalyticsService(db)
        logger.info("Getting sentiment distribution",
                   hotel_id=hotel_id,
                   period=period,
                   group_by=group_by,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Validate parameters
        if group_by not in ["sentiment_type", "hour", "day_of_week", "guest"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="group_by must be sentiment_type, hour, day_of_week, or guest"
            )
        
        # Get distribution data
        distribution = analytics_service.get_sentiment_distribution(
            hotel_id=hotel_id,
            period=period,
            group_by=group_by,
            correlation_id=correlation_id
        )
        
        logger.info("Sentiment distribution retrieved",
                   hotel_id=hotel_id,
                   distribution_items=len(distribution.distribution),
                   correlation_id=correlation_id)
        
        return distribution
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get sentiment distribution",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sentiment distribution"
        )


@router.post("/export")
def export_sentiment_data(
    filters: SentimentAnalyticsFilters,
    hotel_id: str = Query(..., description="Hotel ID"),
    format: str = Query("csv", description="Export format (csv, json, xlsx)"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Export sentiment data
    
    Args:
        hotel_id: Hotel ID
        filters: Export filters
        format: Export format
        db: Database session
        analytics_service: Sentiment analytics service
        tenant_id: Current tenant ID
        
    Returns:
        Exported data file
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        analytics_service = SentimentAnalyticsService(db)
        logger.info("Exporting sentiment data",
                   hotel_id=hotel_id,
                   format=format,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Validate format
        if format not in ["csv", "json", "xlsx"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format must be csv, json, or xlsx"
            )
        
        # Export data
        export_result = analytics_service.export_sentiment_data(
            hotel_id=hotel_id,
            filters=filters,
            format=format,
            correlation_id=correlation_id
        )
        
        logger.info("Sentiment data exported",
                   hotel_id=hotel_id,
                   format=format,
                   file_size=len(export_result.content),
                   correlation_id=correlation_id)
        
        # Return file response
        return JSONResponse(
            content={
                "download_url": export_result.download_url,
                "filename": export_result.filename,
                "file_size": export_result.file_size,
                "expires_at": export_result.expires_at.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to export sentiment data",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export sentiment data"
        )
