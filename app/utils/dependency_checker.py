"""
Dependency checker utilities for system monitoring
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import threading

from app.core.logging import get_logger
from app.services.health_checker import HealthChecker, DependencyStatus, SystemHealthStatus

logger = get_logger(__name__)


class DependencyPriority(Enum):
    """Priority levels for dependencies"""
    CRITICAL = "critical"      # System cannot function without this
    IMPORTANT = "important"    # System can function but with degraded performance
    OPTIONAL = "optional"      # System can function normally without this


@dataclass
class DependencyDefinition:
    """Definition of a system dependency"""
    name: str
    check_function: Callable
    priority: DependencyPriority
    timeout: float = 10.0
    description: str = ""
    required_for_startup: bool = False


class DependencyMonitor:
    """
    Monitor system dependencies and their health status
    """
    
    def __init__(self):
        self.dependencies: Dict[str, DependencyDefinition] = {}
        self.health_checker = HealthChecker()
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._status_cache: Dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        
        # Callbacks
        self._status_change_callbacks: List[Callable] = []
        self._critical_failure_callbacks: List[Callable] = []
    
    def register_dependency(self, dependency: DependencyDefinition) -> None:
        """
        Register a dependency for monitoring
        
        Args:
            dependency: Dependency definition
        """
        self.dependencies[dependency.name] = dependency
        logger.info("Dependency registered", 
                   name=dependency.name,
                   priority=dependency.priority.value,
                   required_for_startup=dependency.required_for_startup)
    
    def register_status_change_callback(self, callback: Callable[[str, DependencyStatus, DependencyStatus], None]) -> None:
        """
        Register callback for dependency status changes
        
        Args:
            callback: Function to call when status changes (name, old_status, new_status)
        """
        self._status_change_callbacks.append(callback)
    
    def register_critical_failure_callback(self, callback: Callable[[str, Exception], None]) -> None:
        """
        Register callback for critical dependency failures
        
        Args:
            callback: Function to call when critical dependency fails (name, exception)
        """
        self._critical_failure_callbacks.append(callback)
    
    async def check_dependency(self, name: str) -> DependencyStatus:
        """
        Check a specific dependency
        
        Args:
            name: Dependency name
            
        Returns:
            Dependency status
        """
        if name not in self.dependencies:
            logger.error("Unknown dependency", name=name)
            return DependencyStatus.UNKNOWN
        
        dependency = self.dependencies[name]
        
        try:
            # Execute check with timeout
            result = await asyncio.wait_for(
                dependency.check_function(),
                timeout=dependency.timeout
            )
            
            if hasattr(result, 'status'):
                return result.status
            else:
                # Assume healthy if check doesn't return status
                return DependencyStatus.HEALTHY
                
        except asyncio.TimeoutError:
            logger.error("Dependency check timeout", 
                        name=name, 
                        timeout=dependency.timeout)
            return DependencyStatus.UNHEALTHY
        
        except Exception as e:
            logger.error("Dependency check failed", 
                        name=name, 
                        error=str(e))
            
            # Call critical failure callbacks for critical dependencies
            if dependency.priority == DependencyPriority.CRITICAL:
                for callback in self._critical_failure_callbacks:
                    try:
                        callback(name, e)
                    except Exception as cb_error:
                        logger.error("Critical failure callback failed", 
                                   error=str(cb_error))
            
            return DependencyStatus.UNHEALTHY
    
    async def check_all_dependencies(self) -> Dict[str, DependencyStatus]:
        """
        Check all registered dependencies
        
        Returns:
            Dict mapping dependency names to their status
        """
        if not self.dependencies:
            return {}
        
        # Create tasks for all dependency checks
        tasks = {
            name: self.check_dependency(name)
            for name in self.dependencies.keys()
        }
        
        # Execute all checks concurrently
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Process results
        status_map = {}
        for i, (name, task) in enumerate(tasks.items()):
            result = results[i]
            if isinstance(result, Exception):
                status_map[name] = DependencyStatus.UNHEALTHY
                logger.error("Dependency check exception", 
                           name=name, 
                           error=str(result))
            else:
                status_map[name] = result
        
        # Check for status changes and call callbacks
        with self._cache_lock:
            for name, new_status in status_map.items():
                old_status = self._status_cache.get(name)
                if old_status != new_status:
                    self._status_cache[name] = new_status
                    
                    # Call status change callbacks
                    for callback in self._status_change_callbacks:
                        try:
                            callback(name, old_status, new_status)
                        except Exception as cb_error:
                            logger.error("Status change callback failed", 
                                       error=str(cb_error))
        
        return status_map
    
    async def check_startup_dependencies(self) -> bool:
        """
        Check dependencies required for startup
        
        Returns:
            True if all startup dependencies are healthy
        """
        startup_deps = {
            name: dep for name, dep in self.dependencies.items()
            if dep.required_for_startup
        }
        
        if not startup_deps:
            return True
        
        logger.info("Checking startup dependencies", 
                   count=len(startup_deps),
                   dependencies=list(startup_deps.keys()))
        
        status_map = {}
        for name in startup_deps.keys():
            status_map[name] = await self.check_dependency(name)
        
        # Check if all startup dependencies are healthy
        failed_deps = [
            name for name, status in status_map.items()
            if status == DependencyStatus.UNHEALTHY
        ]
        
        if failed_deps:
            logger.error("Startup dependencies failed", 
                        failed_dependencies=failed_deps)
            return False
        
        logger.info("All startup dependencies healthy")
        return True
    
    def get_dependency_summary(self) -> Dict[str, Any]:
        """
        Get summary of all dependencies and their current status
        
        Returns:
            Summary dict with dependency information
        """
        with self._cache_lock:
            summary = {
                "total_dependencies": len(self.dependencies),
                "dependencies": {},
                "status_counts": {status.value: 0 for status in DependencyStatus},
                "priority_counts": {priority.value: 0 for priority in DependencyPriority}
            }
            
            for name, dep in self.dependencies.items():
                current_status = self._status_cache.get(name, DependencyStatus.UNKNOWN)
                
                summary["dependencies"][name] = {
                    "priority": dep.priority.value,
                    "status": current_status.value,
                    "description": dep.description,
                    "required_for_startup": dep.required_for_startup,
                    "timeout": dep.timeout
                }
                
                summary["status_counts"][current_status.value] += 1
                summary["priority_counts"][dep.priority.value] += 1
            
            return summary
    
    async def start_monitoring(self, interval: float = 60.0) -> None:
        """
        Start continuous dependency monitoring
        
        Args:
            interval: Check interval in seconds
        """
        if self._monitoring:
            logger.warning("Dependency monitoring already started")
            return
        
        self._monitoring = True
        logger.info("Starting dependency monitoring", interval=interval)
        
        async def monitor_loop():
            while self._monitoring:
                try:
                    await self.check_all_dependencies()
                    await asyncio.sleep(interval)
                except Exception as e:
                    logger.error("Dependency monitoring error", error=str(e))
                    await asyncio.sleep(min(interval, 30.0))  # Shorter sleep on error
        
        self._monitor_task = asyncio.create_task(monitor_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop dependency monitoring"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Dependency monitoring stopped")


# Global dependency monitor instance
dependency_monitor = DependencyMonitor()


# Default dependency definitions
def create_default_dependencies() -> List[DependencyDefinition]:
    """Create default dependency definitions for the system"""
    health_checker = HealthChecker()
    
    return [
        DependencyDefinition(
            name="database",
            check_function=lambda: health_checker.check_database(None),  # Will need DB session
            priority=DependencyPriority.CRITICAL,
            timeout=10.0,
            description="PostgreSQL database connection",
            required_for_startup=True
        ),
        
        DependencyDefinition(
            name="redis",
            check_function=health_checker.check_redis,
            priority=DependencyPriority.CRITICAL,
            timeout=5.0,
            description="Redis cache and session storage",
            required_for_startup=True
        ),
        
        DependencyDefinition(
            name="green_api",
            check_function=health_checker.check_green_api,
            priority=DependencyPriority.IMPORTANT,
            timeout=15.0,
            description="Green API for WhatsApp messaging",
            required_for_startup=False
        ),
        
        DependencyDefinition(
            name="deepseek_api",
            check_function=health_checker.check_deepseek_api,
            priority=DependencyPriority.IMPORTANT,
            timeout=20.0,
            description="DeepSeek API for AI processing",
            required_for_startup=False
        ),
        
        DependencyDefinition(
            name="celery_workers",
            check_function=health_checker.check_celery_workers,
            priority=DependencyPriority.IMPORTANT,
            timeout=10.0,
            description="Celery background workers",
            required_for_startup=False
        )
    ]


def register_default_dependencies() -> None:
    """Register default dependencies with the monitor"""
    for dep in create_default_dependencies():
        dependency_monitor.register_dependency(dep)


# Callback functions for common scenarios
def log_status_change(name: str, old_status: Optional[DependencyStatus], new_status: DependencyStatus) -> None:
    """Log dependency status changes"""
    if old_status is None:
        logger.info("Dependency status initialized", 
                   name=name, 
                   status=new_status.value)
    else:
        logger.warning("Dependency status changed", 
                      name=name, 
                      old_status=old_status.value, 
                      new_status=new_status.value)


def log_critical_failure(name: str, exception: Exception) -> None:
    """Log critical dependency failures"""
    logger.critical("Critical dependency failed", 
                    name=name, 
                    error=str(exception),
                    exception_type=type(exception).__name__)


# Register default callbacks
dependency_monitor.register_status_change_callback(log_status_change)
dependency_monitor.register_critical_failure_callback(log_critical_failure)
