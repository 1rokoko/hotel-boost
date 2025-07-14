"""
Webhook endpoints for Green API integration
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks, Header
from fastapi.responses import JSONResponse
import structlog
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.green_api import (
    WebhookData, WebhookType, parse_webhook_data,
    IncomingMessageWebhook, OutgoingMessageStatusWebhook
)
from app.utils.webhook_validator import validate_green_api_webhook
from app.utils.signature_validator import validate_green_api_webhook_enhanced
from app.core.webhook_config import GreenAPIWebhookConfig
from app.utils.input_sanitizer import default_sanitizer
from app.validators.security_validators import validate_safe_json, validate_content_type
from app.services.webhook_processor import WebhookProcessor
from app.models.hotel import Hotel

logger = structlog.get_logger(__name__)

router = APIRouter()


async def get_hotel_by_instance_id(instance_id: str, db: Session) -> Optional[Hotel]:
    """Get hotel by Green API instance ID"""
    return db.query(Hotel).filter(
        Hotel.green_api_instance_id == instance_id,
        Hotel.is_active == True
    ).first()


@router.post("/green-api")
async def receive_green_api_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_green_api_instance: Optional[str] = Header(None, alias="X-Green-API-Instance"),
    x_green_api_signature: Optional[str] = Header(None, alias="X-Green-API-Signature")
):
    """
    Receive webhook from Green API
    
    This endpoint receives webhooks from Green API and processes them asynchronously.
    It validates the webhook signature and routes the webhook to the appropriate processor.
    """
    try:
        # Get raw body for signature validation
        body = await request.body()
        
        # Validate content type
        content_type = request.headers.get("Content-Type", "")
        try:
            validate_content_type(content_type, {"application/json", "text/plain"})
        except Exception as e:
            logger.error("Invalid content type for webhook", content_type=content_type, error=str(e))
            raise HTTPException(status_code=400, detail="Invalid content type")

        # Parse and sanitize JSON data
        try:
            webhook_data = await request.json()
            # Sanitize webhook data to prevent injection attacks
            webhook_data = validate_safe_json(webhook_data)
        except Exception as e:
            logger.error("Failed to parse or sanitize webhook JSON", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Extract instance data
        instance_data = webhook_data.get("instanceData", {})
        instance_id = instance_data.get("idInstance") or x_green_api_instance
        
        if not instance_id:
            logger.error("Missing instance ID in webhook")
            raise HTTPException(status_code=400, detail="Missing instance ID")
        
        # Find hotel by instance ID
        hotel = await get_hotel_by_instance_id(instance_id, db)
        if not hotel:
            logger.error("Hotel not found for instance ID", instance_id=instance_id)
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        # Validate webhook signature if hotel has webhook token
        if hotel.green_api_webhook_token:
            # Use enhanced validation with timestamp and replay protection
            try:
                timestamp = webhook_data.get("timestamp")
                is_valid = validate_green_api_webhook_enhanced(
                    body=body,
                    signature=x_green_api_signature,
                    secret=hotel.green_api_webhook_token,
                    timestamp=timestamp,
                    config=GreenAPIWebhookConfig()
                )

                if not is_valid:
                    logger.error("Enhanced webhook signature validation failed",
                               hotel_id=hotel.id,
                               instance_id=instance_id,
                               timestamp=timestamp)
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")

            except Exception as e:
                logger.error("Webhook validation error",
                           hotel_id=hotel.id,
                           instance_id=instance_id,
                           error=str(e))
                # Fallback to basic validation for backward compatibility
                is_valid = validate_green_api_webhook(
                    body=body,
                    signature=x_green_api_signature,
                    secret=hotel.green_api_webhook_token
                )

                if not is_valid:
                    logger.error("Fallback webhook signature validation failed",
                               hotel_id=hotel.id,
                               instance_id=instance_id)
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Extract webhook type
        webhook_type = webhook_data.get("typeWebhook")
        if not webhook_type:
            logger.error("Missing webhook type", webhook_data=webhook_data)
            raise HTTPException(status_code=400, detail="Missing webhook type")
        
        # Log webhook receipt
        logger.info("Received Green API webhook",
                   hotel_id=hotel.id,
                   instance_id=instance_id,
                   webhook_type=webhook_type,
                   timestamp=webhook_data.get("timestamp"))
        
        # Parse webhook data
        try:
            parsed_webhook = parse_webhook_data(webhook_type, webhook_data)
        except ValueError as e:
            logger.error("Failed to parse webhook data", 
                        webhook_type=webhook_type,
                        error=str(e))
            raise HTTPException(status_code=400, detail=f"Invalid webhook data: {str(e)}")
        
        # Process webhook asynchronously
        processor = WebhookProcessor(db)
        background_tasks.add_task(
            processor.process_webhook,
            hotel=hotel,
            webhook_data=parsed_webhook
        )
        
        # Return success response
        return JSONResponse(
            status_code=200,
            content={"status": "received", "message": "Webhook processed successfully"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error processing webhook", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/green-api/{instance_id}")
async def receive_green_api_webhook_with_instance(
    instance_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_green_api_signature: Optional[str] = Header(None, alias="X-Green-API-Signature")
):
    """
    Receive webhook from Green API with instance ID in URL
    
    Alternative endpoint that accepts instance ID as URL parameter.
    This is useful when Green API is configured to send webhooks to specific URLs.
    """
    try:
        # Get raw body for signature validation
        body = await request.body()
        
        # Parse JSON data
        try:
            webhook_data = await request.json()
        except Exception as e:
            logger.error("Failed to parse webhook JSON", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Find hotel by instance ID
        hotel = await get_hotel_by_instance_id(instance_id, db)
        if not hotel:
            logger.error("Hotel not found for instance ID", instance_id=instance_id)
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        # Validate webhook signature if hotel has webhook token
        if hotel.green_api_webhook_token:
            # Use enhanced validation with timestamp and replay protection
            try:
                timestamp = webhook_data.get("timestamp")
                is_valid = validate_green_api_webhook_enhanced(
                    body=body,
                    signature=x_green_api_signature,
                    secret=hotel.green_api_webhook_token,
                    timestamp=timestamp,
                    config=GreenAPIWebhookConfig()
                )

                if not is_valid:
                    logger.error("Enhanced webhook signature validation failed",
                               hotel_id=hotel.id,
                               instance_id=instance_id,
                               timestamp=timestamp)
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")

            except Exception as e:
                logger.error("Webhook validation error",
                           hotel_id=hotel.id,
                           instance_id=instance_id,
                           error=str(e))
                # Fallback to basic validation for backward compatibility
                is_valid = validate_green_api_webhook(
                    body=body,
                    signature=x_green_api_signature,
                    secret=hotel.green_api_webhook_token
                )

                if not is_valid:
                    logger.error("Fallback webhook signature validation failed",
                               hotel_id=hotel.id,
                               instance_id=instance_id)
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Extract webhook type
        webhook_type = webhook_data.get("typeWebhook")
        if not webhook_type:
            logger.error("Missing webhook type", webhook_data=webhook_data)
            raise HTTPException(status_code=400, detail="Missing webhook type")
        
        # Log webhook receipt
        logger.info("Received Green API webhook with instance ID",
                   hotel_id=hotel.id,
                   instance_id=instance_id,
                   webhook_type=webhook_type,
                   timestamp=webhook_data.get("timestamp"))
        
        # Parse webhook data
        try:
            parsed_webhook = parse_webhook_data(webhook_type, webhook_data)
        except ValueError as e:
            logger.error("Failed to parse webhook data", 
                        webhook_type=webhook_type,
                        error=str(e))
            raise HTTPException(status_code=400, detail=f"Invalid webhook data: {str(e)}")
        
        # Process webhook asynchronously
        processor = WebhookProcessor(db)
        background_tasks.add_task(
            processor.process_webhook,
            hotel=hotel,
            webhook_data=parsed_webhook
        )
        
        # Return success response
        return JSONResponse(
            status_code=200,
            content={"status": "received", "message": "Webhook processed successfully"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error processing webhook", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/green-api/health")
async def webhook_health_check():
    """
    Health check endpoint for webhook service
    
    This endpoint can be used by Green API or monitoring systems
    to verify that the webhook service is operational.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "green-api-webhook",
            "message": "Webhook service is operational"
        }
    )


@router.get("/green-api/test/{instance_id}")
async def test_webhook_endpoint(
    instance_id: str,
    db: Session = Depends(get_db)
):
    """
    Test endpoint to verify webhook configuration
    
    This endpoint can be used to test if a hotel's webhook configuration
    is properly set up and the instance ID is valid.
    """
    try:
        # Find hotel by instance ID
        hotel = await get_hotel_by_instance_id(instance_id, db)
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Webhook endpoint is configured correctly",
                "hotel_id": str(hotel.id),
                "hotel_name": hotel.name,
                "instance_id": instance_id,
                "webhook_token_configured": bool(hotel.green_api_webhook_token)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in webhook test", instance_id=instance_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# Include router in main API
def include_webhook_routes(app_router: APIRouter):
    """Include webhook routes in main application router"""
    app_router.include_router(
        router,
        prefix="/webhooks",
        tags=["webhooks"]
    )
