"""
DeepSeek monitoring and metrics service for WhatsApp Hotel Bot
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.sentiment import SentimentAnalysis, SentimentSummary
from app.models.message import Message
from app.models.hotel import Hotel
from app.core.deepseek_logging import get_deepseek_logger, get_deepseek_metrics
from app.schemas.deepseek import DeepSeekOperationLog

logger = structlog.get_logger(__name__)


class DeepSeekMonitoringService:
    """Service for monitoring DeepSeek AI operations and performance"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = get_deepseek_logger()
        
        # Real-time metrics tracking
        self.real_time_metrics = {
            'requests_per_minute': deque(maxlen=60),  # Last 60 minutes
            'response_times': deque(maxlen=1000),     # Last 1000 requests
            'error_rates': deque(maxlen=60),          # Last 60 minutes
            'token_usage': deque(maxlen=60),          # Last 60 minutes
            'sentiment_distribution': defaultdict(int),
            'hotel_activity': defaultdict(int)
        }
        
        # Performance thresholds
        self.thresholds = {
            'max_response_time_ms': 10000,  # 10 seconds
            'max_error_rate_percent': 5.0,   # 5%
            'max_tokens_per_minute': 100000,
            'min_confidence_score': 0.6
        }
    
    def record_api_call(
        self,
        operation_type: str,
        response_time_ms: int,
        tokens_used: int,
        success: bool,
        hotel_id: Optional[str] = None
    ):
        """Record API call metrics"""
        current_minute = int(time.time() // 60)
        
        # Record request
        self.real_time_metrics['requests_per_minute'].append({
            'minute': current_minute,
            'operation': operation_type,
            'success': success
        })
        
        # Record response time
        if response_time_ms:
            self.real_time_metrics['response_times'].append({
                'timestamp': time.time(),
                'response_time_ms': response_time_ms,
                'operation': operation_type
            })
        
        # Record error rate
        self.real_time_metrics['error_rates'].append({
            'minute': current_minute,
            'error': not success
        })
        
        # Record token usage
        if tokens_used:
            self.real_time_metrics['token_usage'].append({
                'minute': current_minute,
                'tokens': tokens_used,
                'operation': operation_type
            })
        
        # Record hotel activity
        if hotel_id:
            self.real_time_metrics['hotel_activity'][hotel_id] += 1
    
    def record_sentiment_analysis(
        self,
        sentiment_type: str,
        confidence_score: float,
        hotel_id: str
    ):
        """Record sentiment analysis metrics"""
        self.real_time_metrics['sentiment_distribution'][sentiment_type] += 1
        
        # Check for low confidence alerts
        if confidence_score < self.thresholds['min_confidence_score']:
            logger.warning("Low confidence sentiment analysis detected",
                         sentiment_type=sentiment_type,
                         confidence=confidence_score,
                         hotel_id=hotel_id)
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get current real-time metrics"""
        current_time = time.time()
        current_minute = int(current_time // 60)
        
        # Calculate requests per minute (last 5 minutes)
        recent_requests = [
            req for req in self.real_time_metrics['requests_per_minute']
            if req['minute'] >= current_minute - 5
        ]
        requests_per_minute = len(recent_requests) / 5 if recent_requests else 0
        
        # Calculate average response time (last 100 requests)
        recent_response_times = [
            rt['response_time_ms'] for rt in self.real_time_metrics['response_times']
            if rt['timestamp'] >= current_time - 300  # Last 5 minutes
        ]
        avg_response_time = sum(recent_response_times) / len(recent_response_times) if recent_response_times else 0
        
        # Calculate error rate (last 5 minutes)
        recent_errors = [
            err for err in self.real_time_metrics['error_rates']
            if err['minute'] >= current_minute - 5
        ]
        error_count = sum(1 for err in recent_errors if err['error'])
        error_rate = (error_count / len(recent_errors) * 100) if recent_errors else 0
        
        # Calculate token usage (last 5 minutes)
        recent_tokens = [
            token['tokens'] for token in self.real_time_metrics['token_usage']
            if token['minute'] >= current_minute - 5
        ]
        tokens_per_minute = sum(recent_tokens) / 5 if recent_tokens else 0
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'requests_per_minute': round(requests_per_minute, 2),
            'average_response_time_ms': round(avg_response_time, 2),
            'error_rate_percent': round(error_rate, 2),
            'tokens_per_minute': round(tokens_per_minute, 2),
            'sentiment_distribution': dict(self.real_time_metrics['sentiment_distribution']),
            'active_hotels': len(self.real_time_metrics['hotel_activity']),
            'total_hotel_requests': sum(self.real_time_metrics['hotel_activity'].values())
        }
    
    def check_performance_alerts(self) -> List[Dict[str, Any]]:
        """Check for performance issues and return alerts"""
        alerts = []
        metrics = self.get_real_time_metrics()
        
        # Check response time
        if metrics['average_response_time_ms'] > self.thresholds['max_response_time_ms']:
            alerts.append({
                'type': 'high_response_time',
                'severity': 'warning',
                'message': f"Average response time is {metrics['average_response_time_ms']}ms (threshold: {self.thresholds['max_response_time_ms']}ms)",
                'value': metrics['average_response_time_ms'],
                'threshold': self.thresholds['max_response_time_ms']
            })
        
        # Check error rate
        if metrics['error_rate_percent'] > self.thresholds['max_error_rate_percent']:
            alerts.append({
                'type': 'high_error_rate',
                'severity': 'critical',
                'message': f"Error rate is {metrics['error_rate_percent']}% (threshold: {self.thresholds['max_error_rate_percent']}%)",
                'value': metrics['error_rate_percent'],
                'threshold': self.thresholds['max_error_rate_percent']
            })
        
        # Check token usage
        if metrics['tokens_per_minute'] > self.thresholds['max_tokens_per_minute']:
            alerts.append({
                'type': 'high_token_usage',
                'severity': 'warning',
                'message': f"Token usage is {metrics['tokens_per_minute']} per minute (threshold: {self.thresholds['max_tokens_per_minute']})",
                'value': metrics['tokens_per_minute'],
                'threshold': self.thresholds['max_tokens_per_minute']
            })
        
        return alerts
    
    async def get_hotel_sentiment_metrics(
        self,
        hotel_id: str,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """Get sentiment metrics for a specific hotel"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            # Get sentiment analysis counts
            sentiment_counts = self.db.query(
                SentimentAnalysis.sentiment_type,
                func.count(SentimentAnalysis.id).label('count')
            ).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= cutoff_date
            ).group_by(SentimentAnalysis.sentiment_type).all()
            
            # Get average scores
            avg_scores = self.db.query(
                func.avg(SentimentAnalysis.sentiment_score).label('avg_sentiment'),
                func.avg(SentimentAnalysis.confidence_score).label('avg_confidence')
            ).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= cutoff_date
            ).first()
            
            # Get attention required count
            attention_count = self.db.query(func.count(SentimentAnalysis.id)).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.requires_attention == True,
                SentimentAnalysis.created_at >= cutoff_date
            ).scalar()
            
            # Calculate total messages
            total_messages = sum(count for _, count in sentiment_counts)
            
            # Build response
            sentiment_distribution = {sentiment: count for sentiment, count in sentiment_counts}
            
            return {
                'hotel_id': hotel_id,
                'period_days': days_back,
                'total_messages_analyzed': total_messages,
                'sentiment_distribution': sentiment_distribution,
                'average_sentiment_score': float(avg_scores.avg_sentiment) if avg_scores.avg_sentiment else 0.0,
                'average_confidence_score': float(avg_scores.avg_confidence) if avg_scores.avg_confidence else 0.0,
                'messages_requiring_attention': attention_count,
                'attention_rate_percent': (attention_count / total_messages * 100) if total_messages > 0 else 0.0
            }
            
        except Exception as e:
            logger.error("Failed to get hotel sentiment metrics",
                        hotel_id=hotel_id,
                        error=str(e))
            return {}
    
    async def get_system_health_report(self) -> Dict[str, Any]:
        """Get comprehensive system health report"""
        try:
            # Get global metrics from logger
            global_metrics = get_deepseek_metrics()
            
            # Get real-time metrics
            real_time = self.get_real_time_metrics()
            
            # Get performance alerts
            alerts = self.check_performance_alerts()
            
            # Get recent error logs
            error_logs = self.logger.get_error_logs(limit=10)
            
            # Calculate uptime and reliability
            total_requests = global_metrics.get('total_requests', 0)
            successful_requests = global_metrics.get('successful_requests', 0)
            reliability_percent = (successful_requests / total_requests * 100) if total_requests > 0 else 100.0
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'system_status': 'healthy' if not alerts else 'degraded' if any(a['severity'] == 'warning' for a in alerts) else 'critical',
                'global_metrics': global_metrics,
                'real_time_metrics': real_time,
                'reliability_percent': round(reliability_percent, 2),
                'alerts': alerts,
                'recent_errors': [
                    {
                        'timestamp': log.timestamp.isoformat(),
                        'operation': log.operation_type,
                        'error': log.error_message
                    }
                    for log in error_logs
                ],
                'performance_summary': {
                    'avg_response_time_ms': real_time['average_response_time_ms'],
                    'requests_per_minute': real_time['requests_per_minute'],
                    'error_rate_percent': real_time['error_rate_percent'],
                    'tokens_per_minute': real_time['tokens_per_minute']
                }
            }
            
        except Exception as e:
            logger.error("Failed to generate system health report", error=str(e))
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'system_status': 'unknown',
                'error': str(e)
            }
    
    async def generate_daily_sentiment_summary(
        self,
        hotel_id: str,
        date: datetime
    ) -> Optional[SentimentSummary]:
        """Generate daily sentiment summary for a hotel"""
        try:
            # Get date range for the day
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            
            # Check if summary already exists
            existing_summary = self.db.query(SentimentSummary).filter(
                SentimentSummary.hotel_id == hotel_id,
                SentimentSummary.summary_date == start_date
            ).first()
            
            if existing_summary:
                logger.info("Daily sentiment summary already exists",
                           hotel_id=hotel_id,
                           date=start_date.date())
                return existing_summary
            
            # Get sentiment analyses for the day
            analyses = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.hotel_id == hotel_id,
                SentimentAnalysis.created_at >= start_date,
                SentimentAnalysis.created_at < end_date
            ).all()
            
            if not analyses:
                logger.info("No sentiment analyses found for date",
                           hotel_id=hotel_id,
                           date=start_date.date())
                return None
            
            # Calculate summary statistics
            total_messages = len(analyses)
            positive_count = sum(1 for a in analyses if a.sentiment_type == 'positive')
            negative_count = sum(1 for a in analyses if a.sentiment_type == 'negative')
            neutral_count = sum(1 for a in analyses if a.sentiment_type == 'neutral')
            attention_count = sum(1 for a in analyses if a.requires_attention)
            
            avg_sentiment = sum(a.sentiment_score for a in analyses) / total_messages
            avg_confidence = sum(a.confidence_score for a in analyses) / total_messages
            
            notifications_sent = sum(1 for a in analyses if a.notification_sent)
            total_tokens = sum(a.tokens_used for a in analyses if a.tokens_used)
            avg_processing_time = sum(a.processing_time_ms for a in analyses if a.processing_time_ms) / total_messages
            
            # Create summary record
            summary = SentimentSummary(
                hotel_id=hotel_id,
                summary_date=start_date,
                total_messages=total_messages,
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count,
                attention_required_count=attention_count,
                average_sentiment_score=avg_sentiment,
                average_confidence_score=avg_confidence,
                notifications_sent=notifications_sent,
                total_tokens_used=total_tokens,
                average_processing_time_ms=avg_processing_time
            )
            
            self.db.add(summary)
            self.db.commit()
            self.db.refresh(summary)
            
            logger.info("Daily sentiment summary generated",
                       hotel_id=hotel_id,
                       date=start_date.date(),
                       total_messages=total_messages,
                       positive_percentage=summary.positive_percentage)
            
            return summary
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to generate daily sentiment summary",
                        hotel_id=hotel_id,
                        date=date.date(),
                        error=str(e))
            return None
    
    def export_metrics_json(self, include_logs: bool = False) -> str:
        """Export all metrics as JSON"""
        try:
            export_data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'global_metrics': get_deepseek_metrics(),
                'real_time_metrics': self.get_real_time_metrics(),
                'performance_alerts': self.check_performance_alerts(),
                'thresholds': self.thresholds
            }
            
            if include_logs:
                export_data['recent_logs'] = [
                    log.dict() for log in self.logger.get_recent_logs(limit=100)
                ]
            
            return json.dumps(export_data, indent=2, default=str)
            
        except Exception as e:
            logger.error("Failed to export metrics", error=str(e))
            return json.dumps({'error': str(e)}, indent=2)


# Global monitoring service instance
_global_monitoring_service: Optional[DeepSeekMonitoringService] = None


def get_monitoring_service(db: Session) -> DeepSeekMonitoringService:
    """Get monitoring service instance"""
    return DeepSeekMonitoringService(db)


# Export main components
__all__ = [
    'DeepSeekMonitoringService',
    'get_monitoring_service'
]
