"""
Notification channels configuration and utilities
"""

from enum import Enum
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class NotificationChannel(Enum):
    """Available notification channels"""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    DASHBOARD = "dashboard"
    PUSH = "push"
    TELEGRAM = "telegram"


class ChannelPriority(Enum):
    """Channel priority levels"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"


class NotificationChannelConfig:
    """Configuration for notification channels"""
    
    def __init__(self):
        # Channel configurations by urgency level
        self.urgency_channels = {
            1: [NotificationChannel.DASHBOARD],  # Minimal urgency
            2: [NotificationChannel.EMAIL, NotificationChannel.DASHBOARD],  # Low urgency
            3: [NotificationChannel.EMAIL, NotificationChannel.WEBHOOK, NotificationChannel.DASHBOARD],  # Medium urgency
            4: [NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.WEBHOOK, NotificationChannel.SLACK],  # High urgency
            5: [NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.WEBHOOK, NotificationChannel.SLACK, NotificationChannel.TEAMS]  # Critical urgency
        }
        
        # Channel priorities
        self.channel_priorities = {
            NotificationChannel.EMAIL: ChannelPriority.PRIMARY,
            NotificationChannel.SMS: ChannelPriority.PRIMARY,
            NotificationChannel.WEBHOOK: ChannelPriority.SECONDARY,
            NotificationChannel.SLACK: ChannelPriority.SECONDARY,
            NotificationChannel.TEAMS: ChannelPriority.SECONDARY,
            NotificationChannel.DASHBOARD: ChannelPriority.FALLBACK,
            NotificationChannel.PUSH: ChannelPriority.SECONDARY,
            NotificationChannel.TELEGRAM: ChannelPriority.SECONDARY
        }
        
        # Channel-specific configurations
        self.channel_configs = {
            NotificationChannel.EMAIL: {
                "retry_attempts": 3,
                "retry_delay_seconds": 60,
                "timeout_seconds": 30,
                "template_type": "html"
            },
            NotificationChannel.SMS: {
                "retry_attempts": 2,
                "retry_delay_seconds": 30,
                "timeout_seconds": 15,
                "max_length": 160
            },
            NotificationChannel.WEBHOOK: {
                "retry_attempts": 3,
                "retry_delay_seconds": 30,
                "timeout_seconds": 10,
                "content_type": "application/json"
            },
            NotificationChannel.SLACK: {
                "retry_attempts": 2,
                "retry_delay_seconds": 15,
                "timeout_seconds": 10,
                "format": "markdown"
            },
            NotificationChannel.TEAMS: {
                "retry_attempts": 2,
                "retry_delay_seconds": 15,
                "timeout_seconds": 10,
                "format": "adaptive_card"
            },
            NotificationChannel.DASHBOARD: {
                "retry_attempts": 1,
                "timeout_seconds": 5,
                "real_time": True
            }
        }


def get_notification_channels(urgency_level: int) -> List[NotificationChannel]:
    """
    Get appropriate notification channels for urgency level
    
    Args:
        urgency_level: Urgency level (1-5)
        
    Returns:
        List of notification channels to use
    """
    config = NotificationChannelConfig()
    
    # Ensure urgency level is within valid range
    urgency_level = max(1, min(5, urgency_level))
    
    channels = config.urgency_channels.get(urgency_level, [NotificationChannel.EMAIL])
    
    logger.debug("Selected notification channels",
                urgency_level=urgency_level,
                channels=[c.value for c in channels])
    
    return channels


def get_channel_config(channel: NotificationChannel) -> Dict[str, Any]:
    """
    Get configuration for a specific notification channel
    
    Args:
        channel: Notification channel
        
    Returns:
        Channel configuration dictionary
    """
    config = NotificationChannelConfig()
    return config.channel_configs.get(channel, {})


def get_channel_priority(channel: NotificationChannel) -> ChannelPriority:
    """
    Get priority level for a notification channel
    
    Args:
        channel: Notification channel
        
    Returns:
        Channel priority level
    """
    config = NotificationChannelConfig()
    return config.channel_priorities.get(channel, ChannelPriority.FALLBACK)


def should_use_channel(
    channel: NotificationChannel,
    urgency_level: int,
    hotel_preferences: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Determine if a channel should be used based on urgency and preferences
    
    Args:
        channel: Notification channel to check
        urgency_level: Urgency level (1-5)
        hotel_preferences: Hotel-specific channel preferences
        
    Returns:
        Whether to use the channel
    """
    # Check if channel is enabled for this urgency level
    available_channels = get_notification_channels(urgency_level)
    if channel not in available_channels:
        return False
    
    # Check hotel preferences if provided
    if hotel_preferences:
        channel_settings = hotel_preferences.get("notification_channels", {})
        channel_enabled = channel_settings.get(channel.value, {}).get("enabled", True)
        if not channel_enabled:
            return False
    
    return True


def get_channel_template(
    channel: NotificationChannel,
    alert_type: str,
    urgency_level: int
) -> Dict[str, str]:
    """
    Get message template for a specific channel and alert type
    
    Args:
        channel: Notification channel
        alert_type: Type of alert
        urgency_level: Urgency level
        
    Returns:
        Template dictionary with subject and body
    """
    templates = {
        NotificationChannel.EMAIL: {
            "negative_sentiment": {
                "subject": "🚨 Guest Sentiment Alert - {hotel_name}",
                "body": """
                <h2>Negative Sentiment Detected</h2>
                <p><strong>Guest:</strong> {guest_name}</p>
                <p><strong>Sentiment Score:</strong> {sentiment_score}</p>
                <p><strong>Message:</strong> {message_content}</p>
                <p><strong>Urgency Level:</strong> {urgency_level}/5</p>
                <p><strong>Response Required By:</strong> {response_deadline}</p>
                <p>Please review and respond promptly.</p>
                """
            },
            "critical_sentiment": {
                "subject": "🚨 CRITICAL: Guest Sentiment Alert - {hotel_name}",
                "body": """
                <h2 style="color: red;">CRITICAL Sentiment Alert</h2>
                <p><strong>Guest:</strong> {guest_name}</p>
                <p><strong>Sentiment Score:</strong> {sentiment_score}</p>
                <p><strong>Message:</strong> {message_content}</p>
                <p><strong>Urgency Level:</strong> {urgency_level}/5</p>
                <p><strong>Response Required By:</strong> {response_deadline}</p>
                <p style="color: red;"><strong>IMMEDIATE ATTENTION REQUIRED</strong></p>
                """
            }
        },
        NotificationChannel.SMS: {
            "negative_sentiment": {
                "subject": "",
                "body": "🚨 {hotel_name}: Negative guest sentiment detected. Score: {sentiment_score}. Check dashboard immediately."
            },
            "critical_sentiment": {
                "subject": "",
                "body": "🚨 CRITICAL: {hotel_name}: Critical guest sentiment. Score: {sentiment_score}. IMMEDIATE ACTION REQUIRED."
            }
        },
        NotificationChannel.SLACK: {
            "negative_sentiment": {
                "subject": "",
                "body": """
                🚨 *Guest Sentiment Alert*
                
                *Hotel:* {hotel_name}
                *Guest:* {guest_name}
                *Sentiment Score:* {sentiment_score}
                *Urgency:* {urgency_level}/5
                *Response Required By:* {response_deadline}
                
                *Message:* {message_content}
                
                Please review and respond promptly.
                """
            }
        },
        NotificationChannel.TEAMS: {
            "negative_sentiment": {
                "subject": "Guest Sentiment Alert",
                "body": {
                    "@type": "MessageCard",
                    "@context": "http://schema.org/extensions",
                    "themeColor": "FF6B35" if urgency_level < 4 else "FF0000",
                    "summary": "Guest Sentiment Alert - {hotel_name}",
                    "sections": [
                        {
                            "activityTitle": "🚨 Guest Sentiment Alert",
                            "activitySubtitle": "{hotel_name}",
                            "facts": [
                                {"name": "Guest", "value": "{guest_name}"},
                                {"name": "Sentiment Score", "value": "{sentiment_score}"},
                                {"name": "Urgency Level", "value": "{urgency_level}/5"},
                                {"name": "Response Required By", "value": "{response_deadline}"}
                            ],
                            "text": "{message_content}"
                        }
                    ]
                }
            }
        }
    }
    
    channel_templates = templates.get(channel, {})
    alert_template = channel_templates.get(alert_type, channel_templates.get("negative_sentiment", {}))
    
    return alert_template


def format_notification_message(
    channel: NotificationChannel,
    template: Dict[str, str],
    context: Dict[str, Any]
) -> Dict[str, str]:
    """
    Format notification message using template and context
    
    Args:
        channel: Notification channel
        template: Message template
        context: Context data for formatting
        
    Returns:
        Formatted message with subject and body
    """
    try:
        formatted_subject = template.get("subject", "").format(**context)
        
        if channel == NotificationChannel.TEAMS and isinstance(template.get("body"), dict):
            # For Teams, format the adaptive card JSON
            import json
            body_template = json.dumps(template["body"])
            formatted_body = body_template.format(**context)
            formatted_body = json.loads(formatted_body)
        else:
            formatted_body = template.get("body", "").format(**context)
        
        return {
            "subject": formatted_subject,
            "body": formatted_body
        }
        
    except KeyError as e:
        logger.error("Missing context key for notification formatting",
                    channel=channel.value,
                    missing_key=str(e),
                    available_keys=list(context.keys()))
        
        # Return fallback message
        return {
            "subject": f"Alert - {context.get('hotel_name', 'Hotel')}",
            "body": f"Alert triggered. Please check the dashboard for details."
        }


def validate_channel_configuration(channel: NotificationChannel, config: Dict[str, Any]) -> bool:
    """
    Validate channel configuration
    
    Args:
        channel: Notification channel
        config: Configuration to validate
        
    Returns:
        Whether configuration is valid
    """
    required_fields = {
        NotificationChannel.EMAIL: ["smtp_host", "smtp_port", "username"],
        NotificationChannel.SMS: ["api_key", "sender_id"],
        NotificationChannel.WEBHOOK: ["url"],
        NotificationChannel.SLACK: ["webhook_url"],
        NotificationChannel.TEAMS: ["webhook_url"],
        NotificationChannel.TELEGRAM: ["bot_token", "chat_id"]
    }
    
    required = required_fields.get(channel, [])
    
    for field in required:
        if field not in config or not config[field]:
            logger.warning("Missing required field for notification channel",
                         channel=channel.value,
                         missing_field=field)
            return False
    
    return True
