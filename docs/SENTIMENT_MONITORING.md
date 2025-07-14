# Sentiment Analysis and Monitoring System

## Overview

The Sentiment Analysis and Monitoring system provides real-time analysis of guest messages to detect negative sentiment and automatically alert hotel staff when immediate attention is required.

## Features

### 🔍 Real-time Sentiment Analysis
- Automatic sentiment analysis of all incoming guest messages
- AI-powered detection using DeepSeek integration
- Confidence scoring and keyword extraction
- Support for multiple languages

### 🚨 Staff Alert System
- Automatic alerts for negative sentiment detection
- Configurable urgency levels and response time targets
- Multiple notification channels (email, SMS, Slack, Teams)
- Escalation workflows for overdue alerts

### 📊 Analytics Dashboard
- Sentiment trends and distribution analysis
- Guest satisfaction scoring
- Performance metrics and KPIs
- Exportable reports and data

### ⚙️ Configurable Rules Engine
- Customizable sentiment thresholds
- Hotel-specific alert rules
- Escalation policies
- Response time targets

## Architecture

### Components

1. **Real-time Sentiment Analyzer** (`app/services/realtime_sentiment.py`)
   - Processes messages as they arrive
   - Triggers alerts based on sentiment scores
   - Tracks guest sentiment history

2. **Staff Alert System** (`app/models/staff_alert.py`)
   - Creates and manages alerts
   - Handles escalations and notifications
   - Tracks response times

3. **Analytics Service** (`app/services/sentiment_analytics.py`)
   - Generates insights and reports
   - Calculates trends and metrics
   - Provides data for dashboards

4. **Rules Engine** (`app/services/sentiment_rules.py`)
   - Evaluates sentiment against configurable rules
   - Determines alert priorities and escalation levels
   - Manages threshold configurations

### Data Models

- **SentimentAnalysis**: Stores sentiment analysis results
- **StaffAlert**: Manages staff alerts and notifications
- **SentimentConfig**: Hotel-specific configuration settings
- **AlertEscalation**: Tracks alert escalations

## API Endpoints

### Sentiment Analytics
- `GET /api/v1/sentiment-analytics/overview` - Get sentiment overview
- `GET /api/v1/sentiment-analytics/trends` - Get sentiment trends
- `GET /api/v1/sentiment-analytics/alerts` - Get recent alerts
- `GET /api/v1/sentiment-analytics/metrics` - Get detailed metrics
- `POST /api/v1/sentiment-analytics/export` - Export sentiment data

### Monitoring and Metrics
- `GET /api/v1/sentiment-metrics/prometheus` - Prometheus metrics
- `GET /api/v1/sentiment-metrics/health` - System health status
- `GET /api/v1/sentiment-metrics/performance` - Performance metrics
- `GET /api/v1/sentiment-metrics/ai-model/performance` - AI model metrics

## Configuration

### Sentiment Thresholds

Default thresholds can be customized per hotel:

```json
{
  "negative_sentiment_threshold": -0.3,
  "critical_sentiment_threshold": -0.8,
  "very_negative_threshold": -0.6,
  "low_confidence_threshold": 0.5,
  "consecutive_negative_threshold": 3,
  "escalation_negative_count": 3
}
```

### Notification Channels

Configure notification channels by urgency level:

```json
{
  "notification_channels": {
    "critical": ["email", "sms", "slack"],
    "high": ["email", "slack"],
    "medium": ["email"],
    "low": ["dashboard"]
  }
}
```

### Response Time Targets

Set response time targets by priority:

```json
{
  "response_time_minutes": {
    "critical": 5,
    "high": 15,
    "medium": 30,
    "low": 60,
    "minimal": 120
  }
}
```

## Usage

### Automatic Processing

Sentiment analysis runs automatically for all incoming messages:

```python
# Message processing triggers sentiment analysis
from app.tasks.analyze_message_sentiment import analyze_message_sentiment_realtime_task

# Triggered automatically when message is received
analyze_message_sentiment_realtime_task.delay(
    message_id=message.id,
    conversation_id=conversation.id,
    correlation_id=correlation_id
)
```

### Manual Analysis

You can also trigger sentiment analysis manually:

```python
from app.services.realtime_sentiment import get_realtime_sentiment_analyzer

analyzer = get_realtime_sentiment_analyzer(db)
result = await analyzer.analyze_message(
    message=message,
    conversation_id=conversation_id,
    correlation_id=correlation_id
)
```

### Alert Management

Staff alerts are created automatically but can be managed via API:

```python
from app.models.staff_alert import StaffAlert

# Get pending alerts
pending_alerts = db.query(StaffAlert).filter(
    StaffAlert.hotel_id == hotel_id,
    StaffAlert.status == "pending"
).all()

# Acknowledge alert
alert.acknowledged_at = datetime.utcnow()
alert.acknowledged_by = staff_member_id
alert.status = "acknowledged"
```

## Monitoring

### Prometheus Metrics

The system exposes comprehensive metrics for monitoring:

- `sentiment_analysis_requests_total` - Total sentiment analysis requests
- `sentiment_analysis_duration_seconds` - Analysis duration
- `staff_alerts_created_total` - Total alerts created
- `staff_alert_response_time_seconds` - Alert response times
- `notifications_sent_total` - Total notifications sent

### Health Checks

Monitor system health via the health endpoint:

```bash
curl http://localhost:8000/api/v1/sentiment-metrics/health?hotel_id=<hotel_id>
```

### Logging

All operations are logged with structured logging:

```json
{
  "timestamp": "2025-01-15T12:00:00Z",
  "level": "INFO",
  "event_type": "sentiment_analysis_result",
  "message_id": "msg-123",
  "hotel_id": "hotel-456",
  "sentiment_score": -0.6,
  "requires_attention": true,
  "correlation_id": "req-789"
}
```

## Testing

### Unit Tests

Run sentiment analysis tests:

```bash
pytest tests/unit/test_sentiment_analysis.py -v
pytest tests/unit/test_staff_notifications.py -v
```

### Integration Tests

Run integration tests:

```bash
pytest tests/integration/test_sentiment_integration.py -v
```

### Load Testing

Test system performance:

```bash
pytest tests/performance/test_sentiment_load.py -v
```

## Deployment

### Environment Variables

Required environment variables:

```bash
# DeepSeek API (for sentiment analysis)
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Notification settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Slack integration (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# SMS integration (optional)
SMS_API_KEY=your_sms_api_key
```

### Database Migration

Run the migration to create sentiment monitoring tables:

```bash
alembic upgrade head
```

### Celery Workers

Start Celery workers for sentiment processing:

```bash
# Start general worker
celery -A app.core.celery_app worker --loglevel=info

# Start high-priority worker for alerts
celery -A app.core.celery_app worker --loglevel=info --queues=high_priority

# Start sentiment analysis worker
celery -A app.core.celery_app worker --loglevel=info --queues=sentiment_analysis
```

## Troubleshooting

### Common Issues

1. **Sentiment analysis not working**
   - Check DeepSeek API credentials
   - Verify Celery workers are running
   - Check sentiment analysis queue

2. **Alerts not being sent**
   - Verify notification channel configuration
   - Check SMTP/SMS credentials
   - Review alert thresholds

3. **Performance issues**
   - Monitor Prometheus metrics
   - Check database query performance
   - Scale Celery workers if needed

### Debug Mode

Enable debug logging for troubleshooting:

```python
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
)
```

## Support

For issues and questions:
- Check the logs for error messages
- Review Prometheus metrics for performance issues
- Consult the API documentation at `/docs`
- Contact the development team
