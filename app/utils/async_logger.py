"""
Asynchronous logging utilities for high-performance logging.

This module provides async logging capabilities to prevent blocking
the main application thread during log operations.
"""

import asyncio
import logging
import queue
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import structlog

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LogEntry:
    """Represents a log entry for async processing"""
    logger_name: str
    level: int
    message: str
    args: tuple
    kwargs: Dict[str, Any]
    timestamp: float
    extra: Optional[Dict[str, Any]] = None
    exc_info: Optional[Any] = None


class AsyncLogHandler(logging.Handler):
    """Async log handler that queues log records for background processing"""
    
    def __init__(self, max_queue_size: int = 10000):
        super().__init__()
        self.max_queue_size = max_queue_size
        self.log_queue = queue.Queue(maxsize=max_queue_size)
        self.worker_thread = None
        self.shutdown_event = threading.Event()
        self.stats = {
            'total_logs': 0,
            'queued_logs': 0,
            'dropped_logs': 0,
            'processing_time': 0.0
        }
        
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the async queue"""
        try:
            # Convert to our log entry format
            log_entry = LogEntry(
                logger_name=record.name,
                level=record.levelno,
                message=record.getMessage(),
                args=record.args,
                kwargs={},
                timestamp=record.created,
                extra=getattr(record, '__dict__', {}),
                exc_info=record.exc_info
            )
            
            # Try to add to queue (non-blocking)
            try:
                self.log_queue.put_nowait(log_entry)
                self.stats['queued_logs'] += 1
            except queue.Full:
                # Queue is full, drop the log entry
                self.stats['dropped_logs'] += 1
                
            self.stats['total_logs'] += 1
            
        except Exception:
            # Don't let logging errors crash the application
            pass
            
    def start_worker(self) -> None:
        """Start the background worker thread"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_thread = threading.Thread(
                target=self._worker_loop,
                name="AsyncLogWorker",
                daemon=True
            )
            self.worker_thread.start()
            
    def stop_worker(self) -> None:
        """Stop the background worker thread"""
        self.shutdown_event.set()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
            
    def _worker_loop(self) -> None:
        """Main worker loop for processing log entries"""
        while not self.shutdown_event.is_set():
            try:
                # Get log entry with timeout
                try:
                    log_entry = self.log_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                    
                # Process the log entry
                start_time = time.time()
                self._process_log_entry(log_entry)
                processing_time = time.time() - start_time
                
                self.stats['processing_time'] += processing_time
                self.log_queue.task_done()
                
            except Exception as e:
                # Log worker errors (but don't use async logging to avoid recursion)
                print(f"AsyncLogHandler worker error: {e}")
                
    def _process_log_entry(self, log_entry: LogEntry) -> None:
        """Process a single log entry"""
        # Get the target logger
        target_logger = logging.getLogger(log_entry.logger_name)
        
        # Create a new log record
        record = logging.LogRecord(
            name=log_entry.logger_name,
            level=log_entry.level,
            pathname="",
            lineno=0,
            msg=log_entry.message,
            args=log_entry.args,
            exc_info=log_entry.exc_info
        )
        
        # Add extra fields
        if log_entry.extra:
            for key, value in log_entry.extra.items():
                setattr(record, key, value)
                
        # Set timestamp
        record.created = log_entry.timestamp
        
        # Process through the logger's handlers (excluding async handlers)
        for handler in target_logger.handlers:
            if not isinstance(handler, AsyncLogHandler):
                try:
                    handler.handle(record)
                except Exception:
                    pass
                    
    def get_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        return {
            **self.stats,
            'queue_size': self.log_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'worker_alive': self.worker_thread.is_alive() if self.worker_thread else False
        }


class AsyncStructlogProcessor:
    """Async processor for structlog"""
    
    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self.log_queue = asyncio.Queue(maxsize=max_queue_size)
        self.worker_task = None
        self.shutdown_event = asyncio.Event()
        self.stats = {
            'total_logs': 0,
            'queued_logs': 0,
            'dropped_logs': 0
        }
        
    async def __call__(self, logger, method_name, event_dict):
        """Process structlog event asynchronously"""
        try:
            # Try to add to queue (non-blocking)
            try:
                self.log_queue.put_nowait({
                    'logger': logger,
                    'method_name': method_name,
                    'event_dict': event_dict,
                    'timestamp': time.time()
                })
                self.stats['queued_logs'] += 1
            except asyncio.QueueFull:
                # Queue is full, drop the log entry
                self.stats['dropped_logs'] += 1
                
            self.stats['total_logs'] += 1
            
        except Exception:
            # Don't let logging errors crash the application
            pass
            
        # Return the event_dict for synchronous processing as fallback
        return event_dict
        
    async def start_worker(self) -> None:
        """Start the async worker task"""
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker_loop())
            
    async def stop_worker(self) -> None:
        """Stop the async worker task"""
        self.shutdown_event.set()
        if self.worker_task and not self.worker_task.done():
            try:
                await asyncio.wait_for(self.worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.worker_task.cancel()
                
    async def _worker_loop(self) -> None:
        """Main worker loop for processing structlog events"""
        while not self.shutdown_event.is_set():
            try:
                # Get log event with timeout
                try:
                    log_event = await asyncio.wait_for(
                        self.log_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                    
                # Process the log event
                await self._process_log_event(log_event)
                self.log_queue.task_done()
                
            except Exception as e:
                # Log worker errors
                print(f"AsyncStructlogProcessor worker error: {e}")
                
    async def _process_log_event(self, log_event: Dict[str, Any]) -> None:
        """Process a single structlog event"""
        try:
            logger = log_event['logger']
            method_name = log_event['method_name']
            event_dict = log_event['event_dict']
            
            # Process through structlog's normal pipeline
            # This is a simplified version - in practice you'd want to
            # run through the configured processors
            message = event_dict.get('event', '')
            getattr(logger, method_name)(message, **event_dict)
            
        except Exception:
            pass
            
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.stats,
            'queue_size': self.log_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'worker_running': self.worker_task and not self.worker_task.done()
        }


class BatchLogProcessor:
    """Processes logs in batches for better performance"""
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.log_batch: List[LogEntry] = []
        self.last_flush = time.time()
        self.lock = threading.Lock()
        
    def add_log(self, log_entry: LogEntry) -> None:
        """Add a log entry to the batch"""
        with self.lock:
            self.log_batch.append(log_entry)
            
            # Check if we should flush
            should_flush = (
                len(self.log_batch) >= self.batch_size or
                time.time() - self.last_flush >= self.flush_interval
            )
            
            if should_flush:
                self._flush_batch()
                
    def _flush_batch(self) -> None:
        """Flush the current batch of logs"""
        if not self.log_batch:
            return
            
        batch_to_process = self.log_batch.copy()
        self.log_batch.clear()
        self.last_flush = time.time()
        
        # Process batch in background thread
        threading.Thread(
            target=self._process_batch,
            args=(batch_to_process,),
            daemon=True
        ).start()
        
    def _process_batch(self, batch: List[LogEntry]) -> None:
        """Process a batch of log entries"""
        for log_entry in batch:
            try:
                # Process each log entry
                target_logger = logging.getLogger(log_entry.logger_name)
                
                # Create log record and emit
                record = logging.LogRecord(
                    name=log_entry.logger_name,
                    level=log_entry.level,
                    pathname="",
                    lineno=0,
                    msg=log_entry.message,
                    args=log_entry.args,
                    exc_info=log_entry.exc_info
                )
                
                record.created = log_entry.timestamp
                
                if log_entry.extra:
                    for key, value in log_entry.extra.items():
                        setattr(record, key, value)
                        
                target_logger.handle(record)
                
            except Exception:
                # Don't let individual log failures stop batch processing
                pass
                
    def force_flush(self) -> None:
        """Force flush any remaining logs"""
        with self.lock:
            if self.log_batch:
                self._flush_batch()


class PerformanceOptimizedLogger:
    """High-performance logger with various optimizations"""
    
    def __init__(self, name: str):
        self.name = name
        self.base_logger = logging.getLogger(name)
        self.async_handler = AsyncLogHandler()
        self.batch_processor = BatchLogProcessor()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="LogWorker")
        
        # Setup async handler
        self.async_handler.start_worker()
        
    def log(
        self,
        level: int,
        message: str,
        *args,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Any] = None,
        **kwargs
    ) -> None:
        """Log a message with performance optimizations"""
        # Create log entry
        log_entry = LogEntry(
            logger_name=self.name,
            level=level,
            message=message,
            args=args,
            kwargs=kwargs,
            timestamp=time.time(),
            extra=extra,
            exc_info=exc_info
        )
        
        # Add to batch processor
        self.batch_processor.add_log(log_entry)
        
    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message"""
        self.log(logging.INFO, message, *args, **kwargs)
        
    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message"""
        self.log(logging.WARNING, message, *args, **kwargs)
        
    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message"""
        self.log(logging.ERROR, message, *args, **kwargs)
        
    def critical(self, message: str, *args, **kwargs) -> None:
        """Log critical message"""
        self.log(logging.CRITICAL, message, *args, **kwargs)
        
    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message"""
        if settings.DEBUG:
            self.log(logging.DEBUG, message, *args, **kwargs)
            
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            'async_handler': self.async_handler.get_stats(),
            'executor_stats': {
                'active_threads': self.executor._threads,
                'queue_size': self.executor._work_queue.qsize()
            }
        }
        
    def shutdown(self) -> None:
        """Shutdown the logger and cleanup resources"""
        self.batch_processor.force_flush()
        self.async_handler.stop_worker()
        self.executor.shutdown(wait=True)


# Global performance logger instances
_performance_loggers: Dict[str, PerformanceOptimizedLogger] = {}


def get_performance_logger(name: str) -> PerformanceOptimizedLogger:
    """Get a performance-optimized logger instance"""
    if name not in _performance_loggers:
        _performance_loggers[name] = PerformanceOptimizedLogger(name)
    return _performance_loggers[name]


def shutdown_all_performance_loggers() -> None:
    """Shutdown all performance loggers"""
    for logger in _performance_loggers.values():
        logger.shutdown()
    _performance_loggers.clear()
