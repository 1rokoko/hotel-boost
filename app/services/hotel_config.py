"""
Hotel configuration service for WhatsApp Hotel Bot application
"""

import uuid
from typing import Dict, Any, Optional, List, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog
from datetime import datetime

from app.models.hotel import Hotel
from app.services.hotel_service import HotelService, HotelServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class HotelConfigError(Exception):
    """Base exception for hotel configuration errors"""
    pass


class InvalidConfigurationError(HotelConfigError):
    """Raised when configuration is invalid"""
    pass


class ConfigurationNotFoundError(HotelConfigError):
    """Raised when configuration key is not found"""
    pass


class HotelConfigService:
    """Service for managing hotel configuration and settings"""
    
    def __init__(self, db: Session):
        """
        Initialize hotel configuration service
        
        Args:
            db: Database session
        """
        self.db = db
        self.hotel_service = HotelService(db)
        self.logger = logger.bind(service="hotel_config_service")
    
    def get_hotel_config(self, hotel_id: uuid.UUID) -> Dict[str, Any]:
        """
        Get complete hotel configuration
        
        Args:
            hotel_id: Hotel UUID
            
        Returns:
            Dict[str, Any]: Hotel configuration
            
        Raises:
            HotelConfigError: If hotel not found or config retrieval fails
        """
        try:
            hotel = self.hotel_service.get_hotel(hotel_id)
            if not hotel:
                raise HotelConfigError(f"Hotel {hotel_id} not found")
            
            # Return settings with defaults merged
            config = self._merge_with_defaults(hotel.settings)
            
            self.logger.debug(
                "Hotel configuration retrieved",
                hotel_id=str(hotel_id),
                config_keys=list(config.keys())
            )
            
            return config
            
        except Exception as e:
            self.logger.error(
                "Failed to get hotel configuration",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise HotelConfigError(f"Failed to get hotel configuration: {str(e)}")
    
    def get_config_value(
        self,
        hotel_id: uuid.UUID,
        key_path: str,
        default: Any = None
    ) -> Any:
        """
        Get specific configuration value by key path
        
        Args:
            hotel_id: Hotel UUID
            key_path: Dot-separated key path (e.g., 'notifications.email_enabled')
            default: Default value if key not found
            
        Returns:
            Any: Configuration value
            
        Raises:
            HotelConfigError: If hotel not found
        """
        try:
            config = self.get_hotel_config(hotel_id)
            
            # Navigate through nested keys
            value = config
            for key in key_path.split('.'):
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            
            self.logger.debug(
                "Configuration value retrieved",
                hotel_id=str(hotel_id),
                key_path=key_path,
                value_type=type(value).__name__
            )
            
            return value
            
        except HotelConfigError:
            raise
        except Exception as e:
            self.logger.error(
                "Failed to get configuration value",
                hotel_id=str(hotel_id),
                key_path=key_path,
                error=str(e)
            )
            raise HotelConfigError(f"Failed to get configuration value: {str(e)}")
    
    def update_config(
        self,
        hotel_id: uuid.UUID,
        config_updates: Dict[str, Any],
        merge: bool = True
    ) -> Dict[str, Any]:
        """
        Update hotel configuration
        
        Args:
            hotel_id: Hotel UUID
            config_updates: Configuration updates to apply
            merge: Whether to merge with existing config or replace
            
        Returns:
            Dict[str, Any]: Updated configuration
            
        Raises:
            HotelConfigError: If update fails
            InvalidConfigurationError: If configuration is invalid
        """
        try:
            # Validate configuration updates
            self._validate_config(config_updates)
            
            # Get current configuration
            if merge:
                current_config = self.get_hotel_config(hotel_id)
                updated_config = self._deep_merge(current_config, config_updates)
            else:
                updated_config = self._merge_with_defaults(config_updates)
            
            # Update hotel settings
            from app.schemas.hotel import HotelUpdate
            update_data = HotelUpdate(settings=updated_config)
            
            updated_hotel = self.hotel_service.update_hotel(hotel_id, update_data)
            if not updated_hotel:
                raise HotelConfigError(f"Hotel {hotel_id} not found")
            
            self.logger.info(
                "Hotel configuration updated",
                hotel_id=str(hotel_id),
                updated_keys=list(config_updates.keys()),
                merge=merge
            )
            
            return updated_config
            
        except InvalidConfigurationError:
            raise
        except HotelConfigError:
            raise
        except Exception as e:
            self.logger.error(
                "Failed to update hotel configuration",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise HotelConfigError(f"Failed to update configuration: {str(e)}")
    
    def set_config_value(
        self,
        hotel_id: uuid.UUID,
        key_path: str,
        value: Any
    ) -> Dict[str, Any]:
        """
        Set specific configuration value by key path
        
        Args:
            hotel_id: Hotel UUID
            key_path: Dot-separated key path (e.g., 'notifications.email_enabled')
            value: Value to set
            
        Returns:
            Dict[str, Any]: Updated configuration
            
        Raises:
            HotelConfigError: If update fails
        """
        try:
            # Build nested update dictionary
            update_dict = {}
            current = update_dict
            keys = key_path.split('.')
            
            for key in keys[:-1]:
                current[key] = {}
                current = current[key]
            
            current[keys[-1]] = value
            
            # Update configuration
            return self.update_config(hotel_id, update_dict, merge=True)
            
        except Exception as e:
            self.logger.error(
                "Failed to set configuration value",
                hotel_id=str(hotel_id),
                key_path=key_path,
                error=str(e)
            )
            raise HotelConfigError(f"Failed to set configuration value: {str(e)}")
    
    def reset_to_defaults(self, hotel_id: uuid.UUID) -> Dict[str, Any]:
        """
        Reset hotel configuration to defaults
        
        Args:
            hotel_id: Hotel UUID
            
        Returns:
            Dict[str, Any]: Default configuration
            
        Raises:
            HotelConfigError: If reset fails
        """
        try:
            default_config = self._get_default_config()
            
            # Update hotel with default configuration
            from app.schemas.hotel import HotelUpdate
            update_data = HotelUpdate(settings=default_config)
            
            updated_hotel = self.hotel_service.update_hotel(hotel_id, update_data)
            if not updated_hotel:
                raise HotelConfigError(f"Hotel {hotel_id} not found")
            
            self.logger.info(
                "Hotel configuration reset to defaults",
                hotel_id=str(hotel_id)
            )
            
            return default_config
            
        except Exception as e:
            self.logger.error(
                "Failed to reset hotel configuration",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise HotelConfigError(f"Failed to reset configuration: {str(e)}")
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate configuration structure and values
        
        Args:
            config: Configuration to validate
            
        Raises:
            InvalidConfigurationError: If configuration is invalid
        """
        try:
            # Validate notifications settings
            if 'notifications' in config:
                notifications = config['notifications']
                if not isinstance(notifications, dict):
                    raise InvalidConfigurationError("notifications must be a dictionary")
                
                # Validate boolean fields
                for field in ['email_enabled', 'sms_enabled', 'webhook_enabled']:
                    if field in notifications and not isinstance(notifications[field], bool):
                        raise InvalidConfigurationError(f"notifications.{field} must be boolean")
            
            # Validate auto_responses settings
            if 'auto_responses' in config:
                auto_responses = config['auto_responses']
                if not isinstance(auto_responses, dict):
                    raise InvalidConfigurationError("auto_responses must be a dictionary")
                
                if 'enabled' in auto_responses and not isinstance(auto_responses['enabled'], bool):
                    raise InvalidConfigurationError("auto_responses.enabled must be boolean")
                
                # Validate business hours
                if 'business_hours' in auto_responses:
                    bh = auto_responses['business_hours']
                    if not isinstance(bh, dict):
                        raise InvalidConfigurationError("business_hours must be a dictionary")
                    
                    if 'enabled' in bh and not isinstance(bh['enabled'], bool):
                        raise InvalidConfigurationError("business_hours.enabled must be boolean")
            
            # Validate sentiment analysis settings
            if 'sentiment_analysis' in config:
                sentiment = config['sentiment_analysis']
                if not isinstance(sentiment, dict):
                    raise InvalidConfigurationError("sentiment_analysis must be a dictionary")
                
                if 'enabled' in sentiment and not isinstance(sentiment['enabled'], bool):
                    raise InvalidConfigurationError("sentiment_analysis.enabled must be boolean")
                
                if 'threshold' in sentiment:
                    threshold = sentiment['threshold']
                    if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
                        raise InvalidConfigurationError("sentiment_analysis.threshold must be between 0 and 1")
            
            # Validate language settings
            if 'language' in config:
                language = config['language']
                if not isinstance(language, dict):
                    raise InvalidConfigurationError("language must be a dictionary")
                
                if 'supported' in language and not isinstance(language['supported'], list):
                    raise InvalidConfigurationError("language.supported must be a list")
            
        except InvalidConfigurationError:
            raise
        except Exception as e:
            raise InvalidConfigurationError(f"Configuration validation failed: {str(e)}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default hotel configuration
        
        Returns:
            Dict[str, Any]: Default configuration
        """
        return {
            "notifications": {
                "email_enabled": True,
                "sms_enabled": False,
                "webhook_enabled": False
            },
            "auto_responses": {
                "enabled": True,
                "greeting_message": "Welcome to our hotel! How can we help you today?",
                "business_hours": {
                    "enabled": True,
                    "start": "09:00",
                    "end": "18:00",
                    "timezone": "UTC"
                }
            },
            "sentiment_analysis": {
                "enabled": True,
                "threshold": 0.3,
                "alert_negative": True
            },
            "language": {
                "primary": "en",
                "supported": ["en", "es", "fr"]
            }
        }

    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge configuration with defaults

        Args:
            config: Configuration to merge

        Returns:
            Dict[str, Any]: Merged configuration
        """
        defaults = self._get_default_config()
        return self._deep_merge(defaults, config)

    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries

        Args:
            base: Base dictionary
            updates: Updates to apply

        Returns:
            Dict[str, Any]: Merged dictionary
        """
        result = base.copy()

        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result


# Dependency injection helper
def get_hotel_config_service(db: Session) -> HotelConfigService:
    """
    Get hotel configuration service instance

    Args:
        db: Database session

    Returns:
        HotelConfigService: Hotel configuration service instance
    """
    return HotelConfigService(db)
