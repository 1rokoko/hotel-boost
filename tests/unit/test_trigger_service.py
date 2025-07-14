"""
Unit tests for trigger service
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.services.trigger_service import (
    TriggerService,
    TriggerServiceError,
    TriggerNotFoundError,
    TriggerValidationError,
    TriggerTemplateError
)
from app.models.trigger import Trigger, TriggerType
from app.models.hotel import Hotel
from app.schemas.trigger import TriggerCreate, TriggerUpdate, TriggerConditionsUnion, TimeBasedConditions
from app.schemas.trigger_config import TriggerTemplateValidation


class TestTriggerService:
    """Test cases for TriggerService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def trigger_service(self, mock_db):
        """TriggerService instance with mocked database"""
        return TriggerService(mock_db)
    
    @pytest.fixture
    def sample_hotel(self):
        """Sample hotel for testing"""
        return Hotel(
            id=uuid.uuid4(),
            name="Test Hotel",
            whatsapp_number="+1234567890"
        )
    
    @pytest.fixture
    def sample_trigger_create(self):
        """Sample trigger creation data"""
        return TriggerCreate(
            name="Welcome Message",
            trigger_type=TriggerType.TIME_BASED,
            message_template="Welcome to {{ hotel.name }}, {{ guest.name }}!",
            conditions=TriggerConditionsUnion(
                time_based=TimeBasedConditions(
                    schedule_type="hours_after_checkin",
                    hours_after=2
                )
            ),
            is_active=True,
            priority=1
        )
    
    @pytest.fixture
    def sample_trigger(self, sample_hotel):
        """Sample trigger model"""
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
    
    def test_create_trigger_success(self, trigger_service, mock_db, sample_hotel, sample_trigger_create):
        """Test successful trigger creation"""
        # Mock hotel exists
        mock_db.query.return_value.filter.return_value.first.return_value = sample_hotel
        
        # Mock template validation
        with patch.object(trigger_service, '_validate_template') as mock_validate:
            mock_validate.return_value = TriggerTemplateValidation(
                is_valid=True,
                variables=[],
                errors=[],
                warnings=[]
            )
            
            # Mock database operations
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            
            # Create trigger
            result = trigger_service.create_trigger(sample_hotel.id, sample_trigger_create)
            
            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
    
    def test_create_trigger_hotel_not_found(self, trigger_service, mock_db, sample_trigger_create):
        """Test trigger creation with non-existent hotel"""
        # Mock hotel not found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        hotel_id = uuid.uuid4()
        
        with pytest.raises(TriggerServiceError, match="Hotel with ID .* not found"):
            trigger_service.create_trigger(hotel_id, sample_trigger_create)
    
    def test_create_trigger_invalid_template(self, trigger_service, mock_db, sample_hotel, sample_trigger_create):
        """Test trigger creation with invalid template"""
        # Mock hotel exists
        mock_db.query.return_value.filter.return_value.first.return_value = sample_hotel
        
        # Mock template validation failure
        with patch.object(trigger_service, '_validate_template') as mock_validate:
            mock_validate.return_value = TriggerTemplateValidation(
                is_valid=False,
                variables=[],
                errors=["Invalid syntax"],
                warnings=[]
            )
            
            with pytest.raises(TriggerTemplateError, match="Invalid template"):
                trigger_service.create_trigger(sample_hotel.id, sample_trigger_create)
    
    def test_get_trigger_success(self, trigger_service, mock_db, sample_trigger):
        """Test successful trigger retrieval"""
        # Mock trigger found
        mock_db.query.return_value.filter.return_value.first.return_value = sample_trigger
        
        result = trigger_service.get_trigger(sample_trigger.hotel_id, sample_trigger.id)
        
        assert result.id == sample_trigger.id
        assert result.name == sample_trigger.name
    
    def test_get_trigger_not_found(self, trigger_service, mock_db):
        """Test trigger retrieval with non-existent trigger"""
        # Mock trigger not found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        hotel_id = uuid.uuid4()
        trigger_id = uuid.uuid4()
        
        with pytest.raises(TriggerNotFoundError, match="Trigger with ID .* not found"):
            trigger_service.get_trigger(hotel_id, trigger_id)
    
    def test_update_trigger_success(self, trigger_service, mock_db, sample_trigger):
        """Test successful trigger update"""
        # Mock trigger found
        mock_db.query.return_value.filter.return_value.first.return_value = sample_trigger
        
        # Mock template validation
        with patch.object(trigger_service, '_validate_template') as mock_validate:
            mock_validate.return_value = TriggerTemplateValidation(
                is_valid=True,
                variables=[],
                errors=[],
                warnings=[]
            )
            
            # Mock database operations
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            
            update_data = TriggerUpdate(
                name="Updated Welcome Message",
                message_template="Updated: Welcome to {{ hotel.name }}!"
            )
            
            result = trigger_service.update_trigger(
                sample_trigger.hotel_id, 
                sample_trigger.id, 
                update_data
            )
            
            # Verify updates
            assert sample_trigger.name == "Updated Welcome Message"
            assert sample_trigger.message_template == "Updated: Welcome to {{ hotel.name }}!"
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
    
    def test_update_trigger_not_found(self, trigger_service, mock_db):
        """Test trigger update with non-existent trigger"""
        # Mock trigger not found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        hotel_id = uuid.uuid4()
        trigger_id = uuid.uuid4()
        update_data = TriggerUpdate(name="Updated Name")
        
        with pytest.raises(TriggerNotFoundError, match="Trigger with ID .* not found"):
            trigger_service.update_trigger(hotel_id, trigger_id, update_data)
    
    def test_delete_trigger_success(self, trigger_service, mock_db, sample_trigger):
        """Test successful trigger deletion"""
        # Mock trigger found
        mock_db.query.return_value.filter.return_value.first.return_value = sample_trigger
        
        # Mock database operations
        mock_db.delete = Mock()
        mock_db.commit = Mock()
        
        result = trigger_service.delete_trigger(sample_trigger.hotel_id, sample_trigger.id)
        
        assert result is True
        mock_db.delete.assert_called_once_with(sample_trigger)
        mock_db.commit.assert_called_once()
    
    def test_delete_trigger_not_found(self, trigger_service, mock_db):
        """Test trigger deletion with non-existent trigger"""
        # Mock trigger not found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        hotel_id = uuid.uuid4()
        trigger_id = uuid.uuid4()
        
        with pytest.raises(TriggerNotFoundError, match="Trigger with ID .* not found"):
            trigger_service.delete_trigger(hotel_id, trigger_id)
    
    def test_list_triggers_success(self, trigger_service, mock_db, sample_trigger):
        """Test successful trigger listing"""
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_trigger]
        
        mock_db.query.return_value = mock_query
        
        result = trigger_service.list_triggers(sample_trigger.hotel_id)
        
        assert result.total == 1
        assert len(result.triggers) == 1
        assert result.triggers[0].id == sample_trigger.id
    
    def test_get_trigger_statistics_success(self, trigger_service, mock_db, sample_trigger):
        """Test successful trigger statistics retrieval"""
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5  # Total triggers
        
        mock_db.query.return_value = mock_query
        
        result = trigger_service.get_trigger_statistics(sample_trigger.hotel_id)
        
        assert result.total_triggers == 5
        assert result.active_triggers == 5  # All active in this mock
        assert result.inactive_triggers == 0
        assert isinstance(result.triggers_by_type, dict)
    
    def test_convert_conditions_to_dict(self, trigger_service):
        """Test conditions conversion to dictionary"""
        conditions = TriggerConditionsUnion(
            time_based=TimeBasedConditions(
                schedule_type="hours_after_checkin",
                hours_after=2
            )
        )
        
        result = trigger_service._convert_conditions_to_dict(conditions)
        
        assert isinstance(result, dict)
        assert "time_based" in result
        assert result["time_based"]["schedule_type"] == "hours_after_checkin"
        assert result["time_based"]["hours_after"] == 2
