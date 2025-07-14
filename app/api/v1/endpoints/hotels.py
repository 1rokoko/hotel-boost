"""
Hotel API endpoints for WhatsApp Hotel Bot
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.hotel_service import (
    HotelService,
    HotelServiceError,
    HotelNotFoundError,
    HotelAlreadyExistsError
)
from app.schemas.hotel import (
    HotelCreate,
    HotelUpdate,
    HotelResponse,
    HotelListResponse,
    HotelSearchParams,
    HotelConfigUpdate,
    HotelStatusUpdate,
    GreenAPISettings,
    DeepSeekSettings,
    HotelSettingsUpdate,
    HotelConfigurationResponse
)
from app.core.tenant import require_tenant_context
from app.middleware.tenant import get_current_tenant_id

logger = structlog.get_logger(__name__)

router = APIRouter()


def get_hotel_service_dep(db: Session = Depends(get_db)) -> HotelService:
    """Dependency to get hotel service instance"""
    return HotelService(db)


@router.post("/", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
def create_hotel(
    hotel_data: HotelCreate
):
    """
    Create a new hotel
    
    Creates a new hotel with the provided information. The hotel will be
    associated with the current tenant context.
    """
    try:
        hotel_service = hotelService(db)
        hotel = hotel_service.create_hotel(hotel_data)
        
        logger.info(
            "Hotel created via API",
            hotel_id=str(hotel.id),
            hotel_name=hotel.name
        )
        
        return hotel
        
    except HotelAlreadyExistsError as e:
        logger.warning("Hotel creation failed - already exists", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except HotelServiceError as e:
        logger.error("Hotel creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create hotel"
        )


@router.get("/", response_model=HotelListResponse)
def search_hotels(
    name: Optional[str] = Query(None, description="Search by hotel name"),
    whatsapp_number: Optional[str] = Query(None, description="Search by WhatsApp number"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    has_credentials: Optional[bool] = Query(None, description="Filter by Green API credentials"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", description="Sort order")
):
    """
    Search and list hotels with pagination
    
    Returns a paginated list of hotels based on the provided search criteria.
    """
    try:
        search_params = HotelSearchParams(
            name=name,
            whatsapp_number=whatsapp_number,
            is_active=is_active,
            has_credentials=has_credentials,
            page=page,
            size=size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        result = hotel_service.search_hotels(search_params)
        
        logger.info(
            "Hotels searched via API",
            total_found=result.total,
            page=page,
            size=size
        )
        
        return result
        
    except HotelServiceError as e:
        logger.error("Hotel search failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search hotels"
        )


@router.get("/active", response_model=List[HotelResponse])
def get_active_hotels(    hotel_service: HotelService = Depends(get_hotel_service_dep)
):
    """
    Get all active hotels
    
    Returns a list of all hotels that are currently active.
    """
    try:
        hotels = hotel_service.get_active_hotels()
        
        logger.info("Active hotels retrieved via API", count=len(hotels))
        
        return hotels
        
    except HotelServiceError as e:
        logger.error("Failed to get active hotels", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get active hotels"
        )


@router.get("/operational", response_model=List[HotelResponse])
def get_operational_hotels(    hotel_service: HotelService = Depends(get_hotel_service_dep)
):
    """
    Get all operational hotels
    
    Returns a list of all hotels that are active and have Green API credentials configured.
    """
    try:
        hotels = hotel_service.get_operational_hotels()
        
        logger.info("Operational hotels retrieved via API", count=len(hotels))
        
        return hotels
        
    except HotelServiceError as e:
        logger.error("Failed to get operational hotels", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get operational hotels"
        )


@router.get("/{hotel_id}", response_model=HotelResponse)
def get_hotel(
    hotel_id: uuid.UUID
):
    """
    Get hotel by ID
    
    Returns detailed information about a specific hotel.
    """
    try:
        hotel = hotel_service.get_hotel(hotel_id)
        
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )
        
        logger.info("Hotel retrieved via API", hotel_id=str(hotel_id))
        
        return hotel
        
    except HotelServiceError as e:
        logger.error("Failed to get hotel", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get hotel"
        )


@router.put("/{hotel_id}", response_model=HotelResponse)
def update_hotel(
    hotel_id: uuid.UUID,
    hotel_data: HotelUpdate
):
    """
    Update hotel
    
    Updates an existing hotel with the provided information.
    """
    try:
        hotel = hotel_service.update_hotel(hotel_id, hotel_data)
        
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )
        
        logger.info("Hotel updated via API", hotel_id=str(hotel_id))
        
        return hotel
        
    except HotelAlreadyExistsError as e:
        logger.warning("Hotel update failed - conflict", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except HotelServiceError as e:
        logger.error("Hotel update failed", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update hotel"
        )


@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hotel(
    hotel_id: uuid.UUID
):
    """
    Delete hotel
    
    Permanently deletes a hotel and all associated data.
    """
    try:
        deleted = hotel_service.delete_hotel(hotel_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )
        
        logger.info("Hotel deleted via API", hotel_id=str(hotel_id))
        
        return None
        
    except HotelServiceError as e:
        logger.error("Hotel deletion failed", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete hotel"
        )


@router.get("/whatsapp/{whatsapp_number}", response_model=HotelResponse)
def get_hotel_by_whatsapp_number(
    whatsapp_number: str
):
    """
    Get hotel by WhatsApp number
    
    Returns hotel information based on the WhatsApp number.
    """
    try:
        hotel = hotel_service.get_hotel_by_whatsapp_number(whatsapp_number)
        
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )
        
        logger.info(
            "Hotel retrieved by WhatsApp number via API",
            whatsapp_number=whatsapp_number,
            hotel_id=str(hotel.id)
        )
        
        return hotel
        
    except HotelServiceError as e:
        logger.error(
            "Failed to get hotel by WhatsApp number",
            whatsapp_number=whatsapp_number,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get hotel"
        )


@router.patch("/{hotel_id}/config", response_model=HotelResponse)
def update_hotel_config(
    hotel_id: uuid.UUID,
    config_data: HotelConfigUpdate
):
    """
    Update hotel configuration

    Updates the hotel's settings/configuration. Can merge with existing settings
    or replace them completely based on the merge flag.
    """
    try:
        # Get current hotel
        hotel = hotel_service.get_hotel(hotel_id)
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )

        # Prepare update data
        if config_data.merge:
            # Merge with existing settings
            current_settings = hotel.settings or {}
            updated_settings = {**current_settings, **config_data.settings}
        else:
            # Replace settings completely
            updated_settings = config_data.settings

        # Update hotel
        update_data = HotelUpdate(settings=updated_settings)
        updated_hotel = hotel_service.update_hotel(hotel_id, update_data)

        logger.info(
            "Hotel configuration updated via API",
            hotel_id=str(hotel_id),
            merge=config_data.merge
        )

        return updated_hotel

    except HotelServiceError as e:
        logger.error("Hotel config update failed", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update hotel configuration"
        )


@router.patch("/{hotel_id}/status", response_model=HotelResponse)
def update_hotel_status(
    hotel_id: uuid.UUID,
    status_data: HotelStatusUpdate
):
    """
    Update hotel status

    Updates the hotel's active status with an optional reason.
    """
    try:
        # Update hotel status
        update_data = HotelUpdate(is_active=status_data.is_active)
        updated_hotel = hotel_service.update_hotel(hotel_id, update_data)

        if not updated_hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )

        logger.info(
            "Hotel status updated via API",
            hotel_id=str(hotel_id),
            is_active=status_data.is_active,
            reason=status_data.reason
        )

        return updated_hotel

    except HotelServiceError as e:
        logger.error("Hotel status update failed", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update hotel status"
        )


@router.get("/{hotel_id}/configuration", response_model=HotelConfigurationResponse)
def get_hotel_configuration(
    hotel_id: uuid.UUID
):
    """
    Get hotel configuration status

    Returns the configuration status including Green API and DeepSeek setup.
    """
    try:
        config = hotel_service.get_hotel_configuration(hotel_id)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )

        return config

    except HotelServiceError as e:
        logger.error("Failed to get hotel configuration", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get hotel configuration"
        )


@router.put("/{hotel_id}/green-api", response_model=HotelResponse)
def update_green_api_settings(
    hotel_id: uuid.UUID,
    green_api_settings: GreenAPISettings
):
    """
    Update Green API settings for a hotel

    Updates the Green API configuration for the specified hotel.
    """
    try:
        hotel = hotel_service.update_green_api_settings(
            hotel_id,
            green_api_settings.dict(exclude_unset=True)
        )

        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )

        logger.info("Green API settings updated via API", hotel_id=str(hotel_id))

        return hotel

    except HotelServiceError as e:
        logger.error("Failed to update Green API settings", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Green API settings"
        )


@router.put("/{hotel_id}/deepseek", response_model=HotelResponse)
def update_deepseek_settings(
    hotel_id: uuid.UUID,
    deepseek_settings: DeepSeekSettings
):
    """
    Update DeepSeek AI settings for a hotel

    Updates the DeepSeek AI configuration for the specified hotel.
    """
    try:
        hotel = hotel_service.update_deepseek_settings(
            hotel_id,
            deepseek_settings.dict(exclude_unset=True)
        )

        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )

        logger.info("DeepSeek settings updated via API", hotel_id=str(hotel_id))

        return hotel

    except HotelServiceError as e:
        logger.error("Failed to update DeepSeek settings", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update DeepSeek settings"
        )


@router.post("/{hotel_id}/test-green-api")
def test_green_api_connection(
    hotel_id: uuid.UUID
):
    """
    Test Green API connection for a hotel

    Tests the Green API connection and returns the status.
    """
    try:
        result = hotel_service.test_green_api_connection(hotel_id)

        logger.info("Green API connection tested", hotel_id=str(hotel_id), success=result.get("success"))

        return result

    except HotelServiceError as e:
        logger.error("Green API connection test failed", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test Green API connection"
        )


@router.post("/{hotel_id}/test-deepseek")
def test_deepseek_connection(
    hotel_id: uuid.UUID
):
    """
    Test DeepSeek API connection for a hotel

    Tests the DeepSeek API connection and returns the status.
    """
    try:
        result = hotel_service.test_deepseek_connection(hotel_id)

        logger.info("DeepSeek connection tested", hotel_id=str(hotel_id), success=result.get("success"))

        return result

    except HotelServiceError as e:
        logger.error("DeepSeek connection test failed", hotel_id=str(hotel_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test DeepSeek connection"
        )
