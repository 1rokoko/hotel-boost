"""
Message sender service for WhatsApp Hotel Bot
"""

from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType
from app.models.message_queue import MessageQueue, MessageStatus as QueueStatus
from app.services.green_api_service import GreenAPIService
from app.schemas.green_api import SendMessageResponse
# Removed circular import - will use lazy import when needed

logger = structlog.get_logger(__name__)


class MessageSender:
    """Service for sending messages through Green API with queue management"""
    
    def __init__(self, db: Session):
        self.db = db
        self.green_api_service = GreenAPIService(db)
    
    async def send_text_message(
        self,
        hotel: Hotel,
        guest: Guest,
        message: str,
        priority: str = "normal",
        schedule_at: Optional[datetime] = None,
        quoted_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send text message to guest
        
        Args:
            hotel: Hotel instance
            guest: Guest instance
            message: Message text
            priority: Message priority (high, normal, low)
            schedule_at: Optional scheduled send time
            quoted_message_id: Optional message ID to quote
            
        Returns:
            Dict with message info and queue status
        """
        try:
            # Create conversation if needed
            conversation = self._get_or_create_conversation(hotel, guest)
            
            # Create message record
            message_record = Message(
                hotel_id=hotel.id,
                conversation_id=conversation.id,
                message_type=MessageType.OUTGOING,
                content=message,
                message_metadata={
                    "message_type": "text",
                    "priority": priority,
                    "quoted_message_id": quoted_message_id,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            self.db.add(message_record)
            self.db.flush()  # Get ID
            
            # Queue message for sending
            queue_entry = self._queue_message(
                hotel=hotel,
                guest=guest,
                message_record=message_record,
                priority=priority,
                schedule_at=schedule_at
            )
            
            # Send immediately if not scheduled
            if not schedule_at:
                result = await self._send_message_now(hotel, guest, message_record, queue_entry)
            else:
                result = {
                    "status": "scheduled",
                    "message_id": str(message_record.id),
                    "queue_id": str(queue_entry.id),
                    "scheduled_at": schedule_at.isoformat()
                }
            
            self.db.commit()
            
            logger.info("Text message queued/sent",
                       hotel_id=hotel.id,
                       guest_id=guest.id,
                       message_id=message_record.id,
                       queue_id=queue_entry.id,
                       priority=priority,
                       scheduled=bool(schedule_at))
            
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error sending text message",
                        hotel_id=hotel.id,
                        guest_id=guest.id,
                        error=str(e))
            raise
    
    async def send_file_message(
        self,
        hotel: Hotel,
        guest: Guest,
        file_url: str,
        file_name: str,
        caption: Optional[str] = None,
        priority: str = "normal",
        schedule_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Send file message to guest"""
        try:
            conversation = self._get_or_create_conversation(hotel, guest)
            
            # Create message record
            message_record = Message(
                hotel_id=hotel.id,
                conversation_id=conversation.id,
                message_type=MessageType.OUTGOING,
                content=caption or f"[File: {file_name}]",
                message_metadata={
                    "message_type": "file",
                    "file_url": file_url,
                    "file_name": file_name,
                    "caption": caption,
                    "priority": priority,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            self.db.add(message_record)
            self.db.flush()
            
            # Queue message
            queue_entry = self._queue_message(
                hotel=hotel,
                guest=guest,
                message_record=message_record,
                priority=priority,
                schedule_at=schedule_at
            )
            
            # Send immediately if not scheduled
            if not schedule_at:
                result = await self._send_file_now(hotel, guest, message_record, queue_entry)
            else:
                result = {
                    "status": "scheduled",
                    "message_id": str(message_record.id),
                    "queue_id": str(queue_entry.id),
                    "scheduled_at": schedule_at.isoformat()
                }
            
            self.db.commit()
            
            logger.info("File message queued/sent",
                       hotel_id=hotel.id,
                       guest_id=guest.id,
                       message_id=message_record.id,
                       file_name=file_name)
            
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error sending file message",
                        hotel_id=hotel.id,
                        guest_id=guest.id,
                        error=str(e))
            raise
    
    async def send_location_message(
        self,
        hotel: Hotel,
        guest: Guest,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """Send location message to guest"""
        try:
            conversation = self._get_or_create_conversation(hotel, guest)
            
            # Create message record
            message_record = Message(
                hotel_id=hotel.id,
                conversation_id=conversation.id,
                message_type=MessageType.OUTGOING,
                content=f"Location: {name or 'Shared location'}",
                message_metadata={
                    "message_type": "location",
                    "latitude": latitude,
                    "longitude": longitude,
                    "name": name,
                    "address": address,
                    "priority": priority,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            self.db.add(message_record)
            self.db.flush()
            
            # Queue and send immediately (locations are usually urgent)
            queue_entry = self._queue_message(
                hotel=hotel,
                guest=guest,
                message_record=message_record,
                priority=priority
            )
            
            result = await self._send_location_now(hotel, guest, message_record, queue_entry)
            
            self.db.commit()
            
            logger.info("Location message sent",
                       hotel_id=hotel.id,
                       guest_id=guest.id,
                       message_id=message_record.id)
            
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error sending location message",
                        hotel_id=hotel.id,
                        guest_id=guest.id,
                        error=str(e))
            raise
    
    async def retry_failed_message(self, queue_id: str) -> Dict[str, Any]:
        """Retry a failed message"""
        try:
            queue_entry = self.db.query(MessageQueue).filter(
                MessageQueue.id == queue_id
            ).first()
            
            if not queue_entry:
                raise ValueError(f"Queue entry not found: {queue_id}")
            
            if queue_entry.status != QueueStatus.FAILED:
                raise ValueError(f"Message is not in failed status: {queue_entry.status}")
            
            # Reset status and increment retry count
            queue_entry.status = QueueStatus.PENDING
            queue_entry.retry_count += 1
            queue_entry.last_attempt_at = datetime.utcnow()
            
            # Get related objects
            hotel = self.db.query(Hotel).filter(Hotel.id == queue_entry.hotel_id).first()
            guest = self.db.query(Guest).filter(Guest.id == queue_entry.guest_id).first()
            message = self.db.query(Message).filter(Message.id == queue_entry.message_id).first()
            
            if not all([hotel, guest, message]):
                raise ValueError("Related objects not found")
            
            # Retry sending
            message_type = message.get_metadata("message_type", "text")
            
            if message_type == "text":
                result = await self._send_message_now(hotel, guest, message, queue_entry)
            elif message_type == "file":
                result = await self._send_file_now(hotel, guest, message, queue_entry)
            elif message_type == "location":
                result = await self._send_location_now(hotel, guest, message, queue_entry)
            else:
                raise ValueError(f"Unknown message type: {message_type}")
            
            self.db.commit()
            
            logger.info("Message retry completed",
                       queue_id=queue_id,
                       hotel_id=hotel.id,
                       retry_count=queue_entry.retry_count)
            
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error retrying message",
                        queue_id=queue_id,
                        error=str(e))
            raise
    
    def _get_or_create_conversation(self, hotel: Hotel, guest: Guest) -> Conversation:
        """Get or create conversation for guest"""
        conversation = self.db.query(Conversation).filter(
            Conversation.hotel_id == hotel.id,
            Conversation.guest_id == guest.id,
            Conversation.status == 'active'
        ).first()
        
        if not conversation:
            conversation = Conversation(
                hotel_id=hotel.id,
                guest_id=guest.id,
                status='active'
            )
            self.db.add(conversation)
            self.db.flush()
        
        return conversation
    
    def _queue_message(
        self,
        hotel: Hotel,
        guest: Guest,
        message_record: Message,
        priority: str = "normal",
        schedule_at: Optional[datetime] = None
    ) -> MessageQueue:
        """Queue message for sending"""
        queue_entry = MessageQueue(
            hotel_id=hotel.id,
            guest_id=guest.id,
            message_id=message_record.id,
            phone_number=guest.phone_number,
            priority=priority,
            status=QueueStatus.SCHEDULED if schedule_at else QueueStatus.PENDING,
            scheduled_at=schedule_at,
            message_data={
                "message_type": message_record.get_metadata("message_type"),
                "content": message_record.content,
                "metadata": message_record.message_metadata
            }
        )
        
        self.db.add(queue_entry)
        self.db.flush()
        
        return queue_entry
    
    async def _send_message_now(
        self,
        hotel: Hotel,
        guest: Guest,
        message: Message,
        queue_entry: MessageQueue
    ) -> Dict[str, Any]:
        """Send text message immediately"""
        try:
            queue_entry.status = QueueStatus.SENDING
            queue_entry.last_attempt_at = datetime.utcnow()
            
            # Send through Green API
            response = await self.green_api_service.send_text_message(
                hotel=hotel,
                phone_number=guest.phone_number,
                message=message.content,
                quoted_message_id=message.get_metadata("quoted_message_id")
            )
            
            # Update records
            queue_entry.status = QueueStatus.SENT
            queue_entry.sent_at = datetime.utcnow()
            queue_entry.green_api_message_id = response.idMessage
            
            message.set_metadata("green_api_message_id", response.idMessage)
            message.set_metadata("sent_at", datetime.utcnow().isoformat())
            
            return {
                "status": "sent",
                "message_id": str(message.id),
                "green_api_message_id": response.idMessage,
                "queue_id": str(queue_entry.id)
            }
            
        except Exception as e:
            queue_entry.status = QueueStatus.FAILED
            queue_entry.error_message = str(e)
            queue_entry.retry_count += 1
            
            logger.error("Failed to send message",
                        hotel_id=hotel.id,
                        message_id=message.id,
                        error=str(e))
            
            # Schedule retry if under limit
            if queue_entry.retry_count < 3:
                # Lazy import to avoid circular dependency
                from app.tasks.send_message import send_message_task
                send_message_task.apply_async(
                    args=[str(hotel.id), guest.phone_number, message.content],
                    countdown=60 * (2 ** queue_entry.retry_count)  # Exponential backoff
                )
            
            raise
    
    async def _send_file_now(
        self,
        hotel: Hotel,
        guest: Guest,
        message: Message,
        queue_entry: MessageQueue
    ) -> Dict[str, Any]:
        """Send file message immediately"""
        try:
            queue_entry.status = QueueStatus.SENDING
            queue_entry.last_attempt_at = datetime.utcnow()
            
            # Send through Green API
            response = await self.green_api_service.send_file_message(
                hotel=hotel,
                phone_number=guest.phone_number,
                file_url=message.get_metadata("file_url"),
                file_name=message.get_metadata("file_name"),
                caption=message.get_metadata("caption")
            )
            
            # Update records
            queue_entry.status = QueueStatus.SENT
            queue_entry.sent_at = datetime.utcnow()
            queue_entry.green_api_message_id = response.idMessage
            
            message.set_metadata("green_api_message_id", response.idMessage)
            message.set_metadata("sent_at", datetime.utcnow().isoformat())
            
            return {
                "status": "sent",
                "message_id": str(message.id),
                "green_api_message_id": response.idMessage,
                "queue_id": str(queue_entry.id)
            }
            
        except Exception as e:
            queue_entry.status = QueueStatus.FAILED
            queue_entry.error_message = str(e)
            queue_entry.retry_count += 1
            raise
    
    async def _send_location_now(
        self,
        hotel: Hotel,
        guest: Guest,
        message: Message,
        queue_entry: MessageQueue
    ) -> Dict[str, Any]:
        """Send location message immediately"""
        try:
            queue_entry.status = QueueStatus.SENDING
            queue_entry.last_attempt_at = datetime.utcnow()
            
            # Send through Green API
            response = await self.green_api_service.send_location_message(
                hotel=hotel,
                phone_number=guest.phone_number,
                latitude=message.get_metadata("latitude"),
                longitude=message.get_metadata("longitude"),
                name=message.get_metadata("name"),
                address=message.get_metadata("address")
            )
            
            # Update records
            queue_entry.status = QueueStatus.SENT
            queue_entry.sent_at = datetime.utcnow()
            queue_entry.green_api_message_id = response.idMessage
            
            message.set_metadata("green_api_message_id", response.idMessage)
            message.set_metadata("sent_at", datetime.utcnow().isoformat())
            
            return {
                "status": "sent",
                "message_id": str(message.id),
                "green_api_message_id": response.idMessage,
                "queue_id": str(queue_entry.id)
            }
            
        except Exception as e:
            queue_entry.status = QueueStatus.FAILED
            queue_entry.error_message = str(e)
            queue_entry.retry_count += 1
            raise


# Export main class
__all__ = ['MessageSender']
