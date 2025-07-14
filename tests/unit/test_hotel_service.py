"""
Unit tests for hotel service
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.services.hotel_service import (
    HotelService,
    HotelServiceError,
    HotelNotFoundError,
    HotelAlreadyExistsError
)
from app.schemas.hotel import HotelCreate, HotelUpdate, HotelSearchParams
from app.models.hotel import Hotel


class TestHotelService:
    """Test cases for HotelService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def hotel_service(self, mock_db):
        """Hotel service instance with mocked database"""
        return HotelService(mock_db)
    
    @pytest.fixture
    def sample_hotel_data(self):
        """Sample hotel creation data"""
        return HotelCreate(
            name="Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            settings={"test": "value"},
            is_active=True
        )
    
    @pytest.fixture
    def sample_hotel_model(self):
        """Sample hotel model instance"""
        hotel = Mock(spec=Hotel)
        hotel.id = uuid.uuid4()
        hotel.name = "Test Hotel"
        hotel.whatsapp_number = "+1234567890"
        hotel.green_api_instance_id = "test_instance"
        hotel.green_api_token = "test_token"
        hotel.green_api_webhook_token = None
        hotel.settings = {"test": "value"}
        hotel.is_active = True
        hotel.has_green_api_credentials = True
        hotel.is_operational = True
        hotel.created_at = "2023-01-01T00:00:00"
        hotel.updated_at = "2023-01-01T00:00:00"
        hotel.get_default_settings.return_value = {"default": "settings"}
        return hotel
    
    def test_create_hotel_success(self, hotel_service, mock_db, sample_hotel_data, sample_hotel_model):
        """Test successful hotel creation"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing hotel
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock hotel creation
        with patch('app.services.hotel_service.Hotel') as mock_hotel_class:
            mock_hotel_class.return_value = sample_hotel_model
            
            # Execute
            result = hotel_service.create_hotel(sample_hotel_data)
            
            # Verify
            assert result.id == sample_hotel_model.id
            assert result.name == sample_hotel_data.name
            assert result.whatsapp_number == sample_hotel_data.whatsapp_number
            
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
    
    def test_create_hotel_already_exists(self, hotel_service, mock_db, sample_hotel_data, sample_hotel_model):
        """Test hotel creation when WhatsApp number already exists"""
        # Setup mocks - existing hotel found
        mock_db.query.return_value.filter.return_value.first.return_value = sample_hotel_model
        
        # Execute and verify exception
        with pytest.raises(HotelAlreadyExistsError) as exc_info:
            hotel_service.create_hotel(sample_hotel_data)
        
        assert "already exists" in str(exc_info.value)
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()
    
    def test_create_hotel_integrity_error(self, hotel_service, mock_db, sample_hotel_data):
        """Test hotel creation with database integrity error"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = Mock()
        mock_db.commit = Mock(side_effect=IntegrityError("test", "test", "test"))
        mock_db.rollback = Mock()
        
        # Execute and verify exception
        with pytest.raises(HotelAlreadyExistsError):
            hotel_service.create_hotel(sample_hotel_data)
        
        mock_db.rollback.assert_called_once()
    
    def test_get_hotel_success(self, hotel_service, mock_db, sample_hotel_model):
        """Test successful hotel retrieval"""
        # Setup mocks
        hotel_id = sample_hotel_model.id
        mock_db.query.return_value.filter.return_value.first.return_value = sample_hotel_model
        
        # Execute
        result = hotel_service.get_hotel(hotel_id)
        
        # Verify
        assert result is not None
        assert result.id == hotel_id
        assert result.name == sample_hotel_model.name
    
    def test_get_hotel_not_found(self, hotel_service, mock_db):
        """Test hotel retrieval when hotel not found"""
        # Setup mocks
        hotel_id = uuid.uuid4()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = hotel_service.get_hotel(hotel_id)
        
        # Verify
        assert result is None
    
    def test_get_hotel_by_whatsapp_number_success(self, hotel_service, mock_db, sample_hotel_model):
        """Test successful hotel retrieval by WhatsApp number"""
        # Setup mocks
        whatsapp_number = sample_hotel_model.whatsapp_number
        mock_db.query.return_value.filter.return_value.first.return_value = sample_hotel_model
        
        # Execute
        result = hotel_service.get_hotel_by_whatsapp_number(whatsapp_number)
        
        # Verify
        assert result is not None
        assert result.whatsapp_number == whatsapp_number
    
    def test_update_hotel_success(self, hotel_service, mock_db, sample_hotel_model):
        """Test successful hotel update"""
        # Setup mocks
        hotel_id = sample_hotel_model.id
        update_data = HotelUpdate(name="Updated Hotel Name")
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_hotel_model
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = hotel_service.update_hotel(hotel_id, update_data)
        
        # Verify
        assert result is not None
        assert result.id == hotel_id
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_update_hotel_not_found(self, hotel_service, mock_db):
        """Test hotel update when hotel not found"""
        # Setup mocks
        hotel_id = uuid.uuid4()
        update_data = HotelUpdate(name="Updated Hotel Name")
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = hotel_service.update_hotel(hotel_id, update_data)
        
        # Verify
        assert result is None
        mock_db.commit.assert_not_called()
    
    def test_update_hotel_whatsapp_conflict(self, hotel_service, mock_db, sample_hotel_model):
        """Test hotel update with WhatsApp number conflict"""
        # Setup mocks
        hotel_id = sample_hotel_model.id
        update_data = HotelUpdate(whatsapp_number="+9876543210")
        
        # Mock existing hotel with same WhatsApp number
        conflicting_hotel = Mock(spec=Hotel)
        conflicting_hotel.id = uuid.uuid4()
        
        mock_db.query.return_value.filter.side_effect = [
            Mock(first=Mock(return_value=sample_hotel_model)),  # First query - get hotel
            Mock(first=Mock(return_value=conflicting_hotel))    # Second query - check conflict
        ]
        
        # Execute and verify exception
        with pytest.raises(HotelAlreadyExistsError):
            hotel_service.update_hotel(hotel_id, update_data)
    
    def test_delete_hotel_success(self, hotel_service, mock_db, sample_hotel_model):
        """Test successful hotel deletion"""
        # Setup mocks
        hotel_id = sample_hotel_model.id
        mock_db.query.return_value.filter.return_value.first.return_value = sample_hotel_model
        mock_db.delete = Mock()
        mock_db.commit = Mock()
        
        # Execute
        result = hotel_service.delete_hotel(hotel_id)
        
        # Verify
        assert result is True
        mock_db.delete.assert_called_once_with(sample_hotel_model)
        mock_db.commit.assert_called_once()
    
    def test_delete_hotel_not_found(self, hotel_service, mock_db):
        """Test hotel deletion when hotel not found"""
        # Setup mocks
        hotel_id = uuid.uuid4()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = hotel_service.delete_hotel(hotel_id)
        
        # Verify
        assert result is False
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()
    
    def test_search_hotels_success(self, hotel_service, mock_db, sample_hotel_model):
        """Test successful hotel search"""
        # Setup mocks
        search_params = HotelSearchParams(
            name="Test",
            page=1,
            size=10,
            sort_by="name",
            sort_order="asc"
        )
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_hotel_model]
        
        mock_db.query.return_value = mock_query
        
        # Execute
        result = hotel_service.search_hotels(search_params)
        
        # Verify
        assert result.total == 1
        assert result.page == 1
        assert result.size == 10
        assert len(result.hotels) == 1
        assert result.hotels[0].id == sample_hotel_model.id
    
    def test_get_active_hotels(self, hotel_service, mock_db, sample_hotel_model):
        """Test getting active hotels"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_hotel_model]
        
        # Execute
        result = hotel_service.get_active_hotels()
        
        # Verify
        assert len(result) == 1
        assert result[0].id == sample_hotel_model.id
        assert result[0].is_active is True
    
    def test_get_operational_hotels(self, hotel_service, mock_db, sample_hotel_model):
        """Test getting operational hotels"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_hotel_model]
        
        # Execute
        result = hotel_service.get_operational_hotels()
        
        # Verify
        assert len(result) == 1
        assert result[0].id == sample_hotel_model.id
        assert result[0].is_operational is True
    
    def test_service_error_handling(self, hotel_service, mock_db, sample_hotel_data):
        """Test service error handling for database errors"""
        # Setup mocks
        mock_db.query.side_effect = SQLAlchemyError("Database error")
        
        # Execute and verify exception
        with pytest.raises(HotelServiceError) as exc_info:
            hotel_service.create_hotel(sample_hotel_data)
        
        assert "Failed to create hotel" in str(exc_info.value)
    
    def test_hotel_to_response_conversion(self, hotel_service, sample_hotel_model):
        """Test conversion of hotel model to response schema"""
        # Execute
        result = hotel_service._hotel_to_response(sample_hotel_model)
        
        # Verify
        assert result.id == sample_hotel_model.id
        assert result.name == sample_hotel_model.name
        assert result.whatsapp_number == sample_hotel_model.whatsapp_number
        assert result.has_green_api_credentials == sample_hotel_model.has_green_api_credentials
        assert result.is_active == sample_hotel_model.is_active
        assert result.is_operational == sample_hotel_model.is_operational
        assert result.settings == sample_hotel_model.settings
