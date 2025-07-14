# WhatsApp Hotel Bot - Troubleshooting Guide

This guide provides solutions for common issues encountered when running the WhatsApp Hotel Bot application.

## Table of Contents

1. [Application Issues](#application-issues)
2. [Database Issues](#database-issues)
3. [External API Issues](#external-api-issues)
4. [Kubernetes Issues](#kubernetes-issues)
5. [Performance Issues](#performance-issues)
6. [Security Issues](#security-issues)
7. [Monitoring Issues](#monitoring-issues)
8. [Emergency Procedures](#emergency-procedures)

## Application Issues

### API Not Responding

**Symptoms**: HTTP requests timeout or return 5xx errors

**Diagnosis**:
```bash
# Check pod status
kubectl get pods -n hotel-bot -l component=api

# Check pod logs
kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot --tail=50

# Check service endpoints
kubectl get endpoints whatsapp-hotel-bot-api -n hotel-bot

# Test internal connectivity
kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- curl localhost:8000/health
```

**Solutions**:
1. **Pod not ready**:
   ```bash
   # Check readiness probe
   kubectl describe pod <pod-name> -n hotel-bot
   
   # Restart deployment
   kubectl rollout restart deployment/whatsapp-hotel-bot-api -n hotel-bot
   ```

2. **Resource constraints**:
   ```bash
   # Check resource usage
   kubectl top pods -n hotel-bot
   
   # Increase resource limits
   kubectl patch deployment whatsapp-hotel-bot-api \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi","cpu":"2000m"}}}]}}}}' \
     -n hotel-bot
   ```

3. **Configuration issues**:
   ```bash
   # Check environment variables
   kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- env | grep -E "(DATABASE|REDIS|API)"
   
   # Verify secrets
   kubectl get secret whatsapp-hotel-bot-secrets -o yaml -n hotel-bot
   ```

### Celery Workers Not Processing Tasks

**Symptoms**: Tasks accumulating in queue, no task processing

**Diagnosis**:
```bash
# Check worker pods
kubectl get pods -n hotel-bot -l component=celery-worker

# Check worker logs
kubectl logs deployment/whatsapp-hotel-bot-celery-worker -n hotel-bot

# Check queue status
kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- \
  python -c "from app.core.celery import celery_app; print(celery_app.control.inspect().active_queues())"
```

**Solutions**:
1. **Worker pods down**:
   ```bash
   kubectl rollout restart deployment/whatsapp-hotel-bot-celery-worker -n hotel-bot
   ```

2. **Redis connectivity issues**:
   ```bash
   # Test Redis connection
   kubectl exec deployment/whatsapp-hotel-bot-celery-worker -n hotel-bot -- \
     python -c "import redis; r=redis.from_url('redis://redis:6379'); print(r.ping())"
   ```

3. **Queue backlog**:
   ```bash
   # Scale up workers
   kubectl scale deployment whatsapp-hotel-bot-celery-worker --replicas=4 -n hotel-bot
   
   # Purge old tasks if necessary
   kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- \
     python -c "from app.core.celery import celery_app; celery_app.control.purge()"
   ```

### Application Startup Failures

**Symptoms**: Pods in CrashLoopBackOff state

**Diagnosis**:
```bash
# Check pod events
kubectl describe pod <pod-name> -n hotel-bot

# Check startup logs
kubectl logs <pod-name> -n hotel-bot --previous

# Check liveness/readiness probes
kubectl get pod <pod-name> -o yaml -n hotel-bot | grep -A 10 -B 5 probe
```

**Solutions**:
1. **Database migration issues**:
   ```bash
   # Run migrations manually
   kubectl run migration-job \
     --image=whatsapp-hotel-bot:latest \
     --restart=Never \
     --env="DATABASE_URL=..." \
     --command -- python scripts/run_migrations.py --upgrade head \
     -n hotel-bot
   ```

2. **Missing environment variables**:
   ```bash
   # Check required environment variables
   kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- \
     python -c "from app.core.config import settings; print('Config OK')"
   ```

3. **Image pull issues**:
   ```bash
   # Check image pull secrets
   kubectl get pods <pod-name> -o yaml -n hotel-bot | grep imagePullSecrets
   
   # Verify image exists
   docker pull whatsapp-hotel-bot:latest
   ```

## Database Issues

### Database Connection Failures

**Symptoms**: "Connection refused" or "Connection timeout" errors

**Diagnosis**:
```bash
# Check PostgreSQL pod
kubectl get pods -n hotel-bot -l app=postgres

# Check PostgreSQL logs
kubectl logs deployment/postgres -n hotel-bot

# Test connection from application pod
kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- \
  pg_isready -h postgres -p 5432
```

**Solutions**:
1. **PostgreSQL pod down**:
   ```bash
   kubectl rollout restart deployment/postgres -n hotel-bot
   ```

2. **Network connectivity**:
   ```bash
   # Check service
   kubectl get service postgres -n hotel-bot
   
   # Test DNS resolution
   kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- nslookup postgres
   ```

3. **Authentication issues**:
   ```bash
   # Verify database credentials
   kubectl get secret postgres-secrets -o yaml -n hotel-bot
   
   # Test authentication
   kubectl exec deployment/postgres -n hotel-bot -- \
     psql -U postgres -d hotel_bot -c "SELECT 1"
   ```

### Database Performance Issues

**Symptoms**: Slow query responses, high CPU usage

**Diagnosis**:
```bash
# Run database health check
python scripts/db_maintenance.py --health-check

# Check active connections
kubectl exec deployment/postgres -n hotel-bot -- \
  psql -U postgres -d hotel_bot -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"

# Check slow queries
kubectl exec deployment/postgres -n hotel-bot -- \
  psql -U postgres -d hotel_bot -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10"
```

**Solutions**:
1. **Run maintenance**:
   ```bash
   python scripts/db_maintenance.py --vacuum-all --analyze-all
   ```

2. **Optimize queries**:
   ```bash
   # Check for missing indexes
   python scripts/db_maintenance.py --health-check
   ```

3. **Scale database resources**:
   ```bash
   kubectl patch deployment postgres \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"postgres","resources":{"limits":{"memory":"4Gi","cpu":"2000m"}}}]}}}}' \
     -n hotel-bot
   ```

### Database Corruption

**Symptoms**: Data inconsistencies, constraint violations

**Diagnosis**:
```bash
# Check database integrity
kubectl exec deployment/postgres -n hotel-bot -- \
  psql -U postgres -d hotel_bot -c "SELECT datname, pg_database_size(datname) FROM pg_database WHERE datname = 'hotel_bot'"

# Check for corruption
kubectl exec deployment/postgres -n hotel-bot -- \
  psql -U postgres -d hotel_bot -c "VACUUM VERBOSE"
```

**Solutions**:
1. **Restore from backup**:
   ```bash
   # Stop application
   kubectl scale deployment whatsapp-hotel-bot-api --replicas=0 -n hotel-bot
   
   # Restore database
   python scripts/restore.py --latest --drop-existing --create-db --confirm
   
   # Restart application
   kubectl scale deployment whatsapp-hotel-bot-api --replicas=3 -n hotel-bot
   ```

## External API Issues

### Green API Connection Issues

**Symptoms**: WhatsApp messages not sending/receiving

**Diagnosis**:
```bash
# Test Green API connectivity
curl -X GET "https://api.green-api.com/waInstance{instanceId}/getStateInstance/{apiTokenInstance}"

# Check application logs for Green API errors
kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot | grep -i "green.*api"

# Verify API credentials
kubectl exec deployment/whatsapp-hotel-bot-api -n hotel-bot -- \
  python -c "from app.core.config import settings; print(f'Instance: {settings.GREEN_API_INSTANCE_ID}')"
```

**Solutions**:
1. **Invalid credentials**:
   ```bash
   # Update Green API credentials
   kubectl patch secret whatsapp-hotel-bot-secrets \
     -p '{"data":{"green-api-instance-id":"<base64-encoded-id>","green-api-token":"<base64-encoded-token>"}}' \
     -n hotel-bot
   
   # Restart pods
   kubectl rollout restart deployment/whatsapp-hotel-bot-api -n hotel-bot
   ```

2. **Rate limiting**:
   ```bash
   # Check rate limit status
   curl -X GET "https://api.green-api.com/waInstance{instanceId}/getSettings/{apiTokenInstance}"
   
   # Implement exponential backoff in application
   ```

3. **WhatsApp instance not ready**:
   ```bash
   # Check instance status
   curl -X GET "https://api.green-api.com/waInstance{instanceId}/getStateInstance/{apiTokenInstance}"
   
   # Restart WhatsApp instance if needed
   curl -X GET "https://api.green-api.com/waInstance{instanceId}/reboot/{apiTokenInstance}"
   ```

### DeepSeek API Issues

**Symptoms**: AI responses not generating, API errors

**Diagnosis**:
```bash
# Test DeepSeek API connectivity
curl -X POST "https://api.deepseek.com/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}]}'

# Check application logs for DeepSeek errors
kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot | grep -i "deepseek"
```

**Solutions**:
1. **API key issues**:
   ```bash
   # Update DeepSeek API key
   kubectl patch secret whatsapp-hotel-bot-secrets \
     -p '{"data":{"deepseek-api-key":"<base64-encoded-key>"}}' \
     -n hotel-bot
   ```

2. **Rate limiting**:
   ```bash
   # Check rate limit headers in logs
   # Implement request queuing in application
   ```

3. **Model availability**:
   ```bash
   # Check available models
   curl -X GET "https://api.deepseek.com/v1/models" \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

## Kubernetes Issues

### Pod Scheduling Issues

**Symptoms**: Pods stuck in Pending state

**Diagnosis**:
```bash
# Check pod events
kubectl describe pod <pod-name> -n hotel-bot

# Check node resources
kubectl top nodes

# Check node conditions
kubectl get nodes -o wide
```

**Solutions**:
1. **Insufficient resources**:
   ```bash
   # Reduce resource requests
   kubectl patch deployment whatsapp-hotel-bot-api \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"requests":{"memory":"256Mi","cpu":"100m"}}}]}}}}' \
     -n hotel-bot
   ```

2. **Node affinity issues**:
   ```bash
   # Remove node selectors if present
   kubectl patch deployment whatsapp-hotel-bot-api \
     -p '{"spec":{"template":{"spec":{"nodeSelector":null}}}}' \
     -n hotel-bot
   ```

### Ingress Issues

**Symptoms**: External traffic not reaching application

**Diagnosis**:
```bash
# Check ingress status
kubectl get ingress -n hotel-bot

# Check ingress controller logs
kubectl logs -n ingress-nginx deployment/nginx-ingress-controller

# Test internal service
kubectl port-forward service/whatsapp-hotel-bot-api 8080:8000 -n hotel-bot
```

**Solutions**:
1. **DNS issues**:
   ```bash
   # Check DNS resolution
   nslookup your-domain.com
   
   # Update DNS records if needed
   ```

2. **Certificate issues**:
   ```bash
   # Check certificate status
   kubectl get certificates -n hotel-bot
   
   # Check cert-manager logs
   kubectl logs -n cert-manager deployment/cert-manager
   ```

3. **Ingress controller issues**:
   ```bash
   # Restart ingress controller
   kubectl rollout restart deployment/nginx-ingress-controller -n ingress-nginx
   ```

## Performance Issues

### High Memory Usage

**Symptoms**: Pods being OOMKilled, high memory consumption

**Diagnosis**:
```bash
# Check memory usage
kubectl top pods -n hotel-bot

# Check memory limits
kubectl describe pod <pod-name> -n hotel-bot | grep -A 5 -B 5 memory

# Check for memory leaks in logs
kubectl logs deployment/whatsapp-hotel-bot-api -n hotel-bot | grep -i "memory\|oom"
```

**Solutions**:
1. **Increase memory limits**:
   ```bash
   kubectl patch deployment whatsapp-hotel-bot-api \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi"}}}]}}}}' \
     -n hotel-bot
   ```

2. **Optimize application**:
   ```bash
   # Enable memory profiling
   # Review code for memory leaks
   # Implement connection pooling
   ```

### High CPU Usage

**Symptoms**: Slow response times, CPU throttling

**Diagnosis**:
```bash
# Check CPU usage
kubectl top pods -n hotel-bot

# Check CPU limits
kubectl describe pod <pod-name> -n hotel-bot | grep -A 5 -B 5 cpu
```

**Solutions**:
1. **Scale horizontally**:
   ```bash
   kubectl scale deployment whatsapp-hotel-bot-api --replicas=5 -n hotel-bot
   ```

2. **Increase CPU limits**:
   ```bash
   kubectl patch deployment whatsapp-hotel-bot-api \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"cpu":"2000m"}}}]}}}}' \
     -n hotel-bot
   ```

## Security Issues

### Unauthorized Access

**Symptoms**: 401/403 errors in logs, suspicious activity

**Diagnosis**:
```bash
# Check access logs
kubectl logs deployment/nginx-ingress-controller -n ingress-nginx | grep -E "(401|403)"

# Check authentication configuration
kubectl get secret whatsapp-hotel-bot-secrets -o yaml -n hotel-bot
```

**Solutions**:
1. **Rotate secrets**:
   ```bash
   # Generate new secret key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # Update secret
   kubectl patch secret whatsapp-hotel-bot-secrets \
     -p '{"data":{"secret-key":"<base64-encoded-new-key>"}}' \
     -n hotel-bot
   ```

2. **Implement rate limiting**:
   ```bash
   # Update ingress with rate limiting
   kubectl annotate ingress whatsapp-hotel-bot-ingress \
     nginx.ingress.kubernetes.io/rate-limit="10" \
     -n hotel-bot
   ```

## Emergency Procedures

### Complete System Recovery

**When**: Total system failure, data corruption

**Steps**:
1. **Assess damage**:
   ```bash
   kubectl get all -n hotel-bot
   kubectl get events -n hotel-bot --sort-by='.lastTimestamp'
   ```

2. **Stop all services**:
   ```bash
   kubectl scale deployment --all --replicas=0 -n hotel-bot
   ```

3. **Restore database**:
   ```bash
   python scripts/restore.py --latest --drop-existing --create-db --confirm
   ```

4. **Redeploy application**:
   ```bash
   ./scripts/deploy.sh production latest-known-good-image
   ```

5. **Verify functionality**:
   ```bash
   ./scripts/smoke-tests.sh production
   ```

### Rollback Procedure

**When**: Recent deployment caused issues

**Steps**:
```bash
# Quick rollback
./scripts/rollback.sh production

# Or manual rollback
kubectl rollout undo deployment/whatsapp-hotel-bot-api -n hotel-bot
kubectl rollout undo deployment/whatsapp-hotel-bot-celery-worker -n hotel-bot

# Verify rollback
kubectl rollout status deployment/whatsapp-hotel-bot-api -n hotel-bot
./scripts/smoke-tests.sh production
```

For additional support, contact the development team or refer to the [operations guide](operations.md).
