"""
Conversation context model for persistent context storage
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base import TenantBaseModel


class ConversationContext(TenantBaseModel):
    """
    Model for storing conversation context data persistently
    
    This complements the Redis-based memory service for long-term context storage
    """
    __tablename__ = "conversation_contexts"
    
    # Foreign keys
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('conversations.id', ondelete='CASCADE'),
        nullable=False,
        comment="Conversation ID this context belongs to"
    )
    
    # Context data
    context_type = Column(
        String(50),
        nullable=False,
        comment="Type of context (current_request, guest_preferences, etc.)"
    )
    
    context_key = Column(
        String(100),
        nullable=False,
        comment="Specific key within the context type"
    )
    
    context_value = Column(
        JSON,
        nullable=False,
        comment="Context value stored as JSON"
    )
    
    # Metadata
    confidence_score = Column(
        String(10),
        nullable=True,
        comment="Confidence score for this context data (0.0-1.0)"
    )
    
    source = Column(
        String(50),
        nullable=False,
        default='system',
        comment="Source of this context (user_input, ai_inference, system, etc.)"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this context expires (NULL for permanent)"
    )
    
    last_accessed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When this context was last accessed"
    )
    
    # Table constraints and indexes
    __table_args__ = (
        # Unique constraint for conversation + type + key
        Index(
            'idx_conversation_context_unique',
            'conversation_id', 'context_type', 'context_key',
            unique=True
        ),
        
        # Performance indexes
        Index('idx_conversation_contexts_conversation_id', 'conversation_id'),
        Index('idx_conversation_contexts_type', 'context_type'),
        Index('idx_conversation_contexts_expires', 'expires_at'),
        Index('idx_conversation_contexts_accessed', 'last_accessed_at'),
        
        # Composite indexes for common queries
        Index('idx_conversation_contexts_conv_type', 'conversation_id', 'context_type'),
        Index('idx_conversation_contexts_type_key', 'context_type', 'context_key'),
        
        # Partial index for non-expired contexts
        Index(
            'idx_conversation_contexts_active',
            'conversation_id', 'context_type',
            postgresql_where="expires_at IS NULL OR expires_at > NOW()"
        ),
    )
    
    # Relationships
    conversation = relationship("Conversation", back_populates="context_entries")
    
    @validates('context_type')
    def validate_context_type(self, key: str, value: str) -> str:
        """Validate context type"""
        valid_types = [
            'current_request',
            'guest_preferences', 
            'conversation_history',
            'pending_actions',
            'collected_info',
            'intent_history',
            'sentiment_history',
            'escalation_triggers',
            'session_data',
            'custom'
        ]
        
        if value not in valid_types:
            raise ValueError(f"Invalid context type. Must be one of: {valid_types}")
        
        return value
    
    @validates('source')
    def validate_source(self, key: str, value: str) -> str:
        """Validate context source"""
        valid_sources = [
            'user_input',
            'ai_inference', 
            'system',
            'staff_input',
            'api_integration',
            'webhook',
            'scheduled_task'
        ]
        
        if value not in valid_sources:
            raise ValueError(f"Invalid source. Must be one of: {valid_sources}")
        
        return value
    
    @hybrid_property
    def is_expired(self) -> bool:
        """Check if context has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @hybrid_property
    def confidence_float(self) -> Optional[float]:
        """Get confidence score as float"""
        if self.confidence_score:
            try:
                return float(self.confidence_score)
            except (ValueError, TypeError):
                return None
        return None
    
    def update_access_time(self) -> None:
        """Update last accessed timestamp"""
        self.last_accessed_at = datetime.utcnow()
    
    def set_confidence(self, score: float) -> None:
        """Set confidence score"""
        if not 0.0 <= score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        self.confidence_score = str(score)
    
    def extend_expiry(self, hours: int = 24) -> None:
        """Extend expiry time"""
        from datetime import timedelta
        if self.expires_at:
            self.expires_at = max(self.expires_at, datetime.utcnow()) + timedelta(hours=hours)
        else:
            self.expires_at = datetime.utcnow() + timedelta(hours=hours)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': str(self.id),
            'conversation_id': str(self.conversation_id),
            'context_type': self.context_type,
            'context_key': self.context_key,
            'context_value': self.context_value,
            'confidence_score': self.confidence_float,
            'source': self.source,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_accessed_at': self.last_accessed_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_expired': self.is_expired
        }
    
    @classmethod
    def create_context_entry(
        cls,
        conversation_id: uuid.UUID,
        context_type: str,
        context_key: str,
        context_value: Any,
        confidence_score: Optional[float] = None,
        source: str = 'system',
        expires_hours: Optional[int] = None
    ) -> 'ConversationContext':
        """
        Create a new context entry
        
        Args:
            conversation_id: Conversation ID
            context_type: Type of context
            context_key: Context key
            context_value: Context value
            confidence_score: Optional confidence score
            source: Source of context
            expires_hours: Hours until expiry (None for permanent)
            
        Returns:
            ConversationContext: New context entry
        """
        expires_at = None
        if expires_hours:
            from datetime import timedelta
            expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        
        context_entry = cls(
            conversation_id=conversation_id,
            context_type=context_type,
            context_key=context_key,
            context_value=context_value,
            source=source,
            expires_at=expires_at
        )
        
        if confidence_score is not None:
            context_entry.set_confidence(confidence_score)
        
        return context_entry
    
    def __repr__(self) -> str:
        return (
            f"<ConversationContext(id={self.id}, "
            f"conversation_id={self.conversation_id}, "
            f"type={self.context_type}, "
            f"key={self.context_key})>"
        )


# Add relationship to Conversation model
# This would be added to the Conversation model in message.py:
# context_entries = relationship("ConversationContext", back_populates="conversation", cascade="all, delete-orphan")


# Export model
__all__ = ['ConversationContext']
