# Task 002: Database Schema Design and Setup

## Overview
**Priority:** High | **Complexity:** High | **Estimated Hours:** 12
**Dependencies:** Task 001 | **Phase:** Foundation

## Description
Design and implement PostgreSQL database schema for multi-tenant architecture supporting 50+ hotels with proper data isolation.

## Detailed Implementation Plan

### 1. Database Models Design

```python
# app/models/hotel.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

class Hotel(Base):
    __tablename__ = "hotels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    whatsapp_number = Column(String(20), unique=True, nullable=False)
    green_api_instance = Column(String(100), nullable=False)
    green_api_token = Column(String(255), nullable=False)
    settings = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    
    # Relationships
    guests = relationship("Guest", back_populates="hotel")
    triggers = relationship("Trigger", back_populates="hotel")
    staff_notifications = relationship("StaffNotification", back_populates="hotel")

# app/models/guest.py
class Guest(Base):
    __tablename__ = "guests"
    
    id = Column(Integer, primary_key=True, index=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    phone_number = Column(String(20), nullable=False)
    name = Column(String(255))
    check_in_date = Column(DateTime)
    check_out_date = Column(DateTime)
    room_number = Column(String(10))
    room_type = Column(String(50))
    booking_status = Column(String(20), default="confirmed")
    preferences = Column(JSON, default={})
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    
    # Relationships
    hotel = relationship("Hotel", back_populates="guests")
    conversations = relationship("Conversation", back_populates="guest")
    
    __table_args__ = (
        Index('idx_guest_hotel_phone', 'hotel_id', 'phone_number'),
    )

# app/models/conversation.py
class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=False)
    message_id = Column(String(100), unique=True, nullable=False)
    direction = Column(String(10), nullable=False)  # 'inbound', 'outbound'
    message_type = Column(String(20), default="text")  # 'text', 'image', 'audio'
    content = Column(Text, nullable=False)
    sentiment_score = Column(Float)
    sentiment_label = Column(String(20))  # 'positive', 'negative', 'neutral'
    requires_attention = Column(Boolean, default=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Relationships
    guest = relationship("Guest", back_populates="conversations")

# app/models/trigger.py
class Trigger(Base):
    __tablename__ = "triggers"
    
    id = Column(Integer, primary_key=True, index=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    name = Column(String(255), nullable=False)
    trigger_type = Column(String(20), nullable=False)  # 'time_based', 'condition_based'
    conditions = Column(JSON, nullable=False)  # Trigger conditions
    message_template = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)
    
    # Relationships
    hotel = relationship("Hotel", back_populates="triggers")

# app/models/staff_notification.py
class StaffNotification(Base):
    __tablename__ = "staff_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    notification_type = Column(String(20), nullable=False)  # 'negative_sentiment', 'escalation'
    message = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # 'pending', 'sent', 'acknowledged'
    sent_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    
    # Relationships
    hotel = relationship("Hotel", back_populates="staff_notifications")
```

### 2. Database Connection Setup

```python
# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 3. Alembic Migration Setup

```python
# alembic/env.py
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.core.database import Base
from app.models import hotel, guest, conversation, trigger, staff_notification

target_metadata = Base.metadata

def run_migrations_online():
    configuration = context.config
    configuration.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    
    connectable = engine_from_config(
        configuration.get_section(configuration.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()
```

### 4. Redis Setup

```python
# app/core/redis.py
import redis.asyncio as redis
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_redis():
    return redis_client
```

### 5. Multi-tenant Data Isolation

```python
# app/core/tenant.py
from sqlalchemy.orm import Session
from app.models.hotel import Hotel

class TenantManager:
    @staticmethod
    def get_hotel_filter(hotel_id: int):
        """Returns filter for multi-tenant data isolation"""
        return {"hotel_id": hotel_id}
    
    @staticmethod
    def verify_hotel_access(db: Session, hotel_id: int, user_hotel_id: int):
        """Verify user has access to hotel data"""
        if hotel_id != user_hotel_id:
            raise PermissionError("Access denied to hotel data")
        return True
```

## Test Strategy

### 1. Database Schema Tests
```python
# tests/test_database.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models import Hotel, Guest, Conversation

def test_database_schema_creation():
    """Test that all tables are created correctly"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    
    # Verify tables exist
    assert engine.has_table("hotels")
    assert engine.has_table("guests")
    assert engine.has_table("conversations")

def test_multi_tenant_isolation():
    """Test that data is properly isolated by hotel"""
    # Create test data for different hotels
    # Verify queries only return data for specific hotel
```

### 2. Migration Tests
- All migrations run successfully
- Database schema matches models
- Data integrity maintained during migrations

## Acceptance Criteria
- [ ] All database models created and tested
- [ ] Multi-tenant architecture implemented
- [ ] Database migrations work correctly
- [ ] Redis connection established
- [ ] Data isolation verified between hotels
- [ ] Foreign key constraints properly set
- [ ] Indexes created for performance
- [ ] Connection pooling configured

## Performance Considerations
- Indexes on frequently queried columns (hotel_id, phone_number, timestamp)
- Connection pooling for high concurrency
- Redis caching for frequently accessed data
- Proper foreign key relationships for data integrity

## Security Considerations
- Row-level security for multi-tenant isolation
- Encrypted sensitive data (API tokens)
- Proper access controls
- SQL injection prevention through ORM

## Related Modules
- Database
- Schema
- Multi-tenant
- Security

## Next Steps
After completion, proceed to Task 003: Green API WhatsApp Integration
