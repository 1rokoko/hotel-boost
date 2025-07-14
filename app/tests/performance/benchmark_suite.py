"""
Performance benchmarking suite for WhatsApp Hotel Bot
Provides comprehensive performance testing and validation
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import json

import pytest
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_pool import get_enhanced_pool
from app.services.cache_service import get_cache_service
from app.utils.connection_manager import get_connection_manager
from app.utils.query_optimizer import get_query_analyzer
from app.utils.async_optimizer import get_async_optimizer
from app.utils.memory_optimizer import get_memory_profiler
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BenchmarkResult:
    """Benchmark test result"""
    test_name: str
    duration_ms: float
    success: bool
    throughput_ops_per_sec: float = 0.0
    memory_usage_mb: float = 0.0
    error_rate: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceTargets:
    """Performance targets for validation"""
    max_response_time_ms: float = 1000.0
    min_throughput_ops_per_sec: float = 100.0
    max_memory_usage_mb: float = 512.0
    max_error_rate: float = 0.01  # 1%
    max_p95_response_time_ms: float = 2000.0
    max_p99_response_time_ms: float = 5000.0


class PerformanceBenchmark:
    """Performance benchmark runner"""
    
    def __init__(self, targets: Optional[PerformanceTargets] = None):
        self.targets = targets or PerformanceTargets()
        self.logger = logger.bind(component="performance_benchmark")
        self.results: List[BenchmarkResult] = []
    
    async def run_benchmark(
        self,
        test_name: str,
        test_func: Callable[[], Awaitable[Any]],
        iterations: int = 100,
        concurrent_users: int = 10,
        warmup_iterations: int = 10
    ) -> BenchmarkResult:
        """Run a performance benchmark test"""
        self.logger.info("Starting benchmark", 
                        test_name=test_name, 
                        iterations=iterations,
                        concurrent_users=concurrent_users)
        
        # Warmup phase
        await self._warmup(test_func, warmup_iterations)
        
        # Collect baseline memory
        memory_profiler = get_memory_profiler()
        start_snapshot = memory_profiler.take_snapshot()
        
        # Run benchmark
        start_time = time.time()
        durations = []
        errors = 0
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrent_users)
        
        async def run_single_test():
            async with semaphore:
                test_start = time.time()
                try:
                    await test_func()
                    return (time.time() - test_start) * 1000  # Convert to ms
                except Exception as e:
                    self.logger.error("Benchmark test failed", error=str(e))
                    return None
        
        # Run all iterations
        tasks = [run_single_test() for _ in range(iterations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                errors += 1
            elif result is None:
                errors += 1
            else:
                durations.append(result)
        
        total_duration = time.time() - start_time
        end_snapshot = memory_profiler.take_snapshot()
        
        # Calculate metrics
        if durations:
            avg_duration = statistics.mean(durations)
            p50 = statistics.median(durations)
            p95 = statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else max(durations)
            p99 = statistics.quantiles(durations, n=100)[98] if len(durations) > 100 else max(durations)
        else:
            avg_duration = p50 = p95 = p99 = 0
        
        throughput = len(durations) / total_duration if total_duration > 0 else 0
        error_rate = errors / iterations if iterations > 0 else 0
        memory_usage = end_snapshot.process_memory_mb - start_snapshot.process_memory_mb
        
        result = BenchmarkResult(
            test_name=test_name,
            duration_ms=avg_duration,
            success=error_rate <= self.targets.max_error_rate,
            throughput_ops_per_sec=throughput,
            memory_usage_mb=memory_usage,
            error_rate=error_rate,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            metadata={
                "iterations": iterations,
                "concurrent_users": concurrent_users,
                "total_duration_s": total_duration,
                "successful_operations": len(durations),
                "failed_operations": errors
            }
        )
        
        self.results.append(result)
        
        self.logger.info("Benchmark completed",
                        test_name=test_name,
                        avg_duration_ms=avg_duration,
                        throughput=throughput,
                        error_rate=error_rate,
                        p95_ms=p95)
        
        return result
    
    async def _warmup(self, test_func: Callable, iterations: int):
        """Warmup phase to stabilize performance"""
        self.logger.debug("Running warmup", iterations=iterations)
        
        for _ in range(iterations):
            try:
                await test_func()
            except Exception:
                pass  # Ignore warmup errors
        
        # Small delay to let system stabilize
        await asyncio.sleep(0.1)
    
    def validate_performance(self, result: BenchmarkResult) -> Dict[str, bool]:
        """Validate benchmark result against performance targets"""
        validations = {
            "response_time": result.duration_ms <= self.targets.max_response_time_ms,
            "throughput": result.throughput_ops_per_sec >= self.targets.min_throughput_ops_per_sec,
            "memory_usage": result.memory_usage_mb <= self.targets.max_memory_usage_mb,
            "error_rate": result.error_rate <= self.targets.max_error_rate,
            "p95_response_time": result.p95_ms <= self.targets.max_p95_response_time_ms,
            "p99_response_time": result.p99_ms <= self.targets.max_p99_response_time_ms
        }
        
        return validations
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        if not self.results:
            return {"error": "No benchmark results available"}
        
        # Overall statistics
        avg_duration = statistics.mean(r.duration_ms for r in self.results)
        avg_throughput = statistics.mean(r.throughput_ops_per_sec for r in self.results)
        avg_memory = statistics.mean(r.memory_usage_mb for r in self.results)
        avg_error_rate = statistics.mean(r.error_rate for r in self.results)
        
        # Validation results
        all_validations = []
        for result in self.results:
            validations = self.validate_performance(result)
            all_validations.append(validations)
        
        # Calculate pass rates
        pass_rates = {}
        if all_validations:
            for metric in all_validations[0].keys():
                passed = sum(1 for v in all_validations if v[metric])
                pass_rates[metric] = (passed / len(all_validations)) * 100
        
        return {
            "summary": {
                "total_tests": len(self.results),
                "avg_duration_ms": avg_duration,
                "avg_throughput_ops_per_sec": avg_throughput,
                "avg_memory_usage_mb": avg_memory,
                "avg_error_rate": avg_error_rate
            },
            "targets": {
                "max_response_time_ms": self.targets.max_response_time_ms,
                "min_throughput_ops_per_sec": self.targets.min_throughput_ops_per_sec,
                "max_memory_usage_mb": self.targets.max_memory_usage_mb,
                "max_error_rate": self.targets.max_error_rate,
                "max_p95_response_time_ms": self.targets.max_p95_response_time_ms,
                "max_p99_response_time_ms": self.targets.max_p99_response_time_ms
            },
            "validation_pass_rates": pass_rates,
            "individual_results": [
                {
                    "test_name": r.test_name,
                    "duration_ms": r.duration_ms,
                    "throughput_ops_per_sec": r.throughput_ops_per_sec,
                    "memory_usage_mb": r.memory_usage_mb,
                    "error_rate": r.error_rate,
                    "p95_ms": r.p95_ms,
                    "p99_ms": r.p99_ms,
                    "success": r.success,
                    "validations": self.validate_performance(r)
                }
                for r in self.results
            ]
        }


class DatabasePerformanceTests:
    """Database-specific performance tests"""
    
    def __init__(self, benchmark: PerformanceBenchmark):
        self.benchmark = benchmark
        self.logger = logger.bind(component="db_performance_tests")
    
    async def test_connection_pool_performance(self):
        """Test database connection pool performance"""
        pool = get_enhanced_pool()
        
        async def connection_test():
            async with pool.get_session_context() as session:
                await session.execute("SELECT 1")
        
        return await self.benchmark.run_benchmark(
            "database_connection_pool",
            connection_test,
            iterations=200,
            concurrent_users=20
        )
    
    async def test_query_performance(self):
        """Test database query performance"""
        connection_manager = get_connection_manager()
        
        async def query_test():
            async def test_query(session: AsyncSession):
                result = await session.execute("SELECT COUNT(*) FROM hotels WHERE is_active = true")
                return result.scalar()
            
            return await connection_manager.execute_with_retry(test_query)
        
        return await self.benchmark.run_benchmark(
            "database_query_performance",
            query_test,
            iterations=150,
            concurrent_users=15
        )
    
    async def test_transaction_performance(self):
        """Test database transaction performance"""
        connection_manager = get_connection_manager()
        
        async def transaction_test():
            async def test_transaction(session: AsyncSession):
                # Simulate a typical transaction
                await session.execute("BEGIN")
                await session.execute("SELECT COUNT(*) FROM guests")
                await session.execute("SELECT COUNT(*) FROM conversations")
                await session.execute("COMMIT")
            
            return await connection_manager.execute_with_retry(test_transaction)
        
        return await self.benchmark.run_benchmark(
            "database_transaction_performance",
            transaction_test,
            iterations=100,
            concurrent_users=10
        )


class CachePerformanceTests:
    """Cache-specific performance tests"""
    
    def __init__(self, benchmark: PerformanceBenchmark):
        self.benchmark = benchmark
        self.logger = logger.bind(component="cache_performance_tests")
    
    async def test_cache_get_performance(self):
        """Test cache get performance"""
        cache_service = await get_cache_service()
        
        # Pre-populate cache
        for i in range(1000):
            await cache_service.set(f"test_key_{i}", f"test_value_{i}")
        
        async def cache_get_test():
            key = f"test_key_{time.time() % 1000:.0f}"
            return await cache_service.get(key)
        
        return await self.benchmark.run_benchmark(
            "cache_get_performance",
            cache_get_test,
            iterations=500,
            concurrent_users=25
        )
    
    async def test_cache_set_performance(self):
        """Test cache set performance"""
        cache_service = await get_cache_service()
        
        async def cache_set_test():
            key = f"perf_test_{time.time()}_{id(asyncio.current_task())}"
            value = {"data": "test_value", "timestamp": time.time()}
            return await cache_service.set(key, value)
        
        return await self.benchmark.run_benchmark(
            "cache_set_performance",
            cache_set_test,
            iterations=300,
            concurrent_users=20
        )


class AsyncPerformanceTests:
    """Async processing performance tests"""
    
    def __init__(self, benchmark: PerformanceBenchmark):
        self.benchmark = benchmark
        self.logger = logger.bind(component="async_performance_tests")
    
    async def test_concurrent_task_performance(self):
        """Test concurrent task processing performance"""
        async_optimizer = get_async_optimizer()
        
        async def concurrent_task_test():
            async def dummy_task():
                await asyncio.sleep(0.001)  # 1ms simulated work
                return "completed"
            
            tasks = [dummy_task() for _ in range(10)]
            return await async_optimizer.task_pool.execute_batch(tasks, "general")
        
        return await self.benchmark.run_benchmark(
            "concurrent_task_performance",
            concurrent_task_test,
            iterations=50,
            concurrent_users=5
        )


# Global benchmark instance
performance_benchmark: Optional[PerformanceBenchmark] = None


def get_performance_benchmark() -> PerformanceBenchmark:
    """Get the global performance benchmark instance"""
    global performance_benchmark
    if performance_benchmark is None:
        performance_benchmark = PerformanceBenchmark()
    return performance_benchmark
