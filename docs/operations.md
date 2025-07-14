# WhatsApp Hotel Bot - Operations Guide

This guide covers day-to-day operational procedures for maintaining and monitoring the WhatsApp Hotel Bot application in production.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Monitoring and Alerting](#monitoring-and-alerting)
3. [Backup and Recovery](#backup-and-recovery)
4. [Performance Tuning](#performance-tuning)
5. [Security Operations](#security-operations)
6. [Incident Response](#incident-response)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Scaling Operations](#scaling-operations)

## Daily Operations

### Morning Health Check

Perform these checks every morning:

```bash
# 1. Check overall system health
kubectl get pods -n hotel-bot
kubectl get services -n hotel-bot
kubectl get ingress -n hotel-bot

# 2. Check application health endpoints
curl -f https://your-domain.com/health
curl -f https://your-domain.com/health/ready

# 3. Check recent logs for errors
kubectl logs --since=24h deployment/whatsapp-hotel-bot-api -n hotel-bot | grep -i error

# 4. Check resource usage
kubectl top pods -n hotel-bot
kubectl top nodes

# 5. Verify external API connectivity
./scripts/smoke-tests.sh production
```

### Log Monitoring

Monitor application logs throughout the day:

```bash
# Follow real-time logs
kubectl logs -f deployment/whatsapp-hotel-bot-api -n hotel-bot

# Check for specific patterns
kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot | grep -E "(ERROR|CRITICAL|FATAL)"

# Monitor Celery worker logs
kubectl logs -f deployment/whatsapp-hotel-bot-celery-worker -n hotel-bot

# Check database logs (if accessible)
kubectl logs -f deployment/postgres -n hotel-bot
```

### Performance Monitoring

Check key performance metrics:

```bash
# API response times
curl -w "@curl-format.txt" -o /dev/null -s https://your-domain.com/health

# Database performance
python scripts/db_maintenance.py --health-check

# Queue lengths
kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- \
  python -c "from app.core.celery import celery_app; print(celery_app.control.inspect().active_queues())"
```

## Monitoring and Alerting

### Prometheus Metrics

Key metrics to monitor:

- **API Metrics**:
  - `http_requests_total` - Total HTTP requests
  - `http_request_duration_seconds` - Request latency
  - `http_requests_errors_total` - Error count

- **Application Metrics**:
  - `celery_queue_length` - Queue backlog
  - `database_connections_active` - DB connections
  - `green_api_requests_total` - External API calls
  - `deepseek_api_requests_total` - AI API calls

- **System Metrics**:
  - `container_memory_usage_bytes` - Memory usage
  - `container_cpu_usage_seconds_total` - CPU usage
  - `kube_pod_status_ready` - Pod readiness

### Grafana Dashboards

Access monitoring dashboards:

```bash
# Port-forward to Grafana
kubectl port-forward service/grafana 3000:3000 -n hotel-bot

# Open browser to http://localhost:3000
# Default credentials: admin/admin (change immediately)
```

Key dashboards to monitor:
- **Application Overview**: Overall system health
- **API Performance**: Request rates and latencies
- **Database Metrics**: Connection pools and query performance
- **External APIs**: Green API and DeepSeek API metrics
- **Infrastructure**: Kubernetes cluster metrics

### Alert Management

Common alerts and responses:

1. **API Down Alert**
   ```bash
   # Check pod status
   kubectl get pods -n hotel-bot -l component=api
   
   # Check recent events
   kubectl get events -n hotel-bot --sort-by='.lastTimestamp'
   
   # Restart if necessary
   kubectl rollout restart deployment/whatsapp-hotel-bot-api -n hotel-bot
   ```

2. **High Error Rate Alert**
   ```bash
   # Check error logs
   kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot | tail -100 | grep ERROR
   
   # Check external API status
   curl -I https://api.green-api.com
   curl -I https://api.deepseek.com
   ```

3. **Database Connection Alert**
   ```bash
   # Check database pod
   kubectl get pods -n hotel-bot -l app=postgres
   
   # Test database connectivity
   kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- \
     python -c "from app.core.database import engine; print(engine.execute('SELECT 1').scalar())"
   ```

## Backup and Recovery

### Daily Backup Verification

```bash
# Check backup status
kubectl get cronjobs -n hotel-bot

# Verify latest backup
python scripts/backup.py --list

# Test backup integrity
python scripts/backup.py --verify-only $(ls -t backups/*.sql.gz | head -1)
```

### Weekly Backup Testing

Perform weekly restore tests:

```bash
# Create test database
createdb hotel_bot_test

# Restore latest backup to test database
python scripts/restore.py \
  --backup $(ls -t backups/*.sql.gz | head -1) \
  --target-db hotel_bot_test \
  --create-db \
  --force

# Verify restore
psql hotel_bot_test -c "SELECT count(*) FROM hotels;"

# Cleanup test database
dropdb hotel_bot_test
```

### Emergency Recovery

In case of data loss:

```bash
# 1. Stop application
kubectl scale deployment whatsapp-hotel-bot-api --replicas=0 -n hotel-bot

# 2. Restore from latest backup
python scripts/restore.py --latest --drop-existing --create-db --confirm

# 3. Run database migrations if needed
python scripts/run_migrations.py --upgrade head

# 4. Restart application
kubectl scale deployment whatsapp-hotel-bot-api --replicas=3 -n hotel-bot

# 5. Verify functionality
./scripts/smoke-tests.sh production
```

## Performance Tuning

### Database Optimization

Weekly database maintenance:

```bash
# Run comprehensive maintenance
python scripts/db_maintenance.py --all

# Check for slow queries
python scripts/db_maintenance.py --health-check

# Optimize specific tables if needed
python scripts/db_maintenance.py --vacuum-all --table hotels --table messages
```

### Application Scaling

Monitor and adjust scaling:

```bash
# Check current resource usage
kubectl top pods -n hotel-bot

# Scale API pods based on load
kubectl scale deployment whatsapp-hotel-bot-api --replicas=5 -n hotel-bot

# Scale Celery workers for high queue load
kubectl scale deployment whatsapp-hotel-bot-celery-worker --replicas=4 -n hotel-bot

# Monitor scaling effects
kubectl get hpa -n hotel-bot  # If HPA is configured
```

### Cache Optimization

Monitor and manage Redis cache:

```bash
# Check Redis memory usage
kubectl exec deployment/redis -n hotel-bot -- redis-cli info memory

# Clear cache if needed (use with caution)
kubectl exec deployment/redis -n hotel-bot -- redis-cli flushdb

# Monitor cache hit rates
kubectl exec deployment/redis -n hotel-bot -- redis-cli info stats
```

## Security Operations

### Certificate Management

Monitor SSL certificate expiration:

```bash
# Check certificate expiration
kubectl get certificates -n hotel-bot

# Check cert-manager status
kubectl get certificaterequests -n hotel-bot

# Manual certificate renewal if needed
kubectl delete certificate whatsapp-hotel-bot-tls -n hotel-bot
kubectl apply -f k8s/ingress.yaml -n hotel-bot
```

### Security Scanning

Regular security checks:

```bash
# Scan container images for vulnerabilities
trivy image whatsapp-hotel-bot:latest

# Check for security updates
kubectl get pods -n hotel-bot -o jsonpath='{.items[*].spec.containers[*].image}' | \
  xargs -n1 trivy image

# Review access logs
kubectl logs deployment/nginx-ingress-controller -n ingress-nginx | grep -E "(401|403|404)"
```

### Secret Rotation

Rotate secrets regularly:

```bash
# Generate new secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update secret
kubectl patch secret whatsapp-hotel-bot-secrets \
  -p '{"data":{"secret-key":"<base64-encoded-new-key>"}}' \
  -n hotel-bot

# Restart pods to pick up new secret
kubectl rollout restart deployment/whatsapp-hotel-bot-api -n hotel-bot
```

## Incident Response

### Incident Classification

- **P0 (Critical)**: Complete service outage
- **P1 (High)**: Major functionality impaired
- **P2 (Medium)**: Minor functionality issues
- **P3 (Low)**: Cosmetic or documentation issues

### Response Procedures

1. **Immediate Response** (within 5 minutes):
   ```bash
   # Check overall system status
   kubectl get pods -n hotel-bot
   
   # Check recent events
   kubectl get events -n hotel-bot --sort-by='.lastTimestamp' | tail -20
   
   # Check application logs
   kubectl logs --since=10m deployment/whatsapp-hotel-bot-api -n hotel-bot
   ```

2. **Investigation** (within 15 minutes):
   ```bash
   # Gather diagnostic information
   kubectl describe pods -n hotel-bot
   kubectl top pods -n hotel-bot
   
   # Check external dependencies
   curl -I https://api.green-api.com
   curl -I https://api.deepseek.com
   
   # Check database connectivity
   kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- \
     python -c "from app.core.database import engine; print('DB OK' if engine.execute('SELECT 1').scalar() else 'DB FAIL')"
   ```

3. **Mitigation** (within 30 minutes):
   ```bash
   # Restart affected services
   kubectl rollout restart deployment/whatsapp-hotel-bot-api -n hotel-bot
   
   # Scale up if needed
   kubectl scale deployment whatsapp-hotel-bot-api --replicas=5 -n hotel-bot
   
   # Rollback if recent deployment caused issue
   ./scripts/rollback.sh production
   ```

### Communication

- Update status page
- Notify stakeholders via configured channels
- Document incident in incident management system

## Maintenance Procedures

### Planned Maintenance Windows

Monthly maintenance checklist:

```bash
# 1. Update system packages
kubectl get nodes -o wide  # Check node OS versions

# 2. Update application
./scripts/deploy.sh production new-image-tag

# 3. Database maintenance
python scripts/db_maintenance.py --all

# 4. Clean up old backups
python scripts/backup.py --cleanup

# 5. Review and rotate logs
kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot > monthly-logs.txt

# 6. Security updates
trivy image whatsapp-hotel-bot:latest
```

### Configuration Updates

Update application configuration:

```bash
# Update ConfigMap
kubectl patch configmap whatsapp-hotel-bot-config \
  -p '{"data":{"log-level":"DEBUG"}}' \
  -n hotel-bot

# Restart pods to pick up changes
kubectl rollout restart deployment/whatsapp-hotel-bot-api -n hotel-bot

# Verify changes
kubectl get configmap whatsapp-hotel-bot-config -o yaml -n hotel-bot
```

## Scaling Operations

### Horizontal Pod Autoscaling

Configure HPA for automatic scaling:

```bash
# Create HPA for API pods
kubectl autoscale deployment whatsapp-hotel-bot-api \
  --cpu-percent=70 \
  --min=3 \
  --max=10 \
  -n hotel-bot

# Monitor HPA status
kubectl get hpa -n hotel-bot

# Check scaling events
kubectl describe hpa whatsapp-hotel-bot-api -n hotel-bot
```

### Vertical Scaling

Adjust resource limits:

```bash
# Increase memory limits
kubectl patch deployment whatsapp-hotel-bot-api \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi","cpu":"2000m"}}}]}}}}' \
  -n hotel-bot

# Monitor resource usage after changes
kubectl top pods -n hotel-bot
```

### Database Scaling

For database scaling considerations:

```bash
# Monitor database performance
python scripts/db_maintenance.py --health-check

# Consider read replicas for read-heavy workloads
# Consider connection pooling optimization
# Consider database sharding for very large datasets
```

For emergency procedures and detailed troubleshooting, see [troubleshooting.md](troubleshooting.md).
