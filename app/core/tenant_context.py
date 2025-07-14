"""
Enhanced tenant context utilities for hotel-specific tenant management
"""

import uuid
from typing import Optional, Dict, Any, List
from contextvars import ContextVar
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import structlog

from app.models.hotel import Hotel
from app.core.logging import get_logger

logger = get_logger(__name__)

# Context variables for tenant management
current_hotel_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar('current_hotel_context', default=None)
current_tenant_permissions: ContextVar[Optional[Dict[str, Any]]] = ContextVar('current_tenant_permissions', default=None)


class HotelTenantContext:
    """Enhanced tenant context management for hotels"""
    
    @staticmethod
    def set_hotel_context(
        hotel_id: uuid.UUID,
        hotel_name: str,
        is_active: bool = True,
        permissions: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Set hotel context for the current request
        
        Args:
            hotel_id: Hotel UUID
            hotel_name: Hotel name
            is_active: Whether hotel is active
            permissions: Optional permissions dictionary
        """
        context = {
            "hotel_id": hotel_id,
            "hotel_name": hotel_name,
            "is_active": is_active,
            "set_at": structlog.get_logger().info.__globals__.get('datetime', __import__('datetime')).datetime.utcnow().isoformat()
        }
        
        current_hotel_context.set(context)
        
        if permissions:
            current_tenant_permissions.set(permissions)
        
        logger.debug(
            "Hotel context set",
            hotel_id=str(hotel_id),
            hotel_name=hotel_name,
            is_active=is_active
        )
    
    @staticmethod
    def get_hotel_context() -> Optional[Dict[str, Any]]:
        """
        Get current hotel context
        
        Returns:
            Optional[Dict[str, Any]]: Hotel context or None
        """
        return current_hotel_context.get()
    
    @staticmethod
    def get_current_hotel_id() -> Optional[uuid.UUID]:
        """
        Get current hotel ID from context
        
        Returns:
            Optional[uuid.UUID]: Hotel ID or None
        """
        context = current_hotel_context.get()
        if context:
            return context.get("hotel_id")
        return None
    
    @staticmethod
    def get_current_hotel_name() -> Optional[str]:
        """
        Get current hotel name from context
        
        Returns:
            Optional[str]: Hotel name or None
        """
        context = current_hotel_context.get()
        if context:
            return context.get("hotel_name")
        return None
    
    @staticmethod
    def is_hotel_active() -> bool:
        """
        Check if current hotel is active
        
        Returns:
            bool: True if hotel is active, False otherwise
        """
        context = current_hotel_context.get()
        if context:
            return context.get("is_active", False)
        return False
    
    @staticmethod
    def clear_hotel_context() -> None:
        """Clear hotel context"""
        current_hotel_context.set(None)
        current_tenant_permissions.set(None)
        logger.debug("Hotel context cleared")
    
    @staticmethod
    def require_hotel_context() -> Dict[str, Any]:
        """
        Require hotel context to be set
        
        Returns:
            Dict[str, Any]: Hotel context
            
        Raises:
            ValueError: If no hotel context is set
        """
        context = current_hotel_context.get()
        if not context:
            raise ValueError("No hotel context set")
        return context
    
    @staticmethod
    def require_active_hotel() -> Dict[str, Any]:
        """
        Require active hotel context
        
        Returns:
            Dict[str, Any]: Hotel context
            
        Raises:
            ValueError: If no hotel context or hotel is inactive
        """
        context = HotelTenantContext.require_hotel_context()
        if not context.get("is_active", False):
            raise ValueError("Hotel is not active")
        return context


class HotelTenantManager:
    """Enhanced tenant manager for hotel-specific operations"""
    
    @staticmethod
    def load_hotel_context(db: Session, hotel_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Load hotel context from database
        
        Args:
            db: Database session
            hotel_id: Hotel UUID
            
        Returns:
            Optional[Dict[str, Any]]: Hotel context or None
        """
        try:
            hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
            
            if not hotel:
                logger.warning("Hotel not found for context loading", hotel_id=str(hotel_id))
                return None
            
            context = {
                "hotel_id": hotel.id,
                "hotel_name": hotel.name,
                "is_active": hotel.is_active,
                "whatsapp_number": hotel.whatsapp_number,
                "has_green_api_credentials": hotel.has_green_api_credentials,
                "is_operational": hotel.is_operational,
                "settings": hotel.settings,
                "created_at": hotel.created_at.isoformat() if hotel.created_at else None,
                "updated_at": hotel.updated_at.isoformat() if hotel.updated_at else None
            }
            
            logger.debug(
                "Hotel context loaded from database",
                hotel_id=str(hotel_id),
                hotel_name=hotel.name,
                is_active=hotel.is_active
            )
            
            return context
            
        except SQLAlchemyError as e:
            logger.error(
                "Failed to load hotel context",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            return None
    
    @staticmethod
    def set_database_hotel_context(db: Session, hotel_id: uuid.UUID) -> bool:
        """
        Set hotel context in database session for RLS
        
        Args:
            db: Database session
            hotel_id: Hotel UUID
            
        Returns:
            bool: True if successful
        """
        try:
            # Set the hotel context in PostgreSQL session for RLS
            db.execute(
                text("SELECT set_config('app.current_hotel_id', :hotel_id, true)"),
                {"hotel_id": str(hotel_id)}
            )
            
            # Also set as tenant ID for compatibility
            db.execute(
                text("SELECT set_config('app.current_tenant_id', :hotel_id, true)"),
                {"hotel_id": str(hotel_id)}
            )
            
            logger.debug(
                "Database hotel context set",
                hotel_id=str(hotel_id)
            )
            
            return True
            
        except SQLAlchemyError as e:
            logger.error(
                "Failed to set database hotel context",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            return False
    
    @staticmethod
    def clear_database_hotel_context(db: Session) -> bool:
        """
        Clear hotel context from database session
        
        Args:
            db: Database session
            
        Returns:
            bool: True if successful
        """
        try:
            db.execute(text("SELECT set_config('app.current_hotel_id', '', true)"))
            db.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
            
            logger.debug("Database hotel context cleared")
            return True
            
        except SQLAlchemyError as e:
            logger.error("Failed to clear database hotel context", error=str(e))
            return False
    
    @staticmethod
    def get_hotel_permissions(hotel_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get permissions for hotel based on context
        
        Args:
            hotel_context: Hotel context dictionary
            
        Returns:
            Dict[str, Any]: Permissions dictionary
        """
        permissions = {
            "can_send_messages": hotel_context.get("is_operational", False),
            "can_receive_messages": hotel_context.get("is_active", False),
            "can_modify_settings": hotel_context.get("is_active", False),
            "can_view_analytics": True,
            "can_export_data": hotel_context.get("is_active", False),
            "has_whatsapp_integration": hotel_context.get("has_green_api_credentials", False)
        }
        
        # Additional permissions based on hotel settings
        settings = hotel_context.get("settings", {})
        
        # Check if sentiment analysis is enabled
        sentiment_settings = settings.get("sentiment_analysis", {})
        permissions["can_view_sentiment"] = sentiment_settings.get("enabled", True)
        
        # Check if notifications are configured
        notification_settings = settings.get("notifications", {})
        permissions["has_email_notifications"] = notification_settings.get("email_enabled", True)
        permissions["has_sms_notifications"] = notification_settings.get("sms_enabled", False)
        permissions["has_webhook_notifications"] = notification_settings.get("webhook_enabled", False)
        
        return permissions
    
    @staticmethod
    def validate_hotel_access(
        hotel_context: Dict[str, Any],
        required_permissions: List[str]
    ) -> bool:
        """
        Validate if hotel has required permissions
        
        Args:
            hotel_context: Hotel context dictionary
            required_permissions: List of required permission keys
            
        Returns:
            bool: True if hotel has all required permissions
        """
        permissions = HotelTenantManager.get_hotel_permissions(hotel_context)
        
        for permission in required_permissions:
            if not permissions.get(permission, False):
                logger.warning(
                    "Hotel access denied - missing permission",
                    hotel_id=str(hotel_context.get("hotel_id")),
                    missing_permission=permission
                )
                return False
        
        return True


class HotelTenantFilter:
    """Utility for creating hotel-specific database filters"""
    
    @staticmethod
    def get_hotel_filter(hotel_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """
        Get filter for hotel-specific queries
        
        Args:
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            Dict[str, Any]: Filter dictionary
        """
        if hotel_id is None:
            hotel_id = HotelTenantContext.get_current_hotel_id()
        
        if hotel_id is None:
            raise ValueError("No hotel ID provided and no hotel context set")
        
        return {"hotel_id": hotel_id}
    
    @staticmethod
    def apply_hotel_filter(query, model_class, hotel_id: Optional[uuid.UUID] = None):
        """
        Apply hotel filter to SQLAlchemy query
        
        Args:
            query: SQLAlchemy query object
            model_class: Model class to filter
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            Filtered query object
        """
        if hotel_id is None:
            hotel_id = HotelTenantContext.get_current_hotel_id()
        
        if hotel_id is None:
            raise ValueError("No hotel ID provided and no hotel context set")
        
        # Check if model has hotel_id attribute
        if hasattr(model_class, 'hotel_id'):
            return query.filter(model_class.hotel_id == hotel_id)
        else:
            logger.warning(
                "Model does not have hotel_id attribute",
                model_class=model_class.__name__
            )
            return query


# Decorator for requiring hotel context
def require_hotel_context(func):
    """
    Decorator to require hotel context for function execution
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    def wrapper(*args, **kwargs):
        HotelTenantContext.require_hotel_context()
        return func(*args, **kwargs)
    
    return wrapper


def require_active_hotel(func):
    """
    Decorator to require active hotel context for function execution
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    def wrapper(*args, **kwargs):
        HotelTenantContext.require_active_hotel()
        return func(*args, **kwargs)
    
    return wrapper


def require_hotel_permissions(permissions: List[str]):
    """
    Decorator to require specific hotel permissions
    
    Args:
        permissions: List of required permissions
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            context = HotelTenantContext.require_hotel_context()
            if not HotelTenantManager.validate_hotel_access(context, permissions):
                raise PermissionError(f"Hotel does not have required permissions: {permissions}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Convenience functions
def get_current_hotel_id() -> Optional[uuid.UUID]:
    """Get current hotel ID from context"""
    return HotelTenantContext.get_current_hotel_id()


def get_current_hotel_name() -> Optional[str]:
    """Get current hotel name from context"""
    return HotelTenantContext.get_current_hotel_name()


def is_current_hotel_active() -> bool:
    """Check if current hotel is active"""
    return HotelTenantContext.is_hotel_active()


def get_hotel_filter(hotel_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
    """Get filter for hotel-specific queries"""
    return HotelTenantFilter.get_hotel_filter(hotel_id)
