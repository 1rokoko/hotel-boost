"""
Integrated Green API Service for WhatsApp Hotel Bot
"""

from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.orm import Session

from app.core.green_api_config import (
    GreenAPIConfig, GreenAPIHotelConfig, 
    get_green_api_config, create_hotel_config
)
from app.services.green_api import (
    GreenAPIClient, get_green_api_client, 
    close_green_api_client, get_all_green_api_metrics
)
from app.schemas.green_api import (
    SendTextMessageRequest, SendFileRequest, SendLocationRequest,
    SendContactRequest, SendPollRequest, SendMessageResponse,
    format_chat_id, extract_phone_number, MessageType
)
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType as DBMessageType

logger = structlog.get_logger(__name__)


class GreenAPIService:
    """Main service for Green API operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.global_config = get_green_api_config()
    
    async def get_hotel_client(self, hotel: Hotel) -> GreenAPIClient:
        """Get Green API client for specific hotel"""
        if not hotel.green_api_instance_id or not hotel.green_api_token:
            raise ValueError(f"Hotel {hotel.id} missing Green API credentials")
        
        # Create hotel-specific config
        hotel_config = create_hotel_config(
            hotel_id=str(hotel.id),
            instance_id=hotel.green_api_instance_id,
            token=hotel.green_api_token,
            webhook_token=hotel.green_api_webhook_token
        )
        
        # Get effective configuration
        effective_config = hotel_config.get_effective_config(self.global_config)
        
        # Get client from pool
        return await get_green_api_client(str(hotel.id), effective_config)
    
    async def send_text_message(
        self,
        hotel: Hotel,
        phone_number: str,
        message: str,
        quoted_message_id: Optional[str] = None
    ) -> SendMessageResponse:
        """Send text message to guest"""
        try:
            client = await self.get_hotel_client(hotel)
            
            # Format chat ID
            chat_id = format_chat_id(phone_number)
            
            # Create request
            request = SendTextMessageRequest(
                chatId=chat_id,
                message=message,
                quotedMessageId=quoted_message_id
            )
            
            # Send message
            response = await client.send_text_message(request)
            
            logger.info("Text message sent successfully",
                       hotel_id=hotel.id,
                       phone_number=phone_number,
                       message_id=response.idMessage)
            
            return response
            
        except Exception as e:
            logger.error("Failed to send text message",
                        hotel_id=hotel.id,
                        phone_number=phone_number,
                        error=str(e))
            raise
    
    async def send_file_message(
        self,
        hotel: Hotel,
        phone_number: str,
        file_url: str,
        file_name: str,
        caption: Optional[str] = None
    ) -> SendMessageResponse:
        """Send file message to guest"""
        try:
            client = await self.get_hotel_client(hotel)
            
            # Format chat ID
            chat_id = format_chat_id(phone_number)
            
            # Create request
            request = SendFileRequest(
                chatId=chat_id,
                urlFile=file_url,
                fileName=file_name,
                caption=caption
            )
            
            # Send file
            response = await client.send_file_by_url(request)
            
            logger.info("File message sent successfully",
                       hotel_id=hotel.id,
                       phone_number=phone_number,
                       file_name=file_name,
                       message_id=response.idMessage)
            
            return response
            
        except Exception as e:
            logger.error("Failed to send file message",
                        hotel_id=hotel.id,
                        phone_number=phone_number,
                        file_name=file_name,
                        error=str(e))
            raise
    
    async def send_location_message(
        self,
        hotel: Hotel,
        phone_number: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None
    ) -> SendMessageResponse:
        """Send location message to guest"""
        try:
            client = await self.get_hotel_client(hotel)
            
            # Format chat ID
            chat_id = format_chat_id(phone_number)
            
            # Create request
            request = SendLocationRequest(
                chatId=chat_id,
                latitude=latitude,
                longitude=longitude,
                nameLocation=name,
                address=address
            )
            
            # Send location
            response = await client.send_location(request)
            
            logger.info("Location message sent successfully",
                       hotel_id=hotel.id,
                       phone_number=phone_number,
                       latitude=latitude,
                       longitude=longitude,
                       message_id=response.idMessage)
            
            return response
            
        except Exception as e:
            logger.error("Failed to send location message",
                        hotel_id=hotel.id,
                        phone_number=phone_number,
                        error=str(e))
            raise
    
    async def send_contact_message(
        self,
        hotel: Hotel,
        phone_number: str,
        contact_data: Dict[str, str]
    ) -> SendMessageResponse:
        """Send contact message to guest"""
        try:
            client = await self.get_hotel_client(hotel)
            
            # Format chat ID
            chat_id = format_chat_id(phone_number)
            
            # Create request
            request = SendContactRequest(
                chatId=chat_id,
                contact=contact_data
            )
            
            # Send contact
            response = await client.send_contact(request)
            
            logger.info("Contact message sent successfully",
                       hotel_id=hotel.id,
                       phone_number=phone_number,
                       message_id=response.idMessage)
            
            return response
            
        except Exception as e:
            logger.error("Failed to send contact message",
                        hotel_id=hotel.id,
                        phone_number=phone_number,
                        error=str(e))
            raise
    
    async def send_poll_message(
        self,
        hotel: Hotel,
        phone_number: str,
        question: str,
        options: List[str],
        multiple_answers: bool = False
    ) -> SendMessageResponse:
        """Send poll message to guest"""
        try:
            client = await self.get_hotel_client(hotel)
            
            # Format chat ID
            chat_id = format_chat_id(phone_number)
            
            # Format options
            poll_options = [{"optionName": option} for option in options]
            
            # Create request
            request = SendPollRequest(
                chatId=chat_id,
                message=question,
                options=poll_options,
                multipleAnswers=multiple_answers
            )
            
            # Send poll
            response = await client.send_poll(request)
            
            logger.info("Poll message sent successfully",
                       hotel_id=hotel.id,
                       phone_number=phone_number,
                       question=question,
                       options_count=len(options),
                       message_id=response.idMessage)
            
            return response
            
        except Exception as e:
            logger.error("Failed to send poll message",
                        hotel_id=hotel.id,
                        phone_number=phone_number,
                        error=str(e))
            raise
    
    async def get_instance_status(self, hotel: Hotel) -> Dict[str, Any]:
        """Get Green API instance status for hotel"""
        try:
            client = await self.get_hotel_client(hotel)
            status = await client.get_status_instance()
            
            logger.info("Retrieved instance status",
                       hotel_id=hotel.id,
                       status=status)
            
            return status
            
        except Exception as e:
            logger.error("Failed to get instance status",
                        hotel_id=hotel.id,
                        error=str(e))
            raise
    
    async def get_instance_state(self, hotel: Hotel) -> Dict[str, Any]:
        """Get Green API instance state for hotel"""
        try:
            client = await self.get_hotel_client(hotel)
            state = await client.get_state_instance()
            
            logger.info("Retrieved instance state",
                       hotel_id=hotel.id,
                       state=state.stateInstance)
            
            return state.dict()
            
        except Exception as e:
            logger.error("Failed to get instance state",
                        hotel_id=hotel.id,
                        error=str(e))
            raise
    
    async def setup_webhook(self, hotel: Hotel, webhook_url: str) -> Dict[str, Any]:
        """Setup webhook for hotel instance"""
        try:
            client = await self.get_hotel_client(hotel)
            
            # Get current settings
            current_settings = await client.get_settings()
            
            # Update webhook settings
            from app.schemas.green_api import SetSettingsRequest
            
            settings_request = SetSettingsRequest(
                webhookUrl=webhook_url,
                webhookUrlToken=hotel.green_api_webhook_token,
                incomingWebhook="yes",
                outgoingWebhook="yes"
            )
            
            # Apply settings
            result = await client.set_settings(settings_request)
            
            logger.info("Webhook setup completed",
                       hotel_id=hotel.id,
                       webhook_url=webhook_url)
            
            return result
            
        except Exception as e:
            logger.error("Failed to setup webhook",
                        hotel_id=hotel.id,
                        webhook_url=webhook_url,
                        error=str(e))
            raise
    
    async def close_hotel_client(self, hotel: Hotel) -> None:
        """Close Green API client for hotel"""
        await close_green_api_client(str(hotel.id))
        logger.info("Closed Green API client", hotel_id=hotel.id)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all hotel clients"""
        return get_all_green_api_metrics()


# Utility functions
def map_green_api_message_type(green_api_type: str) -> DBMessageType:
    """Map Green API message type to database message type"""
    # For now, all incoming messages are treated as incoming
    # and all outgoing as outgoing
    return DBMessageType.INCOMING


def extract_message_content(message_data: Dict[str, Any], message_type: str) -> str:
    """Extract message content from Green API message data"""
    if message_type == MessageType.TEXT:
        return message_data.get("textMessageData", {}).get("textMessage", "")
    elif message_type in [MessageType.IMAGE, MessageType.VIDEO, MessageType.AUDIO, MessageType.DOCUMENT]:
        # For media messages, return caption or file name
        media_data = message_data.get(f"{message_type.replace('Message', '')}MessageData", {})
        return media_data.get("caption", media_data.get("fileName", f"[{message_type}]"))
    elif message_type == MessageType.LOCATION:
        location_data = message_data.get("locationMessageData", {})
        return f"Location: {location_data.get('nameLocation', 'Unknown location')}"
    elif message_type == MessageType.CONTACT:
        contact_data = message_data.get("contactMessageData", {})
        return f"Contact: {contact_data.get('displayName', 'Unknown contact')}"
    else:
        return f"[{message_type}]"


# Export main components
__all__ = [
    'GreenAPIService',
    'map_green_api_message_type',
    'extract_message_content'
]
