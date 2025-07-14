"""
Conversation state machine for managing conversation flow
"""

from typing import Dict, Any, Optional, Set, Callable
from datetime import datetime
from uuid import UUID
import structlog

from app.models.message import Conversation, ConversationState, ConversationStatus
from app.schemas.conversation import StateTransitionRequest, StateTransitionResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class StateTransition:
    """Represents a state transition with metadata"""
    
    def __init__(
        self,
        from_state: ConversationState,
        to_state: ConversationState,
        condition: Optional[Callable] = None,
        action: Optional[Callable] = None,
        description: str = ""
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition
        self.action = action
        self.description = description
    
    def can_transition(self, conversation: Conversation, context: Dict[str, Any] = None) -> bool:
        """Check if transition is allowed"""
        if self.condition:
            return self.condition(conversation, context or {})
        return True
    
    async def execute_action(self, conversation: Conversation, context: Dict[str, Any] = None):
        """Execute transition action if defined"""
        if self.action:
            await self.action(conversation, context or {})


class ConversationStateMachine:
    """
    Finite State Machine for managing conversation states
    """
    
    def __init__(self):
        self.transitions: Dict[ConversationState, Dict[ConversationState, StateTransition]] = {}
        self._setup_transitions()
    
    def _setup_transitions(self):
        """Setup allowed state transitions"""
        
        # Define transition rules
        transitions = [
            # From GREETING
            StateTransition(
                ConversationState.GREETING,
                ConversationState.COLLECTING_INFO,
                description="Guest responds to greeting"
            ),
            StateTransition(
                ConversationState.GREETING,
                ConversationState.ESCALATED,
                condition=self._check_negative_sentiment,
                description="Negative sentiment detected in greeting"
            ),
            
            # From COLLECTING_INFO
            StateTransition(
                ConversationState.COLLECTING_INFO,
                ConversationState.PROCESSING_REQUEST,
                condition=self._check_sufficient_info,
                description="Sufficient information collected"
            ),
            StateTransition(
                ConversationState.COLLECTING_INFO,
                ConversationState.ESCALATED,
                condition=self._check_escalation_triggers,
                description="Escalation triggered during info collection"
            ),
            
            # From PROCESSING_REQUEST
            StateTransition(
                ConversationState.PROCESSING_REQUEST,
                ConversationState.WAITING_RESPONSE,
                description="Request processed, waiting for guest response"
            ),
            StateTransition(
                ConversationState.PROCESSING_REQUEST,
                ConversationState.COMPLETED,
                condition=self._check_request_resolved,
                description="Request fully resolved"
            ),
            StateTransition(
                ConversationState.PROCESSING_REQUEST,
                ConversationState.ESCALATED,
                condition=self._check_escalation_triggers,
                description="Escalation triggered during processing"
            ),
            
            # From WAITING_RESPONSE
            StateTransition(
                ConversationState.WAITING_RESPONSE,
                ConversationState.COLLECTING_INFO,
                description="Guest provides additional information"
            ),
            StateTransition(
                ConversationState.WAITING_RESPONSE,
                ConversationState.COMPLETED,
                condition=self._check_guest_satisfied,
                description="Guest confirms satisfaction"
            ),
            StateTransition(
                ConversationState.WAITING_RESPONSE,
                ConversationState.ESCALATED,
                condition=self._check_escalation_triggers,
                description="Escalation triggered while waiting"
            ),
            
            # From any state to ESCALATED
            StateTransition(
                ConversationState.GREETING,
                ConversationState.ESCALATED,
                description="Manual escalation from greeting"
            ),
            StateTransition(
                ConversationState.COLLECTING_INFO,
                ConversationState.ESCALATED,
                description="Manual escalation from collecting info"
            ),
            StateTransition(
                ConversationState.PROCESSING_REQUEST,
                ConversationState.ESCALATED,
                description="Manual escalation from processing"
            ),
            StateTransition(
                ConversationState.WAITING_RESPONSE,
                ConversationState.ESCALATED,
                description="Manual escalation from waiting"
            ),
            
            # From ESCALATED
            StateTransition(
                ConversationState.ESCALATED,
                ConversationState.COMPLETED,
                description="Issue resolved by staff"
            ),
            
            # To COMPLETED from any state (manual completion)
            StateTransition(
                ConversationState.GREETING,
                ConversationState.COMPLETED,
                description="Manual completion from greeting"
            ),
            StateTransition(
                ConversationState.COLLECTING_INFO,
                ConversationState.COMPLETED,
                description="Manual completion from collecting info"
            ),
            StateTransition(
                ConversationState.PROCESSING_REQUEST,
                ConversationState.COMPLETED,
                description="Manual completion from processing"
            ),
            StateTransition(
                ConversationState.WAITING_RESPONSE,
                ConversationState.COMPLETED,
                description="Manual completion from waiting"
            ),
        ]
        
        # Build transition map
        for transition in transitions:
            if transition.from_state not in self.transitions:
                self.transitions[transition.from_state] = {}
            self.transitions[transition.from_state][transition.to_state] = transition
    
    def get_allowed_transitions(self, current_state: ConversationState) -> Set[ConversationState]:
        """Get all allowed transitions from current state"""
        return set(self.transitions.get(current_state, {}).keys())
    
    def can_transition(
        self,
        conversation: Conversation,
        target_state: ConversationState,
        context: Dict[str, Any] = None
    ) -> bool:
        """
        Check if transition is allowed
        
        Args:
            conversation: Current conversation
            target_state: Target state
            context: Additional context for transition
            
        Returns:
            bool: True if transition is allowed
        """
        current_state = conversation.current_state
        
        if current_state not in self.transitions:
            return False
        
        if target_state not in self.transitions[current_state]:
            return False
        
        transition = self.transitions[current_state][target_state]
        return transition.can_transition(conversation, context)
    
    async def transition_to(
        self,
        conversation: Conversation,
        target_state: ConversationState,
        context: Dict[str, Any] = None,
        reason: Optional[str] = None
    ) -> StateTransitionResponse:
        """
        Execute state transition
        
        Args:
            conversation: Conversation to transition
            target_state: Target state
            context: Additional context
            reason: Reason for transition
            
        Returns:
            StateTransitionResponse: Transition result
        """
        previous_state = conversation.current_state
        
        # Check if transition is allowed
        if not self.can_transition(conversation, target_state, context):
            return StateTransitionResponse(
                success=False,
                previous_state=previous_state,
                new_state=previous_state,
                timestamp=datetime.utcnow(),
                message=f"Transition from {previous_state.value} to {target_state.value} not allowed"
            )
        
        try:
            # Get transition
            transition = self.transitions[previous_state][target_state]
            
            # Execute transition action
            await transition.execute_action(conversation, context)
            
            # Update conversation state
            conversation.current_state = target_state
            conversation.update_last_message_time()
            
            # Update context if provided
            if context:
                conversation.update_context(context)
            
            # Update status if transitioning to escalated or completed
            if target_state == ConversationState.ESCALATED:
                conversation.status = ConversationStatus.ESCALATED
            elif target_state == ConversationState.COMPLETED:
                conversation.status = ConversationStatus.CLOSED
            
            logger.info("State transition executed",
                       conversation_id=conversation.id,
                       previous_state=previous_state.value,
                       new_state=target_state.value,
                       reason=reason,
                       transition_description=transition.description)
            
            return StateTransitionResponse(
                success=True,
                previous_state=previous_state,
                new_state=target_state,
                timestamp=datetime.utcnow(),
                message=f"Successfully transitioned from {previous_state.value} to {target_state.value}"
            )
            
        except Exception as e:
            logger.error("State transition failed",
                        conversation_id=conversation.id,
                        previous_state=previous_state.value,
                        target_state=target_state.value,
                        error=str(e))
            
            return StateTransitionResponse(
                success=False,
                previous_state=previous_state,
                new_state=previous_state,
                timestamp=datetime.utcnow(),
                message=f"Transition failed: {str(e)}"
            )
    
    # Condition checking methods
    def _check_negative_sentiment(self, conversation: Conversation, context: Dict[str, Any]) -> bool:
        """Check if message has negative sentiment"""
        sentiment_score = context.get('sentiment_score', 0)
        return sentiment_score < -0.5
    
    def _check_sufficient_info(self, conversation: Conversation, context: Dict[str, Any]) -> bool:
        """Check if sufficient information has been collected"""
        required_fields = context.get('required_fields', [])
        collected_info = conversation.get_context('collected_info', {})
        return all(field in collected_info for field in required_fields)
    
    def _check_escalation_triggers(self, conversation: Conversation, context: Dict[str, Any]) -> bool:
        """Check various escalation triggers"""
        # Check sentiment
        if self._check_negative_sentiment(conversation, context):
            return True
        
        # Check for escalation keywords
        message_content = context.get('message_content', '').lower()
        escalation_keywords = ['complaint', 'manager', 'terrible', 'awful', 'disgusting', 'refund']
        if any(keyword in message_content for keyword in escalation_keywords):
            return True
        
        # Check for repeated requests
        repeat_count = conversation.get_context('repeat_count', 0)
        if repeat_count >= 3:
            return True
        
        return False
    
    def _check_request_resolved(self, conversation: Conversation, context: Dict[str, Any]) -> bool:
        """Check if request has been resolved"""
        return context.get('request_resolved', False)
    
    def _check_guest_satisfied(self, conversation: Conversation, context: Dict[str, Any]) -> bool:
        """Check if guest is satisfied"""
        satisfaction_indicators = ['thank', 'thanks', 'perfect', 'great', 'satisfied', 'resolved']
        message_content = context.get('message_content', '').lower()
        return any(indicator in message_content for indicator in satisfaction_indicators)


# Export state machine
__all__ = ['ConversationStateMachine', 'StateTransition']
