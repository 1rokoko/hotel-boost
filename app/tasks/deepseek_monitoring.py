"""
Celery tasks for DeepSeek monitoring and maintenance
"""

from typing import Optional, List
from datetime import datetime, timedelta
import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.database import get_db
from app.services.deepseek_monitoring import get_monitoring_service
from app.models.hotel import Hotel
from app.models.sentiment import SentimentAnalysis, SentimentSummary
from app.core.deepseek_logging import clear_old_deepseek_logs, get_deepseek_metrics

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=2)
def generate_daily_sentiment_summaries_task(
    self,
    date_str: Optional[str] = None
):
    """
    Generate daily sentiment summaries for all hotels
    
    Args:
        date_str: Date in YYYY-MM-DD format (defaults to yesterday)
    """
    try:
        # Parse date or use yesterday
        if date_str:
            summary_date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            summary_date = datetime.utcnow() - timedelta(days=1)
        
        logger.info("Starting daily sentiment summaries generation",
                   date=summary_date.date())
        
        # Get database session
        db: Session = next(get_db())
        
        try:
            # Get all active hotels
            hotels = db.query(Hotel).filter(Hotel.is_active == True).all()
            
            monitoring_service = get_monitoring_service(db)
            
            summaries_generated = 0
            summaries_failed = 0
            
            for hotel in hotels:
                try:
                    summary = await monitoring_service.generate_daily_sentiment_summary(
                        hotel_id=str(hotel.id),
                        date=summary_date
                    )
                    
                    if summary:
                        summaries_generated += 1
                        logger.info("Daily sentiment summary generated",
                                   hotel_id=str(hotel.id),
                                   hotel_name=hotel.name,
                                   date=summary_date.date(),
                                   total_messages=summary.total_messages)
                    else:
                        logger.info("No sentiment data for hotel",
                                   hotel_id=str(hotel.id),
                                   hotel_name=hotel.name,
                                   date=summary_date.date())
                        
                except Exception as e:
                    summaries_failed += 1
                    logger.error("Failed to generate summary for hotel",
                               hotel_id=str(hotel.id),
                               hotel_name=hotel.name,
                               error=str(e))
            
            logger.info("Daily sentiment summaries generation completed",
                       date=summary_date.date(),
                       total_hotels=len(hotels),
                       summaries_generated=summaries_generated,
                       summaries_failed=summaries_failed)
            
            return {
                'date': summary_date.date().isoformat(),
                'total_hotels': len(hotels),
                'summaries_generated': summaries_generated,
                'summaries_failed': summaries_failed
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Daily sentiment summaries generation task failed",
                    date_str=date_str,
                    error=str(e))
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=1)
def cleanup_old_logs_task(
    self,
    max_age_hours: int = 168  # 7 days
):
    """
    Clean up old DeepSeek operation logs
    
    Args:
        max_age_hours: Maximum age of logs to keep in hours
    """
    try:
        logger.info("Starting old logs cleanup",
                   max_age_hours=max_age_hours)
        
        # Clear old logs from memory
        clear_old_deepseek_logs(max_age_hours)
        
        # Get database session
        db: Session = next(get_db())
        
        try:
            # Clean up old sentiment analyses (keep for 30 days)
            cutoff_date = datetime.utcnow() - timedelta(hours=max_age_hours * 4)  # Keep sentiment data longer
            
            old_analyses = db.query(SentimentAnalysis).filter(
                SentimentAnalysis.created_at < cutoff_date
            ).count()
            
            if old_analyses > 0:
                db.query(SentimentAnalysis).filter(
                    SentimentAnalysis.created_at < cutoff_date
                ).delete()
                db.commit()
                
                logger.info("Old sentiment analyses cleaned up",
                           deleted_count=old_analyses,
                           cutoff_date=cutoff_date.date())
            
            # Clean up old sentiment summaries (keep for 1 year)
            summary_cutoff = datetime.utcnow() - timedelta(days=365)
            
            old_summaries = db.query(SentimentSummary).filter(
                SentimentSummary.created_at < summary_cutoff
            ).count()
            
            if old_summaries > 0:
                db.query(SentimentSummary).filter(
                    SentimentSummary.created_at < summary_cutoff
                ).delete()
                db.commit()
                
                logger.info("Old sentiment summaries cleaned up",
                           deleted_count=old_summaries,
                           cutoff_date=summary_cutoff.date())
            
            return {
                'sentiment_analyses_deleted': old_analyses,
                'sentiment_summaries_deleted': old_summaries,
                'cleanup_completed_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Cleanup old logs task failed",
                    max_age_hours=max_age_hours,
                    error=str(e))
        
        # Retry once
        raise self.retry(countdown=300)


@celery_app.task(bind=True, max_retries=2)
def performance_monitoring_task(self):
    """
    Monitor DeepSeek performance and send alerts if needed
    """
    try:
        logger.info("Starting performance monitoring check")
        
        # Get database session
        db: Session = next(get_db())
        
        try:
            monitoring_service = get_monitoring_service(db)
            
            # Check for performance alerts
            alerts = monitoring_service.check_performance_alerts()
            
            if alerts:
                # Log alerts
                for alert in alerts:
                    logger.warning("Performance alert detected",
                                 alert_type=alert['type'],
                                 severity=alert['severity'],
                                 message=alert['message'],
                                 value=alert['value'],
                                 threshold=alert['threshold'])
                
                # TODO: Send notifications to administrators
                # This could integrate with email, Slack, or other notification systems
                
                # For now, just log the summary
                critical_alerts = [a for a in alerts if a['severity'] == 'critical']
                warning_alerts = [a for a in alerts if a['severity'] == 'warning']
                
                logger.warning("Performance monitoring summary",
                             total_alerts=len(alerts),
                             critical_alerts=len(critical_alerts),
                             warning_alerts=len(warning_alerts))
            else:
                logger.info("Performance monitoring check completed - no alerts")
            
            # Get current metrics for logging
            metrics = monitoring_service.get_real_time_metrics()
            global_metrics = get_deepseek_metrics()
            
            logger.info("Performance monitoring metrics",
                       requests_per_minute=metrics['requests_per_minute'],
                       avg_response_time_ms=metrics['average_response_time_ms'],
                       error_rate_percent=metrics['error_rate_percent'],
                       tokens_per_minute=metrics['tokens_per_minute'],
                       total_requests=global_metrics.get('total_requests', 0),
                       successful_requests=global_metrics.get('successful_requests', 0))
            
            return {
                'alerts_found': len(alerts),
                'critical_alerts': len([a for a in alerts if a['severity'] == 'critical']),
                'warning_alerts': len([a for a in alerts if a['severity'] == 'warning']),
                'current_metrics': metrics,
                'check_completed_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Performance monitoring task failed", error=str(e))
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=1)
def generate_weekly_performance_report_task(self):
    """
    Generate weekly performance report for DeepSeek services
    """
    try:
        logger.info("Starting weekly performance report generation")
        
        # Get database session
        db: Session = next(get_db())
        
        try:
            monitoring_service = get_monitoring_service(db)
            
            # Get metrics for the past week
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            # Get all hotels for individual reports
            hotels = db.query(Hotel).filter(Hotel.is_active == True).all()
            
            hotel_reports = []
            for hotel in hotels:
                try:
                    hotel_metrics = await monitoring_service.get_hotel_sentiment_metrics(
                        str(hotel.id),
                        days_back=7
                    )
                    
                    if hotel_metrics:
                        hotel_reports.append({
                            'hotel_id': str(hotel.id),
                            'hotel_name': hotel.name,
                            'metrics': hotel_metrics
                        })
                        
                except Exception as e:
                    logger.error("Failed to get metrics for hotel in weekly report",
                               hotel_id=str(hotel.id),
                               error=str(e))
            
            # Get system-wide metrics
            global_metrics = get_deepseek_metrics()
            current_metrics = monitoring_service.get_real_time_metrics()
            
            # Generate report summary
            report = {
                'report_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': 7
                },
                'system_metrics': {
                    'total_requests': global_metrics.get('total_requests', 0),
                    'successful_requests': global_metrics.get('successful_requests', 0),
                    'failed_requests': global_metrics.get('failed_requests', 0),
                    'total_tokens_used': global_metrics.get('total_tokens_used', 0),
                    'average_response_time': global_metrics.get('average_response_time', 0)
                },
                'hotel_reports': hotel_reports,
                'generated_at': datetime.utcnow().isoformat()
            }
            
            # TODO: Send report via email or store in reporting system
            
            logger.info("Weekly performance report generated",
                       hotels_included=len(hotel_reports),
                       total_requests=global_metrics.get('total_requests', 0))
            
            return report
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Weekly performance report generation failed", error=str(e))
        
        # Retry once
        raise self.retry(countdown=300)


# Periodic task schedules (to be configured in Celery beat)
@celery_app.task
def schedule_daily_tasks():
    """Schedule daily maintenance tasks"""
    
    # Generate daily sentiment summaries (run at 1 AM)
    generate_daily_sentiment_summaries_task.delay()
    
    # Clean up old logs (run at 2 AM)
    cleanup_old_logs_task.delay()


@celery_app.task
def schedule_monitoring_tasks():
    """Schedule monitoring tasks (run every 5 minutes)"""
    
    # Performance monitoring
    performance_monitoring_task.delay()


@celery_app.task
def schedule_weekly_tasks():
    """Schedule weekly tasks (run on Sundays at 3 AM)"""
    
    # Generate weekly performance report
    generate_weekly_performance_report_task.delay()


# Export main components
__all__ = [
    'generate_daily_sentiment_summaries_task',
    'cleanup_old_logs_task',
    'performance_monitoring_task',
    'generate_weekly_performance_report_task',
    'schedule_daily_tasks',
    'schedule_monitoring_tasks',
    'schedule_weekly_tasks'
]
