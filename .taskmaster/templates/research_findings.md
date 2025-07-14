# Research Findings for WhatsApp Hotel Bot MVP

## 1. Green API WhatsApp Integration Best Practices

### Key Findings:
- **Green API Compatibility**: Green API provides OpenAI-compatible endpoints, making integration straightforward
- **Webhook Architecture**: Use FastAPI webhook endpoints for real-time message processing
- **Rate Limiting**: Implement proper rate limiting to avoid API throttling
- **Message Status Tracking**: Essential for delivery confirmation and error handling

### Recommended Implementation:
```python
# Green API Client Setup
class GreenAPIClient:
    def __init__(self, instance_id: str, token: str):
        self.base_url = f"https://api.green-api.com/waInstance{instance_id}"
        self.token = token
    
    async def send_message(self, phone: str, message: str):
        url = f"{self.base_url}/sendMessage/{self.token}"
        payload = {
            "chatId": f"{phone}@c.us",
            "message": message
        }
        # Implement with httpx for async requests
    
    async def setup_webhook(self, webhook_url: str):
        # Configure webhook for incoming messages
        pass
```

### Best Practices:
- Use async/await for all API calls
- Implement retry logic with exponential backoff
- Store message IDs for tracking delivery status
- Handle different message types (text, media, location)

## 2. DeepSeek API Sentiment Analysis Integration

### Key Findings:
- **OpenAI Compatibility**: DeepSeek API is compatible with OpenAI SDK
- **Real-time Processing**: Suitable for real-time sentiment analysis
- **Cost Effective**: More affordable than GPT-4 for sentiment analysis tasks
- **Structured Output**: Supports JSON mode for structured responses

### Recommended Implementation:
```python
# DeepSeek Sentiment Analysis
class DeepSeekAnalyzer:
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    async def analyze_sentiment(self, message: str, context: dict = None):
        prompt = f"""
        Analyze the sentiment of this hotel guest message:
        Message: "{message}"
        Context: {context}
        
        Return JSON with:
        - sentiment: positive/negative/neutral
        - score: -1.0 to 1.0
        - requires_attention: boolean
        - reason: explanation
        """
        
        response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
```

### Performance Optimizations:
- Batch processing for multiple messages
- Caching common sentiment patterns
- Async processing to avoid blocking
- Fallback to rule-based analysis if API fails

## 3. Multi-tenant Architecture with Celery and Redis

### Key Findings:
- **Task Isolation**: Use separate queues per hotel for task isolation
- **Redis Clustering**: Consider Redis clustering for high availability
- **Celery Beat**: Use for scheduled trigger execution
- **Monitoring**: Implement Celery monitoring with Flower

### Recommended Architecture:
```python
# Multi-tenant Celery Configuration
class CeleryConfig:
    broker_url = 'redis://localhost:6379/0'
    result_backend = 'redis://localhost:6379/0'
    
    # Task routing for multi-tenancy
    task_routes = {
        'hotel_tasks.*': {'queue': 'hotel_queue'},
        'trigger_tasks.*': {'queue': 'trigger_queue'},
        'sentiment_tasks.*': {'queue': 'sentiment_queue'}
    }
    
    # Periodic tasks
    beat_schedule = {
        'process-triggers': {
            'task': 'trigger_tasks.process_scheduled_triggers',
            'schedule': 60.0,  # Every minute
        },
    }

# Hotel-specific task routing
@celery.task(bind=True)
def send_hotel_message(self, hotel_id: int, guest_id: int, message: str):
    # Route task to hotel-specific queue
    queue_name = f"hotel_{hotel_id}_queue"
    # Process message sending
```

### Scalability Considerations:
- Horizontal scaling with multiple worker nodes
- Queue partitioning by hotel for load distribution
- Redis Sentinel for high availability
- Monitoring and alerting for queue health

## 4. FastAPI Best Practices for WhatsApp Bot

### Project Structure:
```
app/
├── api/
│   ├── deps.py              # Dependencies
│   └── v1/
│       ├── endpoints/
│       │   ├── hotels.py    # Hotel management
│       │   ├── webhooks.py  # WhatsApp webhooks
│       │   ├── triggers.py  # Trigger management
│       │   └── analytics.py # Analytics endpoints
├── core/
│   ├── config.py           # Configuration
│   ├── security.py         # Authentication
│   └── database.py         # Database setup
├── models/                 # SQLAlchemy models
├── schemas/                # Pydantic schemas
├── services/               # Business logic
│   ├── whatsapp.py        # WhatsApp service
│   ├── sentiment.py       # Sentiment analysis
│   └── triggers.py        # Trigger processing
└── utils/                 # Utilities
```

### Security Best Practices:
- JWT authentication for API endpoints
- Webhook signature verification
- Rate limiting per hotel
- Input validation with Pydantic
- SQL injection prevention with SQLAlchemy

## 5. Database Optimization for Multi-tenant

### Indexing Strategy:
```sql
-- Performance indexes
CREATE INDEX idx_conversations_hotel_timestamp ON conversations(hotel_id, timestamp);
CREATE INDEX idx_guests_hotel_phone ON guests(hotel_id, phone_number);
CREATE INDEX idx_triggers_hotel_active ON triggers(hotel_id, is_active);
CREATE INDEX idx_sentiment_requires_attention ON conversations(requires_attention, hotel_id);
```

### Partitioning Strategy:
- Partition conversations table by hotel_id for large datasets
- Use time-based partitioning for historical data
- Implement data retention policies

## 6. Monitoring and Observability

### Recommended Stack:
- **Prometheus**: Metrics collection
- **Grafana**: Dashboards and visualization
- **Sentry**: Error tracking
- **Structured Logging**: JSON logs with correlation IDs

### Key Metrics to Monitor:
- Message processing latency
- Sentiment analysis accuracy
- Trigger execution success rate
- API response times
- Queue depth and processing rate

## 7. Testing Strategy

### Test Pyramid:
1. **Unit Tests**: Individual components (70%)
2. **Integration Tests**: API endpoints and services (20%)
3. **E2E Tests**: Full workflow testing (10%)

### Mock Strategy:
- Mock Green API responses
- Mock DeepSeek API for consistent testing
- Use test databases for integration tests
- Implement test fixtures for common scenarios

## Implementation Priority

### Phase 1 (Foundation):
1. FastAPI project setup
2. Database schema and migrations
3. Basic authentication
4. Green API integration

### Phase 2 (Core Features):
1. Message processing pipeline
2. Sentiment analysis integration
3. Trigger system
4. Admin API endpoints

### Phase 3 (Advanced):
1. Monitoring and alerting
2. Performance optimization
3. Comprehensive testing
4. Production deployment

## Risk Mitigation

### Technical Risks:
- **API Rate Limits**: Implement queuing and retry logic
- **Database Performance**: Proper indexing and query optimization
- **External API Failures**: Circuit breaker pattern and fallbacks
- **Scalability**: Horizontal scaling architecture from start

### Business Risks:
- **Data Privacy**: GDPR compliance for guest data
- **Message Delivery**: Backup notification channels
- **Hotel Onboarding**: Automated setup processes
- **Cost Management**: Usage monitoring and alerts
