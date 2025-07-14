"""
Sentiment analysis database models for WhatsApp Hotel Bot
"""

from sqlalchemy import Column, String, Float, Boolean, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from enum import Enum
import uuid

from app.models.base import TenantAuditableModel
from app.schemas.deepseek import SentimentType


class SentimentAnalysis(TenantAuditableModel):
    """
    Sentiment analysis results for guest messages
    
    Stores the results of AI-powered sentiment analysis for each message,
    including confidence scores and metadata for monitoring and analytics.
    """
    __tablename__ = "sentiment_analysis"
    
    # Message reference
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the analyzed message"
    )
    
    # Guest and conversation context
    guest_id = Column(
        UUID(as_uuid=True),
        ForeignKey("guests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Guest who sent the message"
    )
    
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Conversation context"
    )
    
    # Sentiment analysis results
    sentiment_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Sentiment classification (positive, negative, neutral, requires_attention)"
    )
    
    sentiment_score = Column(
        Float,
        nullable=False,
        comment="Sentiment score from -1.0 (very negative) to 1.0 (very positive)"
    )
    
    confidence_score = Column(
        Float,
        nullable=False,
        comment="Confidence in the sentiment analysis from 0.0 to 1.0"
    )
    
    requires_attention = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this sentiment requires staff attention"
    )
    
    # Analysis metadata
    analyzed_text = Column(
        Text,
        nullable=False,
        comment="The text that was analyzed"
    )
    
    language_detected = Column(
        String(10),
        nullable=True,
        comment="Detected language of the text"
    )
    
    keywords = Column(
        JSON,
        nullable=True,
        comment="Key sentiment indicators found in the text"
    )
    
    reasoning = Column(
        Text,
        nullable=True,
        comment="AI explanation for the sentiment classification"
    )
    
    # AI model information
    model_used = Column(
        String(100),
        nullable=False,
        comment="AI model used for analysis"
    )
    
    model_version = Column(
        String(50),
        nullable=True,
        comment="Version of the AI model"
    )
    
    # Processing metadata
    processing_time_ms = Column(
        Float,
        nullable=True,
        comment="Time taken to process the sentiment analysis in milliseconds"
    )
    
    tokens_used = Column(
        Float,
        nullable=True,
        comment="Number of tokens used for the analysis"
    )
    
    correlation_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Correlation ID for tracking across services"
    )
    
    # Notification tracking
    notification_sent = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether staff notification was sent for this sentiment"
    )
    
    notification_sent_at = Column(
        DateTime,
        nullable=True,
        comment="When staff notification was sent"
    )
    
    # Relationships
    message = relationship("Message", back_populates="sentiment_analysis")
    guest = relationship("Guest", back_populates="sentiment_analyses")
    conversation = relationship("Conversation", back_populates="sentiment_analyses")
    staff_alerts = relationship("StaffAlert", back_populates="sentiment_analysis", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_sentiment_hotel_date', 'hotel_id', 'created_at'),
        Index('idx_sentiment_guest_date', 'guest_id', 'created_at'),
        Index('idx_sentiment_type_score', 'sentiment_type', 'sentiment_score'),
        Index('idx_sentiment_attention', 'requires_attention', 'created_at'),
        Index('idx_sentiment_correlation', 'correlation_id'),
    )
    
    def __repr__(self):
        return (
            f"<SentimentAnalysis(id={self.id}, "
            f"sentiment={self.sentiment_type}, "
            f"score={self.sentiment_score:.2f}, "
            f"confidence={self.confidence_score:.2f})>"
        )
    
    @property
    def is_positive(self) -> bool:
        """Check if sentiment is positive"""
        return self.sentiment_type == SentimentType.POSITIVE.value
    
    @property
    def is_negative(self) -> bool:
        """Check if sentiment is negative"""
        return self.sentiment_type in [SentimentType.NEGATIVE.value, SentimentType.REQUIRES_ATTENTION.value]
    
    @property
    def is_neutral(self) -> bool:
        """Check if sentiment is neutral"""
        return self.sentiment_type == SentimentType.NEUTRAL.value
    
    @property
    def needs_staff_attention(self) -> bool:
        """Check if this sentiment needs staff attention"""
        return self.requires_attention and not self.notification_sent
    
    def mark_notification_sent(self):
        """Mark that staff notification has been sent"""
        self.notification_sent = True
        self.notification_sent_at = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'message_id': str(self.message_id),
            'guest_id': str(self.guest_id),
            'conversation_id': str(self.conversation_id) if self.conversation_id else None,
            'sentiment_type': self.sentiment_type,
            'sentiment_score': self.sentiment_score,
            'confidence_score': self.confidence_score,
            'requires_attention': self.requires_attention,
            'analyzed_text': self.analyzed_text,
            'language_detected': self.language_detected,
            'keywords': self.keywords,
            'reasoning': self.reasoning,
            'model_used': self.model_used,
            'model_version': self.model_version,
            'processing_time_ms': self.processing_time_ms,
            'tokens_used': self.tokens_used,
            'correlation_id': self.correlation_id,
            'notification_sent': self.notification_sent,
            'notification_sent_at': self.notification_sent_at.isoformat() if self.notification_sent_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class SentimentSummary(TenantAuditableModel):
    """
    Daily sentiment summary for hotels
    
    Aggregated sentiment data for analytics and reporting.
    """
    __tablename__ = "sentiment_summaries"
    
    # Date and scope
    summary_date = Column(
        DateTime,
        nullable=False,
        index=True,
        comment="Date for this summary"
    )
    
    # Sentiment counts
    total_messages = Column(
        Float,
        nullable=False,
        default=0,
        comment="Total messages analyzed"
    )
    
    positive_count = Column(
        Float,
        nullable=False,
        default=0,
        comment="Number of positive messages"
    )
    
    negative_count = Column(
        Float,
        nullable=False,
        default=0,
        comment="Number of negative messages"
    )
    
    neutral_count = Column(
        Float,
        nullable=False,
        default=0,
        comment="Number of neutral messages"
    )
    
    attention_required_count = Column(
        Float,
        nullable=False,
        default=0,
        comment="Number of messages requiring attention"
    )
    
    # Average scores
    average_sentiment_score = Column(
        Float,
        nullable=True,
        comment="Average sentiment score for the day"
    )
    
    average_confidence_score = Column(
        Float,
        nullable=True,
        comment="Average confidence score for the day"
    )
    
    # Notification metrics
    notifications_sent = Column(
        Float,
        nullable=False,
        default=0,
        comment="Number of staff notifications sent"
    )
    
    # Processing metrics
    total_tokens_used = Column(
        Float,
        nullable=True,
        comment="Total tokens used for sentiment analysis"
    )
    
    average_processing_time_ms = Column(
        Float,
        nullable=True,
        comment="Average processing time in milliseconds"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_sentiment_summary_hotel_date', 'hotel_id', 'summary_date'),
        Index('idx_sentiment_summary_date', 'summary_date'),
    )
    
    def __repr__(self):
        return (
            f"<SentimentSummary(id={self.id}, "
            f"hotel_id={self.hotel_id}, "
            f"date={self.summary_date.date()}, "
            f"total={self.total_messages})>"
        )
    
    @property
    def positive_percentage(self) -> float:
        """Calculate positive sentiment percentage"""
        if self.total_messages == 0:
            return 0.0
        return (self.positive_count / self.total_messages) * 100
    
    @property
    def negative_percentage(self) -> float:
        """Calculate negative sentiment percentage"""
        if self.total_messages == 0:
            return 0.0
        return (self.negative_count / self.total_messages) * 100
    
    @property
    def attention_percentage(self) -> float:
        """Calculate attention required percentage"""
        if self.total_messages == 0:
            return 0.0
        return (self.attention_required_count / self.total_messages) * 100
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'hotel_id': str(self.hotel_id),
            'summary_date': self.summary_date.isoformat(),
            'total_messages': self.total_messages,
            'positive_count': self.positive_count,
            'negative_count': self.negative_count,
            'neutral_count': self.neutral_count,
            'attention_required_count': self.attention_required_count,
            'positive_percentage': self.positive_percentage,
            'negative_percentage': self.negative_percentage,
            'attention_percentage': self.attention_percentage,
            'average_sentiment_score': self.average_sentiment_score,
            'average_confidence_score': self.average_confidence_score,
            'notifications_sent': self.notifications_sent,
            'total_tokens_used': self.total_tokens_used,
            'average_processing_time_ms': self.average_processing_time_ms,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# Export main components
__all__ = [
    'SentimentAnalysis',
    'SentimentSummary'
]
