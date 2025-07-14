"""
Celery tasks for sending staff alerts and notifications
"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app, high_priority_task
from app.database import get_db
from app.models.message import Message
from app.models.sentiment import SentimentAnalysis
from app.models.staff_alert import StaffAlert, AlertType, AlertStatus, AlertPriority
from app.services.staff_notification import StaffNotificationService
from app.utils.notification_channels import get_notification_channels

logger = structlog.get_logger(__name__)


@high_priority_task(bind=True, max_retries=3)
def send_staff_alert_task(
    self,
    message_id: str,
    sentiment_type: str,
    sentiment_score: float,
    urgency_level: int = 3,
    correlation_id: Optional[str] = None
):
    """
    Send staff alert for negative sentiment
    
    Args:
        message_id: ID of the message with negative sentiment
        sentiment_type: Type of sentiment detected
        sentiment_score: Sentiment score
        urgency_level: Urgency level (1-5)
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        logger.info("Starting staff alert task",
                   message_id=message_id,
                   sentiment_type=sentiment_type,
                   sentiment_score=sentiment_score,
                   urgency_level=urgency_level,
                   correlation_id=correlation_id)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get message and related data
            message = db.query(Message).filter(Message.id == message_id).first()
            if not message:
                logger.error("Message not found for staff alert",
                           message_id=message_id,
                           correlation_id=correlation_id)
                return
            
            # Get sentiment analysis
            sentiment_analysis = db.query(SentimentAnalysis).filter(
                SentimentAnalysis.message_id == message_id
            ).first()
            
            # Create staff alert
            alert = await _create_staff_alert(
                db=db,
                message=message,
                sentiment_analysis=sentiment_analysis,
                sentiment_type=sentiment_type,
                sentiment_score=sentiment_score,
                urgency_level=urgency_level,
                correlation_id=correlation_id
            )
            
            # Send notifications through appropriate channels
            notification_service = StaffNotificationService(db)
            channels = get_notification_channels(urgency_level)
            
            for channel in channels:
                try:
                    await notification_service.send_alert_notification(
                        alert=alert,
                        channel=channel,
                        correlation_id=correlation_id
                    )
                except Exception as e:
                    logger.error("Failed to send notification through channel",
                               alert_id=str(alert.id),
                               channel=channel,
                               error=str(e),
                               correlation_id=correlation_id)
            
            logger.info("Staff alert task completed",
                       alert_id=str(alert.id),
                       message_id=message_id,
                       channels_used=len(channels),
                       correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Staff alert task failed",
                    message_id=message_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2)
def escalate_alert_task(
    self,
    alert_id: str,
    escalation_level: str,
    reason: str,
    escalated_by: Optional[str] = None,
    correlation_id: Optional[str] = None
):
    """
    Escalate a staff alert to higher management
    
    Args:
        alert_id: ID of the alert to escalate
        escalation_level: Level to escalate to (supervisor, manager, director)
        reason: Reason for escalation
        escalated_by: Person initiating escalation
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        logger.info("Starting alert escalation task",
                   alert_id=alert_id,
                   escalation_level=escalation_level,
                   correlation_id=correlation_id)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get alert
            alert = db.query(StaffAlert).filter(StaffAlert.id == alert_id).first()
            if not alert:
                logger.error("Alert not found for escalation",
                           alert_id=alert_id,
                           correlation_id=correlation_id)
                return
            
            # Create escalation record
            from app.models.staff_alert import AlertEscalation
            escalation = AlertEscalation(
                hotel_id=alert.hotel_id,
                alert_id=alert.id,
                escalation_level=escalation_level,
                escalated_to=_get_escalation_target(escalation_level, alert.hotel_id),
                escalated_by=escalated_by,
                reason=reason,
                status="pending"
            )
            
            db.add(escalation)
            
            # Update alert status
            alert.status = AlertStatus.ESCALATED.value
            alert.escalation_history = alert.escalation_history or []
            alert.escalation_history.append({
                "escalation_id": str(escalation.id),
                "level": escalation_level,
                "timestamp": datetime.utcnow().isoformat(),
                "reason": reason
            })
            
            db.commit()
            db.refresh(escalation)
            
            # Send escalation notifications
            notification_service = StaffNotificationService(db)
            await notification_service.send_escalation_notification(
                escalation=escalation,
                correlation_id=correlation_id
            )
            
            logger.info("Alert escalation completed",
                       alert_id=alert_id,
                       escalation_id=str(escalation.id),
                       escalation_level=escalation_level,
                       correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Alert escalation task failed",
                    alert_id=alert_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        # Retry with exponential backoff
        raise self.retry(countdown=120 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=1)
def check_overdue_alerts_task(
    self,
    correlation_id: Optional[str] = None
):
    """
    Check for overdue alerts and escalate if necessary
    
    Args:
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        logger.info("Starting overdue alerts check",
                   correlation_id=correlation_id)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Find overdue alerts
            current_time = datetime.utcnow()
            overdue_alerts = db.query(StaffAlert).filter(
                StaffAlert.status == AlertStatus.PENDING.value,
                StaffAlert.response_required_by < current_time
            ).all()
            
            escalated_count = 0
            
            for alert in overdue_alerts:
                try:
                    # Auto-escalate overdue alerts
                    escalate_alert_task.delay(
                        alert_id=str(alert.id),
                        escalation_level="supervisor",
                        reason="Alert overdue - automatic escalation",
                        escalated_by="system",
                        correlation_id=correlation_id
                    )
                    escalated_count += 1
                    
                except Exception as e:
                    logger.error("Failed to escalate overdue alert",
                               alert_id=str(alert.id),
                               error=str(e),
                               correlation_id=correlation_id)
            
            logger.info("Overdue alerts check completed",
                       total_overdue=len(overdue_alerts),
                       escalated_count=escalated_count,
                       correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Overdue alerts check failed",
                    error=str(e),
                    correlation_id=correlation_id)
        raise


@celery_app.task(bind=True, max_retries=1)
def send_daily_alert_summary_task(
    self,
    hotel_id: str,
    date: Optional[str] = None,
    correlation_id: Optional[str] = None
):
    """
    Send daily summary of alerts to hotel management
    
    Args:
        hotel_id: Hotel ID
        date: Date for summary (YYYY-MM-DD format)
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        from datetime import date as date_obj
        
        if date:
            summary_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            summary_date = date_obj.today()
        
        logger.info("Starting daily alert summary",
                   hotel_id=hotel_id,
                   date=summary_date.isoformat(),
                   correlation_id=correlation_id)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get alerts for the day
            start_time = datetime.combine(summary_date, datetime.min.time())
            end_time = start_time + timedelta(days=1)
            
            alerts = db.query(StaffAlert).filter(
                StaffAlert.hotel_id == hotel_id,
                StaffAlert.created_at >= start_time,
                StaffAlert.created_at < end_time
            ).all()
            
            # Generate summary
            summary = _generate_alert_summary(alerts, summary_date)
            
            # Send summary notification
            notification_service = StaffNotificationService(db)
            await notification_service.send_daily_summary(
                hotel_id=hotel_id,
                summary=summary,
                correlation_id=correlation_id
            )
            
            logger.info("Daily alert summary sent",
                       hotel_id=hotel_id,
                       date=summary_date.isoformat(),
                       total_alerts=len(alerts),
                       correlation_id=correlation_id)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Daily alert summary failed",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise


async def _create_staff_alert(
    db: Session,
    message: Message,
    sentiment_analysis: Optional[SentimentAnalysis],
    sentiment_type: str,
    sentiment_score: float,
    urgency_level: int,
    correlation_id: str
) -> StaffAlert:
    """Create a staff alert record"""
    
    # Determine alert type
    if sentiment_score < -0.8:
        alert_type = AlertType.CRITICAL_SENTIMENT
    elif sentiment_score < -0.5:
        alert_type = AlertType.NEGATIVE_SENTIMENT
    else:
        alert_type = AlertType.NEGATIVE_SENTIMENT
    
    # Calculate response deadline
    response_deadline = datetime.utcnow() + timedelta(
        minutes=_get_response_time_minutes(urgency_level)
    )
    
    # Create alert
    alert = StaffAlert(
        hotel_id=message.hotel_id,
        alert_type=alert_type.value,
        priority=_get_priority_from_urgency(urgency_level),
        message_id=message.id,
        guest_id=message.guest_id,
        conversation_id=message.conversation_id,
        sentiment_analysis_id=sentiment_analysis.id if sentiment_analysis else None,
        title=f"Negative sentiment detected - Guest {message.guest_id}",
        description=f"Guest message with sentiment score {sentiment_score:.2f} requires attention",
        sentiment_score=sentiment_score,
        sentiment_type=sentiment_type,
        urgency_level=urgency_level,
        response_required_by=response_deadline,
        correlation_id=correlation_id,
        context_data={
            "message_content": message.content[:200],  # First 200 chars
            "sentiment_analysis": {
                "score": sentiment_score,
                "type": sentiment_type,
                "confidence": sentiment_analysis.confidence_score if sentiment_analysis else None
            }
        }
    )
    
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    return alert


def _get_escalation_target(escalation_level: str, hotel_id: str) -> str:
    """Get escalation target based on level and hotel"""
    # This would typically look up hotel-specific escalation contacts
    targets = {
        "supervisor": f"supervisor@hotel-{hotel_id}",
        "manager": f"manager@hotel-{hotel_id}",
        "director": f"director@hotel-{hotel_id}"
    }
    return targets.get(escalation_level, "manager@hotel")


def _get_response_time_minutes(urgency_level: int) -> int:
    """Get response time in minutes based on urgency level"""
    times = {1: 120, 2: 60, 3: 30, 4: 15, 5: 5}
    return times.get(urgency_level, 30)


def _get_priority_from_urgency(urgency_level: int) -> str:
    """Convert urgency level to priority string"""
    if urgency_level >= 5:
        return AlertPriority.URGENT.name.lower()
    elif urgency_level >= 4:
        return AlertPriority.CRITICAL.name.lower()
    elif urgency_level >= 3:
        return AlertPriority.HIGH.name.lower()
    elif urgency_level >= 2:
        return AlertPriority.MEDIUM.name.lower()
    else:
        return AlertPriority.LOW.name.lower()


def _generate_alert_summary(alerts: List[StaffAlert], date) -> Dict[str, Any]:
    """Generate daily alert summary"""
    total_alerts = len(alerts)
    
    # Count by priority
    priority_counts = {}
    for alert in alerts:
        priority_counts[alert.priority] = priority_counts.get(alert.priority, 0) + 1
    
    # Count by status
    status_counts = {}
    for alert in alerts:
        status_counts[alert.status] = status_counts.get(alert.status, 0) + 1
    
    # Calculate average response time
    response_times = [a.response_time_minutes for a in alerts if a.response_time_minutes]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    return {
        "date": date.isoformat(),
        "total_alerts": total_alerts,
        "priority_breakdown": priority_counts,
        "status_breakdown": status_counts,
        "average_response_time_minutes": round(avg_response_time, 1),
        "overdue_alerts": len([a for a in alerts if a.is_overdue]),
        "escalated_alerts": len([a for a in alerts if a.status == AlertStatus.ESCALATED.value])
    }
