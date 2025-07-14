"""
Enhanced Alert Service for WhatsApp Hotel Bot MVP
Handles security incidents, system failures, critical business events, and error monitoring alerts
"""

import asyncio
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from collections import defaultdict
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import security_events_total, external_api_errors
from app.utils.alert_rules import (
    AlertRuleEngine,
    AlertSeverity as RuleAlertSeverity,
    AlertChannel,
    get_alert_rule_engine
)
from app.tasks.send_alerts import (
    send_email_alert,
    send_slack_alert,
    send_webhook_alert,
    send_telegram_alert
)

logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertType(str, Enum):
    """Types of alerts"""
    SECURITY_INCIDENT = "security_incident"
    SYSTEM_FAILURE = "system_failure"
    API_FAILURE = "api_failure"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    BUSINESS_CRITICAL = "business_critical"


class Alert(BaseModel):
    """Alert model"""
    id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = {}
    resolved: bool = False


class AlertService:
    """Service for handling critical alerts"""
    
    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.rule_engine = get_alert_rule_engine()
        self.recent_alerts: Dict[str, datetime] = {}
        self.alert_configs = self._load_alert_configs()
        
    async def send_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        description: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Send a critical alert"""
        
        alert_id = f"{alert_type.value}_{int(datetime.now().timestamp())}"
        
        alert = Alert(
            id=alert_id,
            type=alert_type,
            severity=severity,
            title=title,
            description=description,
            timestamp=datetime.now(timezone.utc),
            source=source,
            metadata=metadata or {}
        )
        
        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # Log alert
        logger.error(
            f"ALERT [{severity.value.upper()}] {title}",
            extra={
                "alert_id": alert_id,
                "alert_type": alert_type.value,
                "severity": severity.value,
                "source": source,
                "metadata": metadata
            }
        )
        
        # Update metrics
        if alert_type == AlertType.SECURITY_INCIDENT:
            security_events_total.labels(
                event_type=metadata.get('event_type', 'unknown'),
                severity=severity.value
            ).inc()
        elif alert_type == AlertType.API_FAILURE:
            external_api_errors.labels(
                api_name=metadata.get('api_name', 'unknown'),
                error_type=metadata.get('error_type', 'unknown')
            ).inc()
        
        # Send notifications based on severity
        await self._send_notifications(alert)
        
        return alert_id

    def _load_alert_configs(self) -> Dict[str, Any]:
        """Load alert configuration from settings"""
        return {
            'email': {
                'enabled': bool(getattr(settings, 'SMTP_HOST', '')),
                'default_recipients': getattr(settings, 'ALERT_EMAIL_RECIPIENTS', []),
                'smtp_host': getattr(settings, 'SMTP_HOST', ''),
                'smtp_port': getattr(settings, 'SMTP_PORT', 587),
                'smtp_username': getattr(settings, 'SMTP_USERNAME', ''),
                'smtp_password': getattr(settings, 'SMTP_PASSWORD', ''),
                'smtp_use_tls': getattr(settings, 'SMTP_USE_TLS', True),
                'from_email': getattr(settings, 'SMTP_FROM_EMAIL', 'alerts@hotel-bot.com')
            },
            'slack': {
                'enabled': bool(getattr(settings, 'SLACK_WEBHOOK_URL', '')),
                'webhook_url': getattr(settings, 'SLACK_WEBHOOK_URL', ''),
                'default_channel': getattr(settings, 'SLACK_ALERT_CHANNEL', '#alerts')
            },
            'webhook': {
                'enabled': bool(getattr(settings, 'ALERT_WEBHOOK_URL', '')),
                'webhook_url': getattr(settings, 'ALERT_WEBHOOK_URL', ''),
                'headers': getattr(settings, 'ALERT_WEBHOOK_HEADERS', {})
            },
            'telegram': {
                'enabled': bool(getattr(settings, 'TELEGRAM_BOT_TOKEN', '')),
                'bot_token': getattr(settings, 'TELEGRAM_BOT_TOKEN', ''),
                'chat_id': getattr(settings, 'TELEGRAM_ALERT_CHAT_ID', '')
            }
        }

    async def process_error_alert_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process error monitoring data and generate alerts based on rules

        Args:
            data: Error data to evaluate for alerts

        Returns:
            List of sent alerts
        """
        # Evaluate rules
        triggered_alerts = self.rule_engine.evaluate_rules(data)

        sent_alerts = []

        for alert in triggered_alerts:
            # Check cooldown
            if self._is_in_cooldown(alert):
                logger.debug(
                    "Alert in cooldown period",
                    rule_name=alert['rule_name'],
                    hotel_id=data.get('hotel_id')
                )
                continue

            # Send alert through configured channels
            alert_results = await self._send_rule_alert(alert)

            # Update cooldown
            self._update_cooldown(alert)

            # Add results to sent alerts
            sent_alerts.append({
                'alert': alert,
                'results': alert_results,
                'sent_at': datetime.utcnow().isoformat()
            })

        return sent_alerts

    async def _send_rule_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send alert through configured channels

        Args:
            alert: Alert to send

        Returns:
            Results from each channel
        """
        results = {}
        channels = alert.get('channels', [])

        # Prepare common alert data
        alert_data = {
            'rule_name': alert['rule_name'],
            'severity': alert['severity'],
            'description': alert['description'],
            'message': alert['message'],
            'timestamp': alert['timestamp'],
            'data': alert.get('data', {})
        }

        # Send through each channel
        for channel in channels:
            try:
                if channel == AlertChannel.EMAIL.value:
                    result = await self._send_email_alert(alert, alert_data)
                elif channel == AlertChannel.SLACK.value:
                    result = await self._send_slack_alert(alert, alert_data)
                elif channel == AlertChannel.WEBHOOK.value:
                    result = await self._send_webhook_alert(alert, alert_data)
                elif channel == AlertChannel.TELEGRAM.value:
                    result = await self._send_telegram_alert(alert, alert_data)
                else:
                    result = {'status': 'unsupported', 'channel': channel}

                results[channel] = result

            except Exception as e:
                logger.error(
                    f"Failed to send alert through {channel}",
                    error=str(e),
                    alert_rule=alert['rule_name'],
                    exc_info=True
                )
                results[channel] = {'status': 'failed', 'error': str(e)}

        return results
    
    async def _send_notifications(self, alert: Alert):
        """Send notifications based on alert severity"""
        
        if alert.severity == AlertSeverity.CRITICAL:
            # Critical alerts - immediate notification
            await self._send_immediate_notification(alert)
            await self._send_email_notification(alert)
            await self._send_webhook_notification(alert)
            
        elif alert.severity == AlertSeverity.HIGH:
            # High priority - email and webhook
            await self._send_email_notification(alert)
            await self._send_webhook_notification(alert)
            
        elif alert.severity == AlertSeverity.MEDIUM:
            # Medium priority - webhook only
            await self._send_webhook_notification(alert)
        
        # Low priority alerts are only logged
    
    async def _send_immediate_notification(self, alert: Alert):
        """Send immediate notification (SMS, Slack, etc.)"""
        try:
            # TODO: Implement immediate notification (SMS, Slack, PagerDuty)
            logger.info(f"Immediate notification sent for alert {alert.id}")
        except Exception as e:
            logger.error(f"Failed to send immediate notification: {str(e)}")
    
    async def _send_email_notification(self, alert: Alert):
        """Send email notification"""
        try:
            # TODO: Implement email notification
            logger.info(f"Email notification sent for alert {alert.id}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
    
    async def _send_webhook_notification(self, alert: Alert):
        """Send webhook notification"""
        try:
            # TODO: Implement webhook notification
            logger.info(f"Webhook notification sent for alert {alert.id}")
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {str(e)}")
    
    async def resolve_alert(self, alert_id: str, resolution_note: str = ""):
        """Mark an alert as resolved"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.metadata["resolved_at"] = datetime.now(timezone.utc).isoformat()
            alert.metadata["resolution_note"] = resolution_note
            
            del self.active_alerts[alert_id]
            
            logger.info(
                f"Alert {alert_id} resolved",
                extra={
                    "alert_id": alert_id,
                    "resolution_note": resolution_note
                }
            )
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get active alerts, optionally filtered by severity"""
        alerts = list(self.active_alerts.values())
        
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history"""
        return sorted(self.alert_history[-limit:], key=lambda x: x.timestamp, reverse=True)

    async def _send_email_alert(
        self,
        alert: Dict[str, Any],
        alert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send email alert for error monitoring"""
        config = self.alert_configs['email']

        if not config['enabled']:
            return {'status': 'disabled', 'reason': 'Email not configured'}

        recipients = config['default_recipients']
        if not recipients:
            return {'status': 'failed', 'reason': 'No recipients configured'}

        subject = f"Alert: {alert['rule_name']}"

        # Queue email task
        task = send_email_alert.delay(
            recipients=recipients,
            subject=subject,
            message=alert['message'],
            alert_data=alert_data,
            severity=alert['severity']
        )

        return {'status': 'queued', 'task_id': task.id}

    async def _send_slack_alert(
        self,
        alert: Dict[str, Any],
        alert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send Slack alert for error monitoring"""
        config = self.alert_configs['slack']

        if not config['enabled']:
            return {'status': 'disabled', 'reason': 'Slack not configured'}

        # Queue Slack task
        task = send_slack_alert.delay(
            webhook_url=config['webhook_url'],
            message=alert['message'],
            alert_data=alert_data,
            severity=alert['severity'],
            channel=config['default_channel']
        )

        return {'status': 'queued', 'task_id': task.id}

    async def _send_webhook_alert(
        self,
        alert: Dict[str, Any],
        alert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send webhook alert for error monitoring"""
        config = self.alert_configs['webhook']

        if not config['enabled']:
            return {'status': 'disabled', 'reason': 'Webhook not configured'}

        # Queue webhook task
        task = send_webhook_alert.delay(
            webhook_url=config['webhook_url'],
            alert_data=alert_data,
            headers=config['headers']
        )

        return {'status': 'queued', 'task_id': task.id}

    async def _send_telegram_alert(
        self,
        alert: Dict[str, Any],
        alert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send Telegram alert for error monitoring"""
        config = self.alert_configs['telegram']

        if not config['enabled']:
            return {'status': 'disabled', 'reason': 'Telegram not configured'}

        # Queue Telegram task
        task = send_telegram_alert.delay(
            bot_token=config['bot_token'],
            chat_id=config['chat_id'],
            message=alert['message'],
            alert_data=alert_data,
            severity=alert['severity']
        )

        return {'status': 'queued', 'task_id': task.id}

    def _is_in_cooldown(self, alert: Dict[str, Any]) -> bool:
        """Check if alert is in cooldown period"""
        cooldown_key = self._get_cooldown_key(alert)

        if cooldown_key not in self.recent_alerts:
            return False

        last_sent = self.recent_alerts[cooldown_key]
        cooldown_minutes = alert.get('cooldown_minutes', 30)
        cooldown_period = timedelta(minutes=cooldown_minutes)

        return datetime.utcnow() - last_sent < cooldown_period

    def _update_cooldown(self, alert: Dict[str, Any]) -> None:
        """Update cooldown timestamp for alert"""
        cooldown_key = self._get_cooldown_key(alert)
        self.recent_alerts[cooldown_key] = datetime.utcnow()

        # Clean up old cooldowns
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.recent_alerts = {
            key: timestamp
            for key, timestamp in self.recent_alerts.items()
            if timestamp > cutoff_time
        }

    def _get_cooldown_key(self, alert: Dict[str, Any]) -> str:
        """Generate cooldown key for alert"""
        rule_name = alert['rule_name']
        hotel_id = alert.get('data', {}).get('hotel_id', 'global')
        return f"{rule_name}_{hotel_id}"


# Global alert service instance
alert_service = AlertService()


# Convenience functions for common alerts

async def alert_security_incident(
    event_type: str,
    description: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Send security incident alert"""
    return await alert_service.send_alert(
        alert_type=AlertType.SECURITY_INCIDENT,
        severity=AlertSeverity.CRITICAL,
        title=f"Security Incident: {event_type}",
        description=description,
        source=source,
        metadata={**(metadata or {}), "event_type": event_type}
    )


async def alert_api_failure(
    api_name: str,
    error_message: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Send API failure alert"""
    severity = AlertSeverity.CRITICAL if api_name in ["green_api", "database"] else AlertSeverity.HIGH
    
    return await alert_service.send_alert(
        alert_type=AlertType.API_FAILURE,
        severity=severity,
        title=f"API Failure: {api_name}",
        description=error_message,
        source=source,
        metadata={**(metadata or {}), "api_name": api_name}
    )


async def alert_system_failure(
    component: str,
    error_message: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Send system failure alert"""
    return await alert_service.send_alert(
        alert_type=AlertType.SYSTEM_FAILURE,
        severity=AlertSeverity.CRITICAL,
        title=f"System Failure: {component}",
        description=error_message,
        source=source,
        metadata={**(metadata or {}), "component": component}
    )


async def alert_performance_degradation(
    metric_name: str,
    current_value: float,
    threshold: float,
    source: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Send performance degradation alert"""
    return await alert_service.send_alert(
        alert_type=AlertType.PERFORMANCE_DEGRADATION,
        severity=AlertSeverity.HIGH,
        title=f"Performance Degradation: {metric_name}",
        description=f"{metric_name} is {current_value}, exceeding threshold of {threshold}",
        source=source,
        metadata={
            **(metadata or {}),
            "metric_name": metric_name,
            "current_value": current_value,
            "threshold": threshold
        }
    )


async def alert_business_critical(
    event: str,
    description: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Send business critical alert"""
    return await alert_service.send_alert(
        alert_type=AlertType.BUSINESS_CRITICAL,
        severity=AlertSeverity.HIGH,
        title=f"Business Critical: {event}",
        description=description,
        source=source,
        metadata={**(metadata or {}), "event": event}
    )
