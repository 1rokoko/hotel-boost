"""
Schemas for sentiment analytics API responses
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field


class SentimentDataPoint(BaseModel):
    """Data point for sentiment trends"""
    timestamp: datetime
    average_score: float = Field(..., ge=-1.0, le=1.0)
    message_count: int = Field(..., ge=0)
    positive_count: int = Field(..., ge=0)
    negative_count: int = Field(..., ge=0)
    neutral_count: int = Field(..., ge=0)


class SentimentOverviewResponse(BaseModel):
    """Response schema for sentiment overview"""
    hotel_id: str
    period: str
    total_messages: int = Field(..., ge=0)
    average_sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    positive_count: int = Field(..., ge=0)
    negative_count: int = Field(..., ge=0)
    neutral_count: int = Field(..., ge=0)
    requires_attention_count: int = Field(..., ge=0)
    alerts_triggered: int = Field(..., ge=0)
    response_rate: float = Field(..., ge=0.0, le=100.0, description="Percentage of alerts responded to")
    average_response_time_minutes: float = Field(..., ge=0.0)


class SentimentTrendsResponse(BaseModel):
    """Response schema for sentiment trends"""
    hotel_id: str
    period_days: int = Field(..., ge=1)
    granularity: str
    data_points: List[SentimentDataPoint]
    trend_direction: str = Field(..., description="improving, declining, stable, or insufficient_data")


class AlertSummary(BaseModel):
    """Summary of a staff alert"""
    id: str
    alert_type: str
    priority: str
    status: str
    title: str
    description: str
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    urgency_level: float = Field(..., ge=1.0, le=5.0)
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    is_overdue: bool


class SentimentAlertsResponse(BaseModel):
    """Response schema for sentiment alerts"""
    hotel_id: str
    total_alerts: int = Field(..., ge=0)
    pending_alerts: int = Field(..., ge=0)
    overdue_alerts: int = Field(..., ge=0)
    alerts: List[AlertSummary]


class SentimentMetricsResponse(BaseModel):
    """Response schema for detailed sentiment metrics"""
    hotel_id: str
    start_date: date
    end_date: date
    total_analyses: int = Field(..., ge=0)
    average_sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    sentiment_distribution: Dict[str, int]
    top_negative_reasons: List[str]
    guest_satisfaction_score: float = Field(..., ge=0.0, le=100.0)
    processing_metrics: Dict[str, Any]


class SentimentDistributionItem(BaseModel):
    """Item in sentiment distribution"""
    category: str
    count: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0, le=100.0)
    average_score: float = Field(..., ge=-1.0, le=1.0)


class SentimentDistributionResponse(BaseModel):
    """Response schema for sentiment distribution"""
    hotel_id: str
    period: str
    group_by: str
    total_items: int = Field(..., ge=0)
    distribution: List[SentimentDistributionItem]


class SentimentAnalyticsFilters(BaseModel):
    """Filters for sentiment analytics export"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    sentiment_types: Optional[List[str]] = None
    score_range: Optional[Dict[str, float]] = None
    guest_ids: Optional[List[str]] = None
    include_alerts: bool = True
    include_raw_data: bool = False


class ExportResult(BaseModel):
    """Result of data export"""
    download_url: str
    filename: str
    file_size: int = Field(..., ge=0)
    format: str
    expires_at: datetime
    content: Optional[bytes] = None


class SentimentInsight(BaseModel):
    """Sentiment insight or recommendation"""
    type: str = Field(..., description="Type of insight (trend, anomaly, recommendation)")
    title: str
    description: str
    severity: str = Field(..., description="low, medium, high, critical")
    confidence: float = Field(..., ge=0.0, le=1.0)
    data_points: Optional[Dict[str, Any]] = None
    recommended_actions: Optional[List[str]] = None


class SentimentInsightsResponse(BaseModel):
    """Response schema for sentiment insights"""
    hotel_id: str
    generated_at: datetime
    insights: List[SentimentInsight]
    summary: str


class GuestSentimentProfile(BaseModel):
    """Sentiment profile for a specific guest"""
    guest_id: str
    total_messages: int = Field(..., ge=0)
    average_sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    sentiment_trend: str = Field(..., description="improving, declining, stable")
    last_interaction: datetime
    requires_attention: bool
    alert_count: int = Field(..., ge=0)
    satisfaction_level: str = Field(..., description="very_satisfied, satisfied, neutral, dissatisfied, very_dissatisfied")


class GuestSentimentProfilesResponse(BaseModel):
    """Response schema for guest sentiment profiles"""
    hotel_id: str
    total_guests: int = Field(..., ge=0)
    period: str
    profiles: List[GuestSentimentProfile]


class SentimentComparisonResponse(BaseModel):
    """Response schema for sentiment comparison between periods"""
    hotel_id: str
    current_period: Dict[str, Any]
    previous_period: Dict[str, Any]
    comparison_metrics: Dict[str, Any]
    improvement_areas: List[str]
    decline_areas: List[str]


class SentimentBenchmarkResponse(BaseModel):
    """Response schema for sentiment benchmarking"""
    hotel_id: str
    hotel_metrics: Dict[str, Any]
    industry_benchmarks: Dict[str, Any]
    performance_ranking: str = Field(..., description="top_quartile, above_average, average, below_average, bottom_quartile")
    improvement_opportunities: List[str]


class SentimentPredictionResponse(BaseModel):
    """Response schema for sentiment predictions"""
    hotel_id: str
    prediction_period: str
    predicted_metrics: Dict[str, Any]
    confidence_level: float = Field(..., ge=0.0, le=1.0)
    risk_factors: List[str]
    recommended_interventions: List[str]


class SentimentReportResponse(BaseModel):
    """Response schema for comprehensive sentiment report"""
    hotel_id: str
    report_type: str
    generated_at: datetime
    period: str
    executive_summary: str
    key_metrics: Dict[str, Any]
    trends_analysis: Dict[str, Any]
    guest_insights: Dict[str, Any]
    operational_recommendations: List[str]
    appendices: Optional[Dict[str, Any]] = None


# Export all schemas
__all__ = [
    'SentimentDataPoint',
    'SentimentOverviewResponse',
    'SentimentTrendsResponse',
    'AlertSummary',
    'SentimentAlertsResponse',
    'SentimentMetricsResponse',
    'SentimentDistributionItem',
    'SentimentDistributionResponse',
    'SentimentAnalyticsFilters',
    'ExportResult',
    'SentimentInsight',
    'SentimentInsightsResponse',
    'GuestSentimentProfile',
    'GuestSentimentProfilesResponse',
    'SentimentComparisonResponse',
    'SentimentBenchmarkResponse',
    'SentimentPredictionResponse',
    'SentimentReportResponse'
]
