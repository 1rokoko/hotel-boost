"""
Pytest configuration and fixtures for WhatsApp Hotel Bot tests
"""

import asyncio
import os
import pytest
import pytest_asyncio
import uuid
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.config import settings
from app.models.base import Base
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.trigger import Trigger, TriggerType
from app.models.message import Message, Conversation, MessageType, SentimentType
from app.models.notification import StaffNotification, NotificationType, NotificationStatus
from app.core.tenant import TenantContext
from app.core.green_api_config import GreenAPIConfig
from app.core.deepseek_config import DeepSeekConfig, DeepSeekModel
from app.schemas.deepseek import (
    ChatCompletionResponse,
    SentimentAnalysisResult,
    SentimentType,
    ResponseGenerationResult
)
from tests.mocks.green_api_mock import MockGreenAPIClient, GreenAPIMock

# Import conversation handler components for testing
from app.services.conversation_service import ConversationService
from app.services.conversation_state_machine import ConversationStateMachine
from app.services.message_handler import MessageHandler
from app.services.escalation_service import EscalationService
from app.services.conversation_memory import ConversationMemory
from app.utils.intent_classifier import IntentClassifier, MessageIntent, IntentClassificationResult
from app.utils.context_manager import ContextManager
from app.models.message import ConversationState, ConversationStatus

# Test database URL
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def test_settings():
    """Override settings for testing"""
    original_values = {}
    test_overrides = {
        'ENVIRONMENT': 'test',
        'DEBUG': True,
        'DATABASE_URL': TEST_DATABASE_URL,
        'SECRET_KEY': 'test-secret-key',
        'GREEN_API_INSTANCE_ID': 'test-instance',
        'GREEN_API_TOKEN': 'test-token',
        'DEEPSEEK_API_KEY': 'test-deepseek-key'
    }
    
    # Store original values
    for key, value in test_overrides.items():
        original_values[key] = getattr(settings, key, None)
        setattr(settings, key, value)
    
    yield settings
    
    # Restore original values
    for key, value in original_values.items():
        setattr(settings, key, value)

@pytest.fixture
def mock_green_api_response():
    """Mock response for Green API calls"""
    return {
        "idMessage": "test-message-id-123",
        "statusMessage": "sent",
        "timestamp": 1625097600
    }

@pytest.fixture
def mock_deepseek_response():
    """Mock response for DeepSeek API calls"""
    return {
        "choices": [
            {
                "message": {
                    "content": "This is a positive message with sentiment score 0.8"
                }
            }
        ],
        "usage": {
            "total_tokens": 50
        }
    }

@pytest.fixture
def sample_hotel_data():
    """Sample hotel data for testing"""
    return {
        "name": "Test Hotel",
        "whatsapp_number": "+1234567890",
        "green_api_instance_id": "test-instance-123",
        "green_api_token": "test-token-456",
        "settings": {
            "welcome_message": "Welcome to Test Hotel!",
            "business_hours": "9:00-18:00"
        }
    }

@pytest.fixture
def sample_guest_data():
    """Sample guest data for testing"""
    return {
        "phone": "+1987654321",
        "name": "John Doe",
        "preferences": {
            "language": "en",
            "room_type": "suite"
        }
    }

@pytest.fixture
def sample_message_data():
    """Sample message data for testing"""
    return {
        "content": "Hello, I have a question about my reservation",
        "message_type": "incoming",
        "metadata": {
            "phone": "+1987654321",
            "timestamp": "2025-07-11T10:30:00Z"
        }
    }

@pytest.fixture
def sample_webhook_data():
    """Sample webhook data from Green API"""
    return {
        "typeWebhook": "incomingMessageReceived",
        "instanceData": {
            "idInstance": "test-instance-123",
            "wid": "1234567890@c.us",
            "typeInstance": "whatsapp"
        },
        "messageData": {
            "idMessage": "msg-123456",
            "timestamp": 1625097600,
            "typeMessage": "textMessage",
            "chatId": "1987654321@c.us",
            "senderId": "1987654321@c.us",
            "senderName": "John Doe",
            "textMessageData": {
                "textMessage": "Hello, I need help with my booking"
            }
        }
    }

@pytest_asyncio.fixture
async def async_client():
    """Async test client for testing async endpoints"""
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

class MockGreenAPIClient:
    """Mock Green API client for testing"""
    
    def __init__(self):
        self.sent_messages = []
        self.should_fail = False
        self.response_delay = 0
    
    async def send_message(self, phone: str, message: str, **kwargs):
        """Mock send message method"""
        if self.should_fail:
            raise Exception("Mock API error")
        
        if self.response_delay:
            await asyncio.sleep(self.response_delay)
        
        message_data = {
            "phone": phone,
            "message": message,
            "timestamp": "2025-07-11T10:30:00Z",
            "id": f"msg-{len(self.sent_messages) + 1}"
        }
        self.sent_messages.append(message_data)
        return message_data
    
    def get_sent_messages(self):
        """Get all sent messages"""
        return self.sent_messages
    
    def clear_sent_messages(self):
        """Clear sent messages history"""
        self.sent_messages = []
    
    def set_should_fail(self, should_fail: bool):
        """Set whether API calls should fail"""
        self.should_fail = should_fail

@pytest.fixture
def mock_green_api_client():
    """Mock Green API client fixture"""
    return MockGreenAPIClient()

class MockDeepSeekClient:
    """Mock DeepSeek client for testing"""
    
    def __init__(self):
        self.analyzed_messages = []
        self.should_fail = False
        self.sentiment_score = 0.5
    
    async def analyze_sentiment(self, text: str):
        """Mock sentiment analysis"""
        if self.should_fail:
            raise Exception("Mock DeepSeek API error")
        
        analysis = {
            "text": text,
            "sentiment_score": self.sentiment_score,
            "sentiment_type": "positive" if self.sentiment_score > 0.6 else "negative" if self.sentiment_score < 0.4 else "neutral",
            "confidence": 0.9
        }
        self.analyzed_messages.append(analysis)
        return analysis
    
    def set_sentiment_score(self, score: float):
        """Set mock sentiment score"""
        self.sentiment_score = score
    
    def set_should_fail(self, should_fail: bool):
        """Set whether API calls should fail"""
        self.should_fail = should_fail

@pytest.fixture
def mock_deepseek_client():
    """Mock DeepSeek client fixture"""
    return MockDeepSeekClient()


@pytest.fixture
def mock_deepseek_config():
    """Mock DeepSeek configuration for testing"""
    return DeepSeekConfig(
        api_key="test-api-key-12345",
        base_url="https://api.deepseek.com",
        default_model=DeepSeekModel.CHAT,
        max_tokens=4096,
        temperature=0.7,
        timeout=60,
        max_requests_per_minute=50,
        max_tokens_per_minute=100000,
        max_retries=3,
        retry_delay=1.0,
        cache_enabled=True,
        cache_ttl=3600
    )


@pytest.fixture
def mock_openai_chat_response():
    """Mock OpenAI chat completion response"""
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    mock_response.object = "chat.completion"
    mock_response.created = int(datetime.utcnow().timestamp())
    mock_response.model = "deepseek-chat"
    mock_response.system_fingerprint = f"fp_{uuid.uuid4().hex[:8]}"

    # Mock choice
    mock_choice = MagicMock()
    mock_choice.index = 0
    mock_choice.finish_reason = "stop"
    mock_choice.message.role = "assistant"
    mock_choice.message.content = "This is a test response from DeepSeek API"
    mock_response.choices = [mock_choice]

    # Mock usage
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 25
    mock_usage.completion_tokens = 15
    mock_usage.total_tokens = 40
    mock_response.usage = mock_usage

    return mock_response


@pytest.fixture
def mock_sentiment_response():
    """Mock sentiment analysis response"""
    return {
        "sentiment": "positive",
        "score": 0.8,
        "confidence": 0.9,
        "requires_attention": False,
        "reason": "Guest expressed satisfaction with service",
        "keywords": ["great", "excellent", "satisfied"]
    }


@pytest.fixture
def mock_negative_sentiment_response():
    """Mock negative sentiment analysis response"""
    return {
        "sentiment": "requires_attention",
        "score": -0.8,
        "confidence": 0.95,
        "requires_attention": True,
        "reason": "Guest expressed strong dissatisfaction",
        "keywords": ["terrible", "awful", "disappointed"]
    }


@pytest.fixture
def mock_response_generation_result():
    """Mock response generation result"""
    return "Thank you for your feedback! We're delighted to hear about your positive experience. Our team works hard to provide excellent service, and it's wonderful to know we've met your expectations. Please don't hesitate to reach out if there's anything else we can do to make your stay even better!"


class EnhancedMockDeepSeekClient:
    """Enhanced Mock DeepSeek client for testing"""

    def __init__(self, responses: Dict[str, Any] = None):
        self.responses = responses or {}
        self.call_count = 0
        self.last_request = None
        self.should_fail = False
        self.response_delay = 0

    async def chat_completion(self, messages, **kwargs):
        """Mock chat completion"""
        if self.should_fail:
            raise Exception("Mock API error")

        if self.response_delay:
            await asyncio.sleep(self.response_delay)

        self.call_count += 1
        self.last_request = {
            'messages': messages,
            'kwargs': kwargs
        }

        # Determine response type based on content
        user_content = ""
        for msg in messages:
            if hasattr(msg, 'role') and msg.role.value == "user":
                user_content += msg.content.lower()

        if "sentiment" in user_content or "analyze" in user_content:
            # Return sentiment analysis response
            content = self.responses.get('sentiment', '{"sentiment": "neutral", "score": 0.0, "confidence": 0.5, "requires_attention": false, "reason": "Test", "keywords": []}')
        else:
            # Return general response
            content = self.responses.get('response', "This is a test response")

        mock_response = ChatCompletionResponse(
            id=f"test-{self.call_count}",
            object="chat.completion",
            created=int(datetime.utcnow().timestamp()),
            model="deepseek-chat",
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30
            }
        )

        return mock_response

    async def simple_completion(self, prompt, **kwargs):
        """Mock simple completion"""
        response = await self.chat_completion([{"role": "user", "content": prompt}], **kwargs)
        return response.choices[0].message.content

    async def validate_api_key(self):
        """Mock API key validation"""
        return not self.should_fail

    async def get_available_models(self):
        """Mock available models"""
        return ["deepseek-chat", "deepseek-reasoner"]

    async def close(self):
        """Mock close"""
        pass

    def set_should_fail(self, should_fail: bool):
        """Set whether API calls should fail"""
        self.should_fail = should_fail

    def set_response_delay(self, delay: float):
        """Set response delay for testing timeouts"""
        self.response_delay = delay


@pytest.fixture
def enhanced_mock_deepseek_client():
    """Enhanced mock DeepSeek client fixture"""
    return EnhancedMockDeepSeekClient()


@pytest.fixture
def mock_deepseek_client_with_responses():
    """Fixture for mock DeepSeek client with predefined responses"""
    def _create_client(responses: Dict[str, Any]):
        return EnhancedMockDeepSeekClient(responses)
    return _create_client

# Performance testing utilities
@pytest.fixture
def performance_tracker():
    """Track performance metrics during tests"""
    class PerformanceTracker:
        def __init__(self):
            self.metrics = {}
        
        def start_timer(self, operation: str):
            import time
            self.metrics[operation] = {"start": time.time()}
        
        def end_timer(self, operation: str):
            import time
            if operation in self.metrics:
                self.metrics[operation]["end"] = time.time()
                self.metrics[operation]["duration"] = (
                    self.metrics[operation]["end"] - self.metrics[operation]["start"]
                ) * 1000  # Convert to ms
        
        def get_duration(self, operation: str) -> float:
            return self.metrics.get(operation, {}).get("duration", 0)
        
        def assert_duration_under(self, operation: str, max_ms: float):
            duration = self.get_duration(operation)
            assert duration < max_ms, f"Operation {operation} took {duration}ms, expected under {max_ms}ms"
    
    return PerformanceTracker()

# Database testing utilities
@pytest.fixture
def test_db_engine():
    """Create test database engine"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine

@pytest.fixture
def test_db_session(test_db_engine):
    """Create test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

# Enhanced database fixtures for new models
@pytest.fixture
async def async_test_engine():
    """Create async test database engine"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture
async def async_test_session(async_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async test database session"""
    async_session = async_sessionmaker(
        async_test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture
async def sample_hotel(async_test_session) -> Hotel:
    """Create a sample hotel for testing"""
    hotel = Hotel(
        name="Test Hotel",
        whatsapp_number="+1234567890",
        green_api_instance_id="test_instance",
        green_api_token="test_token"
    )
    hotel.apply_default_settings()

    async_test_session.add(hotel)
    await async_test_session.commit()
    await async_test_session.refresh(hotel)

    return hotel


@pytest.fixture
async def sample_guest(async_test_session, sample_hotel) -> Guest:
    """Create a sample guest for testing"""
    guest = Guest(
        hotel_id=sample_hotel.id,
        phone="+1111111111",
        name="John Doe"
    )
    guest.apply_default_preferences()

    async_test_session.add(guest)
    await async_test_session.commit()
    await async_test_session.refresh(guest)

    return guest


@pytest.fixture
async def sample_conversation(async_test_session, sample_hotel, sample_guest) -> Conversation:
    """Create a sample conversation for testing"""
    conversation = Conversation(
        hotel_id=sample_hotel.id,
        guest_id=sample_guest.id
    )

    async_test_session.add(conversation)
    await async_test_session.commit()
    await async_test_session.refresh(conversation)

    return conversation


@pytest.fixture
async def sample_message(async_test_session, sample_conversation) -> Message:
    """Create a sample message for testing"""
    message = Message(
        conversation_id=sample_conversation.id,
        message_type=MessageType.INCOMING,
        content="Hello, I need help with my booking"
    )
    message.set_sentiment(-0.2, SentimentType.NEUTRAL)

    async_test_session.add(message)
    await async_test_session.commit()
    await async_test_session.refresh(message)

    return message


@pytest.fixture
def tenant_context_manager():
    """Fixture for managing tenant context in tests"""
    class TenantContextManager:
        def __init__(self):
            self.original_tenant = None

        def set_tenant(self, tenant_id: uuid.UUID):
            self.original_tenant = TenantContext.get_tenant_id()
            TenantContext.set_tenant_id(tenant_id)

        def clear_tenant(self):
            TenantContext.clear_tenant_id()

        def restore_tenant(self):
            if self.original_tenant:
                TenantContext.set_tenant_id(self.original_tenant)
            else:
                TenantContext.clear_tenant_id()

    manager = TenantContextManager()
    yield manager
    manager.restore_tenant()


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Cleanup test files after each test"""
    # Clear tenant context before each test
    TenantContext.clear_tenant_id()

    yield

    # Clean up test database and tenant context
    if os.path.exists("test.db"):
        os.remove("test.db")
    TenantContext.clear_tenant_id()


# Test markers configuration
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "tenant: mark test as a tenant isolation test")
    config.addinivalue_line("markers", "green_api: mark test as Green API related")
    config.addinivalue_line("markers", "webhook: mark test as webhook related")
    config.addinivalue_line("markers", "celery: mark test as Celery task related")
    config.addinivalue_line("markers", "message_processing: mark test as message processing related")


# Green API specific fixtures
@pytest.fixture
def green_api_config():
    """Create test Green API configuration"""
    return GreenAPIConfig(
        base_url="https://api.green-api.com",
        instance_id="1234567890",
        token="test_token_123"
    )


@pytest.fixture
def mock_green_api():
    """Create mock Green API instance"""
    return GreenAPIMock()


@pytest.fixture
def mock_green_api_client(green_api_config):
    """Create mock Green API client"""
    return MockGreenAPIClient(green_api_config)


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing"""
    from unittest.mock import Mock, patch
    with patch('app.tasks.process_incoming.process_incoming_message_task') as mock_task:
        mock_task.delay = Mock()
        yield mock_task


@pytest.fixture
def webhook_payload():
    """Create sample webhook payload for testing"""
    return {
        "typeWebhook": "incomingMessageReceived",
        "instanceData": {"idInstance": "1234567890"},
        "timestamp": 1640995200,
        "idMessage": "test_msg_123",
        "senderData": {
            "chatId": "1234567890@c.us",
            "sender": "1234567890@c.us",
            "senderName": "Test Guest"
        },
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": "Hello, I need help!"}
        }
    }
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "deepseek: mark test as DeepSeek AI related")
    config.addinivalue_line("markers", "sentiment: mark test as sentiment analysis related")
    config.addinivalue_line("markers", "response_generation: mark test as response generation related")


# Test data constants for DeepSeek AI testing
TEST_SENTIMENT_RESPONSES = {
    "positive": {
        "sentiment": "positive",
        "score": 0.8,
        "confidence": 0.9,
        "requires_attention": False,
        "reason": "Guest expressed satisfaction",
        "keywords": ["wonderful", "amazing", "perfect"]
    },
    "negative": {
        "sentiment": "negative",
        "score": -0.6,
        "confidence": 0.85,
        "requires_attention": False,
        "reason": "Guest expressed dissatisfaction",
        "keywords": ["disappointed", "poor"]
    },
    "requires_attention": {
        "sentiment": "requires_attention",
        "score": -0.9,
        "confidence": 0.95,
        "requires_attention": True,
        "reason": "Guest expressed strong dissatisfaction requiring immediate attention",
        "keywords": ["unacceptable", "terrible", "dirty"]
    }
}

TEST_RESPONSE_TEMPLATES = {
    "positive": "Thank you for your wonderful feedback! We're delighted to hear about your positive experience.",
    "negative": "I apologize for the issues you've experienced. We take your concerns seriously and will address them immediately.",
    "complaint": "I sincerely apologize for this unacceptable experience. I'm escalating this to our management team for immediate attention."
}


# Conversation Handler Test Fixtures

@pytest.fixture
def mock_conversation_service():
    """Create a mock conversation service"""
    from unittest.mock import Mock, AsyncMock
    service = Mock(spec=ConversationService)
    service.get_conversation = AsyncMock()
    service.create_conversation = AsyncMock()
    service.update_conversation = AsyncMock()
    service.get_or_create_conversation = AsyncMock()
    service.get_conversations = AsyncMock()
    service.get_conversation_stats = AsyncMock()
    return service


@pytest.fixture
def mock_state_machine():
    """Create a mock state machine"""
    from unittest.mock import Mock, AsyncMock
    from datetime import datetime

    machine = Mock(spec=ConversationStateMachine)
    machine.get_allowed_transitions = Mock(return_value=set())
    machine.can_transition = Mock(return_value=True)
    machine.transition_to = AsyncMock()

    # Default transition response
    transition_response = Mock()
    transition_response.success = True
    transition_response.previous_state = ConversationState.GREETING
    transition_response.new_state = ConversationState.COLLECTING_INFO
    transition_response.timestamp = datetime.utcnow()
    transition_response.message = "Transition successful"

    machine.transition_to.return_value = transition_response
    return machine


@pytest.fixture
def mock_intent_classifier():
    """Create a mock intent classifier"""
    from unittest.mock import Mock, AsyncMock

    classifier = Mock(spec=IntentClassifier)
    classifier.classify_intent = AsyncMock()

    # Default classification result
    default_result = IntentClassificationResult(
        intent=MessageIntent.GENERAL_QUESTION,
        confidence=0.8,
        entities={},
        keywords=[],
        sentiment_score=0.1,
        urgency_level=2,
        reasoning="Default classification"
    )

    classifier.classify_intent.return_value = default_result
    return classifier


@pytest.fixture
def mock_escalation_service():
    """Create a mock escalation service"""
    from unittest.mock import Mock, AsyncMock

    service = Mock(spec=EscalationService)
    service.evaluate_escalation_triggers = AsyncMock(return_value=[])
    service.escalate_conversation = AsyncMock()
    service.auto_escalate_if_needed = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_conversation_memory():
    """Create a mock conversation memory service"""
    from unittest.mock import Mock, AsyncMock

    memory = Mock(spec=ConversationMemory)
    memory.store_context = AsyncMock(return_value=True)
    memory.get_context = AsyncMock(return_value=None)
    memory.update_context = AsyncMock(return_value=True)
    memory.delete_context = AsyncMock(return_value=True)
    memory.store_guest_preferences = AsyncMock(return_value=True)
    memory.get_guest_preferences = AsyncMock(return_value=None)
    memory.create_conversation_session = AsyncMock(return_value=True)
    memory.get_conversation_session = AsyncMock(return_value=None)
    memory.extend_session = AsyncMock(return_value=True)
    memory.cleanup_expired_data = AsyncMock(return_value={'contexts_cleaned': 0})
    return memory


@pytest.fixture
def mock_context_manager():
    """Create a mock context manager"""
    from unittest.mock import Mock, AsyncMock

    manager = Mock(spec=ContextManager)
    manager.set_current_request = AsyncMock(return_value=True)
    manager.get_current_request = AsyncMock(return_value=None)
    manager.update_request_status = AsyncMock(return_value=True)
    manager.add_collected_info = AsyncMock(return_value=True)
    manager.get_collected_info = AsyncMock(return_value=None)
    manager.add_intent_to_history = AsyncMock(return_value=True)
    manager.get_intent_patterns = AsyncMock(return_value=[])
    manager.add_pending_action = AsyncMock(return_value=True)
    manager.get_pending_actions = AsyncMock(return_value=[])
    manager.complete_action = AsyncMock(return_value=True)
    manager.clear_context_type = AsyncMock(return_value=True)
    manager.get_context_summary = AsyncMock(return_value={})
    return manager


@pytest.fixture
def sample_conversation_with_state():
    """Create a sample conversation with state machine fields"""
    conversation = Conversation(
        id=uuid.uuid4(),
        hotel_id=uuid.uuid4(),
        guest_id=uuid.uuid4(),
        status=ConversationStatus.ACTIVE,
        current_state=ConversationState.GREETING,
        context={
            "guest_name": "John Doe",
            "room_number": "205",
            "language": "en",
            "message_count": 1
        }
    )
    return conversation


# Test data generators
def generate_test_messages(count: int = 5):
    """Generate test messages"""
    from unittest.mock import Mock
    from datetime import datetime

    messages = []
    for i in range(count):
        message = Mock()
        message.id = uuid.uuid4()
        message.content = f"Test message {i+1}"
        message.message_type = MessageType.TEXT
        message.created_at = datetime.utcnow()
        messages.append(message)
    return messages


def generate_test_conversations(count: int = 3):
    """Generate test conversations"""
    from unittest.mock import Mock
    from datetime import datetime

    conversations = []
    for i in range(count):
        conversation = Mock()
        conversation.id = uuid.uuid4()
        conversation.hotel_id = uuid.uuid4()
        conversation.guest_id = uuid.uuid4()
        conversation.status = ConversationStatus.ACTIVE
        conversation.current_state = ConversationState.GREETING
        conversation.context = {}
        conversation.created_at = datetime.utcnow()
        conversation.last_message_at = datetime.utcnow()
        conversations.append(conversation)
    return conversations
