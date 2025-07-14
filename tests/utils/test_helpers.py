"""
Test utilities and helpers for Hotel WhatsApp Bot
Advanced testing utilities for comprehensive test coverage
"""

import asyncio
import time
import random
import string
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import Mock, AsyncMock, patch
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType
from app.models.user import User
from app.core.security import get_password_hash


fake = Faker()


@dataclass
class PerformanceMetrics:
    """Performance metrics tracking"""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None

    def finish(self, success: bool = True, error_message: Optional[str] = None):
        """Mark operation as finished"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error_message = error_message


class PerformanceTracker:
    """Track performance metrics during tests"""

    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.active_operations: Dict[str, PerformanceMetrics] = {}

    def start_operation(self, name: str) -> PerformanceMetrics:
        """Start tracking an operation"""
        metric = PerformanceMetrics(
            operation_name=name,
            start_time=time.time()
        )
        self.active_operations[name] = metric
        return metric

    def end_operation(self, name: str, success: bool = True, error_message: Optional[str] = None):
        """End tracking an operation"""
        if name in self.active_operations:
            metric = self.active_operations.pop(name)
            metric.finish(success, error_message)
            self.metrics.append(metric)
            return metric
        return None

    def get_metrics(self) -> List[PerformanceMetrics]:
        """Get all recorded metrics"""
        return self.metrics.copy()

    def get_average_duration(self, operation_name: str) -> Optional[float]:
        """Get average duration for an operation"""
        durations = [
            m.duration for m in self.metrics
            if m.operation_name == operation_name and m.duration is not None
        ]
        return sum(durations) / len(durations) if durations else None

    def get_success_rate(self, operation_name: str) -> float:
        """Get success rate for an operation"""
        operations = [m for m in self.metrics if m.operation_name == operation_name]
        if not operations:
            return 0.0
        successful = sum(1 for m in operations if m.success)
        return successful / len(operations)

    def clear(self):
        """Clear all metrics"""
        self.metrics.clear()
        self.active_operations.clear()


class TestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_user_data(email: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Create user test data"""
        return {
            "email": email or fake.email(),
            "hashed_password": get_password_hash("test_password"),
            "is_active": True,
            "is_superuser": False,
            **kwargs
        }

    @staticmethod
    def create_hotel_data(owner_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Create hotel test data"""
        return {
            "name": fake.company(),
            "whatsapp_number": f"+{fake.random_number(digits=12)}",
            "green_api_instance_id": f"instance_{fake.random_number(digits=10)}",
            "green_api_token": fake.uuid4(),
            "green_api_webhook_token": fake.uuid4(),
            "owner_id": owner_id,
            "settings": {
                "welcome_message": "Welcome to our hotel!",
                "business_hours": "9:00-18:00",
                "auto_reply": True
            },
            **kwargs
        }

    @staticmethod
    def create_guest_data(hotel_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Create guest test data"""
        return {
            "hotel_id": hotel_id,
            "phone": f"+{fake.random_number(digits=12)}",
            "name": fake.name(),
            "email": fake.email(),
            "language": "en",
            "preferences": {
                "room_type": "standard",
                "notifications": True
            },
            **kwargs
        }

    @staticmethod
    def create_message_data(
        conversation_id: Optional[str] = None,
        guest_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create message test data"""
        return {
            "conversation_id": conversation_id,
            "guest_id": guest_id,
            "content": fake.text(max_nb_chars=200),
            "message_type": MessageType.INCOMING,
            "green_api_message_id": f"msg_{fake.random_number(digits=10)}",
            **kwargs
        }

    @staticmethod
    def create_webhook_data(
        instance_id: str,
        chat_id: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create webhook test data"""
        return {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {
                "idInstance": instance_id,
                "wid": f"{instance_id}@c.us",
                "typeInstance": "whatsapp"
            },
            "timestamp": int(time.time()),
            "idMessage": f"incoming_{fake.random_number(digits=10)}",
            "senderData": {
                "chatId": chat_id or f"{fake.random_number(digits=12)}@c.us",
                "sender": chat_id or f"{fake.random_number(digits=12)}@c.us",
                "senderName": fake.name()
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {
                    "textMessage": message or fake.text(max_nb_chars=100)
                }
            },
            **kwargs
        }


class MockServiceManager:
    """Manage mock services for testing"""

    def __init__(self):
        self.active_mocks: Dict[str, Mock] = {}
        self.patches: List[Any] = []

    def create_green_api_mock(self, **config) -> Mock:
        """Create Green API mock"""
        mock = AsyncMock()
        mock.send_text_message = AsyncMock(return_value={
            "idMessage": f"mock_msg_{int(time.time())}",
            "statusMessage": "sent"
        })
        mock.get_settings = AsyncMock(return_value={
            "wh_url": "https://example.com/webhook",
            "wh_urlToken": "test_token"
        })
        mock.get_state_instance = AsyncMock(return_value={
            "stateInstance": "authorized"
        })

        # Apply custom configuration
        for key, value in config.items():
            setattr(mock, key, value)

        self.active_mocks["green_api"] = mock
        return mock

    def create_deepseek_mock(self, **config) -> Mock:
        """Create DeepSeek mock"""
        mock = AsyncMock()
        mock.analyze_sentiment = AsyncMock(return_value={
            "sentiment": "neutral",
            "confidence": 0.8,
            "requires_attention": False,
            "reasoning": "Test sentiment analysis"
        })
        mock.generate_response = AsyncMock(return_value={
            "response": "Thank you for your message. How can I help you?",
            "confidence": 0.85,
            "suggested_actions": ["offer_assistance"]
        })

        # Apply custom configuration
        for key, value in config.items():
            setattr(mock, key, value)

        self.active_mocks["deepseek"] = mock
        return mock

    def patch_service(self, service_path: str, mock_object: Mock):
        """Patch a service with mock"""
        patcher = patch(service_path, return_value=mock_object)
        self.patches.append(patcher)
        return patcher.start()

    def start_all_patches(self):
        """Start all registered patches"""
        for patcher in self.patches:
            if not patcher.is_local:
                patcher.start()

    def stop_all_patches(self):
        """Stop all patches"""
        for patcher in self.patches:
            try:
                patcher.stop()
            except RuntimeError:
                pass  # Already stopped
        self.patches.clear()
        self.active_mocks.clear()


class DatabaseTestHelper:
    """Helper for database operations in tests"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_test_user(self, **kwargs) -> User:
        """Create a test user"""
        user_data = TestDataFactory.create_user_data(**kwargs)
        user = User(**user_data)
        self.session.add(user)
        await self.session.flush()
        return user

    async def create_test_hotel(self, owner_id: Optional[str] = None, **kwargs) -> Hotel:
        """Create a test hotel"""
        if owner_id is None:
            user = await self.create_test_user()
            owner_id = user.id

        hotel_data = TestDataFactory.create_hotel_data(owner_id=owner_id, **kwargs)
        hotel = Hotel(**hotel_data)
        self.session.add(hotel)
        await self.session.flush()
        return hotel

    async def create_test_guest(self, hotel_id: Optional[str] = None, **kwargs) -> Guest:
        """Create a test guest"""
        if hotel_id is None:
            hotel = await self.create_test_hotel()
            hotel_id = hotel.id

        guest_data = TestDataFactory.create_guest_data(hotel_id=hotel_id, **kwargs)
        guest = Guest(**guest_data)
        self.session.add(guest)
        await self.session.flush()
        return guest

    async def create_test_conversation(
        self,
        hotel_id: Optional[str] = None,
        guest_id: Optional[str] = None,
        **kwargs
    ) -> Conversation:
        """Create a test conversation"""
        if hotel_id is None or guest_id is None:
            guest = await self.create_test_guest()
            hotel_id = guest.hotel_id
            guest_id = guest.id

        conversation = Conversation(
            hotel_id=hotel_id,
            guest_id=guest_id,
            started_at=datetime.utcnow(),
            **kwargs
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def create_test_message(
        self,
        conversation_id: Optional[str] = None,
        guest_id: Optional[str] = None,
        **kwargs
    ) -> Message:
        """Create a test message"""
        if conversation_id is None or guest_id is None:
            conversation = await self.create_test_conversation()
            conversation_id = conversation.id
            guest_id = conversation.guest_id

        message_data = TestDataFactory.create_message_data(
            conversation_id=conversation_id,
            guest_id=guest_id,
            **kwargs
        )
        message = Message(**message_data)
        self.session.add(message)
        await self.session.flush()
        return message

    async def cleanup_test_data(self):
        """Clean up test data"""
        await self.session.rollback()


def generate_random_string(length: int = 10) -> str:
    """Generate random string"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_phone_number() -> str:
    """Generate random phone number"""
    return f"+{random.randint(1000000000, 9999999999)}"


def generate_chat_id() -> str:
    """Generate WhatsApp chat ID"""
    return f"{random.randint(1000000000, 9999999999)}@c.us"


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1
) -> bool:
    """Wait for a condition to become true"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    return False


@asynccontextmanager
async def temporary_env_vars(**env_vars):
    """Temporarily set environment variables"""
    import os
    original_values = {}

    # Set new values and store originals
    for key, value in env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = str(value)

    try:
        yield
    finally:
        # Restore original values
        for key, original_value in original_values.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


def assert_response_time(actual_time: float, expected_max: float, operation: str = "operation"):
    """Assert response time is within expected range"""
    assert actual_time <= expected_max, (
        f"{operation} took {actual_time:.3f}s, expected <= {expected_max:.3f}s"
    )


def assert_memory_usage(max_mb: float, operation: str = "operation"):
    """Assert memory usage is within limits"""
    import psutil
    import os

    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024

    assert memory_mb <= max_mb, (
        f"{operation} used {memory_mb:.2f}MB memory, expected <= {max_mb:.2f}MB"
    )


# Export main utilities
__all__ = [
    'PerformanceMetrics',
    'PerformanceTracker',
    'TestDataFactory',
    'MockServiceManager',
    'DatabaseTestHelper',
    'generate_random_string',
    'generate_phone_number',
    'generate_chat_id',
    'wait_for_condition',
    'temporary_env_vars',
    'assert_response_time',
    'assert_memory_usage'
]