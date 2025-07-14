"""
Performance and load tests for trigger system
"""

import pytest
import uuid
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from app.services.trigger_service import TriggerService
from app.services.trigger_engine import TriggerEngine
from app.services.scheduler import TriggerScheduler
from app.models.trigger import Trigger, TriggerType
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.schemas.trigger import TriggerCreate, TriggerConditionsUnion, TimeBasedConditions


class TestTriggerPerformance:
    """Performance tests for the trigger system"""
    
    @pytest.fixture
    def db_session(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def sample_hotel(self):
        """Sample hotel for testing"""
        return Hotel(
            id=uuid.uuid4(),
            name="Performance Test Hotel",
            whatsapp_number="+1234567890"
        )
    
    @pytest.fixture
    def sample_guests(self, sample_hotel):
        """Create multiple sample guests"""
        guests = []
        for i in range(100):
            guest = Guest(
                id=uuid.uuid4(),
                hotel_id=sample_hotel.id,
                phone_number=f"+123456789{i:02d}",
                name=f"Guest {i}",
                preferences={"room_type": "standard" if i % 2 == 0 else "suite"},
                created_at=datetime.utcnow()
            )
            guests.append(guest)
        return guests
    
    @pytest.fixture
    def sample_triggers(self, sample_hotel):
        """Create multiple sample triggers"""
        triggers = []
        for i in range(50):
            trigger = Trigger(
                id=uuid.uuid4(),
                hotel_id=sample_hotel.id,
                name=f"Trigger {i}",
                trigger_type=TriggerType.TIME_BASED,
                message_template=f"Message {i}: Welcome to {{{{ hotel.name }}}}!",
                conditions={
                    "time_based": {
                        "schedule_type": "hours_after_checkin",
                        "hours_after": i % 24 + 1
                    }
                },
                is_active=True,
                priority=i % 10 + 1
            )
            triggers.append(trigger)
        return triggers
    
    def test_trigger_service_bulk_operations_performance(self, db_session, sample_hotel):
        """Test performance of bulk trigger operations"""
        trigger_service = TriggerService(db_session)
        
        # Mock database operations
        db_session.query.return_value.filter.return_value.first.return_value = sample_hotel
        db_session.add = lambda x: None
        db_session.commit = lambda: None
        db_session.refresh = lambda x: setattr(x, 'id', uuid.uuid4())
        
        # Create trigger data
        trigger_data = TriggerCreate(
            name="Bulk Test Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Bulk test message",
            conditions=TriggerConditionsUnion(
                time_based=TimeBasedConditions(
                    schedule_type="immediate"
                )
            ),
            is_active=True,
            priority=1
        )
        
        with patch.object(trigger_service, '_validate_template') as mock_validate:
            mock_validate.return_value.is_valid = True
            mock_validate.return_value.errors = []
            
            # Measure time for creating 100 triggers
            start_time = time.time()
            
            for i in range(100):
                trigger_service.create_trigger(sample_hotel.id, trigger_data)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should complete within reasonable time (adjust threshold as needed)
            assert execution_time < 5.0, f"Bulk creation took {execution_time:.2f}s, expected < 5.0s"
            
            # Calculate average time per operation
            avg_time = execution_time / 100
            assert avg_time < 0.05, f"Average creation time {avg_time:.3f}s, expected < 0.05s"
    
    @pytest.mark.asyncio
    async def test_trigger_evaluation_performance(self, db_session, sample_hotel, sample_triggers):
        """Test performance of trigger evaluation with many triggers"""
        trigger_engine = TriggerEngine(db_session)
        
        # Mock database query to return all triggers
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = sample_triggers
        db_session.query.return_value = mock_query
        
        # Mock evaluator to return True for some triggers
        with patch.object(trigger_engine.evaluator, 'evaluate_conditions') as mock_evaluate:
            # Return True for every 3rd trigger to simulate realistic conditions
            mock_evaluate.side_effect = lambda *args: hash(str(args)) % 3 == 0
            
            context = {
                "reference_time": datetime.utcnow(),
                "guest": {"preferences": {"room_type": "suite"}}
            }
            
            # Measure evaluation time
            start_time = time.time()
            
            executable_triggers = await trigger_engine.evaluate_triggers(
                hotel_id=sample_hotel.id,
                context=context
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should evaluate 50 triggers quickly
            assert execution_time < 1.0, f"Evaluation took {execution_time:.2f}s, expected < 1.0s"
            
            # Should find approximately 1/3 of triggers as executable
            expected_count = len(sample_triggers) // 3
            assert abs(len(executable_triggers) - expected_count) <= 5
    
    @pytest.mark.asyncio
    async def test_concurrent_trigger_execution_performance(self, db_session, sample_hotel, sample_guests):
        """Test performance of concurrent trigger executions"""
        trigger_engine = TriggerEngine(db_session)
        
        # Create a single trigger for testing
        trigger = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            name="Concurrent Test Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Concurrent test message for {{ guest.name }}",
            conditions={},
            is_active=True,
            priority=1
        )
        
        # Mock database queries
        def mock_query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            
            if model == Trigger:
                mock_query.first.return_value = trigger
            elif model == Hotel:
                mock_query.first.return_value = sample_hotel
            elif model == Guest:
                # Return different guests based on call
                mock_query.first.side_effect = sample_guests
            
            return mock_query
        
        db_session.query.side_effect = mock_query_side_effect
        
        # Mock template renderer and message sender
        with patch.object(trigger_engine.template_renderer, 'render_template') as mock_render, \
             patch.object(trigger_engine.message_sender, 'send_text_message') as mock_send:
            
            mock_render.return_value = "Test message"
            mock_send.return_value = None
            
            # Execute triggers concurrently for multiple guests
            async def execute_for_guest(guest):
                return await trigger_engine.execute_trigger(
                    trigger_id=trigger.id,
                    guest_id=guest.id
                )
            
            start_time = time.time()
            
            # Execute for first 20 guests concurrently
            tasks = [execute_for_guest(guest) for guest in sample_guests[:20]]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should complete concurrent executions quickly
            assert execution_time < 2.0, f"Concurrent execution took {execution_time:.2f}s, expected < 2.0s"
            
            # All executions should succeed
            successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
            assert len(successful_results) == 20
    
    @pytest.mark.asyncio
    async def test_scheduler_performance_with_many_triggers(self, db_session, sample_hotel, sample_guests):
        """Test scheduler performance with many simultaneous scheduling operations"""
        scheduler = TriggerScheduler(db_session)
        
        # Create triggers for scheduling
        triggers = []
        for i in range(50):
            trigger = Trigger(
                id=uuid.uuid4(),
                hotel_id=sample_hotel.id,
                name=f"Scheduled Trigger {i}",
                trigger_type=TriggerType.TIME_BASED,
                message_template=f"Scheduled message {i}",
                conditions={
                    "time_based": {
                        "schedule_type": "hours_after_checkin",
                        "hours_after": i % 12 + 1
                    }
                },
                is_active=True,
                priority=1
            )
            triggers.append(trigger)
        
        # Mock Celery task
        with patch('app.services.scheduler.execute_time_based_trigger_task') as mock_task:
            mock_task.apply_async.return_value.id = "task-id"
            
            # Schedule many triggers
            async def schedule_trigger(trigger, guest):
                execute_at = datetime.utcnow() + timedelta(hours=1)
                return await scheduler.schedule_trigger(
                    trigger=trigger,
                    execute_at=execute_at,
                    guest_id=guest.id
                )
            
            start_time = time.time()
            
            # Schedule triggers for multiple guests
            tasks = []
            for i, trigger in enumerate(triggers):
                guest = sample_guests[i % len(sample_guests)]
                tasks.append(schedule_trigger(trigger, guest))
            
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should schedule all triggers quickly
            assert execution_time < 3.0, f"Scheduling took {execution_time:.2f}s, expected < 3.0s"
            
            # All scheduling operations should succeed
            assert len(results) == 50
            assert all(result == "task-id" for result in results)
    
    def test_memory_usage_with_large_datasets(self, db_session, sample_hotel):
        """Test memory usage with large datasets"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        trigger_service = TriggerService(db_session)
        
        # Mock database operations
        db_session.query.return_value.filter.return_value.first.return_value = sample_hotel
        db_session.add = lambda x: None
        db_session.commit = lambda: None
        db_session.refresh = lambda x: setattr(x, 'id', uuid.uuid4())
        
        # Create many triggers to test memory usage
        trigger_data = TriggerCreate(
            name="Memory Test Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Memory test message",
            conditions=TriggerConditionsUnion(
                time_based=TimeBasedConditions(
                    schedule_type="immediate"
                )
            ),
            is_active=True,
            priority=1
        )
        
        with patch.object(trigger_service, '_validate_template') as mock_validate:
            mock_validate.return_value.is_valid = True
            mock_validate.return_value.errors = []
            
            # Create 1000 triggers
            for i in range(1000):
                trigger_service.create_trigger(sample_hotel.id, trigger_data)
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (adjust threshold as needed)
            assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB, expected < 100MB"
    
    @pytest.mark.asyncio
    async def test_database_query_optimization(self, db_session, sample_hotel, sample_triggers):
        """Test that database queries are optimized for performance"""
        trigger_service = TriggerService(db_session)
        
        # Mock database operations with query counting
        query_count = 0
        
        def count_queries(*args, **kwargs):
            nonlocal query_count
            query_count += 1
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.count.return_value = len(sample_triggers)
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = sample_triggers[:20]  # Simulate pagination
            return mock_query
        
        db_session.query.side_effect = count_queries
        
        # Test paginated listing
        result = trigger_service.list_triggers(
            hotel_id=sample_hotel.id,
            page=1,
            size=20
        )
        
        # Should use minimal number of queries
        assert query_count <= 2, f"Used {query_count} queries, expected <= 2"
        assert result.total == len(sample_triggers)
        assert len(result.triggers) == 20
    
    @pytest.mark.asyncio
    async def test_error_handling_performance(self, db_session, sample_hotel):
        """Test that error handling doesn't significantly impact performance"""
        trigger_engine = TriggerEngine(db_session)
        
        # Create trigger that will cause errors
        trigger = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            name="Error Test Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Error test",
            conditions={},
            is_active=True,
            priority=1
        )
        
        # Mock database to return trigger but cause template error
        def mock_query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            
            if model == Trigger:
                mock_query.first.return_value = trigger
            elif model == Hotel:
                mock_query.first.return_value = sample_hotel
            elif model == Guest:
                mock_query.first.return_value = None  # No guest found
            
            return mock_query
        
        db_session.query.side_effect = mock_query_side_effect
        
        # Mock template renderer to cause errors
        with patch.object(trigger_engine.template_renderer, 'render_template') as mock_render:
            mock_render.side_effect = Exception("Template error")
            
            # Execute multiple failing triggers and measure time
            start_time = time.time()
            
            tasks = []
            for i in range(10):
                task = trigger_engine.execute_trigger(trigger_id=trigger.id)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Error handling should not significantly slow down execution
            assert execution_time < 1.0, f"Error handling took {execution_time:.2f}s, expected < 1.0s"
            
            # All should return error results
            assert len(results) == 10
            for result in results:
                assert isinstance(result, dict)
                assert result['success'] is False
