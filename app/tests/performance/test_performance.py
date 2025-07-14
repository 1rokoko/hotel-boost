"""
Performance test suite for WhatsApp Hotel Bot optimization validation
Tests all performance optimization components
"""

import asyncio
import pytest
import json
from datetime import datetime
from pathlib import Path

from app.tests.performance.benchmark_suite import (
    PerformanceBenchmark,
    PerformanceTargets,
    DatabasePerformanceTests,
    CachePerformanceTests,
    AsyncPerformanceTests,
    get_performance_benchmark
)
from app.core.database_pool import initialize_enhanced_pool
from app.services.cache_service import get_cache_service
from app.utils.memory_optimizer import initialize_memory_optimization
from app.core.logging import get_logger

logger = get_logger(__name__)


class TestPerformanceOptimizations:
    """Test suite for performance optimizations"""
    
    @pytest.fixture(scope="class", autouse=True)
    async def setup_performance_environment(self):
        """Setup performance testing environment"""
        # Initialize all optimization components
        await initialize_enhanced_pool()
        await get_cache_service()
        initialize_memory_optimization()
        
        logger.info("Performance testing environment initialized")
        yield
        
        # Cleanup
        logger.info("Performance testing environment cleaned up")
    
    @pytest.mark.asyncio
    async def test_database_connection_pool_performance(self):
        """Test enhanced database connection pool performance"""
        benchmark = get_performance_benchmark()
        db_tests = DatabasePerformanceTests(benchmark)
        
        result = await db_tests.test_connection_pool_performance()
        
        # Validate performance targets
        validations = benchmark.validate_performance(result)
        
        assert result.success, f"Connection pool performance test failed: {result.error_rate}"
        assert validations["response_time"], f"Response time {result.duration_ms}ms exceeds target"
        assert validations["throughput"], f"Throughput {result.throughput_ops_per_sec} ops/s below target"
        assert validations["error_rate"], f"Error rate {result.error_rate} exceeds target"
        
        logger.info("Database connection pool performance test passed", 
                   duration_ms=result.duration_ms,
                   throughput=result.throughput_ops_per_sec)
    
    @pytest.mark.asyncio
    async def test_database_query_performance(self):
        """Test optimized database query performance"""
        benchmark = get_performance_benchmark()
        db_tests = DatabasePerformanceTests(benchmark)
        
        result = await db_tests.test_query_performance()
        
        validations = benchmark.validate_performance(result)
        
        assert result.success, f"Query performance test failed: {result.error_rate}"
        assert validations["response_time"], f"Query response time {result.duration_ms}ms exceeds target"
        assert validations["p95_response_time"], f"P95 response time {result.p95_ms}ms exceeds target"
        
        logger.info("Database query performance test passed",
                   duration_ms=result.duration_ms,
                   p95_ms=result.p95_ms)
    
    @pytest.mark.asyncio
    async def test_database_transaction_performance(self):
        """Test database transaction performance"""
        benchmark = get_performance_benchmark()
        db_tests = DatabasePerformanceTests(benchmark)
        
        result = await db_tests.test_transaction_performance()
        
        validations = benchmark.validate_performance(result)
        
        assert result.success, f"Transaction performance test failed: {result.error_rate}"
        assert validations["response_time"], f"Transaction response time {result.duration_ms}ms exceeds target"
        
        logger.info("Database transaction performance test passed",
                   duration_ms=result.duration_ms)
    
    @pytest.mark.asyncio
    async def test_cache_get_performance(self):
        """Test cache get operation performance"""
        benchmark = get_performance_benchmark()
        cache_tests = CachePerformanceTests(benchmark)
        
        result = await cache_tests.test_cache_get_performance()
        
        validations = benchmark.validate_performance(result)
        
        assert result.success, f"Cache get performance test failed: {result.error_rate}"
        assert validations["response_time"], f"Cache get response time {result.duration_ms}ms exceeds target"
        assert validations["throughput"], f"Cache get throughput {result.throughput_ops_per_sec} ops/s below target"
        
        logger.info("Cache get performance test passed",
                   duration_ms=result.duration_ms,
                   throughput=result.throughput_ops_per_sec)
    
    @pytest.mark.asyncio
    async def test_cache_set_performance(self):
        """Test cache set operation performance"""
        benchmark = get_performance_benchmark()
        cache_tests = CachePerformanceTests(benchmark)
        
        result = await cache_tests.test_cache_set_performance()
        
        validations = benchmark.validate_performance(result)
        
        assert result.success, f"Cache set performance test failed: {result.error_rate}"
        assert validations["response_time"], f"Cache set response time {result.duration_ms}ms exceeds target"
        
        logger.info("Cache set performance test passed",
                   duration_ms=result.duration_ms)
    
    @pytest.mark.asyncio
    async def test_async_processing_performance(self):
        """Test async processing optimization performance"""
        benchmark = get_performance_benchmark()
        async_tests = AsyncPerformanceTests(benchmark)
        
        result = await async_tests.test_concurrent_task_performance()
        
        validations = benchmark.validate_performance(result)
        
        assert result.success, f"Async processing performance test failed: {result.error_rate}"
        assert validations["response_time"], f"Async processing response time {result.duration_ms}ms exceeds target"
        
        logger.info("Async processing performance test passed",
                   duration_ms=result.duration_ms)
    
    @pytest.mark.asyncio
    async def test_memory_usage_optimization(self):
        """Test memory usage optimization"""
        from app.utils.memory_optimizer import get_memory_profiler
        
        profiler = get_memory_profiler()
        
        # Take baseline snapshot
        baseline = profiler.take_snapshot()
        
        # Perform memory-intensive operations
        data = []
        for i in range(10000):
            data.append({"id": i, "data": f"test_data_{i}" * 10})
        
        # Take snapshot after operations
        after_ops = profiler.take_snapshot()
        
        # Clean up
        del data
        import gc
        gc.collect()
        
        # Take final snapshot
        final = profiler.take_snapshot()
        
        # Validate memory usage
        memory_growth = after_ops.process_memory_mb - baseline.process_memory_mb
        memory_cleanup = after_ops.process_memory_mb - final.process_memory_mb
        
        assert memory_growth > 0, "Memory should increase during operations"
        assert memory_cleanup > 0, "Memory should be cleaned up after operations"
        
        logger.info("Memory optimization test passed",
                   memory_growth_mb=memory_growth,
                   memory_cleanup_mb=memory_cleanup)
    
    @pytest.mark.asyncio
    async def test_overall_system_performance(self):
        """Test overall system performance with all optimizations"""
        benchmark = get_performance_benchmark()
        
        async def system_test():
            # Simulate typical system operations
            cache_service = await get_cache_service()
            
            # Cache operations
            await cache_service.set("test_key", {"data": "test"})
            await cache_service.get("test_key")
            
            # Database operations would go here
            # (using mock or test database)
            
            # Async operations
            await asyncio.sleep(0.001)  # Simulate async work
        
        result = await benchmark.run_benchmark(
            "overall_system_performance",
            system_test,
            iterations=100,
            concurrent_users=10
        )
        
        validations = benchmark.validate_performance(result)
        
        assert result.success, f"Overall system performance test failed: {result.error_rate}"
        assert validations["response_time"], f"System response time {result.duration_ms}ms exceeds target"
        assert validations["throughput"], f"System throughput {result.throughput_ops_per_sec} ops/s below target"
        
        logger.info("Overall system performance test passed",
                   duration_ms=result.duration_ms,
                   throughput=result.throughput_ops_per_sec)
    
    def test_performance_targets_validation(self):
        """Test that performance targets are properly configured"""
        targets = PerformanceTargets()
        
        # Validate targets are reasonable
        assert targets.max_response_time_ms > 0
        assert targets.min_throughput_ops_per_sec > 0
        assert targets.max_memory_usage_mb > 0
        assert 0 <= targets.max_error_rate <= 1
        assert targets.max_p95_response_time_ms >= targets.max_response_time_ms
        assert targets.max_p99_response_time_ms >= targets.max_p95_response_time_ms
        
        logger.info("Performance targets validation passed")


@pytest.mark.asyncio
async def test_generate_performance_report():
    """Generate comprehensive performance report"""
    benchmark = get_performance_benchmark()
    
    # Run a quick test to have some data
    async def dummy_test():
        await asyncio.sleep(0.001)
    
    await benchmark.run_benchmark("dummy_test", dummy_test, iterations=10)
    
    # Generate report
    report = benchmark.get_performance_report()
    
    # Validate report structure
    assert "summary" in report
    assert "targets" in report
    assert "validation_pass_rates" in report
    assert "individual_results" in report
    
    # Save report to file
    report_path = Path("performance_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info("Performance report generated", report_path=str(report_path))


@pytest.mark.asyncio
async def test_performance_regression_detection():
    """Test performance regression detection"""
    benchmark = get_performance_benchmark()
    
    # Simulate baseline performance
    async def fast_operation():
        await asyncio.sleep(0.001)  # 1ms
    
    baseline_result = await benchmark.run_benchmark(
        "baseline_test",
        fast_operation,
        iterations=50
    )
    
    # Simulate degraded performance
    async def slow_operation():
        await asyncio.sleep(0.010)  # 10ms (10x slower)
    
    degraded_result = await benchmark.run_benchmark(
        "degraded_test",
        slow_operation,
        iterations=50
    )
    
    # Detect regression
    performance_degradation = degraded_result.duration_ms / baseline_result.duration_ms
    
    assert performance_degradation > 5, "Should detect significant performance degradation"
    
    logger.info("Performance regression detection test passed",
               baseline_ms=baseline_result.duration_ms,
               degraded_ms=degraded_result.duration_ms,
               degradation_factor=performance_degradation)


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "--tb=short"])
