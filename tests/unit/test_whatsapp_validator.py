"""
Unit tests for WhatsApp validator utility
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import aiohttp

from app.utils.whatsapp_validator import (
    WhatsAppValidator,
    WhatsAppValidationResult,
    ValidationStatus,
    validate_whatsapp_number,
    check_whatsapp_availability
)


class TestWhatsAppValidationResult:
    """Test cases for WhatsAppValidationResult"""
    
    def test_validation_result_initialization(self):
        """Test WhatsAppValidationResult initialization"""
        result = WhatsAppValidationResult(
            number="+1234567890",
            formatted_number="+1234567890",
            status=ValidationStatus.VALID
        )
        
        assert result.number == "+1234567890"
        assert result.formatted_number == "+1234567890"
        assert result.status == ValidationStatus.VALID
        assert result.errors == []
        assert result.warnings == []
    
    def test_is_valid_property(self):
        """Test is_valid property"""
        valid_result = WhatsAppValidationResult(
            number="+1234567890",
            formatted_number="+1234567890",
            status=ValidationStatus.VALID
        )
        
        invalid_result = WhatsAppValidationResult(
            number="invalid",
            formatted_number="",
            status=ValidationStatus.INVALID
        )
        
        assert valid_result.is_valid is True
        assert invalid_result.is_valid is False
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        result = WhatsAppValidationResult(
            number="+1234567890",
            formatted_number="+1234567890",
            status=ValidationStatus.VALID,
            country_code="1",
            country_name="US/CA"
        )
        
        dict_result = result.to_dict()
        
        assert dict_result["number"] == "+1234567890"
        assert dict_result["formatted_number"] == "+1234567890"
        assert dict_result["status"] == "valid"
        assert dict_result["country_code"] == "1"
        assert dict_result["country_name"] == "US/CA"
        assert dict_result["is_valid"] is True


class TestWhatsAppValidator:
    """Test cases for WhatsAppValidator"""
    
    @pytest.fixture
    def validator(self):
        """WhatsApp validator instance"""
        return WhatsAppValidator()
    
    def test_clean_number_basic(self, validator):
        """Test basic number cleaning"""
        # Test with spaces and dashes
        result = validator._clean_number("+1 (234) 567-890")
        assert result == "+1234567890"
        
        # Test with multiple plus signs
        result = validator._clean_number("++1234567890")
        assert result == "+1234567890"
        
        # Test without plus
        result = validator._clean_number("1234567890")
        assert result == "1234567890"
    
    def test_validate_basic_format(self, validator):
        """Test basic format validation"""
        # Valid formats
        assert validator._validate_basic_format("+1234567890") is True
        assert validator._validate_basic_format("1234567890") is True
        
        # Invalid formats
        assert validator._validate_basic_format("+0234567890") is False  # Starts with 0
        assert validator._validate_basic_format("abc123") is False
        assert validator._validate_basic_format("") is False
    
    def test_validate_length(self, validator):
        """Test length validation"""
        # Valid lengths
        assert validator._validate_length("+1234567") is True  # 7 digits
        assert validator._validate_length("+123456789012345") is True  # 15 digits
        
        # Invalid lengths
        assert validator._validate_length("+123456") is False  # 6 digits (too short)
        assert validator._validate_length("+1234567890123456") is False  # 16 digits (too long)
    
    def test_format_number(self, validator):
        """Test number formatting"""
        # Already has plus
        assert validator._format_number("+1234567890") == "+1234567890"
        
        # Missing plus
        assert validator._format_number("1234567890") == "+1234567890"
    
    def test_extract_country_code(self, validator):
        """Test country code extraction"""
        # US/Canada
        assert validator._extract_country_code("+1234567890") == "1"
        
        # Germany
        assert validator._extract_country_code("+49123456789") == "49"
        
        # Unknown country code
        assert validator._extract_country_code("+999123456789") is None
    
    def test_has_sequential_digits(self, validator):
        """Test sequential digits detection"""
        # Has sequential digits
        assert validator._has_sequential_digits("1234567890") is True
        assert validator._has_sequential_digits("9876543210") is True
        
        # No sequential digits
        assert validator._has_sequential_digits("1357924680") is False
        assert validator._has_sequential_digits("123") is False  # Too short
    
    def test_validate_format_success(self, validator):
        """Test successful format validation"""
        result = validator.validate_format("+1234567890")
        
        assert result.is_valid is True
        assert result.status == ValidationStatus.VALID
        assert result.formatted_number == "+1234567890"
        assert result.country_code == "1"
        assert result.country_name == "US/CA"
        assert len(result.errors) == 0
    
    def test_validate_format_invalid_number(self, validator):
        """Test format validation with invalid number"""
        result = validator.validate_format("invalid_number")
        
        assert result.is_valid is False
        assert result.status == ValidationStatus.INVALID
        assert len(result.errors) > 0
        assert any("Invalid phone number format" in error for error in result.errors)
    
    def test_validate_format_empty_number(self, validator):
        """Test format validation with empty number"""
        result = validator.validate_format("")
        
        assert result.is_valid is False
        assert result.status == ValidationStatus.INVALID
        assert any("empty or invalid" in error for error in result.errors)
    
    def test_validate_format_too_short(self, validator):
        """Test format validation with too short number"""
        result = validator.validate_format("+123456")
        
        assert result.is_valid is False
        assert result.status == ValidationStatus.INVALID
        assert any("length is invalid" in error for error in result.errors)
    
    def test_validate_format_too_long(self, validator):
        """Test format validation with too long number"""
        result = validator.validate_format("+1234567890123456")
        
        assert result.is_valid is False
        assert result.status == ValidationStatus.INVALID
        assert any("length is invalid" in error for error in result.errors)
    
    def test_validate_format_warnings(self, validator):
        """Test format validation warnings"""
        # Test repeated digits warning
        result = validator.validate_format("+1111111111")
        assert any("repeated digits" in warning for warning in result.warnings)
        
        # Test sequential digits warning
        result = validator.validate_format("+1234567890")
        assert any("sequential digits" in warning for warning in result.warnings)
        
        # Test test number warning
        result = validator.validate_format("+1234567890")
        assert any("test number" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_check_whatsapp_availability_success(self, validator):
        """Test successful WhatsApp availability check"""
        mock_response_data = {"existsWhatsapp": True}
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await validator._check_whatsapp_availability(
                "+1234567890",
                "test_instance",
                "test_token"
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_whatsapp_availability_not_found(self, validator):
        """Test WhatsApp availability check when number not found"""
        mock_response_data = {"existsWhatsapp": False}
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await validator._check_whatsapp_availability(
                "+1234567890",
                "test_instance",
                "test_token"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_check_whatsapp_availability_api_error(self, validator):
        """Test WhatsApp availability check with API error"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 500
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            result = await validator._check_whatsapp_availability(
                "+1234567890",
                "test_instance",
                "test_token"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_whatsapp_availability_with_credentials(self, validator):
        """Test WhatsApp availability validation with credentials"""
        with patch.object(validator, '_check_whatsapp_availability', return_value=True) as mock_check:
            result = await validator.validate_whatsapp_availability(
                "+1234567890",
                "test_instance",
                "test_token"
            )
            
            assert result.is_valid is True
            assert result.is_whatsapp is True
            mock_check.assert_called_once_with("+1234567890", "test_instance", "test_token")
    
    @pytest.mark.asyncio
    async def test_validate_whatsapp_availability_without_credentials(self, validator):
        """Test WhatsApp availability validation without credentials"""
        result = await validator.validate_whatsapp_availability("+1234567890")
        
        assert result.is_valid is True
        assert result.is_whatsapp is None  # Not checked without credentials
    
    def test_batch_validate_format(self, validator):
        """Test batch format validation"""
        numbers = ["+1234567890", "invalid_number", "+49123456789"]
        
        results = validator.batch_validate_format(numbers)
        
        assert len(results) == 3
        assert results[0].is_valid is True
        assert results[1].is_valid is False
        assert results[2].is_valid is True
    
    def test_validate_format_exception_handling(self, validator):
        """Test exception handling in format validation"""
        with patch.object(validator, '_clean_number', side_effect=Exception("Test error")):
            result = validator.validate_format("+1234567890")
            
            assert result.status == ValidationStatus.ERROR
            assert any("Validation error" in error for error in result.errors)


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_validate_whatsapp_number_function(self):
        """Test validate_whatsapp_number convenience function"""
        with patch('app.utils.whatsapp_validator.get_whatsapp_validator') as mock_get_validator:
            mock_validator = Mock()
            mock_result = WhatsAppValidationResult(
                number="+1234567890",
                formatted_number="+1234567890",
                status=ValidationStatus.VALID
            )
            mock_validator.validate_format.return_value = mock_result
            mock_get_validator.return_value = mock_validator
            
            result = validate_whatsapp_number("+1234567890")
            
            assert result.is_valid is True
            mock_validator.validate_format.assert_called_once_with("+1234567890")
    
    @pytest.mark.asyncio
    async def test_check_whatsapp_availability_function(self):
        """Test check_whatsapp_availability convenience function"""
        with patch('app.utils.whatsapp_validator.get_whatsapp_validator') as mock_get_validator:
            mock_validator = Mock()
            mock_result = WhatsAppValidationResult(
                number="+1234567890",
                formatted_number="+1234567890",
                status=ValidationStatus.VALID,
                is_whatsapp=True
            )
            mock_validator.validate_whatsapp_availability = AsyncMock(return_value=mock_result)
            mock_get_validator.return_value = mock_validator
            
            result = await check_whatsapp_availability(
                "+1234567890",
                "test_instance",
                "test_token"
            )
            
            assert result.is_valid is True
            assert result.is_whatsapp is True
            mock_validator.validate_whatsapp_availability.assert_called_once_with(
                "+1234567890",
                "test_instance",
                "test_token"
            )
