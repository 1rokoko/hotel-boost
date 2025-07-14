# Green API Integration Documentation

## Overview

This document describes the complete Green API integration for the WhatsApp Hotel Bot system. The integration provides comprehensive WhatsApp messaging capabilities with monitoring, logging, and error handling.

## Architecture

### Core Components

1. **Green API Client** (`app/services/green_api.py`)
   - HTTP client with retry logic and rate limiting
   - Support for all Green API message types
   - Connection pooling for multiple hotel instances

2. **Webhook Processing** (`app/services/webhook_processor.py`)
   - Handles incoming webhooks from Green API
   - Validates webhook signatures
   - Processes different webhook types asynchronously

3. **Message Handling** (`app/services/message_sender.py`, `app/services/message_processor.py`)
   - Queue-based message sending with retry
   - Intelligent message parsing and processing
   - Integration with conversation management

4. **Monitoring & Logging** (`app/core/green_api_logging.py`, `app/middleware/green_api_middleware.py`)
   - Structured logging for all operations
   - Real-time metrics collection
   - Alert system for error conditions

## Configuration

### Environment Variables

```bash
# Green API Configuration
GREEN_API_BASE_URL=https://api.green-api.com
GREEN_API_TIMEOUT=30
GREEN_API_MAX_RETRIES=3
GREEN_API_RATE_LIMIT_PER_MINUTE=60
GREEN_API_RATE_LIMIT_PER_SECOND=2

# Webhook Configuration
GREEN_API_WEBHOOK_SECRET=your_webhook_secret_here

# Logging Configuration
GREEN_API_ENABLE_DETAILED_LOGGING=true
GREEN_API_LOG_REQUEST_BODY=false
GREEN_API_LOG_RESPONSE_BODY=false
```

### Hotel-Specific Configuration

Each hotel requires the following Green API credentials:

```python
# In Hotel model
green_api_instance_id: str
green_api_token: str
green_api_webhook_token: str
```

## API Endpoints

### Webhook Endpoints

- `POST /api/v1/webhooks/green-api` - Receive webhooks from Green API

### Monitoring Endpoints

- `GET /api/v1/monitoring/dashboard` - Monitoring dashboard (HTML)
- `GET /api/v1/monitoring/metrics` - Current metrics (JSON)
- `GET /api/v1/monitoring/health` - Health status (JSON)
- `GET /api/v1/monitoring/alerts` - Active alerts (JSON)

### Management Endpoints

- `POST /api/v1/monitoring/alerts/rules` - Create alert rule
- `PUT /api/v1/monitoring/alerts/rules/{rule_name}` - Update alert rule
- `DELETE /api/v1/monitoring/alerts/rules/{rule_name}` - Delete alert rule

## Message Types Supported

### Outgoing Messages

1. **Text Messages**
   ```python
   await message_sender.send_text_message(
       hotel=hotel,
       guest=guest,
       message="Hello from the hotel!"
   )
   ```

2. **File Messages**
   ```python
   await message_sender.send_file_message(
       hotel=hotel,
       guest=guest,
       file_url="https://example.com/file.pdf",
       caption="Your booking confirmation"
   )
   ```

3. **Location Messages**
   ```python
   await message_sender.send_location_message(
       hotel=hotel,
       guest=guest,
       latitude=40.7128,
       longitude=-74.0060,
       name="Hotel Location"
   )
   ```

4. **Contact Messages**
   ```python
   await message_sender.send_contact_message(
       hotel=hotel,
       guest=guest,
       contact_data={
           "firstName": "Hotel",
           "lastName": "Reception",
           "phoneNumber": "+1234567890"
       }
   )
   ```

### Incoming Messages

The system automatically processes:
- Text messages
- Image messages
- Document messages
- Location messages
- Contact messages
- Voice messages

## Monitoring & Alerting

### Metrics Collected

1. **Request Metrics**
   - Total requests
   - Error rate
   - Response times (average, p50, p95, p99)
   - Success rate

2. **Rate Limiting Metrics**
   - Rate limit hits
   - Average wait times

3. **Message Metrics**
   - Messages sent
   - Messages received
   - Message failures

4. **Webhook Metrics**
   - Webhooks received
   - Webhook errors
   - Webhook types distribution

5. **Instance Metrics**
   - Per-instance request counts
   - Per-instance error rates
   - Last request timestamps

### Default Alert Rules

1. **High Error Rate** (10% for 5 minutes)
2. **Critical Error Rate** (25% for 1 minute)
3. **Slow Response Time** (>5 seconds for 5 minutes)
4. **Very Slow Response Time** (>10 seconds for 3 minutes)
5. **Rate Limit Hits** (5 hits in 5 minutes)
6. **Webhook Failures** (20% failure rate for 5 minutes)
7. **Message Send Failures** (15% failure rate for 5 minutes)

### Monitoring Dashboard

Access the monitoring dashboard at `/api/v1/monitoring/dashboard` to view:
- Real-time metrics
- Response time trends
- Error distribution
- Active alerts
- Instance health status

## Error Handling

### Retry Logic

The system implements exponential backoff with jitter for failed requests:
- Initial delay: 1 second
- Maximum delay: 60 seconds
- Maximum retries: 3
- Jitter: ±50% of calculated delay

### Rate Limiting

Built-in rate limiting prevents API quota exhaustion:
- Default: 60 requests per minute, 2 per second
- Configurable per hotel instance
- Automatic backoff when limits are hit

### Error Recovery

1. **Temporary Failures**: Automatic retry with exponential backoff
2. **Rate Limit Errors**: Automatic waiting and retry
3. **Authentication Errors**: Alert generation and manual intervention required
4. **Network Errors**: Retry with circuit breaker pattern

## Testing

### Running Tests

```bash
# Run all Green API tests
make test-green-api

# Run specific test types
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-webhook       # Webhook tests only

# Run with coverage
make test-coverage
```

### Mock Testing

Use the provided mock objects for testing:

```python
from tests.mocks.green_api_mock import MockGreenAPIClient

# Create mock client
mock_client = MockGreenAPIClient()

# Configure failure rate for testing
mock_client.mock_api.set_failure_rate(0.1)  # 10% failure rate

# Test with mock
result = await mock_client.send_text_message(request)
```

## Deployment

### Production Checklist

1. **Environment Variables**
   - [ ] All Green API credentials configured
   - [ ] Webhook secrets set
   - [ ] Rate limits configured appropriately

2. **Monitoring**
   - [ ] Alert rules configured
   - [ ] Dashboard accessible
   - [ ] Log aggregation setup

3. **Security**
   - [ ] Webhook signature validation enabled
   - [ ] HTTPS endpoints configured
   - [ ] Sensitive data redaction in logs

4. **Performance**
   - [ ] Rate limits tuned for expected load
   - [ ] Connection pooling configured
   - [ ] Retry policies optimized

### Scaling Considerations

1. **Horizontal Scaling**
   - Green API client pool supports multiple instances
   - Webhook processing is stateless
   - Metrics collection is thread-safe

2. **Vertical Scaling**
   - Adjust rate limits based on Green API quotas
   - Increase connection pool sizes
   - Tune retry timeouts

## Troubleshooting

### Common Issues

1. **High Error Rates**
   - Check Green API instance status
   - Verify authentication credentials
   - Review rate limit settings

2. **Slow Response Times**
   - Check network connectivity
   - Review Green API service status
   - Adjust timeout settings

3. **Webhook Delivery Failures**
   - Verify webhook URL accessibility
   - Check webhook signature validation
   - Review firewall settings

4. **Message Delivery Issues**
   - Check recipient phone number format
   - Verify Green API instance permissions
   - Review message content restrictions

### Debugging

1. **Enable Detailed Logging**
   ```bash
   GREEN_API_ENABLE_DETAILED_LOGGING=true
   GREEN_API_LOG_REQUEST_BODY=true
   GREEN_API_LOG_RESPONSE_BODY=true
   ```

2. **Check Metrics**
   - Visit monitoring dashboard
   - Review error distribution
   - Check instance health

3. **Review Logs**
   ```bash
   # Filter Green API logs
   grep "green_api" /var/log/app.log

   # Check for errors
   grep "ERROR" /var/log/app.log | grep "green_api"
   ```

## Support

For issues related to:
- **Green API Service**: Contact Green API support
- **Integration Code**: Check GitHub issues or create new issue
- **Hotel-Specific Issues**: Review hotel configuration and credentials

## Changelog

### Version 1.0.0
- Initial Green API integration
- Complete webhook processing
- Monitoring and alerting system
- Comprehensive test suite
- Production-ready deployment
