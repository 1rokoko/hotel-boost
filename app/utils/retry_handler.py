"""
Universal retry handler with exponential backoff and jitter
"""

import asyncio
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union, List
from dataclasses import dataclass
from enum import Enum
import functools

from app.core.logging import get_logger

logger = get_logger(__name__)


class RetryStrategy(Enum):
    """Retry strategies"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_retries: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Base for exponential backoff
    jitter: bool = True  # Add random jitter to delays
    jitter_range: Tuple[float, float] = (0.1, 0.1)  # Jitter range (min, max)
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    
    # Exception handling
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()
    
    # Conditional retry
    retry_condition: Optional[Callable[[Exception], bool]] = None
    
    # Callbacks
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
    on_failure: Optional[Callable[[Exception, int], None]] = None


class RetryHandler:
    """
    Universal retry handler with multiple strategies
    """
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self._fibonacci_cache = [1, 1]  # Cache for fibonacci sequence
    
    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if we should retry based on exception and attempt count
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number (0-based)
            
        Returns:
            True if should retry, False otherwise
        """
        # Check attempt count
        if attempt >= self.config.max_retries:
            return False
        
        # Check non-retryable exceptions first
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False
        
        # Check retryable exceptions
        if not isinstance(exception, self.config.retryable_exceptions):
            return False
        
        # Check custom retry condition
        if self.config.retry_condition:
            return self.config.retry_condition(exception)
        
        return True
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry attempt based on strategy
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * (attempt + 1)
        
        elif self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay
        
        elif self.config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            # Extend fibonacci sequence if needed
            while len(self._fibonacci_cache) <= attempt + 1:
                next_fib = self._fibonacci_cache[-1] + self._fibonacci_cache[-2]
                self._fibonacci_cache.append(next_fib)
            
            delay = self.config.base_delay * self._fibonacci_cache[attempt]
        
        else:
            delay = self.config.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter if enabled
        if self.config.jitter:
            jitter_min, jitter_max = self.config.jitter_range
            jitter_factor = 1 + random.uniform(-jitter_min, jitter_max)
            delay *= jitter_factor
        
        return max(0, delay)
    
    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute async function with retry logic
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries failed
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                # Log successful retry if this wasn't the first attempt
                if attempt > 0:
                    logger.info("Function succeeded after retry",
                               function=func.__name__,
                               attempt=attempt + 1,
                               total_attempts=self.config.max_retries + 1)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry
                if not self._should_retry(e, attempt):
                    logger.error("Function failed, not retrying",
                               function=func.__name__,
                               attempt=attempt + 1,
                               error=str(e),
                               error_type=type(e).__name__)
                    break
                
                # Calculate delay for next attempt
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    
                    logger.warning("Function failed, retrying",
                                 function=func.__name__,
                                 attempt=attempt + 1,
                                 max_retries=self.config.max_retries,
                                 delay=delay,
                                 error=str(e),
                                 error_type=type(e).__name__)
                    
                    # Call retry callback if provided
                    if self.config.on_retry:
                        try:
                            self.config.on_retry(attempt, e, delay)
                        except Exception as callback_error:
                            logger.error("Retry callback failed",
                                       error=str(callback_error))
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
                else:
                    logger.error("Function failed, max retries exceeded",
                               function=func.__name__,
                               attempts=attempt + 1,
                               error=str(e),
                               error_type=type(e).__name__)
        
        # Call failure callback if provided
        if self.config.on_failure and last_exception:
            try:
                self.config.on_failure(last_exception, self.config.max_retries + 1)
            except Exception as callback_error:
                logger.error("Failure callback failed",
                           error=str(callback_error))
        
        # Raise the last exception
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Retry handler failed without exception")
    
    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute sync function with retry logic
        
        Args:
            func: Sync function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries failed
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                # Log successful retry if this wasn't the first attempt
                if attempt > 0:
                    logger.info("Function succeeded after retry",
                               function=func.__name__,
                               attempt=attempt + 1,
                               total_attempts=self.config.max_retries + 1)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry
                if not self._should_retry(e, attempt):
                    logger.error("Function failed, not retrying",
                               function=func.__name__,
                               attempt=attempt + 1,
                               error=str(e),
                               error_type=type(e).__name__)
                    break
                
                # Calculate delay for next attempt
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    
                    logger.warning("Function failed, retrying",
                                 function=func.__name__,
                                 attempt=attempt + 1,
                                 max_retries=self.config.max_retries,
                                 delay=delay,
                                 error=str(e),
                                 error_type=type(e).__name__)
                    
                    # Call retry callback if provided
                    if self.config.on_retry:
                        try:
                            self.config.on_retry(attempt, e, delay)
                        except Exception as callback_error:
                            logger.error("Retry callback failed",
                                       error=str(callback_error))
                    
                    # Wait before retry
                    time.sleep(delay)
                else:
                    logger.error("Function failed, max retries exceeded",
                               function=func.__name__,
                               attempts=attempt + 1,
                               error=str(e),
                               error_type=type(e).__name__)
        
        # Call failure callback if provided
        if self.config.on_failure and last_exception:
            try:
                self.config.on_failure(last_exception, self.config.max_retries + 1)
            except Exception as callback_error:
                logger.error("Failure callback failed",
                           error=str(callback_error))
        
        # Raise the last exception
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Retry handler failed without exception")


# Convenience function for quick retry
async def retry_async(func: Callable, config: Optional[RetryConfig] = None, *args, **kwargs) -> Any:
    """
    Quick async retry function
    
    Args:
        func: Function to retry
        config: Retry configuration (uses default if None)
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
    """
    if config is None:
        config = RetryConfig()
    
    handler = RetryHandler(config)
    return await handler.execute_async(func, *args, **kwargs)


def retry_sync(func: Callable, config: Optional[RetryConfig] = None, *args, **kwargs) -> Any:
    """
    Quick sync retry function
    
    Args:
        func: Function to retry
        config: Retry configuration (uses default if None)
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
    """
    if config is None:
        config = RetryConfig()
    
    handler = RetryHandler(config)
    return handler.execute_sync(func, *args, **kwargs)
