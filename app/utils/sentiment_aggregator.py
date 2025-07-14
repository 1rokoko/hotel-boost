"""
Sentiment data aggregation utilities
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from collections import defaultdict, Counter
from dataclasses import dataclass
import statistics

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.sentiment import SentimentAnalysis, SentimentSummary
from app.models.staff_alert import StaffAlert
from app.models.message import Message
from app.models.guest import Guest

logger = structlog.get_logger(__name__)


@dataclass
class AggregationPeriod:
    """Period configuration for aggregation"""
    start_date: datetime
    end_date: datetime
    granularity: str  # hourly, daily, weekly, monthly
    
    def get_period_key(self, timestamp: datetime) -> datetime:
        """Get period key for a timestamp"""
        if self.granularity == "hourly":
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif self.granularity == "daily":
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.granularity == "weekly":
            # Start of week (Monday)
            days_since_monday = timestamp.weekday()
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        elif self.granularity == "monthly":
            return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)


class SentimentAggregator:
    """Service for aggregating sentiment data"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def aggregate_sentiment_by_period(
        self,
        hotel_id: str,
        period: AggregationPeriod,
        correlation_id: Optional[str] = None
    ) -> Dict[datetime, Dict[str, Any]]:
        """
        Aggregate sentiment data by time period
        
        Args:
            hotel_id: Hotel ID
            period: Aggregation period configuration
            correlation_id: Correlation ID for tracking
            
        Returns:
            Dictionary of aggregated data by period
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Aggregating sentiment by period",
                       hotel_id=hotel_id,
                       granularity=period.granularity,
                       start_date=period.start_date,
                       end_date=period.end_date,
                       correlation_id=correlation_id)
            
            # Get sentiment analyses for period
            sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= period.start_date,
                SentimentAnalysis.created_at <= period.end_date
            ).all()
            
            # Group by period
            grouped_data = defaultdict(list)
            for sentiment in sentiments:
                period_key = period.get_period_key(sentiment.created_at)
                grouped_data[period_key].append(sentiment)
            
            # Aggregate each period
            aggregated = {}
            for period_key, period_sentiments in grouped_data.items():
                aggregated[period_key] = self._aggregate_sentiment_group(period_sentiments)
            
            logger.info("Sentiment aggregation completed",
                       hotel_id=hotel_id,
                       periods_aggregated=len(aggregated),
                       total_sentiments=len(sentiments),
                       correlation_id=correlation_id)
            
            return aggregated
            
        except Exception as e:
            logger.error("Failed to aggregate sentiment by period",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    def aggregate_sentiment_by_guest(
        self,
        hotel_id: str,
        start_date: datetime,
        end_date: datetime,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate sentiment data by guest
        
        Args:
            hotel_id: Hotel ID
            start_date: Start date
            end_date: End date
            correlation_id: Correlation ID for tracking
            
        Returns:
            Dictionary of aggregated data by guest
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Aggregating sentiment by guest",
                       hotel_id=hotel_id,
                       start_date=start_date,
                       end_date=end_date,
                       correlation_id=correlation_id)
            
            # Get sentiment analyses for period
            sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= start_date,
                SentimentAnalysis.created_at <= end_date
            ).all()
            
            # Group by guest
            grouped_data = defaultdict(list)
            for sentiment in sentiments:
                grouped_data[str(sentiment.guest_id)].append(sentiment)
            
            # Aggregate each guest
            aggregated = {}
            for guest_id, guest_sentiments in grouped_data.items():
                aggregated[guest_id] = self._aggregate_sentiment_group(guest_sentiments)
                
                # Add guest-specific metrics
                aggregated[guest_id].update({
                    "sentiment_trend": self._calculate_sentiment_trend(guest_sentiments),
                    "interaction_frequency": self._calculate_interaction_frequency(guest_sentiments),
                    "escalation_risk": self._calculate_escalation_risk(guest_sentiments)
                })
            
            logger.info("Guest sentiment aggregation completed",
                       hotel_id=hotel_id,
                       guests_analyzed=len(aggregated),
                       total_sentiments=len(sentiments),
                       correlation_id=correlation_id)
            
            return aggregated
            
        except Exception as e:
            logger.error("Failed to aggregate sentiment by guest",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    def aggregate_sentiment_by_category(
        self,
        hotel_id: str,
        start_date: datetime,
        end_date: datetime,
        category_field: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate sentiment data by category
        
        Args:
            hotel_id: Hotel ID
            start_date: Start date
            end_date: End date
            category_field: Field to categorize by (sentiment_type, hour, day_of_week)
            correlation_id: Correlation ID for tracking
            
        Returns:
            Dictionary of aggregated data by category
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Aggregating sentiment by category",
                       hotel_id=hotel_id,
                       category_field=category_field,
                       correlation_id=correlation_id)
            
            # Get sentiment analyses for period
            sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= start_date,
                SentimentAnalysis.created_at <= end_date
            ).all()
            
            # Group by category
            grouped_data = defaultdict(list)
            for sentiment in sentiments:
                category_value = self._get_category_value(sentiment, category_field)
                grouped_data[category_value].append(sentiment)
            
            # Aggregate each category
            aggregated = {}
            for category, category_sentiments in grouped_data.items():
                aggregated[category] = self._aggregate_sentiment_group(category_sentiments)
            
            logger.info("Category sentiment aggregation completed",
                       hotel_id=hotel_id,
                       categories_analyzed=len(aggregated),
                       total_sentiments=len(sentiments),
                       correlation_id=correlation_id)
            
            return aggregated
            
        except Exception as e:
            logger.error("Failed to aggregate sentiment by category",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    def calculate_sentiment_benchmarks(
        self,
        hotel_id: str,
        comparison_period_days: int = 30,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate sentiment benchmarks and comparisons
        
        Args:
            hotel_id: Hotel ID
            comparison_period_days: Days to compare against
            correlation_id: Correlation ID for tracking
            
        Returns:
            Benchmark data
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Calculating sentiment benchmarks",
                       hotel_id=hotel_id,
                       comparison_period_days=comparison_period_days,
                       correlation_id=correlation_id)
            
            end_date = datetime.utcnow()
            current_start = end_date - timedelta(days=comparison_period_days)
            previous_start = current_start - timedelta(days=comparison_period_days)
            
            # Get current period data
            current_sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= current_start,
                SentimentAnalysis.created_at <= end_date
            ).all()
            
            # Get previous period data
            previous_sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= previous_start,
                SentimentAnalysis.created_at < current_start
            ).all()
            
            # Calculate metrics for both periods
            current_metrics = self._aggregate_sentiment_group(current_sentiments)
            previous_metrics = self._aggregate_sentiment_group(previous_sentiments)
            
            # Calculate changes
            score_change = current_metrics["average_score"] - previous_metrics["average_score"]
            volume_change = current_metrics["total_count"] - previous_metrics["total_count"]
            
            # Calculate percentile rankings (simplified)
            performance_level = self._calculate_performance_level(current_metrics["average_score"])
            
            benchmarks = {
                "current_period": current_metrics,
                "previous_period": previous_metrics,
                "changes": {
                    "score_change": round(score_change, 3),
                    "volume_change": volume_change,
                    "score_change_percentage": round((score_change / abs(previous_metrics["average_score"])) * 100, 1) if previous_metrics["average_score"] != 0 else 0
                },
                "performance_level": performance_level,
                "trends": {
                    "sentiment_improving": score_change > 0.05,
                    "volume_increasing": volume_change > 0,
                    "consistency_score": self._calculate_consistency_score(current_sentiments)
                }
            }
            
            logger.info("Sentiment benchmarks calculated",
                       hotel_id=hotel_id,
                       score_change=score_change,
                       performance_level=performance_level,
                       correlation_id=correlation_id)
            
            return benchmarks
            
        except Exception as e:
            logger.error("Failed to calculate sentiment benchmarks",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    def _aggregate_sentiment_group(self, sentiments: List[SentimentAnalysis]) -> Dict[str, Any]:
        """Aggregate a group of sentiment analyses"""
        if not sentiments:
            return {
                "total_count": 0,
                "average_score": 0.0,
                "median_score": 0.0,
                "score_std_dev": 0.0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "requires_attention_count": 0,
                "average_confidence": 0.0,
                "score_distribution": {}
            }
        
        scores = [s.sentiment_score for s in sentiments]
        confidences = [s.confidence_score for s in sentiments if s.confidence_score]
        
        # Basic statistics
        total_count = len(sentiments)
        average_score = sum(scores) / len(scores)
        median_score = statistics.median(scores)
        score_std_dev = statistics.stdev(scores) if len(scores) > 1 else 0.0
        
        # Sentiment counts
        positive_count = len([s for s in sentiments if s.sentiment_score > 0.1])
        negative_count = len([s for s in sentiments if s.sentiment_score < -0.1])
        neutral_count = total_count - positive_count - negative_count
        requires_attention_count = len([s for s in sentiments if s.requires_attention])
        
        # Confidence
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Score distribution
        score_distribution = self._calculate_score_distribution(scores)
        
        return {
            "total_count": total_count,
            "average_score": round(average_score, 3),
            "median_score": round(median_score, 3),
            "score_std_dev": round(score_std_dev, 3),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "requires_attention_count": requires_attention_count,
            "average_confidence": round(average_confidence, 3),
            "score_distribution": score_distribution
        }
    
    def _calculate_sentiment_trend(self, sentiments: List[SentimentAnalysis]) -> str:
        """Calculate sentiment trend for a group"""
        if len(sentiments) < 3:
            return "insufficient_data"
        
        # Sort by timestamp
        sorted_sentiments = sorted(sentiments, key=lambda x: x.created_at)
        
        # Compare first third vs last third
        third = len(sorted_sentiments) // 3
        early_scores = [s.sentiment_score for s in sorted_sentiments[:third]]
        late_scores = [s.sentiment_score for s in sorted_sentiments[-third:]]
        
        early_avg = sum(early_scores) / len(early_scores)
        late_avg = sum(late_scores) / len(late_scores)
        
        if late_avg > early_avg + 0.1:
            return "improving"
        elif late_avg < early_avg - 0.1:
            return "declining"
        else:
            return "stable"
    
    def _calculate_interaction_frequency(self, sentiments: List[SentimentAnalysis]) -> float:
        """Calculate interaction frequency (messages per day)"""
        if not sentiments:
            return 0.0
        
        sorted_sentiments = sorted(sentiments, key=lambda x: x.created_at)
        first_date = sorted_sentiments[0].created_at
        last_date = sorted_sentiments[-1].created_at
        
        days = max(1, (last_date - first_date).days)
        return round(len(sentiments) / days, 2)
    
    def _calculate_escalation_risk(self, sentiments: List[SentimentAnalysis]) -> str:
        """Calculate escalation risk level"""
        if not sentiments:
            return "low"
        
        recent_sentiments = sorted(sentiments, key=lambda x: x.created_at)[-5:]  # Last 5 messages
        negative_count = len([s for s in recent_sentiments if s.sentiment_score < -0.3])
        attention_count = len([s for s in recent_sentiments if s.requires_attention])
        
        if attention_count >= 2 or negative_count >= 3:
            return "high"
        elif attention_count >= 1 or negative_count >= 2:
            return "medium"
        else:
            return "low"
    
    def _get_category_value(self, sentiment: SentimentAnalysis, category_field: str) -> str:
        """Get category value for a sentiment"""
        if category_field == "sentiment_type":
            return sentiment.sentiment_type
        elif category_field == "hour":
            return str(sentiment.created_at.hour)
        elif category_field == "day_of_week":
            return sentiment.created_at.strftime("%A")
        elif category_field == "confidence_level":
            if sentiment.confidence_score >= 0.8:
                return "high_confidence"
            elif sentiment.confidence_score >= 0.6:
                return "medium_confidence"
            else:
                return "low_confidence"
        else:
            return "unknown"
    
    def _calculate_score_distribution(self, scores: List[float]) -> Dict[str, int]:
        """Calculate score distribution in ranges"""
        distribution = {
            "very_positive": 0,    # 0.5 to 1.0
            "positive": 0,         # 0.1 to 0.5
            "neutral": 0,          # -0.1 to 0.1
            "negative": 0,         # -0.5 to -0.1
            "very_negative": 0     # -1.0 to -0.5
        }
        
        for score in scores:
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
    
    def _calculate_performance_level(self, average_score: float) -> str:
        """Calculate performance level based on average score"""
        if average_score >= 0.5:
            return "excellent"
        elif average_score >= 0.2:
            return "good"
        elif average_score >= -0.1:
            return "average"
        elif average_score >= -0.3:
            return "below_average"
        else:
            return "poor"
    
    def _calculate_consistency_score(self, sentiments: List[SentimentAnalysis]) -> float:
        """Calculate consistency score (lower standard deviation = higher consistency)"""
        if len(sentiments) < 2:
            return 1.0
        
        scores = [s.sentiment_score for s in sentiments]
        std_dev = statistics.stdev(scores)
        
        # Convert to 0-1 scale (lower std_dev = higher consistency)
        # Assuming max reasonable std_dev is 1.0
        consistency = max(0.0, 1.0 - std_dev)
        return round(consistency, 3)


def get_sentiment_aggregator(db: Session) -> SentimentAggregator:
    """Get sentiment aggregator instance"""
    return SentimentAggregator(db)
