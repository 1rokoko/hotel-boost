"""
State transition utilities and rules for conversation management
"""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import re
import structlog

from app.models.message import ConversationState, ConversationStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class TransitionTrigger(Enum):
    """Types of transition triggers"""
    MESSAGE_RECEIVED = "message_received"
    SENTIMENT_NEGATIVE = "sentiment_negative"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    KEYWORD_DETECTED = "keyword_detected"
    SATISFACTION_CONFIRMED = "satisfaction_confirmed"
    INFO_COMPLETE = "info_complete"


class TransitionRule:
    """Represents a rule for state transitions"""
    
    def __init__(
        self,
        name: str,
        trigger: TransitionTrigger,
        from_states: List[ConversationState],
        to_state: ConversationState,
        condition: Callable[[Dict[str, Any]], bool],
        priority: int = 0,
        description: str = ""
    ):
        self.name = name
        self.trigger = trigger
        self.from_states = from_states
        self.to_state = to_state
        self.condition = condition
        self.priority = priority
        self.description = description


class StateTransitionValidator:
    """Validates state transitions and provides transition rules"""
    
    def __init__(self):
        self.rules: List[TransitionRule] = []
        self._setup_rules()
    
    def _setup_rules(self):
        """Setup transition rules"""
        
        # Negative sentiment escalation
        self.rules.append(TransitionRule(
            name="negative_sentiment_escalation",
            trigger=TransitionTrigger.SENTIMENT_NEGATIVE,
            from_states=[
                ConversationState.GREETING,
                ConversationState.COLLECTING_INFO,
                ConversationState.PROCESSING_REQUEST,
                ConversationState.WAITING_RESPONSE
            ],
            to_state=ConversationState.ESCALATED,
            condition=lambda ctx: ctx.get('sentiment_score', 0) < -0.7,
            priority=10,
            description="Escalate on very negative sentiment"
        ))
        
        # Keyword-based escalation
        self.rules.append(TransitionRule(
            name="keyword_escalation",
            trigger=TransitionTrigger.KEYWORD_DETECTED,
            from_states=[
                ConversationState.GREETING,
                ConversationState.COLLECTING_INFO,
                ConversationState.PROCESSING_REQUEST,
                ConversationState.WAITING_RESPONSE
            ],
            to_state=ConversationState.ESCALATED,
            condition=self._check_escalation_keywords,
            priority=9,
            description="Escalate on complaint keywords"
        ))
        
        # Information collection completion
        self.rules.append(TransitionRule(
            name="info_collection_complete",
            trigger=TransitionTrigger.INFO_COMPLETE,
            from_states=[ConversationState.COLLECTING_INFO],
            to_state=ConversationState.PROCESSING_REQUEST,
            condition=self._check_info_complete,
            priority=5,
            description="Move to processing when info is complete"
        ))
        
        # Satisfaction confirmation
        self.rules.append(TransitionRule(
            name="satisfaction_confirmed",
            trigger=TransitionTrigger.SATISFACTION_CONFIRMED,
            from_states=[
                ConversationState.WAITING_RESPONSE,
                ConversationState.PROCESSING_REQUEST
            ],
            to_state=ConversationState.COMPLETED,
            condition=self._check_satisfaction_keywords,
            priority=8,
            description="Complete on satisfaction confirmation"
        ))
        
        # Timeout rules
        self.rules.append(TransitionRule(
            name="waiting_timeout",
            trigger=TransitionTrigger.TIMEOUT,
            from_states=[ConversationState.WAITING_RESPONSE],
            to_state=ConversationState.ESCALATED,
            condition=lambda ctx: self._check_timeout(ctx, hours=24),
            priority=3,
            description="Escalate if waiting too long"
        ))
        
        # Message flow rules
        self.rules.append(TransitionRule(
            name="greeting_to_info",
            trigger=TransitionTrigger.MESSAGE_RECEIVED,
            from_states=[ConversationState.GREETING],
            to_state=ConversationState.COLLECTING_INFO,
            condition=lambda ctx: len(ctx.get('message_content', '')) > 5,
            priority=1,
            description="Move to info collection after greeting response"
        ))
    
    def get_applicable_rules(
        self,
        current_state: ConversationState,
        trigger: TransitionTrigger,
        context: Dict[str, Any]
    ) -> List[TransitionRule]:
        """
        Get applicable rules for current state and trigger
        
        Args:
            current_state: Current conversation state
            trigger: Transition trigger
            context: Context data
            
        Returns:
            List[TransitionRule]: Applicable rules sorted by priority
        """
        applicable = []
        
        for rule in self.rules:
            if (current_state in rule.from_states and 
                rule.trigger == trigger and 
                rule.condition(context)):
                applicable.append(rule)
        
        # Sort by priority (higher priority first)
        return sorted(applicable, key=lambda r: r.priority, reverse=True)
    
    def suggest_transition(
        self,
        current_state: ConversationState,
        context: Dict[str, Any]
    ) -> Optional[ConversationState]:
        """
        Suggest next state based on context
        
        Args:
            current_state: Current state
            context: Context data
            
        Returns:
            Optional[ConversationState]: Suggested next state
        """
        # Check different triggers in order of priority
        triggers_to_check = [
            TransitionTrigger.SENTIMENT_NEGATIVE,
            TransitionTrigger.KEYWORD_DETECTED,
            TransitionTrigger.SATISFACTION_CONFIRMED,
            TransitionTrigger.INFO_COMPLETE,
            TransitionTrigger.MESSAGE_RECEIVED,
            TransitionTrigger.TIMEOUT
        ]
        
        for trigger in triggers_to_check:
            rules = self.get_applicable_rules(current_state, trigger, context)
            if rules:
                return rules[0].to_state
        
        return None
    
    # Condition checking methods
    def _check_escalation_keywords(self, context: Dict[str, Any]) -> bool:
        """Check for escalation keywords in message"""
        message = context.get('message_content', '').lower()
        escalation_keywords = [
            'complaint', 'complain', 'manager', 'supervisor',
            'terrible', 'awful', 'disgusting', 'horrible',
            'refund', 'money back', 'cancel', 'unacceptable',
            'worst', 'never again', 'disappointed', 'angry'
        ]
        return any(keyword in message for keyword in escalation_keywords)
    
    def _check_satisfaction_keywords(self, context: Dict[str, Any]) -> bool:
        """Check for satisfaction keywords in message"""
        message = context.get('message_content', '').lower()
        satisfaction_keywords = [
            'thank', 'thanks', 'perfect', 'great', 'excellent',
            'satisfied', 'resolved', 'solved', 'good', 'fine',
            'appreciate', 'helpful', 'wonderful', 'amazing'
        ]
        return any(keyword in message for keyword in satisfaction_keywords)
    
    def _check_info_complete(self, context: Dict[str, Any]) -> bool:
        """Check if required information is complete"""
        required_fields = context.get('required_fields', [])
        collected_info = context.get('collected_info', {})
        
        if not required_fields:
            return True
        
        return all(field in collected_info and collected_info[field] for field in required_fields)
    
    def _check_timeout(self, context: Dict[str, Any], hours: int = 24) -> bool:
        """Check if conversation has timed out"""
        last_message_time = context.get('last_message_at')
        if not last_message_time:
            return False
        
        if isinstance(last_message_time, str):
            last_message_time = datetime.fromisoformat(last_message_time)
        
        timeout_threshold = datetime.utcnow() - timedelta(hours=hours)
        return last_message_time < timeout_threshold


class StateTransitionLogger:
    """Logs state transitions for analytics and debugging"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def log_transition(
        self,
        conversation_id: str,
        from_state: ConversationState,
        to_state: ConversationState,
        trigger: TransitionTrigger,
        rule_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        Log a state transition
        
        Args:
            conversation_id: Conversation ID
            from_state: Previous state
            to_state: New state
            trigger: What triggered the transition
            rule_name: Name of the rule that triggered transition
            context: Additional context
            success: Whether transition was successful
            error_message: Error message if failed
        """
        log_data = {
            "event": "state_transition",
            "conversation_id": conversation_id,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "trigger": trigger.value,
            "rule_name": rule_name,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error_message:
            log_data["error"] = error_message
        
        if context:
            # Log relevant context (avoid logging sensitive data)
            safe_context = {
                "sentiment_score": context.get("sentiment_score"),
                "message_length": len(context.get("message_content", "")),
                "has_keywords": bool(context.get("detected_keywords")),
                "info_fields_count": len(context.get("collected_info", {}))
            }
            log_data["context"] = safe_context
        
        if success:
            self.logger.info("State transition executed", **log_data)
        else:
            self.logger.error("State transition failed", **log_data)
    
    def log_transition_suggestion(
        self,
        conversation_id: str,
        current_state: ConversationState,
        suggested_state: Optional[ConversationState],
        applicable_rules: List[str]
    ):
        """Log transition suggestion for analytics"""
        self.logger.info(
            "Transition suggestion generated",
            event="transition_suggestion",
            conversation_id=conversation_id,
            current_state=current_state.value,
            suggested_state=suggested_state.value if suggested_state else None,
            applicable_rules=applicable_rules,
            timestamp=datetime.utcnow().isoformat()
        )


# Export utilities
__all__ = [
    'TransitionTrigger',
    'TransitionRule', 
    'StateTransitionValidator',
    'StateTransitionLogger'
]
