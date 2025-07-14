"""
Green API monitoring and alerting service
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import structlog

from app.middleware.green_api_middleware import get_green_api_metrics
from app.core.green_api_logging import get_green_api_logger
from app.models.notification import StaffNotification

logger = structlog.get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts"""
    ERROR_RATE = "error_rate"
    RESPONSE_TIME = "response_time"
    RATE_LIMIT = "rate_limit"
    INSTANCE_DOWN = "instance_down"
    WEBHOOK_FAILURE = "webhook_failure"
    MESSAGE_FAILURE = "message_failure"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    alert_type: AlertType
    severity: AlertSeverity
    threshold: float
    duration: int  # seconds
    enabled: bool = True
    cooldown: int = 300  # 5 minutes default cooldown
    
    # Callback function for custom handling
    callback: Optional[Callable] = None
    
    # Metadata for rule
    description: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class AlertManager:
    """Manages alerts and monitoring for Green API"""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, datetime] = {}
        self.alert_history: List[Dict[str, Any]] = []
        self.green_api_logger = get_green_api_logger("monitoring")
        
        # Default alert rules
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup default monitoring rules"""
        default_rules = [
            AlertRule(
                name="High Error Rate",
                alert_type=AlertType.ERROR_RATE,
                severity=AlertSeverity.HIGH,
                threshold=0.1,  # 10% error rate
                duration=300,   # 5 minutes
                description="Error rate exceeds 10% for 5 minutes"
            ),
            AlertRule(
                name="Critical Error Rate",
                alert_type=AlertType.ERROR_RATE,
                severity=AlertSeverity.CRITICAL,
                threshold=0.25,  # 25% error rate
                duration=60,     # 1 minute
                description="Error rate exceeds 25% for 1 minute"
            ),
            AlertRule(
                name="Slow Response Time",
                alert_type=AlertType.RESPONSE_TIME,
                severity=AlertSeverity.MEDIUM,
                threshold=5000,  # 5 seconds
                duration=300,    # 5 minutes
                description="Average response time exceeds 5 seconds"
            ),
            AlertRule(
                name="Very Slow Response Time",
                alert_type=AlertType.RESPONSE_TIME,
                severity=AlertSeverity.HIGH,
                threshold=10000,  # 10 seconds
                duration=180,     # 3 minutes
                description="Average response time exceeds 10 seconds"
            ),
            AlertRule(
                name="Rate Limit Hit",
                alert_type=AlertType.RATE_LIMIT,
                severity=AlertSeverity.MEDIUM,
                threshold=5,     # 5 rate limit hits
                duration=300,    # 5 minutes
                description="Rate limit hit 5 times in 5 minutes"
            ),
            AlertRule(
                name="Webhook Failures",
                alert_type=AlertType.WEBHOOK_FAILURE,
                severity=AlertSeverity.HIGH,
                threshold=0.2,   # 20% webhook failure rate
                duration=300,    # 5 minutes
                description="Webhook failure rate exceeds 20%"
            ),
            AlertRule(
                name="Message Send Failures",
                alert_type=AlertType.MESSAGE_FAILURE,
                severity=AlertSeverity.HIGH,
                threshold=0.15,  # 15% message failure rate
                duration=300,    # 5 minutes
                description="Message send failure rate exceeds 15%"
            )
        ]
        
        self.rules.extend(default_rules)
    
    def add_rule(self, rule: AlertRule):
        """Add a new alert rule"""
        self.rules.append(rule)
        logger.info("Alert rule added", rule_name=rule.name, alert_type=rule.alert_type.value)
    
    def remove_rule(self, rule_name: str):
        """Remove an alert rule"""
        self.rules = [rule for rule in self.rules if rule.name != rule_name]
        logger.info("Alert rule removed", rule_name=rule_name)
    
    def enable_rule(self, rule_name: str):
        """Enable an alert rule"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                logger.info("Alert rule enabled", rule_name=rule_name)
                break
    
    def disable_rule(self, rule_name: str):
        """Disable an alert rule"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                logger.info("Alert rule disabled", rule_name=rule_name)
                break
    
    async def check_alerts(self):
        """Check all alert rules against current metrics"""
        metrics = get_green_api_metrics().get_metrics()
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                should_alert = await self._evaluate_rule(rule, metrics)
                
                if should_alert:
                    await self._trigger_alert(rule, metrics)
                else:
                    # Clear alert if it was active
                    self._clear_alert(rule.name)
                    
            except Exception as e:
                logger.error("Error evaluating alert rule", 
                           rule_name=rule.name, 
                           error=str(e))
    
    async def _evaluate_rule(self, rule: AlertRule, metrics: Dict[str, Any]) -> bool:
        """Evaluate if a rule should trigger an alert"""
        current_time = datetime.utcnow()
        
        # Check if rule is in cooldown
        if rule.name in self.active_alerts:
            last_alert = self.active_alerts[rule.name]
            if (current_time - last_alert).total_seconds() < rule.cooldown:
                return False
        
        # Evaluate based on alert type
        if rule.alert_type == AlertType.ERROR_RATE:
            error_rate = metrics['requests']['error_rate']
            return error_rate >= rule.threshold
        
        elif rule.alert_type == AlertType.RESPONSE_TIME:
            avg_response_time = metrics['response_times']['average']
            return avg_response_time >= rule.threshold
        
        elif rule.alert_type == AlertType.RATE_LIMIT:
            rate_limit_hits = metrics['rate_limiting']['hits']
            return rate_limit_hits >= rule.threshold
        
        elif rule.alert_type == AlertType.WEBHOOK_FAILURE:
            webhook_total = metrics['webhooks']['total']
            webhook_errors = metrics['webhooks']['errors']
            if webhook_total > 0:
                webhook_error_rate = webhook_errors / webhook_total
                return webhook_error_rate >= rule.threshold
        
        elif rule.alert_type == AlertType.MESSAGE_FAILURE:
            messages_sent = metrics['messages']['sent']
            messages_failed = metrics['messages']['failed']
            total_messages = messages_sent + messages_failed
            if total_messages > 0:
                failure_rate = messages_failed / total_messages
                return failure_rate >= rule.threshold
        
        elif rule.alert_type == AlertType.INSTANCE_DOWN:
            # Check if any instances haven't had requests recently
            for instance_id, instance_metrics in metrics['instances'].items():
                if instance_metrics['last_request']:
                    last_request = datetime.fromisoformat(instance_metrics['last_request'])
                    if (current_time - last_request).total_seconds() > rule.threshold:
                        return True
        
        return False
    
    async def _trigger_alert(self, rule: AlertRule, metrics: Dict[str, Any]):
        """Trigger an alert"""
        current_time = datetime.utcnow()
        
        # Record alert
        self.active_alerts[rule.name] = current_time
        
        # Create alert data
        alert_data = {
            'rule_name': rule.name,
            'alert_type': rule.alert_type.value,
            'severity': rule.severity.value,
            'threshold': rule.threshold,
            'description': rule.description,
            'timestamp': current_time.isoformat(),
            'metrics_snapshot': metrics,
            'tags': rule.tags
        }
        
        # Add to history
        self.alert_history.append(alert_data)
        
        # Log alert
        self.green_api_logger.logger.warning(
            "Green API alert triggered",
            **alert_data
        )
        
        # Execute callback if provided
        if rule.callback:
            try:
                await rule.callback(alert_data)
            except Exception as e:
                logger.error("Error executing alert callback", 
                           rule_name=rule.name, 
                           error=str(e))
        
        # Send notification
        await self._send_alert_notification(alert_data)
    
    def _clear_alert(self, rule_name: str):
        """Clear an active alert"""
        if rule_name in self.active_alerts:
            del self.active_alerts[rule_name]
            logger.info("Alert cleared", rule_name=rule_name)
    
    async def _send_alert_notification(self, alert_data: Dict[str, Any]):
        """Send alert notification to staff"""
        try:
            # This would integrate with your notification system
            # For now, we'll just log it
            logger.warning(
                "Green API Alert",
                alert_type=alert_data['alert_type'],
                severity=alert_data['severity'],
                description=alert_data['description']
            )
            
            # TODO: Integrate with StaffNotification model
            # notification = StaffNotification(
            #     notification_type='green_api_alert',
            #     title=f"Green API Alert: {alert_data['rule_name']}",
            #     message=alert_data['description'],
            #     metadata=alert_data
            # )
            
        except Exception as e:
            logger.error("Error sending alert notification", error=str(e))
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get list of active alerts"""
        return [
            {
                'rule_name': rule_name,
                'triggered_at': timestamp.isoformat(),
                'duration': (datetime.utcnow() - timestamp).total_seconds()
            }
            for rule_name, timestamp in self.active_alerts.items()
        ]
    
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get alert history"""
        return self.alert_history[-limit:]
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all alert rules"""
        return [
            {
                'name': rule.name,
                'alert_type': rule.alert_type.value,
                'severity': rule.severity.value,
                'threshold': rule.threshold,
                'duration': rule.duration,
                'enabled': rule.enabled,
                'cooldown': rule.cooldown,
                'description': rule.description,
                'tags': rule.tags
            }
            for rule in self.rules
        ]


class GreenAPIHealthChecker:
    """Health checker for Green API instances"""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.health_checks: Dict[str, Dict[str, Any]] = {}
    
    async def check_instance_health(self, instance_id: str) -> Dict[str, Any]:
        """Check health of a specific Green API instance"""
        try:
            # This would make actual health check requests
            # For now, we'll use metrics to determine health
            metrics = get_green_api_metrics().get_metrics()
            
            instance_metrics = metrics['instances'].get(instance_id, {})
            
            health_status = {
                'instance_id': instance_id,
                'status': 'healthy',
                'last_request': instance_metrics.get('last_request'),
                'error_rate': 0.0,
                'avg_response_time': instance_metrics.get('avg_response_time', 0),
                'total_requests': instance_metrics.get('requests', 0),
                'total_errors': instance_metrics.get('errors', 0),
                'checked_at': datetime.utcnow().isoformat()
            }
            
            # Calculate error rate
            if health_status['total_requests'] > 0:
                health_status['error_rate'] = (
                    health_status['total_errors'] / health_status['total_requests']
                )
            
            # Determine status based on metrics
            if health_status['error_rate'] > 0.5:
                health_status['status'] = 'unhealthy'
            elif health_status['error_rate'] > 0.2:
                health_status['status'] = 'degraded'
            elif health_status['avg_response_time'] > 10000:
                health_status['status'] = 'slow'
            
            # Store health check result
            self.health_checks[instance_id] = health_status
            
            return health_status
            
        except Exception as e:
            logger.error("Error checking instance health", 
                        instance_id=instance_id, 
                        error=str(e))
            
            error_status = {
                'instance_id': instance_id,
                'status': 'error',
                'error': str(e),
                'checked_at': datetime.utcnow().isoformat()
            }
            
            self.health_checks[instance_id] = error_status
            return error_status
    
    async def check_all_instances(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all known instances"""
        metrics = get_green_api_metrics().get_metrics()
        instance_ids = list(metrics['instances'].keys())
        
        health_results = {}
        for instance_id in instance_ids:
            health_results[instance_id] = await self.check_instance_health(instance_id)
        
        return health_results
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary"""
        if not self.health_checks:
            return {
                'overall_status': 'unknown',
                'total_instances': 0,
                'healthy_instances': 0,
                'unhealthy_instances': 0,
                'degraded_instances': 0
            }
        
        status_counts = {
            'healthy': 0,
            'degraded': 0,
            'slow': 0,
            'unhealthy': 0,
            'error': 0
        }
        
        for health_check in self.health_checks.values():
            status = health_check.get('status', 'unknown')
            if status in status_counts:
                status_counts[status] += 1
        
        total_instances = len(self.health_checks)
        healthy_instances = status_counts['healthy']
        
        # Determine overall status
        if status_counts['error'] > 0 or status_counts['unhealthy'] > 0:
            overall_status = 'unhealthy'
        elif status_counts['degraded'] > 0 or status_counts['slow'] > 0:
            overall_status = 'degraded'
        elif healthy_instances == total_instances:
            overall_status = 'healthy'
        else:
            overall_status = 'unknown'
        
        return {
            'overall_status': overall_status,
            'total_instances': total_instances,
            'healthy_instances': healthy_instances,
            'unhealthy_instances': status_counts['unhealthy'] + status_counts['error'],
            'degraded_instances': status_counts['degraded'] + status_counts['slow'],
            'status_breakdown': status_counts
        }


# Global instances
alert_manager = AlertManager()
health_checker = GreenAPIHealthChecker(alert_manager)


async def start_monitoring():
    """Start the monitoring loop"""
    logger.info("Starting Green API monitoring")
    
    while True:
        try:
            # Check alerts
            await alert_manager.check_alerts()
            
            # Check health
            await health_checker.check_all_instances()
            
            # Wait before next check
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error("Error in monitoring loop", error=str(e))
            await asyncio.sleep(60)


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance"""
    return alert_manager


def get_health_checker() -> GreenAPIHealthChecker:
    """Get global health checker instance"""
    return health_checker


# Export main components
__all__ = [
    'AlertManager',
    'GreenAPIHealthChecker',
    'AlertRule',
    'AlertSeverity',
    'AlertType',
    'alert_manager',
    'health_checker',
    'start_monitoring',
    'get_alert_manager',
    'get_health_checker'
]
