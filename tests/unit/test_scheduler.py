"""
Unit tests for trigger scheduler
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.services.scheduler import (
    TriggerScheduler,
    TriggerSchedulerError
)
from app.models.trigger import Trigger, TriggerType
from app.models.guest import Guest


class TestTriggerScheduler:
    """Test cases for TriggerScheduler"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def scheduler(self, mock_db):
        """TriggerScheduler instance with mocked database"""
        return TriggerScheduler(mock_db)
    
    @pytest.fixture
    def sample_trigger(self):
        """Sample trigger for testing"""
        return Trigger(
            id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            name="Welcome Message",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Welcome to {{ hotel.name }}!",
            conditions={
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 2
                }
            },
            is_active=True,
            priority=1
        )
    
    @pytest.fixture
    def sample_guest(self):
        """Sample guest for testing"""
        return Guest(
            id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            phone_number="+1234567890",
            name="John Doe",
            preferences={}
        )
    
    @pytest.mark.asyncio
    async def test_schedule_trigger_future_time(self, scheduler):
        """Test scheduling trigger for future execution"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        
        execute_at = datetime.utcnow() + timedelta(hours=1)
        guest_id = uuid.uuid4()
        
        with patch('app.services.scheduler.execute_time_based_trigger_task') as mock_task:
            mock_task.apply_async.return_value = Mock(id="task-123")
            
            result = await scheduler.schedule_trigger(
                trigger=trigger,
                execute_at=execute_at,
                guest_id=guest_id
            )
            
            assert result == "task-123"
            mock_task.apply_async.assert_called_once()
            
            # Verify task arguments
            args, kwargs = mock_task.apply_async.call_args
            assert str(trigger.id) in args[0]
            assert str(guest_id) in args[0]
            assert execute_at.isoformat() in args[0]
            assert 'countdown' in kwargs
            assert kwargs['countdown'] > 0
    
    @pytest.mark.asyncio
    async def test_schedule_trigger_past_time(self, scheduler):
        """Test scheduling trigger for past execution (immediate)"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        
        execute_at = datetime.utcnow() - timedelta(hours=1)
        
        with patch('app.services.scheduler.execute_time_based_trigger_task') as mock_task:
            mock_task.apply_async.return_value = Mock(id="task-123")
            
            result = await scheduler.schedule_trigger(
                trigger=trigger,
                execute_at=execute_at
            )
            
            assert result == "task-123"
            
            # Verify immediate execution (countdown=0)
            args, kwargs = mock_task.apply_async.call_args
            assert kwargs['countdown'] == 0
    
    @pytest.mark.asyncio
    async def test_cancel_scheduled_trigger_success(self, scheduler):
        """Test successful trigger cancellation"""
        task_id = "task-123"
        
        with patch('app.services.scheduler.celery_app') as mock_celery:
            mock_control = Mock()
            mock_celery.control = mock_control
            
            result = await scheduler.cancel_scheduled_trigger(task_id)
            
            assert result is True
            mock_control.revoke.assert_called_once_with(task_id, terminate=True)
    
    @pytest.mark.asyncio
    async def test_cancel_scheduled_trigger_failure(self, scheduler):
        """Test trigger cancellation failure"""
        task_id = "task-123"
        
        with patch('app.services.scheduler.celery_app') as mock_celery:
            mock_celery.control.revoke.side_effect = Exception("Revoke failed")
            
            result = await scheduler.cancel_scheduled_trigger(task_id)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_reschedule_trigger_success(self, scheduler):
        """Test successful trigger rescheduling"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        
        old_task_id = "old-task-123"
        new_time = datetime.utcnow() + timedelta(hours=2)
        
        with patch.object(scheduler, 'cancel_scheduled_trigger') as mock_cancel, \
             patch.object(scheduler, 'schedule_trigger') as mock_schedule:
            
            mock_cancel.return_value = True
            mock_schedule.return_value = "new-task-456"
            
            result = await scheduler.reschedule_trigger(
                task_id=old_task_id,
                trigger=trigger,
                new_time=new_time
            )
            
            assert result == "new-task-456"
            mock_cancel.assert_called_once_with(old_task_id)
            mock_schedule.assert_called_once_with(
                trigger=trigger,
                execute_at=new_time,
                guest_id=None,
                context=None
            )
    
    @pytest.mark.asyncio
    async def test_schedule_time_based_triggers_for_guest(self, scheduler, mock_db, sample_guest):
        """Test scheduling all time-based triggers for a guest"""
        # Create sample triggers
        trigger1 = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_guest.hotel_id,
            trigger_type=TriggerType.TIME_BASED,
            conditions={
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 1
                }
            },
            is_active=True
        )
        
        trigger2 = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_guest.hotel_id,
            trigger_type=TriggerType.TIME_BASED,
            conditions={
                "time_based": {
                    "schedule_type": "days_after_checkin",
                    "days_after": 1
                }
            },
            is_active=True
        )
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [trigger1, trigger2]
        mock_db.query.return_value = mock_query
        
        with patch.object(scheduler, 'schedule_trigger') as mock_schedule:
            mock_schedule.return_value = "task-id"
            
            result = await scheduler.schedule_time_based_triggers_for_guest(sample_guest)
            
            assert len(result) == 2
            assert all(task_id == "task-id" for task_id in result)
            assert mock_schedule.call_count == 2
    
    @pytest.mark.asyncio
    async def test_trigger_event_success(self, scheduler):
        """Test successful event triggering"""
        hotel_id = uuid.uuid4()
        event_type = "guest_checkin"
        event_data = {"guest_id": str(uuid.uuid4())}
        
        with patch('app.services.scheduler.evaluate_event_triggers_task') as mock_task:
            mock_task.delay.return_value = Mock(id="task-123")
            
            result = await scheduler.trigger_event(hotel_id, event_type, event_data)
            
            assert result == "task-123"
            mock_task.delay.assert_called_once_with(
                hotel_id=str(hotel_id),
                event_type=event_type,
                event_data=event_data,
                correlation_id=result  # This will be different, but that's ok
            )
    
    def test_calculate_execution_time_hours_after_checkin(self, scheduler):
        """Test execution time calculation for hours after check-in"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        trigger.conditions = {
            "time_based": {
                "schedule_type": "hours_after_checkin",
                "hours_after": 3
            }
        }
        
        reference_time = datetime(2023, 1, 1, 12, 0, 0)
        
        result = scheduler._calculate_execution_time(trigger, reference_time)
        
        expected_time = reference_time + timedelta(hours=3)
        assert result == expected_time
    
    def test_calculate_execution_time_days_after_checkin(self, scheduler):
        """Test execution time calculation for days after check-in"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        trigger.conditions = {
            "time_based": {
                "schedule_type": "days_after_checkin",
                "days_after": 2
            }
        }
        
        reference_time = datetime(2023, 1, 1, 12, 0, 0)
        
        result = scheduler._calculate_execution_time(trigger, reference_time)
        
        expected_time = reference_time + timedelta(days=2)
        assert result == expected_time
    
    def test_calculate_execution_time_immediate(self, scheduler):
        """Test execution time calculation for immediate execution"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        trigger.conditions = {
            "time_based": {
                "schedule_type": "immediate"
            }
        }
        
        reference_time = datetime(2023, 1, 1, 12, 0, 0)
        
        result = scheduler._calculate_execution_time(trigger, reference_time)
        
        assert result == reference_time
    
    def test_calculate_execution_time_invalid_conditions(self, scheduler):
        """Test execution time calculation with invalid conditions"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        trigger.conditions = {}
        
        reference_time = datetime(2023, 1, 1, 12, 0, 0)
        
        result = scheduler._calculate_execution_time(trigger, reference_time)
        
        assert result is None
    
    def test_calculate_execution_time_unknown_schedule_type(self, scheduler):
        """Test execution time calculation with unknown schedule type"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        trigger.conditions = {
            "time_based": {
                "schedule_type": "unknown_type"
            }
        }
        
        reference_time = datetime(2023, 1, 1, 12, 0, 0)
        
        result = scheduler._calculate_execution_time(trigger, reference_time)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_schedule_trigger_with_context(self, scheduler):
        """Test scheduling trigger with additional context"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        
        execute_at = datetime.utcnow() + timedelta(hours=1)
        context = {"custom_field": "custom_value"}
        
        with patch('app.services.scheduler.execute_time_based_trigger_task') as mock_task:
            mock_task.apply_async.return_value = Mock(id="task-123")
            
            result = await scheduler.schedule_trigger(
                trigger=trigger,
                execute_at=execute_at,
                context=context
            )
            
            assert result == "task-123"
            mock_task.apply_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_schedule_trigger_error_handling(self, scheduler):
        """Test error handling in trigger scheduling"""
        trigger = Mock()
        trigger.id = uuid.uuid4()
        
        execute_at = datetime.utcnow() + timedelta(hours=1)
        
        with patch('app.services.scheduler.execute_time_based_trigger_task') as mock_task:
            mock_task.apply_async.side_effect = Exception("Scheduling failed")
            
            with pytest.raises(TriggerSchedulerError, match="Failed to schedule trigger"):
                await scheduler.schedule_trigger(
                    trigger=trigger,
                    execute_at=execute_at
                )
    
    @pytest.mark.asyncio
    async def test_trigger_event_error_handling(self, scheduler):
        """Test error handling in event triggering"""
        hotel_id = uuid.uuid4()
        event_type = "guest_checkin"
        event_data = {}
        
        with patch('app.services.scheduler.evaluate_event_triggers_task') as mock_task:
            mock_task.delay.side_effect = Exception("Event trigger failed")
            
            with pytest.raises(TriggerSchedulerError, match="Failed to trigger event evaluation"):
                await scheduler.trigger_event(hotel_id, event_type, event_data)
