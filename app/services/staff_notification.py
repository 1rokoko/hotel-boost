"""
Staff notification service for WhatsApp Hotel Bot
"""

from typing import Optional, Dict, Any, List
import uuid

import structlog
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.sentiment import SentimentAnalysis
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.notification import StaffNotification, NotificationType, NotificationStatus
from app.core.config import settings
from datetime import datetime
from enum import Enum


class NotificationChannel(str, Enum):
    """Notification channels"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    SLACK = "slack"
    TEAMS = "teams"


class NotificationResult:
    """Result of notification sending"""

    def __init__(
        self,
        success: bool,
        channels_sent: List[str] = None,
        channels_failed: List[str] = None,
        error_messages: Dict[str, str] = None
    ):
        self.success = success
        self.channels_sent = channels_sent or []
        self.channels_failed = channels_failed or []
        self.error_messages = error_messages or {}
        self.timestamp = datetime.utcnow()

logger = structlog.get_logger(__name__)


class StaffNotificationService:
    """Service for sending notifications to hotel staff"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def send_negative_sentiment_alert(
        self,
        message: Message,
        sentiment_analysis: SentimentAnalysis,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Send alert to hotel staff about negative sentiment
        
        Args:
            message: The message with negative sentiment
            sentiment_analysis: Sentiment analysis results
            correlation_id: Correlation ID for tracking
            
        Returns:
            bool: True if notification was sent successfully
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            # Get hotel and guest information
            hotel = self.db.query(Hotel).filter(Hotel.id == message.hotel_id).first()
            guest = self.db.query(Guest).filter(Guest.id == message.guest_id).first()
            
            if not hotel or not guest:
                logger.error("Hotel or guest not found for notification",
                           message_id=str(message.id),
                           correlation_id=correlation_id)
                return False
            
            # Create notification record
            notification = StaffNotification(
                hotel_id=message.hotel_id,
                guest_id=message.guest_id,
                message_id=message.id,
                notification_type=NotificationType.NEGATIVE_SENTIMENT,
                status=NotificationStatus.PENDING,
                title="Negative Guest Sentiment Detected",
                content=f"Guest {guest.name or guest.phone} sent a message with negative sentiment (score: {sentiment_analysis.sentiment_score:.2f})",
                metadata={
                    'sentiment_type': sentiment_analysis.sentiment_type,
                    'sentiment_score': sentiment_analysis.sentiment_score,
                    'confidence_score': sentiment_analysis.confidence_score,
                    'message_content': message.content[:200],  # Truncate for privacy
                    'correlation_id': correlation_id
                }
            )
            
            self.db.add(notification)
            self.db.commit()
            self.db.refresh(notification)
            
            # TODO: Implement actual notification sending (email, SMS, webhook, etc.)
            # This will be implemented in Task 8 (Sentiment Analysis and Monitoring)
            
            # For now, just mark as sent
            notification.status = NotificationStatus.SENT
            notification.sent_at = sentiment_analysis.created_at
            self.db.commit()
            
            logger.info("Negative sentiment notification created",
                       notification_id=str(notification.id),
                       message_id=str(message.id),
                       sentiment_score=sentiment_analysis.sentiment_score,
                       correlation_id=correlation_id)
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to send negative sentiment alert",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            return False

    async def send_escalation_notification(
        self,
        notification: StaffNotification,
        channels: Optional[List[str]] = None,
        priority: str = 'medium'
    ) -> NotificationResult:
        """
        Send escalation notification through multiple channels

        Args:
            notification: Notification object
            channels: List of channels to use
            priority: Priority level for channel selection

        Returns:
            NotificationResult: Result of notification sending
        """
        try:
            # Default channels based on priority
            if not channels:
                priority_channels = {
                    'low': ['email'],
                    'medium': ['email', 'webhook'],
                    'high': ['email', 'webhook', 'sms'],
                    'critical': ['email', 'webhook', 'sms', 'slack'],
                    'emergency': ['email', 'webhook', 'sms', 'slack', 'teams']
                }
                channels = priority_channels.get(priority, ['email', 'webhook'])

            channels_sent = []
            channels_failed = []
            error_messages = {}

            # Send through each channel
            for channel in channels:
                try:
                    success = await self._send_through_channel(notification, channel)
                    if success:
                        channels_sent.append(channel)
                    else:
                        channels_failed.append(channel)
                        error_messages[channel] = "Failed to send notification"

                except Exception as e:
                    channels_failed.append(channel)
                    error_messages[channel] = str(e)
                    logger.error("Failed to send notification through channel",
                               notification_id=notification.id,
                               channel=channel,
                               error=str(e))

            # Update notification status
            notification.status = NotificationStatus.SENT if channels_sent else NotificationStatus.FAILED
            self.db.commit()

            success = len(channels_sent) > 0

            logger.info("Escalation notification sending completed",
                       notification_id=notification.id,
                       channels_sent=channels_sent,
                       channels_failed=channels_failed,
                       success=success)

            return NotificationResult(
                success=success,
                channels_sent=channels_sent,
                channels_failed=channels_failed,
                error_messages=error_messages
            )

        except Exception as e:
            logger.error("Failed to send escalation notification",
                        notification_id=notification.id,
                        error=str(e))

            return NotificationResult(
                success=False,
                error_messages={'general': str(e)}
            )

    async def _send_through_channel(
        self,
        notification: StaffNotification,
        channel: str
    ) -> bool:
        """
        Send notification through specific channel

        Args:
            notification: Notification object
            channel: Channel to send through

        Returns:
            bool: Success status
        """
        try:
            if channel == NotificationChannel.EMAIL:
                return await self._send_email_notification(notification)
            elif channel == NotificationChannel.WEBHOOK:
                return await self._send_webhook_notification(notification)
            elif channel == NotificationChannel.SMS:
                return await self._send_sms_notification(notification)
            elif channel == NotificationChannel.SLACK:
                return await self._send_slack_notification(notification)
            elif channel == NotificationChannel.TEAMS:
                return await self._send_teams_notification(notification)
            else:
                logger.warning("Unknown notification channel", channel=channel)
                return False

        except Exception as e:
            logger.error("Channel-specific notification failed",
                        notification_id=notification.id,
                        channel=channel,
                        error=str(e))
            return False

    async def _send_email_notification(self, notification: StaffNotification) -> bool:
        """Send email notification"""
        try:
            # Get hotel staff emails
            hotel = self.db.query(Hotel).filter(Hotel.id == notification.hotel_id).first()
            if not hotel:
                return False

            # Build email content
            subject = f"🚨 Guest Escalation Alert - {hotel.name}"
            body = f"""
Dear {hotel.name} Staff,

A guest conversation requires immediate attention:

Notification ID: {notification.id}
Guest ID: {notification.guest_id}
Urgency Level: {notification.urgency_level}/5
Type: {notification.notification_type}

Message:
{notification.message}

Please log into the hotel management system to review and respond to this escalation.

Time: {notification.created_at.strftime('%Y-%m-%d %H:%M:%S')}

Best regards,
Hotel Boost AI System
            """.strip()

            # Here you would integrate with your email service
            # For now, we'll log the email content
            logger.info("Email notification prepared",
                       notification_id=notification.id,
                       hotel_id=notification.hotel_id,
                       subject=subject)

            return True

        except Exception as e:
            logger.error("Failed to send email notification",
                        notification_id=notification.id,
                        error=str(e))
            return False

    async def _send_webhook_notification(self, notification: StaffNotification) -> bool:
        """Send webhook notification"""
        try:
            # Build webhook payload
            payload = {
                'event_type': 'conversation_escalation',
                'hotel_id': str(notification.hotel_id),
                'notification_id': str(notification.id),
                'guest_id': str(notification.guest_id),
                'urgency_level': notification.urgency_level,
                'notification_type': notification.notification_type,
                'message': notification.message,
                'metadata': notification.metadata,
                'created_at': notification.created_at.isoformat(),
                'timestamp': datetime.utcnow().isoformat()
            }

            # Here you would send the webhook
            # For now, we'll log the webhook payload
            logger.info("Webhook notification prepared",
                       notification_id=notification.id,
                       payload=payload)

            return True

        except Exception as e:
            logger.error("Failed to send webhook notification",
                        notification_id=notification.id,
                        error=str(e))
            return False

    async def _send_sms_notification(self, notification: StaffNotification) -> bool:
        """Send SMS notification"""
        try:
            # Build SMS message
            hotel = self.db.query(Hotel).filter(Hotel.id == notification.hotel_id).first()
            message = f"🚨 {hotel.name if hotel else 'Hotel'}: Guest escalation (Urgency: {notification.urgency_level}/5). Check management system."

            # Here you would send the SMS
            # For now, we'll log the SMS content
            logger.info("SMS notification prepared",
                       notification_id=notification.id,
                       message=message)

            return True

        except Exception as e:
            logger.error("Failed to send SMS notification",
                        notification_id=notification.id,
                        error=str(e))
            return False

    async def _send_slack_notification(self, notification: StaffNotification) -> bool:
        """Send Slack notification"""
        try:
            # Build Slack payload
            hotel = self.db.query(Hotel).filter(Hotel.id == notification.hotel_id).first()
            payload = {
                "text": f"🚨 Guest Escalation Alert - {hotel.name if hotel else 'Hotel'}",
                "attachments": [
                    {
                        "color": "danger" if notification.urgency_level >= 4 else "warning",
                        "fields": [
                            {"title": "Urgency", "value": f"{notification.urgency_level}/5", "short": True},
                            {"title": "Type", "value": notification.notification_type, "short": True},
                            {"title": "Message", "value": notification.message, "short": False}
                        ]
                    }
                ]
            }

            # Here you would send to Slack
            # For now, we'll log the Slack payload
            logger.info("Slack notification prepared",
                       notification_id=notification.id,
                       payload=payload)

            return True

        except Exception as e:
            logger.error("Failed to send Slack notification",
                        notification_id=notification.id,
                        error=str(e))
            return False

    async def _send_teams_notification(self, notification: StaffNotification) -> bool:
        """Send Microsoft Teams notification"""
        try:
            # Build Teams payload
            hotel = self.db.query(Hotel).filter(Hotel.id == notification.hotel_id).first()
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "FF0000" if notification.urgency_level >= 4 else "FFA500",
                "summary": f"Guest Escalation Alert - {hotel.name if hotel else 'Hotel'}",
                "sections": [
                    {
                        "activityTitle": f"🚨 Guest Escalation Alert",
                        "activitySubtitle": hotel.name if hotel else "Hotel",
                        "facts": [
                            {"name": "Urgency Level", "value": f"{notification.urgency_level}/5"},
                            {"name": "Type", "value": notification.notification_type}
                        ],
                        "text": notification.message
                    }
                ]
            }

            # Here you would send to Teams
            # For now, we'll log the Teams payload
            logger.info("Teams notification prepared",
                       notification_id=notification.id,
                       payload=payload)

            return True

        except Exception as e:
            logger.error("Failed to send Teams notification",
                        notification_id=notification.id,
                        error=str(e))
            return False


# Export main components
__all__ = [
    'StaffNotificationService',
    'NotificationChannel',
    'NotificationResult'
]
