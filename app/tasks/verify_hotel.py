"""
Celery tasks for hotel verification in WhatsApp Hotel Bot application
"""

import uuid
from typing import Dict, Any, Optional
from celery import Celery
from sqlalchemy.orm import Session
import structlog
import asyncio
from datetime import datetime

from app.database import get_db_session
from app.models.hotel import Hotel
from app.services.hotel_service import HotelService
from app.services.hotel_validator import HotelValidator
from app.utils.whatsapp_validator import get_whatsapp_validator
from app.services.green_api_service import GreenAPIService
from app.core.logging import get_logger
from app.core.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def verify_hotel_whatsapp_number(self, hotel_id: str, correlation_id: Optional[str] = None):
    """
    Verify hotel's WhatsApp number availability
    
    Args:
        hotel_id: Hotel UUID as string
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        Dict with verification results
    """
    task_logger = logger.bind(
        task="verify_hotel_whatsapp_number",
        hotel_id=hotel_id,
        correlation_id=correlation_id,
        task_id=self.request.id
    )
    
    try:
        with get_db_session() as db:
            # Get hotel
            hotel_service = HotelService(db)
            hotel = hotel_service.get_hotel(uuid.UUID(hotel_id))
            
            if not hotel:
                task_logger.error("Hotel not found")
                return {
                    "success": False,
                    "error": "Hotel not found",
                    "hotel_id": hotel_id
                }
            
            # Validate WhatsApp number
            validator = get_whatsapp_validator()
            
            # Run async validation in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                validation_result = loop.run_until_complete(
                    validator.validate_whatsapp_availability(
                        hotel.whatsapp_number,
                        hotel.green_api_instance_id,
                        hotel.green_api_token
                    )
                )
            finally:
                loop.close()
            
            # Update hotel with validation results
            verification_data = {
                "whatsapp_verification": {
                    "verified_at": datetime.utcnow().isoformat(),
                    "is_valid": validation_result.is_valid,
                    "is_whatsapp": validation_result.is_whatsapp,
                    "formatted_number": validation_result.formatted_number,
                    "country_code": validation_result.country_code,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "task_id": self.request.id
                }
            }
            
            # Merge with existing settings
            current_settings = hotel.settings or {}
            updated_settings = {**current_settings, **verification_data}
            
            # Update hotel
            from app.schemas.hotel import HotelUpdate
            update_data = HotelUpdate(settings=updated_settings)
            hotel_service.update_hotel(uuid.UUID(hotel_id), update_data)
            
            task_logger.info(
                "WhatsApp number verification completed",
                is_valid=validation_result.is_valid,
                is_whatsapp=validation_result.is_whatsapp,
                formatted_number=validation_result.formatted_number
            )
            
            return {
                "success": True,
                "hotel_id": hotel_id,
                "validation_result": validation_result.to_dict(),
                "verification_data": verification_data
            }
            
    except Exception as e:
        task_logger.error("WhatsApp number verification failed", error=str(e))
        
        # Retry on certain errors
        if "timeout" in str(e).lower() or "connection" in str(e).lower():
            if self.request.retries < self.max_retries:
                task_logger.info("Retrying WhatsApp verification", retry_count=self.request.retries + 1)
                raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return {
            "success": False,
            "error": str(e),
            "hotel_id": hotel_id,
            "task_id": self.request.id
        }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def verify_hotel_green_api_credentials(self, hotel_id: str, correlation_id: Optional[str] = None):
    """
    Verify hotel's Green API credentials
    
    Args:
        hotel_id: Hotel UUID as string
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        Dict with verification results
    """
    task_logger = logger.bind(
        task="verify_hotel_green_api_credentials",
        hotel_id=hotel_id,
        correlation_id=correlation_id,
        task_id=self.request.id
    )
    
    try:
        with get_db_session() as db:
            # Get hotel
            hotel_service = HotelService(db)
            hotel = hotel_service.get_hotel(uuid.UUID(hotel_id))
            
            if not hotel:
                task_logger.error("Hotel not found")
                return {
                    "success": False,
                    "error": "Hotel not found",
                    "hotel_id": hotel_id
                }
            
            # Check if hotel has Green API credentials
            if not hotel.green_api_instance_id or not hotel.green_api_token:
                task_logger.warning("Hotel has no Green API credentials")
                return {
                    "success": False,
                    "error": "No Green API credentials configured",
                    "hotel_id": hotel_id
                }
            
            # Test Green API credentials
            green_api_service = GreenAPIService(
                instance_id=hotel.green_api_instance_id,
                token=hotel.green_api_token
            )
            
            # Run async credential test in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Test by getting instance state
                state_result = loop.run_until_complete(
                    green_api_service.get_state_instance()
                )
                
                is_valid = state_result.get("stateInstance") in ["authorized", "got qr code"]
                
                # Get additional instance info if authorized
                instance_info = None
                if is_valid:
                    try:
                        instance_info = loop.run_until_complete(
                            green_api_service.get_status_instance()
                        )
                    except Exception as e:
                        task_logger.warning("Could not get instance info", error=str(e))
                
            finally:
                loop.close()
            
            # Update hotel with verification results
            verification_data = {
                "green_api_verification": {
                    "verified_at": datetime.utcnow().isoformat(),
                    "is_valid": is_valid,
                    "state": state_result.get("stateInstance"),
                    "instance_info": instance_info,
                    "task_id": self.request.id
                }
            }
            
            # Merge with existing settings
            current_settings = hotel.settings or {}
            updated_settings = {**current_settings, **verification_data}
            
            # Update hotel
            from app.schemas.hotel import HotelUpdate
            update_data = HotelUpdate(settings=updated_settings)
            hotel_service.update_hotel(uuid.UUID(hotel_id), update_data)
            
            task_logger.info(
                "Green API credentials verification completed",
                is_valid=is_valid,
                state=state_result.get("stateInstance")
            )
            
            return {
                "success": True,
                "hotel_id": hotel_id,
                "is_valid": is_valid,
                "state": state_result.get("stateInstance"),
                "instance_info": instance_info,
                "verification_data": verification_data
            }
            
    except Exception as e:
        task_logger.error("Green API credentials verification failed", error=str(e))
        
        # Retry on certain errors
        if "timeout" in str(e).lower() or "connection" in str(e).lower():
            if self.request.retries < self.max_retries:
                task_logger.info("Retrying Green API verification", retry_count=self.request.retries + 1)
                raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return {
            "success": False,
            "error": str(e),
            "hotel_id": hotel_id,
            "task_id": self.request.id
        }


@celery_app.task(bind=True)
def verify_hotel_complete(self, hotel_id: str, correlation_id: Optional[str] = None):
    """
    Complete hotel verification (runs all verification tasks)
    
    Args:
        hotel_id: Hotel UUID as string
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        Dict with complete verification results
    """
    task_logger = logger.bind(
        task="verify_hotel_complete",
        hotel_id=hotel_id,
        correlation_id=correlation_id,
        task_id=self.request.id
    )
    
    try:
        # Run WhatsApp number verification
        whatsapp_result = verify_hotel_whatsapp_number.delay(hotel_id, correlation_id)
        whatsapp_data = whatsapp_result.get(timeout=300)  # 5 minutes timeout
        
        # Run Green API credentials verification
        green_api_result = verify_hotel_green_api_credentials.delay(hotel_id, correlation_id)
        green_api_data = green_api_result.get(timeout=300)  # 5 minutes timeout
        
        # Combine results
        verification_summary = {
            "hotel_id": hotel_id,
            "verified_at": datetime.utcnow().isoformat(),
            "whatsapp_verification": whatsapp_data,
            "green_api_verification": green_api_data,
            "overall_status": "verified" if (
                whatsapp_data.get("success", False) and 
                green_api_data.get("success", False)
            ) else "failed",
            "task_id": self.request.id
        }
        
        # Update hotel with complete verification summary
        with get_db_session() as db:
            hotel_service = HotelService(db)
            
            # Get current settings
            hotel = hotel_service.get_hotel(uuid.UUID(hotel_id))
            if hotel:
                current_settings = hotel.settings or {}
                updated_settings = {
                    **current_settings,
                    "verification_summary": verification_summary
                }
                
                # Update hotel
                from app.schemas.hotel import HotelUpdate
                update_data = HotelUpdate(settings=updated_settings)
                hotel_service.update_hotel(uuid.UUID(hotel_id), update_data)
        
        task_logger.info(
            "Complete hotel verification finished",
            overall_status=verification_summary["overall_status"],
            whatsapp_success=whatsapp_data.get("success", False),
            green_api_success=green_api_data.get("success", False)
        )
        
        return verification_summary
        
    except Exception as e:
        task_logger.error("Complete hotel verification failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "hotel_id": hotel_id,
            "task_id": self.request.id
        }


@celery_app.task(bind=True)
def verify_hotel_configuration(self, hotel_id: str, correlation_id: Optional[str] = None):
    """
    Verify hotel configuration validity
    
    Args:
        hotel_id: Hotel UUID as string
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        Dict with configuration verification results
    """
    task_logger = logger.bind(
        task="verify_hotel_configuration",
        hotel_id=hotel_id,
        correlation_id=correlation_id,
        task_id=self.request.id
    )
    
    try:
        with get_db_session() as db:
            # Get hotel
            hotel_service = HotelService(db)
            hotel = hotel_service.get_hotel(uuid.UUID(hotel_id))
            
            if not hotel:
                task_logger.error("Hotel not found")
                return {
                    "success": False,
                    "error": "Hotel not found",
                    "hotel_id": hotel_id
                }
            
            # Validate configuration
            validator = HotelValidator(db)
            validation_result = validator.validate_hotel_configuration(hotel.settings or {})
            
            # Update hotel with validation results
            verification_data = {
                "configuration_verification": {
                    "verified_at": datetime.utcnow().isoformat(),
                    "is_valid": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "field_errors": validation_result.field_errors,
                    "task_id": self.request.id
                }
            }
            
            # Merge with existing settings
            current_settings = hotel.settings or {}
            updated_settings = {**current_settings, **verification_data}
            
            # Update hotel
            from app.schemas.hotel import HotelUpdate
            update_data = HotelUpdate(settings=updated_settings)
            hotel_service.update_hotel(uuid.UUID(hotel_id), update_data)
            
            task_logger.info(
                "Hotel configuration verification completed",
                is_valid=validation_result.is_valid,
                error_count=len(validation_result.errors),
                warning_count=len(validation_result.warnings)
            )
            
            return {
                "success": True,
                "hotel_id": hotel_id,
                "validation_result": validation_result.to_dict(),
                "verification_data": verification_data
            }
            
    except Exception as e:
        task_logger.error("Hotel configuration verification failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "hotel_id": hotel_id,
            "task_id": self.request.id
        }


# Convenience functions for triggering verification tasks
def trigger_hotel_verification(hotel_id: uuid.UUID, correlation_id: Optional[str] = None) -> str:
    """
    Trigger complete hotel verification
    
    Args:
        hotel_id: Hotel UUID
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        str: Task ID
    """
    task = verify_hotel_complete.delay(str(hotel_id), correlation_id)
    return task.id


def trigger_whatsapp_verification(hotel_id: uuid.UUID, correlation_id: Optional[str] = None) -> str:
    """
    Trigger WhatsApp number verification
    
    Args:
        hotel_id: Hotel UUID
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        str: Task ID
    """
    task = verify_hotel_whatsapp_number.delay(str(hotel_id), correlation_id)
    return task.id


def trigger_green_api_verification(hotel_id: uuid.UUID, correlation_id: Optional[str] = None) -> str:
    """
    Trigger Green API credentials verification
    
    Args:
        hotel_id: Hotel UUID
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        str: Task ID
    """
    task = verify_hotel_green_api_credentials.delay(str(hotel_id), correlation_id)
    return task.id


def trigger_configuration_verification(hotel_id: uuid.UUID, correlation_id: Optional[str] = None) -> str:
    """
    Trigger hotel configuration verification
    
    Args:
        hotel_id: Hotel UUID
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        str: Task ID
    """
    task = verify_hotel_configuration.delay(str(hotel_id), correlation_id)
    return task.id
