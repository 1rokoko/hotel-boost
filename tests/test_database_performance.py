"""
Performance and load tests for database operations
"""

import pytest
import asyncio
import time
import uuid
import statistics
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.models.base import Base
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.trigger import Trigger, TriggerType
from app.models.message import Message, Conversation, MessageType, SentimentType
from app.models.notification import StaffNotification, NotificationType, NotificationStatus
from app.utils.db_monitor import DatabasePerformanceMonitor


@pytest.fixture
async def performance_test_engine():
    """Create test database engine for performance testing"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        pool_size=20,
        max_overflow=30
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    await engine.dispose()


@pytest.fixture
async def performance_session(performance_test_engine):
    """Create test database session for performance testing"""
    async_session = async_sessionmaker(
        performance_test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_data(performance_session):
    """Create test data for performance tests"""
    # Create hotels
    hotels = []
    for i in range(10):
        hotel = Hotel(
            name=f"Hotel {i}",
            whatsapp_number=f"+{1000000000 + i}"
        )
        hotels.append(hotel)
    
    performance_session.add_all(hotels)
    await performance_session.commit()
    
    # Create guests for each hotel
    guests = []
    for hotel in hotels:
        await performance_session.refresh(hotel)
        for j in range(50):  # 50 guests per hotel
            guest = Guest(
                hotel_id=hotel.id,
                phone=f"+{2000000000 + (i * 50) + j}",
                name=f"Guest {i}-{j}"
            )
            guests.append(guest)
    
    performance_session.add_all(guests)
    await performance_session.commit()
    
    # Create conversations and messages
    conversations = []
    messages = []
    
    for guest in guests[:100]:  # First 100 guests
        await performance_session.refresh(guest)
        conversation = Conversation(
            hotel_id=guest.hotel_id,
            guest_id=guest.id
        )
        conversations.append(conversation)
    
    performance_session.add_all(conversations)
    await performance_session.commit()
    
    for conversation in conversations:
        await performance_session.refresh(conversation)
        for k in range(10):  # 10 messages per conversation
            message = Message(
                conversation_id=conversation.id,
                message_type=MessageType.INCOMING if k % 2 == 0 else MessageType.OUTGOING,
                content=f"Message {k} in conversation {conversation.id}"
            )
            messages.append(message)
    
    performance_session.add_all(messages)
    await performance_session.commit()
    
    return {
        "hotels": hotels,
        "guests": guests,
        "conversations": conversations,
        "messages": messages
    }


class TestQueryPerformance:
    """Test query performance and optimization"""
    
    @pytest.mark.asyncio
    async def test_simple_select_performance(self, performance_session, test_data):
        """Test simple SELECT query performance"""
        monitor = DatabasePerformanceMonitor()
        
        # Warm up
        await performance_session.execute(text("SELECT COUNT(*) FROM hotels"))
        
        # Test multiple simple queries
        times = []
        for _ in range(100):
            start_time = time.time()
            result = await performance_session.execute(text("SELECT * FROM hotels LIMIT 10"))
            result.fetchall()
            end_time = time.time()
            
            execution_time = (end_time - start_time) * 1000
            times.append(execution_time)
            monitor.record_query("SELECT * FROM hotels LIMIT 10", execution_time)
        
        # Performance assertions
        avg_time = statistics.mean(times)
        max_time = max(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]
        
        assert avg_time < 50.0  # Average should be under 50ms
        assert max_time < 200.0  # Max should be under 200ms
        assert p95_time < 100.0  # 95th percentile under 100ms
        
        print(f"Simple SELECT - Avg: {avg_time:.2f}ms, Max: {max_time:.2f}ms, P95: {p95_time:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_join_query_performance(self, performance_session, test_data):
        """Test JOIN query performance"""
        times = []
        
        # Test JOIN queries
        for _ in range(50):
            start_time = time.time()
            result = await performance_session.execute(text("""
                SELECT h.name, g.name, g.phone 
                FROM hotels h 
                JOIN guests g ON h.id = g.hotel_id 
                LIMIT 100
            """))
            result.fetchall()
            end_time = time.time()
            
            times.append((end_time - start_time) * 1000)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        assert avg_time < 100.0  # JOIN queries should be under 100ms average
        assert max_time < 500.0  # Max should be under 500ms
        
        print(f"JOIN Query - Avg: {avg_time:.2f}ms, Max: {max_time:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_complex_query_performance(self, performance_session, test_data):
        """Test complex query with multiple JOINs and aggregations"""
        times = []
        
        for _ in range(20):
            start_time = time.time()
            result = await performance_session.execute(text("""
                SELECT 
                    h.name as hotel_name,
                    COUNT(DISTINCT g.id) as guest_count,
                    COUNT(DISTINCT c.id) as conversation_count,
                    COUNT(m.id) as message_count
                FROM hotels h
                LEFT JOIN guests g ON h.id = g.hotel_id
                LEFT JOIN conversations c ON g.id = c.guest_id
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY h.id, h.name
                ORDER BY message_count DESC
            """))
            result.fetchall()
            end_time = time.time()
            
            times.append((end_time - start_time) * 1000)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        assert avg_time < 500.0  # Complex queries should be under 500ms average
        assert max_time < 2000.0  # Max should be under 2 seconds
        
        print(f"Complex Query - Avg: {avg_time:.2f}ms, Max: {max_time:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_pagination_performance(self, performance_session, test_data):
        """Test pagination query performance"""
        page_size = 20
        total_pages = 25  # Test 25 pages
        times = []
        
        for page in range(total_pages):
            offset = page * page_size
            start_time = time.time()
            
            result = await performance_session.execute(text("""
                SELECT g.*, h.name as hotel_name
                FROM guests g
                JOIN hotels h ON g.hotel_id = h.id
                ORDER BY g.created_at DESC
                LIMIT :limit OFFSET :offset
            """), {"limit": page_size, "offset": offset})
            result.fetchall()
            
            end_time = time.time()
            times.append((end_time - start_time) * 1000)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Pagination should maintain consistent performance
        assert avg_time < 100.0
        assert max_time < 300.0
        
        # Performance shouldn't degrade significantly with offset
        first_page_time = times[0]
        last_page_time = times[-1]
        degradation_ratio = last_page_time / first_page_time
        
        assert degradation_ratio < 3.0  # Last page shouldn't be 3x slower than first
        
        print(f"Pagination - Avg: {avg_time:.2f}ms, Degradation: {degradation_ratio:.2f}x")


class TestConcurrentAccess:
    """Test concurrent database access patterns"""
    
    @pytest.mark.asyncio
    async def test_concurrent_reads(self, performance_test_engine, test_data):
        """Test concurrent read operations"""
        async_session = async_sessionmaker(performance_test_engine, class_=AsyncSession)
        
        async def read_hotels(session_id):
            async with async_session() as session:
                start_time = time.time()
                result = await session.execute(text("SELECT * FROM hotels"))
                hotels = result.fetchall()
                end_time = time.time()
                
                return {
                    "session_id": session_id,
                    "hotel_count": len(hotels),
                    "execution_time": (end_time - start_time) * 1000
                }
        
        # Run 20 concurrent read operations
        tasks = [read_hotels(i) for i in range(20)]
        results = await asyncio.gather(*tasks)
        
        # All reads should succeed
        assert len(results) == 20
        assert all(r["hotel_count"] > 0 for r in results)
        
        # Performance should be reasonable
        avg_time = statistics.mean([r["execution_time"] for r in results])
        max_time = max([r["execution_time"] for r in results])
        
        assert avg_time < 200.0  # Average under 200ms
        assert max_time < 1000.0  # Max under 1 second
        
        print(f"Concurrent Reads - Avg: {avg_time:.2f}ms, Max: {max_time:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, performance_test_engine):
        """Test concurrent write operations"""
        async_session = async_sessionmaker(performance_test_engine, class_=AsyncSession)
        
        async def create_hotel(session_id):
            async with async_session() as session:
                start_time = time.time()
                
                hotel = Hotel(
                    name=f"Concurrent Hotel {session_id}",
                    whatsapp_number=f"+{3000000000 + session_id}"
                )
                session.add(hotel)
                await session.commit()
                
                end_time = time.time()
                return {
                    "session_id": session_id,
                    "hotel_id": hotel.id,
                    "execution_time": (end_time - start_time) * 1000
                }
        
        # Run 10 concurrent write operations
        tasks = [create_hotel(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All writes should succeed
        assert len(results) == 10
        assert all(r["hotel_id"] is not None for r in results)
        
        # All hotel IDs should be unique
        hotel_ids = [r["hotel_id"] for r in results]
        assert len(set(hotel_ids)) == len(hotel_ids)
        
        avg_time = statistics.mean([r["execution_time"] for r in results])
        max_time = max([r["execution_time"] for r in results])
        
        assert avg_time < 500.0  # Average under 500ms
        assert max_time < 2000.0  # Max under 2 seconds
        
        print(f"Concurrent Writes - Avg: {avg_time:.2f}ms, Max: {max_time:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_mixed_concurrent_operations(self, performance_test_engine, test_data):
        """Test mixed read/write concurrent operations"""
        async_session = async_sessionmaker(performance_test_engine, class_=AsyncSession)
        
        async def read_operation(op_id):
            async with async_session() as session:
                result = await session.execute(text("SELECT COUNT(*) FROM guests"))
                return {"type": "read", "id": op_id, "count": result.scalar()}
        
        async def write_operation(op_id):
            async with async_session() as session:
                # Get a random hotel
                hotel_result = await session.execute(text("SELECT id FROM hotels LIMIT 1"))
                hotel_id = hotel_result.scalar()
                
                if hotel_id:
                    guest = Guest(
                        hotel_id=hotel_id,
                        phone=f"+{4000000000 + op_id}",
                        name=f"Concurrent Guest {op_id}"
                    )
                    session.add(guest)
                    await session.commit()
                    return {"type": "write", "id": op_id, "guest_id": guest.id}
                return {"type": "write", "id": op_id, "guest_id": None}
        
        # Mix of read and write operations
        tasks = []
        for i in range(20):
            if i % 3 == 0:  # 1/3 writes, 2/3 reads
                tasks.append(write_operation(i))
            else:
                tasks.append(read_operation(i))
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        total_time = (end_time - start_time) * 1000
        
        # All operations should succeed
        assert len(results) == 20
        
        read_results = [r for r in results if r["type"] == "read"]
        write_results = [r for r in results if r["type"] == "write"]
        
        assert len(read_results) > 0
        assert len(write_results) > 0
        
        # Total time should be reasonable
        assert total_time < 5000.0  # Under 5 seconds total
        
        print(f"Mixed Operations - Total: {total_time:.2f}ms, Reads: {len(read_results)}, Writes: {len(write_results)}")


class TestLoadTesting:
    """Test database under load conditions"""
    
    @pytest.mark.asyncio
    async def test_high_volume_inserts(self, performance_test_engine):
        """Test high volume insert operations"""
        async_session = async_sessionmaker(performance_test_engine, class_=AsyncSession)
        
        # Create a hotel first
        async with async_session() as session:
            hotel = Hotel(name="Load Test Hotel", whatsapp_number="+5000000000")
            session.add(hotel)
            await session.commit()
            hotel_id = hotel.id
        
        async def batch_insert(batch_id, batch_size=100):
            async with async_session() as session:
                start_time = time.time()
                
                guests = []
                for i in range(batch_size):
                    guest = Guest(
                        hotel_id=hotel_id,
                        phone=f"+{6000000000 + (batch_id * batch_size) + i}",
                        name=f"Load Test Guest {batch_id}-{i}"
                    )
                    guests.append(guest)
                
                session.add_all(guests)
                await session.commit()
                
                end_time = time.time()
                return {
                    "batch_id": batch_id,
                    "batch_size": batch_size,
                    "execution_time": (end_time - start_time) * 1000
                }
        
        # Run 10 batches of 100 inserts each (1000 total)
        tasks = [batch_insert(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All batches should succeed
        assert len(results) == 10
        
        total_inserts = sum(r["batch_size"] for r in results)
        total_time = sum(r["execution_time"] for r in results)
        avg_batch_time = statistics.mean([r["execution_time"] for r in results])
        
        assert total_inserts == 1000
        assert avg_batch_time < 2000.0  # Average batch under 2 seconds
        
        # Calculate throughput
        throughput = total_inserts / (total_time / 1000)  # Inserts per second
        
        assert throughput > 100  # At least 100 inserts per second
        
        print(f"High Volume Inserts - Total: {total_inserts}, Throughput: {throughput:.2f} inserts/sec")
    
    @pytest.mark.asyncio
    async def test_stress_concurrent_connections(self, performance_test_engine):
        """Test database under stress with many concurrent connections"""
        async_session = async_sessionmaker(performance_test_engine, class_=AsyncSession)
        
        async def stress_operation(op_id):
            async with async_session() as session:
                start_time = time.time()
                
                # Perform multiple operations in one session
                # 1. Read hotels
                hotels_result = await session.execute(text("SELECT COUNT(*) FROM hotels"))
                hotel_count = hotels_result.scalar()
                
                # 2. Read guests
                guests_result = await session.execute(text("SELECT COUNT(*) FROM guests"))
                guest_count = guests_result.scalar()
                
                # 3. Create a notification
                if hotel_count > 0:
                    hotel_result = await session.execute(text("SELECT id FROM hotels LIMIT 1"))
                    hotel_id = hotel_result.scalar()
                    
                    notification = StaffNotification(
                        hotel_id=hotel_id,
                        notification_type=NotificationType.SYSTEM_ALERT,
                        title=f"Stress Test {op_id}",
                        content=f"Stress test notification {op_id}"
                    )
                    session.add(notification)
                    await session.commit()
                
                end_time = time.time()
                return {
                    "op_id": op_id,
                    "hotel_count": hotel_count,
                    "guest_count": guest_count,
                    "execution_time": (end_time - start_time) * 1000
                }
        
        # Run 50 concurrent stress operations
        tasks = [stress_operation(i) for i in range(50)]
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        total_time = (end_time - start_time) * 1000
        
        # All operations should succeed
        assert len(results) == 50
        assert all(r["hotel_count"] >= 0 for r in results)
        
        avg_op_time = statistics.mean([r["execution_time"] for r in results])
        max_op_time = max([r["execution_time"] for r in results])
        
        # Performance under stress should still be reasonable
        assert avg_op_time < 1000.0  # Average under 1 second
        assert max_op_time < 5000.0  # Max under 5 seconds
        assert total_time < 10000.0  # Total under 10 seconds
        
        print(f"Stress Test - Ops: 50, Total: {total_time:.2f}ms, Avg: {avg_op_time:.2f}ms, Max: {max_op_time:.2f}ms")


class TestMemoryAndResourceUsage:
    """Test memory and resource usage patterns"""
    
    @pytest.mark.asyncio
    async def test_large_result_set_handling(self, performance_session, test_data):
        """Test handling of large result sets"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Query large result set
        result = await performance_session.execute(text("""
            SELECT g.*, h.name as hotel_name
            FROM guests g
            JOIN hotels h ON g.hotel_id = h.id
        """))
        
        # Fetch all results
        all_results = result.fetchall()
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        assert len(all_results) > 0
        assert memory_increase < 100  # Should not use more than 100MB additional memory
        
        print(f"Large Result Set - Rows: {len(all_results)}, Memory increase: {memory_increase:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_connection_pool_efficiency(self, performance_test_engine):
        """Test connection pool efficiency under load"""
        async_session = async_sessionmaker(performance_test_engine, class_=AsyncSession)
        
        async def quick_operation(op_id):
            async with async_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar()
        
        # Run many quick operations to test pool efficiency
        tasks = [quick_operation(i) for i in range(100)]
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        total_time = (end_time - start_time) * 1000
        avg_time_per_op = total_time / len(results)
        
        assert len(results) == 100
        assert all(r == 1 for r in results)
        assert avg_time_per_op < 50.0  # Average under 50ms per operation
        
        print(f"Connection Pool Test - Ops: 100, Total: {total_time:.2f}ms, Avg: {avg_time_per_op:.2f}ms/op")
