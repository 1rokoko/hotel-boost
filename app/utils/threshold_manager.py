"""
Threshold management utilities for sentiment analysis
"""

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

import structlog
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.sentiment_config import SentimentConfig

logger = structlog.get_logger(__name__)


class ThresholdManager:
    """Manager for sentiment analysis thresholds and configuration"""
    
    def __init__(self, db: Session):
        self.db = db
        self.default_thresholds = self._get_default_thresholds()
    
    async def get_hotel_thresholds(
        self,
        hotel_id: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get sentiment thresholds for a specific hotel
        
        Args:
            hotel_id: Hotel ID
            correlation_id: Correlation ID for tracking
            
        Returns:
            Dictionary of threshold values
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.debug("Getting hotel thresholds",
                        hotel_id=hotel_id,
                        correlation_id=correlation_id)
            
            # Try to get hotel-specific configuration
            config = self.db.query(SentimentConfig).filter(
                SentimentConfig.hotel_id == hotel_id,
                SentimentConfig.is_active == True
            ).first()
            
            if config and config.thresholds:
                # Merge with defaults to ensure all thresholds are present
                thresholds = self.default_thresholds.copy()
                thresholds.update(config.thresholds)
                
                logger.debug("Using hotel-specific thresholds",
                           hotel_id=hotel_id,
                           threshold_count=len(thresholds),
                           correlation_id=correlation_id)
                
                return thresholds
            else:
                logger.debug("Using default thresholds",
                           hotel_id=hotel_id,
                           correlation_id=correlation_id)
                
                return self.default_thresholds.copy()
                
        except Exception as e:
            logger.error("Failed to get hotel thresholds",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            return self.default_thresholds.copy()
    
    async def update_hotel_thresholds(
        self,
        hotel_id: str,
        thresholds: Dict[str, Any],
        updated_by: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Update sentiment thresholds for a hotel
        
        Args:
            hotel_id: Hotel ID
            thresholds: New threshold values
            updated_by: User who updated the thresholds
            correlation_id: Correlation ID for tracking
            
        Returns:
            Success status
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Updating hotel thresholds",
                       hotel_id=hotel_id,
                       updated_by=updated_by,
                       correlation_id=correlation_id)
            
            # Validate thresholds
            if not self._validate_thresholds(thresholds):
                logger.error("Invalid threshold values",
                           hotel_id=hotel_id,
                           correlation_id=correlation_id)
                return False
            
            # Get existing configuration or create new one
            config = self.db.query(SentimentConfig).filter(
                SentimentConfig.hotel_id == hotel_id
            ).first()
            
            if config:
                # Update existing configuration
                config.thresholds = thresholds
                config.updated_by = updated_by
                config.updated_at = datetime.utcnow()
            else:
                # Create new configuration
                config = SentimentConfig(
                    hotel_id=hotel_id,
                    thresholds=thresholds,
                    notification_settings={},
                    escalation_rules={},
                    is_active=True,
                    created_by=updated_by,
                    updated_by=updated_by
                )
                self.db.add(config)
            
            self.db.commit()
            
            logger.info("Hotel thresholds updated successfully",
                       hotel_id=hotel_id,
                       threshold_count=len(thresholds),
                       correlation_id=correlation_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to update hotel thresholds",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            self.db.rollback()
            return False
    
    async def get_threshold_recommendations(
        self,
        hotel_id: str,
        analysis_period_days: int = 30,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get threshold recommendations based on historical data
        
        Args:
            hotel_id: Hotel ID
            analysis_period_days: Days of data to analyze
            correlation_id: Correlation ID for tracking
            
        Returns:
            Recommended threshold values with rationale
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            from datetime import timedelta
            from app.models.sentiment import SentimentAnalysis
            
            logger.info("Generating threshold recommendations",
                       hotel_id=hotel_id,
                       analysis_period_days=analysis_period_days,
                       correlation_id=correlation_id)
            
            # Get historical sentiment data
            start_date = datetime.utcnow() - timedelta(days=analysis_period_days)
            sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= start_date
            ).all()
            
            if len(sentiments) < 10:
                logger.warning("Insufficient data for recommendations",
                             hotel_id=hotel_id,
                             sentiment_count=len(sentiments),
                             correlation_id=correlation_id)
                return {
                    "recommendations": self.default_thresholds.copy(),
                    "rationale": "Insufficient historical data - using default thresholds",
                    "confidence": "low",
                    "data_points": len(sentiments)
                }
            
            # Analyze sentiment distribution
            scores = [s.sentiment_score for s in sentiments]
            scores.sort()
            
            # Calculate percentiles
            total_count = len(scores)
            p10 = scores[int(total_count * 0.1)]  # 10th percentile
            p25 = scores[int(total_count * 0.25)]  # 25th percentile
            p75 = scores[int(total_count * 0.75)]  # 75th percentile
            p90 = scores[int(total_count * 0.9)]   # 90th percentile
            
            # Generate recommendations
            recommendations = {
                "negative_sentiment_threshold": max(-0.5, p25),  # 25th percentile but not too strict
                "critical_sentiment_threshold": max(-0.8, p10),  # 10th percentile for critical
                "very_negative_threshold": max(-0.6, (p10 + p25) / 2),
                "low_confidence_threshold": 0.5,  # Keep default
                "consecutive_negative_threshold": 3,  # Keep default
                "escalation_negative_count": 3,  # Keep default
                "response_time_minutes": {
                    "critical": 5,
                    "high": 15,
                    "medium": 30,
                    "low": 60
                }
            }
            
            # Calculate confidence based on data volume and distribution
            confidence = self._calculate_recommendation_confidence(sentiments)
            
            # Generate rationale
            rationale = f"Based on {total_count} messages over {analysis_period_days} days. " \
                       f"Negative threshold set at {recommendations['negative_sentiment_threshold']:.2f} " \
                       f"(25th percentile: {p25:.2f}). Critical threshold at " \
                       f"{recommendations['critical_sentiment_threshold']:.2f} (10th percentile: {p10:.2f})."
            
            logger.info("Threshold recommendations generated",
                       hotel_id=hotel_id,
                       confidence=confidence,
                       data_points=total_count,
                       correlation_id=correlation_id)
            
            return {
                "recommendations": recommendations,
                "rationale": rationale,
                "confidence": confidence,
                "data_points": total_count,
                "analysis_period_days": analysis_period_days,
                "percentiles": {
                    "p10": p10,
                    "p25": p25,
                    "p75": p75,
                    "p90": p90
                }
            }
            
        except Exception as e:
            logger.error("Failed to generate threshold recommendations",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            return {
                "recommendations": self.default_thresholds.copy(),
                "rationale": f"Error generating recommendations: {str(e)}",
                "confidence": "low",
                "data_points": 0
            }
    
    async def validate_threshold_effectiveness(
        self,
        hotel_id: str,
        test_period_days: int = 7,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate effectiveness of current thresholds
        
        Args:
            hotel_id: Hotel ID
            test_period_days: Days to test against
            correlation_id: Correlation ID for tracking
            
        Returns:
            Effectiveness metrics
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            from datetime import timedelta
            from app.models.sentiment import SentimentAnalysis
            from app.models.staff_alert import StaffAlert
            
            logger.info("Validating threshold effectiveness",
                       hotel_id=hotel_id,
                       test_period_days=test_period_days,
                       correlation_id=correlation_id)
            
            # Get current thresholds
            thresholds = await self.get_hotel_thresholds(hotel_id, correlation_id)
            
            # Get test period data
            start_date = datetime.utcnow() - timedelta(days=test_period_days)
            sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= start_date
            ).all()
            
            alerts = self.db.query(StaffAlert).filter(
                StaffAlert.hotel_id == hotel_id,
                StaffAlert.created_at >= start_date
            ).all()
            
            # Calculate metrics
            total_messages = len(sentiments)
            negative_messages = len([s for s in sentiments if s.sentiment_score < thresholds["negative_sentiment_threshold"]])
            critical_messages = len([s for s in sentiments if s.sentiment_score < thresholds["critical_sentiment_threshold"]])
            
            total_alerts = len(alerts)
            false_positives = self._estimate_false_positives(alerts, sentiments)
            missed_issues = self._estimate_missed_issues(sentiments, thresholds)
            
            # Calculate effectiveness scores
            alert_precision = max(0, (total_alerts - false_positives) / total_alerts) if total_alerts > 0 else 0
            alert_recall = max(0, 1 - (missed_issues / max(1, negative_messages)))
            
            effectiveness = {
                "overall_score": (alert_precision + alert_recall) / 2,
                "alert_precision": alert_precision,
                "alert_recall": alert_recall,
                "alert_volume": total_alerts / max(1, total_messages),
                "false_positive_rate": false_positives / max(1, total_alerts),
                "missed_issue_rate": missed_issues / max(1, negative_messages),
                "metrics": {
                    "total_messages": total_messages,
                    "negative_messages": negative_messages,
                    "critical_messages": critical_messages,
                    "total_alerts": total_alerts,
                    "false_positives": false_positives,
                    "missed_issues": missed_issues
                }
            }
            
            logger.info("Threshold effectiveness validated",
                       hotel_id=hotel_id,
                       overall_score=effectiveness["overall_score"],
                       correlation_id=correlation_id)
            
            return effectiveness
            
        except Exception as e:
            logger.error("Failed to validate threshold effectiveness",
                        hotel_id=hotel_id,
                        error=str(e),
                        correlation_id=correlation_id)
            return {
                "overall_score": 0.0,
                "error": str(e)
            }
    
    def _get_default_thresholds(self) -> Dict[str, Any]:
        """Get default threshold values"""
        return {
            "negative_sentiment_threshold": -0.3,
            "critical_sentiment_threshold": -0.8,
            "very_negative_threshold": -0.6,
            "low_confidence_threshold": 0.5,
            "consecutive_negative_threshold": 3,
            "escalation_negative_count": 3,
            "response_time_minutes": {
                "critical": 5,
                "high": 15,
                "medium": 30,
                "low": 60,
                "minimal": 120
            },
            "notification_channels": {
                "critical": ["email", "sms", "slack"],
                "high": ["email", "slack"],
                "medium": ["email"],
                "low": ["dashboard"]
            }
        }
    
    def _validate_thresholds(self, thresholds: Dict[str, Any]) -> bool:
        """Validate threshold values"""
        try:
            # Check required thresholds exist
            required_thresholds = [
                "negative_sentiment_threshold",
                "critical_sentiment_threshold"
            ]
            
            for threshold in required_thresholds:
                if threshold not in thresholds:
                    return False
            
            # Check value ranges
            if not (-1.0 <= thresholds["negative_sentiment_threshold"] <= 0.0):
                return False
            
            if not (-1.0 <= thresholds["critical_sentiment_threshold"] <= 0.0):
                return False
            
            # Check logical consistency
            if thresholds["critical_sentiment_threshold"] >= thresholds["negative_sentiment_threshold"]:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _calculate_recommendation_confidence(self, sentiments: List) -> str:
        """Calculate confidence level for recommendations"""
        data_points = len(sentiments)
        
        if data_points >= 1000:
            return "high"
        elif data_points >= 100:
            return "medium"
        elif data_points >= 30:
            return "low"
        else:
            return "very_low"
    
    def _estimate_false_positives(self, alerts: List, sentiments: List) -> int:
        """Estimate false positive alerts"""
        # Simplified estimation - in reality would need more sophisticated analysis
        return max(0, len(alerts) - len([s for s in sentiments if s.sentiment_score < -0.3]))
    
    def _estimate_missed_issues(self, sentiments: List, thresholds: Dict[str, Any]) -> int:
        """Estimate missed issues that should have triggered alerts"""
        # Simplified estimation
        very_negative = len([s for s in sentiments if s.sentiment_score < -0.7])
        threshold_negative = len([s for s in sentiments if s.sentiment_score < thresholds["negative_sentiment_threshold"]])
        
        # Estimate that very negative messages without alerts are missed issues
        return max(0, very_negative - threshold_negative)


def get_threshold_manager(db: Session) -> ThresholdManager:
    """Get threshold manager instance"""
    return ThresholdManager(db)
