"""
Sentiment rules engine for configurable alert thresholds and escalation logic
"""

import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json

import structlog
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.sentiment import SentimentAnalysis
from app.models.staff_alert import StaffAlert, AlertType, AlertPriority
from app.models.message import Message
from app.models.guest import Guest
from app.schemas.deepseek import SentimentAnalysisResult, SentimentType
from app.utils.threshold_manager import get_threshold_manager, ThresholdManager

logger = structlog.get_logger(__name__)


class EscalationLevel(Enum):
    """Escalation levels for sentiment alerts"""
    NONE = "none"
    STAFF = "staff"
    SUPERVISOR = "supervisor"
    MANAGER = "manager"
    DIRECTOR = "director"


class RuleCondition(Enum):
    """Types of rule conditions"""
    SENTIMENT_SCORE = "sentiment_score"
    CONFIDENCE_LEVEL = "confidence_level"
    REQUIRES_ATTENTION = "requires_attention"
    CONSECUTIVE_NEGATIVE = "consecutive_negative"
    GUEST_HISTORY = "guest_history"
    TIME_BASED = "time_based"
    KEYWORD_MATCH = "keyword_match"


class RuleAction(Enum):
    """Types of rule actions"""
    CREATE_ALERT = "create_alert"
    ESCALATE = "escalate"
    NOTIFY_STAFF = "notify_staff"
    FLAG_GUEST = "flag_guest"
    SCHEDULE_FOLLOWUP = "schedule_followup"
    LOG_INCIDENT = "log_incident"


class SentimentRulesEngine:
    """Engine for evaluating sentiment rules and triggering actions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.threshold_manager = get_threshold_manager(db)
        self.default_rules = self._load_default_rules()
    
    async def evaluate_sentiment_rules(
        self,
        sentiment: SentimentAnalysisResult,
        message: Message,
        hotel_id: str,
        correlation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all sentiment rules for a given sentiment analysis
        
        Args:
            sentiment: Sentiment analysis result
            message: Original message
            hotel_id: Hotel ID
            correlation_id: Correlation ID for tracking
            
        Returns:
            List of triggered actions
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            logger.info("Evaluating sentiment rules",
                       message_id=str(message.id),
                       sentiment_score=sentiment.score,
                       hotel_id=hotel_id,
                       correlation_id=correlation_id)
            
            # Get hotel-specific rules or use defaults
            rules = await self._get_hotel_rules(hotel_id)
            
            triggered_actions = []
            
            # Evaluate each rule
            for rule in rules:
                try:
                    if await self._evaluate_rule_conditions(rule, sentiment, message, hotel_id):
                        actions = await self._execute_rule_actions(rule, sentiment, message, correlation_id)
                        triggered_actions.extend(actions)
                        
                        logger.info("Rule triggered",
                                   rule_id=rule.get("id"),
                                   rule_name=rule.get("name"),
                                   actions_count=len(actions),
                                   correlation_id=correlation_id)
                
                except Exception as e:
                    logger.error("Failed to evaluate rule",
                               rule_id=rule.get("id"),
                               error=str(e),
                               correlation_id=correlation_id)
                    continue
            
            logger.info("Sentiment rules evaluation completed",
                       message_id=str(message.id),
                       rules_evaluated=len(rules),
                       actions_triggered=len(triggered_actions),
                       correlation_id=correlation_id)
            
            return triggered_actions
            
        except Exception as e:
            logger.error("Failed to evaluate sentiment rules",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def should_alert_staff(
        self,
        sentiment: SentimentAnalysisResult,
        message: Message,
        hotel_id: str
    ) -> bool:
        """
        Determine if staff should be alerted based on sentiment
        
        Args:
            sentiment: Sentiment analysis result
            message: Original message
            hotel_id: Hotel ID
            
        Returns:
            Whether to alert staff
        """
        try:
            # Get thresholds for hotel
            thresholds = await self.threshold_manager.get_hotel_thresholds(hotel_id)
            
            # Check basic sentiment score threshold
            if sentiment.score < thresholds.get("negative_sentiment_threshold", -0.3):
                return True
            
            # Check if AI flagged for attention
            if sentiment.requires_attention:
                return True
            
            # Check confidence threshold for uncertain positive sentiment
            if (sentiment.sentiment == SentimentType.POSITIVE and 
                sentiment.confidence < thresholds.get("low_confidence_threshold", 0.5)):
                return True
            
            # Check for consecutive negative messages
            consecutive_threshold = thresholds.get("consecutive_negative_threshold", 3)
            if await self._check_consecutive_negative_messages(message.guest_id, hotel_id, consecutive_threshold):
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to determine if staff alert needed",
                        message_id=str(message.id),
                        error=str(e))
            return False
    
    async def get_escalation_level(
        self,
        sentiment: SentimentAnalysisResult,
        message: Message,
        hotel_id: str
    ) -> EscalationLevel:
        """
        Determine escalation level based on sentiment
        
        Args:
            sentiment: Sentiment analysis result
            message: Original message
            hotel_id: Hotel ID
            
        Returns:
            Escalation level
        """
        try:
            # Get thresholds for hotel
            thresholds = await self.threshold_manager.get_hotel_thresholds(hotel_id)
            
            # Critical sentiment - escalate to manager
            if sentiment.score < thresholds.get("critical_sentiment_threshold", -0.8):
                return EscalationLevel.MANAGER
            
            # Very negative sentiment - escalate to supervisor
            if sentiment.score < thresholds.get("very_negative_threshold", -0.6):
                return EscalationLevel.SUPERVISOR
            
            # AI flagged for attention - escalate to supervisor
            if sentiment.requires_attention:
                return EscalationLevel.SUPERVISOR
            
            # Multiple recent negative messages - escalate to supervisor
            recent_negative_count = await self._count_recent_negative_messages(
                message.guest_id, hotel_id, hours=24
            )
            if recent_negative_count >= thresholds.get("escalation_negative_count", 3):
                return EscalationLevel.SUPERVISOR
            
            # Regular negative sentiment - staff level
            if sentiment.score < thresholds.get("negative_sentiment_threshold", -0.3):
                return EscalationLevel.STAFF
            
            return EscalationLevel.NONE
            
        except Exception as e:
            logger.error("Failed to determine escalation level",
                        message_id=str(message.id),
                        error=str(e))
            return EscalationLevel.STAFF
    
    async def _get_hotel_rules(self, hotel_id: str) -> List[Dict[str, Any]]:
        """Get rules for a specific hotel"""
        # In a real implementation, this would load from database
        # For now, return default rules
        return self.default_rules
    
    async def _evaluate_rule_conditions(
        self,
        rule: Dict[str, Any],
        sentiment: SentimentAnalysisResult,
        message: Message,
        hotel_id: str
    ) -> bool:
        """Evaluate if rule conditions are met"""
        conditions = rule.get("conditions", [])
        
        for condition in conditions:
            condition_type = condition.get("type")
            
            if condition_type == RuleCondition.SENTIMENT_SCORE.value:
                if not self._check_sentiment_score_condition(condition, sentiment):
                    return False
            
            elif condition_type == RuleCondition.CONFIDENCE_LEVEL.value:
                if not self._check_confidence_condition(condition, sentiment):
                    return False
            
            elif condition_type == RuleCondition.REQUIRES_ATTENTION.value:
                if not sentiment.requires_attention:
                    return False
            
            elif condition_type == RuleCondition.CONSECUTIVE_NEGATIVE.value:
                threshold = condition.get("threshold", 3)
                if not await self._check_consecutive_negative_messages(message.guest_id, hotel_id, threshold):
                    return False
            
            elif condition_type == RuleCondition.KEYWORD_MATCH.value:
                keywords = condition.get("keywords", [])
                if not self._check_keyword_match(message.content, keywords):
                    return False
        
        return True
    
    async def _execute_rule_actions(
        self,
        rule: Dict[str, Any],
        sentiment: SentimentAnalysisResult,
        message: Message,
        correlation_id: str
    ) -> List[Dict[str, Any]]:
        """Execute actions for a triggered rule"""
        actions = rule.get("actions", [])
        executed_actions = []
        
        for action in actions:
            action_type = action.get("type")
            
            if action_type == RuleAction.CREATE_ALERT.value:
                alert_data = await self._create_alert_action(action, sentiment, message, correlation_id)
                executed_actions.append(alert_data)
            
            elif action_type == RuleAction.NOTIFY_STAFF.value:
                notification_data = await self._notify_staff_action(action, sentiment, message, correlation_id)
                executed_actions.append(notification_data)
            
            elif action_type == RuleAction.LOG_INCIDENT.value:
                incident_data = await self._log_incident_action(action, sentiment, message, correlation_id)
                executed_actions.append(incident_data)
        
        return executed_actions
    
    def _check_sentiment_score_condition(
        self,
        condition: Dict[str, Any],
        sentiment: SentimentAnalysisResult
    ) -> bool:
        """Check sentiment score condition"""
        operator = condition.get("operator", "less_than")
        threshold = condition.get("threshold", -0.3)
        
        if operator == "less_than":
            return sentiment.score < threshold
        elif operator == "greater_than":
            return sentiment.score > threshold
        elif operator == "equals":
            return abs(sentiment.score - threshold) < 0.01
        
        return False
    
    def _check_confidence_condition(
        self,
        condition: Dict[str, Any],
        sentiment: SentimentAnalysisResult
    ) -> bool:
        """Check confidence level condition"""
        operator = condition.get("operator", "less_than")
        threshold = condition.get("threshold", 0.5)
        
        if operator == "less_than":
            return sentiment.confidence < threshold
        elif operator == "greater_than":
            return sentiment.confidence > threshold
        
        return False
    
    async def _check_consecutive_negative_messages(
        self,
        guest_id: str,
        hotel_id: str,
        threshold: int
    ) -> bool:
        """Check for consecutive negative messages"""
        try:
            # Get recent sentiment analyses for guest
            recent_sentiments = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.guest_id == guest_id,
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).order_by(SentimentAnalysis.created_at.desc()).limit(threshold).all()
            
            if len(recent_sentiments) < threshold:
                return False
            
            # Check if all recent messages are negative
            negative_count = len([s for s in recent_sentiments if s.sentiment_score < -0.1])
            return negative_count >= threshold
            
        except Exception:
            return False
    
    async def _count_recent_negative_messages(
        self,
        guest_id: str,
        hotel_id: str,
        hours: int = 24
    ) -> int:
        """Count recent negative messages from guest"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            count = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.guest_id == guest_id,
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.sentiment_score < -0.1,
                SentimentAnalysis.created_at >= cutoff_time
            ).count()
            
            return count
            
        except Exception:
            return 0
    
    def _check_keyword_match(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the specified keywords"""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)
    
    async def _create_alert_action(
        self,
        action: Dict[str, Any],
        sentiment: SentimentAnalysisResult,
        message: Message,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Execute create alert action"""
        return {
            "type": "alert_created",
            "priority": action.get("priority", "medium"),
            "message_id": str(message.id),
            "sentiment_score": sentiment.score,
            "correlation_id": correlation_id
        }
    
    async def _notify_staff_action(
        self,
        action: Dict[str, Any],
        sentiment: SentimentAnalysisResult,
        message: Message,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Execute notify staff action"""
        return {
            "type": "staff_notified",
            "channels": action.get("channels", ["email"]),
            "message_id": str(message.id),
            "correlation_id": correlation_id
        }
    
    async def _log_incident_action(
        self,
        action: Dict[str, Any],
        sentiment: SentimentAnalysisResult,
        message: Message,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Execute log incident action"""
        return {
            "type": "incident_logged",
            "severity": action.get("severity", "medium"),
            "message_id": str(message.id),
            "correlation_id": correlation_id
        }
    
    def _load_default_rules(self) -> List[Dict[str, Any]]:
        """Load default sentiment rules"""
        return [
            {
                "id": "critical_sentiment",
                "name": "Critical Sentiment Alert",
                "description": "Alert for critical negative sentiment",
                "conditions": [
                    {
                        "type": "sentiment_score",
                        "operator": "less_than",
                        "threshold": -0.8
                    }
                ],
                "actions": [
                    {
                        "type": "create_alert",
                        "priority": "critical"
                    },
                    {
                        "type": "notify_staff",
                        "channels": ["email", "sms", "slack"]
                    }
                ]
            },
            {
                "id": "negative_sentiment",
                "name": "Negative Sentiment Alert",
                "description": "Alert for negative sentiment",
                "conditions": [
                    {
                        "type": "sentiment_score",
                        "operator": "less_than",
                        "threshold": -0.3
                    }
                ],
                "actions": [
                    {
                        "type": "create_alert",
                        "priority": "medium"
                    },
                    {
                        "type": "notify_staff",
                        "channels": ["email"]
                    }
                ]
            },
            {
                "id": "requires_attention",
                "name": "AI Flagged Attention",
                "description": "Alert when AI flags message for attention",
                "conditions": [
                    {
                        "type": "requires_attention"
                    }
                ],
                "actions": [
                    {
                        "type": "create_alert",
                        "priority": "high"
                    },
                    {
                        "type": "notify_staff",
                        "channels": ["email", "slack"]
                    }
                ]
            },
            {
                "id": "consecutive_negative",
                "name": "Consecutive Negative Messages",
                "description": "Alert for multiple consecutive negative messages",
                "conditions": [
                    {
                        "type": "consecutive_negative",
                        "threshold": 3
                    }
                ],
                "actions": [
                    {
                        "type": "create_alert",
                        "priority": "high"
                    },
                    {
                        "type": "notify_staff",
                        "channels": ["email", "sms"]
                    }
                ]
            }
        ]


def get_sentiment_rules_engine(db: Session) -> SentimentRulesEngine:
    """Get sentiment rules engine instance"""
    return SentimentRulesEngine(db)
