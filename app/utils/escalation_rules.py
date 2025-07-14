"""
Escalation rules engine for determining when conversations should be escalated
"""

import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import structlog

from app.core.logging import get_logger

logger = get_logger(__name__)


class EscalationTrigger(str, Enum):
    """Types of escalation triggers"""
    SENTIMENT_NEGATIVE = "sentiment_negative"
    KEYWORDS_COMPLAINT = "keywords_complaint"
    KEYWORDS_EMERGENCY = "keywords_emergency"
    REPEATED_REQUESTS = "repeated_requests"
    TIMEOUT = "timeout"
    URGENCY_HIGH = "urgency_high"
    MANUAL = "manual"


class EscalationRule:
    """Represents an escalation rule"""
    
    def __init__(
        self,
        name: str,
        trigger: EscalationTrigger,
        condition: Callable[[Dict[str, Any]], bool],
        priority: int = 1,
        description: str = "",
        enabled: bool = True
    ):
        self.name = name
        self.trigger = trigger
        self.condition = condition
        self.priority = priority
        self.description = description
        self.enabled = enabled
        self.created_at = datetime.utcnow()
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate if rule should trigger escalation"""
        if not self.enabled:
            return False
        
        try:
            return self.condition(context)
        except Exception as e:
            logger.error("Escalation rule evaluation failed",
                        rule_name=self.name,
                        error=str(e))
            return False


class EscalationRuleEngine:
    """
    Engine for managing and evaluating escalation rules
    """
    
    def __init__(self):
        self.rules: List[EscalationRule] = []
        self.keyword_patterns = self._setup_keyword_patterns()
        self._setup_default_rules()
    
    def _setup_keyword_patterns(self) -> Dict[str, List[str]]:
        """Setup keyword patterns for different escalation types"""
        return {
            'complaint': [
                'complaint', 'complain', 'terrible', 'awful', 'horrible',
                'disgusting', 'worst', 'unacceptable', 'disappointed',
                'angry', 'furious', 'outraged', 'disgusted', 'appalled',
                'manager', 'supervisor', 'refund', 'money back',
                'never again', 'cancel', 'cancellation'
            ],
            'emergency': [
                'emergency', 'urgent', 'help', 'fire', 'police',
                'ambulance', 'medical', 'accident', 'danger',
                'security', 'break-in', 'theft', 'robbery',
                'assault', 'injury', 'bleeding', 'unconscious',
                'heart attack', 'stroke', 'overdose'
            ],
            'escalation_requests': [
                'manager', 'supervisor', 'boss', 'escalate',
                'speak to someone', 'higher up', 'in charge',
                'complaint department', 'customer service'
            ],
            'negative_intensity': [
                'extremely', 'absolutely', 'completely', 'totally',
                'utterly', 'ridiculously', 'incredibly', 'unbelievably'
            ]
        }
    
    def _setup_default_rules(self):
        """Setup default escalation rules"""
        
        # Sentiment-based rules
        self.add_rule(EscalationRule(
            name="very_negative_sentiment",
            trigger=EscalationTrigger.SENTIMENT_NEGATIVE,
            condition=lambda ctx: ctx.get('sentiment_score', 0) < -0.7,
            priority=8,
            description="Very negative sentiment detected"
        ))
        
        self.add_rule(EscalationRule(
            name="negative_sentiment_with_intensity",
            trigger=EscalationTrigger.SENTIMENT_NEGATIVE,
            condition=self._check_negative_with_intensity,
            priority=7,
            description="Negative sentiment with intensity words"
        ))
        
        # Keyword-based rules
        self.add_rule(EscalationRule(
            name="complaint_keywords",
            trigger=EscalationTrigger.KEYWORDS_COMPLAINT,
            condition=self._check_complaint_keywords_rule,
            priority=6,
            description="Complaint keywords detected"
        ))
        
        self.add_rule(EscalationRule(
            name="emergency_keywords",
            trigger=EscalationTrigger.KEYWORDS_EMERGENCY,
            condition=self._check_emergency_keywords_rule,
            priority=10,
            description="Emergency keywords detected"
        ))
        
        # Behavioral rules
        self.add_rule(EscalationRule(
            name="repeated_requests",
            trigger=EscalationTrigger.REPEATED_REQUESTS,
            condition=lambda ctx: ctx.get('repeat_count', 0) >= 3,
            priority=5,
            description="Multiple repeated requests"
        ))
        
        self.add_rule(EscalationRule(
            name="high_urgency",
            trigger=EscalationTrigger.URGENCY_HIGH,
            condition=lambda ctx: ctx.get('urgency_level', 1) >= 4,
            priority=7,
            description="High urgency level detected"
        ))
        
        # Timeout rules
        self.add_rule(EscalationRule(
            name="conversation_timeout",
            trigger=EscalationTrigger.TIMEOUT,
            condition=self._check_timeout_rule,
            priority=3,
            description="Conversation has timed out"
        ))
    
    def add_rule(self, rule: EscalationRule):
        """Add escalation rule"""
        self.rules.append(rule)
        # Sort by priority (higher first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove escalation rule by name"""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                return True
        return False
    
    def enable_rule(self, rule_name: str) -> bool:
        """Enable escalation rule"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """Disable escalation rule"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                return True
        return False
    
    def evaluate_all_rules(self, context: Dict[str, Any]) -> List[EscalationRule]:
        """
        Evaluate all rules and return triggered ones
        
        Args:
            context: Context data for evaluation
            
        Returns:
            List[EscalationRule]: Triggered rules sorted by priority
        """
        triggered_rules = []
        
        for rule in self.rules:
            if rule.evaluate(context):
                triggered_rules.append(rule)
                logger.debug("Escalation rule triggered",
                           rule_name=rule.name,
                           trigger=rule.trigger.value,
                           priority=rule.priority)
        
        return triggered_rules
    
    def should_escalate(self, context: Dict[str, Any]) -> bool:
        """
        Determine if conversation should be escalated
        
        Args:
            context: Context data for evaluation
            
        Returns:
            bool: True if escalation is recommended
        """
        triggered_rules = self.evaluate_all_rules(context)
        return len(triggered_rules) > 0
    
    def get_escalation_reason(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Get escalation reason based on triggered rules
        
        Args:
            context: Context data for evaluation
            
        Returns:
            Optional[str]: Escalation reason or None
        """
        triggered_rules = self.evaluate_all_rules(context)
        
        if not triggered_rules:
            return None
        
        # Use highest priority rule for reason
        highest_priority_rule = triggered_rules[0]
        return highest_priority_rule.description
    
    # Keyword checking methods
    def check_complaint_keywords(self, text: str) -> bool:
        """Check if text contains complaint keywords"""
        text_lower = text.lower()
        complaint_keywords = self.keyword_patterns['complaint']
        return any(keyword in text_lower for keyword in complaint_keywords)
    
    def check_emergency_keywords(self, text: str) -> bool:
        """Check if text contains emergency keywords"""
        text_lower = text.lower()
        emergency_keywords = self.keyword_patterns['emergency']
        return any(keyword in text_lower for keyword in emergency_keywords)
    
    def check_escalation_request_keywords(self, text: str) -> bool:
        """Check if text contains escalation request keywords"""
        text_lower = text.lower()
        escalation_keywords = self.keyword_patterns['escalation_requests']
        return any(keyword in text_lower for keyword in escalation_keywords)
    
    # Rule condition methods
    def _check_complaint_keywords_rule(self, context: Dict[str, Any]) -> bool:
        """Rule condition for complaint keywords"""
        message_content = context.get('message_content', '')
        return self.check_complaint_keywords(message_content)
    
    def _check_emergency_keywords_rule(self, context: Dict[str, Any]) -> bool:
        """Rule condition for emergency keywords"""
        message_content = context.get('message_content', '')
        return self.check_emergency_keywords(message_content)
    
    def _check_negative_with_intensity(self, context: Dict[str, Any]) -> bool:
        """Rule condition for negative sentiment with intensity words"""
        sentiment_score = context.get('sentiment_score', 0)
        message_content = context.get('message_content', '').lower()
        
        if sentiment_score >= -0.5:  # Not negative enough
            return False
        
        # Check for intensity words
        intensity_words = self.keyword_patterns['negative_intensity']
        has_intensity = any(word in message_content for word in intensity_words)
        
        return has_intensity
    
    def _check_timeout_rule(self, context: Dict[str, Any]) -> bool:
        """Rule condition for timeout"""
        last_message_at = context.get('last_message_at')
        if not last_message_at:
            return False
        
        if isinstance(last_message_at, str):
            last_message_at = datetime.fromisoformat(last_message_at)
        
        timeout_threshold = datetime.utcnow() - timedelta(hours=24)
        return last_message_at < timeout_threshold
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get statistics about rules"""
        total_rules = len(self.rules)
        enabled_rules = sum(1 for rule in self.rules if rule.enabled)
        
        trigger_counts = {}
        for rule in self.rules:
            trigger = rule.trigger.value
            trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
        
        return {
            'total_rules': total_rules,
            'enabled_rules': enabled_rules,
            'disabled_rules': total_rules - enabled_rules,
            'trigger_distribution': trigger_counts,
            'rules': [
                {
                    'name': rule.name,
                    'trigger': rule.trigger.value,
                    'priority': rule.priority,
                    'enabled': rule.enabled,
                    'description': rule.description
                }
                for rule in self.rules
            ]
        }
    
    def export_rules_config(self) -> Dict[str, Any]:
        """Export rules configuration for backup/import"""
        return {
            'version': '1.0',
            'exported_at': datetime.utcnow().isoformat(),
            'keyword_patterns': self.keyword_patterns,
            'rules': [
                {
                    'name': rule.name,
                    'trigger': rule.trigger.value,
                    'priority': rule.priority,
                    'enabled': rule.enabled,
                    'description': rule.description
                }
                for rule in self.rules
            ]
        }


# Export rule engine
__all__ = ['EscalationRuleEngine', 'EscalationRule', 'EscalationTrigger']
