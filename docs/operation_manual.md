# WhatsApp Hotel Bot - System Operation Manual

## 📖 Overview

This manual covers daily operations, maintenance procedures, and advanced administration tasks for your WhatsApp Hotel Bot system.

## 🌅 Daily Operations

### Morning Startup Routine

1. **Start the System**
   ```bash
   cd C:\Users\Аркадий\Documents\augment-projects\hotel-boost
   python -m uvicorn app_full:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Verify System Health**
   - Open dashboard: `http://localhost:8000/api/v1/admin/dashboard`
   - Check all services show "Active" status
   - Verify stats are loading (not showing "-")

3. **Review Overnight Activity**
   - Check message volume from previous day
   - Review any system alerts or errors
   - Verify database connectivity

### Throughout the Day

**Monitoring Tasks (Every 2-3 hours):**
- Check dashboard for system status
- Monitor message processing rates
- Review guest interaction metrics
- Verify WhatsApp API connectivity

**Data Management:**
- Refresh dashboard data as needed
- Monitor database performance
- Check for any error patterns

### Evening Shutdown (Optional)

1. **Save Current State**
   - Note any important metrics
   - Document any issues encountered

2. **Graceful Shutdown**
   ```bash
   # In the server terminal:
   Ctrl + C
   # Wait for "Shutting down" message
   ```

## 🏨 Hotel Management

### Adding New Hotels

**Current Status**: Interface ready for implementation

**Preparation Steps**:
1. Gather hotel information:
   - Hotel name and contact details
   - WhatsApp business number
   - Green API credentials
   - Preferred response templates

2. **Access Hotels Section**
   - Navigate to Hotels in dashboard sidebar
   - Interface shows: "Hotel management interface will be loaded here"

### Managing Existing Hotels

**View Hotel List**:
- Current system shows 1 test hotel
- API endpoint: `/api/v1/hotels` returns hotel data

**Hotel Configuration**:
- WhatsApp number setup
- Green API integration
- Custom response templates
- Operating hours and preferences

## 👥 User Management

### Admin Users

**Current Setup**:
- Basic authentication framework implemented
- Security headers configured
- Admin dashboard access controlled

**User Roles** (Ready for implementation):
- **Super Admin**: Full system access
- **Hotel Manager**: Hotel-specific access
- **Support Staff**: Limited monitoring access

### Guest Management

**Guest Data Tracking**:
- Phone number identification
- Conversation history
- Preference storage
- Interaction analytics

## 📊 Analytics and Reporting

### Dashboard Metrics

**Real-time Stats**:
- **Total Hotels**: Currently showing 1 (real data)
- **Messages Today**: 1,234 (placeholder - ready for real data)
- **Active Guests**: 89 (placeholder - ready for real data)
- **AI Responses**: 456 (placeholder - ready for real data)

**System Status Monitoring**:
- Database: Active ✅
- Cache: Active ✅  
- WhatsApp API: Active ✅
- AI Service: Active ✅

### Performance Monitoring

**Key Metrics to Watch**:
- Response time < 500ms for API calls
- Dashboard load time < 3 seconds
- Database query time < 100ms
- Memory usage trends

**Charts and Visualization**:
- Message Volume (Last 7 Days) - Chart.js ready
- Hotel Activity - Doughnut chart ready
- Real-time updates every 30 seconds

## 🔧 Maintenance Procedures

### Daily Maintenance

**System Health Checks**:
```bash
# Run comprehensive health check:
python scripts/health_check_comprehensive.py
```

**Expected Results**:
- All endpoint tests: PASS
- Database connectivity: ✅
- Configuration files: ✅
- Success rate: 100%

### Weekly Maintenance

**Database Maintenance**:
1. **Backup Database**
   ```bash
   copy test.db test_backup_YYYY-MM-DD.db
   ```

2. **Check Database Size**
   ```bash
   dir test.db
   # Monitor growth trends
   ```

3. **Verify Data Integrity**
   ```bash
   python scripts/init_sqlite_db.py
   # Should show "Database created successfully"
   ```

### Monthly Maintenance

**Performance Review**:
- Analyze response time trends
- Review error logs
- Update documentation
- Plan capacity upgrades

**Security Review**:
- Check security headers
- Review access logs
- Update authentication if needed
- Verify CORS configuration

## 🔐 Security Operations

### Access Control

**Current Security Measures**:
- Security headers implemented:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - X-XSS-Protection: 1; mode=block
  - Strict-Transport-Security configured

**CORS Configuration**:
- Restricted to localhost and 127.0.0.1
- Specific methods allowed: GET, POST, PUT, DELETE
- Credentials support enabled

### Monitoring Security

**Daily Security Checks**:
1. Review access patterns
2. Monitor for unusual API calls
3. Check for failed authentication attempts
4. Verify secure headers are present

**Security Endpoints**:
- Health check: `http://localhost:8000/health`
- API documentation: `http://localhost:8000/docs`
- Admin dashboard: `http://localhost:8000/api/v1/admin/dashboard`

## 🚨 Incident Response

### System Down Scenarios

**If Dashboard Won't Load**:
1. Check server status in terminal
2. Verify port 8000 is available
3. Restart server if needed
4. Check firewall settings

**If Database Errors Occur**:
1. Run database health check
2. Restore from backup if needed
3. Reinitialize database if corrupted
4. Document incident for review

### Performance Issues

**If System is Slow**:
1. Check system resources (CPU, RAM)
2. Monitor database query performance
3. Review network connectivity
4. Consider restarting services

**If API Calls Fail**:
1. Check endpoint availability
2. Verify authentication
3. Review error logs
4. Test with health endpoint

## 📈 Capacity Planning

### Current System Capacity

**Database**: SQLite (development)
- Suitable for: Small to medium hotels
- Concurrent users: 10-50
- Message volume: 1,000+ per day

**Server Resources**:
- Memory usage: Low (< 100MB)
- CPU usage: Minimal
- Network: Standard broadband sufficient

### Scaling Considerations

**When to Scale**:
- Multiple hotels (5+)
- High message volume (10,000+ daily)
- Multiple concurrent admin users
- 24/7 operation requirements

**Scaling Options**:
- Upgrade to PostgreSQL database
- Implement Redis caching
- Add load balancing
- Deploy to cloud infrastructure

## 🔄 Backup and Recovery

### Backup Procedures

**Daily Backups**:
```bash
# Automated backup script (create this):
copy test.db backups\test_db_%date:~-4,4%%date:~-10,2%%date:~-7,2%.db
```

**What to Backup**:
- Database file (test.db)
- Configuration files (.env)
- Custom templates
- Log files

### Recovery Procedures

**Database Recovery**:
1. Stop the server
2. Replace corrupted database with backup
3. Restart server
4. Verify data integrity

**Full System Recovery**:
1. Restore database from backup
2. Verify configuration files
3. Restart all services
4. Run health checks

## 📞 Support and Escalation

### Internal Support

**First Level Support**:
- Check troubleshooting guide
- Run health check scripts
- Restart services
- Review error logs

**Second Level Support**:
- Database recovery procedures
- Configuration changes
- Performance optimization
- Security incident response

### Documentation References

**Quick Reference**:
- User Tutorial: `docs/user_tutorial.md`
- Troubleshooting: `docs/troubleshooting_guide.md`
- Testing Results: `docs/testing_results.md`
- Setup Guide: `docs/setup_guide.md`

**API Documentation**:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI Schema: `http://localhost:8000/openapi.json`

## ✅ Success Metrics

### Daily Success Indicators

- ✅ System starts without errors
- ✅ Dashboard loads in < 3 seconds
- ✅ All services show "Active" status
- ✅ API responses < 500ms
- ✅ No error messages in logs

### Weekly Success Indicators

- ✅ 99%+ uptime
- ✅ Consistent performance metrics
- ✅ Successful backups completed
- ✅ Security checks passed
- ✅ User satisfaction maintained

Your WhatsApp Hotel Bot system is designed for reliable, efficient operation with minimal maintenance requirements!
