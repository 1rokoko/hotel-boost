# Task 003: Green API WhatsApp Integration

## Overview
**Priority:** High | **Complexity:** High | **Estimated Hours:** 16
**Dependencies:** Task 001, Task 002 | **Phase:** Core

## Description
Implement core WhatsApp messaging functionality using Green API for sending/receiving messages, handling webhooks, and managing message status.

## Detailed Implementation Plan

### 1. Green API Client Setup

```python
# app/services/whatsapp.py
import httpx
import asyncio
from typing import Optional, Dict, Any
from app.core.config import settings
from app.models.hotel import Hotel

class GreenAPIClient:
    def __init__(self, instance_id: str, token: str):
        self.instance_id = instance_id
        self.token = token
        self.base_url = f"https://api.green-api.com/waInstance{instance_id}"
        self.timeout = httpx.Timeout(30.0)
        
    async def send_text_message(self, phone: str, message: str) -> Dict[str, Any]:
        """Send text message to WhatsApp number"""
        url = f"{self.base_url}/sendMessage/{self.token}"
        
        payload = {
            "chatId": f"{phone}@c.us",
            "message": message
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                # Log error and handle appropriately
                raise WhatsAppAPIError(f"Failed to send message: {e}")
    
    async def send_media_message(self, phone: str, media_url: str, caption: str = "") -> Dict[str, Any]:
        """Send media message (image, video, audio)"""
        url = f"{self.base_url}/sendFileByUrl/{self.token}"
        
        payload = {
            "chatId": f"{phone}@c.us",
            "urlFile": media_url,
            "fileName": "media_file",
            "caption": caption
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """Check message delivery status"""
        url = f"{self.base_url}/getMessageStatus/{self.token}"
        
        payload = {"idMessage": message_id}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def setup_webhook(self, webhook_url: str) -> bool:
        """Configure webhook URL for incoming messages"""
        url = f"{self.base_url}/setSettings/{self.token}"
        
        payload = {
            "webhookUrl": webhook_url,
            "webhookUrlToken": settings.WEBHOOK_TOKEN,
            "outgoingWebhook": "yes",
            "incomingWebhook": "yes"
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            return response.status_code == 200

# Custom exceptions
class WhatsAppAPIError(Exception):
    pass

class MessageDeliveryError(Exception):
    pass
```

### 2. WhatsApp Service Layer

```python
# app/services/whatsapp_service.py
from sqlalchemy.orm import Session
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.conversation import Conversation
from app.services.whatsapp import GreenAPIClient
from app.core.database import get_db

class WhatsAppService:
    def __init__(self, db: Session):
        self.db = db
        self._clients = {}  # Cache for API clients
    
    def get_client(self, hotel: Hotel) -> GreenAPIClient:
        """Get or create Green API client for hotel"""
        if hotel.id not in self._clients:
            self._clients[hotel.id] = GreenAPIClient(
                instance_id=hotel.green_api_instance,
                token=hotel.green_api_token
            )
        return self._clients[hotel.id]
    
    async def send_message_to_guest(
        self, 
        hotel_id: int, 
        guest_id: int, 
        message: str,
        message_type: str = "text"
    ) -> bool:
        """Send message to specific guest"""
        
        # Get hotel and guest
        hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
        guest = self.db.query(Guest).filter(
            Guest.id == guest_id,
            Guest.hotel_id == hotel_id
        ).first()
        
        if not hotel or not guest:
            raise ValueError("Hotel or guest not found")
        
        # Get WhatsApp client
        client = self.get_client(hotel)
        
        try:
            # Send message
            result = await client.send_text_message(guest.phone_number, message)
            
            # Store conversation record
            conversation = Conversation(
                guest_id=guest.id,
                message_id=result.get("idMessage"),
                direction="outbound",
                message_type=message_type,
                content=message,
                timestamp=datetime.utcnow()
            )
            
            self.db.add(conversation)
            self.db.commit()
            
            return True
            
        except WhatsAppAPIError as e:
            # Log error and handle
            logger.error(f"Failed to send message to guest {guest_id}: {e}")
            return False
    
    async def process_incoming_message(self, webhook_data: Dict[str, Any]) -> bool:
        """Process incoming WhatsApp message from webhook"""
        
        try:
            # Extract message data
            message_data = webhook_data.get("messageData", {})
            sender_data = webhook_data.get("senderData", {})
            
            phone_number = sender_data.get("sender", "").replace("@c.us", "")
            message_text = message_data.get("textMessageData", {}).get("textMessage", "")
            message_id = message_data.get("idMessage")
            message_type = message_data.get("typeMessage", "textMessage")
            
            # Find guest by phone number
            guest = self.db.query(Guest).filter(
                Guest.phone_number == phone_number
            ).first()
            
            if not guest:
                # Handle unknown guest - could create new guest or ignore
                logger.warning(f"Received message from unknown number: {phone_number}")
                return False
            
            # Store conversation
            conversation = Conversation(
                guest_id=guest.id,
                message_id=message_id,
                direction="inbound",
                message_type=message_type,
                content=message_text,
                timestamp=datetime.utcnow()
            )
            
            self.db.add(conversation)
            self.db.commit()
            
            # Trigger sentiment analysis (async task)
            from app.tasks.sentiment_tasks import analyze_message_sentiment
            analyze_message_sentiment.delay(conversation.id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing incoming message: {e}")
            return False
```

### 3. Webhook Endpoints

```python
# app/api/v1/endpoints/webhooks.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.whatsapp_service import WhatsAppService
from app.core.security import verify_webhook_signature

router = APIRouter()

@router.post("/whatsapp/webhook")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle incoming WhatsApp messages"""
    
    # Verify webhook signature for security
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature")
    
    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse webhook data
    webhook_data = await request.json()
    
    # Process message
    whatsapp_service = WhatsAppService(db)
    success = await whatsapp_service.process_incoming_message(webhook_data)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to process message")
    
    return {"status": "success"}

@router.post("/whatsapp/send")
async def send_message(
    hotel_id: int,
    guest_id: int,
    message: str,
    db: Session = Depends(get_db)
):
    """Send message to guest (for testing/manual sending)"""
    
    whatsapp_service = WhatsAppService(db)
    success = await whatsapp_service.send_message_to_guest(
        hotel_id=hotel_id,
        guest_id=guest_id,
        message=message
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to send message")
    
    return {"status": "sent"}

@router.get("/whatsapp/status/{message_id}")
async def get_message_status(
    message_id: str,
    hotel_id: int,
    db: Session = Depends(get_db)
):
    """Get message delivery status"""
    
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    whatsapp_service = WhatsAppService(db)
    client = whatsapp_service.get_client(hotel)
    
    try:
        status = await client.get_message_status(message_id)
        return status
    except WhatsAppAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 4. Message Status Tracking

```python
# app/tasks/whatsapp_tasks.py
from celery import Celery
from app.core.database import SessionLocal
from app.models.conversation import Conversation
from app.services.whatsapp_service import WhatsAppService

@celery.task(bind=True, max_retries=3)
def update_message_status(self, conversation_id: int):
    """Update message delivery status"""
    
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation or conversation.direction != "outbound":
            return
        
        # Get hotel and WhatsApp client
        hotel = conversation.guest.hotel
        whatsapp_service = WhatsAppService(db)
        client = whatsapp_service.get_client(hotel)
        
        # Check message status
        status = await client.get_message_status(conversation.message_id)
        
        # Update conversation with status
        conversation.delivery_status = status.get("status")
        conversation.delivered_at = datetime.utcnow() if status.get("status") == "delivered" else None
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to update message status: {e}")
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()
```

### 5. Error Handling and Retry Logic

```python
# app/utils/retry.py
import asyncio
from functools import wraps
from typing import Callable, Any

def async_retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for async function retry with exponential backoff"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (backoff ** attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    break
            
            raise last_exception
        
        return wrapper
    return decorator

# Usage in WhatsApp client
class GreenAPIClient:
    @async_retry(max_retries=3, delay=1.0, backoff=2.0)
    async def send_text_message(self, phone: str, message: str):
        # Implementation with automatic retry
        pass
```

## Test Strategy

### 1. Unit Tests
```python
# tests/test_whatsapp_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.whatsapp_service import WhatsAppService

@pytest.mark.asyncio
async def test_send_message_success():
    """Test successful message sending"""
    # Mock database and API responses
    # Verify message is sent and stored correctly

@pytest.mark.asyncio
async def test_webhook_processing():
    """Test incoming message processing"""
    # Mock webhook data
    # Verify conversation is created and sentiment analysis triggered

@pytest.mark.asyncio
async def test_api_error_handling():
    """Test API error handling and retries"""
    # Mock API failures
    # Verify proper error handling and retry logic
```

### 2. Integration Tests
```python
# tests/test_whatsapp_integration.py
@pytest.mark.asyncio
async def test_end_to_end_message_flow():
    """Test complete message flow from sending to status update"""
    # Test with real API (in test environment)
    # Verify all components work together
```

## Acceptance Criteria
- [ ] Green API client successfully sends text messages
- [ ] Webhook endpoint processes incoming messages
- [ ] Message status tracking works correctly
- [ ] Error handling and retry logic implemented
- [ ] Multi-tenant support (different API credentials per hotel)
- [ ] Message history stored in database
- [ ] Async processing for performance
- [ ] Security measures for webhook verification

## Performance Requirements
- Message sending: <2 seconds response time
- Webhook processing: <500ms
- Support for 1000+ messages per minute
- Graceful handling of API rate limits

## Security Considerations
- Webhook signature verification
- API credential encryption in database
- Rate limiting per hotel
- Input validation for all endpoints

## Related Modules
- WhatsApp
- Messaging
- Webhooks
- API Integration

## Next Steps
After completion, proceed to Task 004: DeepSeek AI Integration
