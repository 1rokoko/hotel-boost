"""
Database models for WhatsApp Hotel Bot
"""

from app.models.base import (
    Base,
    BaseModel,
    TenantBaseModel,
    AuditableModel,
    TenantAuditableModel,
    TimestampMixin,
    UUIDMixin,
    SoftDeleteMixin
)

# Import all models here as they are created
from app.models.hotel import Hotel
from app.models.hotel_settings import HotelSettings
from app.models.guest import Guest
from app.models.trigger import Trigger, TriggerType
from app.models.message import Message, Conversation, MessageType, SentimentType
from app.models.message_queue import MessageQueue, MessageStatus, MessagePriority
from app.models.notification import StaffNotification, NotificationType, NotificationStatus
from app.models.sentiment import SentimentAnalysis, SentimentSummary
from app.models.sentiment_config import SentimentConfig
from app.models.staff_alert import StaffAlert
from app.models.message_template import MessageTemplate, TemplateCategory
from app.models.auto_response_rule import AutoResponseRule, TriggerCondition, ResponseAction
from app.models.admin_user import AdminUser, AdminRole, AdminPermission
from app.models.admin_audit_log import AdminAuditLog, AuditAction, AuditSeverity
from app.models.user import User
from app.models.role import Role, UserRole, UserPermission
from app.models.error_log import ErrorLog, ErrorSummary

__all__ = [
    'Base',
    'BaseModel',
    'TenantBaseModel',
    'AuditableModel',
    'TenantAuditableModel',
    'TimestampMixin',
    'UUIDMixin',
    'SoftDeleteMixin',
    'Hotel',
    'HotelSettings',
    'Guest',
    'Trigger',
    'TriggerType',
    'Message',
    'Conversation',
    'MessageType',
    'SentimentType',
    'MessageQueue',
    'MessageStatus',
    'MessagePriority',
    'StaffNotification',
    'NotificationType',
    'NotificationStatus',
    'SentimentAnalysis',
    'SentimentSummary',
    'SentimentConfig',
    'StaffAlert',
    'MessageTemplate',
    'TemplateCategory',
    'AutoResponseRule',
    'TriggerCondition',
    'ResponseAction',
    'AdminUser',
    'AdminRole',
    'AdminPermission',
    'AdminAuditLog',
    'AuditAction',
    'AuditSeverity',
    'User',
    'Role',
    'UserRole',
    'UserPermission',
    'ErrorLog',
    'ErrorSummary'
]
