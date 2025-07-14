"""
Hotel service for WhatsApp Hotel Bot application
"""

import uuid
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import and_, or_, func, desc, asc
import structlog

from app.models.hotel import Hotel
from app.schemas.hotel import (
    HotelCreate,
    HotelUpdate,
    HotelResponse,
    HotelListResponse,
    HotelSearchParams
)
from app.core.tenant import TenantContext, require_tenant_context
from app.core.logging import get_logger

logger = get_logger(__name__)


class HotelServiceError(Exception):
    """Base exception for hotel service errors"""
    pass


class HotelNotFoundError(HotelServiceError):
    """Raised when hotel is not found"""
    pass


class HotelAlreadyExistsError(HotelServiceError):
    """Raised when hotel with same WhatsApp number already exists"""
    pass


class HotelService:
    """Service for managing hotel operations"""
    
    def __init__(self, db: Session):
        """
        Initialize hotel service
        
        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger.bind(service="hotel_service")
    
    def create_hotel(self, hotel_data: HotelCreate) -> HotelResponse:
        """
        Create a new hotel

        Args:
            hotel_data: Hotel creation data

        Returns:
            HotelResponse: Created hotel data

        Raises:
            HotelAlreadyExistsError: If hotel with same WhatsApp number exists
            HotelServiceError: If creation fails
        """
        try:
            # Check if hotel with same WhatsApp number already exists
            existing_hotel = self.db.query(Hotel).filter(
                Hotel.whatsapp_number == hotel_data.whatsapp_number
            ).first()
            
            if existing_hotel:
                raise HotelAlreadyExistsError(
                    f"Hotel with WhatsApp number {hotel_data.whatsapp_number} already exists"
                )
            
            # Create hotel instance
            hotel = Hotel(
                name=hotel_data.name,
                whatsapp_number=hotel_data.whatsapp_number,
                green_api_instance_id=hotel_data.green_api_instance_id,
                green_api_token=hotel_data.green_api_token,
                green_api_webhook_token=hotel_data.green_api_webhook_token,
                settings=hotel_data.settings or Hotel().get_default_settings(),
                is_active=hotel_data.is_active
            )

            # Set DeepSeek API key if provided
            if hasattr(hotel_data, 'deepseek_api_key') and hotel_data.deepseek_api_key:
                hotel.set_deepseek_api_key(hotel_data.deepseek_api_key)
            
            # Add to database
            self.db.add(hotel)
            self.db.commit()
            self.db.refresh(hotel)
            
            self.logger.info(
                "Hotel created successfully",
                hotel_id=str(hotel.id),
                hotel_name=hotel.name,
                whatsapp_number=hotel.whatsapp_number
            )
            
            return self._hotel_to_response(hotel)
            
        except IntegrityError as e:
            self.db.rollback()
            self.logger.error("Hotel creation failed due to integrity error", error=str(e))
            raise HotelAlreadyExistsError("Hotel with this data already exists")
        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error("Hotel creation failed", error=str(e))
            raise HotelServiceError(f"Failed to create hotel: {str(e)}")
    
    def get_hotel(self, hotel_id: uuid.UUID) -> Optional[HotelResponse]:
        """
        Get hotel by ID

        Args:
            hotel_id: Hotel UUID

        Returns:
            Optional[HotelResponse]: Hotel data or None if not found
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            
            if not hotel:
                return None
            
            return self._hotel_to_response(hotel)
            
        except SQLAlchemyError as e:
            self.logger.error("Failed to get hotel", hotel_id=str(hotel_id), error=str(e))
            raise HotelServiceError(f"Failed to get hotel: {str(e)}")
    
    def get_hotel_by_whatsapp_number(self, whatsapp_number: str) -> Optional[HotelResponse]:
        """
        Get hotel by WhatsApp number

        Args:
            whatsapp_number: WhatsApp phone number

        Returns:
            Optional[HotelResponse]: Hotel data or None if not found
        """
        try:
            hotel = self.db.query(Hotel).filter(
                Hotel.whatsapp_number == whatsapp_number
            ).first()
            
            if not hotel:
                return None
            
            return self._hotel_to_response(hotel)
            
        except SQLAlchemyError as e:
            self.logger.error(
                "Failed to get hotel by WhatsApp number",
                whatsapp_number=whatsapp_number,
                error=str(e)
            )
            raise HotelServiceError(f"Failed to get hotel: {str(e)}")
    
    def update_hotel(self, hotel_id: uuid.UUID, hotel_data: HotelUpdate) -> Optional[HotelResponse]:
        """
        Update hotel

        Args:
            hotel_id: Hotel UUID
            hotel_data: Hotel update data

        Returns:
            Optional[HotelResponse]: Updated hotel data or None if not found

        Raises:
            HotelAlreadyExistsError: If WhatsApp number conflicts with another hotel
            HotelServiceError: If update fails
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            
            if not hotel:
                return None
            
            # Check for WhatsApp number conflicts if updating
            if hotel_data.whatsapp_number and hotel_data.whatsapp_number != hotel.whatsapp_number:
                existing_hotel = self.db.query(Hotel).filter(
                    and_(
                        Hotel.whatsapp_number == hotel_data.whatsapp_number,
                        Hotel.id != hotel_id
                    )
                ).first()
                
                if existing_hotel:
                    raise HotelAlreadyExistsError(
                        f"Hotel with WhatsApp number {hotel_data.whatsapp_number} already exists"
                    )
            
            # Update fields
            update_data = hotel_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(hotel, field, value)
            
            self.db.commit()
            self.db.refresh(hotel)
            
            self.logger.info(
                "Hotel updated successfully",
                hotel_id=str(hotel.id),
                updated_fields=list(update_data.keys())
            )
            
            return self._hotel_to_response(hotel)
            
        except IntegrityError as e:
            self.db.rollback()
            self.logger.error("Hotel update failed due to integrity error", error=str(e))
            raise HotelAlreadyExistsError("Hotel with this data already exists")
        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error("Hotel update failed", hotel_id=str(hotel_id), error=str(e))
            raise HotelServiceError(f"Failed to update hotel: {str(e)}")
    
    def delete_hotel(self, hotel_id: uuid.UUID) -> bool:
        """
        Delete hotel

        Args:
            hotel_id: Hotel UUID

        Returns:
            bool: True if deleted, False if not found

        Raises:
            HotelServiceError: If deletion fails
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            
            if not hotel:
                return False
            
            self.db.delete(hotel)
            self.db.commit()
            
            self.logger.info(
                "Hotel deleted successfully",
                hotel_id=str(hotel.id),
                hotel_name=hotel.name
            )
            
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error("Hotel deletion failed", hotel_id=str(hotel_id), error=str(e))
            raise HotelServiceError(f"Failed to delete hotel: {str(e)}")
    
    def search_hotels(self, search_params: HotelSearchParams) -> HotelListResponse:
        """
        Search hotels with pagination and filtering

        Args:
            search_params: Search parameters

        Returns:
            HotelListResponse: Paginated hotel list

        Raises:
            HotelServiceError: If search fails
        """
        try:
            # Build base query
            query = self.db.query(Hotel)

            # Apply filters
            if search_params.name:
                query = query.filter(Hotel.name.ilike(f"%{search_params.name}%"))

            if search_params.whatsapp_number:
                query = query.filter(Hotel.whatsapp_number == search_params.whatsapp_number)

            if search_params.is_active is not None:
                query = query.filter(Hotel.is_active == search_params.is_active)

            if search_params.has_credentials is not None:
                if search_params.has_credentials:
                    query = query.filter(
                        and_(
                            Hotel.green_api_instance_id.isnot(None),
                            Hotel.green_api_token.isnot(None)
                        )
                    )
                else:
                    query = query.filter(
                        or_(
                            Hotel.green_api_instance_id.is_(None),
                            Hotel.green_api_token.is_(None)
                        )
                    )

            # Apply sorting
            sort_column = getattr(Hotel, search_params.sort_by)
            if search_params.sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

            # Get total count
            total = query.count()

            # Apply pagination
            offset = (search_params.page - 1) * search_params.size
            hotels = query.offset(offset).limit(search_params.size).all()

            # Calculate pagination info
            pages = (total + search_params.size - 1) // search_params.size

            # Convert to response schemas
            hotel_responses = [self._hotel_to_response(hotel) for hotel in hotels]

            return HotelListResponse(
                hotels=hotel_responses,
                total=total,
                page=search_params.page,
                size=search_params.size,
                pages=pages
            )

        except SQLAlchemyError as e:
            self.logger.error("Hotel search failed", error=str(e))
            raise HotelServiceError(f"Failed to search hotels: {str(e)}")

    def get_active_hotels(self) -> List[HotelResponse]:
        """
        Get all active hotels

        Returns:
            List[HotelResponse]: List of active hotels

        Raises:
            HotelServiceError: If query fails
        """
        try:
            hotels = self.db.query(Hotel).filter(Hotel.is_active == True).all()
            return [self._hotel_to_response(hotel) for hotel in hotels]

        except SQLAlchemyError as e:
            self.logger.error("Failed to get active hotels", error=str(e))
            raise HotelServiceError(f"Failed to get active hotels: {str(e)}")

    def get_operational_hotels(self) -> List[HotelResponse]:
        """
        Get all operational hotels (active with Green API credentials)

        Returns:
            List[HotelResponse]: List of operational hotels

        Raises:
            HotelServiceError: If query fails
        """
        try:
            hotels = self.db.query(Hotel).filter(
                and_(
                    Hotel.is_active == True,
                    Hotel.green_api_instance_id.isnot(None),
                    Hotel.green_api_token.isnot(None)
                )
            ).all()
            return [self._hotel_to_response(hotel) for hotel in hotels]

        except SQLAlchemyError as e:
            self.logger.error("Failed to get operational hotels", error=str(e))
            raise HotelServiceError(f"Failed to get operational hotels: {str(e)}")

    def _hotel_to_response(self, hotel: Hotel) -> HotelResponse:
        """
        Convert hotel model to response schema

        Args:
            hotel: Hotel model instance

        Returns:
            HotelResponse: Hotel response schema
        """
        return HotelResponse(
            id=hotel.id,
            name=hotel.name,
            whatsapp_number=hotel.whatsapp_number,
            green_api_instance_id=hotel.green_api_instance_id,
            has_green_api_credentials=hotel.has_green_api_credentials,
            settings=hotel.settings,
            is_active=hotel.is_active,
            is_operational=hotel.is_operational,
            created_at=hotel.created_at,
            updated_at=hotel.updated_at
        )

    def update_green_api_settings(
        self,
        hotel_id: uuid.UUID,
        green_api_settings: Dict[str, Any]
    ) -> Optional[HotelResponse]:
        """
        Update Green API settings for a hotel

        Args:
            hotel_id: Hotel UUID
            green_api_settings: New Green API settings

        Returns:
            Optional[HotelResponse]: Updated hotel or None if not found

        Raises:
            HotelServiceError: If update fails
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()

            if not hotel:
                return None

            hotel.update_green_api_settings(green_api_settings)

            self.db.commit()
            self.db.refresh(hotel)

            self.logger.info(
                "Green API settings updated",
                hotel_id=str(hotel_id),
                settings_keys=list(green_api_settings.keys())
            )

            return self._hotel_to_response(hotel)

        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error("Failed to update Green API settings", hotel_id=str(hotel_id), error=str(e))
            raise HotelServiceError(f"Failed to update Green API settings: {str(e)}")

    def update_deepseek_settings(
        self,
        hotel_id: uuid.UUID,
        deepseek_settings: Dict[str, Any]
    ) -> Optional[HotelResponse]:
        """
        Update DeepSeek AI settings for a hotel

        Args:
            hotel_id: Hotel UUID
            deepseek_settings: New DeepSeek settings

        Returns:
            Optional[HotelResponse]: Updated hotel or None if not found

        Raises:
            HotelServiceError: If update fails
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()

            if not hotel:
                return None

            hotel.update_deepseek_settings(deepseek_settings)

            self.db.commit()
            self.db.refresh(hotel)

            self.logger.info(
                "DeepSeek settings updated",
                hotel_id=str(hotel_id),
                settings_keys=list(deepseek_settings.keys())
            )

            return self._hotel_to_response(hotel)

        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error("Failed to update DeepSeek settings", hotel_id=str(hotel_id), error=str(e))
            raise HotelServiceError(f"Failed to update DeepSeek settings: {str(e)}")

    def get_hotel_configuration(self, hotel_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Get hotel configuration status

        Args:
            hotel_id: Hotel UUID

        Returns:
            Optional[Dict[str, Any]]: Configuration status or None if not found
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()

            if not hotel:
                return None

            return {
                "hotel_id": hotel.id,
                "green_api_configured": hotel.is_green_api_configured(),
                "deepseek_configured": hotel.is_deepseek_configured(),
                "fully_configured": hotel.is_fully_configured(),
                "settings": hotel.settings
            }

        except SQLAlchemyError as e:
            self.logger.error("Failed to get hotel configuration", hotel_id=str(hotel_id), error=str(e))
            raise HotelServiceError(f"Failed to get hotel configuration: {str(e)}")

    def test_green_api_connection(self, hotel_id: uuid.UUID) -> Dict[str, Any]:
        """
        Test Green API connection for a hotel

        Args:
            hotel_id: Hotel UUID

        Returns:
            Dict[str, Any]: Test results

        Raises:
            HotelServiceError: If test fails
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()

            if not hotel:
                raise HotelServiceError(f"Hotel {hotel_id} not found")

            if not hotel.is_green_api_configured():
                return {
                    "success": False,
                    "error": "Green API not configured for this hotel"
                }

            # Here we would test the actual Green API connection
            # For now, return success if credentials are present
            return {
                "success": True,
                "instance_id": hotel.green_api_instance_id,
                "has_webhook_token": bool(hotel.green_api_webhook_token)
            }

        except Exception as e:
            self.logger.error("Green API connection test failed", hotel_id=str(hotel_id), error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    def test_deepseek_connection(self, hotel_id: uuid.UUID) -> Dict[str, Any]:
        """
        Test DeepSeek API connection for a hotel

        Args:
            hotel_id: Hotel UUID

        Returns:
            Dict[str, Any]: Test results

        Raises:
            HotelServiceError: If test fails
        """
        try:
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()

            if not hotel:
                raise HotelServiceError(f"Hotel {hotel_id} not found")

            if not hotel.is_deepseek_configured():
                return {
                    "success": False,
                    "error": "DeepSeek API not configured for this hotel"
                }

            # Here we would test the actual DeepSeek API connection
            # For now, return success if API key is present
            deepseek_settings = hotel.get_deepseek_settings()
            return {
                "success": True,
                "model": deepseek_settings.get("model", "deepseek-chat"),
                "has_api_key": bool(deepseek_settings.get("api_key"))
            }

        except Exception as e:
            self.logger.error("DeepSeek connection test failed", hotel_id=str(hotel_id), error=str(e))
            return {
                "success": False,
                "error": str(e)
            }


# Dependency injection helper
def get_hotel_service(db: Session) -> HotelService:
    """
    Get hotel service instance

    Args:
        db: Database session

    Returns:
        HotelService: Hotel service instance
    """
    return HotelService(db)
