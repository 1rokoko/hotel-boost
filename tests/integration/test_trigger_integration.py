"""
Integration tests for trigger system
"""

import pytest
import uuid
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models.trigger import Trigger, TriggerType
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.services.trigger_service import TriggerService
from app.services.trigger_engine import TriggerEngine
from app.services.scheduler import TriggerScheduler
from app.schemas.trigger import TriggerCreate, TriggerConditionsUnion, TimeBasedConditions


class TestTriggerIntegration:
    """Integration tests for the complete trigger system"""
    
    @pytest.fixture
    def client(self):
        """Test client"""
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        """Database session for testing"""
        # In a real test, this would be a test database session
        # For now, we'll mock it
        from unittest.mock import Mock
        return Mock(spec=Session)
    
    @pytest.fixture
    def sample_hotel(self, db_session):
        """Create a sample hotel"""
        hotel = Hotel(
            id=uuid.uuid4(),
            name="Integration Test Hotel",
            whatsapp_number="+1234567890",
            settings={"timezone": "UTC"}
        )
        return hotel
    
    @pytest.fixture
    def sample_guest(self, sample_hotel, db_session):
        """Create a sample guest"""
        guest = Guest(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            phone_number="+1987654321",
            name="John Doe",
            preferences={"room_type": "suite", "vip": True},
            created_at=datetime.utcnow()
        )
        return guest
    
    @pytest.mark.asyncio
    async def test_end_to_end_trigger_creation_and_execution(self, db_session, sample_hotel, sample_guest):
        """Test complete flow from trigger creation to execution"""
        # Step 1: Create trigger service
        trigger_service = TriggerService(db_session)
        
        # Mock database operations for trigger creation
        db_session.query.return_value.filter.return_value.first.return_value = sample_hotel
        db_session.add = lambda x: None
        db_session.commit = lambda: None
        db_session.refresh = lambda x: setattr(x, 'id', uuid.uuid4())
        
        # Step 2: Create a trigger
        trigger_data = TriggerCreate(
            name="Welcome Message",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Welcome to {{ hotel.name }}, {{ guest.name }}! Your {{ guest.preferences.room_type }} room is ready.",
            conditions=TriggerConditionsUnion(
                time_based=TimeBasedConditions(
                    schedule_type="hours_after_checkin",
                    hours_after=2
                )
            ),
            is_active=True,
            priority=1
        )
        
        with patch.object(trigger_service, '_validate_template') as mock_validate:
            mock_validate.return_value.is_valid = True
            mock_validate.return_value.errors = []
            
            trigger_response = trigger_service.create_trigger(sample_hotel.id, trigger_data)
            assert trigger_response.name == "Welcome Message"
        
        # Step 3: Create trigger engine and execute
        trigger_engine = TriggerEngine(db_session)
        
        # Mock the trigger retrieval for execution
        sample_trigger = Trigger(
            id=trigger_response.id,
            hotel_id=sample_hotel.id,
            name="Welcome Message",
            trigger_type=TriggerType.TIME_BASED,
            message_template=trigger_data.message_template,
            conditions={
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 2
                }
            },
            is_active=True,
            priority=1
        )
        
        def mock_query_side_effect(model):
            from unittest.mock import Mock
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            
            if model == Trigger:
                mock_query.first.return_value = sample_trigger
            elif model == Hotel:
                mock_query.first.return_value = sample_hotel
            elif model == Guest:
                mock_query.first.return_value = sample_guest
            
            return mock_query
        
        db_session.query.side_effect = mock_query_side_effect
        
        # Mock template renderer and message sender
        with patch.object(trigger_engine.template_renderer, 'render_template') as mock_render, \
             patch.object(trigger_engine.message_sender, 'send_text_message') as mock_send:
            
            mock_render.return_value = "Welcome to Integration Test Hotel, John Doe! Your suite room is ready."
            mock_send.return_value = None
            
            # Execute the trigger
            result = await trigger_engine.execute_trigger(
                trigger_id=sample_trigger.id,
                guest_id=sample_guest.id
            )
            
            # Verify execution
            assert result['success'] is True
            assert result['message_sent'] is True
            assert "Integration Test Hotel" in result['rendered_message']
            assert "John Doe" in result['rendered_message']
            assert "suite" in result['rendered_message']
    
    @pytest.mark.asyncio
    async def test_trigger_evaluation_and_scheduling_flow(self, db_session, sample_hotel, sample_guest):
        """Test trigger evaluation and scheduling integration"""
        # Create trigger engine
        trigger_engine = TriggerEngine(db_session)
        
        # Create sample triggers
        time_trigger = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            name="Time-based Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Time-based message",
            conditions={
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 1
                }
            },
            is_active=True,
            priority=1
        )
        
        condition_trigger = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            name="Condition-based Trigger",
            trigger_type=TriggerType.CONDITION_BASED,
            message_template="VIP message",
            conditions={
                "condition_based": {
                    "conditions": [
                        {
                            "field": "guest.preferences.vip",
                            "operator": "equals",
                            "value": True
                        }
                    ],
                    "logic": "AND"
                }
            },
            is_active=True,
            priority=2
        )
        
        # Mock database query to return triggers
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [time_trigger, condition_trigger]
        db_session.query.return_value = mock_query
        
        # Test context for evaluation
        context = {
            "reference_time": datetime.utcnow() - timedelta(hours=2),  # 2 hours ago
            "guest": {
                "preferences": {
                    "vip": True,
                    "room_type": "suite"
                }
            }
        }
        
        # Mock evaluator to return True for both triggers
        with patch.object(trigger_engine.evaluator, 'evaluate_conditions') as mock_evaluate:
            mock_evaluate.return_value = True
            
            # Evaluate triggers
            executable_triggers = await trigger_engine.evaluate_triggers(
                hotel_id=sample_hotel.id,
                context=context
            )
            
            # Should find both triggers as executable
            assert len(executable_triggers) == 2
            assert executable_triggers[0]['trigger'] == time_trigger  # Higher priority first
            assert executable_triggers[1]['trigger'] == condition_trigger
    
    @pytest.mark.asyncio
    async def test_scheduler_integration_with_celery_tasks(self, db_session, sample_hotel, sample_guest):
        """Test scheduler integration with Celery tasks"""
        # Create scheduler
        scheduler = TriggerScheduler(db_session)
        
        # Create a time-based trigger
        trigger = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            name="Scheduled Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Scheduled message",
            conditions={
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 3
                }
            },
            is_active=True,
            priority=1
        )
        
        # Mock Celery task
        with patch('app.services.scheduler.execute_time_based_trigger_task') as mock_task:
            mock_task.apply_async.return_value.id = "task-123"
            
            # Schedule trigger for future execution
            execute_at = datetime.utcnow() + timedelta(hours=1)
            task_id = await scheduler.schedule_trigger(
                trigger=trigger,
                execute_at=execute_at,
                guest_id=sample_guest.id
            )
            
            assert task_id == "task-123"
            mock_task.apply_async.assert_called_once()
            
            # Verify task arguments
            args, kwargs = mock_task.apply_async.call_args
            assert str(trigger.id) in args[0]
            assert str(sample_guest.id) in args[0]
            assert 'countdown' in kwargs
    
    @pytest.mark.asyncio
    async def test_event_based_trigger_flow(self, db_session, sample_hotel, sample_guest):
        """Test event-based trigger evaluation and execution flow"""
        # Create trigger engine
        trigger_engine = TriggerEngine(db_session)
        
        # Create event-based trigger
        event_trigger = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            name="Check-in Event Trigger",
            trigger_type=TriggerType.EVENT_BASED,
            message_template="Thank you for checking in, {{ guest.name }}!",
            conditions={
                "event_based": {
                    "event_type": "guest_checkin",
                    "delay_minutes": 0
                }
            },
            is_active=True,
            priority=1
        )
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [event_trigger]
        db_session.query.return_value = mock_query
        
        # Event context
        event_context = {
            "event_type": "guest_checkin",
            "event_time": datetime.utcnow(),
            "guest_id": str(sample_guest.id),
            "guest": {
                "name": "John Doe",
                "preferences": {}
            }
        }
        
        # Mock evaluator
        with patch.object(trigger_engine.evaluator, 'evaluate_conditions') as mock_evaluate:
            mock_evaluate.return_value = True
            
            # Evaluate event triggers
            executable_triggers = await trigger_engine.evaluate_triggers(
                hotel_id=sample_hotel.id,
                context=event_context,
                trigger_type=TriggerType.EVENT_BASED
            )
            
            assert len(executable_triggers) == 1
            assert executable_triggers[0]['trigger'] == event_trigger
    
    def test_api_integration_with_services(self, client):
        """Test API integration with underlying services"""
        hotel_id = uuid.uuid4()
        
        # Mock dependencies
        with patch('app.api.v1.endpoints.triggers.get_current_tenant_id') as mock_tenant, \
             patch('app.api.v1.endpoints.triggers.get_trigger_service') as mock_service:
            
            mock_tenant.return_value = hotel_id
            
            # Mock successful trigger creation
            from app.schemas.trigger import TriggerResponse
            mock_response = TriggerResponse(
                id=uuid.uuid4(),
                hotel_id=hotel_id,
                name="API Test Trigger",
                trigger_type=TriggerType.TIME_BASED,
                message_template="API test message",
                conditions={
                    "time_based": {
                        "schedule_type": "immediate"
                    }
                },
                is_active=True,
                priority=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            mock_service.return_value.create_trigger.return_value = mock_response
            
            # Test trigger creation via API
            trigger_data = {
                "name": "API Test Trigger",
                "trigger_type": "TIME_BASED",
                "message_template": "API test message",
                "conditions": {
                    "time_based": {
                        "schedule_type": "immediate"
                    }
                },
                "is_active": True,
                "priority": 1
            }
            
            response = client.post("/api/v1/triggers/", json=trigger_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "API Test Trigger"
            
            # Verify service was called correctly
            mock_service.return_value.create_trigger.assert_called_once()
            call_args = mock_service.return_value.create_trigger.call_args
            assert call_args[0][0] == hotel_id  # hotel_id
            assert call_args[0][1].name == "API Test Trigger"  # trigger_data
    
    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, db_session):
        """Test that triggers are properly isolated between hotels"""
        # Create two hotels
        hotel1 = Hotel(id=uuid.uuid4(), name="Hotel 1", whatsapp_number="+1111111111")
        hotel2 = Hotel(id=uuid.uuid4(), name="Hotel 2", whatsapp_number="+2222222222")
        
        # Create trigger service
        trigger_service = TriggerService(db_session)
        
        # Mock database operations
        def mock_query_side_effect(model):
            from unittest.mock import Mock
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            
            if model == Hotel:
                # Return different hotels based on filter
                mock_query.first.side_effect = [hotel1, hotel2]
            
            return mock_query
        
        db_session.query.side_effect = mock_query_side_effect
        db_session.add = lambda x: None
        db_session.commit = lambda: None
        db_session.refresh = lambda x: setattr(x, 'id', uuid.uuid4())
        
        # Create triggers for both hotels
        trigger_data = TriggerCreate(
            name="Hotel Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Welcome to {{ hotel.name }}!",
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
            
            # Create trigger for hotel 1
            trigger1 = trigger_service.create_trigger(hotel1.id, trigger_data)
            assert trigger1.hotel_id == hotel1.id
            
            # Create trigger for hotel 2
            trigger2 = trigger_service.create_trigger(hotel2.id, trigger_data)
            assert trigger2.hotel_id == hotel2.id
            
            # Verify triggers are associated with correct hotels
            assert trigger1.hotel_id != trigger2.hotel_id
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, db_session, sample_hotel, sample_guest):
        """Test error handling and recovery in the trigger system"""
        # Create trigger engine
        trigger_engine = TriggerEngine(db_session)
        
        # Create a trigger
        trigger = Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            name="Error Test Trigger",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Error test message",
            conditions={},
            is_active=True,
            priority=1
        )
        
        # Mock database queries
        def mock_query_side_effect(model):
            from unittest.mock import Mock
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            
            if model == Trigger:
                mock_query.first.return_value = trigger
            elif model == Hotel:
                mock_query.first.return_value = sample_hotel
            elif model == Guest:
                mock_query.first.return_value = sample_guest
            
            return mock_query
        
        db_session.query.side_effect = mock_query_side_effect
        
        # Test template rendering error
        with patch.object(trigger_engine.template_renderer, 'render_template') as mock_render:
            mock_render.side_effect = Exception("Template rendering failed")
            
            result = await trigger_engine.execute_trigger(
                trigger_id=trigger.id,
                guest_id=sample_guest.id
            )
            
            # Should handle error gracefully
            assert result['success'] is False
            assert "Template rendering failed" in result['error_message']
        
        # Test message sending error
        with patch.object(trigger_engine.template_renderer, 'render_template') as mock_render, \
             patch.object(trigger_engine.message_sender, 'send_text_message') as mock_send:
            
            mock_render.return_value = "Test message"
            mock_send.side_effect = Exception("Message sending failed")
            
            with pytest.raises(Exception, match="Failed to send message"):
                await trigger_engine.execute_trigger(
                    trigger_id=trigger.id,
                    guest_id=sample_guest.id
                )
