# WhatsApp Hotel Bot - Database Layer Documentation

## Overview

The WhatsApp Hotel Bot uses a sophisticated multi-tenant database architecture built with SQLAlchemy, PostgreSQL, and Row Level Security (RLS) to ensure complete data isolation between hotel tenants.

## Architecture

### Multi-Tenant Design

- **Tenant Isolation**: Each hotel is a separate tenant with complete data isolation
- **Row Level Security**: PostgreSQL RLS policies ensure tenants can only access their own data
- **Shared Schema**: All tenants share the same database schema for efficiency
- **Tenant Context**: Request-level tenant context management for secure operations

### Database Models

#### Core Models

1. **Hotel** (`hotels` table)
   - Primary tenant entity
   - WhatsApp integration settings
   - Hotel-specific configuration
   - Green API credentials

2. **Guest** (`guests` table)
   - Hotel guests with contact information
   - Preference storage (JSONB)
   - Interaction tracking
   - Tenant-isolated by `hotel_id`

3. **Conversation** (`conversations` table)
   - WhatsApp conversation threads
   - Status tracking (active, closed, escalated)
   - Tenant-isolated by `hotel_id`

4. **Message** (`messages` table)
   - Individual WhatsApp messages
   - Sentiment analysis results
   - Message metadata (JSONB)
   - Isolated through conversation relationship

5. **Trigger** (`triggers` table)
   - Automated message triggers
   - Condition-based logic (JSONB)
   - Priority and scheduling
   - Tenant-isolated by `hotel_id`

6. **StaffNotification** (`staff_notifications` table)
   - Staff alerts and notifications
   - Priority scoring
   - Status tracking
   - Tenant-isolated by `hotel_id`

### Database Features

#### Row Level Security (RLS)

```sql
-- Example RLS policy for guests table
CREATE POLICY tenant_isolation_guests ON guests
    FOR ALL TO hotel_bot_tenant
    USING (hotel_id = get_current_tenant_id());
```

#### Performance Optimization

- **Indexes**: Comprehensive indexing strategy for all query patterns
- **Partial Indexes**: Conditional indexes for specific use cases
- **GIN Indexes**: Full-text search on JSONB fields
- **Connection Pooling**: Optimized connection management

#### Monitoring and Logging

- **Query Performance**: Automatic slow query detection
- **Connection Monitoring**: Pool utilization tracking
- **Audit Logging**: Tenant action logging for compliance
- **Health Checks**: Comprehensive database health monitoring

## Setup and Configuration

### Environment Variables

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/hotel_bot
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_POOL_TIMEOUT=30

# Logging
DATABASE_LOG_QUERIES=false
DATABASE_LOG_SLOW_QUERIES=true
DATABASE_SLOW_QUERY_THRESHOLD=1000
```

### Database Initialization

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Migrations**
   ```bash
   python scripts/run_migrations.py --upgrade
   ```

3. **Set Up RLS**
   ```bash
   python scripts/run_migrations.py --setup-rls
   ```

4. **Create Indexes**
   ```bash
   python scripts/run_migrations.py --create-indexes
   ```

### Migration Management

The project uses Alembic for database migrations:

```bash
# Create new migration
python scripts/run_migrations.py --create "Add new feature"

# Upgrade to latest
python scripts/run_migrations.py --upgrade

# Downgrade to specific revision
python scripts/run_migrations.py --downgrade abc123

# Show current status
python scripts/run_migrations.py --current
```

## Usage Examples

### Basic Model Operations

```python
from app.models import Hotel, Guest, Conversation, Message
from app.database import get_db_session
from app.core.tenant import TenantContext

# Create a hotel
async with get_db_session() as session:
    hotel = Hotel(
        name="Grand Hotel",
        whatsapp_number="+1234567890"
    )
    session.add(hotel)
    await session.commit()
```

### Tenant Context Management

```python
from app.core.tenant import TenantContext

# Set tenant context
TenantContext.set_tenant_id(hotel.id)

# All subsequent database operations will be tenant-isolated
async with get_db_session() as session:
    # This query will only return guests for the current tenant
    guests = await session.execute(
        select(Guest).where(Guest.hotel_id == TenantContext.get_tenant_id())
    )
```

### Using Middleware

```python
from fastapi import FastAPI
from app.middleware import add_tenant_middlewares, add_database_middlewares

app = FastAPI()

# Add tenant isolation middleware
add_tenant_middlewares(app)

# Add database monitoring middleware
add_database_middlewares(app)
```

## Testing

### Running Tests

```bash
# Run all tests
python scripts/run_tests.py --all

# Run specific test categories
python scripts/run_tests.py --unit
python scripts/run_tests.py --integration
python scripts/run_tests.py --performance
python scripts/run_tests.py --tenant

# Run with coverage
python scripts/run_tests.py --coverage
```

### Test Categories

1. **Unit Tests** (`test_models.py`)
   - Model validation
   - Business logic
   - Utility methods

2. **Integration Tests** (`test_database_integration.py`)
   - Database operations
   - Transaction handling
   - Constraint validation

3. **Performance Tests** (`test_database_performance.py`)
   - Query performance
   - Concurrent access
   - Load testing

4. **Tenant Isolation Tests** (`test_tenant_isolation.py`)
   - RLS policy validation
   - Cross-tenant access prevention
   - Context management

## Monitoring and Maintenance

### Performance Monitoring

```python
from app.utils.db_monitor import performance_monitor

# Get performance summary
summary = await performance_monitor.get_performance_summary()

# Get slow queries
slow_queries = await performance_monitor.get_slow_queries(limit=10)

# Reset metrics
await performance_monitor.reset_metrics()
```

### Health Checks

```python
from app.database import DatabaseManager

db_manager = DatabaseManager()

# Comprehensive health check
health = await db_manager.health_check()

# Connection pool status
pool_health = await get_connection_pool_health()
```

### Logging Configuration

The database layer provides structured JSON logging:

```python
from app.core.database_logging import db_logger

# Configure logging
db_logger.configure(
    log_all_queries=False,
    log_slow_queries=True,
    slow_query_threshold=1000
)
```

## Security Considerations

### Row Level Security

- All tenant-specific tables have RLS enabled
- Policies enforce `hotel_id` filtering
- Admin role can bypass RLS for maintenance

### Tenant Isolation

- Request-level tenant context
- Automatic tenant validation
- Cross-tenant access prevention

### Audit Logging

- All tenant actions are logged
- IP address and user agent tracking
- Compliance-ready audit trail

## Troubleshooting

### Common Issues

1. **Connection Pool Exhaustion**
   ```bash
   # Check pool status
   python -c "from app.database import get_connection_pool_health; print(await get_connection_pool_health())"
   ```

2. **Slow Queries**
   ```bash
   # Analyze slow queries
   python scripts/run_tests.py --performance
   ```

3. **Tenant Context Issues**
   ```python
   # Verify tenant context
   from app.core.tenant import TenantContext
   print(f"Current tenant: {TenantContext.get_tenant_id()}")
   ```

### Performance Tuning

1. **Index Analysis**
   ```sql
   -- Check index usage
   SELECT * FROM analyze_index_usage();
   
   -- Find unused indexes
   SELECT * FROM find_unused_indexes();
   ```

2. **Query Optimization**
   ```sql
   -- Analyze query performance
   EXPLAIN ANALYZE SELECT * FROM guests WHERE hotel_id = $1;
   ```

## Best Practices

1. **Always use tenant context** when accessing tenant-specific data
2. **Use async sessions** for all database operations
3. **Handle connection pool limits** with proper session management
4. **Monitor query performance** regularly
5. **Test tenant isolation** thoroughly
6. **Use transactions** for multi-step operations
7. **Validate input data** at the model level
8. **Log important operations** for audit trails

## Migration Strategy

### Development
- Use auto-generated migrations for schema changes
- Test migrations on sample data
- Validate RLS policies after changes

### Production
- Review all migrations before deployment
- Backup database before major changes
- Monitor performance after migrations
- Have rollback plan ready

## Future Enhancements

1. **Read Replicas**: Implement read-only replicas for scaling
2. **Sharding**: Consider sharding for very large deployments
3. **Caching**: Add Redis caching layer for frequently accessed data
4. **Analytics**: Implement data warehouse for analytics
5. **Backup**: Automated backup and restore procedures
