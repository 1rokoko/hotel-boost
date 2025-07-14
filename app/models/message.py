"""
Message and Conversation models for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from decimal import Decimal
from sqlalchemy import Column, String, Text, DateTime, Index, ForeignKey, CheckConstraint, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import enum

from app.models.base import TenantBaseModel

class MessageType(enum.Enum):
    """Enumeration of message types"""
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    SYSTEM = "system"

class SentimentType(enum.Enum):
    """Enumeration of sentiment types"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    REQUIRES_ATTENTION = "requires_attention"

# Create PostgreSQL ENUM types
message_type_enum = ENUM(
    MessageType,
    name='message_type',
    create_type=True,
    checkfirst=True
)

sentiment_type_enum = ENUM(
    SentimentType,
    name='sentiment_type',
    create_type=True,
    checkfirst=True
)

class ConversationStatus(enum.Enum):
    """Enumeration for conversation status"""
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"
    ESCALATED = "escalated"

class ConversationState(enum.Enum):
    """Enumeration for conversation states in the state machine"""
    GREETING = "greeting"
    COLLECTING_INFO = "collecting_info"
    PROCESSING_REQUEST = "processing_request"
    WAITING_RESPONSE = "waiting_response"
    ESCALATED = "escalated"
    COMPLETED = "completed"

# Create PostgreSQL ENUM types for conversation
conversation_status_enum = ENUM(
    ConversationStatus,
    name='conversation_status',
    create_type=True,
    checkfirst=True
)

conversation_state_enum = ENUM(
    ConversationState,
    name='conversation_state',
    create_type=True,
    checkfirst=True
)

class Conversation(TenantBaseModel):
    """
    Conversation model for tracking guest conversations
    
    Each conversation represents a series of messages between a guest and the hotel.
    """
    __tablename__ = "conversations"
    
    # Foreign keys
    hotel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hotels.id', ondelete='CASCADE'),
        nullable=False,
        comment="Hotel ID for multi-tenant data isolation"
    )
    
    guest_id = Column(
        UUID(as_uuid=True),
        ForeignKey('guests.id', ondelete='CASCADE'),
        nullable=False,
        comment="Guest ID for the conversation participant"
    )
    
    # Conversation metadata
    status = Column(
        conversation_status_enum,
        nullable=False,
        default=ConversationStatus.ACTIVE,
        comment="Conversation status (active, closed, archived, escalated)"
    )

    # State machine fields
    current_state = Column(
        conversation_state_enum,
        nullable=False,
        default=ConversationState.GREETING,
        comment="Current state in the conversation state machine"
    )

    context = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Conversation context and memory storage"
    )

    last_message_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Timestamp of the last message in the conversation"
    )
    
    # Table constraints
    __table_args__ = (
        # Indexes for performance
        Index('idx_conversations_hotel_id', 'hotel_id'),
        Index('idx_conversations_guest_id', 'guest_id'),
        Index('idx_conversations_status', 'status'),
        Index('idx_conversations_current_state', 'current_state'),
        Index('idx_conversations_last_message', 'last_message_at'),
        Index('idx_conversations_hotel_guest', 'hotel_id', 'guest_id'),
        Index('idx_conversations_hotel_status', 'hotel_id', 'status'),
        Index('idx_conversations_hotel_state', 'hotel_id', 'current_state'),

        # Partial index for active conversations
        Index(
            'idx_conversations_active',
            'hotel_id', 'last_message_at',
            postgresql_where="status = 'active'"
        ),

        # Partial index for conversations in specific states
        Index(
            'idx_conversations_processing',
            'hotel_id', 'current_state', 'last_message_at',
            postgresql_where="current_state IN ('processing_request', 'waiting_response')"
        ),
    )
    
    # Relationships
    hotel = relationship("Hotel", back_populates="conversations")
    guest = relationship("Guest", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    sentiment_analyses = relationship("SentimentAnalysis", back_populates="conversation", cascade="all, delete-orphan")
    staff_alerts = relationship("StaffAlert", back_populates="conversation", cascade="all, delete-orphan")
    
    @validates('status')
    def validate_status(self, key: str, value) -> ConversationStatus:
        """
        Validate conversation status

        Args:
            key: Field name
            value: Status to validate

        Returns:
            ConversationStatus: Validated status

        Raises:
            ValueError: If the status is invalid
        """
        if isinstance(value, str):
            try:
                value = ConversationStatus(value)
            except ValueError:
                raise ValueError(f"Invalid status. Must be one of: {[s.value for s in ConversationStatus]}")
        elif not isinstance(value, ConversationStatus):
            raise ValueError(f"Status must be ConversationStatus enum or string")
        return value

    @validates('current_state')
    def validate_current_state(self, key: str, value) -> ConversationState:
        """
        Validate conversation state

        Args:
            key: Field name
            value: State to validate

        Returns:
            ConversationState: Validated state

        Raises:
            ValueError: If the state is invalid
        """
        if isinstance(value, str):
            try:
                value = ConversationState(value)
            except ValueError:
                raise ValueError(f"Invalid state. Must be one of: {[s.value for s in ConversationState]}")
        elif not isinstance(value, ConversationState):
            raise ValueError(f"State must be ConversationState enum or string")
        return value

    def update_last_message_time(self) -> None:
        """Update the last message timestamp to now"""
        self.last_message_at = datetime.utcnow()

    def set_context(self, key: str, value: Any) -> None:
        """Set a context value"""
        if self.context is None:
            self.context = {}
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value"""
        if self.context is None:
            return default
        return self.context.get(key, default)

    def update_context(self, updates: Dict[str, Any]) -> None:
        """Update multiple context values"""
        if self.context is None:
            self.context = {}
        self.context.update(updates)

    def clear_context(self) -> None:
        """Clear all context data"""
        self.context = {}

    def close_conversation(self) -> None:
        """Close the conversation"""
        self.status = ConversationStatus.CLOSED
        self.current_state = ConversationState.COMPLETED
        self.update_last_message_time()

    def escalate_conversation(self) -> None:
        """Escalate the conversation"""
        self.status = ConversationStatus.ESCALATED
        self.current_state = ConversationState.ESCALATED
        self.update_last_message_time()

    def archive_conversation(self) -> None:
        """Archive the conversation"""
        self.status = ConversationStatus.ARCHIVED
    
    @hybrid_property
    def is_active(self) -> bool:
        """Check if conversation is active"""
        return self.status == 'active'
    
    @hybrid_property
    def is_closed(self) -> bool:
        """Check if conversation is closed"""
        return self.status == 'closed'
    
    @hybrid_property
    def is_escalated(self) -> bool:
        """Check if conversation is escalated"""
        return self.status == 'escalated'
    
    def __repr__(self) -> str:
        """String representation of the conversation"""
        return (f"<Conversation(id={self.id}, hotel_id={self.hotel_id}, "
                f"guest_id={self.guest_id}, status='{self.status}')>")

class Message(TenantBaseModel):
    """
    Message model for individual messages within conversations
    
    Each message represents a single communication between guest and hotel.
    """
    __tablename__ = "messages"
    
    # Foreign key to conversation (hotel_id inherited from TenantBaseModel)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('conversations.id', ondelete='CASCADE'),
        nullable=False,
        comment="Conversation ID for the message"
    )
    
    # Message type and content
    message_type = Column(
        message_type_enum,
        nullable=False,
        comment="Type of message (incoming, outgoing, system)"
    )
    
    content = Column(
        Text,
        nullable=False,
        comment="Message content"
    )
    
    # Sentiment analysis
    sentiment_score = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Sentiment score from -1.0 to 1.0"
    )
    
    sentiment_type = Column(
        sentiment_type_enum,
        nullable=True,
        comment="Categorized sentiment type"
    )
    
    # Message metadata
    message_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default='{}',
        comment="Message metadata (WhatsApp message ID, delivery status, etc.)"
    )
    
    # Table constraints
    __table_args__ = (
        # Check constraint for sentiment score range
        CheckConstraint(
            "sentiment_score IS NULL OR (sentiment_score >= -1.0 AND sentiment_score <= 1.0)",
            name='ck_messages_sentiment_score_range'
        ),
        
        # Indexes for performance
        Index('idx_messages_conversation_id', 'conversation_id'),
        Index('idx_messages_type', 'message_type'),
        Index('idx_messages_sentiment_type', 'sentiment_type'),
        Index('idx_messages_created_at', 'created_at'),
        Index('idx_messages_conversation_created', 'conversation_id', 'created_at'),
        
        # Partial index for negative sentiment messages
        Index(
            'idx_messages_negative_sentiment',
            'conversation_id', 'created_at',
            postgresql_where="sentiment_type = 'negative' OR sentiment_type = 'requires_attention'"
        ),
        
        # Partial index for incoming messages
        Index(
            'idx_messages_incoming',
            'conversation_id', 'created_at',
            postgresql_where="message_type = 'incoming'"
        ),
    )
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    queue_entry = relationship("MessageQueue", back_populates="message", uselist=False)
    sentiment_analysis = relationship("SentimentAnalysis", back_populates="message", uselist=False)
    staff_alerts = relationship("StaffAlert", back_populates="message", cascade="all, delete-orphan")
    
    @validates('content')
    def validate_content(self, key: str, value: str) -> str:
        """
        Validate message content
        
        Args:
            key: Field name
            value: Content to validate
            
        Returns:
            str: Validated content
            
        Raises:
            ValueError: If the content is invalid
        """
        if not value or not value.strip():
            raise ValueError("Message content is required")
        
        if len(value) > 4000:
            raise ValueError("Message content must be less than 4000 characters")
        
        return value.strip()
    
    @validates('sentiment_score')
    def validate_sentiment_score(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """
        Validate sentiment score
        
        Args:
            key: Field name
            value: Sentiment score to validate
            
        Returns:
            Optional[Decimal]: Validated sentiment score
            
        Raises:
            ValueError: If the sentiment score is invalid
        """
        if value is None:
            return None
        
        if not isinstance(value, (int, float, Decimal)):
            raise ValueError("Sentiment score must be a number")
        
        score = Decimal(str(value))
        if score < -1 or score > 1:
            raise ValueError("Sentiment score must be between -1.0 and 1.0")
        
        return score
    
    def set_sentiment(self, score: float, sentiment_type: Optional[SentimentType] = None) -> None:
        """
        Set sentiment score and type
        
        Args:
            score: Sentiment score (-1.0 to 1.0)
            sentiment_type: Optional sentiment type (will be auto-determined if not provided)
        """
        self.sentiment_score = Decimal(str(score))
        
        if sentiment_type:
            self.sentiment_type = sentiment_type
        else:
            # Auto-determine sentiment type based on score
            if score >= 0.3:
                self.sentiment_type = SentimentType.POSITIVE
            elif score <= -0.3:
                self.sentiment_type = SentimentType.NEGATIVE
            elif score <= -0.7:
                self.sentiment_type = SentimentType.REQUIRES_ATTENTION
            else:
                self.sentiment_type = SentimentType.NEUTRAL
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get a specific metadata value

        Args:
            key: Metadata key (supports dot notation for nested keys)
            default: Default value if key is not found

        Returns:
            Any: Metadata value or default
        """
        if not self.message_metadata:
            return default

        # Support dot notation for nested keys
        keys = key.split('.')
        value = self.message_metadata

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set a specific metadata value

        Args:
            key: Metadata key (supports dot notation for nested keys)
            value: Metadata value
        """
        if not self.message_metadata:
            self.message_metadata = {}

        # Support dot notation for nested keys
        keys = key.split('.')
        current = self.message_metadata

        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Set the final value
        current[keys[-1]] = value
    
    @hybrid_property
    def is_incoming(self) -> bool:
        """Check if message is incoming"""
        return self.message_type == MessageType.INCOMING
    
    @hybrid_property
    def is_outgoing(self) -> bool:
        """Check if message is outgoing"""
        return self.message_type == MessageType.OUTGOING
    
    @hybrid_property
    def is_system(self) -> bool:
        """Check if message is system-generated"""
        return self.message_type == MessageType.SYSTEM
    
    @hybrid_property
    def has_negative_sentiment(self) -> bool:
        """Check if message has negative sentiment"""
        return self.sentiment_type in [SentimentType.NEGATIVE, SentimentType.REQUIRES_ATTENTION]
    
    @hybrid_property
    def requires_attention(self) -> bool:
        """Check if message requires staff attention"""
        return self.sentiment_type == SentimentType.REQUIRES_ATTENTION
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary
        
        Returns:
            Dict[str, Any]: Message dictionary representation
        """
        result = super().to_dict()
        
        # Add computed properties
        result['is_incoming'] = self.is_incoming
        result['is_outgoing'] = self.is_outgoing
        result['is_system'] = self.is_system
        result['has_negative_sentiment'] = self.has_negative_sentiment
        result['requires_attention'] = self.requires_attention
        
        # Convert enums to strings
        result['message_type'] = self.message_type.value if self.message_type else None
        result['sentiment_type'] = self.sentiment_type.value if self.sentiment_type else None
        
        # Convert Decimal to float for JSON serialization
        if self.sentiment_score is not None:
            result['sentiment_score'] = float(self.sentiment_score)
        
        return result
    
    def __repr__(self) -> str:
        """String representation of the message"""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return (f"<Message(id={self.id}, conversation_id={self.conversation_id}, "
                f"type={self.message_type.value if self.message_type else None}, "
                f"content='{content_preview}')>")
