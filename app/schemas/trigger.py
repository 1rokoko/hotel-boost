"""
Trigger schemas for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime, time
from typing import Dict, Any, Optional, List, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.types import constr, conint

from app.models.trigger import TriggerType


class TriggerConditionOperator(str, Enum):
    """Operators for trigger conditions"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    REGEX = "regex"


class TriggerConditionLogic(str, Enum):
    """Logic operators for combining conditions"""
    AND = "AND"
    OR = "OR"


class TriggerScheduleType(str, Enum):
    """Types of trigger scheduling"""
    HOURS_AFTER_CHECKIN = "hours_after_checkin"
    DAYS_AFTER_CHECKIN = "days_after_checkin"
    MINUTES_AFTER_FIRST_MESSAGE = "minutes_after_first_message"
    SECONDS_AFTER_FIRST_MESSAGE = "seconds_after_first_message"
    SPECIFIC_TIME = "specific_time"
    CRON_EXPRESSION = "cron_expression"
    IMMEDIATE = "immediate"


class TriggerEventType(str, Enum):
    """Types of events that can trigger actions"""
    GUEST_CHECKIN = "guest_checkin"
    GUEST_CHECKOUT = "guest_checkout"
    MESSAGE_RECEIVED = "message_received"
    FIRST_MESSAGE_RECEIVED = "first_message_received"
    NEGATIVE_SENTIMENT_DETECTED = "negative_sentiment_detected"
    POSITIVE_SENTIMENT_DETECTED = "positive_sentiment_detected"
    GUEST_COMPLAINT = "guest_complaint"
    REVIEW_REQUEST_TIME = "review_request_time"
    NEGATIVE_SENTIMENT = "negative_sentiment"
    BOOKING_CONFIRMED = "booking_confirmed"
    BOOKING_CANCELLED = "booking_cancelled"


class TriggerCondition(BaseModel):
    """Schema for individual trigger condition"""
    field: constr(min_length=1, max_length=255) = Field(
        ..., 
        description="Field path to evaluate (e.g., 'guest.preferences.room_type')"
    )
    operator: TriggerConditionOperator = Field(
        ..., 
        description="Comparison operator"
    )
    value: Union[str, int, float, bool, List[Any]] = Field(
        ..., 
        description="Value to compare against"
    )
    
    @field_validator('field')
    @classmethod
    def validate_field_path(cls, v):
        """Validate field path format"""
        if not v or '..' in v or v.startswith('.') or v.endswith('.'):
            raise ValueError("Invalid field path format")
        return v


class TimeBasedConditions(BaseModel):
    """Schema for time-based trigger conditions"""
    schedule_type: TriggerScheduleType = Field(
        ..., 
        description="Type of scheduling"
    )
    hours_after: Optional[conint(ge=0, le=8760)] = Field(  # Max 1 year
        None, 
        description="Hours after check-in (for hours_after_checkin)"
    )
    days_after: Optional[conint(ge=0, le=365)] = Field(  # Max 1 year
        None, 
        description="Days after check-in (for days_after_checkin)"
    )
    specific_time: Optional[time] = Field(
        None, 
        description="Specific time of day (for specific_time)"
    )
    cron_expression: Optional[constr(max_length=100)] = Field(
        None, 
        description="Cron expression (for cron_expression)"
    )
    timezone: str = Field(
        default="Asia/Bangkok",
        description="Timezone for scheduling"
    )
    
    @model_validator(mode='before')
    @classmethod
    def validate_schedule_conditions(cls, values):
        """Validate that required fields are present for each schedule type"""
        schedule_type = values.get('schedule_type')
        
        if schedule_type == TriggerScheduleType.HOURS_AFTER_CHECKIN:
            if not values.get('hours_after'):
                raise ValueError("hours_after is required for hours_after_checkin")
        elif schedule_type == TriggerScheduleType.DAYS_AFTER_CHECKIN:
            if not values.get('days_after'):
                raise ValueError("days_after is required for days_after_checkin")
        elif schedule_type == TriggerScheduleType.SPECIFIC_TIME:
            if not values.get('specific_time'):
                raise ValueError("specific_time is required for specific_time")
        elif schedule_type == TriggerScheduleType.CRON_EXPRESSION:
            if not values.get('cron_expression'):
                raise ValueError("cron_expression is required for cron_expression")
        
        return values


class ConditionBasedConditions(BaseModel):
    """Schema for condition-based trigger conditions"""
    conditions: List[TriggerCondition] = Field(
        ..., 
        min_items=1, 
        description="List of conditions to evaluate"
    )
    logic: TriggerConditionLogic = Field(
        default=TriggerConditionLogic.AND, 
        description="Logic operator for combining conditions"
    )


class EventBasedConditions(BaseModel):
    """Schema for event-based trigger conditions"""
    event_type: TriggerEventType = Field(
        ..., 
        description="Type of event that triggers the action"
    )
    delay_minutes: conint(ge=0, le=10080) = Field(  # Max 1 week
        default=0, 
        description="Delay in minutes before executing trigger"
    )
    event_filters: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional filters for the event"
    )


class TriggerConditionsUnion(BaseModel):
    """Union schema for all trigger condition types"""
    time_based: Optional[TimeBasedConditions] = None
    condition_based: Optional[ConditionBasedConditions] = None
    event_based: Optional[EventBasedConditions] = None
    
    @model_validator(mode='before')
    @classmethod
    def validate_single_condition_type(cls, values):
        """Ensure only one condition type is specified"""
        condition_types = [v for v in values.values() if v is not None]
        if len(condition_types) != 1:
            raise ValueError("Exactly one condition type must be specified")
        return values


class TriggerBase(BaseModel):
    """Base schema for trigger"""
    name: constr(min_length=1, max_length=255) = Field(
        ..., 
        description="Human-readable name for the trigger"
    )
    trigger_type: TriggerType = Field(
        ..., 
        description="Type of trigger"
    )
    message_template: constr(min_length=1, max_length=10000) = Field(
        ..., 
        description="Message template with Jinja2 syntax"
    )
    is_active: bool = Field(
        default=True, 
        description="Whether the trigger is active"
    )
    priority: conint(ge=1, le=10) = Field(
        default=1, 
        description="Trigger priority (1 = highest)"
    )


class TriggerCreate(TriggerBase):
    """Schema for creating a trigger"""
    conditions: TriggerConditionsUnion = Field(
        ..., 
        description="Trigger conditions based on trigger type"
    )
    
    @model_validator(mode='before')
    @classmethod
    def validate_conditions_match_type(cls, values):
        """Validate that conditions match the trigger type"""
        trigger_type = values.get('trigger_type')
        conditions = values.get('conditions')

        if not conditions:
            return values

        if trigger_type == TriggerType.TIME_BASED and not conditions.time_based:
            raise ValueError("time_based conditions required for TIME_BASED trigger")
        elif trigger_type == TriggerType.CONDITION_BASED and not conditions.condition_based:
            raise ValueError("condition_based conditions required for CONDITION_BASED trigger")
        elif trigger_type == TriggerType.EVENT_BASED and not conditions.event_based:
            raise ValueError("event_based conditions required for EVENT_BASED trigger")

        return values


class TriggerUpdate(BaseModel):
    """Schema for updating a trigger"""
    name: Optional[constr(min_length=1, max_length=255)] = None
    message_template: Optional[constr(min_length=1, max_length=10000)] = None
    conditions: Optional[TriggerConditionsUnion] = None
    is_active: Optional[bool] = None
    priority: Optional[conint(ge=1, le=10)] = None


class TriggerResponse(TriggerBase):
    """Schema for trigger response"""
    id: uuid.UUID = Field(..., description="Trigger unique identifier")
    hotel_id: uuid.UUID = Field(..., description="Hotel unique identifier")
    conditions: Dict[str, Any] = Field(..., description="Trigger conditions")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class TriggerListResponse(BaseModel):
    """Schema for trigger list response"""
    triggers: List[TriggerResponse] = Field(..., description="List of triggers")
    total: int = Field(..., description="Total number of triggers")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")


class TriggerTestData(BaseModel):
    """Schema for trigger testing"""
    guest_data: Optional[Dict[str, Any]] = Field(
        None, 
        description="Mock guest data for testing"
    )
    context_data: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional context data for testing"
    )
    dry_run: bool = Field(
        default=True, 
        description="Whether to perform a dry run (no actual message sending)"
    )


class TriggerTestResult(BaseModel):
    """Schema for trigger test result"""
    success: bool = Field(..., description="Whether the test was successful")
    conditions_met: bool = Field(..., description="Whether conditions were met")
    rendered_message: Optional[str] = Field(None, description="Rendered message template")
    error_message: Optional[str] = Field(None, description="Error message if test failed")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")


class TriggerExecutionLog(BaseModel):
    """Schema for trigger execution log"""
    trigger_id: uuid.UUID = Field(..., description="Trigger ID")
    guest_id: Optional[uuid.UUID] = Field(None, description="Guest ID")
    executed_at: datetime = Field(..., description="Execution timestamp")
    success: bool = Field(..., description="Whether execution was successful")
    message_sent: Optional[str] = Field(None, description="Message that was sent")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")


# Export all schemas
__all__ = [
    # Enums
    'TriggerConditionOperator', 'TriggerConditionLogic', 'TriggerScheduleType', 
    'TriggerEventType',
    
    # Condition schemas
    'TriggerCondition', 'TimeBasedConditions', 'ConditionBasedConditions', 
    'EventBasedConditions', 'TriggerConditionsUnion',
    
    # Main schemas
    'TriggerBase', 'TriggerCreate', 'TriggerUpdate', 'TriggerResponse', 
    'TriggerListResponse',
    
    # Testing schemas
    'TriggerTestData', 'TriggerTestResult',
    
    # Logging schemas
    'TriggerExecutionLog'
]
