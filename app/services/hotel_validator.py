"""
Hotel data validator service for WhatsApp Hotel Bot application
"""

import uuid
import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog
from datetime import datetime

from app.models.hotel import Hotel
from app.schemas.hotel import HotelCreate, HotelUpdate
from app.schemas.hotel_config import HotelConfigurationSchema
from app.core.logging import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Base exception for validation errors"""
    pass


class ValidationResult:
    """Result of validation operation"""
    
    def __init__(self):
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.field_errors: Dict[str, List[str]] = {}
    
    def add_error(self, message: str, field: Optional[str] = None):
        """Add validation error"""
        self.is_valid = False
        self.errors.append(message)
        if field:
            if field not in self.field_errors:
                self.field_errors[field] = []
            self.field_errors[field].append(message)
    
    def add_warning(self, message: str):
        """Add validation warning"""
        self.warnings.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "field_errors": self.field_errors
        }


class HotelValidator:
    """Service for validating hotel data and configurations"""
    
    def __init__(self, db: Session):
        """
        Initialize hotel validator
        
        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger.bind(service="hotel_validator")
    
    def validate_hotel_create(self, hotel_data: HotelCreate) -> ValidationResult:
        """
        Validate hotel creation data
        
        Args:
            hotel_data: Hotel creation data
            
        Returns:
            ValidationResult: Validation result
        """
        result = ValidationResult()
        
        try:
            # Validate basic fields
            self._validate_hotel_name(hotel_data.name, result)
            self._validate_whatsapp_number(hotel_data.whatsapp_number, result)
            
            # Validate Green API credentials if provided
            if hotel_data.green_api_instance_id or hotel_data.green_api_token:
                self._validate_green_api_credentials(
                    hotel_data.green_api_instance_id,
                    hotel_data.green_api_token,
                    result
                )
            
            # Validate webhook token if provided
            if hotel_data.green_api_webhook_token:
                self._validate_webhook_token(hotel_data.green_api_webhook_token, result)
            
            # Validate settings if provided
            if hotel_data.settings:
                self._validate_hotel_settings(hotel_data.settings, result)
            
            # Check for duplicate WhatsApp number
            self._check_whatsapp_number_uniqueness(hotel_data.whatsapp_number, result)
            
            self.logger.debug(
                "Hotel creation data validated",
                is_valid=result.is_valid,
                error_count=len(result.errors),
                warning_count=len(result.warnings)
            )
            
            return result
            
        except Exception as e:
            self.logger.error("Hotel creation validation failed", error=str(e))
            result.add_error(f"Validation failed: {str(e)}")
            return result
    
    def validate_hotel_update(
        self,
        hotel_id: uuid.UUID,
        hotel_data: HotelUpdate
    ) -> ValidationResult:
        """
        Validate hotel update data
        
        Args:
            hotel_id: Hotel UUID
            hotel_data: Hotel update data
            
        Returns:
            ValidationResult: Validation result
        """
        result = ValidationResult()
        
        try:
            # Check if hotel exists
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            if not hotel:
                result.add_error(f"Hotel with ID {hotel_id} not found")
                return result
            
            # Validate fields that are being updated
            if hotel_data.name is not None:
                self._validate_hotel_name(hotel_data.name, result)
            
            if hotel_data.whatsapp_number is not None:
                self._validate_whatsapp_number(hotel_data.whatsapp_number, result)
                # Check uniqueness only if number is changing
                if hotel_data.whatsapp_number != hotel.whatsapp_number:
                    self._check_whatsapp_number_uniqueness(
                        hotel_data.whatsapp_number,
                        result,
                        exclude_hotel_id=hotel_id
                    )
            
            # Validate Green API credentials if being updated
            instance_id = hotel_data.green_api_instance_id
            token = hotel_data.green_api_token
            
            # Use existing values if not being updated
            if instance_id is None:
                instance_id = hotel.green_api_instance_id
            if token is None:
                token = hotel.green_api_token
            
            if instance_id or token:
                self._validate_green_api_credentials(instance_id, token, result)
            
            # Validate webhook token if being updated
            if hotel_data.green_api_webhook_token is not None:
                self._validate_webhook_token(hotel_data.green_api_webhook_token, result)
            
            # Validate settings if being updated
            if hotel_data.settings is not None:
                self._validate_hotel_settings(hotel_data.settings, result)
            
            self.logger.debug(
                "Hotel update data validated",
                hotel_id=str(hotel_id),
                is_valid=result.is_valid,
                error_count=len(result.errors),
                warning_count=len(result.warnings)
            )
            
            return result
            
        except Exception as e:
            self.logger.error("Hotel update validation failed", hotel_id=str(hotel_id), error=str(e))
            result.add_error(f"Validation failed: {str(e)}")
            return result
    
    def validate_hotel_configuration(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate hotel configuration
        
        Args:
            config: Configuration dictionary
            
        Returns:
            ValidationResult: Validation result
        """
        result = ValidationResult()
        
        try:
            # Use Pydantic schema for validation
            HotelConfigurationSchema(**config)
            
            # Additional custom validations
            self._validate_business_hours_logic(config, result)
            self._validate_language_consistency(config, result)
            self._validate_notification_settings(config, result)
            
            self.logger.debug(
                "Hotel configuration validated",
                is_valid=result.is_valid,
                error_count=len(result.errors),
                warning_count=len(result.warnings)
            )
            
            return result
            
        except Exception as e:
            self.logger.error("Hotel configuration validation failed", error=str(e))
            result.add_error(f"Configuration validation failed: {str(e)}")
            return result
    
    def _validate_hotel_name(self, name: str, result: ValidationResult):
        """Validate hotel name"""
        if not name or not name.strip():
            result.add_error("Hotel name cannot be empty", "name")
            return
        
        if len(name.strip()) < 2:
            result.add_error("Hotel name must be at least 2 characters long", "name")
        
        if len(name) > 255:
            result.add_error("Hotel name cannot exceed 255 characters", "name")
        
        # Check for potentially problematic characters
        if re.search(r'[<>"\']', name):
            result.add_warning("Hotel name contains special characters that may cause issues")
    
    def _validate_whatsapp_number(self, number: str, result: ValidationResult):
        """Validate WhatsApp number format"""
        if not number:
            result.add_error("WhatsApp number is required", "whatsapp_number")
            return
        
        # Remove spaces and common separators for validation
        clean_number = re.sub(r'[\s\-\(\)]', '', number)
        
        # Check basic format
        if not re.match(r'^\+?[1-9]\d{1,14}$', clean_number):
            result.add_error(
                "WhatsApp number must be a valid international phone number",
                "whatsapp_number"
            )
            return
        
        # Check length constraints
        if len(clean_number.lstrip('+')) < 7:
            result.add_error("WhatsApp number is too short", "whatsapp_number")
        
        if len(clean_number.lstrip('+')) > 15:
            result.add_error("WhatsApp number is too long", "whatsapp_number")
        
        # Warn about common issues
        if not clean_number.startswith('+'):
            result.add_warning("WhatsApp number should include country code with + prefix")
    
    def _validate_green_api_credentials(
        self,
        instance_id: Optional[str],
        token: Optional[str],
        result: ValidationResult
    ):
        """Validate Green API credentials"""
        if instance_id and not token:
            result.add_error(
                "Green API token is required when instance ID is provided",
                "green_api_token"
            )
        
        if token and not instance_id:
            result.add_error(
                "Green API instance ID is required when token is provided",
                "green_api_instance_id"
            )
        
        if instance_id:
            if len(instance_id) < 5:
                result.add_error("Green API instance ID is too short", "green_api_instance_id")
            
            if len(instance_id) > 50:
                result.add_error("Green API instance ID is too long", "green_api_instance_id")
        
        if token:
            if len(token) < 10:
                result.add_error("Green API token is too short", "green_api_token")
            
            if len(token) > 255:
                result.add_error("Green API token is too long", "green_api_token")
    
    def _validate_webhook_token(self, webhook_token: str, result: ValidationResult):
        """Validate webhook token"""
        if len(webhook_token) < 8:
            result.add_error("Webhook token is too short (minimum 8 characters)", "green_api_webhook_token")
        
        if len(webhook_token) > 255:
            result.add_error("Webhook token is too long (maximum 255 characters)", "green_api_webhook_token")
    
    def _validate_hotel_settings(self, settings: Dict[str, Any], result: ValidationResult):
        """Validate hotel settings"""
        try:
            # Use configuration schema for validation
            config_result = self.validate_hotel_configuration(settings)
            
            # Merge results
            result.errors.extend(config_result.errors)
            result.warnings.extend(config_result.warnings)
            result.field_errors.update(config_result.field_errors)
            
            if not config_result.is_valid:
                result.is_valid = False
                
        except Exception as e:
            result.add_error(f"Settings validation failed: {str(e)}", "settings")
    
    def _check_whatsapp_number_uniqueness(
        self,
        whatsapp_number: str,
        result: ValidationResult,
        exclude_hotel_id: Optional[uuid.UUID] = None
    ):
        """Check if WhatsApp number is unique"""
        try:
            query = self.db.query(Hotel).filter(Hotel.whatsapp_number == whatsapp_number)
            
            if exclude_hotel_id:
                query = query.filter(Hotel.id != exclude_hotel_id)
            
            existing_hotel = query.first()
            
            if existing_hotel:
                result.add_error(
                    f"WhatsApp number {whatsapp_number} is already in use by another hotel",
                    "whatsapp_number"
                )
                
        except SQLAlchemyError as e:
            self.logger.error("Failed to check WhatsApp number uniqueness", error=str(e))
            result.add_error("Failed to verify WhatsApp number uniqueness")
    
    def _validate_business_hours_logic(self, config: Dict[str, Any], result: ValidationResult):
        """Validate business hours logic"""
        auto_responses = config.get("auto_responses", {})
        business_hours = auto_responses.get("business_hours", {})
        
        if business_hours.get("enabled", True):
            start_time = business_hours.get("start", "09:00")
            end_time = business_hours.get("end", "18:00")
            
            try:
                start_hour, start_min = map(int, start_time.split(':'))
                end_hour, end_min = map(int, end_time.split(':'))
                
                start_minutes = start_hour * 60 + start_min
                end_minutes = end_hour * 60 + end_min
                
                if start_minutes >= end_minutes:
                    result.add_warning("Business hours end time should be after start time")
                    
            except (ValueError, AttributeError):
                result.add_error("Invalid business hours time format")
    
    def _validate_language_consistency(self, config: Dict[str, Any], result: ValidationResult):
        """Validate language settings consistency"""
        language = config.get("language", {})
        primary = language.get("primary", "en")
        supported = language.get("supported", ["en"])
        
        if primary not in supported:
            result.add_warning("Primary language should be included in supported languages list")
    
    def _validate_notification_settings(self, config: Dict[str, Any], result: ValidationResult):
        """Validate notification settings"""
        notifications = config.get("notifications", {})
        
        # Check if at least one notification method is enabled
        email_enabled = notifications.get("email_enabled", True)
        sms_enabled = notifications.get("sms_enabled", False)
        webhook_enabled = notifications.get("webhook_enabled", False)
        
        if not any([email_enabled, sms_enabled, webhook_enabled]):
            result.add_warning("No notification methods are enabled - staff may miss important alerts")


# Dependency injection helper
def get_hotel_validator(db: Session) -> HotelValidator:
    """
    Get hotel validator instance
    
    Args:
        db: Database session
        
    Returns:
        HotelValidator: Hotel validator instance
    """
    return HotelValidator(db)
