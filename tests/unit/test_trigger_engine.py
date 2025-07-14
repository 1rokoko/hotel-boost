"""
Unit tests for trigger engine
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.services.trigger_engine import (
    TriggerEngine,
    TriggerEngineError,
    TriggerExecutionError
)
from app.models.trigger import Trigger, TriggerType
from app.models.hotel import Hotel
from app.models.guest import Guest


class TestTriggerEngine:
    """Test cases for TriggerEngine"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def trigger_engine(self, mock_db):
        """TriggerEngine instance with mocked database"""
        with patch('app.services.trigger_engine.MessageSender'):
            engine = TriggerEngine(mock_db)
            engine.message_sender = Mock()
            engine.message_sender.send_text_message = AsyncMock()
            return engine
    
    @pytest.fixture
    def sample_hotel(self):
        """Sample hotel for testing"""
        return Hotel(
            id=uuid.uuid4(),
            name="Test Hotel",
            whatsapp_number="+1234567890",
            settings={"timezone": "UTC"}
        )
    
    @pytest.fixture
    def sample_guest(self, sample_hotel):
        """Sample guest for testing"""
        return Guest(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            phone_number="+1987654321",
            name="John Doe",
            preferences={"room_type": "suite"},
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_trigger(self, sample_hotel):
        """Sample trigger for testing"""
        return Trigger(
            id=uuid.uuid4(),
            hotel_id=sample_hotel.id,
            name="Welcome Message",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Welcome to {{ hotel.name }}, {{ guest.name }}!",
            conditions={
                "time_based": {
                    "schedule_type": "hours_after_checkin",
                    "hours_after": 2
                }
            },
            is_active=True,
            priority=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_evaluate_triggers_success(self, trigger_engine, mock_db, sample_trigger):
        """Test successful trigger evaluation"""
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [sample_trigger]
        mock_db.query.return_value = mock_query
        
        # Mock evaluator
        trigger_engine.evaluator.evaluate_conditions = AsyncMock(return_value=True)
        
        context = {
            "reference_time": datetime.utcnow(),
            "guest_id": str(uuid.uuid4())
        }
        
        result = await trigger_engine.evaluate_triggers(
            sample_trigger.hotel_id,
            context,
            TriggerType.TIME_BASED
        )
        
        assert len(result) == 1
        assert result[0]['trigger'] == sample_trigger
        assert result[0]['context'] == context
    
    @pytest.mark.asyncio
    async def test_evaluate_triggers_no_matches(self, trigger_engine, mock_db, sample_trigger):
        """Test trigger evaluation with no matching triggers"""
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [sample_trigger]
        mock_db.query.return_value = mock_query
        
        # Mock evaluator returns False
        trigger_engine.evaluator.evaluate_conditions = AsyncMock(return_value=False)
        
        context = {"reference_time": datetime.utcnow()}
        
        result = await trigger_engine.evaluate_triggers(
            sample_trigger.hotel_id,
            context
        )
        
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_execute_trigger_success(self, trigger_engine, mock_db, sample_trigger, sample_hotel, sample_guest):
        """Test successful trigger execution"""
        # Mock database queries
        def mock_query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            
            if model == Trigger:
                mock_query.first.return_value = sample_trigger
            elif model == Hotel:
                mock_query.first.return_value = sample_hotel
            elif model == Guest:
                mock_query.first.return_value = sample_guest
            
            return mock_query
        
        mock_db.query.side_effect = mock_query_side_effect
        
        # Mock template renderer
        trigger_engine.template_renderer.render_template = AsyncMock(
            return_value="Welcome to Test Hotel, John Doe!"
        )
        
        result = await trigger_engine.execute_trigger(
            sample_trigger.id,
            sample_guest.id
        )
        
        assert result['success'] is True
        assert result['message_sent'] is True
        assert result['rendered_message'] == "Welcome to Test Hotel, John Doe!"
        assert 'execution_time_ms' in result
        
        # Verify message was sent
        trigger_engine.message_sender.send_text_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_trigger_not_found(self, trigger_engine, mock_db):
        """Test trigger execution with non-existent trigger"""
        # Mock trigger not found
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        
        trigger_id = uuid.uuid4()
        
        with pytest.raises(TriggerExecutionError, match="Trigger .* not found"):
            await trigger_engine.execute_trigger(trigger_id)
    
    @pytest.mark.asyncio
    async def test_execute_trigger_inactive(self, trigger_engine, mock_db, sample_trigger):
        """Test trigger execution with inactive trigger"""
        # Make trigger inactive
        sample_trigger.is_active = False
        
        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_trigger
        mock_db.query.return_value = mock_query
        
        with pytest.raises(TriggerExecutionError, match="Trigger .* is not active"):
            await trigger_engine.execute_trigger(sample_trigger.id)
    
    @pytest.mark.asyncio
    async def test_execute_trigger_message_send_failure(self, trigger_engine, mock_db, sample_trigger, sample_hotel, sample_guest):
        """Test trigger execution with message sending failure"""
        # Mock database queries
        def mock_query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            
            if model == Trigger:
                mock_query.first.return_value = sample_trigger
            elif model == Hotel:
                mock_query.first.return_value = sample_hotel
            elif model == Guest:
                mock_query.first.return_value = sample_guest
            
            return mock_query
        
        mock_db.query.side_effect = mock_query_side_effect
        
        # Mock template renderer
        trigger_engine.template_renderer.render_template = AsyncMock(
            return_value="Welcome message"
        )
        
        # Mock message sender failure
        trigger_engine.message_sender.send_text_message = AsyncMock(
            side_effect=Exception("Send failed")
        )
        
        with pytest.raises(TriggerExecutionError, match="Failed to send message"):
            await trigger_engine.execute_trigger(sample_trigger.id, sample_guest.id)
    
    @pytest.mark.asyncio
    async def test_schedule_time_based_trigger_success(self, trigger_engine, sample_trigger, sample_guest):
        """Test successful time-based trigger scheduling"""
        reference_time = datetime.utcnow()
        
        result = await trigger_engine.schedule_time_based_trigger(
            sample_trigger,
            sample_guest,
            reference_time
        )
        
        # Should return scheduled time (2 hours after reference)
        expected_time = reference_time + timedelta(hours=2)
        assert result == expected_time
    
    @pytest.mark.asyncio
    async def test_schedule_time_based_trigger_wrong_type(self, trigger_engine, sample_trigger, sample_guest):
        """Test scheduling non-time-based trigger"""
        # Change trigger type
        sample_trigger.trigger_type = TriggerType.EVENT_BASED
        
        with pytest.raises(TriggerEngineError, match="Trigger is not time-based"):
            await trigger_engine.schedule_time_based_trigger(
                sample_trigger,
                sample_guest
            )
    
    @pytest.mark.asyncio
    async def test_schedule_time_based_trigger_invalid_conditions(self, trigger_engine, sample_trigger, sample_guest):
        """Test scheduling with invalid conditions"""
        # Remove time-based conditions
        sample_trigger.conditions = {}
        
        with pytest.raises(TriggerEngineError, match="Invalid time-based conditions"):
            await trigger_engine.schedule_time_based_trigger(
                sample_trigger,
                sample_guest
            )
    
    def test_build_template_context(self, trigger_engine, sample_hotel, sample_guest, sample_trigger):
        """Test template context building"""
        additional_context = {"custom_field": "custom_value"}
        
        context = trigger_engine._build_template_context(
            sample_hotel,
            sample_guest,
            sample_trigger,
            additional_context
        )
        
        # Verify context structure
        assert 'hotel' in context
        assert context['hotel']['name'] == sample_hotel.name
        assert context['hotel']['whatsapp_number'] == sample_hotel.whatsapp_number
        
        assert 'guest' in context
        assert context['guest']['name'] == sample_guest.name
        assert context['guest']['phone_number'] == sample_guest.phone_number
        assert context['guest']['preferences'] == sample_guest.preferences
        
        assert 'trigger' in context
        assert context['trigger']['name'] == sample_trigger.name
        assert context['trigger']['type'] == sample_trigger.trigger_type.value
        
        assert 'now' in context
        assert isinstance(context['now'], datetime)
        
        assert context['custom_field'] == "custom_value"
    
    def test_build_template_context_no_guest(self, trigger_engine, sample_hotel, sample_trigger):
        """Test template context building without guest"""
        context = trigger_engine._build_template_context(
            sample_hotel,
            None,
            sample_trigger,
            {}
        )
        
        # Should still have hotel and trigger context
        assert 'hotel' in context
        assert 'trigger' in context
        assert 'now' in context
        
        # Guest should not be in context
        assert 'guest' not in context
