"""
Celery tasks for sending alerts and notifications.

This module contains background tasks for sending various types of alerts
through different channels (email, Slack, SMS, etc.).
"""

import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional
import requests

from celery import current_task
from celery.exceptions import Retry

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger
from app.tasks.base import BaseTask
from app.utils.alert_rules import AlertSeverity, AlertChannel

logger = get_logger(__name__)


@celery_app.task(bind=True, base=BaseTask)
def send_email_alert(
    self,
    recipients: List[str],
    subject: str,
    message: str,
    alert_data: Dict[str, Any],
    severity: str = "medium"
) -> Dict[str, Any]:
    """
    Send email alert
    
    Args:
        recipients: List of email addresses
        subject: Email subject
        message: Alert message
        alert_data: Additional alert data
        severity: Alert severity level
        
    Returns:
        Result dictionary
    """
    try:
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[{severity.upper()}] {subject}"
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = ', '.join(recipients)
        
        # Create HTML content
        html_content = _create_email_html(message, alert_data, severity)
        
        # Attach both plain text and HTML
        text_part = MIMEText(message, 'plain')
        html_part = MIMEText(html_content, 'html')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            
            server.send_message(msg)
            
        logger.info(
            "Email alert sent successfully",
            recipients=recipients,
            subject=subject,
            severity=severity,
            task_id=current_task.request.id
        )
        
        return {
            'status': 'success',
            'recipients': recipients,
            'subject': subject,
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to send email alert",
            error=str(e),
            recipients=recipients,
            subject=subject,
            task_id=current_task.request.id,
            exc_info=True
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'failed',
            'error': str(e),
            'recipients': recipients,
            'subject': subject
        }


@celery_app.task(bind=True, base=BaseTask)
def send_slack_alert(
    self,
    webhook_url: str,
    message: str,
    alert_data: Dict[str, Any],
    severity: str = "medium",
    channel: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send Slack alert
    
    Args:
        webhook_url: Slack webhook URL
        message: Alert message
        alert_data: Additional alert data
        severity: Alert severity level
        channel: Slack channel (optional)
        
    Returns:
        Result dictionary
    """
    try:
        # Create Slack payload
        payload = _create_slack_payload(message, alert_data, severity, channel)
        
        # Send to Slack
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        
        logger.info(
            "Slack alert sent successfully",
            webhook_url=webhook_url[:50] + "...",
            severity=severity,
            channel=channel,
            task_id=current_task.request.id
        )
        
        return {
            'status': 'success',
            'channel': channel,
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to send Slack alert",
            error=str(e),
            webhook_url=webhook_url[:50] + "...",
            severity=severity,
            task_id=current_task.request.id,
            exc_info=True
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'failed',
            'error': str(e),
            'channel': channel
        }


@celery_app.task(bind=True, base=BaseTask)
def send_webhook_alert(
    self,
    webhook_url: str,
    alert_data: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Send webhook alert
    
    Args:
        webhook_url: Webhook URL
        alert_data: Alert data to send
        headers: Optional HTTP headers
        
    Returns:
        Result dictionary
    """
    try:
        # Prepare headers
        request_headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'WhatsApp-Hotel-Bot/{settings.VERSION}'
        }
        if headers:
            request_headers.update(headers)
            
        # Send webhook
        response = requests.post(
            webhook_url,
            json=alert_data,
            headers=request_headers,
            timeout=30
        )
        response.raise_for_status()
        
        logger.info(
            "Webhook alert sent successfully",
            webhook_url=webhook_url,
            status_code=response.status_code,
            task_id=current_task.request.id
        )
        
        return {
            'status': 'success',
            'webhook_url': webhook_url,
            'status_code': response.status_code,
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to send webhook alert",
            error=str(e),
            webhook_url=webhook_url,
            task_id=current_task.request.id,
            exc_info=True
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'failed',
            'error': str(e),
            'webhook_url': webhook_url
        }


@celery_app.task(bind=True, base=BaseTask)
def send_telegram_alert(
    self,
    bot_token: str,
    chat_id: str,
    message: str,
    alert_data: Dict[str, Any],
    severity: str = "medium"
) -> Dict[str, Any]:
    """
    Send Telegram alert
    
    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        message: Alert message
        alert_data: Additional alert data
        severity: Alert severity level
        
    Returns:
        Result dictionary
    """
    try:
        # Format message for Telegram
        formatted_message = _format_telegram_message(message, alert_data, severity)
        
        # Send to Telegram
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': formatted_message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        logger.info(
            "Telegram alert sent successfully",
            chat_id=chat_id,
            severity=severity,
            task_id=current_task.request.id
        )
        
        return {
            'status': 'success',
            'chat_id': chat_id,
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to send Telegram alert",
            error=str(e),
            chat_id=chat_id,
            severity=severity,
            task_id=current_task.request.id,
            exc_info=True
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'failed',
            'error': str(e),
            'chat_id': chat_id
        }


def _create_email_html(message: str, alert_data: Dict[str, Any], severity: str) -> str:
    """Create HTML content for email alert"""
    severity_colors = {
        'low': '#28a745',
        'medium': '#ffc107',
        'high': '#fd7e14',
        'critical': '#dc3545'
    }
    
    color = severity_colors.get(severity, '#6c757d')
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <div style="background-color: {color}; color: white; padding: 15px; border-radius: 5px 5px 0 0;">
                <h2 style="margin: 0;">Alert: {severity.upper()}</h2>
            </div>
            <div style="border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px;">
                <h3>Message</h3>
                <p>{message}</p>
                
                <h3>Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
    """
    
    for key, value in alert_data.items():
        if key not in ['data', 'timestamp']:
            html += f"""
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">{key.replace('_', ' ').title()}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{value}</td>
                    </tr>
            """
    
    html += """
                </table>
                
                <p style="margin-top: 20px; font-size: 12px; color: #666;">
                    This alert was generated by WhatsApp Hotel Bot monitoring system.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def _create_slack_payload(
    message: str,
    alert_data: Dict[str, Any],
    severity: str,
    channel: Optional[str] = None
) -> Dict[str, Any]:
    """Create Slack message payload"""
    severity_colors = {
        'low': 'good',
        'medium': 'warning',
        'high': 'danger',
        'critical': 'danger'
    }
    
    color = severity_colors.get(severity, 'warning')
    
    payload = {
        'text': f"Alert: {severity.upper()}",
        'attachments': [
            {
                'color': color,
                'title': 'Error Monitoring Alert',
                'text': message,
                'fields': [
                    {
                        'title': key.replace('_', ' ').title(),
                        'value': str(value),
                        'short': True
                    }
                    for key, value in alert_data.items()
                    if key not in ['data', 'timestamp'] and len(str(value)) < 100
                ],
                'footer': 'WhatsApp Hotel Bot',
                'ts': int(datetime.utcnow().timestamp())
            }
        ]
    }
    
    if channel:
        payload['channel'] = channel
        
    return payload


def _format_telegram_message(
    message: str,
    alert_data: Dict[str, Any],
    severity: str
) -> str:
    """Format message for Telegram"""
    severity_emojis = {
        'low': '🟢',
        'medium': '🟡',
        'high': '🟠',
        'critical': '🔴'
    }
    
    emoji = severity_emojis.get(severity, '⚪')
    
    formatted = f"{emoji} *Alert: {severity.upper()}*\n\n"
    formatted += f"{message}\n\n"
    
    # Add key details
    for key, value in alert_data.items():
        if key not in ['data', 'timestamp'] and len(str(value)) < 100:
            formatted += f"*{key.replace('_', ' ').title()}:* {value}\n"
    
    formatted += f"\n_Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC_"
    
    return formatted
