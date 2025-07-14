"""
Message queue model for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal
from sqlalchemy import Column, String, Text, DateTime, Index, ForeignKey, CheckConstraint, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import enum

from app.models.base import TenantBaseModel


class MessageStatus(enum.Enum):
    """Enumeration of message queue status"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessagePriority(enum.Enum):
    """Enumeration of message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Create PostgreSQL ENUM types
message_status_enum = ENUM(
    MessageStatus,
    name='message_status',
    create_type=True,
    checkfirst=True
)

message_priority_enum = ENUM(
    MessagePriority,
    name='message_priority',
    create_type=True,
    checkfirst=True
)


class MessageQueue(TenantBaseModel):
    """
    Message queue model for managing outgoing messages
    
    This model handles the queuing, scheduling, and retry logic for outgoing messages.
    It provides reliable message delivery with retry mechanisms and status tracking.
    """
    __tablename__ = "message_queue"
    
    # Foreign keys
    guest_id = Column(
        UUID(as_uuid=True),
        ForeignKey('guests.id', ondelete='CASCADE'),
        nullable=False,
        comment="Guest ID for the message recipient"
    )
    
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey('messages.id', ondelete='CASCADE'),
        nullable=True,  # Can be null for system messages
        comment="Associated message ID"
    )
    
    # Message details
    phone_number = Column(
        String(20),
        nullable=False,
        comment="Recipient phone number"
    )
    
    priority = Column(
        message_priority_enum,
        nullable=False,
        default=MessagePriority.NORMAL,
        comment="Message priority level"
    )
    
    status = Column(
        message_status_enum,
        nullable=False,
        default=MessageStatus.PENDING,
        comment="Current message status"
    )
    
    # Message content and metadata
    message_data = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default='{}',
        comment="Message content and metadata"
    )
    
    # Scheduling and timing
    scheduled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Scheduled send time (null for immediate)"
    )
    
    sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Actual send time"
    )
    
    delivered_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Delivery confirmation time"
    )
    
    read_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Read confirmation time"
    )
    
    # Retry and error handling
    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts"
    )
    
    max_retries = Column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum number of retry attempts"
    )
    
    last_attempt_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last attempt timestamp"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Last error message if failed"
    )
    
    # Green API integration
    green_api_message_id = Column(
        String(255),
        nullable=True,
        comment="Green API message ID"
    )
    
    # Table constraints
    __table_args__ = (
        # Check constraint for retry count
        CheckConstraint(
            "retry_count >= 0 AND retry_count <= max_retries",
            name='ck_message_queue_retry_count'
        ),
        
        # Check constraint for phone number format
        CheckConstraint(
            "phone_number ~ '^\\+?[1-9]\\d{1,14}$'",
            name='ck_message_queue_phone_format'
        ),
        
        # Indexes for performance
        Index('idx_message_queue_hotel_id', 'hotel_id'),
        Index('idx_message_queue_guest_id', 'guest_id'),
        Index('idx_message_queue_status', 'status'),
        Index('idx_message_queue_priority', 'priority'),
        Index('idx_message_queue_scheduled', 'scheduled_at'),
        Index('idx_message_queue_phone', 'phone_number'),
        Index('idx_message_queue_green_api_id', 'green_api_message_id'),
        
        # Composite indexes
        Index('idx_message_queue_hotel_status', 'hotel_id', 'status'),
        Index('idx_message_queue_status_priority', 'status', 'priority'),
        Index('idx_message_queue_hotel_guest', 'hotel_id', 'guest_id'),
        
        # Partial indexes for active processing
        Index(
            'idx_message_queue_pending',
            'hotel_id', 'priority', 'created_at',
            postgresql_where="status = 'pending'"
        ),
        
        Index(
            'idx_message_queue_scheduled_ready',
            'hotel_id', 'scheduled_at',
            postgresql_where="status = 'scheduled' AND scheduled_at <= NOW()"
        ),
        
        Index(
            'idx_message_queue_failed_retryable',
            'hotel_id', 'last_attempt_at',
            postgresql_where="status = 'failed' AND retry_count < max_retries"
        ),
    )
    
    # Relationships
    hotel = relationship("Hotel", back_populates="message_queue")
    guest = relationship("Guest", back_populates="message_queue")
    message = relationship("Message", back_populates="queue_entry")
    
    @validates('phone_number')
    def validate_phone_number(self, key: str, value: str) -> str:
        """Validate phone number format"""
        if not value:
            raise ValueError("Phone number is required")
        
        # Basic validation - more detailed validation in service layer
        import re
        cleaned = re.sub(r'[^\d+]', '', value)
        
        if not re.match(r'^\+?[1-9]\d{1,14}$', cleaned):
            raise ValueError("Invalid phone number format")
        
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
            
        return cleaned
    
    @validates('retry_count')
    def validate_retry_count(self, key: str, value: int) -> int:
        """Validate retry count"""
        if value < 0:
            raise ValueError("Retry count cannot be negative")
        
        if hasattr(self, 'max_retries') and value > self.max_retries:
            raise ValueError(f"Retry count ({value}) exceeds max retries ({self.max_retries})")
        
        return value
    
    @hybrid_property
    def is_pending(self) -> bool:
        """Check if message is pending"""
        return self.status == MessageStatus.PENDING
    
    @hybrid_property
    def is_scheduled(self) -> bool:
        """Check if message is scheduled"""
        return self.status == MessageStatus.SCHEDULED
    
    @hybrid_property
    def is_ready_to_send(self) -> bool:
        """Check if message is ready to send"""
        if self.status == MessageStatus.PENDING:
            return True
        
        if self.status == MessageStatus.SCHEDULED and self.scheduled_at:
            return datetime.utcnow() >= self.scheduled_at
        
        return False
    
    @hybrid_property
    def is_failed(self) -> bool:
        """Check if message failed"""
        return self.status == MessageStatus.FAILED
    
    @hybrid_property
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return self.is_failed and self.retry_count < self.max_retries
    
    @hybrid_property
    def is_final_status(self) -> bool:
        """Check if message is in final status"""
        return self.status in [
            MessageStatus.DELIVERED,
            MessageStatus.READ,
            MessageStatus.CANCELLED
        ] or (self.status == MessageStatus.FAILED and not self.can_retry)
    
    def mark_as_sending(self) -> None:
        """Mark message as currently being sent"""
        self.status = MessageStatus.SENDING
        self.last_attempt_at = datetime.utcnow()
    
    def mark_as_sent(self, green_api_message_id: str) -> None:
        """Mark message as sent"""
        self.status = MessageStatus.SENT
        self.sent_at = datetime.utcnow()
        self.green_api_message_id = green_api_message_id
    
    def mark_as_delivered(self) -> None:
        """Mark message as delivered"""
        self.status = MessageStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
    
    def mark_as_read(self) -> None:
        """Mark message as read"""
        self.status = MessageStatus.READ
        self.read_at = datetime.utcnow()
    
    def mark_as_failed(self, error_message: str) -> None:
        """Mark message as failed"""
        self.status = MessageStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1
        self.last_attempt_at = datetime.utcnow()
    
    def mark_as_cancelled(self) -> None:
        """Mark message as cancelled"""
        self.status = MessageStatus.CANCELLED
    
    def reset_for_retry(self) -> None:
        """Reset message for retry"""
        if not self.can_retry:
            raise ValueError("Message cannot be retried")
        
        self.status = MessageStatus.PENDING
        self.error_message = None
    
    def get_message_data(self, key: str, default: Any = None) -> Any:
        """Get specific message data"""
        if not self.message_data:
            return default
        
        keys = key.split('.')
        value = self.message_data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_message_data(self, key: str, value: Any) -> None:
        """Set specific message data"""
        if not self.message_data:
            self.message_data = {}
        
        keys = key.split('.')
        current = self.message_data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = super().to_dict()
        
        # Add computed properties
        result['is_pending'] = self.is_pending
        result['is_scheduled'] = self.is_scheduled
        result['is_ready_to_send'] = self.is_ready_to_send
        result['is_failed'] = self.is_failed
        result['can_retry'] = self.can_retry
        result['is_final_status'] = self.is_final_status
        
        # Convert enums to strings
        result['status'] = self.status.value if self.status else None
        result['priority'] = self.priority.value if self.priority else None
        
        return result
    
    def __repr__(self) -> str:
        """String representation"""
        return (f"<MessageQueue(id={self.id}, hotel_id={self.hotel_id}, "
                f"guest_id={self.guest_id}, status='{self.status.value if self.status else None}', "
                f"priority='{self.priority.value if self.priority else None}')>")


# Export main components
__all__ = [
    'MessageQueue',
    'MessageStatus',
    'MessagePriority'
]
