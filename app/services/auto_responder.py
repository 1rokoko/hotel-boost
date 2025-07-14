"""
Auto-responder service for WhatsApp Hotel Bot application
"""

import uuid
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
import structlog

from app.models.auto_response_rule import AutoResponseRule, TriggerCondition, ResponseAction
from app.models.message_template import MessageTemplate
from app.models.message import Message, Conversation
from app.models.guest import Guest
from app.services.template_engine import TemplateEngine, TemplateEngineError
from app.utils.response_matcher import ResponseMatcher
from app.core.logging import get_logger

logger = get_logger(__name__)


class AutoResponderError(Exception):
    """Base exception for auto-responder errors"""
    pass


class AutoResponder:
    """
    Auto-responder service for processing and executing automatic responses

    This service evaluates incoming messages against configured rules and
    executes appropriate actions such as sending template responses.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize auto-responder

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.logger = logger.bind(service="auto_responder")
        self.template_engine = TemplateEngine(db_session)
        self.response_matcher = ResponseMatcher()

    async def process_message(
        self,
        message: Message,
        conversation: Conversation,
        guest: Guest
    ) -> List[Dict[str, Any]]:
        """
        Process incoming message and determine auto-responses

        Args:
            message: Incoming message
            conversation: Conversation context
            guest: Guest information

        Returns:
            List[Dict[str, Any]]: List of response actions to execute
        """
        try:
            # Get active rules for the hotel
            rules = await self._get_active_rules(message.hotel_id)

            if not rules:
                self.logger.debug(
                    "No active auto-response rules found",
                    hotel_id=str(message.hotel_id)
                )
                return []

            # Evaluate rules against message
            triggered_rules = []
            for rule in rules:
                if await self._evaluate_rule(rule, message, conversation, guest):
                    triggered_rules.append(rule)

            if not triggered_rules:
                self.logger.debug(
                    "No rules triggered for message",
                    message_id=str(message.id),
                    hotel_id=str(message.hotel_id)
                )
                return []

            # Sort by priority (lower number = higher priority)
            triggered_rules.sort(key=lambda r: r.priority)

            # Execute actions for triggered rules
            response_actions = []
            for rule in triggered_rules:
                actions = await self._execute_rule_actions(rule, message, conversation, guest)
                response_actions.extend(actions)

                # Update rule usage
                rule.increment_usage({
                    'message_id': str(message.id),
                    'guest_id': str(guest.id),
                    'conversation_id': str(conversation.id)
                })

            # Commit rule usage updates
            await self.db.commit()

            self.logger.info(
                "Auto-response processing completed",
                message_id=str(message.id),
                hotel_id=str(message.hotel_id),
                triggered_rules=len(triggered_rules),
                response_actions=len(response_actions)
            )

            return response_actions

        except Exception as e:
            self.logger.error(
                "Error processing message for auto-response",
                message_id=str(message.id) if message else None,
                hotel_id=str(message.hotel_id) if message else None,
                error=str(e)
            )
            raise AutoResponderError(f"Failed to process message: {str(e)}")

    async def _get_active_rules(self, hotel_id: Union[str, uuid.UUID]) -> List[AutoResponseRule]:
        """
        Get active auto-response rules for hotel

        Args:
            hotel_id: Hotel ID

        Returns:
            List[AutoResponseRule]: Active rules sorted by priority
        """
        try:
            current_time = datetime.now().time()

            query = select(AutoResponseRule).options(
                selectinload(AutoResponseRule.template)
            ).where(
                and_(
                    AutoResponseRule.hotel_id == hotel_id,
                    AutoResponseRule.is_active == True
                )
            ).order_by(AutoResponseRule.priority)

            result = await self.db.execute(query)
            all_rules = result.scalars().all()

            # Filter by time constraints
            active_rules = []
            for rule in all_rules:
                if rule.is_active_at_time(current_time):
                    active_rules.append(rule)

            self.logger.debug(
                "Active rules retrieved",
                hotel_id=str(hotel_id),
                total_rules=len(all_rules),
                active_rules=len(active_rules)
            )

            return active_rules

        except Exception as e:
            self.logger.error(
                "Error retrieving active rules",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            return []

    async def _evaluate_rule(
        self,
        rule: AutoResponseRule,
        message: Message,
        conversation: Conversation,
        guest: Guest
    ) -> bool:
        """
        Evaluate if rule conditions are met

        Args:
            rule: Auto-response rule to evaluate
            message: Incoming message
            conversation: Conversation context
            guest: Guest information

        Returns:
            bool: True if rule should be triggered
        """
        try:
            # Check language constraints
            if not rule.supports_language(guest.language or 'en'):
                return False

            conditions = rule.get_trigger_conditions()
            if not conditions:
                return False

            # Evaluate all conditions (AND logic)
            for condition in conditions:
                condition_type = condition.get('type')
                parameters = condition.get('parameters', {})

                if not await self._evaluate_condition(
                    condition_type, parameters, message, conversation, guest
                ):
                    return False

            return True

        except Exception as e:
            self.logger.error(
                "Error evaluating rule",
                rule_id=str(rule.id),
                message_id=str(message.id),
                error=str(e)
            )
            return False

    async def _evaluate_condition(
        self,
        condition_type: str,
        parameters: Dict[str, Any],
        message: Message,
        conversation: Conversation,
        guest: Guest
    ) -> bool:
        """
        Evaluate a specific condition

        Args:
            condition_type: Type of condition to evaluate
            parameters: Condition parameters
            message: Incoming message
            conversation: Conversation context
            guest: Guest information

        Returns:
            bool: True if condition is met
        """
        try:
            if condition_type == TriggerCondition.KEYWORD_MATCH.value:
                return await self._evaluate_keyword_condition(parameters, message)

            elif condition_type == TriggerCondition.TIME_BASED.value:
                return await self._evaluate_time_condition(parameters)

            elif condition_type == TriggerCondition.CONVERSATION_STATE.value:
                return await self._evaluate_conversation_state_condition(parameters, conversation)

            elif condition_type == TriggerCondition.MESSAGE_COUNT.value:
                return await self._evaluate_message_count_condition(parameters, conversation)

            elif condition_type == TriggerCondition.SENTIMENT_BASED.value:
                return await self._evaluate_sentiment_condition(parameters, message)

            elif condition_type == TriggerCondition.GUEST_TYPE.value:
                return await self._evaluate_guest_type_condition(parameters, guest)

            elif condition_type == TriggerCondition.LANGUAGE_BASED.value:
                return await self._evaluate_language_condition(parameters, guest)

            else:
                self.logger.warning(
                    "Unknown condition type",
                    condition_type=condition_type
                )
                return False

        except Exception as e:
            self.logger.error(
                "Error evaluating condition",
                condition_type=condition_type,
                parameters=parameters,
                error=str(e)
            )
            return False

    async def _evaluate_keyword_condition(
        self,
        parameters: Dict[str, Any],
        message: Message
    ) -> bool:
        """Evaluate keyword matching condition"""
        keywords = parameters.get('keywords', [])
        match_type = parameters.get('match_type', 'any')  # 'any' or 'all'
        case_sensitive = parameters.get('case_sensitive', False)

        if not keywords or not message.content:
            return False

        content = message.content if case_sensitive else message.content.lower()

        if not case_sensitive:
            keywords = [kw.lower() for kw in keywords]

        matches = [kw for kw in keywords if kw in content]

        if match_type == 'all':
            return len(matches) == len(keywords)
        else:  # 'any'
            return len(matches) > 0

    async def _evaluate_time_condition(self, parameters: Dict[str, Any]) -> bool:
        """Evaluate time-based condition"""
        current_time = datetime.now().time()
        start_time_str = parameters.get('start_time')
        end_time_str = parameters.get('end_time')

        if not start_time_str or not end_time_str:
            return True

        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()

            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:  # Crosses midnight
                return current_time >= start_time or current_time <= end_time

        except ValueError:
            return True

    async def _evaluate_conversation_state_condition(
        self,
        parameters: Dict[str, Any],
        conversation: Conversation
    ) -> bool:
        """Evaluate conversation state condition"""
        required_status = parameters.get('status')
        if not required_status:
            return True

        return conversation.status == required_status

    async def _evaluate_message_count_condition(
        self,
        parameters: Dict[str, Any],
        conversation: Conversation
    ) -> bool:
        """Evaluate message count condition"""
        min_count = parameters.get('min_count', 0)
        max_count = parameters.get('max_count')

        # Get message count for conversation
        query = select(Message).where(Message.conversation_id == conversation.id)
        result = await self.db.execute(query)
        message_count = len(result.scalars().all())

        if message_count < min_count:
            return False

        if max_count is not None and message_count > max_count:
            return False

        return True

    async def _evaluate_sentiment_condition(
        self,
        parameters: Dict[str, Any],
        message: Message
    ) -> bool:
        """Evaluate sentiment-based condition"""
        min_sentiment = parameters.get('min_sentiment', -1.0)
        max_sentiment = parameters.get('max_sentiment', 1.0)

        sentiment = message.sentiment_score or 0.0
        return min_sentiment <= sentiment <= max_sentiment

    async def _evaluate_guest_type_condition(
        self,
        parameters: Dict[str, Any],
        guest: Guest
    ) -> bool:
        """Evaluate guest type condition"""
        required_types = parameters.get('guest_types', [])
        if not required_types:
            return True

        # This would need to be implemented based on guest classification logic
        # For now, return True as a placeholder
        return True

    async def _evaluate_language_condition(
        self,
        parameters: Dict[str, Any],
        guest: Guest
    ) -> bool:
        """Evaluate language-based condition"""
        required_languages = parameters.get('languages', [])
        if not required_languages:
            return True

        guest_language = guest.language or 'en'
        return guest_language in required_languages

    async def _execute_rule_actions(
        self,
        rule: AutoResponseRule,
        message: Message,
        conversation: Conversation,
        guest: Guest
    ) -> List[Dict[str, Any]]:
        """
        Execute actions for a triggered rule

        Args:
            rule: Triggered auto-response rule
            message: Incoming message
            conversation: Conversation context
            guest: Guest information

        Returns:
            List[Dict[str, Any]]: List of actions to execute
        """
        try:
            actions = rule.get_response_actions()
            executed_actions = []

            for action in actions:
                action_type = action.get('type')
                parameters = action.get('parameters', {})

                if action_type == ResponseAction.SEND_TEMPLATE.value:
                    template_action = await self._execute_send_template_action(
                        rule, parameters, message, conversation, guest
                    )
                    if template_action:
                        executed_actions.append(template_action)

                elif action_type == ResponseAction.ESCALATE_TO_STAFF.value:
                    escalation_action = await self._execute_escalation_action(
                        parameters, message, conversation, guest
                    )
                    if escalation_action:
                        executed_actions.append(escalation_action)

                elif action_type == ResponseAction.SET_CONVERSATION_STATE.value:
                    state_action = await self._execute_state_change_action(
                        parameters, conversation
                    )
                    if state_action:
                        executed_actions.append(state_action)

                elif action_type == ResponseAction.DELAY_RESPONSE.value:
                    delay_action = await self._execute_delay_action(
                        parameters, message, conversation, guest
                    )
                    if delay_action:
                        executed_actions.append(delay_action)

                elif action_type == ResponseAction.FORWARD_TO_AI.value:
                    ai_action = await self._execute_ai_forward_action(
                        parameters, message, conversation, guest
                    )
                    if ai_action:
                        executed_actions.append(ai_action)

                else:
                    self.logger.warning(
                        "Unknown action type",
                        action_type=action_type,
                        rule_id=str(rule.id)
                    )

            return executed_actions

        except Exception as e:
            self.logger.error(
                "Error executing rule actions",
                rule_id=str(rule.id),
                message_id=str(message.id),
                error=str(e)
            )
            return []

    async def _execute_send_template_action(
        self,
        rule: AutoResponseRule,
        parameters: Dict[str, Any],
        message: Message,
        conversation: Conversation,
        guest: Guest
    ) -> Optional[Dict[str, Any]]:
        """Execute send template action"""
        try:
            template_id = rule.template_id or parameters.get('template_id')
            if not template_id:
                self.logger.warning(
                    "No template ID specified for send_template action",
                    rule_id=str(rule.id)
                )
                return None

            # Build context for template rendering
            context = {
                'guest_id': str(guest.id),
                'conversation_id': str(conversation.id),
                'message_id': str(message.id),
                'trigger_rule_id': str(rule.id)
            }

            # Add any additional context from parameters
            context.update(parameters.get('context', {}))

            # Render template
            rendered_message = await self.template_engine.render_template(
                template_id, message.hotel_id, context
            )

            return {
                'type': 'send_message',
                'content': rendered_message,
                'conversation_id': str(conversation.id),
                'guest_id': str(guest.id),
                'hotel_id': str(message.hotel_id),
                'template_id': str(template_id),
                'rule_id': str(rule.id)
            }

        except Exception as e:
            self.logger.error(
                "Error executing send template action",
                rule_id=str(rule.id),
                template_id=str(template_id) if 'template_id' in locals() else None,
                error=str(e)
            )
            return None

    async def _execute_escalation_action(
        self,
        parameters: Dict[str, Any],
        message: Message,
        conversation: Conversation,
        guest: Guest
    ) -> Optional[Dict[str, Any]]:
        """Execute escalation to staff action"""
        return {
            'type': 'escalate_to_staff',
            'reason': parameters.get('reason', 'Auto-escalation triggered'),
            'priority': parameters.get('priority', 'normal'),
            'conversation_id': str(conversation.id),
            'guest_id': str(guest.id),
            'hotel_id': str(message.hotel_id),
            'message_id': str(message.id)
        }

    async def _execute_state_change_action(
        self,
        parameters: Dict[str, Any],
        conversation: Conversation
    ) -> Optional[Dict[str, Any]]:
        """Execute conversation state change action"""
        new_state = parameters.get('new_state')
        if not new_state:
            return None

        return {
            'type': 'change_conversation_state',
            'new_state': new_state,
            'conversation_id': str(conversation.id)
        }

    async def _execute_delay_action(
        self,
        parameters: Dict[str, Any],
        message: Message,
        conversation: Conversation,
        guest: Guest
    ) -> Optional[Dict[str, Any]]:
        """Execute delayed response action"""
        delay_seconds = parameters.get('delay_seconds', 60)

        return {
            'type': 'delayed_response',
            'delay_seconds': delay_seconds,
            'conversation_id': str(conversation.id),
            'guest_id': str(guest.id),
            'hotel_id': str(message.hotel_id)
        }

    async def _execute_ai_forward_action(
        self,
        parameters: Dict[str, Any],
        message: Message,
        conversation: Conversation,
        guest: Guest
    ) -> Optional[Dict[str, Any]]:
        """Execute forward to AI action"""
        return {
            'type': 'forward_to_ai',
            'ai_model': parameters.get('ai_model', 'default'),
            'context': parameters.get('context', {}),
            'conversation_id': str(conversation.id),
            'guest_id': str(guest.id),
            'hotel_id': str(message.hotel_id),
            'message_id': str(message.id)
        }