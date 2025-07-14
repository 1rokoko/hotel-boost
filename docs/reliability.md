# System Reliability & Resilience

Comprehensive documentation for the reliability and resilience components implemented in Task 016.

## Overview

The reliability system provides multiple layers of protection against failures and ensures graceful degradation when services are unavailable. The system includes:

- **Circuit Breakers** - Prevent cascading failures
- **Retry Logic** - Handle transient failures
- **Health Checks** - Monitor system health
- **Graceful Degradation** - Maintain functionality during outages
- **Dead Letter Queue** - Handle failed messages

## Components

### 1. Circuit Breaker

Circuit breakers prevent cascading failures by monitoring service health and failing fast when services are down.

#### Configuration

```python
from app.utils.circuit_breaker import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=60.0,    # Wait 60s before trying again
    success_threshold=3,      # Need 3 successes to close
    timeout=30.0,            # Request timeout
    window_size=100,         # Track last 100 requests
    minimum_requests=10      # Need 10 requests to calculate failure rate
)
```

#### Usage

```python
from app.utils.circuit_breaker import get_circuit_breaker

# Get circuit breaker instance
cb = get_circuit_breaker("my_service", config)

# Use circuit breaker
async def my_function():
    return "success"

result = await cb.call(my_function)
```

#### States

- **CLOSED** - Normal operation, requests pass through
- **OPEN** - Circuit is open, requests fail fast
- **HALF_OPEN** - Testing if service is back

### 2. Retry Logic

Intelligent retry mechanisms with multiple strategies and exponential backoff.

#### Strategies

- **Exponential Backoff** - Delay increases exponentially
- **Linear Backoff** - Delay increases linearly
- **Fixed Delay** - Constant delay between retries
- **Fibonacci Backoff** - Delay follows Fibonacci sequence

#### Usage with Decorators

```python
from app.decorators.retry_decorator import retry, retry_http_requests

@retry(max_retries=3, base_delay=1.0)
async def my_function():
    # Function that might fail
    pass

@retry_http_requests(max_retries=3)
async def api_call():
    # HTTP request that might fail
    pass
```

#### Manual Usage

```python
from app.utils.retry_handler import RetryHandler, RetryConfig

config = RetryConfig(max_retries=3, base_delay=1.0)
handler = RetryHandler(config)

result = await handler.execute_async(my_function)
```

### 3. Health Checks

Comprehensive health monitoring for all system dependencies.

#### Endpoints

- `GET /health/` - Basic health check
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe with dependency checks
- `GET /health/detailed` - Detailed health information
- `GET /health/circuit-breakers` - Circuit breaker status
- `GET /health/degradation` - System degradation status
- `GET /health/dlq` - Dead letter queue status

#### Health Checker Service

```python
from app.services.health_checker import HealthChecker

health_checker = HealthChecker()
system_health = await health_checker.check_all_dependencies(db)

print(f"Overall status: {system_health.overall_status}")
for name, result in system_health.checks.items():
    print(f"{name}: {result.status} ({result.response_time_ms}ms)")
```

### 4. Graceful Degradation

Fallback mechanisms that maintain functionality when services are unavailable.

#### Degradation Levels

- **NORMAL** - All services working
- **MINOR** - Minor degradation, some features disabled
- **MODERATE** - Moderate degradation, fallback responses
- **SEVERE** - Severe degradation, minimal functionality
- **CRITICAL** - Critical degradation, emergency mode

#### Fallback Service

```python
from app.services.fallback_service import fallback_service

# AI fallback
result = await fallback_service.ai_fallback("greeting")

# WhatsApp fallback (message queuing)
result = await fallback_service.whatsapp_fallback(message_data)

# Database fallback (read-only mode)
result = await fallback_service.database_fallback("read")

# Redis fallback (memory cache)
result = await fallback_service.redis_fallback("get", "key")
```

#### Degradation Handler

Automatically monitors system health and adjusts degradation level:

```python
from app.utils.degradation_handler import get_degradation_handler

handler = get_degradation_handler()
await handler.start_monitoring(interval=30.0)
```

### 5. Dead Letter Queue

Handles messages that fail processing after all retry attempts.

#### Adding Failed Messages

```python
from app.tasks.dead_letter_handler import dlq_handler

message_id = await dlq_handler.add_to_dlq(
    message_data={"type": "test", "content": "message"},
    error=Exception("Processing failed"),
    message_type="whatsapp_message",
    max_retries=5
)
```

#### Processing DLQ

```python
# Get messages from DLQ
messages = await dlq_handler.get_dlq_messages(limit=100)

# Retry specific message
success = await dlq_handler.retry_message(message_id)

# Process batch
stats = await dlq_handler.process_dlq_batch(batch_size=10)
```

#### Failed Message Processor

Intelligent recovery strategies for different failure types:

```python
from app.services.failed_message_processor import get_failed_message_processor

processor = get_failed_message_processor()
stats = await processor.process_dlq_with_strategies(batch_size=20)
```

## Integration

### Circuit Breaker Middleware

Automatically applied to API endpoints:

```python
from app.middleware.circuit_breaker_middleware import add_circuit_breaker_middleware

# Add to FastAPI app
add_circuit_breaker_middleware(app)
```

Protected paths:
- `/api/v1/webhooks/` - Webhook processing
- `/api/v1/messages/` - Message sending
- `/api/v1/sentiment/` - Sentiment analysis
- `/api/v1/triggers/` - Trigger execution

### Service Integration

Services automatically use circuit breakers and retry logic:

```python
# Green API with circuit breaker
from app.services.green_api import get_green_api_client

async with get_green_api_client() as client:
    result = await client.send_message(phone, message)

# DeepSeek API with circuit breaker
from app.services.deepseek_client import get_deepseek_client

client = get_deepseek_client()
result = await client.analyze_sentiment(message)
```

## Monitoring

### Metrics

Circuit breaker metrics:
- Total requests
- Success/failure rates
- Circuit state changes
- Response times

Health check metrics:
- Dependency status
- Response times
- Error rates

### Logging

All reliability components provide structured logging:

```python
# Circuit breaker events
logger.warning("Circuit breaker opened", name="service", failure_rate=0.8)

# Retry attempts
logger.warning("Retry attempt", attempt=2, delay=4.0, error="Connection failed")

# Degradation changes
logger.warning("System degradation", old_level="normal", new_level="moderate")
```

## Configuration

### Environment-Specific Settings

The system automatically adjusts settings based on environment:

- **Production** - More conservative thresholds, longer timeouts
- **Development** - More lenient settings, faster failures
- **Testing** - Minimal retries, short timeouts

### Service-Specific Configurations

Each service has optimized settings:

```python
# Green API - More tolerant for messaging
CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0)

# DeepSeek API - More sensitive for AI
CircuitBreakerConfig(failure_threshold=3, recovery_timeout=120.0)

# Database - Very tolerant for critical service
CircuitBreakerConfig(failure_threshold=10, recovery_timeout=30.0)
```

## Best Practices

1. **Circuit Breaker Placement** - Place circuit breakers around external service calls
2. **Retry Strategy** - Use exponential backoff with jitter for most cases
3. **Health Check Frequency** - Balance between responsiveness and load
4. **Degradation Gracefully** - Always provide some level of functionality
5. **Monitor Everything** - Track all reliability metrics
6. **Test Failure Scenarios** - Regularly test circuit breakers and fallbacks

## Troubleshooting

### Circuit Breaker Issues

```bash
# Check circuit breaker status
curl http://localhost:8000/health/circuit-breakers

# Reset circuit breaker
from app.utils.circuit_breaker import get_circuit_breaker
cb = get_circuit_breaker("service_name")
cb.reset()
```

### Health Check Failures

```bash
# Detailed health check
curl http://localhost:8000/health/detailed

# Check specific dependency
curl http://localhost:8000/health/ready
```

### DLQ Processing

```bash
# Check DLQ status
curl http://localhost:8000/health/dlq

# Process DLQ manually
from app.tasks.dead_letter_handler import process_dead_letter_queue_task
process_dead_letter_queue_task.delay(batch_size=10)
```

## Testing

The reliability system includes comprehensive tests:

- Unit tests for each component
- Integration tests for component interaction
- End-to-end tests for complete failure scenarios

Run tests:

```bash
# Unit tests
pytest tests/unit/test_circuit_breaker.py
pytest tests/unit/test_retry_handler.py

# Integration tests
pytest tests/integration/test_reliability_system.py
pytest tests/integration/test_reliability_endpoints.py
pytest tests/integration/test_complete_reliability_system.py
```

## Production Deployment

### Celery Tasks

The reliability system includes several Celery tasks for maintenance:

```python
# Process DLQ every 5 minutes
process_dead_letter_queue_batch.delay(batch_size=20)

# Monitor circuit breakers every 2 minutes
monitor_circuit_breakers.delay()

# Health check monitoring every 1 minute
health_check_monitoring.delay()

# Generate reliability report every hour
generate_reliability_report.delay()

# Cleanup old DLQ messages daily
cleanup_old_dlq_messages.delay(max_age_days=7)
```

### Monitoring and Alerting

#### Prometheus Metrics

The system exports comprehensive metrics:

```python
# Circuit breaker metrics
circuit_breaker_requests_total
circuit_breaker_state
circuit_breaker_failures_total
circuit_breaker_response_time

# Retry metrics
retry_attempts_total
retry_delay_seconds

# Health check metrics
health_check_duration_seconds
health_check_status

# Degradation metrics
system_degradation_level
degradation_events_total
fallback_usage_total

# DLQ metrics
dlq_messages_total
dlq_messages_added_total
dlq_processing_duration_seconds
```

#### Grafana Dashboard

Example Grafana queries:

```promql
# Circuit breaker failure rate
rate(circuit_breaker_failures_total[5m])

# System degradation level
system_degradation_level

# DLQ queue size
dlq_messages_total

# Health check success rate
rate(health_check_total{status="healthy"}[5m]) / rate(health_check_total[5m])
```

### Administrative Interface

Access admin endpoints for reliability management:

```bash
# Get circuit breaker status
GET /admin/reliability/circuit-breakers

# Reset circuit breaker
POST /admin/reliability/circuit-breakers/{service}/reset

# Set degradation level
POST /admin/reliability/degradation/set-level?level=moderate&reason=maintenance

# View DLQ status
GET /admin/reliability/dlq

# Retry DLQ message
POST /admin/reliability/dlq/{message_id}/retry

# Generate reliability report
GET /admin/reliability/reports/reliability
```

## Performance Impact

The reliability system is designed to have minimal performance impact:

- **Circuit Breakers**: ~1-2ms overhead per request
- **Retry Logic**: Only activates on failures
- **Health Checks**: Cached for 30 seconds
- **Metrics Collection**: Asynchronous, minimal overhead

## Security Considerations

- Admin endpoints require authentication
- Circuit breaker metrics don't expose sensitive data
- DLQ messages are stored securely in Redis
- Fallback responses don't leak system information

## Maintenance

### Regular Tasks

1. **Weekly**: Review circuit breaker metrics and adjust thresholds
2. **Monthly**: Analyze DLQ patterns and improve error handling
3. **Quarterly**: Review degradation rules and update as needed

### Capacity Planning

Monitor these metrics for capacity planning:

- Circuit breaker open frequency
- DLQ message volume
- Health check response times
- Fallback usage patterns

## Migration Guide

### From Previous Version

If upgrading from a version without reliability features:

1. **Deploy new code** with reliability components
2. **Configure circuit breakers** for your services
3. **Set up monitoring** and alerting
4. **Test fallback mechanisms** in staging
5. **Gradually enable** in production

### Configuration Migration

Update your configuration:

```python
# Old configuration
RETRY_ATTEMPTS = 3
TIMEOUT = 30

# New configuration
CIRCUIT_BREAKER_CONFIGS = {
    "my_service": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        timeout=30.0
    )
}
```
