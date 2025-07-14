"""
Sentiment configuration models for hotel-specific settings
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import TenantAuditableModel


class SentimentConfig(TenantAuditableModel):
    """Model for hotel-specific sentiment analysis configuration"""
    
    __tablename__ = "sentiment_configs"
    
    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique configuration identifier"
    )
    
    # Configuration name and description
    config_name = Column(
        String(100),
        nullable=False,
        default="Default Configuration",
        comment="Name of the configuration"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Description of the configuration"
    )
    
    # Sentiment thresholds
    thresholds = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Sentiment analysis thresholds and limits"
    )
    
    # Notification settings
    notification_settings = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Notification channel configurations"
    )
    
    # Escalation rules
    escalation_rules = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Escalation rules and procedures"
    )
    
    # Alert configuration
    alert_config = Column(
        JSON,
        nullable=True,
        comment="Alert generation and management settings"
    )
    
    # Response time targets
    response_time_targets = Column(
        JSON,
        nullable=True,
        comment="Target response times by priority level"
    )
    
    # Custom rules
    custom_rules = Column(
        JSON,
        nullable=True,
        comment="Hotel-specific custom sentiment rules"
    )
    
    # AI model settings
    ai_model_settings = Column(
        JSON,
        nullable=True,
        comment="AI model configuration and parameters"
    )
    
    # Status and activation
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this configuration is active"
    )
    
    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the default configuration for the hotel"
    )
    
    # Versioning
    version = Column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Configuration version"
    )
    
    # Audit fields
    created_by = Column(
        String(100),
        nullable=False,
        comment="User who created the configuration"
    )
    
    updated_by = Column(
        String(100),
        nullable=False,
        comment="User who last updated the configuration"
    )
    
    activated_at = Column(
        DateTime,
        nullable=True,
        comment="When this configuration was activated"
    )
    
    activated_by = Column(
        String(100),
        nullable=True,
        comment="User who activated this configuration"
    )
    
    # Effectiveness tracking
    effectiveness_score = Column(
        JSON,
        nullable=True,
        comment="Effectiveness metrics for this configuration"
    )
    
    last_effectiveness_check = Column(
        DateTime,
        nullable=True,
        comment="Last time effectiveness was evaluated"
    )
    
    # Usage statistics
    usage_stats = Column(
        JSON,
        nullable=True,
        comment="Usage statistics and performance metrics"
    )
    
    # Relationships
    hotel = relationship("Hotel", back_populates="sentiment_configs")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_sentiment_config_hotel_active', 'hotel_id', 'is_active'),
        Index('idx_sentiment_config_hotel_default', 'hotel_id', 'is_default'),
        Index('idx_sentiment_config_version', 'hotel_id', 'version'),
        Index('idx_sentiment_config_activated', 'activated_at'),
    )
    
    def __repr__(self):
        return f"<SentimentConfig(id={self.id}, hotel_id={self.hotel_id}, name={self.config_name}, active={self.is_active})>"
    
    @property
    def negative_sentiment_threshold(self) -> float:
        """Get negative sentiment threshold"""
        return self.thresholds.get("negative_sentiment_threshold", -0.3)
    
    @property
    def critical_sentiment_threshold(self) -> float:
        """Get critical sentiment threshold"""
        return self.thresholds.get("critical_sentiment_threshold", -0.8)
    
    @property
    def response_time_critical(self) -> int:
        """Get critical response time in minutes"""
        return self.response_time_targets.get("critical", 5) if self.response_time_targets else 5
    
    @property
    def notification_channels_critical(self) -> list:
        """Get notification channels for critical alerts"""
        return self.notification_settings.get("critical", ["email", "sms"]) if self.notification_settings else ["email"]
    
    def get_threshold(self, threshold_name: str, default_value: float = 0.0) -> float:
        """Get a specific threshold value"""
        return self.thresholds.get(threshold_name, default_value)
    
    def set_threshold(self, threshold_name: str, value: float) -> None:
        """Set a specific threshold value"""
        if self.thresholds is None:
            self.thresholds = {}
        self.thresholds[threshold_name] = value
    
    def get_notification_channels(self, priority: str) -> list:
        """Get notification channels for a priority level"""
        if not self.notification_settings:
            return ["email"]
        return self.notification_settings.get(priority, ["email"])
    
    def get_response_time_target(self, priority: str) -> int:
        """Get response time target for a priority level"""
        if not self.response_time_targets:
            return 30  # Default 30 minutes
        return self.response_time_targets.get(priority, 30)
    
    def is_rule_enabled(self, rule_name: str) -> bool:
        """Check if a custom rule is enabled"""
        if not self.custom_rules:
            return False
        rule = self.custom_rules.get(rule_name, {})
        return rule.get("enabled", False)
    
    def get_ai_model_parameter(self, parameter_name: str, default_value=None):
        """Get AI model parameter value"""
        if not self.ai_model_settings:
            return default_value
        return self.ai_model_settings.get(parameter_name, default_value)
    
    def update_effectiveness_score(self, score_data: dict) -> None:
        """Update effectiveness score"""
        self.effectiveness_score = score_data
        self.last_effectiveness_check = datetime.utcnow()
    
    def increment_usage_stat(self, stat_name: str, increment: int = 1) -> None:
        """Increment a usage statistic"""
        if self.usage_stats is None:
            self.usage_stats = {}
        
        current_value = self.usage_stats.get(stat_name, 0)
        self.usage_stats[stat_name] = current_value + increment
    
    def get_usage_stat(self, stat_name: str, default_value: int = 0) -> int:
        """Get a usage statistic value"""
        if not self.usage_stats:
            return default_value
        return self.usage_stats.get(stat_name, default_value)


class SentimentConfigHistory(TenantAuditableModel):
    """Model for tracking sentiment configuration changes"""
    
    __tablename__ = "sentiment_config_history"
    
    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique history record identifier"
    )
    
    # Related configuration
    config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sentiment_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Configuration that was changed"
    )
    
    # Change details
    change_type = Column(
        String(50),
        nullable=False,
        comment="Type of change (created, updated, activated, deactivated)"
    )
    
    changed_fields = Column(
        JSON,
        nullable=True,
        comment="Fields that were changed"
    )
    
    old_values = Column(
        JSON,
        nullable=True,
        comment="Previous values of changed fields"
    )
    
    new_values = Column(
        JSON,
        nullable=True,
        comment="New values of changed fields"
    )
    
    change_reason = Column(
        Text,
        nullable=True,
        comment="Reason for the change"
    )
    
    # Change metadata
    changed_by = Column(
        String(100),
        nullable=False,
        comment="User who made the change"
    )
    
    change_source = Column(
        String(50),
        nullable=True,
        comment="Source of the change (manual, automatic, api)"
    )
    
    # Relationships
    config = relationship("SentimentConfig", back_populates="history")
    
    # Indexes
    __table_args__ = (
        Index('idx_config_history_config_date', 'config_id', 'created_at'),
        Index('idx_config_history_change_type', 'change_type', 'created_at'),
    )


# Add relationship to SentimentConfig
SentimentConfig.history = relationship("SentimentConfigHistory", back_populates="config", cascade="all, delete-orphan")
