"""
Error monitoring service for real-time error tracking and alerting.

This service provides comprehensive error monitoring capabilities including
real-time tracking, alerting, and analysis of application errors.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.config import settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.error_log import ErrorLog, ErrorSummary
from app.utils.error_tracker import ErrorTracker, ErrorAnalyzer
from app.exceptions.custom_exceptions import BaseCustomException

logger = get_logger(__name__)


class ErrorMonitor:
    """Real-time error monitoring service"""
    
    def __init__(self):
        self.alert_thresholds = {
            'error_rate_per_hour': 100,
            'critical_errors_per_hour': 10,
            'unique_errors_per_hour': 20,
            'spike_threshold_multiplier': 3.0
        }
        self.recent_alerts: Set[str] = set()
        self.alert_cooldown = 300  # 5 minutes
        
    async def monitor_errors(self) -> None:
        """Main monitoring loop"""
        logger.info("Starting error monitoring service")
        
        while True:
            try:
                await self._check_error_rates()
                await self._check_error_spikes()
                await self._check_critical_errors()
                await self._cleanup_old_alerts()
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)
                
    async def _check_error_rates(self) -> None:
        """Check if error rates exceed thresholds"""
        db = next(get_db())
        try:
            tracker = ErrorTracker(db)
            
            # Check overall error rate
            stats = tracker.get_error_statistics(
                start_time=datetime.utcnow() - timedelta(hours=1)
            )
            
            if stats['error_rate'] > self.alert_thresholds['error_rate_per_hour']:
                await self._send_alert(
                    alert_type="high_error_rate",
                    message=f"High error rate detected: {stats['error_rate']} errors/hour",
                    details=stats,
                    severity="warning"
                )
                
            # Check per-hotel error rates
            hotels_with_errors = db.query(ErrorLog.hotel_id).filter(
                ErrorLog.hotel_id.isnot(None),
                ErrorLog.timestamp >= datetime.utcnow() - timedelta(hours=1)
            ).distinct().all()
            
            for (hotel_id,) in hotels_with_errors:
                hotel_stats = tracker.get_error_statistics(
                    hotel_id=hotel_id,
                    start_time=datetime.utcnow() - timedelta(hours=1)
                )
                
                if hotel_stats['error_rate'] > self.alert_thresholds['error_rate_per_hour'] / 2:
                    await self._send_alert(
                        alert_type="hotel_high_error_rate",
                        message=f"High error rate for hotel {hotel_id}: {hotel_stats['error_rate']} errors/hour",
                        details=hotel_stats,
                        severity="warning",
                        hotel_id=hotel_id
                    )
                    
        finally:
            db.close()
            
    async def _check_error_spikes(self) -> None:
        """Check for error spikes"""
        db = next(get_db())
        try:
            analyzer = ErrorAnalyzer(db)
            
            # Check for overall spikes
            spikes = analyzer.detect_error_spikes(
                threshold_multiplier=self.alert_thresholds['spike_threshold_multiplier'],
                hours_to_analyze=6
            )
            
            for spike in spikes:
                await self._send_alert(
                    alert_type="error_spike",
                    message=f"Error spike detected: {spike['error_count']} errors in hour {spike['hour']}",
                    details=spike,
                    severity="error"
                )
                
            # Check for hotel-specific spikes
            hotels_with_errors = db.query(ErrorLog.hotel_id).filter(
                ErrorLog.hotel_id.isnot(None),
                ErrorLog.timestamp >= datetime.utcnow() - timedelta(hours=6)
            ).distinct().all()
            
            for (hotel_id,) in hotels_with_errors:
                hotel_spikes = analyzer.detect_error_spikes(
                    hotel_id=hotel_id,
                    threshold_multiplier=self.alert_thresholds['spike_threshold_multiplier'],
                    hours_to_analyze=6
                )
                
                for spike in hotel_spikes:
                    await self._send_alert(
                        alert_type="hotel_error_spike",
                        message=f"Error spike for hotel {hotel_id}: {spike['error_count']} errors in hour {spike['hour']}",
                        details=spike,
                        severity="error",
                        hotel_id=hotel_id
                    )
                    
        finally:
            db.close()
            
    async def _check_critical_errors(self) -> None:
        """Check for critical errors"""
        db = next(get_db())
        try:
            # Check for critical errors in the last hour
            critical_errors = db.query(ErrorLog).filter(
                ErrorLog.severity == 'critical',
                ErrorLog.timestamp >= datetime.utcnow() - timedelta(hours=1)
            ).all()
            
            if len(critical_errors) > self.alert_thresholds['critical_errors_per_hour']:
                await self._send_alert(
                    alert_type="critical_errors",
                    message=f"High number of critical errors: {len(critical_errors)} in the last hour",
                    details={
                        'critical_error_count': len(critical_errors),
                        'errors': [error.to_dict() for error in critical_errors[:5]]
                    },
                    severity="critical"
                )
                
            # Check for new critical error types
            for error in critical_errors:
                alert_key = f"critical_error_{error.fingerprint}"
                if alert_key not in self.recent_alerts:
                    await self._send_alert(
                        alert_type="new_critical_error",
                        message=f"New critical error: {error.error_type} - {error.error_message}",
                        details=error.to_dict(),
                        severity="critical",
                        hotel_id=error.hotel_id
                    )
                    self.recent_alerts.add(alert_key)
                    
        finally:
            db.close()
            
    async def _send_alert(
        self,
        alert_type: str,
        message: str,
        details: Dict[str, Any],
        severity: str,
        hotel_id: Optional[str] = None
    ) -> None:
        """Send an alert"""
        # Create alert key for deduplication
        alert_key = f"{alert_type}_{hotel_id or 'global'}_{severity}"
        
        # Check if we've already sent this alert recently
        if alert_key in self.recent_alerts:
            return
            
        # Add to recent alerts
        self.recent_alerts.add(alert_key)
        
        # Log the alert
        logger.error(
            f"Error monitoring alert: {message}",
            alert_type=alert_type,
            severity=severity,
            hotel_id=hotel_id,
            details=details
        )
        
        # TODO: Send to external alerting systems (email, Slack, etc.)
        # This would integrate with the alert service
        
    async def _cleanup_old_alerts(self) -> None:
        """Clean up old alerts from recent alerts set"""
        # For now, just clear the set periodically
        # In a real implementation, you'd track timestamps
        if len(self.recent_alerts) > 1000:
            self.recent_alerts.clear()
            
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        db = next(get_db())
        try:
            tracker = ErrorTracker(db)
            
            # Get recent statistics
            recent_stats = tracker.get_error_statistics(
                start_time=datetime.utcnow() - timedelta(hours=1)
            )
            
            daily_stats = tracker.get_error_statistics(
                start_time=datetime.utcnow() - timedelta(hours=24)
            )
            
            # Get top errors
            top_errors = tracker.get_top_errors(limit=5)
            
            return {
                'status': 'active',
                'last_check': datetime.utcnow().isoformat(),
                'alert_thresholds': self.alert_thresholds,
                'recent_alerts_count': len(self.recent_alerts),
                'recent_stats': recent_stats,
                'daily_stats': daily_stats,
                'top_errors': top_errors
            }
            
        finally:
            db.close()


class ErrorReporter:
    """Generates error reports and summaries"""
    
    def __init__(self):
        pass
        
    def generate_daily_report(
        self,
        date: Optional[datetime] = None,
        hotel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate daily error report"""
        if not date:
            date = datetime.utcnow().date()
            
        start_time = datetime.combine(date, datetime.min.time())
        end_time = start_time + timedelta(days=1)
        
        db = next(get_db())
        try:
            tracker = ErrorTracker(db)
            analyzer = ErrorAnalyzer(db)
            
            # Get statistics
            stats = tracker.get_error_statistics(
                hotel_id=hotel_id,
                start_time=start_time,
                end_time=end_time
            )
            
            # Get trends
            trends = tracker.get_error_trends(
                hotel_id=hotel_id,
                hours=24
            )
            
            # Get top errors
            top_errors = tracker.get_top_errors(
                hotel_id=hotel_id,
                limit=10
            )
            
            # Get patterns
            patterns = analyzer.find_error_patterns(
                hotel_id=hotel_id,
                days=1
            )
            
            return {
                'date': date.isoformat(),
                'hotel_id': hotel_id,
                'statistics': stats,
                'trends': trends,
                'top_errors': top_errors,
                'patterns': patterns,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    def generate_weekly_summary(
        self,
        week_start: Optional[datetime] = None,
        hotel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate weekly error summary"""
        if not week_start:
            today = datetime.utcnow().date()
            week_start = today - timedelta(days=today.weekday())
            
        week_end = week_start + timedelta(days=7)
        
        db = next(get_db())
        try:
            tracker = ErrorTracker(db)
            
            # Get weekly statistics
            stats = tracker.get_error_statistics(
                hotel_id=hotel_id,
                start_time=week_start,
                end_time=week_end
            )
            
            # Get daily breakdown
            daily_stats = []
            for i in range(7):
                day_start = week_start + timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                
                day_stats = tracker.get_error_statistics(
                    hotel_id=hotel_id,
                    start_time=day_start,
                    end_time=day_end
                )
                day_stats['date'] = day_start.isoformat()
                daily_stats.append(day_stats)
                
            return {
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'hotel_id': hotel_id,
                'weekly_statistics': stats,
                'daily_breakdown': daily_stats,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()


# Global monitor instance
_error_monitor: Optional[ErrorMonitor] = None


def get_error_monitor() -> ErrorMonitor:
    """Get the global error monitor instance"""
    global _error_monitor
    if _error_monitor is None:
        _error_monitor = ErrorMonitor()
    return _error_monitor


async def start_error_monitoring() -> None:
    """Start the error monitoring service"""
    monitor = get_error_monitor()
    await monitor.monitor_errors()
