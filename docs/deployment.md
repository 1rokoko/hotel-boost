# WhatsApp Hotel Bot - Deployment Guide

This guide covers the complete deployment process for the WhatsApp Hotel Bot application, including Docker, Kubernetes, and CI/CD setup.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [Monitoring Setup](#monitoring-setup)
7. [Backup Configuration](#backup-configuration)
8. [Security Considerations](#security-considerations)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Docker**: Version 20.10 or higher
- **Kubernetes**: Version 1.24 or higher
- **kubectl**: Compatible with your Kubernetes cluster
- **Helm**: Version 3.8 or higher (optional)
- **Git**: Version 2.30 or higher

### Infrastructure Requirements

- **CPU**: Minimum 4 cores (8 cores recommended for production)
- **Memory**: Minimum 8GB RAM (16GB recommended for production)
- **Storage**: Minimum 50GB available space
- **Network**: Stable internet connection for external API access

### External Services

- **PostgreSQL**: Version 15 or higher
- **Redis**: Version 7 or higher
- **Green API**: Active WhatsApp API instance
- **DeepSeek API**: Valid API key for AI services

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/whatsapp-hotel-bot.git
cd whatsapp-hotel-bot
```

### 2. Environment Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your specific configuration:

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hotel_bot

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Green API Configuration
GREEN_API_INSTANCE_ID=your_instance_id
GREEN_API_TOKEN=your_api_token

# DeepSeek AI Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key

# Security
SECRET_KEY=your-super-secret-key-change-in-production

# Application Settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

### 3. SSL/TLS Certificates

For production deployments, ensure you have valid SSL certificates:

```bash
# Using Let's Encrypt with cert-manager (recommended)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Or provide your own certificates
kubectl create secret tls whatsapp-hotel-bot-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  -n hotel-bot
```

## Docker Deployment

### 1. Build Production Image

```bash
# Build the production Docker image
docker build -f Dockerfile.prod -t whatsapp-hotel-bot:latest .

# Tag for registry (if using)
docker tag whatsapp-hotel-bot:latest your-registry/whatsapp-hotel-bot:v1.0.0
```

### 2. Docker Compose Deployment

For simple deployments or development:

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f api
```

### 3. Environment Variables for Docker

Create a production environment file:

```bash
# Create production environment file
cp .env.example .env.prod

# Edit with production values
nano .env.prod
```

## Kubernetes Deployment

### 1. Namespace Setup

```bash
# Create namespace
kubectl create namespace hotel-bot

# Label namespace for monitoring
kubectl label namespace hotel-bot name=hotel-bot
```

### 2. Secrets Configuration

Create Kubernetes secrets from your environment variables:

```bash
# Create secrets from .env file
kubectl create secret generic whatsapp-hotel-bot-secrets \
  --from-env-file=.env.prod \
  -n hotel-bot

# Or create individual secrets
kubectl create secret generic whatsapp-hotel-bot-secrets \
  --from-literal=database-url="postgresql+asyncpg://user:password@postgres:5432/hotel_bot" \
  --from-literal=redis-url="redis://:password@redis:6379" \
  --from-literal=green-api-instance-id="your_instance_id" \
  --from-literal=green-api-token="your_api_token" \
  --from-literal=deepseek-api-key="your_deepseek_api_key" \
  --from-literal=secret-key="your-super-secret-key" \
  -n hotel-bot
```

### 3. Deploy Application

```bash
# Apply ConfigMaps
kubectl apply -f k8s/configmap.yaml -n hotel-bot

# Apply Secrets (if using YAML files)
kubectl apply -f k8s/secrets-production.yaml -n hotel-bot

# Deploy services
kubectl apply -f k8s/service.yaml -n hotel-bot

# Deploy applications
kubectl apply -f k8s/deployment.yaml -n hotel-bot

# Deploy ingress
kubectl apply -f k8s/ingress.yaml -n hotel-bot
```

### 4. Verify Deployment

```bash
# Check pod status
kubectl get pods -n hotel-bot

# Check services
kubectl get services -n hotel-bot

# Check ingress
kubectl get ingress -n hotel-bot

# View logs
kubectl logs -f deployment/whatsapp-hotel-bot-api -n hotel-bot
```

### 5. Database Migration

Run database migrations after deployment:

```bash
# Run migrations using a job
kubectl run migration-job \
  --image=whatsapp-hotel-bot:latest \
  --restart=Never \
  --env="DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/hotel_bot" \
  --command -- python scripts/run_migrations.py --upgrade head \
  -n hotel-bot

# Check migration status
kubectl logs migration-job -n hotel-bot

# Clean up job
kubectl delete pod migration-job -n hotel-bot
```

## CI/CD Pipeline

### 1. GitHub Actions Setup

The CI/CD pipeline is configured in `.github/workflows/deploy.yml`. Set up the following secrets in your GitHub repository:

```bash
# Required GitHub Secrets:
GITHUB_TOKEN                 # Automatically provided
KUBE_CONFIG_STAGING         # Base64 encoded kubeconfig for staging
KUBE_CONFIG_PRODUCTION      # Base64 encoded kubeconfig for production
```

### 2. Pipeline Stages

The pipeline includes the following stages:

1. **Test**: Run unit tests, integration tests, and security scans
2. **Build**: Build and push Docker images to registry
3. **Deploy Staging**: Deploy to staging environment (develop branch)
4. **Deploy Production**: Deploy to production environment (tags)

### 3. Manual Deployment

For manual deployments, use the provided scripts:

```bash
# Deploy to staging
./scripts/deploy.sh staging ghcr.io/your-org/whatsapp-hotel-bot:develop

# Deploy to production
./scripts/deploy.sh production ghcr.io/your-org/whatsapp-hotel-bot:v1.0.0

# Rollback if needed
./scripts/rollback.sh production

# Run smoke tests
./scripts/smoke-tests.sh production
```

## Monitoring Setup

### 1. Prometheus Configuration

Deploy Prometheus for metrics collection:

```bash
# Apply Prometheus configuration
kubectl apply -f monitoring/prometheus.yml -n hotel-bot

# Deploy Prometheus
kubectl create deployment prometheus \
  --image=prom/prometheus:latest \
  -n hotel-bot

# Expose Prometheus service
kubectl expose deployment prometheus \
  --port=9090 \
  --target-port=9090 \
  -n hotel-bot
```

### 2. Grafana Dashboard

Deploy Grafana for visualization:

```bash
# Deploy Grafana
kubectl create deployment grafana \
  --image=grafana/grafana:latest \
  -n hotel-bot

# Expose Grafana service
kubectl expose deployment grafana \
  --port=3000 \
  --target-port=3000 \
  -n hotel-bot

# Import dashboard
kubectl create configmap grafana-dashboard \
  --from-file=monitoring/grafana-dashboard.json \
  -n hotel-bot
```

### 3. Alerting Setup

Configure alerting rules:

```bash
# Apply alert rules
kubectl create configmap prometheus-alerts \
  --from-file=monitoring/alerts.yml \
  -n hotel-bot
```

## Backup Configuration

### 1. Automated Backups

Set up automated database backups:

```bash
# Create backup CronJob
kubectl create cronjob database-backup \
  --image=whatsapp-hotel-bot:latest \
  --schedule="0 2 * * *" \
  --restart=OnFailure \
  --command -- python scripts/backup.py --full \
  -n hotel-bot

# Verify CronJob
kubectl get cronjobs -n hotel-bot
```

### 2. Manual Backup

Create manual backups when needed:

```bash
# Run backup script
python scripts/backup.py --full

# List available backups
python scripts/backup.py --list

# Verify backup
python scripts/backup.py --verify-only backup_file.sql.gz
```

### 3. Restore Procedures

Restore from backup when needed:

```bash
# List available backups
python scripts/restore.py --list-backups

# Restore from latest backup
python scripts/restore.py --latest --confirm

# Restore from specific backup
python scripts/restore.py --backup hotel_bot_full_20240101_120000.sql.gz --confirm
```

## Security Considerations

### 1. Network Security

- Use network policies to restrict pod-to-pod communication
- Configure ingress with proper SSL/TLS termination
- Implement rate limiting at the ingress level

### 2. Secret Management

- Store sensitive data in Kubernetes secrets
- Use external secret management systems (e.g., HashiCorp Vault)
- Rotate secrets regularly

### 3. Container Security

- Run containers as non-root users
- Use minimal base images
- Scan images for vulnerabilities
- Implement resource limits and quotas

### 4. Access Control

- Use RBAC for Kubernetes access control
- Implement proper authentication for monitoring endpoints
- Audit access logs regularly

## Troubleshooting

### Common Issues

1. **Pod Startup Failures**
   ```bash
   # Check pod events
   kubectl describe pod <pod-name> -n hotel-bot
   
   # Check logs
   kubectl logs <pod-name> -n hotel-bot
   ```

2. **Database Connection Issues**
   ```bash
   # Test database connectivity
   kubectl run db-test \
     --image=postgres:15-alpine \
     --rm -it \
     --restart=Never \
     --env="PGPASSWORD=password" \
     -- psql -h postgres -U user -d hotel_bot
   ```

3. **External API Issues**
   ```bash
   # Check API connectivity from pod
   kubectl exec -it <pod-name> -n hotel-bot -- curl -v https://api.green-api.com
   ```

### Performance Issues

1. **High Memory Usage**
   ```bash
   # Check resource usage
   kubectl top pods -n hotel-bot
   
   # Adjust resource limits
   kubectl patch deployment whatsapp-hotel-bot-api \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi"}}}]}}}}' \
     -n hotel-bot
   ```

2. **Database Performance**
   ```bash
   # Run maintenance script
   python scripts/db_maintenance.py --health-check --vacuum-all
   ```

### Monitoring and Alerts

1. **Check Application Health**
   ```bash
   # Health check endpoint
   curl https://your-domain.com/health
   
   # Detailed health check
   curl https://your-domain.com/health/ready
   ```

2. **Monitor Logs**
   ```bash
   # Follow application logs
   kubectl logs -f deployment/whatsapp-hotel-bot-api -n hotel-bot
   
   # Check error logs
   kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot | grep ERROR
   ```

For additional troubleshooting, see [troubleshooting.md](troubleshooting.md) and [operations.md](operations.md).
