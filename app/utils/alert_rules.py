"""
Alert rules and conditions for error monitoring.

This module defines rules and conditions that determine when alerts
should be triggered based on error patterns and thresholds.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    TELEGRAM = "telegram"


@dataclass
class AlertCondition:
    """Represents an alert condition"""
    name: str
    description: str
    severity: AlertSeverity
    channels: List[AlertChannel]
    enabled: bool = True
    cooldown_minutes: int = 30
    hotel_specific: bool = False


class AlertRule(ABC):
    """Base class for alert rules"""
    
    def __init__(self, condition: AlertCondition):
        self.condition = condition
        
    @abstractmethod
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """
        Evaluate if the rule condition is met
        
        Args:
            data: Data to evaluate against
            
        Returns:
            True if alert should be triggered
        """
        pass
        
    @abstractmethod
    def get_alert_message(self, data: Dict[str, Any]) -> str:
        """
        Generate alert message
        
        Args:
            data: Data that triggered the alert
            
        Returns:
            Alert message
        """
        pass


class ErrorRateRule(AlertRule):
    """Rule for error rate thresholds"""
    
    def __init__(
        self,
        condition: AlertCondition,
        threshold: float,
        time_window_minutes: int = 60
    ):
        super().__init__(condition)
        self.threshold = threshold
        self.time_window_minutes = time_window_minutes
        
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if error rate exceeds threshold"""
        error_rate = data.get('error_rate', 0)
        return error_rate > self.threshold
        
    def get_alert_message(self, data: Dict[str, Any]) -> str:
        """Generate error rate alert message"""
        error_rate = data.get('error_rate', 0)
        hotel_id = data.get('hotel_id')
        
        if hotel_id:
            return f"High error rate for hotel {hotel_id}: {error_rate:.2f} errors/hour (threshold: {self.threshold})"
        else:
            return f"High error rate detected: {error_rate:.2f} errors/hour (threshold: {self.threshold})"


class ErrorSpikeRule(AlertRule):
    """Rule for detecting error spikes"""
    
    def __init__(
        self,
        condition: AlertCondition,
        spike_multiplier: float = 3.0,
        minimum_errors: int = 10
    ):
        super().__init__(condition)
        self.spike_multiplier = spike_multiplier
        self.minimum_errors = minimum_errors
        
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if error spike is detected"""
        spike_ratio = data.get('spike_ratio', 0)
        error_count = data.get('error_count', 0)
        
        return (spike_ratio > self.spike_multiplier and 
                error_count >= self.minimum_errors)
        
    def get_alert_message(self, data: Dict[str, Any]) -> str:
        """Generate error spike alert message"""
        error_count = data.get('error_count', 0)
        spike_ratio = data.get('spike_ratio', 0)
        hour = data.get('hour', 'unknown')
        hotel_id = data.get('hotel_id')
        
        if hotel_id:
            return f"Error spike detected for hotel {hotel_id}: {error_count} errors in hour {hour} ({spike_ratio:.1f}x normal)"
        else:
            return f"Error spike detected: {error_count} errors in hour {hour} ({spike_ratio:.1f}x normal)"


class CriticalErrorRule(AlertRule):
    """Rule for critical errors"""
    
    def __init__(
        self,
        condition: AlertCondition,
        max_critical_errors: int = 5
    ):
        super().__init__(condition)
        self.max_critical_errors = max_critical_errors
        
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if critical error threshold is exceeded"""
        critical_count = data.get('critical_errors', 0)
        return critical_count > self.max_critical_errors
        
    def get_alert_message(self, data: Dict[str, Any]) -> str:
        """Generate critical error alert message"""
        critical_count = data.get('critical_errors', 0)
        hotel_id = data.get('hotel_id')
        
        if hotel_id:
            return f"High number of critical errors for hotel {hotel_id}: {critical_count} in the last hour"
        else:
            return f"High number of critical errors: {critical_count} in the last hour"


class NewErrorTypeRule(AlertRule):
    """Rule for new error types"""
    
    def __init__(self, condition: AlertCondition):
        super().__init__(condition)
        
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if this is a new error type"""
        return data.get('is_new_error_type', False)
        
    def get_alert_message(self, data: Dict[str, Any]) -> str:
        """Generate new error type alert message"""
        error_type = data.get('error_type', 'Unknown')
        error_message = data.get('error_message', '')
        hotel_id = data.get('hotel_id')
        
        if hotel_id:
            return f"New error type for hotel {hotel_id}: {error_type} - {error_message[:100]}"
        else:
            return f"New error type detected: {error_type} - {error_message[:100]}"


class ServiceDownRule(AlertRule):
    """Rule for service downtime detection"""
    
    def __init__(
        self,
        condition: AlertCondition,
        consecutive_failures: int = 5
    ):
        super().__init__(condition)
        self.consecutive_failures = consecutive_failures
        
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if service appears to be down"""
        consecutive_errors = data.get('consecutive_errors', 0)
        return consecutive_errors >= self.consecutive_failures
        
    def get_alert_message(self, data: Dict[str, Any]) -> str:
        """Generate service down alert message"""
        service_name = data.get('service_name', 'Unknown service')
        consecutive_errors = data.get('consecutive_errors', 0)
        
        return f"Service potentially down: {service_name} ({consecutive_errors} consecutive failures)"


class DatabaseErrorRule(AlertRule):
    """Rule for database-related errors"""
    
    def __init__(
        self,
        condition: AlertCondition,
        db_error_threshold: int = 20
    ):
        super().__init__(condition)
        self.db_error_threshold = db_error_threshold
        
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if database error threshold is exceeded"""
        db_errors = data.get('database_errors', 0)
        return db_errors > self.db_error_threshold
        
    def get_alert_message(self, data: Dict[str, Any]) -> str:
        """Generate database error alert message"""
        db_errors = data.get('database_errors', 0)
        return f"High number of database errors: {db_errors} in the last hour"


class ExternalAPIErrorRule(AlertRule):
    """Rule for external API errors"""
    
    def __init__(
        self,
        condition: AlertCondition,
        api_error_threshold: int = 30,
        api_name: Optional[str] = None
    ):
        super().__init__(condition)
        self.api_error_threshold = api_error_threshold
        self.api_name = api_name
        
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if API error threshold is exceeded"""
        api_errors = data.get('api_errors', 0)
        api_name = data.get('api_name')
        
        if self.api_name and api_name != self.api_name:
            return False
            
        return api_errors > self.api_error_threshold
        
    def get_alert_message(self, data: Dict[str, Any]) -> str:
        """Generate API error alert message"""
        api_errors = data.get('api_errors', 0)
        api_name = data.get('api_name', 'External API')
        
        return f"High number of {api_name} errors: {api_errors} in the last hour"


class AlertRuleEngine:
    """Engine for managing and evaluating alert rules"""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self._setup_default_rules()
        
    def _setup_default_rules(self) -> None:
        """Setup default alert rules"""
        # High error rate rule
        self.add_rule(ErrorRateRule(
            condition=AlertCondition(
                name="high_error_rate",
                description="Error rate exceeds threshold",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
                cooldown_minutes=30
            ),
            threshold=100.0
        ))
        
        # Error spike rule
        self.add_rule(ErrorSpikeRule(
            condition=AlertCondition(
                name="error_spike",
                description="Sudden spike in error rate",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
                cooldown_minutes=15
            ),
            spike_multiplier=3.0,
            minimum_errors=10
        ))
        
        # Critical errors rule
        self.add_rule(CriticalErrorRule(
            condition=AlertCondition(
                name="critical_errors",
                description="High number of critical errors",
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.SMS],
                cooldown_minutes=10
            ),
            max_critical_errors=5
        ))
        
        # New error type rule
        self.add_rule(NewErrorTypeRule(
            condition=AlertCondition(
                name="new_error_type",
                description="New error type detected",
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.EMAIL],
                cooldown_minutes=60
            )
        ))
        
        # Service down rule
        self.add_rule(ServiceDownRule(
            condition=AlertCondition(
                name="service_down",
                description="Service appears to be down",
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.SMS],
                cooldown_minutes=5
            ),
            consecutive_failures=5
        ))
        
        # Database error rule
        self.add_rule(DatabaseErrorRule(
            condition=AlertCondition(
                name="database_errors",
                description="High number of database errors",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
                cooldown_minutes=20
            ),
            db_error_threshold=20
        ))
        
        # Green API error rule
        self.add_rule(ExternalAPIErrorRule(
            condition=AlertCondition(
                name="green_api_errors",
                description="High number of Green API errors",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
                cooldown_minutes=30
            ),
            api_error_threshold=30,
            api_name="Green API"
        ))
        
        # DeepSeek API error rule
        self.add_rule(ExternalAPIErrorRule(
            condition=AlertCondition(
                name="deepseek_api_errors",
                description="High number of DeepSeek API errors",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
                cooldown_minutes=30
            ),
            api_error_threshold=20,
            api_name="DeepSeek API"
        ))
        
    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule"""
        self.rules.append(rule)
        
    def remove_rule(self, rule_name: str) -> bool:
        """Remove an alert rule by name"""
        for i, rule in enumerate(self.rules):
            if rule.condition.name == rule_name:
                del self.rules[i]
                return True
        return False
        
    def evaluate_rules(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against data
        
        Args:
            data: Data to evaluate
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        for rule in self.rules:
            if not rule.condition.enabled:
                continue
                
            try:
                if rule.evaluate(data):
                    alert = {
                        'rule_name': rule.condition.name,
                        'severity': rule.condition.severity.value,
                        'channels': [channel.value for channel in rule.condition.channels],
                        'message': rule.get_alert_message(data),
                        'description': rule.condition.description,
                        'cooldown_minutes': rule.condition.cooldown_minutes,
                        'hotel_specific': rule.condition.hotel_specific,
                        'data': data,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    triggered_alerts.append(alert)
                    
            except Exception as e:
                # Log rule evaluation error but don't fail
                print(f"Error evaluating rule {rule.condition.name}: {e}")
                
        return triggered_alerts
        
    def get_rule_by_name(self, name: str) -> Optional[AlertRule]:
        """Get a rule by name"""
        for rule in self.rules:
            if rule.condition.name == name:
                return rule
        return None
        
    def update_rule_condition(self, name: str, **kwargs) -> bool:
        """Update rule condition parameters"""
        rule = self.get_rule_by_name(name)
        if not rule:
            return False
            
        for key, value in kwargs.items():
            if hasattr(rule.condition, key):
                setattr(rule.condition, key, value)
                
        return True
        
    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Get all rules as dictionaries"""
        return [
            {
                'name': rule.condition.name,
                'description': rule.condition.description,
                'severity': rule.condition.severity.value,
                'channels': [channel.value for channel in rule.condition.channels],
                'enabled': rule.condition.enabled,
                'cooldown_minutes': rule.condition.cooldown_minutes,
                'hotel_specific': rule.condition.hotel_specific
            }
            for rule in self.rules
        ]


# Global rule engine instance
_rule_engine: Optional[AlertRuleEngine] = None


def get_alert_rule_engine() -> AlertRuleEngine:
    """Get the global alert rule engine"""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = AlertRuleEngine()
    return _rule_engine
