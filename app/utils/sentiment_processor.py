"""
Sentiment analysis result processor utilities
"""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.sentiment import SentimentAnalysis, SentimentSummary
from app.models.message import Message
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.schemas.deepseek import SentimentAnalysisResult, SentimentType

logger = structlog.get_logger(__name__)


class SentimentTrend(Enum):
    """Sentiment trend indicators"""
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    VOLATILE = "volatile"


class SentimentProcessor:
    """Processor for sentiment analysis results and aggregations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def process_sentiment_result(
        self,
        result: SentimentAnalysisResult,
        message: Message,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Process sentiment analysis result and generate insights
        
        Args:
            result: Sentiment analysis result
            message: Original message
            correlation_id: Correlation ID for tracking
            
        Returns:
            Dict containing processed insights
        """
        try:
            insights = {
                "sentiment_classification": self._classify_sentiment_level(result),
                "urgency_assessment": self._assess_urgency(result, message),
                "guest_sentiment_history": self._get_guest_sentiment_history(message.guest_id),
                "conversation_context": self._analyze_conversation_context(message),
                "recommended_actions": self._recommend_actions(result, message),
                "escalation_needed": self._should_escalate(result, message),
                "correlation_id": correlation_id
            }
            
            logger.info("Sentiment result processed",
                       message_id=str(message.id),
                       sentiment=result.sentiment.value,
                       urgency=insights["urgency_assessment"]["level"],
                       escalation_needed=insights["escalation_needed"],
                       correlation_id=correlation_id)
            
            return insights
            
        except Exception as e:
            logger.error("Failed to process sentiment result",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    def _classify_sentiment_level(self, result: SentimentAnalysisResult) -> Dict[str, Any]:
        """Classify sentiment into detailed levels"""
        if result.score >= 0.7:
            level = "very_positive"
        elif result.score >= 0.3:
            level = "positive"
        elif result.score >= -0.1:
            level = "neutral"
        elif result.score >= -0.5:
            level = "negative"
        elif result.score >= -0.8:
            level = "very_negative"
        else:
            level = "critical"
        
        return {
            "level": level,
            "score": result.score,
            "confidence": result.confidence,
            "requires_attention": result.requires_attention,
            "keywords": result.keywords or []
        }
    
    def _assess_urgency(
        self,
        result: SentimentAnalysisResult,
        message: Message
    ) -> Dict[str, Any]:
        """Assess urgency level based on sentiment and context"""
        urgency_score = 0
        factors = []
        
        # Sentiment score factor
        if result.score < -0.8:
            urgency_score += 5
            factors.append("critical_sentiment")
        elif result.score < -0.5:
            urgency_score += 3
            factors.append("very_negative_sentiment")
        elif result.score < -0.3:
            urgency_score += 2
            factors.append("negative_sentiment")
        
        # Requires attention flag
        if result.requires_attention:
            urgency_score += 3
            factors.append("ai_flagged_attention")
        
        # Low confidence in positive sentiment (might be sarcasm)
        if result.sentiment == SentimentType.POSITIVE and result.confidence < 0.5:
            urgency_score += 1
            factors.append("uncertain_positive")
        
        # Recent negative messages from same guest
        recent_negative = self._count_recent_negative_messages(message.guest_id)
        if recent_negative >= 3:
            urgency_score += 2
            factors.append("repeated_negative_messages")
        
        # Determine urgency level
        if urgency_score >= 7:
            level = "critical"
        elif urgency_score >= 5:
            level = "high"
        elif urgency_score >= 3:
            level = "medium"
        elif urgency_score >= 1:
            level = "low"
        else:
            level = "minimal"
        
        return {
            "level": level,
            "score": urgency_score,
            "factors": factors,
            "response_time_target": self._get_response_time_target(level)
        }
    
    def _get_guest_sentiment_history(self, guest_id: str) -> Dict[str, Any]:
        """Get guest's sentiment history and trends"""
        try:
            # Get recent sentiment analyses for guest
            recent_sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.guest_id == guest_id,
                SentimentAnalysis.created_at >= datetime.utcnow() - timedelta(days=30)
            ).order_by(SentimentAnalysis.created_at.desc()).limit(10).all()
            
            if not recent_sentiments:
                return {"trend": "no_history", "average_score": 0, "message_count": 0}
            
            scores = [s.sentiment_score for s in recent_sentiments]
            average_score = sum(scores) / len(scores)
            
            # Determine trend
            if len(scores) >= 3:
                recent_avg = sum(scores[:3]) / 3
                older_avg = sum(scores[3:]) / len(scores[3:]) if len(scores) > 3 else recent_avg
                
                if recent_avg > older_avg + 0.2:
                    trend = SentimentTrend.IMPROVING
                elif recent_avg < older_avg - 0.2:
                    trend = SentimentTrend.DECLINING
                else:
                    trend = SentimentTrend.STABLE
            else:
                trend = SentimentTrend.STABLE
            
            return {
                "trend": trend.value,
                "average_score": round(average_score, 2),
                "message_count": len(recent_sentiments),
                "recent_scores": scores[:5],  # Last 5 scores
                "negative_streak": self._calculate_negative_streak(scores)
            }
            
        except Exception as e:
            logger.error("Failed to get guest sentiment history",
                        guest_id=guest_id,
                        error=str(e))
            return {"trend": "error", "average_score": 0, "message_count": 0}
    
    def _analyze_conversation_context(self, message: Message) -> Dict[str, Any]:
        """Analyze conversation context for sentiment"""
        try:
            # Get conversation messages
            conversation_messages = self.db.query(Message).filter(
                Message.conversation_id == message.conversation_id
            ).order_by(Message.created_at).all()
            
            # Get sentiment analyses for conversation
            sentiment_analyses = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.conversation_id == message.conversation_id
            ).order_by(SentimentAnalysis.created_at).all()
            
            if not sentiment_analyses:
                return {"context": "no_sentiment_history"}
            
            scores = [s.sentiment_score for s in sentiment_analyses]
            
            return {
                "message_count": len(conversation_messages),
                "sentiment_count": len(sentiment_analyses),
                "average_sentiment": round(sum(scores) / len(scores), 2),
                "sentiment_trend": self._calculate_conversation_trend(scores),
                "escalation_history": any(s.requires_attention for s in sentiment_analyses)
            }
            
        except Exception as e:
            logger.error("Failed to analyze conversation context",
                        message_id=str(message.id),
                        error=str(e))
            return {"context": "error"}
    
    def _recommend_actions(
        self,
        result: SentimentAnalysisResult,
        message: Message
    ) -> List[Dict[str, Any]]:
        """Recommend actions based on sentiment analysis"""
        actions = []
        
        if result.requires_attention or result.score < -0.5:
            actions.append({
                "action": "immediate_staff_notification",
                "priority": "high",
                "description": "Notify staff immediately for negative sentiment"
            })
        
        if result.score < -0.3:
            actions.append({
                "action": "manager_review",
                "priority": "medium",
                "description": "Manager should review guest interaction"
            })
        
        if result.score < -0.1:
            actions.append({
                "action": "follow_up_message",
                "priority": "low",
                "description": "Send follow-up message to address concerns"
            })
        
        # Check for repeated negative sentiment
        recent_negative = self._count_recent_negative_messages(message.guest_id)
        if recent_negative >= 2:
            actions.append({
                "action": "escalate_to_management",
                "priority": "high",
                "description": f"Guest has {recent_negative} recent negative messages"
            })
        
        return actions
    
    def _should_escalate(self, result: SentimentAnalysisResult, message: Message) -> bool:
        """Determine if situation should be escalated"""
        # Critical sentiment score
        if result.score < -0.7:
            return True
        
        # AI flagged for attention
        if result.requires_attention:
            return True
        
        # Multiple recent negative messages
        if self._count_recent_negative_messages(message.guest_id) >= 3:
            return True
        
        return False
    
    def _count_recent_negative_messages(self, guest_id: str, hours: int = 24) -> int:
        """Count recent negative messages from guest"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            count = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.guest_id == guest_id,
                SentimentAnalysis.sentiment_score < -0.1,
                SentimentAnalysis.created_at >= cutoff_time
            ).count()
            
            return count
            
        except Exception:
            return 0
    
    def _calculate_negative_streak(self, scores: List[float]) -> int:
        """Calculate current negative sentiment streak"""
        streak = 0
        for score in scores:
            if score < -0.1:
                streak += 1
            else:
                break
        return streak
    
    def _calculate_conversation_trend(self, scores: List[float]) -> str:
        """Calculate sentiment trend for conversation"""
        if len(scores) < 3:
            return "insufficient_data"
        
        # Compare first half vs second half
        mid_point = len(scores) // 2
        first_half_avg = sum(scores[:mid_point]) / mid_point
        second_half_avg = sum(scores[mid_point:]) / (len(scores) - mid_point)
        
        if second_half_avg > first_half_avg + 0.2:
            return "improving"
        elif second_half_avg < first_half_avg - 0.2:
            return "declining"
        else:
            return "stable"
    
    def _get_response_time_target(self, urgency_level: str) -> int:
        """Get response time target in minutes based on urgency"""
        targets = {
            "critical": 5,
            "high": 15,
            "medium": 30,
            "low": 60,
            "minimal": 120
        }
        return targets.get(urgency_level, 60)


def get_sentiment_processor(db: Session) -> SentimentProcessor:
    """Get sentiment processor instance"""
    return SentimentProcessor(db)
