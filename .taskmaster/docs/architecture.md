# WhatsApp Hotel Bot - System Architecture

## Overview

The WhatsApp Hotel Bot is a comprehensive multi-tenant system designed to handle automated customer service for 50+ hotels through WhatsApp integration. The system provides AI-powered responses, sentiment analysis, and automated trigger-based interactions.

## High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WhatsApp      │    │   Hotel Staff   │    │   Admin Panel   │
│   Guests        │    │   Interface     │    │   Management    │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │                      │                      │
┌─────────▼──────────────────────▼──────────────────────▼───────┐
│                    API Gateway / Load Balancer                │
└─────────┬──────────────────────────────────────────────────┘
          │
┌─────────▼───────┐
│   FastAPI       │
│   Application   │
│   - Auth        │
│   - Routing     │
│   - Validation  │
└─────────┬───────┘
          │
┌─────────▼───────┐    ┌─────────────────┐    ┌─────────────────┐
│   Business      │    │   External      │    │   Reliability   │
│   Logic Layer   │    │   Integrations  │    │   Layer         │
│   - Hotels      │    │   - Green API   │    │   - Circuit     │
│   - Guests      │    │   - DeepSeek    │    │     Breakers    │
│   - Messages    │    │   - Webhooks    │    │   - Retry Logic │
│   - Triggers    │    │                 │    │   - Health      │
│   - Analytics   │    │                 │    │     Checks      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
┌─────────▼──────────────────────▼──────────────────────▼───────┐
│                    Message Queue (Celery)                     │
│   - Async Processing  - Background Tasks  - Scheduled Jobs    │
└─────────┬──────────────────────────────────────────────────┘
          │
┌─────────▼───────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │   Monitoring    │
│   Database      │    │   - Cache       │    │   - Prometheus  │
│   - Hotels      │    │   - Sessions    │    │   - Grafana     │
│   - Guests      │    │   - Rate Limit  │    │   - Logging     │
│   - Messages    │    │   - DLQ         │    │   - Alerting    │
│   - Analytics   │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Core Components

### 1. API Layer (FastAPI)
- **Authentication & Authorization** - JWT-based auth with role management
- **Request Validation** - Pydantic schema validation
- **Rate Limiting** - Per-user and per-endpoint rate limits
- **CORS Handling** - Cross-origin request support
- **API Documentation** - Auto-generated OpenAPI docs

### 2. Business Logic Layer
- **Hotel Management** - Multi-tenant hotel configuration
- **Guest Management** - Guest profiles and preferences
- **Message Processing** - Incoming/outgoing message handling
- **Trigger System** - Automated response triggers
- **Analytics Engine** - Performance and usage analytics
- **Template System** - Message template management

### 3. External Integrations
- **Green API** - WhatsApp Business API integration
- **DeepSeek AI** - Sentiment analysis and response generation
- **Webhook Processing** - Real-time message reception
- **Third-party APIs** - Additional service integrations

### 4. Reliability Layer
- **Circuit Breakers** - Fault tolerance for external services
- **Retry Logic** - Exponential backoff for transient failures
- **Health Checks** - System and dependency monitoring
- **Graceful Degradation** - Fallback mechanisms
- **Dead Letter Queue** - Failed message recovery

### 5. Data Layer
- **PostgreSQL** - Primary data storage
- **Redis** - Caching and session storage
- **Message Queue** - Asynchronous task processing
- **File Storage** - Media and document storage

### 6. Monitoring & Observability
- **Prometheus** - Metrics collection
- **Grafana** - Visualization and dashboards
- **Structured Logging** - Centralized log management
- **Alerting** - Proactive issue notification

## Data Flow

### Incoming Message Flow
1. **WhatsApp** → Green API webhook → **API Gateway**
2. **API Gateway** → FastAPI webhook endpoint
3. **FastAPI** → Message validation and parsing
4. **Business Logic** → Guest identification and context
5. **AI Processing** → Sentiment analysis (DeepSeek)
6. **Trigger Engine** → Automated response evaluation
7. **Response Generation** → AI or template-based response
8. **Message Queue** → Async message sending
9. **Green API** → WhatsApp message delivery

### Outgoing Message Flow
1. **Hotel Staff** → Admin interface or API
2. **API Gateway** → FastAPI message endpoint
3. **Business Logic** → Message validation and enrichment
4. **Message Queue** → Async processing
5. **Green API** → WhatsApp message delivery
6. **Status Updates** → Delivery confirmation handling

## Security Architecture

### Authentication & Authorization
- **JWT Tokens** - Stateless authentication
- **Role-Based Access** - Admin, hotel staff, guest roles
- **API Key Management** - External service authentication
- **Session Management** - Secure session handling

### Data Protection
- **Encryption at Rest** - Database encryption
- **Encryption in Transit** - TLS/SSL everywhere
- **PII Protection** - Personal data anonymization
- **Audit Logging** - Security event tracking

### Network Security
- **API Gateway** - Single entry point
- **Rate Limiting** - DDoS protection
- **IP Whitelisting** - Webhook source validation
- **CORS Policy** - Cross-origin protection

## Scalability Design

### Horizontal Scaling
- **Stateless Services** - Easy horizontal scaling
- **Load Balancing** - Traffic distribution
- **Database Sharding** - Data partitioning
- **Cache Distribution** - Redis clustering

### Performance Optimization
- **Connection Pooling** - Database connection efficiency
- **Query Optimization** - Database performance
- **Caching Strategy** - Multi-level caching
- **Async Processing** - Non-blocking operations

### Resource Management
- **Auto Scaling** - Dynamic resource allocation
- **Resource Limits** - Container resource constraints
- **Queue Management** - Message queue optimization
- **Memory Management** - Efficient memory usage

## Deployment Architecture

### Containerization
- **Docker Images** - Application containerization
- **Multi-stage Builds** - Optimized image sizes
- **Security Scanning** - Vulnerability detection
- **Registry Management** - Container image storage

### Orchestration
- **Kubernetes** - Container orchestration
- **Helm Charts** - Package management
- **Service Discovery** - Dynamic service location
- **Config Management** - Environment configuration

### CI/CD Pipeline
- **Source Control** - Git-based workflow
- **Automated Testing** - Unit, integration, e2e tests
- **Build Automation** - Automated image building
- **Deployment Automation** - Zero-downtime deployment

## Technology Stack

### Backend
- **Python 3.11+** - Programming language
- **FastAPI** - Web framework
- **SQLAlchemy** - ORM
- **Alembic** - Database migrations
- **Pydantic** - Data validation

### Database & Cache
- **PostgreSQL 15+** - Primary database
- **Redis 7+** - Cache and session store
- **Celery** - Task queue
- **RabbitMQ/Redis** - Message broker

### External Services
- **Green API** - WhatsApp integration
- **DeepSeek API** - AI processing
- **Prometheus** - Metrics
- **Grafana** - Visualization

### Infrastructure
- **Docker** - Containerization
- **Kubernetes** - Orchestration
- **Nginx** - Load balancer
- **Let's Encrypt** - SSL certificates

## Quality Attributes

### Reliability
- **99.9% Uptime** - High availability target
- **Circuit Breakers** - Fault tolerance
- **Graceful Degradation** - Service continuity
- **Automated Recovery** - Self-healing capabilities

### Performance
- **<200ms Response Time** - API response target
- **1000+ Concurrent Users** - Scalability target
- **Message Throughput** - High message processing
- **Resource Efficiency** - Optimized resource usage

### Security
- **Data Encryption** - End-to-end security
- **Access Control** - Strict authorization
- **Audit Trail** - Complete activity logging
- **Compliance** - GDPR and data protection

### Maintainability
- **Modular Design** - Loosely coupled components
- **Comprehensive Testing** - High test coverage
- **Documentation** - Complete system documentation
- **Monitoring** - Proactive issue detection
