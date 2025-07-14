# Performance Optimization Guide

This document describes the comprehensive performance optimization system implemented for the WhatsApp Hotel Bot.

## Overview

The performance optimization system includes:

1. **Enhanced Database Connection Pooling** - Dynamic pool sizing with health monitoring
2. **Query Optimization** - Query analysis, N+1 detection, and performance indexing
3. **Multi-Level Caching** - Memory + Redis caching with compression and warming
4. **Async Processing Optimization** - Concurrent task management and optimization
5. **Memory Usage Optimization** - Memory profiling and garbage collection tuning
6. **Performance Monitoring** - Real-time metrics and alerting

## Components

### 1. Enhanced Database Connection Pool

**Location**: `app/core/database_pool.py`

Features:
- Dynamic pool sizing based on utilization
- Connection health monitoring
- Performance metrics collection
- Automatic scaling with configurable thresholds

**Configuration**:
```python
from app.core.database_pool import PoolConfiguration

config = PoolConfiguration(
    min_pool_size=5,
    max_pool_size=20,
    max_overflow=30,
    scale_up_threshold=0.8,  # Scale up at 80% utilization
    scale_down_threshold=0.3,  # Scale down at 30% utilization
    health_check_interval=60  # Health check every 60 seconds
)
```

**Usage**:
```python
from app.core.database_pool import get_enhanced_pool

pool = get_enhanced_pool()
async with pool.get_session_context() as session:
    # Use session for database operations
    result = await session.execute("SELECT * FROM hotels")
```

### 2. Query Optimization

**Location**: `app/utils/query_optimizer.py`

Features:
- Automatic query analysis and optimization suggestions
- N+1 query detection
- Slow query tracking
- Performance indexing recommendations

**Usage**:
```python
from app.utils.query_optimizer import optimized_query_execution

async with optimized_query_execution(session, query) as result:
    # Query is automatically tracked and analyzed
    data = result.fetchall()
```

**Performance Indexes**:
The system includes comprehensive database indexes in `alembic/versions/add_performance_indexes.py`:
- Multi-tenant isolation indexes
- Time-based query optimization
- Trigger execution optimization
- Content search optimization

### 3. Multi-Level Caching

**Location**: `app/services/cache_service.py`

Features:
- Memory + Redis dual-level caching
- Automatic compression for large values
- Cache warming and intelligent invalidation
- Configurable TTL and strategies

**Usage**:
```python
from app.services.cache_service import get_cache_service
from app.utils.cache_decorators import cached

# Using the service directly
cache_service = await get_cache_service()
await cache_service.set("key", value, ttl=3600)
result = await cache_service.get("key")

# Using decorators
@cached(ttl=1800, level=CacheLevel.BOTH)
async def get_hotel_data(hotel_id: str):
    # Function result is automatically cached
    return await fetch_hotel_data(hotel_id)
```

**Cache Configuration**:
```python
from app.core.cache_config import get_cache_config

# Get predefined configuration for data type
config = get_cache_config("hotel_settings")
# Returns: ttl=3600, level=BOTH, compression=True, warming=True
```

### 4. Async Processing Optimization

**Location**: `app/utils/async_optimizer.py`

Features:
- Concurrent task management with semaphores
- Automatic retry with exponential backoff
- Performance metrics collection
- Thread pool integration for CPU/IO bound tasks

**Usage**:
```python
from app.utils.async_optimizer import get_async_optimizer, optimized_gather

optimizer = get_async_optimizer()

# Execute with concurrency control
result = await optimizer.task_pool.execute_with_semaphore(
    my_coroutine(),
    operation_type="database"
)

# Batch execution with automatic concurrency management
results = await optimized_gather(
    *coroutines,
    operation_type="api",
    return_exceptions=True
)
```

### 5. Memory Optimization

**Location**: `app/utils/memory_optimizer.py`

Features:
- Memory usage profiling and tracking
- Memory leak detection
- Garbage collection optimization
- Performance monitoring

**Usage**:
```python
from app.utils.memory_optimizer import memory_profiling, get_memory_profiler

# Profile memory usage of operations
with memory_profiling("expensive_operation"):
    # Memory usage is automatically tracked
    result = perform_expensive_operation()

# Get memory report
profiler = get_memory_profiler()
report = profiler.get_memory_report()
```

### 6. Performance Monitoring

**Location**: `app/monitoring/performance_dashboard.py`

Features:
- Real-time performance metrics collection
- Prometheus metrics export
- Automatic alerting on performance issues
- Comprehensive performance dashboards

**Metrics Collected**:
- Database connection pool utilization
- Cache hit rates and performance
- Memory usage and leak detection
- Query performance and slow query detection
- Async task performance

## API Endpoints

Performance monitoring is available through REST API endpoints:

### Get Performance Status
```
GET /api/v1/performance/status
```

### Get Performance Metrics
```
GET /api/v1/performance/metrics
```

### Get Prometheus Metrics
```
GET /api/v1/performance/metrics/prometheus
```

### Get Performance Alerts
```
GET /api/v1/performance/alerts
```

### Component-Specific Metrics
```
GET /api/v1/performance/database/pool
GET /api/v1/performance/cache
GET /api/v1/performance/memory
GET /api/v1/performance/queries
GET /api/v1/performance/async
```

### Administrative Actions
```
POST /api/v1/performance/cache/clear
POST /api/v1/performance/memory/gc
```

## Performance Testing

**Location**: `app/tests/performance/`

The system includes comprehensive performance testing:

```bash
# Run performance tests
python -m pytest app/tests/performance/ -v

# Run specific performance test
python -m pytest app/tests/performance/test_performance.py::TestPerformanceOptimizations::test_database_connection_pool_performance -v

# Generate performance report
python -m pytest app/tests/performance/test_performance.py::test_generate_performance_report -v
```

**Performance Targets**:
- Response time: < 1000ms
- Throughput: > 100 ops/sec
- Memory usage: < 512MB
- Error rate: < 1%
- P95 response time: < 2000ms
- P99 response time: < 5000ms

## Configuration

### Environment Variables

```bash
# Database optimization
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30

# Cache optimization
REDIS_URL=redis://localhost:6379/0
CACHE_DEFAULT_TTL=3600
CACHE_COMPRESSION_THRESHOLD=1024

# Memory optimization
MEMORY_MONITORING_ENABLED=true
MEMORY_PROFILING_ENABLED=true
GC_OPTIMIZATION_ENABLED=true

# Performance monitoring
PERFORMANCE_MONITORING_ENABLED=true
PERFORMANCE_MONITORING_INTERVAL=60
PROMETHEUS_ENABLED=true
```

### Startup Integration

The performance optimizations are automatically initialized during application startup in `app/main.py`:

```python
# Performance optimizations are initialized in the lifespan function
await initialize_performance_optimizations()
```

## Monitoring and Alerting

### Performance Alerts

The system automatically generates alerts for:
- High database pool utilization (>85%)
- Low cache hit rate (<70%)
- High memory usage (>90%)
- Slow query performance (>2000ms)
- High error rates (>5%)

### Prometheus Integration

Metrics are exported in Prometheus format and can be scraped by monitoring systems:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'whatsapp-hotel-bot'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/performance/metrics/prometheus'
```

### Grafana Dashboards

The system provides metrics compatible with Grafana dashboards for visualization:
- Database performance metrics
- Cache performance metrics
- Memory usage trends
- Query performance analysis
- Async processing metrics

## Best Practices

### Database Optimization
1. Use the enhanced connection pool for all database operations
2. Implement proper query optimization with indexes
3. Monitor for N+1 queries and use eager loading
4. Use connection health monitoring

### Caching Strategy
1. Use appropriate cache levels (memory vs Redis)
2. Implement cache warming for frequently accessed data
3. Use intelligent cache invalidation patterns
4. Monitor cache hit rates and adjust TTL accordingly

### Memory Management
1. Enable memory profiling in development
2. Monitor for memory leaks in production
3. Use garbage collection optimization
4. Profile memory-intensive operations

### Async Processing
1. Use semaphores for concurrency control
2. Implement proper retry mechanisms
3. Monitor async task performance
4. Use thread pools for CPU/IO bound operations

## Troubleshooting

### High Database Pool Utilization
1. Check for long-running queries
2. Increase pool size if needed
3. Optimize slow queries
4. Check for connection leaks

### Low Cache Hit Rate
1. Review cache TTL settings
2. Implement cache warming
3. Check cache invalidation patterns
4. Monitor cache size limits

### Memory Issues
1. Check for memory leaks
2. Review garbage collection settings
3. Profile memory-intensive operations
4. Monitor memory growth trends

### Performance Degradation
1. Check performance alerts
2. Review slow query logs
3. Monitor resource utilization
4. Analyze performance trends

## Migration Guide

To integrate the performance optimizations into an existing system:

1. **Install Dependencies**:
   ```bash
   pip install psutil
   ```

2. **Update Application Startup**:
   ```python
   from app.core.performance_integration import initialize_performance_optimizations
   await initialize_performance_optimizations()
   ```

3. **Run Database Migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Update Configuration**:
   Add performance-related environment variables

5. **Test Performance**:
   ```bash
   python -m pytest app/tests/performance/ -v
   ```

## Conclusion

The performance optimization system provides comprehensive monitoring and optimization capabilities for the WhatsApp Hotel Bot. It automatically optimizes database connections, caching, memory usage, and async processing while providing detailed metrics and alerting for proactive performance management.
