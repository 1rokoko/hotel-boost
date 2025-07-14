"""
Staff Notification model for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, Text, DateTime, Index, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import enum

from app.models.base import TenantBaseModel

class NotificationType(enum.Enum):
    """Enumeration of notification types"""
    NEGATIVE_SENTIMENT = "negative_sentiment"
    URGENT_REQUEST = "urgent_request"
    SYSTEM_ALERT = "system_alert"
    GUEST_COMPLAINT = "guest_complaint"
    SERVICE_REQUEST = "service_request"
    ESCALATION = "escalation"

class NotificationStatus(enum.Enum):
    """Enumeration of notification statuses"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

# Create PostgreSQL ENUM types
notification_type_enum = ENUM(
    NotificationType,
    name='notification_type',
    create_type=True,
    checkfirst=True
)

notification_status_enum = ENUM(
    NotificationStatus,
    name='notification_status',
    create_type=True,
    checkfirst=True
)

class StaffNotification(TenantBaseModel):
    """
    Staff Notification model for alerting hotel staff about important events
    
    Notifications are created when certain conditions are met (negative sentiment,
    urgent requests, system alerts, etc.) and need staff attention.
    """
    __tablename__ = "staff_notifications"
    
    # Foreign keys
    hotel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hotels.id', ondelete='CASCADE'),
        nullable=False,
        comment="Hotel ID for multi-tenant data isolation"
    )
    
    guest_id = Column(
        UUID(as_uuid=True),
        ForeignKey('guests.id', ondelete='SET NULL'),
        nullable=True,
        comment="Guest ID related to the notification (optional)"
    )
    
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey('messages.id', ondelete='SET NULL'),
        nullable=True,
        comment="Message ID that triggered the notification (optional)"
    )
    
    # Notification details
    notification_type = Column(
        notification_type_enum,
        nullable=False,
        comment="Type of notification"
    )
    
    title = Column(
        String(255),
        nullable=False,
        comment="Notification title"
    )
    
    content = Column(
        Text,
        nullable=False,
        comment="Notification content/description"
    )
    
    # Status tracking
    status = Column(
        notification_status_enum,
        nullable=False,
        default=NotificationStatus.PENDING,
        comment="Current status of the notification"
    )
    
    # Timestamps
    sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when notification was sent"
    )
    
    acknowledged_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when notification was acknowledged by staff"
    )
    
    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the issue was resolved"
    )
    
    # Additional metadata
    notification_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default='{}',
        comment="Additional notification metadata"
    )
    
    # Table constraints
    __table_args__ = (
        # Indexes for performance
        Index('idx_staff_notifications_hotel_id', 'hotel_id'),
        Index('idx_staff_notifications_guest_id', 'guest_id'),
        Index('idx_staff_notifications_message_id', 'message_id'),
        Index('idx_staff_notifications_type', 'notification_type'),
        Index('idx_staff_notifications_status', 'status'),
        Index('idx_staff_notifications_created_at', 'created_at'),
        Index('idx_staff_notifications_sent_at', 'sent_at'),
        Index('idx_staff_notifications_hotel_status', 'hotel_id', 'status'),
        Index('idx_staff_notifications_hotel_type', 'hotel_id', 'notification_type'),
        
        # Partial index for pending notifications
        Index(
            'idx_staff_notifications_pending',
            'hotel_id', 'created_at',
            postgresql_where="status = 'pending'"
        ),
        
        # Partial index for unresolved notifications
        Index(
            'idx_staff_notifications_unresolved',
            'hotel_id', 'notification_type', 'created_at',
            postgresql_where="status IN ('pending', 'sent', 'acknowledged')"
        ),
    )
    
    # Relationships
    hotel = relationship("Hotel", back_populates="staff_notifications")
    guest = relationship("Guest", back_populates="staff_notifications")
    message = relationship("Message")
    
    @validates('title')
    def validate_title(self, key: str, value: str) -> str:
        """
        Validate notification title
        
        Args:
            key: Field name
            value: Title to validate
            
        Returns:
            str: Validated title
            
        Raises:
            ValueError: If the title is invalid
        """
        if not value or not value.strip():
            raise ValueError("Notification title is required")
        
        if len(value.strip()) > 255:
            raise ValueError("Notification title must be less than 255 characters")
        
        return value.strip()
    
    @validates('content')
    def validate_content(self, key: str, value: str) -> str:
        """
        Validate notification content
        
        Args:
            key: Field name
            value: Content to validate
            
        Returns:
            str: Validated content
            
        Raises:
            ValueError: If the content is invalid
        """
        if not value or not value.strip():
            raise ValueError("Notification content is required")
        
        if len(value.strip()) > 4000:
            raise ValueError("Notification content must be less than 4000 characters")
        
        return value.strip()
    
    def mark_as_sent(self) -> None:
        """Mark notification as sent"""
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.utcnow()
    
    def mark_as_failed(self) -> None:
        """Mark notification as failed"""
        self.status = NotificationStatus.FAILED
    
    def acknowledge(self) -> None:
        """Acknowledge the notification"""
        if self.status in [NotificationStatus.SENT, NotificationStatus.PENDING]:
            self.status = NotificationStatus.ACKNOWLEDGED
            self.acknowledged_at = datetime.utcnow()
    
    def resolve(self) -> None:
        """Mark the notification as resolved"""
        self.status = NotificationStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        if not self.acknowledged_at:
            self.acknowledged_at = datetime.utcnow()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get a specific metadata value

        Args:
            key: Metadata key (supports dot notation for nested keys)
            default: Default value if key is not found

        Returns:
            Any: Metadata value or default
        """
        if not self.notification_metadata:
            return default

        # Support dot notation for nested keys
        keys = key.split('.')
        value = self.notification_metadata

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
        if not self.notification_metadata:
            self.notification_metadata = {}

        # Support dot notation for nested keys
        keys = key.split('.')
        current = self.notification_metadata

        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Set the final value
        current[keys[-1]] = value
    
    @hybrid_property
    def is_pending(self) -> bool:
        """Check if notification is pending"""
        return self.status == NotificationStatus.PENDING
    
    @hybrid_property
    def is_sent(self) -> bool:
        """Check if notification is sent"""
        return self.status == NotificationStatus.SENT
    
    @hybrid_property
    def is_acknowledged(self) -> bool:
        """Check if notification is acknowledged"""
        return self.status == NotificationStatus.ACKNOWLEDGED
    
    @hybrid_property
    def is_resolved(self) -> bool:
        """Check if notification is resolved"""
        return self.status == NotificationStatus.RESOLVED
    
    @hybrid_property
    def is_failed(self) -> bool:
        """Check if notification failed"""
        return self.status == NotificationStatus.FAILED
    
    @hybrid_property
    def requires_action(self) -> bool:
        """Check if notification requires action"""
        return self.status in [NotificationStatus.PENDING, NotificationStatus.SENT, NotificationStatus.ACKNOWLEDGED]
    
    @hybrid_property
    def is_urgent(self) -> bool:
        """Check if notification is urgent"""
        return self.notification_type in [
            NotificationType.URGENT_REQUEST,
            NotificationType.GUEST_COMPLAINT,
            NotificationType.ESCALATION
        ]
    
    def get_priority_score(self) -> int:
        """
        Get priority score for notification ordering
        
        Returns:
            int: Priority score (higher = more urgent)
        """
        base_scores = {
            NotificationType.ESCALATION: 100,
            NotificationType.URGENT_REQUEST: 90,
            NotificationType.GUEST_COMPLAINT: 80,
            NotificationType.NEGATIVE_SENTIMENT: 70,
            NotificationType.SERVICE_REQUEST: 60,
            NotificationType.SYSTEM_ALERT: 50,
        }
        
        score = base_scores.get(self.notification_type, 50)
        
        # Increase priority for older notifications
        if self.created_at:
            hours_old = (datetime.utcnow() - self.created_at).total_seconds() / 3600
            score += min(hours_old * 2, 20)  # Max 20 points for age
        
        return int(score)
    
    @classmethod
    def create_from_message(
        cls,
        hotel_id: uuid.UUID,
        message_id: uuid.UUID,
        guest_id: uuid.UUID,
        notification_type: NotificationType,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "StaffNotification":
        """
        Create a notification from a message
        
        Args:
            hotel_id: Hotel ID
            message_id: Message ID that triggered the notification
            guest_id: Guest ID
            notification_type: Type of notification
            title: Notification title
            content: Notification content
            metadata: Additional metadata
            
        Returns:
            StaffNotification: New notification instance
        """
        return cls(
            hotel_id=hotel_id,
            message_id=message_id,
            guest_id=guest_id,
            notification_type=notification_type,
            title=title,
            content=content,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_system_alert(
        cls,
        hotel_id: uuid.UUID,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "StaffNotification":
        """
        Create a system alert notification
        
        Args:
            hotel_id: Hotel ID
            title: Alert title
            content: Alert content
            metadata: Additional metadata
            
        Returns:
            StaffNotification: New notification instance
        """
        return cls(
            hotel_id=hotel_id,
            notification_type=NotificationType.SYSTEM_ALERT,
            title=title,
            content=content,
            metadata=metadata or {}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert notification to dictionary
        
        Returns:
            Dict[str, Any]: Notification dictionary representation
        """
        result = super().to_dict()
        
        # Add computed properties
        result['is_pending'] = self.is_pending
        result['is_sent'] = self.is_sent
        result['is_acknowledged'] = self.is_acknowledged
        result['is_resolved'] = self.is_resolved
        result['is_failed'] = self.is_failed
        result['requires_action'] = self.requires_action
        result['is_urgent'] = self.is_urgent
        result['priority_score'] = self.get_priority_score()
        
        # Convert enums to strings
        result['notification_type'] = self.notification_type.value if self.notification_type else None
        result['status'] = self.status.value if self.status else None
        
        return result
    
    def __repr__(self) -> str:
        """String representation of the notification"""
        return (f"<StaffNotification(id={self.id}, hotel_id={self.hotel_id}, "
                f"type={self.notification_type.value if self.notification_type else None}, "
                f"status={self.status.value if self.status else None}, "
                f"title='{self.title[:30]}...')>")
