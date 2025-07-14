"""
Async processing optimization utilities for WhatsApp Hotel Bot
Provides async/await pattern optimization, concurrent processing, and event loop tuning
"""

import asyncio
import time
import weakref
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Awaitable, TypeVar, Generic
from dataclasses import dataclass, field
from collections import deque, defaultdict
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
import multiprocessing

import structlog
from app.core.logging import get_logger
from app.core.metrics import track_async_operation

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class AsyncMetrics:
    """Async operation metrics"""
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    concurrent_operations: int = 0
    memory_usage_mb: float = 0.0


@dataclass
class ConcurrencyLimits:
    """Concurrency limits configuration"""
    max_concurrent_tasks: int = 100
    max_concurrent_db_operations: int = 20
    max_concurrent_api_calls: int = 10
    max_concurrent_file_operations: int = 5
    task_timeout_seconds: float = 30.0
    batch_size: int = 50


class AsyncTaskPool:
    """Optimized async task pool with concurrency control"""
    
    def __init__(self, limits: Optional[ConcurrencyLimits] = None):
        self.limits = limits or ConcurrencyLimits()
        self.logger = logger.bind(component="async_task_pool")
        
        # Semaphores for different operation types
        self.general_semaphore = asyncio.Semaphore(self.limits.max_concurrent_tasks)
        self.db_semaphore = asyncio.Semaphore(self.limits.max_concurrent_db_operations)
        self.api_semaphore = asyncio.Semaphore(self.limits.max_concurrent_api_calls)
        self.file_semaphore = asyncio.Semaphore(self.limits.max_concurrent_file_operations)
        
        # Task tracking
        self.active_tasks: weakref.WeakSet = weakref.WeakSet()
        self.completed_tasks: deque = deque(maxlen=1000)
        self.task_metrics: Dict[str, List[AsyncMetrics]] = defaultdict(list)
        
        # Thread pools for CPU-bound and I/O-bound operations
        self.cpu_executor = ThreadPoolExecutor(
            max_workers=min(4, multiprocessing.cpu_count()),
            thread_name_prefix="async_cpu"
        )
        self.io_executor = ThreadPoolExecutor(
            max_workers=20,
            thread_name_prefix="async_io"
        )
    
    async def execute_with_semaphore(
        self,
        coro: Awaitable[T],
        operation_type: str = "general",
        timeout: Optional[float] = None
    ) -> T:
        """Execute coroutine with appropriate semaphore"""
        semaphore_map = {
            "general": self.general_semaphore,
            "database": self.db_semaphore,
            "api": self.api_semaphore,
            "file": self.file_semaphore
        }
        
        semaphore = semaphore_map.get(operation_type, self.general_semaphore)
        timeout = timeout or self.limits.task_timeout_seconds
        
        start_time = datetime.utcnow()
        metrics = AsyncMetrics(
            operation_name=operation_type,
            start_time=start_time,
            concurrent_operations=len(self.active_tasks)
        )
        
        async with semaphore:
            try:
                result = await asyncio.wait_for(coro, timeout=timeout)
                metrics.success = True
                return result
                
            except asyncio.TimeoutError as e:
                metrics.error = f"Timeout after {timeout}s"
                metrics.success = False
                self.logger.warning("Async operation timeout", 
                                  operation_type=operation_type, 
                                  timeout=timeout)
                raise
                
            except Exception as e:
                metrics.error = str(e)
                metrics.success = False
                self.logger.error("Async operation failed", 
                                operation_type=operation_type, 
                                error=str(e))
                raise
                
            finally:
                metrics.end_time = datetime.utcnow()
                metrics.duration_ms = (metrics.end_time - metrics.start_time).total_seconds() * 1000
                
                # Track metrics
                self.task_metrics[operation_type].append(metrics)
                track_async_operation(operation_type, metrics.duration_ms / 1000, metrics.success)
    
    async def execute_batch(
        self,
        coroutines: List[Awaitable[T]],
        operation_type: str = "general",
        batch_size: Optional[int] = None,
        return_exceptions: bool = True
    ) -> List[T]:
        """Execute coroutines in batches with concurrency control"""
        batch_size = batch_size or self.limits.batch_size
        results = []
        
        for i in range(0, len(coroutines), batch_size):
            batch = coroutines[i:i + batch_size]
            
            # Execute batch with semaphore control
            batch_tasks = [
                self.execute_with_semaphore(coro, operation_type)
                for coro in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=return_exceptions)
            results.extend(batch_results)
            
            # Small delay between batches to prevent overwhelming
            if i + batch_size < len(coroutines):
                await asyncio.sleep(0.01)
        
        return results
    
    async def execute_with_retry(
        self,
        coro_factory: Callable[[], Awaitable[T]],
        operation_type: str = "general",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        exponential_backoff: bool = True
    ) -> T:
        """Execute coroutine with retry logic"""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                coro = coro_factory()
                return await self.execute_with_semaphore(coro, operation_type)
                
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt) if exponential_backoff else retry_delay
                    self.logger.warning("Async operation failed, retrying",
                                      operation_type=operation_type,
                                      attempt=attempt + 1,
                                      max_retries=max_retries,
                                      delay=delay,
                                      error=str(e))
                    await asyncio.sleep(delay)
                else:
                    self.logger.error("Async operation failed after all retries",
                                    operation_type=operation_type,
                                    attempts=max_retries + 1,
                                    error=str(e))
        
        raise last_exception
    
    async def run_in_thread(
        self,
        func: Callable,
        *args,
        executor_type: str = "io",
        **kwargs
    ) -> Any:
        """Run blocking function in thread pool"""
        executor = self.io_executor if executor_type == "io" else self.cpu_executor
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, func, *args)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get async performance statistics"""
        stats = {
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "operation_stats": {}
        }
        
        for operation_type, metrics_list in self.task_metrics.items():
            if not metrics_list:
                continue
            
            successful_metrics = [m for m in metrics_list if m.success]
            failed_metrics = [m for m in metrics_list if not m.success]
            
            if successful_metrics:
                avg_duration = sum(m.duration_ms for m in successful_metrics) / len(successful_metrics)
                max_duration = max(m.duration_ms for m in successful_metrics)
                min_duration = min(m.duration_ms for m in successful_metrics)
            else:
                avg_duration = max_duration = min_duration = 0
            
            stats["operation_stats"][operation_type] = {
                "total_operations": len(metrics_list),
                "successful_operations": len(successful_metrics),
                "failed_operations": len(failed_metrics),
                "success_rate": len(successful_metrics) / len(metrics_list) * 100,
                "avg_duration_ms": avg_duration,
                "max_duration_ms": max_duration,
                "min_duration_ms": min_duration
            }
        
        return stats
    
    async def cleanup(self):
        """Cleanup resources"""
        # Cancel active tasks
        for task in list(self.active_tasks):
            if not task.done():
                task.cancel()
        
        # Shutdown thread pools
        self.cpu_executor.shutdown(wait=True)
        self.io_executor.shutdown(wait=True)
        
        self.logger.info("Async task pool cleaned up")


class AsyncContextManager:
    """Context manager for optimized async operations"""
    
    def __init__(self, task_pool: AsyncTaskPool):
        self.task_pool = task_pool
        self.logger = logger.bind(component="async_context")
    
    @asynccontextmanager
    async def database_operation(self, timeout: float = 10.0):
        """Context manager for database operations"""
        async with self.task_pool.db_semaphore:
            start_time = time.time()
            try:
                yield
            finally:
                duration = (time.time() - start_time) * 1000
                self.logger.debug("Database operation completed", duration_ms=duration)
    
    @asynccontextmanager
    async def api_operation(self, timeout: float = 30.0):
        """Context manager for API operations"""
        async with self.task_pool.api_semaphore:
            start_time = time.time()
            try:
                yield
            finally:
                duration = (time.time() - start_time) * 1000
                self.logger.debug("API operation completed", duration_ms=duration)
    
    @asynccontextmanager
    async def file_operation(self, timeout: float = 5.0):
        """Context manager for file operations"""
        async with self.task_pool.file_semaphore:
            start_time = time.time()
            try:
                yield
            finally:
                duration = (time.time() - start_time) * 1000
                self.logger.debug("File operation completed", duration_ms=duration)


class AsyncOptimizer:
    """Main async optimization coordinator"""
    
    def __init__(self, limits: Optional[ConcurrencyLimits] = None):
        self.limits = limits or ConcurrencyLimits()
        self.task_pool = AsyncTaskPool(self.limits)
        self.context_manager = AsyncContextManager(self.task_pool)
        self.logger = logger.bind(component="async_optimizer")
        
        # Event loop optimization
        self._optimize_event_loop()
    
    def _optimize_event_loop(self):
        """Optimize event loop settings"""
        try:
            loop = asyncio.get_event_loop()
            
            # Set debug mode in development
            if hasattr(loop, 'set_debug'):
                loop.set_debug(False)  # Disable in production for performance
            
            # Optimize task factory if available
            if hasattr(loop, 'set_task_factory'):
                loop.set_task_factory(self._optimized_task_factory)
            
            self.logger.info("Event loop optimized")
            
        except Exception as e:
            self.logger.warning("Failed to optimize event loop", error=str(e))
    
    def _optimized_task_factory(self, loop, coro):
        """Optimized task factory for better performance"""
        task = asyncio.Task(coro, loop=loop)
        
        # Add task to tracking
        self.task_pool.active_tasks.add(task)
        
        # Add completion callback
        task.add_done_callback(self._task_completion_callback)
        
        return task
    
    def _task_completion_callback(self, task):
        """Callback for task completion"""
        try:
            # Remove from active tasks (WeakSet handles this automatically)
            self.task_pool.completed_tasks.append({
                "completed_at": datetime.utcnow(),
                "success": not task.exception(),
                "exception": str(task.exception()) if task.exception() else None
            })
        except Exception as e:
            self.logger.warning("Error in task completion callback", error=str(e))


# Global async optimizer instance
async_optimizer: Optional[AsyncOptimizer] = None


def get_async_optimizer() -> AsyncOptimizer:
    """Get the global async optimizer instance"""
    global async_optimizer
    if async_optimizer is None:
        async_optimizer = AsyncOptimizer()
    return async_optimizer


# Convenience functions
async def optimized_gather(*coroutines, operation_type: str = "general", return_exceptions: bool = True):
    """Optimized version of asyncio.gather with concurrency control"""
    optimizer = get_async_optimizer()
    return await optimizer.task_pool.execute_batch(
        list(coroutines),
        operation_type=operation_type,
        return_exceptions=return_exceptions
    )


async def optimized_wait_for(coro: Awaitable[T], timeout: float, operation_type: str = "general") -> T:
    """Optimized version of asyncio.wait_for with metrics"""
    optimizer = get_async_optimizer()
    return await optimizer.task_pool.execute_with_semaphore(coro, operation_type, timeout)
