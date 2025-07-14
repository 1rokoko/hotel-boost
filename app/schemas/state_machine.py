"""
Pydantic schemas for state machine operations
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.message import ConversationState, ConversationStatus
from app.utils.state_transitions import TransitionTrigger


class StateTransitionRequest(BaseModel):
    """Request schema for state transitions"""
    target_state: ConversationState
    trigger: TransitionTrigger = Field(default=TransitionTrigger.MANUAL)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    reason: Optional[str] = None
    force: bool = Field(default=False, description="Force transition even if rules don't allow it")


class StateTransitionResponse(BaseModel):
    """Response schema for state transitions"""
    success: bool
    previous_state: ConversationState
    new_state: ConversationState
    trigger: TransitionTrigger
    rule_applied: Optional[str] = None
    timestamp: datetime
    message: Optional[str] = None
    context_updates: Optional[Dict[str, Any]] = None


class StateTransitionSuggestion(BaseModel):
    """Schema for state transition suggestions"""
    current_state: ConversationState
    suggested_state: Optional[ConversationState]
    confidence: float = Field(ge=0.0, le=1.0)
    applicable_rules: List[str]
    reasoning: str
    context_analysis: Dict[str, Any]


class ConversationStateInfo(BaseModel):
    """Information about a conversation state"""
    state: ConversationState
    description: str
    allowed_transitions: List[ConversationState]
    typical_duration_minutes: Optional[int] = None
    auto_transition_rules: List[str] = Field(default_factory=list)


class StateMachineStatus(BaseModel):
    """Status of the state machine"""
    total_states: int
    total_transitions: int
    active_rules: int
    last_updated: datetime


class StateTransitionHistory(BaseModel):
    """History entry for state transitions"""
    id: UUID
    conversation_id: UUID
    from_state: ConversationState
    to_state: ConversationState
    trigger: TransitionTrigger
    rule_name: Optional[str]
    timestamp: datetime
    context_snapshot: Optional[Dict[str, Any]] = None
    success: bool
    error_message: Optional[str] = None


class StateAnalytics(BaseModel):
    """Analytics for state transitions"""
    state: ConversationState
    total_entries: int
    total_exits: int
    avg_duration_minutes: float
    most_common_next_states: Dict[str, int]
    most_common_triggers: Dict[str, int]
    success_rate: float


class ConversationFlowAnalytics(BaseModel):
    """Analytics for conversation flows"""
    hotel_id: UUID
    date_range: Dict[str, datetime]
    total_conversations: int
    state_analytics: List[StateAnalytics]
    completion_rate: float
    escalation_rate: float
    avg_conversation_duration_minutes: float
    most_common_paths: List[List[str]]


class StateValidationRequest(BaseModel):
    """Request to validate a state transition"""
    conversation_id: UUID
    current_state: ConversationState
    target_state: ConversationState
    context: Dict[str, Any] = Field(default_factory=dict)


class StateValidationResponse(BaseModel):
    """Response for state validation"""
    valid: bool
    applicable_rules: List[str]
    blocking_reasons: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class AutoTransitionConfig(BaseModel):
    """Configuration for automatic transitions"""
    enabled: bool = True
    check_interval_seconds: int = Field(default=300, ge=60)  # 5 minutes minimum
    timeout_rules: Dict[ConversationState, int] = Field(default_factory=dict)  # state -> timeout in minutes
    sentiment_threshold: float = Field(default=-0.5, ge=-1.0, le=1.0)
    keyword_escalation_enabled: bool = True
    auto_completion_enabled: bool = True


class StateMachineMetrics(BaseModel):
    """Metrics for state machine performance"""
    transitions_per_hour: float
    avg_transition_time_ms: float
    error_rate: float
    most_active_states: Dict[str, int]
    bottleneck_states: List[str]  # States where conversations get stuck
    performance_score: float = Field(ge=0.0, le=100.0)


# Export all schemas
__all__ = [
    'StateTransitionRequest',
    'StateTransitionResponse', 
    'StateTransitionSuggestion',
    'ConversationStateInfo',
    'StateMachineStatus',
    'StateTransitionHistory',
    'StateAnalytics',
    'ConversationFlowAnalytics',
    'StateValidationRequest',
    'StateValidationResponse',
    'AutoTransitionConfig',
    'StateMachineMetrics'
]
