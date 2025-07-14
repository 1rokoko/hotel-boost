# Database Documentation

This directory contains database-related documentation for the WhatsApp Hotel Bot system.

## Files

- `schema.md` - Database schema documentation
- `migrations.md` - Migration procedures
- `performance.md` - Database performance optimization
- `backup_recovery.md` - Backup and recovery procedures

## Database Design

### Primary Database: PostgreSQL

- **Hotels** - Hotel information and configuration
- **Guests** - Guest profiles and preferences
- **Conversations** - Chat conversation history
- **Messages** - Individual message records
- **Triggers** - Automated response triggers
- **Templates** - Message templates
- **Analytics** - Performance and usage analytics

### Cache Layer: Redis

- **Session Storage** - User session data
- **Rate Limiting** - API rate limit counters
- **Circuit Breaker State** - Circuit breaker status
- **Dead Letter Queue** - Failed message queue
- **Temporary Data** - Short-lived cache data

## Connection Management

- **Connection Pooling** - Optimized connection usage
- **Read Replicas** - Read scaling capabilities
- **Failover** - Automatic failover mechanisms
- **Monitoring** - Database health monitoring
