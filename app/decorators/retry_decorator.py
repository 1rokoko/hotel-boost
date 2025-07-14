"""
Retry decorators for easy function decoration
"""

import asyncio
import functools
from typing import Callable, Optional, Type, Tuple, Union

from app.utils.retry_handler import RetryHandler, RetryConfig, RetryStrategy
from app.core.logging import get_logger

logger = get_logger(__name__)


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (),
    retry_condition: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    on_failure: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator for adding retry logic to functions
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delays
        strategy: Retry strategy to use
        retryable_exceptions: Tuple of exceptions that should trigger retries
        non_retryable_exceptions: Tuple of exceptions that should not trigger retries
        retry_condition: Custom function to determine if retry should happen
        on_retry: Callback function called on each retry
        on_failure: Callback function called when all retries fail
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        config = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            strategy=strategy,
            retryable_exceptions=retryable_exceptions,
            non_retryable_exceptions=non_retryable_exceptions,
            retry_condition=retry_condition,
            on_retry=on_retry,
            on_failure=on_failure
        )
        
        handler = RetryHandler(config)
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await handler.execute_async(func, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return handler.execute_sync(func, *args, **kwargs)
            return sync_wrapper
    
    return decorator


def retry_on_exception(*exception_types: Type[Exception], **kwargs):
    """
    Decorator that retries only on specific exception types
    
    Args:
        *exception_types: Exception types to retry on
        **kwargs: Additional retry configuration
    
    Returns:
        Decorated function
    """
    kwargs['retryable_exceptions'] = exception_types
    return retry(**kwargs)


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    **kwargs
):
    """
    Decorator for exponential backoff retry
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        **kwargs: Additional retry configuration
    
    Returns:
        Decorated function
    """
    return retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        **kwargs
    )


def retry_with_linear_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    **kwargs
):
    """
    Decorator for linear backoff retry
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        **kwargs: Additional retry configuration
    
    Returns:
        Decorated function
    """
    return retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        strategy=RetryStrategy.LINEAR_BACKOFF,
        **kwargs
    )


def retry_with_fixed_delay(
    max_retries: int = 3,
    delay: float = 1.0,
    **kwargs
):
    """
    Decorator for fixed delay retry
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Fixed delay between retries in seconds
        **kwargs: Additional retry configuration
    
    Returns:
        Decorated function
    """
    return retry(
        max_retries=max_retries,
        base_delay=delay,
        max_delay=delay,
        strategy=RetryStrategy.FIXED_DELAY,
        **kwargs
    )


def retry_database_operations(max_retries: int = 5, base_delay: float = 0.5):
    """
    Specialized retry decorator for database operations
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
    
    Returns:
        Decorated function
    """
    from sqlalchemy.exc import (
        DisconnectionError, 
        TimeoutError, 
        OperationalError,
        DatabaseError
    )
    
    return retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=30.0,
        retryable_exceptions=(
            DisconnectionError,
            TimeoutError,
            OperationalError,
            DatabaseError,
            ConnectionError
        ),
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True
    )


def retry_http_requests(max_retries: int = 3, base_delay: float = 1.0):
    """
    Specialized retry decorator for HTTP requests
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
    
    Returns:
        Decorated function
    """
    import httpx
    
    def should_retry_http(exception: Exception) -> bool:
        """Custom retry condition for HTTP requests"""
        if isinstance(exception, httpx.HTTPStatusError):
            # Retry on server errors and rate limiting
            return exception.response.status_code >= 500 or exception.response.status_code == 429
        return True
    
    return retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=60.0,
        retryable_exceptions=(
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
            ConnectionError
        ),
        retry_condition=should_retry_http,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True
    )


def retry_redis_operations(max_retries: int = 3, base_delay: float = 0.1):
    """
    Specialized retry decorator for Redis operations
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
    
    Returns:
        Decorated function
    """
    import redis
    
    return retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=5.0,
        retryable_exceptions=(
            redis.ConnectionError,
            redis.TimeoutError,
            redis.BusyLoadingError,
            ConnectionError
        ),
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True
    )


def retry_celery_tasks(max_retries: int = 3, base_delay: float = 2.0):
    """
    Specialized retry decorator for Celery tasks
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
    
    Returns:
        Decorated function
    """
    from celery.exceptions import Retry, WorkerLostError
    
    return retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=300.0,  # 5 minutes max delay for tasks
        retryable_exceptions=(
            ConnectionError,
            TimeoutError,
            WorkerLostError,
            Exception  # Celery tasks can retry on any exception
        ),
        non_retryable_exceptions=(Retry,),  # Don't double-retry Celery retries
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True
    )


# Convenience decorators with common configurations
quick_retry = retry(max_retries=2, base_delay=0.5, max_delay=5.0)
standard_retry = retry(max_retries=3, base_delay=1.0, max_delay=30.0)
aggressive_retry = retry(max_retries=5, base_delay=2.0, max_delay=60.0)
patient_retry = retry(max_retries=10, base_delay=5.0, max_delay=300.0)
