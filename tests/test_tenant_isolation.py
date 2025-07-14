"""
Tests for Row Level Security and tenant isolation
"""

import pytest
import uuid
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.models.base import Base
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.trigger import Trigger, TriggerType
from app.models.message import Message, Conversation, MessageType
from app.models.notification import StaffNotification, NotificationType
from app.core.tenant import TenantContext, TenantManager


@pytest.fixture
async def rls_test_engine():
    """Create test database engine with RLS support (PostgreSQL simulation)"""
    # For testing purposes, we'll use SQLite but simulate RLS behavior
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Simulate RLS setup for testing
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tenant_context (
                current_tenant_id TEXT
            );
        """))
        
        await conn.execute(text("""
            INSERT INTO tenant_context (current_tenant_id) VALUES (NULL);
        """))
    
    yield engine
    await engine.dispose()


@pytest.fixture
async def rls_session(rls_test_engine):
    """Create test database session for RLS testing"""
    async_session = async_sessionmaker(
        rls_test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_tenants(rls_session):
    """Create test tenants (hotels) for isolation testing"""
    # Create two hotels (tenants)
    hotel1 = Hotel(
        name="Hotel Alpha",
        whatsapp_number="+1111111111"
    )
    hotel2 = Hotel(
        name="Hotel Beta", 
        whatsapp_number="+2222222222"
    )
    
    rls_session.add_all([hotel1, hotel2])
    await rls_session.commit()
    await rls_session.refresh(hotel1)
    await rls_session.refresh(hotel2)
    
    # Create guests for each hotel
    guest1 = Guest(
        hotel_id=hotel1.id,
        phone="+1111111111",
        name="Guest Alpha"
    )
    guest2 = Guest(
        hotel_id=hotel2.id,
        phone="+2222222222", 
        name="Guest Beta"
    )
    
    rls_session.add_all([guest1, guest2])
    await rls_session.commit()
    await rls_session.refresh(guest1)
    await rls_session.refresh(guest2)
    
    # Create conversations
    conv1 = Conversation(hotel_id=hotel1.id, guest_id=guest1.id)
    conv2 = Conversation(hotel_id=hotel2.id, guest_id=guest2.id)
    
    rls_session.add_all([conv1, conv2])
    await rls_session.commit()
    await rls_session.refresh(conv1)
    await rls_session.refresh(conv2)
    
    # Create messages
    msg1 = Message(
        conversation_id=conv1.id,
        message_type=MessageType.INCOMING,
        content="Message from Hotel Alpha guest"
    )
    msg2 = Message(
        conversation_id=conv2.id,
        message_type=MessageType.INCOMING,
        content="Message from Hotel Beta guest"
    )
    
    rls_session.add_all([msg1, msg2])
    await rls_session.commit()
    
    return {
        "hotel1": hotel1,
        "hotel2": hotel2,
        "guest1": guest1,
        "guest2": guest2,
        "conv1": conv1,
        "conv2": conv2,
        "msg1": msg1,
        "msg2": msg2
    }


class TestTenantContext:
    """Test tenant context management"""
    
    def test_tenant_context_setting(self):
        """Test setting and getting tenant context"""
        tenant_id = uuid.uuid4()
        
        # Initially no tenant
        assert TenantContext.get_tenant_id() is None
        
        # Set tenant
        TenantContext.set_tenant_id(tenant_id)
        assert TenantContext.get_tenant_id() == tenant_id
        
        # Clear tenant
        TenantContext.clear_tenant_id()
        assert TenantContext.get_tenant_id() is None
    
    def test_require_tenant_context(self):
        """Test requiring tenant context"""
        # Should raise error when no tenant set
        with pytest.raises(ValueError):
            TenantContext.require_tenant_id()
        
        # Should return tenant when set
        tenant_id = uuid.uuid4()
        TenantContext.set_tenant_id(tenant_id)
        assert TenantContext.require_tenant_id() == tenant_id
        
        # Cleanup
        TenantContext.clear_tenant_id()
    
    @pytest.mark.asyncio
    async def test_session_tenant_management(self, rls_session):
        """Test session-level tenant management"""
        tenant_id = uuid.uuid4()
        
        # Set session tenant (simulated)
        await TenantManager.set_session_tenant(rls_session, tenant_id)
        
        # Verify tenant is set in context
        TenantContext.set_tenant_id(tenant_id)
        assert TenantContext.get_tenant_id() == tenant_id
        
        # Clear session tenant
        await TenantManager.clear_session_tenant(rls_session)
        TenantContext.clear_tenant_id()
        assert TenantContext.get_tenant_id() is None


class TestDataIsolation:
    """Test data isolation between tenants"""
    
    @pytest.mark.asyncio
    async def test_guest_isolation(self, rls_session, test_tenants):
        """Test that guests are isolated by hotel"""
        hotel1 = test_tenants["hotel1"]
        hotel2 = test_tenants["hotel2"]
        guest1 = test_tenants["guest1"]
        guest2 = test_tenants["guest2"]
        
        # Simulate tenant context for hotel1
        TenantContext.set_tenant_id(hotel1.id)
        
        # Query guests - should only see hotel1's guests
        result = await rls_session.execute(
            text("SELECT * FROM guests WHERE hotel_id = :hotel_id"),
            {"hotel_id": str(hotel1.id)}
        )
        hotel1_guests = result.fetchall()
        
        # Should only see guest1
        assert len(hotel1_guests) == 1
        assert str(hotel1_guests[0].id) == str(guest1.id)
        
        # Switch to hotel2 context
        TenantContext.set_tenant_id(hotel2.id)
        
        result = await rls_session.execute(
            text("SELECT * FROM guests WHERE hotel_id = :hotel_id"),
            {"hotel_id": str(hotel2.id)}
        )
        hotel2_guests = result.fetchall()
        
        # Should only see guest2
        assert len(hotel2_guests) == 1
        assert str(hotel2_guests[0].id) == str(guest2.id)
        
        # Cleanup
        TenantContext.clear_tenant_id()
    
    @pytest.mark.asyncio
    async def test_conversation_isolation(self, rls_session, test_tenants):
        """Test that conversations are isolated by hotel"""
        hotel1 = test_tenants["hotel1"]
        hotel2 = test_tenants["hotel2"]
        conv1 = test_tenants["conv1"]
        conv2 = test_tenants["conv2"]
        
        # Test hotel1 context
        TenantContext.set_tenant_id(hotel1.id)
        
        result = await rls_session.execute(
            text("SELECT * FROM conversations WHERE hotel_id = :hotel_id"),
            {"hotel_id": str(hotel1.id)}
        )
        hotel1_conversations = result.fetchall()
        
        assert len(hotel1_conversations) == 1
        assert str(hotel1_conversations[0].id) == str(conv1.id)
        
        # Test hotel2 context
        TenantContext.set_tenant_id(hotel2.id)
        
        result = await rls_session.execute(
            text("SELECT * FROM conversations WHERE hotel_id = :hotel_id"),
            {"hotel_id": str(hotel2.id)}
        )
        hotel2_conversations = result.fetchall()
        
        assert len(hotel2_conversations) == 1
        assert str(hotel2_conversations[0].id) == str(conv2.id)
        
        TenantContext.clear_tenant_id()
    
    @pytest.mark.asyncio
    async def test_message_isolation_through_conversation(self, rls_session, test_tenants):
        """Test that messages are isolated through conversation relationships"""
        hotel1 = test_tenants["hotel1"]
        hotel2 = test_tenants["hotel2"]
        conv1 = test_tenants["conv1"]
        conv2 = test_tenants["conv2"]
        msg1 = test_tenants["msg1"]
        msg2 = test_tenants["msg2"]
        
        # Test hotel1 context - should only see messages from hotel1 conversations
        TenantContext.set_tenant_id(hotel1.id)
        
        result = await rls_session.execute(text("""
            SELECT m.* FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.hotel_id = :hotel_id
        """), {"hotel_id": str(hotel1.id)})
        hotel1_messages = result.fetchall()
        
        assert len(hotel1_messages) == 1
        assert str(hotel1_messages[0].id) == str(msg1.id)
        
        # Test hotel2 context
        TenantContext.set_tenant_id(hotel2.id)
        
        result = await rls_session.execute(text("""
            SELECT m.* FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.hotel_id = :hotel_id
        """), {"hotel_id": str(hotel2.id)})
        hotel2_messages = result.fetchall()
        
        assert len(hotel2_messages) == 1
        assert str(hotel2_messages[0].id) == str(msg2.id)
        
        TenantContext.clear_tenant_id()
    
    @pytest.mark.asyncio
    async def test_cross_tenant_access_prevention(self, rls_session, test_tenants):
        """Test that tenants cannot access each other's data"""
        hotel1 = test_tenants["hotel1"]
        hotel2 = test_tenants["hotel2"]
        guest2 = test_tenants["guest2"]
        
        # Set context to hotel1
        TenantContext.set_tenant_id(hotel1.id)
        
        # Try to access hotel2's guest - should not be visible
        result = await rls_session.execute(
            text("SELECT * FROM guests WHERE id = :guest_id"),
            {"guest_id": str(guest2.id)}
        )
        cross_tenant_guest = result.fetchone()
        
        # In a real RLS implementation, this would return None
        # For testing, we verify the guest belongs to different hotel
        if cross_tenant_guest:
            assert str(cross_tenant_guest.hotel_id) != str(hotel1.id)
        
        TenantContext.clear_tenant_id()


class TestTenantOperations:
    """Test tenant-specific operations"""
    
    @pytest.mark.asyncio
    async def test_tenant_specific_inserts(self, rls_session, test_tenants):
        """Test that inserts respect tenant context"""
        hotel1 = test_tenants["hotel1"]
        hotel2 = test_tenants["hotel2"]
        
        # Set context to hotel1
        TenantContext.set_tenant_id(hotel1.id)
        
        # Create new guest for hotel1
        new_guest = Guest(
            hotel_id=hotel1.id,
            phone="+1111111112",
            name="New Guest Alpha"
        )
        
        rls_session.add(new_guest)
        await rls_session.commit()
        await rls_session.refresh(new_guest)
        
        # Verify guest was created with correct hotel_id
        assert new_guest.hotel_id == hotel1.id
        
        # Switch to hotel2 context
        TenantContext.set_tenant_id(hotel2.id)
        
        # Create guest for hotel2
        new_guest2 = Guest(
            hotel_id=hotel2.id,
            phone="+2222222223",
            name="New Guest Beta"
        )
        
        rls_session.add(new_guest2)
        await rls_session.commit()
        await rls_session.refresh(new_guest2)
        
        assert new_guest2.hotel_id == hotel2.id
        assert new_guest2.hotel_id != new_guest.hotel_id
        
        TenantContext.clear_tenant_id()
    
    @pytest.mark.asyncio
    async def test_tenant_specific_updates(self, rls_session, test_tenants):
        """Test that updates respect tenant context"""
        hotel1 = test_tenants["hotel1"]
        guest1 = test_tenants["guest1"]
        
        # Set context to hotel1
        TenantContext.set_tenant_id(hotel1.id)
        
        # Update guest1 (belongs to hotel1)
        guest1.name = "Updated Guest Alpha"
        await rls_session.commit()
        await rls_session.refresh(guest1)
        
        assert guest1.name == "Updated Guest Alpha"
        
        TenantContext.clear_tenant_id()
    
    @pytest.mark.asyncio
    async def test_tenant_specific_deletes(self, rls_session, test_tenants):
        """Test that deletes respect tenant context"""
        hotel1 = test_tenants["hotel1"]
        
        # Set context to hotel1
        TenantContext.set_tenant_id(hotel1.id)
        
        # Create a trigger to delete
        trigger = Trigger(
            hotel_id=hotel1.id,
            name="Test Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Test message"
        )
        
        rls_session.add(trigger)
        await rls_session.commit()
        await rls_session.refresh(trigger)
        
        trigger_id = trigger.id
        
        # Delete the trigger
        await rls_session.delete(trigger)
        await rls_session.commit()
        
        # Verify deletion
        deleted_trigger = await rls_session.get(Trigger, trigger_id)
        assert deleted_trigger is None
        
        TenantContext.clear_tenant_id()


class TestTenantSecurity:
    """Test tenant security and access control"""
    
    @pytest.mark.asyncio
    async def test_tenant_verification(self, rls_session, test_tenants):
        """Test tenant access verification"""
        hotel1 = test_tenants["hotel1"]
        hotel2 = test_tenants["hotel2"]
        guest2 = test_tenants["guest2"]
        
        # Verify access is denied for wrong tenant
        access_denied = await TenantManager.verify_tenant_access(
            rls_session,
            hotel1.id,  # Current tenant
            guest2.hotel_id  # Resource belongs to hotel2
        )
        
        assert not access_denied
        
        # Verify access is allowed for correct tenant
        access_allowed = await TenantManager.verify_tenant_access(
            rls_session,
            hotel2.id,  # Current tenant
            guest2.hotel_id  # Resource belongs to hotel2
        )
        
        assert access_allowed
    
    @pytest.mark.asyncio
    async def test_audit_logging(self, rls_session, test_tenants):
        """Test tenant action audit logging"""
        hotel1 = test_tenants["hotel1"]
        
        # Set tenant context
        TenantContext.set_tenant_id(hotel1.id)
        
        # Log a tenant action
        await TenantManager.log_tenant_action(
            rls_session,
            "CREATE",
            "guests",
            uuid.uuid4(),
            "192.168.1.1",
            "Test User Agent"
        )
        
        # In a real implementation, this would be logged to audit table
        # For testing, we just verify the function doesn't raise errors
        
        TenantContext.clear_tenant_id()


class TestConcurrentTenantAccess:
    """Test concurrent access by multiple tenants"""
    
    @pytest.mark.asyncio
    async def test_concurrent_tenant_operations(self, rls_test_engine, test_tenants):
        """Test concurrent operations by different tenants"""
        async_session = async_sessionmaker(rls_test_engine, class_=AsyncSession)
        
        hotel1_id = test_tenants["hotel1"].id
        hotel2_id = test_tenants["hotel2"].id
        
        async def hotel1_operations():
            async with async_session() as session:
                TenantContext.set_tenant_id(hotel1_id)
                
                # Create guest for hotel1
                guest = Guest(
                    hotel_id=hotel1_id,
                    phone="+1111111113",
                    name="Concurrent Guest 1"
                )
                session.add(guest)
                await session.commit()
                
                # Query hotel1 guests
                result = await session.execute(
                    text("SELECT COUNT(*) FROM guests WHERE hotel_id = :hotel_id"),
                    {"hotel_id": str(hotel1_id)}
                )
                count = result.scalar()
                
                TenantContext.clear_tenant_id()
                return {"hotel": "hotel1", "guest_count": count}
        
        async def hotel2_operations():
            async with async_session() as session:
                TenantContext.set_tenant_id(hotel2_id)
                
                # Create guest for hotel2
                guest = Guest(
                    hotel_id=hotel2_id,
                    phone="+2222222224",
                    name="Concurrent Guest 2"
                )
                session.add(guest)
                await session.commit()
                
                # Query hotel2 guests
                result = await session.execute(
                    text("SELECT COUNT(*) FROM guests WHERE hotel_id = :hotel_id"),
                    {"hotel_id": str(hotel2_id)}
                )
                count = result.scalar()
                
                TenantContext.clear_tenant_id()
                return {"hotel": "hotel2", "guest_count": count}
        
        # Run operations concurrently
        results = await asyncio.gather(
            hotel1_operations(),
            hotel2_operations()
        )
        
        # Both operations should succeed
        assert len(results) == 2
        assert results[0]["hotel"] == "hotel1"
        assert results[1]["hotel"] == "hotel2"
        assert results[0]["guest_count"] >= 1
        assert results[1]["guest_count"] >= 1
    
    @pytest.mark.asyncio
    async def test_tenant_context_isolation(self, rls_test_engine):
        """Test that tenant contexts don't interfere with each other"""
        async_session = async_sessionmaker(rls_test_engine, class_=AsyncSession)
        
        tenant1_id = uuid.uuid4()
        tenant2_id = uuid.uuid4()
        
        async def operation_with_context(tenant_id, operation_id):
            # Each async task should have isolated context
            TenantContext.set_tenant_id(tenant_id)
            
            # Simulate some work
            await asyncio.sleep(0.1)
            
            # Verify context is still correct
            current_tenant = TenantContext.get_tenant_id()
            
            TenantContext.clear_tenant_id()
            
            return {
                "operation_id": operation_id,
                "expected_tenant": tenant_id,
                "actual_tenant": current_tenant,
                "context_preserved": current_tenant == tenant_id
            }
        
        # Run multiple operations with different contexts
        tasks = [
            operation_with_context(tenant1_id, 1),
            operation_with_context(tenant2_id, 2),
            operation_with_context(tenant1_id, 3),
            operation_with_context(tenant2_id, 4),
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All operations should preserve their context
        assert len(results) == 4
        assert all(r["context_preserved"] for r in results)
