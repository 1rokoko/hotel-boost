# DeepSeek AI Integration

This document describes the comprehensive DeepSeek AI integration implemented for the WhatsApp Hotel Bot project.

## Overview

The DeepSeek AI integration provides advanced sentiment analysis and intelligent response generation capabilities for hotel guest communications. The system is designed to be scalable, reliable, and cost-effective.

## Features

### 1. Sentiment Analysis
- **Real-time Analysis**: Automatic sentiment analysis of all incoming guest messages
- **Multi-language Support**: Configurable language detection and analysis
- **Confidence Scoring**: Each analysis includes a confidence score (0.0-1.0)
- **Attention Alerts**: Automatic flagging of messages requiring staff attention
- **Staff Notifications**: Automated alerts for negative sentiment requiring immediate response

### 2. Response Generation
- **Context-Aware**: Responses consider conversation history, guest preferences, and hotel settings
- **Multiple Response Types**: Helpful, apologetic, informational, escalation, booking assistance, etc.
- **Brand Voice**: Customizable hotel branding and voice in responses
- **Multilingual**: Support for multiple languages with automatic detection
- **Quality Control**: Response validation and post-processing

### 3. Performance Optimization
- **Redis Caching**: Intelligent caching of AI responses to reduce API calls and costs
- **Token Optimization**: Advanced text optimization to minimize token usage
- **Rate Limiting**: Built-in rate limiting to prevent API quota exhaustion
- **Batch Processing**: Efficient batch processing for multiple requests

### 4. Monitoring and Analytics
- **Real-time Metrics**: Live performance monitoring and metrics
- **Health Monitoring**: System health checks and performance alerts
- **Usage Analytics**: Detailed analytics on AI usage, costs, and performance
- **Daily Summaries**: Automated daily sentiment summaries for each hotel

## Architecture

### Core Components

1. **DeepSeek Client** (`app/services/deepseek_client.py`)
   - Async HTTP client with retry logic
   - Rate limiting and circuit breaker patterns
   - Token usage tracking

2. **Sentiment Analyzer** (`app/services/sentiment_analyzer.py`)
   - AI-powered sentiment analysis
   - Database storage and retrieval
   - Notification triggers

3. **Response Generator** (`app/services/response_generator.py`)
   - Context-aware response generation
   - Template management system
   - Multi-type response handling

4. **Caching Service** (`app/services/deepseek_cache.py`)
   - Redis-based response caching
   - Cache invalidation strategies
   - Performance optimization

5. **Token Optimizer** (`app/services/token_optimizer.py`)
   - Text optimization for token efficiency
   - Context compression
   - Usage analytics

6. **Monitoring Service** (`app/services/deepseek_monitoring.py`)
   - Real-time performance monitoring
   - Alert generation
   - Analytics and reporting

### Database Models

- **SentimentAnalysis**: Stores sentiment analysis results
- **SentimentSummary**: Daily aggregated sentiment data
- **DeepSeekOperationLog**: Operation logs and metrics

### API Endpoints

- `GET /api/v1/deepseek/health` - System health report
- `GET /api/v1/deepseek/metrics` - Real-time metrics
- `GET /api/v1/deepseek/alerts` - Performance alerts
- `GET /api/v1/deepseek/hotels/{hotel_id}/sentiment-metrics` - Hotel sentiment metrics
- `GET /api/v1/deepseek/logs` - Operation logs
- `POST /api/v1/deepseek/hotels/{hotel_id}/generate-summary` - Generate daily summary

## Configuration

### Environment Variables

```bash
# DeepSeek API Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_URL=https://api.deepseek.com
DEEPSEEK_MAX_TOKENS=4096
DEEPSEEK_TEMPERATURE=0.7
DEEPSEEK_TIMEOUT=60
DEEPSEEK_MAX_REQUESTS_PER_MINUTE=50
DEEPSEEK_MAX_TOKENS_PER_MINUTE=100000
DEEPSEEK_MAX_RETRIES=3
DEEPSEEK_RETRY_DELAY=1.0
DEEPSEEK_CACHE_ENABLED=true
DEEPSEEK_CACHE_TTL=3600

# Sentiment Analysis Configuration
SENTIMENT_POSITIVE_THRESHOLD=0.3
SENTIMENT_NEGATIVE_THRESHOLD=-0.3
SENTIMENT_ATTENTION_THRESHOLD=-0.7
SENTIMENT_MIN_CONFIDENCE=0.6
SENTIMENT_NOTIFY_ON_NEGATIVE=true
SENTIMENT_NOTIFY_ON_ATTENTION=true
SENTIMENT_DEFAULT_LANGUAGE=en

# Response Generation Configuration
RESPONSE_MAX_TOKENS=500
RESPONSE_TEMPERATURE=0.8
RESPONSE_MAX_CONTEXT_MESSAGES=10
RESPONSE_INCLUDE_GUEST_HISTORY=true
RESPONSE_MIN_LENGTH=10
RESPONSE_MAX_LENGTH=1000
RESPONSE_USE_GUEST_PREFERENCES=true
RESPONSE_USE_HOTEL_BRANDING=true
```

## Usage

### Automatic Processing

The system automatically processes incoming messages through Celery tasks:

1. **Message Received** → Triggers sentiment analysis
2. **Sentiment Analysis** → Stores results and triggers notifications if needed
3. **Response Generation** → Can be triggered manually or automatically
4. **Monitoring** → Continuous performance monitoring and alerting

### Manual Operations

```python
# Analyze sentiment
from app.services.sentiment_analyzer import SentimentAnalyzer
analyzer = SentimentAnalyzer(db)
result = await analyzer.analyze_message_sentiment(message)

# Generate response
from app.services.response_generator import ResponseGenerator
generator = ResponseGenerator(db)
response = await generator.generate_response(message)

# Get metrics
from app.services.deepseek_monitoring import get_monitoring_service
monitoring = get_monitoring_service(db)
metrics = monitoring.get_real_time_metrics()
```

### Celery Tasks

```python
# Analyze sentiment (async)
from app.tasks.analyze_sentiment import analyze_message_sentiment_task
analyze_message_sentiment_task.delay(message_id)

# Generate response (async)
from app.tasks.generate_response import generate_response_task
generate_response_task.delay(message_id, auto_send=True)

# Daily maintenance
from app.tasks.deepseek_monitoring import generate_daily_sentiment_summaries_task
generate_daily_sentiment_summaries_task.delay()
```

## Testing

### Unit Tests
- `tests/unit/test_deepseek_client.py` - DeepSeek client tests
- `tests/unit/test_sentiment_analyzer.py` - Sentiment analysis tests
- `tests/unit/test_response_generator.py` - Response generation tests

### Integration Tests
- `tests/integration/test_deepseek_integration.py` - End-to-end integration tests

### Running Tests

```bash
# Run all DeepSeek tests
pytest tests/ -k "deepseek" -v

# Run with coverage
pytest tests/ -k "deepseek" --cov=app.services --cov-report=html
```

## Monitoring and Maintenance

### Daily Tasks
- Sentiment summary generation
- Log cleanup
- Performance monitoring

### Weekly Tasks
- Performance report generation
- Cache optimization
- Usage analytics review

### Alerts
- High response times (>10 seconds)
- High error rates (>5%)
- High token usage
- Low confidence scores

## Cost Optimization

### Caching Strategy
- Cache sentiment analysis results for identical text
- Cache response generation for similar contexts
- Configurable TTL based on content type

### Token Optimization
- Text compression and optimization
- Context truncation for long conversations
- Prompt optimization for efficiency

### Rate Limiting
- Configurable request and token limits
- Exponential backoff for rate limit hits
- Queue management for high-volume periods

## Security Considerations

- API keys stored securely in environment variables
- Input validation for all AI prompts
- Rate limiting to prevent abuse
- Audit logging for all operations

## Troubleshooting

### Common Issues

1. **API Key Invalid**
   - Check DEEPSEEK_API_KEY environment variable
   - Verify API key with DeepSeek dashboard

2. **High Response Times**
   - Check network connectivity
   - Review rate limiting settings
   - Monitor DeepSeek API status

3. **Cache Issues**
   - Verify Redis connection
   - Check cache configuration
   - Review cache hit rates

4. **Low Confidence Scores**
   - Review input text quality
   - Check language detection
   - Adjust confidence thresholds

### Logs and Debugging

```bash
# View DeepSeek operation logs
curl -X GET "http://localhost:8000/api/v1/deepseek/logs?limit=50"

# Check system health
curl -X GET "http://localhost:8000/api/v1/deepseek/health"

# View performance metrics
curl -X GET "http://localhost:8000/api/v1/deepseek/metrics"
```

## Future Enhancements

- Advanced prompt engineering
- Custom model fine-tuning
- Multi-model ensemble approaches
- Advanced analytics and reporting
- Integration with business intelligence tools

## Support

For technical support or questions about the DeepSeek integration, please refer to:
- Project documentation
- API endpoint documentation
- Test cases for usage examples
- Monitoring dashboards for system health
