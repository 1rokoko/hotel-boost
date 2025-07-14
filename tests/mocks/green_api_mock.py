"""
Mock objects for Green API testing
"""

import asyncio
import random
import time
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from app.schemas.green_api import (
    SendTextMessageRequest, SendFileRequest, SendLocationRequest,
    SendContactRequest, SendPollRequest, SetSettingsRequest,
    SendMessageResponse, GetSettingsResponse, GetStateInstanceResponse,
    MessageStatus, WebhookType
)


class GreenAPIMock:
    """Mock Green API responses and behavior"""
    
    def __init__(self):
        self.message_counter = 1000
        self.webhook_counter = 2000
        self.instance_state = "authorized"
        self.settings = {
            "wh_url": "https://example.com/webhook",
            "wh_urlToken": "webhook_token_123",
            "delaySendMessagesMilliseconds": 1000,
            "markIncomingMessagesReaded": "yes",
            "outgoingWebhook": "yes",
            "incomingWebhook": "yes"
        }
        
        # Track sent messages for webhook simulation
        self.sent_messages: List[Dict[str, Any]] = []
        
        # Simulate network delays
        self.simulate_delays = True
        self.min_delay = 0.1
        self.max_delay = 0.5
        
        # Simulate failures
        self.failure_rate = 0.0  # 0.0 = no failures, 1.0 = always fail
        self.rate_limit_enabled = False
    
    async def _simulate_delay(self):
        """Simulate network delay"""
        if self.simulate_delays:
            delay = random.uniform(self.min_delay, self.max_delay)
            await asyncio.sleep(delay)
    
    def _should_fail(self) -> bool:
        """Determine if request should fail"""
        return random.random() < self.failure_rate
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        self.message_counter += 1
        return f"mock_msg_{self.message_counter}_{int(time.time())}"
    
    def _generate_webhook_id(self) -> str:
        """Generate unique webhook ID"""
        self.webhook_counter += 1
        return f"mock_webhook_{self.webhook_counter}"
    
    async def send_text_message(self, request: SendTextMessageRequest) -> SendMessageResponse:
        """Mock send text message"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        message_id = self._generate_message_id()
        
        # Track message for webhook simulation
        self.sent_messages.append({
            "id": message_id,
            "type": "text",
            "chatId": request.chatId,
            "content": request.message,
            "timestamp": int(time.time()),
            "status": "sent"
        })
        
        return SendMessageResponse(idMessage=message_id)
    
    async def send_file_by_url(self, request: SendFileRequest) -> SendMessageResponse:
        """Mock send file message"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        message_id = self._generate_message_id()
        
        self.sent_messages.append({
            "id": message_id,
            "type": "file",
            "chatId": request.chatId,
            "fileUrl": request.urlFile,
            "fileName": request.fileName,
            "caption": request.caption,
            "timestamp": int(time.time()),
            "status": "sent"
        })
        
        return SendMessageResponse(idMessage=message_id)
    
    async def send_location(self, request: SendLocationRequest) -> SendMessageResponse:
        """Mock send location message"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        message_id = self._generate_message_id()
        
        self.sent_messages.append({
            "id": message_id,
            "type": "location",
            "chatId": request.chatId,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "name": request.nameLocation,
            "address": request.address,
            "timestamp": int(time.time()),
            "status": "sent"
        })
        
        return SendMessageResponse(idMessage=message_id)
    
    async def send_contact(self, request: SendContactRequest) -> SendMessageResponse:
        """Mock send contact message"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        message_id = self._generate_message_id()
        
        self.sent_messages.append({
            "id": message_id,
            "type": "contact",
            "chatId": request.chatId,
            "contact": request.contact,
            "timestamp": int(time.time()),
            "status": "sent"
        })
        
        return SendMessageResponse(idMessage=message_id)
    
    async def send_poll(self, request: SendPollRequest) -> SendMessageResponse:
        """Mock send poll message"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        message_id = self._generate_message_id()
        
        self.sent_messages.append({
            "id": message_id,
            "type": "poll",
            "chatId": request.chatId,
            "message": request.message,
            "options": request.options,
            "multipleAnswers": request.multipleAnswers,
            "timestamp": int(time.time()),
            "status": "sent"
        })
        
        return SendMessageResponse(idMessage=message_id)
    
    async def get_settings(self) -> GetSettingsResponse:
        """Mock get settings"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        return GetSettingsResponse(**self.settings)
    
    async def set_settings(self, request: SetSettingsRequest) -> Dict[str, Any]:
        """Mock set settings"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        # Update mock settings
        if request.webhookUrl:
            self.settings["wh_url"] = request.webhookUrl
        if request.webhookUrlToken:
            self.settings["wh_urlToken"] = request.webhookUrlToken
        if request.delaySendMessagesMilliseconds is not None:
            self.settings["delaySendMessagesMilliseconds"] = request.delaySendMessagesMilliseconds
        if request.markIncomingMessagesReaded:
            self.settings["markIncomingMessagesReaded"] = request.markIncomingMessagesReaded
        if request.outgoingWebhook:
            self.settings["outgoingWebhook"] = request.outgoingWebhook
        if request.incomingWebhook:
            self.settings["incomingWebhook"] = request.incomingWebhook
        
        return {"result": "success"}
    
    async def get_state_instance(self) -> GetStateInstanceResponse:
        """Mock get state instance"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        return GetStateInstanceResponse(stateInstance=self.instance_state)
    
    async def get_status_instance(self) -> Dict[str, Any]:
        """Mock get status instance"""
        await self._simulate_delay()
        
        if self._should_fail():
            raise Exception("Mock API failure")
        
        return {
            "statusInstance": "online" if self.instance_state == "authorized" else "offline"
        }
    
    async def receive_notification(self) -> Optional[Dict[str, Any]]:
        """Mock receive notification"""
        await self._simulate_delay()
        
        # Randomly return notification or None
        if random.random() < 0.3:  # 30% chance of notification
            return self._generate_mock_notification()
        
        return None
    
    async def delete_notification(self, receipt_id: str) -> Dict[str, Any]:
        """Mock delete notification"""
        await self._simulate_delay()
        
        return {"result": "deleted", "receiptId": receipt_id}
    
    def _generate_mock_notification(self) -> Dict[str, Any]:
        """Generate mock notification"""
        notification_types = [
            "incomingMessageReceived",
            "outgoingMessageStatus",
            "stateInstanceChanged"
        ]
        
        notification_type = random.choice(notification_types)
        
        if notification_type == "incomingMessageReceived":
            return {
                "receiptId": self._generate_webhook_id(),
                "body": {
                    "typeWebhook": "incomingMessageReceived",
                    "instanceData": {"idInstance": "1234567890"},
                    "timestamp": int(time.time()),
                    "idMessage": self._generate_message_id(),
                    "senderData": {
                        "chatId": "1234567890@c.us",
                        "sender": "1234567890@c.us",
                        "senderName": "Mock Guest"
                    },
                    "messageData": {
                        "typeMessage": "textMessage",
                        "textMessageData": {
                            "textMessage": random.choice([
                                "Hello, I need help!",
                                "What time is breakfast?",
                                "My room is too cold",
                                "Thank you for the great service!"
                            ])
                        }
                    }
                }
            }
        
        elif notification_type == "outgoingMessageStatus":
            if self.sent_messages:
                message = random.choice(self.sent_messages)
                return {
                    "receiptId": self._generate_webhook_id(),
                    "body": {
                        "typeWebhook": "outgoingMessageStatus",
                        "instanceData": {"idInstance": "1234567890"},
                        "timestamp": int(time.time()),
                        "idMessage": message["id"],
                        "status": random.choice(["delivered", "read"]),
                        "chatId": message["chatId"]
                    }
                }
        
        elif notification_type == "stateInstanceChanged":
            return {
                "receiptId": self._generate_webhook_id(),
                "body": {
                    "typeWebhook": "stateInstanceChanged",
                    "instanceData": {"idInstance": "1234567890"},
                    "timestamp": int(time.time()),
                    "stateInstance": random.choice(["authorized", "notAuthorized", "blocked"])
                }
            }
        
        return None
    
    def generate_incoming_webhook(
        self,
        chat_id: str = "1234567890@c.us",
        message: str = "Test incoming message",
        sender_name: str = "Test Guest"
    ) -> Dict[str, Any]:
        """Generate incoming message webhook for testing"""
        return {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {"idInstance": "1234567890"},
            "timestamp": int(time.time()),
            "idMessage": self._generate_message_id(),
            "senderData": {
                "chatId": chat_id,
                "sender": chat_id,
                "senderName": sender_name
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {"textMessage": message}
            }
        }
    
    def generate_status_webhook(
        self,
        message_id: str,
        status: str = "delivered",
        chat_id: str = "1234567890@c.us"
    ) -> Dict[str, Any]:
        """Generate message status webhook for testing"""
        return {
            "typeWebhook": "outgoingMessageStatus",
            "instanceData": {"idInstance": "1234567890"},
            "timestamp": int(time.time()),
            "idMessage": message_id,
            "status": status,
            "chatId": chat_id
        }
    
    def set_failure_rate(self, rate: float):
        """Set failure rate for testing error scenarios"""
        self.failure_rate = max(0.0, min(1.0, rate))
    
    def set_instance_state(self, state: str):
        """Set instance state for testing"""
        self.instance_state = state
    
    def enable_rate_limiting(self, enabled: bool = True):
        """Enable/disable rate limiting simulation"""
        self.rate_limit_enabled = enabled
    
    def clear_sent_messages(self):
        """Clear sent messages history"""
        self.sent_messages.clear()
    
    def get_sent_messages(self) -> List[Dict[str, Any]]:
        """Get list of sent messages"""
        return self.sent_messages.copy()


class MockGreenAPIClient:
    """Mock Green API client for testing"""
    
    def __init__(self, config=None):
        self.config = config
        self.mock_api = GreenAPIMock()
        self._client = None
        
        # Metrics
        self.request_count = 0
        self.error_count = 0
        self.last_request_time = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self):
        """Start mock client"""
        self._client = Mock()
    
    async def close(self):
        """Close mock client"""
        self._client = None
    
    async def _track_request(self):
        """Track request metrics"""
        self.request_count += 1
        self.last_request_time = datetime.utcnow()
    
    async def send_text_message(self, request: SendTextMessageRequest) -> SendMessageResponse:
        """Mock send text message"""
        await self._track_request()
        try:
            return await self.mock_api.send_text_message(request)
        except Exception as e:
            self.error_count += 1
            raise
    
    async def send_file_by_url(self, request: SendFileRequest) -> SendMessageResponse:
        """Mock send file message"""
        await self._track_request()
        try:
            return await self.mock_api.send_file_by_url(request)
        except Exception as e:
            self.error_count += 1
            raise
    
    async def send_location(self, request: SendLocationRequest) -> SendMessageResponse:
        """Mock send location message"""
        await self._track_request()
        try:
            return await self.mock_api.send_location(request)
        except Exception as e:
            self.error_count += 1
            raise
    
    async def send_contact(self, request: SendContactRequest) -> SendMessageResponse:
        """Mock send contact message"""
        await self._track_request()
        try:
            return await self.mock_api.send_contact(request)
        except Exception as e:
            self.error_count += 1
            raise
    
    async def send_poll(self, request: SendPollRequest) -> SendMessageResponse:
        """Mock send poll message"""
        await self._track_request()
        try:
            return await self.mock_api.send_poll(request)
        except Exception as e:
            self.error_count += 1
            raise
    
    async def get_settings(self) -> GetSettingsResponse:
        """Mock get settings"""
        await self._track_request()
        try:
            return await self.mock_api.get_settings()
        except Exception as e:
            self.error_count += 1
            raise
    
    async def set_settings(self, request: SetSettingsRequest) -> Dict[str, Any]:
        """Mock set settings"""
        await self._track_request()
        try:
            return await self.mock_api.set_settings(request)
        except Exception as e:
            self.error_count += 1
            raise
    
    async def get_state_instance(self) -> GetStateInstanceResponse:
        """Mock get state instance"""
        await self._track_request()
        try:
            return await self.mock_api.get_state_instance()
        except Exception as e:
            self.error_count += 1
            raise
    
    async def get_status_instance(self) -> Dict[str, Any]:
        """Mock get status instance"""
        await self._track_request()
        try:
            return await self.mock_api.get_status_instance()
        except Exception as e:
            self.error_count += 1
            raise
    
    async def receive_notification(self) -> Optional[Dict[str, Any]]:
        """Mock receive notification"""
        await self._track_request()
        try:
            return await self.mock_api.receive_notification()
        except Exception as e:
            self.error_count += 1
            raise
    
    async def delete_notification(self, receipt_id: str) -> Dict[str, Any]:
        """Mock delete notification"""
        await self._track_request()
        try:
            return await self.mock_api.delete_notification(receipt_id)
        except Exception as e:
            self.error_count += 1
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics"""
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "instance_id": self.config.instance_id if self.config else "mock_instance"
        }


# Export main components
__all__ = [
    'GreenAPIMock',
    'MockGreenAPIClient'
]
