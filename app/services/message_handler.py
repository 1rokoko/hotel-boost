"""
Enhanced message handler for conversation management
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
import structlog

from app.models.message import Message, Conversation, ConversationState, ConversationStatus
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.services.conversation_service import ConversationService
from app.services.conversation_state_machine import ConversationStateMachine
from app.services.deepseek_client import DeepSeekClient
from app.utils.intent_classifier import IntentClassifier, MessageIntent, IntentClassificationResult
from app.utils.state_transitions import StateTransitionValidator, TransitionTrigger, StateTransitionLogger
from app.schemas.conversation import StateTransitionRequest
from app.core.logging import get_logger

logger = get_logger(__name__)


class MessageHandlingResult:
    """Result of message handling"""
    
    def __init__(
        self,
        success: bool,
        conversation: Optional[Conversation] = None,
        intent_result: Optional[IntentClassificationResult] = None,
        state_transition: Optional[Dict[str, Any]] = None,
        actions_taken: List[str] = None,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.conversation = conversation
        self.intent_result = intent_result
        self.state_transition = state_transition
        self.actions_taken = actions_taken or []
        self.error_message = error_message
        self.timestamp = datetime.utcnow()


class MessageHandler:
    """
    Enhanced message handler with intent classification and state management
    """
    
    def __init__(
        self,
        db: Session,
        deepseek_client: DeepSeekClient
    ):
        self.db = db
        self.conversation_service = ConversationService(db)
        self.state_machine = ConversationStateMachine()
        self.intent_classifier = IntentClassifier(deepseek_client)
        self.state_validator = StateTransitionValidator()
        self.transition_logger = StateTransitionLogger()
    
    async def handle_incoming_message(
        self,
        hotel_id: UUID,
        guest_id: UUID,
        message: Message
    ) -> MessageHandlingResult:
        """
        Handle incoming message with full conversation management
        
        Args:
            hotel_id: Hotel ID
            guest_id: Guest ID
            message: Message object
            
        Returns:
            MessageHandlingResult: Handling result
        """
        try:
            # Get or create conversation
            conversation = await self.conversation_service.get_or_create_conversation(
                hotel_id=hotel_id,
                guest_id=guest_id
            )
            
            # Update conversation with new message
            conversation.update_last_message_time()
            
            # Classify message intent
            intent_result = await self.classify_intent(message, conversation)
            
            # Process based on intent and current state
            actions_taken = []
            state_transition = None
            
            # Handle emergency messages immediately
            if intent_result.intent == MessageIntent.EMERGENCY:
                state_transition = await self._handle_emergency(conversation, intent_result)
                actions_taken.append("emergency_escalation")
            else:
                # Normal message processing
                state_transition = await self._process_normal_message(
                    conversation, message, intent_result
                )
                actions_taken.extend(await self._execute_intent_actions(
                    conversation, intent_result
                ))
            
            # Update conversation context
            await self._update_conversation_context(
                conversation, message, intent_result
            )
            
            # Commit changes
            self.db.commit()
            
            logger.info("Message handled successfully",
                       conversation_id=conversation.id,
                       intent=intent_result.intent.value,
                       confidence=intent_result.confidence,
                       actions_taken=actions_taken)
            
            return MessageHandlingResult(
                success=True,
                conversation=conversation,
                intent_result=intent_result,
                state_transition=state_transition,
                actions_taken=actions_taken
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error("Message handling failed",
                        hotel_id=hotel_id,
                        guest_id=guest_id,
                        error=str(e))
            
            return MessageHandlingResult(
                success=False,
                error_message=str(e)
            )
    
    async def classify_intent(
        self,
        message: Message,
        conversation: Conversation
    ) -> IntentClassificationResult:
        """
        Classify message intent with conversation context
        
        Args:
            message: Message to classify
            conversation: Conversation context
            
        Returns:
            IntentClassificationResult: Classification result
        """
        # Build context for classification
        context = {
            'conversation_state': conversation.current_state.value,
            'conversation_context': conversation.context,
            'guest_id': str(conversation.guest_id),
            'hotel_id': str(conversation.hotel_id),
            'last_message_at': conversation.last_message_at.isoformat()
        }
        
        # Add recent message history if available
        recent_messages = self.db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at.desc()).limit(5).all()
        
        if recent_messages:
            context['recent_messages'] = [
                {'content': msg.content, 'type': msg.message_type.value}
                for msg in recent_messages
            ]
        
        return await self.intent_classifier.classify_intent(
            message=message.content,
            context=context
        )
    
    async def route_to_handler(
        self,
        intent: MessageIntent,
        conversation: Conversation,
        message: Message
    ) -> List[str]:
        """
        Route message to appropriate handler based on intent
        
        Args:
            intent: Classified intent
            conversation: Conversation object
            message: Message object
            
        Returns:
            List[str]: Actions taken
        """
        actions = []
        
        # Route based on intent
        if intent == MessageIntent.EMERGENCY:
            actions.extend(await self._handle_emergency_intent(conversation, message))
        elif intent == MessageIntent.COMPLAINT:
            actions.extend(await self._handle_complaint_intent(conversation, message))
        elif intent == MessageIntent.REQUEST_SERVICE:
            actions.extend(await self._handle_service_request_intent(conversation, message))
        elif intent == MessageIntent.BOOKING_INQUIRY:
            actions.extend(await self._handle_booking_inquiry_intent(conversation, message))
        elif intent == MessageIntent.ROOM_ISSUE:
            actions.extend(await self._handle_room_issue_intent(conversation, message))
        elif intent == MessageIntent.COMPLIMENT:
            actions.extend(await self._handle_compliment_intent(conversation, message))
        else:
            actions.extend(await self._handle_general_intent(conversation, message))
        
        return actions
    
    async def _process_normal_message(
        self,
        conversation: Conversation,
        message: Message,
        intent_result: IntentClassificationResult
    ) -> Optional[Dict[str, Any]]:
        """Process normal (non-emergency) message"""
        
        # Build context for state transition
        transition_context = {
            'message_content': message.content,
            'intent': intent_result.intent.value,
            'confidence': intent_result.confidence,
            'sentiment_score': intent_result.sentiment_score,
            'urgency_level': intent_result.urgency_level,
            'entities': intent_result.entities,
            'last_message_at': conversation.last_message_at
        }
        
        # Get suggested transition
        suggested_state = self.state_validator.suggest_transition(
            current_state=conversation.current_state,
            context=transition_context
        )
        
        if suggested_state and suggested_state != conversation.current_state:
            # Execute state transition
            transition_result = await self.state_machine.transition_to(
                conversation=conversation,
                target_state=suggested_state,
                context=transition_context,
                reason=f"Intent: {intent_result.intent.value}"
            )
            
            # Log transition
            self.transition_logger.log_transition(
                conversation_id=str(conversation.id),
                from_state=transition_result.previous_state,
                to_state=transition_result.new_state,
                trigger=TransitionTrigger.MESSAGE_RECEIVED,
                context=transition_context,
                success=transition_result.success
            )
            
            return {
                'previous_state': transition_result.previous_state.value,
                'new_state': transition_result.new_state.value,
                'success': transition_result.success,
                'message': transition_result.message
            }
        
        return None
    
    async def _handle_emergency(
        self,
        conversation: Conversation,
        intent_result: IntentClassificationResult
    ) -> Dict[str, Any]:
        """Handle emergency message"""
        
        # Immediately escalate to staff
        transition_result = await self.state_machine.transition_to(
            conversation=conversation,
            target_state=ConversationState.ESCALATED,
            context={
                'emergency_type': 'detected',
                'urgency_level': 5,
                'keywords': intent_result.keywords
            },
            reason="Emergency detected in message"
        )
        
        # Log emergency
        self.transition_logger.log_transition(
            conversation_id=str(conversation.id),
            from_state=transition_result.previous_state,
            to_state=transition_result.new_state,
            trigger=TransitionTrigger.SENTIMENT_NEGATIVE,
            rule_name="emergency_escalation",
            context={'emergency': True},
            success=transition_result.success
        )
        
        return {
            'previous_state': transition_result.previous_state.value,
            'new_state': transition_result.new_state.value,
            'success': transition_result.success,
            'emergency': True
        }
    
    async def _update_conversation_context(
        self,
        conversation: Conversation,
        message: Message,
        intent_result: IntentClassificationResult
    ):
        """Update conversation context with message information"""
        
        # Update context with latest message info
        context_updates = {
            'last_intent': intent_result.intent.value,
            'last_confidence': intent_result.confidence,
            'last_sentiment': intent_result.sentiment_score,
            'last_urgency': intent_result.urgency_level,
            'message_count': conversation.get_context('message_count', 0) + 1
        }
        
        # Track entities
        if intent_result.entities:
            existing_entities = conversation.get_context('entities', {})
            existing_entities.update(intent_result.entities)
            context_updates['entities'] = existing_entities
        
        # Track intent history
        intent_history = conversation.get_context('intent_history', [])
        intent_history.append({
            'intent': intent_result.intent.value,
            'timestamp': datetime.utcnow().isoformat(),
            'confidence': intent_result.confidence
        })
        # Keep only last 10 intents
        context_updates['intent_history'] = intent_history[-10:]
        
        # Update conversation context
        conversation.update_context(context_updates)
    
    async def _execute_intent_actions(
        self,
        conversation: Conversation,
        intent_result: IntentClassificationResult
    ) -> List[str]:
        """Execute actions based on classified intent"""
        actions = []
        
        # High urgency messages
        if intent_result.urgency_level >= 4:
            actions.append("high_priority_flagged")
        
        # Negative sentiment
        if intent_result.sentiment_score and intent_result.sentiment_score < -0.5:
            actions.append("negative_sentiment_detected")
        
        # Track repeat requests
        if intent_result.intent in [MessageIntent.COMPLAINT, MessageIntent.REQUEST_SERVICE]:
            repeat_count = conversation.get_context('repeat_count', 0) + 1
            conversation.set_context('repeat_count', repeat_count)
            
            if repeat_count >= 3:
                actions.append("repeat_request_escalation")
        
        return actions
    
    # Intent-specific handlers
    async def _handle_emergency_intent(self, conversation: Conversation, message: Message) -> List[str]:
        return ["emergency_protocol_activated", "staff_notified_immediately"]
    
    async def _handle_complaint_intent(self, conversation: Conversation, message: Message) -> List[str]:
        return ["complaint_logged", "manager_notified"]
    
    async def _handle_service_request_intent(self, conversation: Conversation, message: Message) -> List[str]:
        return ["service_request_created", "housekeeping_notified"]
    
    async def _handle_booking_inquiry_intent(self, conversation: Conversation, message: Message) -> List[str]:
        return ["booking_inquiry_processed", "availability_checked"]
    
    async def _handle_room_issue_intent(self, conversation: Conversation, message: Message) -> List[str]:
        return ["room_issue_logged", "maintenance_notified"]
    
    async def _handle_compliment_intent(self, conversation: Conversation, message: Message) -> List[str]:
        return ["positive_feedback_recorded", "staff_recognition_sent"]
    
    async def _handle_general_intent(self, conversation: Conversation, message: Message) -> List[str]:
        return ["general_inquiry_processed", "information_provided"]


# Export handler
__all__ = ['MessageHandler', 'MessageHandlingResult']
