"""
Auto-response rule model for WhatsApp Hotel Bot application
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, time
from sqlalchemy import Column, String, Text, Boolean, Integer, Time, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from enum import Enum

from app.models.base import TenantBaseModel


class TriggerCondition(str, Enum):
    """Conditions that can trigger auto-responses"""
    KEYWORD_MATCH = "keyword_match"
    TIME_BASED = "time_based"
    CONVERSATION_STATE = "conversation_state"
    MESSAGE_COUNT = "message_count"
    SENTIMENT_BASED = "sentiment_based"
    GUEST_TYPE = "guest_type"
    LANGUAGE_BASED = "language_based"


class ResponseAction(str, Enum):
    """Actions that can be taken when rule is triggered"""
    SEND_TEMPLATE = "send_template"
    ESCALATE_TO_STAFF = "escalate_to_staff"
    SET_CONVERSATION_STATE = "set_conversation_state"
    DELAY_RESPONSE = "delay_response"
    FORWARD_TO_AI = "forward_to_ai"


class AutoResponseRule(TenantBaseModel):
    """
    Auto-response rule model for defining automated response behavior

    Rules define conditions under which automatic responses should be triggered
    and what actions should be taken. Each rule belongs to a specific hotel
    and can be activated/deactivated.
    """
    __tablename__ = "auto_response_rules"

    # Rule identification
    name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for the rule"
    )

    description = Column(
        Text,
        nullable=True,
        comment="Optional description of the rule's purpose"
    )

    # Rule priority and status
    priority = Column(
        Integer,
        default=100,
        nullable=False,
        comment="Rule priority (lower numbers = higher priority)"
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the rule is active and can be triggered"
    )

    # Trigger conditions
    trigger_conditions = Column(
        JSONB,
        nullable=False,
        comment="JSON array of conditions that must be met to trigger the rule"
    )

    # Response actions
    response_actions = Column(
        JSONB,
        nullable=False,
        comment="JSON array of actions to take when rule is triggered"
    )

    # Time-based constraints
    active_hours_start = Column(
        Time,
        nullable=True,
        comment="Start time for when rule is active (24-hour format)"
    )

    active_hours_end = Column(
        Time,
        nullable=True,
        comment="End time for when rule is active (24-hour format)"
    )

    # Language constraints
    languages = Column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of language codes this rule applies to (empty = all languages)"
    )

    # Template relationship
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey('message_templates.id', ondelete='SET NULL'),
        nullable=True,
        comment="Template to use for responses (if action is send_template)"
    )

    # Usage tracking
    usage_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of times this rule has been triggered"
    )

    last_triggered = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Timestamp and context of last trigger"
    )

    # Relationships
    hotel = relationship(
        "Hotel",
        back_populates="auto_response_rules",
        lazy="select"
    )

    template = relationship(
        "MessageTemplate",
        back_populates="auto_response_rules",
        lazy="select"
    )

    # Indexes for performance
    __table_args__ = (
        Index('idx_auto_response_rules_hotel_active', 'hotel_id', 'is_active'),
        Index('idx_auto_response_rules_hotel_priority', 'hotel_id', 'priority'),
        Index('idx_auto_response_rules_template', 'template_id'),
    )

    def __repr__(self) -> str:
        """String representation of the rule"""
        return f"<AutoResponseRule(id={self.id}, name='{self.name}', priority={self.priority}, hotel_id={self.hotel_id})>"

    def get_trigger_conditions(self) -> List[Dict[str, Any]]:
        """
        Get list of trigger conditions for this rule

        Returns:
            List[Dict[str, Any]]: List of condition dictionaries
        """
        return self.trigger_conditions if isinstance(self.trigger_conditions, list) else []

    def get_response_actions(self) -> List[Dict[str, Any]]:
        """
        Get list of response actions for this rule

        Returns:
            List[Dict[str, Any]]: List of action dictionaries
        """
        return self.response_actions if isinstance(self.response_actions, list) else []

    def add_condition(self, condition_type: TriggerCondition, parameters: Dict[str, Any]) -> None:
        """
        Add a trigger condition to this rule

        Args:
            condition_type: Type of condition to add
            parameters: Parameters for the condition
        """
        conditions = self.get_trigger_conditions()
        conditions.append({
            "type": condition_type.value,
            "parameters": parameters
        })
        self.trigger_conditions = conditions

    def add_action(self, action_type: ResponseAction, parameters: Dict[str, Any]) -> None:
        """
        Add a response action to this rule

        Args:
            action_type: Type of action to add
            parameters: Parameters for the action
        """
        actions = self.get_response_actions()
        actions.append({
            "type": action_type.value,
            "parameters": parameters
        })
        self.response_actions = actions

    def is_active_at_time(self, check_time: Optional[time] = None) -> bool:
        """
        Check if rule is active at a specific time

        Args:
            check_time: Time to check (defaults to current time)

        Returns:
            bool: True if rule is active at the given time
        """
        if not self.is_active:
            return False

        if not self.active_hours_start or not self.active_hours_end:
            return True  # No time restrictions

        if check_time is None:
            check_time = datetime.now().time()

        # Handle cases where end time is before start time (crosses midnight)
        if self.active_hours_start <= self.active_hours_end:
            return self.active_hours_start <= check_time <= self.active_hours_end
        else:
            return check_time >= self.active_hours_start or check_time <= self.active_hours_end

    def supports_language(self, language_code: str) -> bool:
        """
        Check if rule supports a specific language

        Args:
            language_code: Language code to check

        Returns:
            bool: True if rule supports the language
        """
        languages = self.languages if isinstance(self.languages, list) else []
        return not languages or language_code in languages

    def increment_usage(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Increment usage count and update last triggered info

        Args:
            context: Optional context information about the trigger
        """
        self.usage_count += 1
        self.last_triggered = {
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {}
        }

    def get_last_triggered_info(self) -> Dict[str, Any]:
        """
        Get information about when this rule was last triggered

        Returns:
            Dict[str, Any]: Last triggered information
        """
        return self.last_triggered if isinstance(self.last_triggered, dict) else {}

    def validate_rule(self) -> List[str]:
        """
        Validate rule configuration for common issues

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []

        if not self.name or not self.name.strip():
            errors.append("Rule name cannot be empty")

        conditions = self.get_trigger_conditions()
        if not conditions:
            errors.append("Rule must have at least one trigger condition")

        actions = self.get_response_actions()
        if not actions:
            errors.append("Rule must have at least one response action")

        # Validate time constraints
        if self.active_hours_start and self.active_hours_end:
            if self.active_hours_start == self.active_hours_end:
                errors.append("Active hours start and end cannot be the same")

        # Validate template reference for send_template actions
        for action in actions:
            if action.get("type") == ResponseAction.SEND_TEMPLATE.value:
                if not self.template_id:
                    errors.append("Template ID is required for send_template actions")

        return errors