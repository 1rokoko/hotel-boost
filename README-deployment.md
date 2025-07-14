# WhatsApp Hotel Bot - Production Deployment

This repository contains the production-ready deployment configuration for the WhatsApp Hotel Bot application, a multi-tenant AI-powered customer service solution for hotels.

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Kubernetes 1.24+
- kubectl configured
- Helm 3.8+ (optional)

### 1. Clone and Setup

```bash
git clone https://github.com/your-org/whatsapp-hotel-bot.git
cd whatsapp-hotel-bot
cp .env.example .env
# Edit .env with your configuration
```

### 2. Deploy with Docker Compose (Development/Testing)

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Deploy to Kubernetes (Production)

```bash
# Create namespace and secrets
kubectl create namespace hotel-bot
kubectl create secret generic whatsapp-hotel-bot-secrets --from-env-file=.env -n hotel-bot

# Deploy application
kubectl apply -f k8s/ -n hotel-bot

# Verify deployment
kubectl get pods -n hotel-bot
```

## 📋 Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Kubernetes    │    │   Monitoring    │
│   (Ingress)     │────│   Cluster       │────│   (Prometheus)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │                 │
                ┌──────▼──────┐   ┌──────▼──────┐
                │  FastAPI    │   │   Celery    │
                │  (3 pods)   │   │  Workers    │
                └──────┬──────┘   └──────┬──────┘
                       │                 │
                ┌──────▼─────────────────▼──────┐
                │                              │
         ┌──────▼──────┐              ┌──────▼──────┐
         │ PostgreSQL  │              │    Redis    │
         │ (Database)  │              │   (Cache)   │
         └─────────────┘              └─────────────┘
```

## 🛠 Components

### Core Services

- **FastAPI Application**: Main API server handling WhatsApp webhooks and HTTP requests
- **Celery Workers**: Background task processing for message handling and AI responses
- **Celery Beat**: Scheduled task management
- **PostgreSQL**: Primary database for persistent data
- **Redis**: Cache and message broker for Celery

### External Integrations

- **Green API**: WhatsApp Business API integration
- **DeepSeek AI**: AI-powered response generation and sentiment analysis
- **Prometheus**: Metrics collection and monitoring
- **Grafana**: Visualization and dashboards

## 📁 Directory Structure

```
├── k8s/                    # Kubernetes manifests
│   ├── deployment.yaml     # Application deployments
│   ├── service.yaml        # Kubernetes services
│   ├── ingress.yaml        # Ingress configuration
│   ├── configmap.yaml      # Configuration maps
│   └── secrets.yaml        # Secrets template
├── monitoring/             # Monitoring configuration
│   ├── prometheus.yml      # Prometheus config
│   ├── alerts.yml          # Alert rules
│   └── grafana-dashboard.json
├── scripts/                # Deployment and maintenance scripts
│   ├── deploy.sh           # Deployment script
│   ├── rollback.sh         # Rollback script
│   ├── smoke-tests.sh      # Health verification
│   ├── backup.py           # Database backup
│   ├── restore.py          # Database restore
│   └── db_maintenance.py   # Database maintenance
├── docs/                   # Documentation
│   ├── deployment.md       # Deployment guide
│   ├── operations.md       # Operations manual
│   └── troubleshooting.md  # Troubleshooting guide
├── .github/workflows/      # CI/CD pipelines
│   └── deploy.yml          # GitHub Actions workflow
├── Dockerfile.prod         # Production Docker image
├── docker-compose.prod.yml # Production Docker Compose
└── .dockerignore          # Docker ignore rules
```

## 🔧 Configuration

### Environment Variables

Key configuration variables (see `.env.example` for complete list):

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/hotel_bot

# Redis
REDIS_URL=redis://redis:6379

# External APIs
GREEN_API_INSTANCE_ID=your_instance_id
GREEN_API_TOKEN=your_api_token
DEEPSEEK_API_KEY=your_deepseek_api_key

# Security
SECRET_KEY=your-super-secret-key-change-in-production

# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

### Kubernetes Secrets

Create secrets for sensitive data:

```bash
kubectl create secret generic whatsapp-hotel-bot-secrets \
  --from-literal=database-url="postgresql+asyncpg://..." \
  --from-literal=redis-url="redis://..." \
  --from-literal=green-api-instance-id="..." \
  --from-literal=green-api-token="..." \
  --from-literal=deepseek-api-key="..." \
  --from-literal=secret-key="..." \
  -n hotel-bot
```

## 🚀 Deployment Options

### Option 1: Automated CI/CD

Push to main branch or create a release tag to trigger automated deployment:

```bash
git tag v1.0.0
git push origin v1.0.0
```

### Option 2: Manual Deployment

Use the deployment script:

```bash
./scripts/deploy.sh production ghcr.io/your-org/whatsapp-hotel-bot:v1.0.0
```

### Option 3: Docker Compose

For smaller deployments:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 📊 Monitoring

### Health Checks

- **Application Health**: `https://your-domain.com/health`
- **Readiness Check**: `https://your-domain.com/health/ready`
- **Metrics**: `https://your-domain.com/metrics` (if enabled)

### Monitoring Stack

- **Prometheus**: Metrics collection at `:9090`
- **Grafana**: Dashboards at `:3000`
- **Alerts**: Configured for critical issues

### Key Metrics

- API request rate and latency
- Celery queue length
- Database connection pool usage
- External API response times
- Error rates and availability

## 🔒 Security

### Security Features

- Non-root container execution
- Network policies for pod isolation
- TLS/SSL encryption for all traffic
- Secret management with Kubernetes secrets
- Regular security scanning with Trivy

### Security Checklist

- [ ] Update default passwords
- [ ] Configure SSL certificates
- [ ] Set up network policies
- [ ] Enable audit logging
- [ ] Configure backup encryption
- [ ] Set up secret rotation

## 🔄 Backup and Recovery

### Automated Backups

Daily automated backups are configured via CronJob:

```bash
# Check backup status
kubectl get cronjobs -n hotel-bot

# Manual backup
python scripts/backup.py --full
```

### Recovery Procedures

```bash
# List available backups
python scripts/restore.py --list-backups

# Restore from latest backup
python scripts/restore.py --latest --confirm

# Emergency rollback
./scripts/rollback.sh production
```

## 🔧 Maintenance

### Regular Maintenance

Weekly tasks:

```bash
# Database maintenance
python scripts/db_maintenance.py --all

# Check system health
./scripts/smoke-tests.sh production

# Review logs and metrics
kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot --since=24h
```

### Scaling

```bash
# Scale API pods
kubectl scale deployment whatsapp-hotel-bot-api --replicas=5 -n hotel-bot

# Scale Celery workers
kubectl scale deployment whatsapp-hotel-bot-celery-worker --replicas=3 -n hotel-bot
```

## 🆘 Troubleshooting

### Common Issues

1. **Pods not starting**: Check logs and resource limits
2. **Database connection issues**: Verify credentials and network connectivity
3. **External API failures**: Check API keys and rate limits
4. **High memory usage**: Scale pods or increase limits

### Quick Diagnostics

```bash
# Check overall status
kubectl get pods -n hotel-bot

# Check recent events
kubectl get events -n hotel-bot --sort-by='.lastTimestamp'

# Check application logs
kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot --tail=50

# Run health checks
./scripts/smoke-tests.sh production
```

## 📚 Documentation

- [Deployment Guide](docs/deployment.md) - Complete deployment instructions
- [Operations Manual](docs/operations.md) - Day-to-day operations
- [Troubleshooting Guide](docs/troubleshooting.md) - Problem resolution

## 🤝 Support

### Getting Help

1. Check the [troubleshooting guide](docs/troubleshooting.md)
2. Review application logs
3. Check monitoring dashboards
4. Contact the development team

### Emergency Contacts

- **On-call Engineer**: [contact information]
- **DevOps Team**: [contact information]
- **Product Owner**: [contact information]

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔄 Version History

- **v1.0.0**: Initial production release
- **v1.1.0**: Added monitoring and alerting
- **v1.2.0**: Enhanced security and backup features

---

For detailed deployment instructions, see [docs/deployment.md](docs/deployment.md)
