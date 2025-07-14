# Architecture Documentation

This directory contains architectural documentation for the WhatsApp Hotel Bot system.

## Files

- `system_overview.md` - High-level system architecture
- `component_diagram.md` - Component interaction diagrams
- `data_flow.md` - Data flow documentation
- `security_architecture.md` - Security design patterns
- `scalability_design.md` - Scalability considerations

## Architecture Principles

1. **Microservices Architecture** - Modular, loosely coupled services
2. **Event-Driven Design** - Asynchronous message processing
3. **Fault Tolerance** - Circuit breakers and retry mechanisms
4. **Scalability** - Horizontal scaling capabilities
5. **Security First** - Security by design principles

## Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Cache**: Redis
- **Message Queue**: Celery
- **AI Integration**: DeepSeek API
- **WhatsApp Integration**: Green API
- **Monitoring**: Prometheus + Grafana
- **Deployment**: Docker + Kubernetes
