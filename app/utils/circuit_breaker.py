"""
Circuit Breaker implementation for external service reliability
"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
from collections import deque

from app.core.logging import get_logger

# Import metrics (with try/catch to avoid import errors if prometheus not available)
try:
    from app.monitoring.reliability_metrics import get_reliability_metrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Number of failures to open circuit
    recovery_timeout: float = 60.0  # Seconds to wait before trying half-open
    success_threshold: int = 3  # Successes needed in half-open to close
    timeout: float = 30.0  # Request timeout in seconds
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures
    
    # Sliding window configuration
    window_size: int = 100  # Size of sliding window for failure tracking
    minimum_requests: int = 10  # Minimum requests before considering failure rate


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    circuit_open_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    current_state: CircuitState = CircuitState.CLOSED
    
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    def failure_rate(self) -> float:
        """Calculate failure rate"""
        return 1.0 - self.success_rate()


class CircuitBreaker:
    """
    Circuit breaker implementation with sliding window failure tracking
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.next_attempt_time: Optional[float] = None
        
        # Sliding window for tracking requests
        self.request_window = deque(maxlen=config.window_size)
        
        # Metrics
        self.metrics = CircuitBreakerMetrics()
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info("Circuit breaker initialized", 
                   name=name, 
                   config=config.__dict__)
    
    def _record_request(self, success: bool) -> None:
        """Record a request result in the sliding window"""
        timestamp = time.time()
        self.request_window.append((timestamp, success))
        
        # Update metrics
        self.metrics.total_requests += 1
        if success:
            self.metrics.successful_requests += 1
            self.metrics.last_success_time = datetime.now()
        else:
            self.metrics.failed_requests += 1
            self.metrics.last_failure_time = datetime.now()
    
    def _get_failure_rate(self) -> float:
        """Calculate current failure rate from sliding window"""
        if len(self.request_window) < self.config.minimum_requests:
            return 0.0
        
        failures = sum(1 for _, success in self.request_window if not success)
        return failures / len(self.request_window)
    
    def _should_open_circuit(self) -> bool:
        """Check if circuit should be opened based on failure rate"""
        if len(self.request_window) < self.config.minimum_requests:
            return False
        
        failure_rate = self._get_failure_rate()
        threshold_rate = self.config.failure_threshold / self.config.window_size
        
        return failure_rate >= threshold_rate
    
    def _can_attempt_request(self) -> bool:
        """Check if a request can be attempted based on current state"""
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        
        elif self.state == CircuitState.OPEN:
            if (self.next_attempt_time and 
                current_time >= self.next_attempt_time):
                # Transition to half-open
                with self._lock:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    self.metrics.current_state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to half-open", 
                               name=self.name)
                return True
            return False
        
        elif self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def _handle_success(self) -> None:
        """Handle successful request"""
        with self._lock:
            self._record_request(True)

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    # Close the circuit
                    old_state = self.state
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.metrics.current_state = CircuitState.CLOSED

                    # Record metrics
                    if METRICS_AVAILABLE:
                        metrics = get_reliability_metrics()
                        metrics.record_circuit_breaker_state_change(
                            self.name, old_state.value, CircuitState.CLOSED.value
                        )

                    logger.info("Circuit breaker closed after successful recovery",
                               name=self.name)
    
    def _handle_failure(self) -> None:
        """Handle failed request"""
        with self._lock:
            self._record_request(False)
            self.last_failure_time = time.time()

            if self.state == CircuitState.CLOSED:
                if self._should_open_circuit():
                    # Open the circuit
                    old_state = self.state
                    self.state = CircuitState.OPEN
                    self.next_attempt_time = time.time() + self.config.recovery_timeout
                    self.metrics.circuit_open_count += 1
                    self.metrics.current_state = CircuitState.OPEN

                    # Record metrics
                    if METRICS_AVAILABLE:
                        metrics = get_reliability_metrics()
                        metrics.record_circuit_breaker_state_change(
                            self.name, old_state.value, CircuitState.OPEN.value
                        )
                        metrics.record_circuit_breaker_failure(self.name, "threshold_exceeded")

                    logger.warning("Circuit breaker opened due to failures",
                                 name=self.name,
                                 failure_rate=self._get_failure_rate())

            elif self.state == CircuitState.HALF_OPEN:
                # Go back to open
                old_state = self.state
                self.state = CircuitState.OPEN
                self.next_attempt_time = time.time() + self.config.recovery_timeout
                self.metrics.current_state = CircuitState.OPEN

                # Record metrics
                if METRICS_AVAILABLE:
                    metrics = get_reliability_metrics()
                    metrics.record_circuit_breaker_state_change(
                        self.name, old_state.value, CircuitState.OPEN.value
                    )
                    metrics.record_circuit_breaker_failure(self.name, "half_open_failure")

                logger.warning("Circuit breaker reopened during half-open test",
                             name=self.name)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        """
        if not self._can_attempt_request():
            logger.warning("Circuit breaker is open, failing fast",
                         name=self.name)

            # Record metrics
            if METRICS_AVAILABLE:
                metrics = get_reliability_metrics()
                metrics.record_circuit_breaker_request(self.name, self.state.value, "blocked")

            raise CircuitBreakerOpenException(
                f"Circuit breaker '{self.name}' is open"
            )
        
        start_time = time.time()

        try:
            # Apply timeout if it's an async function
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout
                )
            else:
                result = func(*args, **kwargs)

            response_time = time.time() - start_time

            # Record success metrics
            if METRICS_AVAILABLE:
                metrics = get_reliability_metrics()
                metrics.record_circuit_breaker_request(
                    self.name, self.state.value, "success", response_time
                )

            self._handle_success()
            return result
            
        except self.config.expected_exception as e:
            response_time = time.time() - start_time

            # Record failure metrics
            if METRICS_AVAILABLE:
                metrics = get_reliability_metrics()
                metrics.record_circuit_breaker_request(
                    self.name, self.state.value, "failure", response_time
                )
                metrics.record_circuit_breaker_failure(self.name, "exception")

            self._handle_failure()
            logger.error("Circuit breaker recorded failure",
                        name=self.name,
                        error=str(e),
                        state=self.state.value)
            raise

        except asyncio.TimeoutError as e:
            response_time = time.time() - start_time

            # Record timeout metrics
            if METRICS_AVAILABLE:
                metrics = get_reliability_metrics()
                metrics.record_circuit_breaker_request(
                    self.name, self.state.value, "timeout", response_time
                )
                metrics.record_circuit_breaker_failure(self.name, "timeout")

            self._handle_failure()
            logger.error("Circuit breaker timeout",
                        name=self.name,
                        timeout=self.config.timeout)
            raise CircuitBreakerTimeoutException(
                f"Circuit breaker '{self.name}' timeout after {self.config.timeout}s"
            ) from e
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current metrics"""
        with self._lock:
            self.metrics.current_state = self.state
            return self.metrics
    
    def reset(self) -> None:
        """Reset circuit breaker to closed state"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.next_attempt_time = None
            self.request_window.clear()
            self.metrics = CircuitBreakerMetrics()
            logger.info("Circuit breaker reset", name=self.name)


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class CircuitBreakerTimeoutException(Exception):
    """Exception raised when circuit breaker times out"""
    pass


# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """
    Get or create a circuit breaker instance
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            if config is None:
                config = CircuitBreakerConfig()
            _circuit_breakers[name] = CircuitBreaker(name, config)
        return _circuit_breakers[name]


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """Get all registered circuit breakers"""
    with _registry_lock:
        return _circuit_breakers.copy()


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers"""
    with _registry_lock:
        for cb in _circuit_breakers.values():
            cb.reset()
        logger.info("All circuit breakers reset")
