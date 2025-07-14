"""
Unit tests for hotel validator
"""

import pytest
import uuid
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.services.hotel_validator import (
    HotelValidator,
    ValidationResult,
    ValidationError
)
from app.schemas.hotel import HotelCreate, HotelUpdate
from app.models.hotel import Hotel


class TestValidationResult:
    """Test cases for ValidationResult"""
    
    def test_validation_result_initialization(self):
        """Test ValidationResult initialization"""
        result = ValidationResult()
        
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.field_errors == {}
    
    def test_add_error(self):
        """Test adding validation errors"""
        result = ValidationResult()
        
        result.add_error("Test error")
        assert result.is_valid is False
        assert "Test error" in result.errors
        
        result.add_error("Field error", "field_name")
        assert "field_name" in result.field_errors
        assert "Field error" in result.field_errors["field_name"]
    
    def test_add_warning(self):
        """Test adding validation warnings"""
        result = ValidationResult()
        
        result.add_warning("Test warning")
        assert result.is_valid is True  # Warnings don't affect validity
        assert "Test warning" in result.warnings
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        result = ValidationResult()
        result.add_error("Test error", "test_field")
        result.add_warning("Test warning")
        
        dict_result = result.to_dict()
        
        assert dict_result["is_valid"] is False
        assert "Test error" in dict_result["errors"]
        assert "Test warning" in dict_result["warnings"]
        assert "test_field" in dict_result["field_errors"]


class TestHotelValidator:
    """Test cases for HotelValidator"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def hotel_validator(self, mock_db):
        """Hotel validator instance with mocked database"""
        return HotelValidator(mock_db)
    
    @pytest.fixture
    def valid_hotel_data(self):
        """Valid hotel creation data"""
        return HotelCreate(
            name="Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            green_api_webhook_token="webhook_token_123",
            settings={
                "notifications": {"email_enabled": True},
                "auto_responses": {"enabled": True}
            },
            is_active=True
        )
    
    def test_validate_hotel_create_success(self, hotel_validator, mock_db, valid_hotel_data):
        """Test successful hotel creation validation"""
        # Setup mocks - no existing hotel
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = hotel_validator.validate_hotel_create(valid_hotel_data)
        
        # Verify
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_hotel_name_empty(self, hotel_validator, mock_db):
        """Test validation with empty hotel name"""
        hotel_data = HotelCreate(
            name="",
            whatsapp_number="+1234567890"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("name cannot be empty" in error for error in result.errors)
    
    def test_validate_hotel_name_too_short(self, hotel_validator, mock_db):
        """Test validation with too short hotel name"""
        hotel_data = HotelCreate(
            name="A",
            whatsapp_number="+1234567890"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("at least 2 characters" in error for error in result.errors)
    
    def test_validate_hotel_name_too_long(self, hotel_validator, mock_db):
        """Test validation with too long hotel name"""
        hotel_data = HotelCreate(
            name="A" * 256,  # Exceeds 255 character limit
            whatsapp_number="+1234567890"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("cannot exceed 255 characters" in error for error in result.errors)
    
    def test_validate_whatsapp_number_invalid_format(self, hotel_validator, mock_db):
        """Test validation with invalid WhatsApp number format"""
        hotel_data = HotelCreate(
            name="Test Hotel",
            whatsapp_number="invalid_number"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("valid international phone number" in error for error in result.errors)
    
    def test_validate_whatsapp_number_too_short(self, hotel_validator, mock_db):
        """Test validation with too short WhatsApp number"""
        hotel_data = HotelCreate(
            name="Test Hotel",
            whatsapp_number="+123"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("too short" in error for error in result.errors)
    
    def test_validate_whatsapp_number_too_long(self, hotel_validator, mock_db):
        """Test validation with too long WhatsApp number"""
        hotel_data = HotelCreate(
            name="Test Hotel",
            whatsapp_number="+1234567890123456"  # Too long
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("too long" in error for error in result.errors)
    
    def test_validate_green_api_credentials_incomplete(self, hotel_validator, mock_db):
        """Test validation with incomplete Green API credentials"""
        hotel_data = HotelCreate(
            name="Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="test_instance"
            # Missing green_api_token
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("token is required" in error for error in result.errors)
    
    def test_validate_green_api_credentials_too_short(self, hotel_validator, mock_db):
        """Test validation with too short Green API credentials"""
        hotel_data = HotelCreate(
            name="Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="123",  # Too short
            green_api_token="abc"  # Too short
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("instance ID is too short" in error for error in result.errors)
        assert any("token is too short" in error for error in result.errors)
    
    def test_validate_webhook_token_too_short(self, hotel_validator, mock_db):
        """Test validation with too short webhook token"""
        hotel_data = HotelCreate(
            name="Test Hotel",
            whatsapp_number="+1234567890",
            green_api_webhook_token="short"  # Too short
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_create(hotel_data)
        
        assert result.is_valid is False
        assert any("Webhook token is too short" in error for error in result.errors)
    
    def test_validate_whatsapp_number_uniqueness_conflict(self, hotel_validator, mock_db, valid_hotel_data):
        """Test validation when WhatsApp number already exists"""
        # Setup mocks - existing hotel found
        existing_hotel = Mock(spec=Hotel)
        existing_hotel.id = uuid.uuid4()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_hotel
        
        result = hotel_validator.validate_hotel_create(valid_hotel_data)
        
        assert result.is_valid is False
        assert any("already in use" in error for error in result.errors)
    
    def test_validate_hotel_update_success(self, hotel_validator, mock_db):
        """Test successful hotel update validation"""
        hotel_id = uuid.uuid4()
        update_data = HotelUpdate(name="Updated Hotel Name")
        
        # Setup mocks - hotel exists
        existing_hotel = Mock(spec=Hotel)
        existing_hotel.id = hotel_id
        existing_hotel.whatsapp_number = "+1234567890"
        existing_hotel.green_api_instance_id = "test_instance"
        existing_hotel.green_api_token = "test_token"
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_hotel
        
        result = hotel_validator.validate_hotel_update(hotel_id, update_data)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_hotel_update_not_found(self, hotel_validator, mock_db):
        """Test hotel update validation when hotel not found"""
        hotel_id = uuid.uuid4()
        update_data = HotelUpdate(name="Updated Hotel Name")
        
        # Setup mocks - hotel not found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = hotel_validator.validate_hotel_update(hotel_id, update_data)
        
        assert result.is_valid is False
        assert any("not found" in error for error in result.errors)
    
    def test_validate_hotel_configuration_success(self, hotel_validator):
        """Test successful hotel configuration validation"""
        config = {
            "notifications": {
                "email_enabled": True,
                "sms_enabled": False
            },
            "auto_responses": {
                "enabled": True,
                "greeting_message": "Welcome!",
                "business_hours": {
                    "enabled": True,
                    "start": "09:00",
                    "end": "17:00",
                    "timezone": "UTC"
                }
            },
            "sentiment_analysis": {
                "enabled": True,
                "threshold": 0.5,
                "alert_negative": True
            },
            "language": {
                "primary": "en",
                "supported": ["en", "es"]
            }
        }
        
        result = hotel_validator.validate_hotel_configuration(config)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_business_hours_logic_warning(self, hotel_validator):
        """Test business hours logic validation warning"""
        config = {
            "auto_responses": {
                "business_hours": {
                    "enabled": True,
                    "start": "18:00",  # End before start
                    "end": "09:00",
                    "timezone": "UTC"
                }
            }
        }
        
        result = hotel_validator.validate_hotel_configuration(config)
        
        assert result.is_valid is True  # Warning, not error
        assert len(result.warnings) > 0
        assert any("end time should be after start time" in warning for warning in result.warnings)
    
    def test_validate_language_consistency_warning(self, hotel_validator):
        """Test language consistency validation warning"""
        config = {
            "language": {
                "primary": "fr",  # Not in supported list
                "supported": ["en", "es"]
            }
        }
        
        result = hotel_validator.validate_hotel_configuration(config)
        
        assert result.is_valid is True  # Warning, not error
        assert len(result.warnings) > 0
        assert any("Primary language should be included" in warning for warning in result.warnings)
    
    def test_validate_notification_settings_warning(self, hotel_validator):
        """Test notification settings validation warning"""
        config = {
            "notifications": {
                "email_enabled": False,
                "sms_enabled": False,
                "webhook_enabled": False
            }
        }
        
        result = hotel_validator.validate_hotel_configuration(config)
        
        assert result.is_valid is True  # Warning, not error
        assert len(result.warnings) > 0
        assert any("No notification methods are enabled" in warning for warning in result.warnings)
    
    def test_validate_hotel_settings_integration(self, hotel_validator, mock_db):
        """Test hotel settings validation integration"""
        hotel_data = HotelCreate(
            name="Test Hotel",
            whatsapp_number="+1234567890",
            settings={
                "invalid_structure": "should_be_dict"
            }
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch.object(hotel_validator, 'validate_hotel_configuration') as mock_validate_config:
            mock_config_result = ValidationResult()
            mock_config_result.add_error("Invalid configuration")
            mock_validate_config.return_value = mock_config_result
            
            result = hotel_validator.validate_hotel_create(hotel_data)
            
            assert result.is_valid is False
            assert any("Invalid configuration" in error for error in result.errors)


class TestHotelValidatorEdgeCases:
    """Test edge cases for HotelValidator"""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def hotel_validator(self, mock_db):
        return HotelValidator(mock_db)

    def test_validate_hotel_name_with_special_characters(self, hotel_validator, mock_db):
        """Test validation with special characters in hotel name"""
        hotel_data = HotelCreate(
            name="Hotel <script>alert('xss')</script>",
            whatsapp_number="+1234567890"
        )

        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = hotel_validator.validate_hotel_create(hotel_data)

        # Should have warning about special characters
        assert any("special characters" in warning for warning in result.warnings)

    def test_validate_whatsapp_number_without_plus_prefix(self, hotel_validator, mock_db):
        """Test validation with WhatsApp number without + prefix"""
        hotel_data = HotelCreate(
            name="Test Hotel",
            whatsapp_number="1234567890"
        )

        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = hotel_validator.validate_hotel_create(hotel_data)

        # Should have warning about missing + prefix
        assert any("should include country code with + prefix" in warning for warning in result.warnings)

    def test_validate_configuration_with_invalid_sentiment_threshold(self, hotel_validator):
        """Test configuration validation with invalid sentiment threshold"""
        config = {
            "sentiment_analysis": {
                "threshold": 1.5  # Invalid - should be between 0 and 1
            }
        }

        result = hotel_validator.validate_hotel_configuration(config)

        assert result.is_valid is False
        assert len(result.errors) > 0
