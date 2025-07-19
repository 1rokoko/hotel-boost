"""
Message template model for WhatsApp Hotel Bot application
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
from enum import Enum

from app.models.base import TenantBaseModel


class TemplateCategory(str, Enum):
    """Categories for message templates"""
    WELCOME = "welcome"
    BOOKING_CONFIRMATION = "booking_confirmation"
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"
    COMPLAINT_RESPONSE = "complaint_response"
    INFORMATION_REQUEST = "information_request"
    AMENITY_INFO = "amenity_info"
    ROOM_SERVICE = "room_service"
    MAINTENANCE = "maintenance"
    FEEDBACK_REQUEST = "feedback_request"
    PROMOTIONAL = "promotional"
    EMERGENCY = "emergency"
    CUSTOM = "custom"


class MessageTemplate(TenantBaseModel):
    """
    Message template model for storing reusable message templates

    Templates support Jinja2 syntax for variable substitution and can be
    categorized for easy organization. Each template belongs to a specific
    hotel (tenant) and can be activated/deactivated.
    """
    __tablename__ = "message_templates"

    # Template identification
    name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for the template"
    )

    category = Column(
        SQLEnum(TemplateCategory),
        nullable=False,
        comment="Category of the template for organization"
    )

    # Template content
    content = Column(
        Text,
        nullable=False,
        comment="Template content with Jinja2 syntax for variables"
    )

    # Template metadata
    variables = Column(
        JSON,
        default=list,
        nullable=False,
        comment="List of variable names used in the template"
    )

    language = Column(
        String(5),
        default="en",
        nullable=False,
        comment="Language code for the template (ISO 639-1)"
    )

    # Template status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the template is active and can be used"
    )

    # Optional description
    description = Column(
        Text,
        nullable=True,
        comment="Optional description of the template's purpose"
    )

    # Usage tracking
    usage_count = Column(
        JSON,
        default=dict,
        nullable=False,
        comment="Usage statistics for the template"
    )

    # Relationships
    hotel = relationship(
        "Hotel",
        back_populates="message_templates",
        lazy="select"
    )

    auto_response_rules = relationship(
        "AutoResponseRule",
        back_populates="template",
        lazy="select"
    )

    # Indexes for performance
    __table_args__ = (
        Index('idx_message_templates_hotel_category', 'hotel_id', 'category'),
        Index('idx_message_templates_hotel_active', 'hotel_id', 'is_active'),
        Index('idx_message_templates_hotel_language', 'hotel_id', 'language'),
        Index('idx_message_templates_category_language', 'category', 'language'),
    )

    def __repr__(self) -> str:
        """String representation of the template"""
        return f"<MessageTemplate(id={self.id}, name='{self.name}', category='{self.category.value}', hotel_id={self.hotel_id})>"

    def get_variable_names(self) -> List[str]:
        """
        Get list of variable names used in this template

        Returns:
            List[str]: List of variable names
        """
        return self.variables if isinstance(self.variables, list) else []

    def add_variable(self, variable_name: str) -> None:
        """
        Add a variable to the template's variable list

        Args:
            variable_name: Name of the variable to add
        """
        variables = self.get_variable_names()
        if variable_name not in variables:
            variables.append(variable_name)
            self.variables = variables

    def remove_variable(self, variable_name: str) -> None:
        """
        Remove a variable from the template's variable list

        Args:
            variable_name: Name of the variable to remove
        """
        variables = self.get_variable_names()
        if variable_name in variables:
            variables.remove(variable_name)
            self.variables = variables

    def increment_usage(self, context_type: str = "general") -> None:
        """
        Increment usage count for this template

        Args:
            context_type: Type of context where template was used
        """
        usage = self.usage_count if isinstance(self.usage_count, dict) else {}
        usage[context_type] = usage.get(context_type, 0) + 1
        usage['total'] = usage.get('total', 0) + 1
        usage['last_used'] = datetime.utcnow().isoformat()
        self.usage_count = usage

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for this template

        Returns:
            Dict[str, Any]: Usage statistics
        """
        return self.usage_count if isinstance(self.usage_count, dict) else {}

    def is_multilingual_variant(self, other_template: 'MessageTemplate') -> bool:
        """
        Check if this template is a multilingual variant of another template

        Args:
            other_template: Another template to compare with

        Returns:
            bool: True if templates are multilingual variants
        """
        return (
            self.hotel_id == other_template.hotel_id and
            self.category == other_template.category and
            self.name == other_template.name and
            self.language != other_template.language
        )

    def validate_content(self) -> List[str]:
        """
        Validate template content for common issues

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []

        if not self.content or not self.content.strip():
            errors.append("Template content cannot be empty")

        if len(self.content) > 4096:  # WhatsApp message limit
            errors.append("Template content exceeds maximum length (4096 characters)")

        # Check for basic Jinja2 syntax issues
        if self.content.count('{{') != self.content.count('}}'):
            errors.append("Unmatched Jinja2 variable delimiters")

        if self.content.count('{%') != self.content.count('%}'):
            errors.append("Unmatched Jinja2 block delimiters")

        return errors