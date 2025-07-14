"""
Analytics schemas for Admin Dashboard API
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class AnalyticsTimeRange(str, Enum):
    """Time range options for analytics"""
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    LAST_YEAR = "last_year"
    CUSTOM = "custom"


class MetricValue(BaseModel):
    """Base metric value with metadata"""
    value: float = Field(..., description="Metric value")
    change: Optional[float] = Field(None, description="Change from previous period")
    change_percentage: Optional[float] = Field(None, description="Percentage change from previous period")
    trend: Optional[str] = Field(None, description="Trend direction (up, down, stable)")


class DashboardOverviewResponse(BaseModel):
    """Dashboard overview response schema"""
    
    # Summary metrics
    total_messages: MetricValue = Field(..., description="Total messages in period")
    total_conversations: MetricValue = Field(..., description="Total conversations in period")
    total_hotels: MetricValue = Field(..., description="Total active hotels")
    active_conversations: MetricValue = Field(..., description="Currently active conversations")
    
    # Performance metrics
    average_response_time: MetricValue = Field(..., description="Average response time in seconds")
    message_volume_today: int = Field(..., description="Messages sent today")
    
    # Sentiment metrics
    sentiment_summary: Dict[str, Any] = Field(..., description="Sentiment analysis summary")
    guest_satisfaction_score: float = Field(..., description="Overall guest satisfaction score")
    
    # System health
    system_health_score: float = Field(..., description="Overall system health score (0-1)")
    active_alerts: int = Field(..., description="Number of active alerts")
    
    # Recent activity
    recent_activity: List[Dict[str, Any]] = Field(..., description="Recent system activity")
    
    # Time range info
    time_range: AnalyticsTimeRange = Field(..., description="Time range for the data")
    generated_at: datetime = Field(..., description="When the overview was generated")


class MessageStatisticsResponse(BaseModel):
    """Message statistics response schema"""
    
    # Volume metrics
    total_messages: int = Field(..., description="Total messages in period")
    incoming_messages: int = Field(..., description="Incoming messages from guests")
    outgoing_messages: int = Field(..., description="Outgoing messages to guests")
    automated_messages: int = Field(..., description="Automated messages sent")
    
    # Timing metrics
    average_response_time: float = Field(..., description="Average response time in seconds")
    median_response_time: float = Field(..., description="Median response time in seconds")
    response_time_distribution: Dict[str, int] = Field(..., description="Response time buckets")
    
    # Message trends
    daily_message_counts: List[Dict[str, Any]] = Field(..., description="Daily message volume")
    hourly_distribution: Dict[str, int] = Field(..., description="Messages by hour of day")
    
    # Message types
    message_type_distribution: Dict[str, int] = Field(..., description="Distribution by message type")
    popular_keywords: List[Dict[str, Any]] = Field(..., description="Most common keywords")
    
    # Sentiment data (if included)
    sentiment_distribution: Optional[Dict[str, int]] = Field(None, description="Sentiment distribution")
    sentiment_trends: Optional[List[Dict[str, Any]]] = Field(None, description="Sentiment over time")
    
    # Performance metrics
    delivery_rate: float = Field(..., description="Message delivery success rate")
    error_rate: float = Field(..., description="Message error rate")
    
    # Time range info
    time_range: AnalyticsTimeRange = Field(..., description="Time range for the data")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Hotel ID if hotel-specific")


class HotelAnalyticsResponse(BaseModel):
    """Hotel-specific analytics response schema"""
    
    hotel_id: uuid.UUID = Field(..., description="Hotel ID")
    hotel_name: str = Field(..., description="Hotel name")
    
    # Guest metrics
    total_guests: int = Field(..., description="Total unique guests")
    new_guests: int = Field(..., description="New guests in period")
    returning_guests: int = Field(..., description="Returning guests in period")
    guest_engagement_score: float = Field(..., description="Guest engagement score")
    
    # Conversation metrics
    total_conversations: int = Field(..., description="Total conversations")
    completed_conversations: int = Field(..., description="Completed conversations")
    escalated_conversations: int = Field(..., description="Escalated conversations")
    average_conversation_length: float = Field(..., description="Average conversation length")
    
    # Trigger performance
    trigger_performance: List[Dict[str, Any]] = Field(..., description="Trigger performance metrics")
    automation_rate: float = Field(..., description="Percentage of automated responses")
    
    # Staff metrics
    staff_response_time: float = Field(..., description="Average staff response time")
    staff_workload: Dict[str, Any] = Field(..., description="Staff workload distribution")
    
    # Guest satisfaction
    satisfaction_score: float = Field(..., description="Guest satisfaction score")
    nps_score: Optional[float] = Field(None, description="Net Promoter Score")
    sentiment_breakdown: Dict[str, int] = Field(..., description="Sentiment distribution")
    
    # Comparisons (if included)
    period_comparison: Optional[Dict[str, Any]] = Field(None, description="Period-over-period comparison")
    
    # Time range info
    time_range: AnalyticsTimeRange = Field(..., description="Time range for the data")
    generated_at: datetime = Field(..., description="When the analytics were generated")


class SystemMetricsResponse(BaseModel):
    """System-wide metrics response schema"""
    
    # API performance
    api_response_times: Dict[str, float] = Field(..., description="API endpoint response times")
    api_error_rates: Dict[str, float] = Field(..., description="API endpoint error rates")
    total_api_requests: int = Field(..., description="Total API requests in period")
    
    # Database performance
    database_metrics: Dict[str, Any] = Field(..., description="Database performance metrics")
    query_performance: List[Dict[str, Any]] = Field(..., description="Slow query analysis")
    
    # External services
    external_service_status: Dict[str, Dict[str, Any]] = Field(..., description="External service health")
    green_api_metrics: Dict[str, Any] = Field(..., description="Green API performance")
    deepseek_metrics: Dict[str, Any] = Field(..., description="DeepSeek API performance")
    
    # Resource utilization
    cpu_usage: float = Field(..., description="CPU usage percentage")
    memory_usage: float = Field(..., description="Memory usage percentage")
    disk_usage: float = Field(..., description="Disk usage percentage")
    
    # Error tracking
    error_summary: Dict[str, int] = Field(..., description="Error count by type")
    critical_errors: List[Dict[str, Any]] = Field(..., description="Recent critical errors")
    
    # Performance trends (if included)
    performance_trends: Optional[List[Dict[str, Any]]] = Field(None, description="Performance over time")
    
    # System health
    overall_health_score: float = Field(..., description="Overall system health score")
    uptime_percentage: float = Field(..., description="System uptime percentage")
    
    # Time range info
    time_range: AnalyticsTimeRange = Field(..., description="Time range for the data")
    generated_at: datetime = Field(..., description="When the metrics were generated")


class TrendDataPoint(BaseModel):
    """Single data point in a trend"""
    timestamp: datetime = Field(..., description="Data point timestamp")
    value: float = Field(..., description="Data point value")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SentimentTrendsResponse(BaseModel):
    """Sentiment trends response schema"""
    
    # Trend data
    positive_trend: List[TrendDataPoint] = Field(..., description="Positive sentiment trend")
    negative_trend: List[TrendDataPoint] = Field(..., description="Negative sentiment trend")
    neutral_trend: List[TrendDataPoint] = Field(..., description="Neutral sentiment trend")
    
    # Summary statistics
    average_sentiment: float = Field(..., description="Average sentiment score")
    sentiment_volatility: float = Field(..., description="Sentiment volatility measure")
    
    # Period comparison
    period_change: Dict[str, float] = Field(..., description="Change from previous period")
    
    # Configuration
    granularity: str = Field(..., description="Data granularity (hourly, daily, weekly)")
    time_range: AnalyticsTimeRange = Field(..., description="Time range for the data")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Hotel ID if hotel-specific")


class ResponseTimeAnalyticsResponse(BaseModel):
    """Response time analytics response schema"""
    
    # Response time metrics
    average_response_time: float = Field(..., description="Average response time in seconds")
    median_response_time: float = Field(..., description="Median response time in seconds")
    p95_response_time: float = Field(..., description="95th percentile response time")
    p99_response_time: float = Field(..., description="99th percentile response time")
    
    # Distribution
    response_time_buckets: Dict[str, int] = Field(..., description="Response time distribution")
    
    # Trends
    response_time_trend: List[TrendDataPoint] = Field(..., description="Response time over time")
    
    # Peak analysis
    peak_periods: List[Dict[str, Any]] = Field(..., description="Peak response time periods")
    
    # Staff performance
    staff_performance: Optional[List[Dict[str, Any]]] = Field(None, description="Individual staff metrics")
    
    # Time range info
    time_range: AnalyticsTimeRange = Field(..., description="Time range for the data")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Hotel ID if hotel-specific")


class AnalyticsExportRequest(BaseModel):
    """Request schema for analytics data export"""
    
    export_type: str = Field(..., regex="^(csv|json|excel)$", description="Export format")
    time_range: AnalyticsTimeRange = Field(..., description="Time range for export")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Hotel ID for hotel-specific export")
    include_raw_data: bool = Field(default=False, description="Include raw data in export")
    metrics: List[str] = Field(..., description="Metrics to include in export")


class AnalyticsExportResponse(BaseModel):
    """Response schema for analytics data export"""
    
    export_id: str = Field(..., description="Export job ID")
    download_url: str = Field(..., description="Download URL for the export")
    expires_at: datetime = Field(..., description="When the download link expires")
    file_size: int = Field(..., description="File size in bytes")
    record_count: int = Field(..., description="Number of records in export")
