"""
Webhook processor for Green API webhooks
"""

from typing import Dict, Any, Optional
import structlog
from sqlalchemy.orm import Session
from datetime import datetime

from app.schemas.green_api import (
    WebhookData, WebhookType, IncomingMessageWebhook,
    OutgoingMessageStatusWebhook, StateInstanceWebhook,
    DeviceInfoWebhook, extract_phone_number
)
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType, SentimentType
from app.models.notification import StaffNotification
from app.services.green_api_service import (
    map_green_api_message_type, extract_message_content
)
from app.services.message_processor import MessageProcessor
# Removed circular imports - will use lazy imports when needed

logger = structlog.get_logger(__name__)


class WebhookProcessor:
    """Processes different types of Green API webhooks"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def process_webhook(self, hotel: Hotel, webhook_data: WebhookData) -> None:
        """
        Process webhook based on its type
        
        Args:
            hotel: Hotel instance
            webhook_data: Parsed webhook data
        """
        try:
            webhook_type = webhook_data.typeWebhook
            
            logger.info("Processing webhook",
                       hotel_id=hotel.id,
                       webhook_type=webhook_type,
                       timestamp=webhook_data.timestamp)
            
            # Route to appropriate handler
            if webhook_type == WebhookType.INCOMING_MESSAGE:
                await self._process_incoming_message(hotel, webhook_data)
            elif webhook_type == WebhookType.OUTGOING_MESSAGE:
                await self._process_outgoing_message(hotel, webhook_data)
            elif webhook_type == WebhookType.MESSAGE_STATUS:
                await self._process_message_status(hotel, webhook_data)
            elif webhook_type == WebhookType.STATE_INSTANCE:
                await self._process_state_change(hotel, webhook_data)
            elif webhook_type == WebhookType.DEVICE_INFO:
                await self._process_device_info(hotel, webhook_data)
            else:
                logger.warning("Unknown webhook type",
                             webhook_type=webhook_type,
                             hotel_id=hotel.id)
            
        except Exception as e:
            logger.error("Error processing webhook",
                        hotel_id=hotel.id,
                        webhook_type=webhook_data.typeWebhook,
                        error=str(e))
            raise
    
    async def _process_incoming_message(
        self, 
        hotel: Hotel, 
        webhook_data: IncomingMessageWebhook
    ) -> None:
        """Process incoming message webhook"""
        try:
            # Extract message information
            sender_data = webhook_data.senderData
            message_data = webhook_data.messageData
            
            # Extract phone number from chat ID
            phone_number = extract_phone_number(sender_data.chatId)
            
            # Find or create guest
            guest = self._get_or_create_guest(hotel, phone_number, sender_data)
            
            # Find or create conversation
            conversation = self._get_or_create_conversation(hotel, guest)
            
            # Extract message content
            message_content = extract_message_content(
                message_data.dict(), 
                message_data.typeMessage
            )
            
            # Create message record
            message = Message(
                hotel_id=hotel.id,
                conversation_id=conversation.id,
                message_type=MessageType.INCOMING,
                content=message_content,
                message_metadata={
                    "green_api_message_id": webhook_data.idMessage,
                    "green_api_message_type": message_data.typeMessage,
                    "chat_id": sender_data.chatId,
                    "sender": sender_data.sender,
                    "sender_name": sender_data.senderName,
                    "timestamp": webhook_data.timestamp,
                    "raw_message_data": message_data.dict()
                }
            )
            
            self.db.add(message)
            
            # Update conversation timestamp
            conversation.update_last_message_time()
            
            # Commit changes
            self.db.commit()
            
            logger.info("Incoming message processed",
                       hotel_id=hotel.id,
                       guest_id=guest.id,
                       conversation_id=conversation.id,
                       message_id=message.id,
                       green_api_message_id=webhook_data.idMessage)

            # Process message immediately for urgent cases
            processor = MessageProcessor(self.db)
            try:
                await processor.process_incoming_message(hotel, message)
                logger.info("Message processing completed",
                           hotel_id=hotel.id,
                           message_id=message.id)
            except Exception as e:
                logger.error("Error in immediate message processing",
                           hotel_id=hotel.id,
                           message_id=message.id,
                           error=str(e))
                # Fall back to async processing
                # Lazy import to avoid circular dependency
                from app.tasks.process_incoming import process_incoming_message_task
                process_incoming_message_task.delay(
                    hotel_id=str(hotel.id),
                    message_id=str(message.id)
                )
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error processing incoming message",
                        hotel_id=hotel.id,
                        error=str(e))
            raise
    
    async def _process_outgoing_message(
        self,
        hotel: Hotel,
        webhook_data: IncomingMessageWebhook  # Same structure as incoming
    ) -> None:
        """Process outgoing message webhook"""
        try:
            # For outgoing messages, we mainly want to log them
            # The actual message should already be in our database
            
            sender_data = webhook_data.senderData
            message_data = webhook_data.messageData
            
            # Try to find existing message by Green API message ID
            existing_message = self.db.query(Message).filter(
                Message.hotel_id == hotel.id,
                Message.message_metadata['green_api_message_id'].astext == webhook_data.idMessage
            ).first()
            
            if existing_message:
                # Update metadata with confirmation
                existing_message.set_metadata('confirmed_sent', True)
                existing_message.set_metadata('sent_timestamp', webhook_data.timestamp)
                self.db.commit()
                
                logger.info("Outgoing message confirmed",
                           hotel_id=hotel.id,
                           message_id=existing_message.id,
                           green_api_message_id=webhook_data.idMessage)
            else:
                logger.warning("Outgoing message not found in database",
                             hotel_id=hotel.id,
                             green_api_message_id=webhook_data.idMessage)
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error processing outgoing message",
                        hotel_id=hotel.id,
                        error=str(e))
            raise
    
    async def _process_message_status(
        self,
        hotel: Hotel,
        webhook_data: OutgoingMessageStatusWebhook
    ) -> None:
        """Process message status webhook"""
        try:
            # Find message by Green API message ID
            message = self.db.query(Message).filter(
                Message.hotel_id == hotel.id,
                Message.message_metadata['green_api_message_id'].astext == webhook_data.idMessage
            ).first()
            
            if message:
                # Update message status
                message.set_metadata('delivery_status', webhook_data.status)
                message.set_metadata('status_timestamp', webhook_data.timestamp)
                
                self.db.commit()
                
                logger.info("Message status updated",
                           hotel_id=hotel.id,
                           message_id=message.id,
                           green_api_message_id=webhook_data.idMessage,
                           status=webhook_data.status)
                
                # Queue for async processing if needed
                # Lazy import to avoid circular dependency
                from app.tasks.send_message import update_message_status_task
                update_message_status_task.delay(
                    message_id=str(message.id),
                    status=webhook_data.status
                )
            else:
                logger.warning("Message not found for status update",
                             hotel_id=hotel.id,
                             green_api_message_id=webhook_data.idMessage,
                             status=webhook_data.status)
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error processing message status",
                        hotel_id=hotel.id,
                        error=str(e))
            raise
    
    async def _process_state_change(
        self,
        hotel: Hotel,
        webhook_data: StateInstanceWebhook
    ) -> None:
        """Process instance state change webhook"""
        try:
            state = webhook_data.stateInstance
            
            # Update hotel settings with current state
            hotel.set_setting('green_api.current_state', state)
            hotel.set_setting('green_api.last_state_update', webhook_data.timestamp)
            
            self.db.commit()
            
            logger.info("Instance state updated",
                       hotel_id=hotel.id,
                       state=state,
                       timestamp=webhook_data.timestamp)
            
            # Create notification for critical state changes
            if state in ['notAuthorized', 'blocked', 'sleepMode']:
                notification = StaffNotification(
                    hotel_id=hotel.id,
                    notification_type='system_alert',
                    title=f'WhatsApp Instance State Change',
                    message=f'WhatsApp instance state changed to: {state}',
                    metadata={
                        'webhook_type': 'stateInstanceChanged',
                        'state': state,
                        'timestamp': webhook_data.timestamp
                    }
                )
                self.db.add(notification)
                self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error processing state change",
                        hotel_id=hotel.id,
                        error=str(e))
            raise
    
    async def _process_device_info(
        self,
        hotel: Hotel,
        webhook_data: DeviceInfoWebhook
    ) -> None:
        """Process device info webhook"""
        try:
            device_data = webhook_data.deviceData
            
            # Update hotel settings with device info
            hotel.set_setting('green_api.device_info', device_data)
            hotel.set_setting('green_api.last_device_update', webhook_data.timestamp)
            
            self.db.commit()
            
            logger.info("Device info updated",
                       hotel_id=hotel.id,
                       device_data=device_data,
                       timestamp=webhook_data.timestamp)
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error processing device info",
                        hotel_id=hotel.id,
                        error=str(e))
            raise
    
    def _get_or_create_guest(
        self,
        hotel: Hotel,
        phone_number: str,
        sender_data: Any
    ) -> Guest:
        """Get or create guest from sender data"""
        # Try to find existing guest
        guest = self.db.query(Guest).filter(
            Guest.hotel_id == hotel.id,
            Guest.phone_number == phone_number
        ).first()
        
        if not guest:
            # Create new guest
            guest = Guest(
                hotel_id=hotel.id,
                phone_number=phone_number,
                name=sender_data.senderName or f"Guest {phone_number}",
                metadata={
                    "chat_id": sender_data.chatId,
                    "first_contact": datetime.utcnow().isoformat(),
                    "source": "whatsapp_incoming"
                }
            )
            self.db.add(guest)
            self.db.flush()  # Get ID without committing
            
            logger.info("New guest created",
                       hotel_id=hotel.id,
                       guest_id=guest.id,
                       phone_number=phone_number)
        
        return guest
    
    def _get_or_create_conversation(self, hotel: Hotel, guest: Guest) -> Conversation:
        """Get or create conversation for guest"""
        # Try to find active conversation
        conversation = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel.id,
            Conversation.guest_id == guest.id,
            Conversation.status == 'active'
        ).first()
        
        if not conversation:
            # Create new conversation
            conversation = Conversation(
                hotel_id=hotel.id,
                guest_id=guest.id,
                status='active'
            )
            self.db.add(conversation)
            self.db.flush()  # Get ID without committing
            
            logger.info("New conversation created",
                       hotel_id=hotel.id,
                       guest_id=guest.id,
                       conversation_id=conversation.id)
        
        return conversation


# Export main class
__all__ = ['WebhookProcessor']
