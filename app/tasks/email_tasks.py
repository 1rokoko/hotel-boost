"""
Email task implementations for WhatsApp Hotel Bot
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import structlog

from app.tasks.base import email_task, maintenance_task
from app.core.config import settings
from app.models.hotel import Hotel
from app.models.notification import StaffNotification, NotificationStatus
from app.models.sentiment import SentimentSummary
from app.database import get_async_session
from app.utils.task_logger import task_logger

logger = structlog.get_logger(__name__)


@email_task(bind=True)
def send_email(self, to_email: str, subject: str, body: str, 
               html_body: Optional[str] = None, 
               attachments: Optional[List[Dict[str, Any]]] = None,
               hotel_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Send email notification
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: HTML body (optional)
        attachments: List of attachments (optional)
        hotel_id: Hotel ID for context (optional)
    
    Returns:
        Dict with send status and details
    """
    task_logger.log_task_custom(
        task_id=self.request.id,
        task_name=self.name,
        event="email_send_start",
        data={
            "to_email": to_email,
            "subject": subject,
            "hotel_id": hotel_id,
            "has_html": bool(html_body),
            "attachment_count": len(attachments) if attachments else 0
        }
    )
    
    if not self.validate_email_params(to_email=to_email, subject=subject):
        raise ValueError("Invalid email parameters")
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = settings.NOTIFICATION_EMAIL_USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add plain text part
        text_part = MIMEText(body, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # Add HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
        
        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attachment["filename"]}'
                )
                msg.attach(part)
        
        # Send email
        with smtplib.SMTP(settings.NOTIFICATION_EMAIL_SMTP_HOST, 
                         settings.NOTIFICATION_EMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(settings.NOTIFICATION_EMAIL_USERNAME, 
                        settings.NOTIFICATION_EMAIL_PASSWORD)
            server.send_message(msg)
        
        result = {
            "status": "sent",
            "to_email": to_email,
            "subject": subject,
            "sent_at": datetime.utcnow().isoformat(),
            "message_id": msg.get('Message-ID')
        }
        
        task_logger.log_task_custom(
            task_id=self.request.id,
            task_name=self.name,
            event="email_send_success",
            data=result
        )
        
        logger.info("Email sent successfully", **result)
        return result
        
    except Exception as exc:
        error_details = {
            "error": str(exc),
            "to_email": to_email,
            "subject": subject,
            "hotel_id": hotel_id
        }
        
        task_logger.log_task_custom(
            task_id=self.request.id,
            task_name=self.name,
            event="email_send_error",
            data=error_details
        )
        
        logger.error("Failed to send email", **error_details)
        raise


@email_task(bind=True)
def send_staff_notification_email(self, notification_id: int, 
                                 hotel_id: int) -> Dict[str, Any]:
    """
    Send staff notification email for negative sentiment alerts
    
    Args:
        notification_id: Staff notification ID
        hotel_id: Hotel ID
    
    Returns:
        Dict with send status
    """
    task_logger.log_task_custom(
        task_id=self.request.id,
        task_name=self.name,
        event="staff_notification_start",
        data={"notification_id": notification_id, "hotel_id": hotel_id}
    )
    
    try:
        async with get_async_session() as session:
            # Get notification details
            notification = await session.get(StaffNotification, notification_id)
            if not notification:
                raise ValueError(f"Notification {notification_id} not found")
            
            # Get hotel details
            hotel = await session.get(Hotel, hotel_id)
            if not hotel:
                raise ValueError(f"Hotel {hotel_id} not found")
            
            # Prepare email content
            subject = f"🚨 Negative Guest Feedback Alert - {hotel.name}"
            
            body = f"""
Dear {hotel.name} Team,

We've detected negative sentiment in a guest conversation that requires your immediate attention.

Guest Details:
- Phone: {notification.guest.phone if notification.guest else 'Unknown'}
- Conversation ID: {notification.conversation_id}
- Sentiment Score: {notification.sentiment_score}

Message Content:
{notification.message_content[:500]}{'...' if len(notification.message_content) > 500 else ''}

Please review this conversation and take appropriate action to address the guest's concerns.

Time: {notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

Best regards,
WhatsApp Hotel Bot System
            """
            
            html_body = f"""
<html>
<body>
    <h2>🚨 Negative Guest Feedback Alert</h2>
    <h3>Hotel: {hotel.name}</h3>
    
    <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 10px 0;">
        <strong>Guest Details:</strong><br>
        Phone: {notification.guest.phone if notification.guest else 'Unknown'}<br>
        Conversation ID: {notification.conversation_id}<br>
        Sentiment Score: <span style="color: red;">{notification.sentiment_score}</span>
    </div>
    
    <div style="background-color: #f8f9fa; border-left: 4px solid #dc3545; padding: 15px; margin: 10px 0;">
        <strong>Message Content:</strong><br>
        <em>{notification.message_content[:500]}{'...' if len(notification.message_content) > 500 else ''}</em>
    </div>
    
    <p><strong>Action Required:</strong> Please review this conversation and take appropriate action to address the guest's concerns.</p>
    
    <p><small>Time: {notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</small></p>
    
    <hr>
    <p><small>This is an automated message from the WhatsApp Hotel Bot System.</small></p>
</body>
</html>
            """
            
            # Send email to hotel staff
            staff_emails = hotel.staff_notification_emails or []
            if not staff_emails:
                logger.warning("No staff emails configured for hotel", hotel_id=hotel_id)
                return {"status": "skipped", "reason": "no_staff_emails"}
            
            results = []
            for email in staff_emails:
                try:
                    result = await send_email.apply_async(
                        args=[email, subject, body],
                        kwargs={"html_body": html_body, "hotel_id": hotel_id}
                    ).get()
                    results.append({"email": email, "status": "sent", "result": result})
                except Exception as e:
                    results.append({"email": email, "status": "failed", "error": str(e)})
            
            # Update notification status
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            await session.commit()
            
            task_logger.log_task_custom(
                task_id=self.request.id,
                task_name=self.name,
                event="staff_notification_complete",
                data={
                    "notification_id": notification_id,
                    "hotel_id": hotel_id,
                    "emails_sent": len([r for r in results if r["status"] == "sent"]),
                    "emails_failed": len([r for r in results if r["status"] == "failed"])
                }
            )
            
            return {
                "status": "completed",
                "notification_id": notification_id,
                "results": results
            }
            
    except Exception as exc:
        logger.error("Failed to send staff notification email", 
                    notification_id=notification_id,
                    hotel_id=hotel_id,
                    error=str(exc))
        raise


@email_task(bind=True)
def send_daily_report(self, hotel_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Send daily sentiment and activity report
    
    Args:
        hotel_id: Specific hotel ID, or None for all hotels
    
    Returns:
        Dict with report send status
    """
    task_logger.log_task_custom(
        task_id=self.request.id,
        task_name=self.name,
        event="daily_report_start",
        data={"hotel_id": hotel_id}
    )
    
    try:
        async with get_async_session() as session:
            # Get hotels to report on
            if hotel_id:
                hotels = [await session.get(Hotel, hotel_id)]
            else:
                result = await session.execute("SELECT * FROM hotels WHERE is_active = true")
                hotels = result.fetchall()
            
            reports_sent = 0
            for hotel in hotels:
                if not hotel:
                    continue
                
                # Generate report for this hotel
                yesterday = datetime.utcnow() - timedelta(days=1)
                
                # Get sentiment summary for yesterday
                # This would typically query the sentiment analysis results
                # For now, we'll create a placeholder report
                
                subject = f"Daily Report - {hotel.name} - {yesterday.strftime('%Y-%m-%d')}"
                
                body = f"""
Daily Activity Report for {hotel.name}
Date: {yesterday.strftime('%Y-%m-%d')}

Summary:
- Total conversations: [To be implemented]
- Positive sentiment: [To be implemented]
- Negative sentiment: [To be implemented]
- Staff alerts sent: [To be implemented]

This is a placeholder report. Full implementation requires sentiment analytics.

Best regards,
WhatsApp Hotel Bot System
                """
                
                # Send to hotel admin emails
                admin_emails = hotel.admin_notification_emails or []
                for email in admin_emails:
                    try:
                        await send_email.apply_async(
                            args=[email, subject, body],
                            kwargs={"hotel_id": hotel.id}
                        )
                        reports_sent += 1
                    except Exception as e:
                        logger.error("Failed to send daily report", 
                                   hotel_id=hotel.id,
                                   email=email,
                                   error=str(e))
            
            result = {
                "status": "completed",
                "reports_sent": reports_sent,
                "date": yesterday.strftime('%Y-%m-%d')
            }
            
            task_logger.log_task_custom(
                task_id=self.request.id,
                task_name=self.name,
                event="daily_report_complete",
                data=result
            )
            
            return result
            
    except Exception as exc:
        logger.error("Failed to send daily reports", error=str(exc))
        raise


@maintenance_task(bind=True)
def cleanup_old_email_logs(self, days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old email logs and notifications
    
    Args:
        days_to_keep: Number of days to keep logs
    
    Returns:
        Dict with cleanup results
    """
    task_logger.log_task_custom(
        task_id=self.request.id,
        task_name=self.name,
        event="email_cleanup_start",
        data={"days_to_keep": days_to_keep}
    )
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        async with get_async_session() as session:
            # Clean up old notifications
            result = await session.execute(
                "DELETE FROM staff_notifications WHERE created_at < :cutoff_date",
                {"cutoff_date": cutoff_date}
            )
            deleted_notifications = result.rowcount
            
            await session.commit()
            
            cleanup_result = {
                "status": "completed",
                "deleted_notifications": deleted_notifications,
                "cutoff_date": cutoff_date.isoformat(),
                "days_kept": days_to_keep
            }
            
            task_logger.log_task_custom(
                task_id=self.request.id,
                task_name=self.name,
                event="email_cleanup_complete",
                data=cleanup_result
            )
            
            logger.info("Email cleanup completed", **cleanup_result)
            return cleanup_result
            
    except Exception as exc:
        logger.error("Failed to cleanup email logs", error=str(exc))
        raise
