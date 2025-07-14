"""
Degradation handler for managing system degradation scenarios
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import threading

from app.core.logging import get_logger
from app.services.fallback_service import FallbackService, DegradationLevel
from app.utils.circuit_breaker import get_all_circuit_breakers, CircuitState
from app.services.health_checker import DependencyStatus

logger = get_logger(__name__)


@dataclass
class DegradationRule:
    """Rule for determining when to degrade service"""
    name: str
    condition: Callable[[], bool]
    target_level: DegradationLevel
    priority: int = 0  # Higher priority rules are checked first
    description: str = ""
    cooldown_seconds: float = 60.0  # Minimum time between rule activations


@dataclass
class DegradationEvent:
    """Event representing a degradation occurrence"""
    timestamp: float
    rule_name: str
    old_level: DegradationLevel
    new_level: DegradationLevel
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DegradationHandler:
    """
    Handler for managing system degradation based on various conditions
    """
    
    def __init__(self, fallback_service: FallbackService):
        self.fallback_service = fallback_service
        self.rules: List[DegradationRule] = []
        self.events: List[DegradationEvent] = []
        self.max_events = 1000  # Maximum events to keep in memory
        
        # Rule activation tracking
        self._rule_last_activated: Dict[str, float] = {}
        self._active_rules: Set[str] = set()
        
        # Monitoring
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        
        # Setup default rules
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Setup default degradation rules"""
        
        # Circuit breaker rules
        self.add_rule(DegradationRule(
            name="multiple_circuit_breakers_open",
            condition=self._check_multiple_circuit_breakers_open,
            target_level=DegradationLevel.MODERATE,
            priority=100,
            description="Multiple circuit breakers are open",
            cooldown_seconds=30.0
        ))
        
        self.add_rule(DegradationRule(
            name="critical_circuit_breakers_open",
            condition=self._check_critical_circuit_breakers_open,
            target_level=DegradationLevel.SEVERE,
            priority=200,
            description="Critical circuit breakers are open",
            cooldown_seconds=60.0
        ))
        
        # Memory and resource rules
        self.add_rule(DegradationRule(
            name="high_memory_usage",
            condition=self._check_high_memory_usage,
            target_level=DegradationLevel.MINOR,
            priority=50,
            description="High memory usage detected",
            cooldown_seconds=120.0
        ))
        
        # Error rate rules
        self.add_rule(DegradationRule(
            name="high_error_rate",
            condition=self._check_high_error_rate,
            target_level=DegradationLevel.MODERATE,
            priority=150,
            description="High error rate detected",
            cooldown_seconds=90.0
        ))
    
    def add_rule(self, rule: DegradationRule) -> None:
        """
        Add a degradation rule
        
        Args:
            rule: Degradation rule to add
        """
        with self._lock:
            self.rules.append(rule)
            # Sort rules by priority (highest first)
            self.rules.sort(key=lambda r: r.priority, reverse=True)
        
        logger.info("Degradation rule added",
                   name=rule.name,
                   priority=rule.priority,
                   target_level=rule.target_level.value)
    
    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a degradation rule
        
        Args:
            rule_name: Name of rule to remove
            
        Returns:
            True if rule was removed, False if not found
        """
        with self._lock:
            for i, rule in enumerate(self.rules):
                if rule.name == rule_name:
                    del self.rules[i]
                    self._active_rules.discard(rule_name)
                    logger.info("Degradation rule removed", name=rule_name)
                    return True
        
        return False
    
    def _check_multiple_circuit_breakers_open(self) -> bool:
        """Check if multiple circuit breakers are open"""
        try:
            circuit_breakers = get_all_circuit_breakers()
            open_count = sum(1 for cb in circuit_breakers.values() 
                           if cb.state == CircuitState.OPEN)
            return open_count >= 2
        except Exception as e:
            logger.error("Error checking circuit breakers", error=str(e))
            return False
    
    def _check_critical_circuit_breakers_open(self) -> bool:
        """Check if critical circuit breakers are open"""
        try:
            circuit_breakers = get_all_circuit_breakers()
            critical_services = ["database", "redis", "green_api"]
            
            for service in critical_services:
                if service in circuit_breakers:
                    if circuit_breakers[service].state == CircuitState.OPEN:
                        return True
            
            return False
        except Exception as e:
            logger.error("Error checking critical circuit breakers", error=str(e))
            return False
    
    def _check_high_memory_usage(self) -> bool:
        """Check if memory usage is high"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent > 85.0  # 85% memory usage threshold
        except ImportError:
            # psutil not available, skip this check
            return False
        except Exception as e:
            logger.error("Error checking memory usage", error=str(e))
            return False
    
    def _check_high_error_rate(self) -> bool:
        """Check if error rate is high"""
        try:
            # This would typically check application metrics
            # For now, we'll check circuit breaker failure rates
            circuit_breakers = get_all_circuit_breakers()
            
            high_failure_count = 0
            for cb in circuit_breakers.values():
                metrics = cb.get_metrics()
                if metrics.total_requests > 10 and metrics.failure_rate() > 0.5:
                    high_failure_count += 1
            
            return high_failure_count >= 2
        except Exception as e:
            logger.error("Error checking error rate", error=str(e))
            return False
    
    def _can_activate_rule(self, rule: DegradationRule) -> bool:
        """Check if a rule can be activated (considering cooldown)"""
        current_time = time.time()
        last_activated = self._rule_last_activated.get(rule.name, 0)
        
        return (current_time - last_activated) >= rule.cooldown_seconds
    
    def _record_event(self, rule_name: str, old_level: DegradationLevel, 
                     new_level: DegradationLevel, reason: str,
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a degradation event"""
        event = DegradationEvent(
            timestamp=time.time(),
            rule_name=rule_name,
            old_level=old_level,
            new_level=new_level,
            reason=reason,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.events.append(event)
            # Keep only the most recent events
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events:]
    
    async def evaluate_rules(self) -> Optional[DegradationLevel]:
        """
        Evaluate all degradation rules and return the highest degradation level needed
        
        Returns:
            Highest degradation level required, or None if no rules triggered
        """
        current_level = self.fallback_service.current_degradation_level
        highest_level = None
        triggered_rules = []
        
        with self._lock:
            rules_to_check = self.rules.copy()
        
        for rule in rules_to_check:
            try:
                # Check if rule can be activated
                if not self._can_activate_rule(rule):
                    continue
                
                # Evaluate rule condition
                if rule.condition():
                    triggered_rules.append(rule)
                    
                    # Track highest degradation level
                    if (highest_level is None or 
                        self._compare_degradation_levels(rule.target_level, highest_level) > 0):
                        highest_level = rule.target_level
                    
                    # Mark rule as activated
                    self._rule_last_activated[rule.name] = time.time()
                    self._active_rules.add(rule.name)
                    
                    logger.warning("Degradation rule triggered",
                                 rule=rule.name,
                                 target_level=rule.target_level.value,
                                 description=rule.description)
                else:
                    # Rule not triggered, remove from active rules
                    self._active_rules.discard(rule.name)
                    
            except Exception as e:
                logger.error("Error evaluating degradation rule",
                           rule=rule.name,
                           error=str(e))
        
        # Apply degradation if needed
        if highest_level and highest_level != current_level:
            reason = f"Rules triggered: {', '.join(r.name for r in triggered_rules)}"
            self.fallback_service.set_degradation_level(highest_level, reason)
            
            # Record event
            self._record_event(
                rule_name=f"combined_{len(triggered_rules)}_rules",
                old_level=current_level,
                new_level=highest_level,
                reason=reason,
                metadata={"triggered_rules": [r.name for r in triggered_rules]}
            )
        
        # Check for recovery (no rules triggered and currently degraded)
        elif not triggered_rules and current_level != DegradationLevel.NORMAL:
            # Gradual recovery - move one level towards normal
            recovery_level = self._get_recovery_level(current_level)
            if recovery_level != current_level:
                self.fallback_service.set_degradation_level(recovery_level, "Automatic recovery")
                
                self._record_event(
                    rule_name="automatic_recovery",
                    old_level=current_level,
                    new_level=recovery_level,
                    reason="No degradation rules triggered",
                    metadata={"recovery": True}
                )
        
        return highest_level
    
    def _compare_degradation_levels(self, level1: DegradationLevel, level2: DegradationLevel) -> int:
        """Compare degradation levels (higher is worse)"""
        level_order = {
            DegradationLevel.NORMAL: 0,
            DegradationLevel.MINOR: 1,
            DegradationLevel.MODERATE: 2,
            DegradationLevel.SEVERE: 3,
            DegradationLevel.CRITICAL: 4
        }
        
        return level_order[level1] - level_order[level2]
    
    def _get_recovery_level(self, current_level: DegradationLevel) -> DegradationLevel:
        """Get the next recovery level (one step towards normal)"""
        recovery_map = {
            DegradationLevel.CRITICAL: DegradationLevel.SEVERE,
            DegradationLevel.SEVERE: DegradationLevel.MODERATE,
            DegradationLevel.MODERATE: DegradationLevel.MINOR,
            DegradationLevel.MINOR: DegradationLevel.NORMAL,
            DegradationLevel.NORMAL: DegradationLevel.NORMAL
        }
        
        return recovery_map.get(current_level, DegradationLevel.NORMAL)
    
    async def start_monitoring(self, interval: float = 30.0) -> None:
        """
        Start continuous degradation monitoring
        
        Args:
            interval: Check interval in seconds
        """
        if self._monitoring:
            logger.warning("Degradation monitoring already started")
            return
        
        self._monitoring = True
        logger.info("Starting degradation monitoring", interval=interval)
        
        async def monitor_loop():
            while self._monitoring:
                try:
                    await self.evaluate_rules()
                    await asyncio.sleep(interval)
                except Exception as e:
                    logger.error("Degradation monitoring error", error=str(e))
                    await asyncio.sleep(min(interval, 30.0))
        
        self._monitor_task = asyncio.create_task(monitor_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop degradation monitoring"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Degradation monitoring stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current degradation handler status"""
        with self._lock:
            return {
                "current_level": self.fallback_service.current_degradation_level.value,
                "monitoring": self._monitoring,
                "total_rules": len(self.rules),
                "active_rules": list(self._active_rules),
                "recent_events": len([e for e in self.events if time.time() - e.timestamp < 3600]),  # Last hour
                "rules": [
                    {
                        "name": rule.name,
                        "priority": rule.priority,
                        "target_level": rule.target_level.value,
                        "description": rule.description,
                        "last_activated": self._rule_last_activated.get(rule.name),
                        "is_active": rule.name in self._active_rules
                    }
                    for rule in self.rules
                ]
            }
    
    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent degradation events"""
        with self._lock:
            recent_events = sorted(self.events, key=lambda e: e.timestamp, reverse=True)[:limit]
            
            return [
                {
                    "timestamp": event.timestamp,
                    "rule_name": event.rule_name,
                    "old_level": event.old_level.value,
                    "new_level": event.new_level.value,
                    "reason": event.reason,
                    "metadata": event.metadata
                }
                for event in recent_events
            ]


# Global degradation handler instance
degradation_handler = None


def get_degradation_handler() -> DegradationHandler:
    """Get or create global degradation handler instance"""
    global degradation_handler
    if degradation_handler is None:
        from app.services.fallback_service import fallback_service
        degradation_handler = DegradationHandler(fallback_service)
    return degradation_handler
