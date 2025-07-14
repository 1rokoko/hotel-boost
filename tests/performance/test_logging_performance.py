"""
Performance tests for the logging system.

Tests logging throughput, memory usage, and performance
under various load conditions.
"""

import pytest
import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
import logging

from app.utils.async_logger import (
    AsyncLogHandler,
    AsyncStructlogProcessor,
    BatchLogProcessor,
    PerformanceOptimizedLogger,
    get_performance_logger
)
from app.core.log_performance import (
    LogPerformanceMonitor,
    LogOptimizer,
    LogResourceManager
)
from app.middleware.logging_middleware import LoggingMiddleware, PerformanceLoggingMiddleware


class TestAsyncLogHandler:
    """Test async log handler performance"""
    
    @pytest.fixture
    def async_handler(self):
        """Create async log handler"""
        handler = AsyncLogHandler(max_queue_size=1000)
        handler.start_worker()
        yield handler
        handler.stop_worker()
        
    def test_async_handler_throughput(self, async_handler):
        """Test async handler can handle high throughput"""
        logger = logging.getLogger('test')
        logger.addHandler(async_handler)
        logger.setLevel(logging.INFO)
        
        # Send many log messages quickly
        start_time = time.time()
        num_messages = 1000
        
        for i in range(num_messages):
            logger.info(f"Test message {i}")
            
        # Wait for queue to be processed
        time.sleep(2)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle at least 500 messages per second
        messages_per_second = num_messages / duration
        assert messages_per_second > 500
        
        # Check stats
        stats = async_handler.get_stats()
        assert stats['total_logs'] == num_messages
        assert stats['dropped_logs'] == 0
        
    def test_async_handler_queue_full(self):
        """Test behavior when queue is full"""
        handler = AsyncLogHandler(max_queue_size=10)
        handler.start_worker()
        
        try:
            logger = logging.getLogger('test_full')
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
            # Fill the queue beyond capacity
            for i in range(20):
                logger.info(f"Message {i}")
                
            stats = handler.get_stats()
            assert stats['dropped_logs'] > 0
            
        finally:
            handler.stop_worker()
            
    def test_async_handler_memory_usage(self, async_handler):
        """Test memory usage doesn't grow unbounded"""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        logger = logging.getLogger('test_memory')
        logger.addHandler(async_handler)
        logger.setLevel(logging.INFO)
        
        # Generate many log messages
        for i in range(5000):
            logger.info(f"Memory test message {i} with some additional data")
            
        # Wait for processing
        time.sleep(3)
        gc.collect()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024


class TestBatchLogProcessor:
    """Test batch log processor performance"""
    
    def test_batch_processing_efficiency(self):
        """Test that batch processing is more efficient"""
        from app.utils.async_logger import LogEntry
        
        processor = BatchLogProcessor(batch_size=100, flush_interval=1.0)
        
        # Time individual processing
        start_time = time.time()
        for i in range(100):
            log_entry = LogEntry(
                logger_name='test',
                level=logging.INFO,
                message=f'Test message {i}',
                args=(),
                kwargs={},
                timestamp=time.time()
            )
            processor.add_log(log_entry)
            
        # Force flush and wait
        processor.force_flush()
        time.sleep(0.5)
        
        batch_time = time.time() - start_time
        
        # Batch processing should be fast
        assert batch_time < 1.0
        
    def test_batch_size_optimization(self):
        """Test different batch sizes for optimal performance"""
        from app.utils.async_logger import LogEntry
        
        batch_sizes = [10, 50, 100, 200]
        results = {}
        
        for batch_size in batch_sizes:
            processor = BatchLogProcessor(batch_size=batch_size, flush_interval=0.1)
            
            start_time = time.time()
            for i in range(1000):
                log_entry = LogEntry(
                    logger_name='test',
                    level=logging.INFO,
                    message=f'Test message {i}',
                    args=(),
                    kwargs={},
                    timestamp=time.time()
                )
                processor.add_log(log_entry)
                
            processor.force_flush()
            time.sleep(0.2)
            
            results[batch_size] = time.time() - start_time
            
        # Larger batch sizes should generally be faster
        assert results[100] <= results[10]


class TestPerformanceOptimizedLogger:
    """Test performance optimized logger"""
    
    def test_performance_logger_throughput(self):
        """Test performance logger can handle high throughput"""
        logger = PerformanceOptimizedLogger('perf_test')
        
        start_time = time.time()
        num_messages = 2000
        
        # Use multiple threads to simulate concurrent logging
        def log_messages(thread_id, count):
            for i in range(count):
                logger.info(f"Thread {thread_id} message {i}")
                
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for thread_id in range(4):
                future = executor.submit(log_messages, thread_id, num_messages // 4)
                futures.append(future)
                
            # Wait for all threads to complete
            for future in futures:
                future.result()
                
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle at least 1000 messages per second
        messages_per_second = num_messages / duration
        assert messages_per_second > 1000
        
        # Cleanup
        logger.shutdown()
        
    def test_performance_logger_stats(self):
        """Test performance logger statistics"""
        logger = PerformanceOptimizedLogger('stats_test')
        
        # Log some messages
        for i in range(100):
            logger.info(f"Stats test message {i}")
            
        time.sleep(0.5)
        
        stats = logger.get_stats()
        assert 'async_handler' in stats
        assert 'executor_stats' in stats
        
        logger.shutdown()


class TestLogPerformanceMonitor:
    """Test log performance monitoring"""
    
    def test_performance_monitoring(self):
        """Test performance monitoring functionality"""
        monitor = LogPerformanceMonitor()
        
        # Record some events
        for i in range(100):
            monitor.record_log_event(
                processing_time=0.001 + (i * 0.0001),  # Gradually increasing time
                queue_size=i,
                dropped=i % 20 == 0,  # 5% drop rate
                error=i % 50 == 0     # 2% error rate
            )
            
        metrics = monitor.get_current_metrics()
        
        assert metrics.total_logs == 100
        assert metrics.dropped_logs == 5
        assert metrics.error_count == 2
        assert metrics.logs_per_second > 0
        
    def test_performance_summary(self):
        """Test performance summary generation"""
        monitor = LogPerformanceMonitor()
        
        # Record events that should trigger issues
        for i in range(100):
            monitor.record_log_event(
                processing_time=0.02,  # 20ms - should trigger slow processing
                queue_size=1500,       # Should trigger large queue warning
                dropped=i % 10 == 0    # 10% drop rate - should trigger high drop rate
            )
            
        summary = monitor.get_performance_summary()
        
        assert summary['performance_status'] == 'degraded'
        assert len(summary['issues']) > 0
        assert len(summary['recommendations']) > 0
        
    def test_trend_analysis(self):
        """Test trend analysis"""
        monitor = LogPerformanceMonitor()
        
        # Record events with increasing processing time
        for i in range(50):
            monitor.record_log_event(
                processing_time=0.001 * (i + 1),  # Increasing processing time
                queue_size=i
            )
            
        time.sleep(0.1)  # Ensure some time passes
        
        trends = monitor.get_trend_analysis(minutes=1)
        
        if trends.get('status') != 'insufficient_data':
            assert 'trends' in trends
            assert 'processing_time_ms' in trends['trends']


class TestLogOptimizer:
    """Test log optimizer"""
    
    def test_auto_optimization(self):
        """Test automatic optimization"""
        monitor = LogPerformanceMonitor()
        optimizer = LogOptimizer(monitor)
        
        # Create conditions that need optimization
        for i in range(100):
            monitor.record_log_event(
                processing_time=0.02,  # Slow processing
                queue_size=2000,       # Large queue
                dropped=i % 5 == 0     # High drop rate
            )
            
        result = optimizer.auto_optimize()
        
        assert result['status'] in ['optimized', 'no_action_needed']
        if result['status'] == 'optimized':
            assert len(result['optimizations_applied']) > 0


class TestLogResourceManager:
    """Test log resource management"""
    
    def test_disk_usage_check(self, tmp_path):
        """Test disk usage checking"""
        manager = LogResourceManager()
        
        # Create some test log files
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        
        for i in range(5):
            log_file = log_dir / f"test_{i}.log"
            log_file.write_text("test log content" * 100)
            
        usage = manager.check_disk_usage(str(log_dir))
        
        assert usage['status'] == 'success'
        assert usage['log_files_count'] == 5
        assert usage['log_directory_size_mb'] > 0
        
    def test_log_cleanup(self, tmp_path):
        """Test log file cleanup"""
        manager = LogResourceManager()
        manager.resource_limits['retention_days'] = 0  # Clean all files
        
        # Create test log files
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        
        for i in range(3):
            log_file = log_dir / f"old_{i}.log"
            log_file.write_text("old log content")
            
        result = manager.cleanup_old_logs(str(log_dir))
        
        assert result['status'] == 'completed'
        assert result['files_cleaned'] == 3


@pytest.mark.asyncio
class TestLoggingMiddleware:
    """Test logging middleware performance"""
    
    async def test_middleware_performance(self):
        """Test middleware doesn't significantly impact performance"""
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
            
        # Test without middleware
        start_time = time.time()
        for _ in range(100):
            # Simulate request processing
            await asyncio.sleep(0.001)
        baseline_time = time.time() - start_time
        
        # Add logging middleware
        app.add_middleware(LoggingMiddleware)
        
        # Test with middleware
        start_time = time.time()
        for _ in range(100):
            # Simulate request processing with middleware
            await asyncio.sleep(0.001)
        middleware_time = time.time() - start_time
        
        # Middleware should add minimal overhead (less than 50% increase)
        overhead_ratio = middleware_time / baseline_time
        assert overhead_ratio < 1.5
        
    async def test_performance_middleware_sampling(self):
        """Test performance middleware with sampling"""
        from fastapi import FastAPI
        
        app = FastAPI()
        
        # Test with low sample rate
        middleware = PerformanceLoggingMiddleware(app, sample_rate=0.1)
        
        # This should complete quickly since most requests are skipped
        start_time = time.time()
        
        # Simulate many requests
        for _ in range(1000):
            # Mock request processing
            pass
            
        duration = time.time() - start_time
        
        # Should be very fast with low sampling
        assert duration < 1.0


class TestConcurrentLogging:
    """Test logging under concurrent load"""
    
    def test_concurrent_logging_safety(self):
        """Test that concurrent logging doesn't cause issues"""
        logger = get_performance_logger('concurrent_test')
        
        def log_worker(worker_id, num_messages):
            for i in range(num_messages):
                logger.info(f"Worker {worker_id} message {i}")
                
        # Start multiple threads logging concurrently
        threads = []
        for worker_id in range(10):
            thread = threading.Thread(
                target=log_worker,
                args=(worker_id, 100)
            )
            threads.append(thread)
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # Should complete without errors
        stats = logger.get_stats()
        assert stats['async_handler']['total_logs'] == 1000
        
        logger.shutdown()
        
    def test_memory_stability_under_load(self):
        """Test memory stability under sustained load"""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        logger = get_performance_logger('memory_test')
        
        # Generate sustained load
        for batch in range(10):
            for i in range(1000):
                logger.info(f"Batch {batch} message {i}")
                
            # Check memory periodically
            if batch % 3 == 0:
                gc.collect()
                current_memory = process.memory_info().rss
                memory_increase = current_memory - initial_memory
                
                # Memory shouldn't grow excessively (less than 100MB)
                assert memory_increase < 100 * 1024 * 1024
                
        logger.shutdown()
