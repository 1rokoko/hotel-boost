"""
Pydantic schemas for conversation models
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, validator

from app.models.message import ConversationStatus, ConversationState


class ConversationBase(BaseModel):
    """Base conversation schema"""
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    current_state: ConversationState = Field(default=ConversationState.GREETING)
    context: Dict[str, Any] = Field(default_factory=dict)


class ConversationCreate(ConversationBase):
    """Schema for creating a conversation"""
    hotel_id: UUID
    guest_id: UUID


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation"""
    status: Optional[ConversationStatus] = None
    current_state: Optional[ConversationState] = None
    context: Optional[Dict[str, Any]] = None


class ConversationResponse(ConversationBase):
    """Schema for conversation response"""
    id: UUID
    hotel_id: UUID
    guest_id: UUID
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    """Detailed conversation response with relationships"""
    # Will be populated by the API layer with related data
    guest_name: Optional[str] = None
    hotel_name: Optional[str] = None
    message_count: Optional[int] = None
    last_message_content: Optional[str] = None


class StateTransitionRequest(BaseModel):
    """Schema for state transition requests"""
    new_state: ConversationState
    context_updates: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class StateTransitionResponse(BaseModel):
    """Schema for state transition responses"""
    success: bool
    previous_state: ConversationState
    new_state: ConversationState
    timestamp: datetime
    message: Optional[str] = None


class ConversationContextUpdate(BaseModel):
    """Schema for updating conversation context"""
    updates: Dict[str, Any]
    merge: bool = Field(default=True, description="Whether to merge with existing context or replace")


class ConversationListFilter(BaseModel):
    """Schema for filtering conversation lists"""
    hotel_id: Optional[UUID] = None
    guest_id: Optional[UUID] = None
    status: Optional[ConversationStatus] = None
    current_state: Optional[ConversationState] = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ConversationStats(BaseModel):
    """Schema for conversation statistics"""
    total_conversations: int
    active_conversations: int
    escalated_conversations: int
    completed_conversations: int
    state_distribution: Dict[str, int]
    avg_resolution_time: Optional[float] = None


# Export all schemas
__all__ = [
    'ConversationBase',
    'ConversationCreate', 
    'ConversationUpdate',
    'ConversationResponse',
    'ConversationDetailResponse',
    'StateTransitionRequest',
    'StateTransitionResponse',
    'ConversationContextUpdate',
    'ConversationListFilter',
    'ConversationStats'
]
