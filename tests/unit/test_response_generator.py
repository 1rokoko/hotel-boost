"""
Unit tests for response generator service
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.response_generator import ResponseGenerator
from app.utils.prompt_templates import ResponseType, get_prompt_template_manager
from app.schemas.deepseek import ResponseGenerationResult
from app.models.message import Message, MessageType
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.models.sentiment import SentimentAnalysis


class TestResponseGenerator:
    """Test response generator functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return MagicMock()
    
    @pytest.fixture
    def mock_hotel(self):
        """Mock hotel object"""
        hotel = MagicMock(spec=Hotel)
        hotel.id = uuid.uuid4()
        hotel.name = "Grand Test Hotel"
        hotel.settings = {
            "brand_voice": "professional and friendly",
            "ai_instructions": "Always mention our 24/7 concierge service"
        }
        return hotel
    
    @pytest.fixture
    def mock_guest(self):
        """Mock guest object"""
        guest = MagicMock(spec=Guest)
        guest.id = uuid.uuid4()
        guest.name = "Alice Johnson"
        guest.phone = "+1234567890"
        guest.preferences = {
            "language": "en",
            "loyalty_status": "gold",
            "stay_count": 5
        }
        return guest
    
    @pytest.fixture
    def mock_message(self, mock_hotel, mock_guest):
        """Mock message object"""
        message = MagicMock(spec=Message)
        message.id = uuid.uuid4()
        message.hotel_id = mock_hotel.id
        message.guest_id = mock_guest.id
        message.conversation_id = uuid.uuid4()
        message.content = "I need help with my reservation"
        message.message_type = MessageType.INCOMING
        message.created_at = datetime.utcnow()
        return message
    
    @pytest.fixture
    def response_generator(self, mock_db_session):
        """Create response generator instance"""
        return ResponseGenerator(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_generate_response_success(
        self,
        response_generator,
        mock_message,
        mock_hotel,
        mock_guest
    ):
        """Test successful response generation"""
        # Mock database queries
        response_generator.db.query.return_value.filter.return_value.first.side_effect = [
            mock_hotel,  # Hotel query
            mock_guest   # Guest query
        ]
        
        # Mock conversation history and sentiment context
        with patch.object(response_generator, '_get_conversation_history', new_callable=AsyncMock) as mock_history:
            with patch.object(response_generator, '_get_sentiment_context', new_callable=AsyncMock) as mock_sentiment:
                with patch.object(response_generator, '_generate_response_with_ai', new_callable=AsyncMock) as mock_ai:
                    with patch.object(response_generator, '_post_process_response') as mock_post_process:
                        
                        mock_history.return_value = []
                        mock_sentiment.return_value = {"sentiment_score": 0.0}
                        
                        expected_result = ResponseGenerationResult(
                            response="Thank you for contacting us, Alice! I'd be happy to help you with your reservation.",
                            confidence=0.9,
                            response_type=ResponseType.HELPFUL.value,
                            reasoning="Generated helpful response",
                            suggested_actions=["Verify reservation details"]
                        )
                        
                        mock_ai.return_value = expected_result
                        mock_post_process.return_value = expected_result
                        
                        result = await response_generator.generate_response(mock_message)
                        
                        assert result == expected_result
                        mock_ai.assert_called_once()
                        mock_post_process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_response_hotel_not_found(
        self,
        response_generator,
        mock_message
    ):
        """Test response generation when hotel not found"""
        # Mock database query to return None for hotel
        response_generator.db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="Hotel or guest not found"):
            await response_generator.generate_response(mock_message)
    
    @pytest.mark.asyncio
    async def test_generate_response_with_ai_success(
        self,
        response_generator,
        mock_hotel,
        mock_guest
    ):
        """Test AI response generation success"""
        from app.schemas.deepseek import ResponseGenerationRequest
        
        request = ResponseGenerationRequest(
            message="I need help with my booking",
            hotel_id=str(mock_hotel.id),
            guest_id=str(mock_guest.id)
        )
        
        # Mock DeepSeek client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I'd be happy to help you with your booking, Alice! Let me assist you with that right away."
        mock_client.chat_completion.return_value = mock_response
        
        with patch('app.services.response_generator.get_deepseek_client', new_callable=AsyncMock) as mock_get_client:
            mock_get_client.return_value = mock_client
            
            result = await response_generator._generate_response_with_ai(
                request=request,
                hotel=mock_hotel,
                guest=mock_guest,
                response_type=ResponseType.HELPFUL,
                correlation_id="test-correlation-id"
            )
            
            assert "Alice" in result.response
            assert "booking" in result.response
            assert result.confidence > 0.5
            assert result.response_type == ResponseType.HELPFUL.value
    
    @pytest.mark.asyncio
    async def test_generate_response_with_ai_api_error(
        self,
        response_generator,
        mock_hotel,
        mock_guest
    ):
        """Test AI response generation with API error"""
        from app.schemas.deepseek import ResponseGenerationRequest
        
        request = ResponseGenerationRequest(
            message="Test message",
            hotel_id=str(mock_hotel.id),
            guest_id=str(mock_guest.id)
        )
        
        # Mock DeepSeek client to raise exception
        mock_client = AsyncMock()
        mock_client.chat_completion.side_effect = Exception("API Error")
        
        with patch('app.services.response_generator.get_deepseek_client', new_callable=AsyncMock) as mock_get_client:
            with patch.object(response_generator, '_create_fallback_response') as mock_fallback:
                mock_fallback.return_value = ResponseGenerationResult(
                    response="Thank you for contacting Grand Test Hotel, Alice. I've received your message and will ensure you receive proper assistance shortly.",
                    confidence=0.6,
                    response_type=ResponseType.HELPFUL.value,
                    reasoning="Fallback response",
                    suggested_actions=["Connect guest with human agent"]
                )
                mock_get_client.return_value = mock_client
                
                result = await response_generator._generate_response_with_ai(
                    request=request,
                    hotel=mock_hotel,
                    guest=mock_guest,
                    response_type=ResponseType.HELPFUL,
                    correlation_id="test-correlation-id"
                )
                
                assert "Grand Test Hotel" in result.response
                assert "Alice" in result.response
                assert result.confidence == 0.6
                mock_fallback.assert_called_once()
    
    def test_extract_suggested_actions(self, response_generator):
        """Test suggested actions extraction"""
        # Test complaint resolution
        actions = response_generator._extract_suggested_actions(
            "I apologize for the issue. We will follow up with you.",
            ResponseType.COMPLAINT_RESOLUTION
        )
        
        assert "Follow up with guest within 24 hours" in actions
        assert "Document issue in guest profile" in actions
        assert "Schedule follow-up contact" in actions
        
        # Test booking assistance
        actions = response_generator._extract_suggested_actions(
            "I'll help you with your booking confirmation.",
            ResponseType.BOOKING_ASSISTANCE
        )
        
        assert "Confirm booking details" in actions
        assert "Send confirmation email" in actions
        
        # Test escalation indicators
        actions = response_generator._extract_suggested_actions(
            "Let me connect you with our manager for assistance.",
            ResponseType.HELPFUL
        )
        
        assert "Escalate to management" in actions
    
    def test_create_fallback_response(self, response_generator, mock_hotel, mock_guest):
        """Test fallback response creation"""
        # Test helpful fallback
        result = response_generator._create_fallback_response(
            "I need help",
            ResponseType.HELPFUL,
            mock_hotel,
            mock_guest
        )
        
        assert "Alice" in result.response
        assert "Grand Test Hotel" in result.response
        assert result.confidence == 0.6
        assert result.response_type == ResponseType.HELPFUL.value
        
        # Test complaint resolution fallback
        result = response_generator._create_fallback_response(
            "This is terrible",
            ResponseType.COMPLAINT_RESOLUTION,
            mock_hotel,
            mock_guest
        )
        
        assert "apologize" in result.response.lower()
        assert "management" in result.response.lower()
        assert result.response_type == ResponseType.COMPLAINT_RESOLUTION.value
    
    def test_post_process_response(self, response_generator, mock_hotel, mock_guest):
        """Test response post-processing"""
        # Test short response extension
        result = ResponseGenerationResult(
            response="OK",
            confidence=0.8,
            response_type=ResponseType.HELPFUL.value,
            reasoning="Test",
            suggested_actions=[]
        )
        
        processed = response_generator._post_process_response(result, mock_hotel, mock_guest)
        
        assert len(processed.response) > len(result.response)
        assert "anything else" in processed.response.lower()
        
        # Test long response truncation
        long_response = "This is a very long response that exceeds the maximum length limit. " * 50
        result = ResponseGenerationResult(
            response=long_response,
            confidence=0.8,
            response_type=ResponseType.HELPFUL.value,
            reasoning="Test",
            suggested_actions=[]
        )
        
        processed = response_generator._post_process_response(result, mock_hotel, mock_guest)
        
        assert len(processed.response) <= response_generator.config.max_response_length
        assert "more information" in processed.response
    
    @pytest.mark.asyncio
    async def test_get_conversation_history(self, response_generator):
        """Test conversation history retrieval"""
        conversation_id = str(uuid.uuid4())
        
        # Mock messages
        mock_messages = [
            MagicMock(message_type=MessageType.INCOMING, content="Hello", created_at=datetime.utcnow()),
            MagicMock(message_type=MessageType.OUTGOING, content="Hi there!", created_at=datetime.utcnow())
        ]
        
        response_generator.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_messages
        
        history = await response_generator._get_conversation_history(conversation_id, limit=5)
        
        assert len(history) == 2
        assert history[0]['content'] == "Hello"
        assert history[1]['content'] == "Hi there!"
    
    @pytest.mark.asyncio
    async def test_get_sentiment_context(self, response_generator):
        """Test sentiment context retrieval"""
        message_id = str(uuid.uuid4())
        
        # Mock sentiment analysis
        mock_sentiment = MagicMock()
        mock_sentiment.sentiment_type = "positive"
        mock_sentiment.sentiment_score = 0.8
        mock_sentiment.confidence_score = 0.9
        mock_sentiment.requires_attention = False
        
        response_generator.db.query.return_value.filter.return_value.first.return_value = mock_sentiment
        
        context = await response_generator._get_sentiment_context(message_id)
        
        assert context['sentiment_type'] == "positive"
        assert context['sentiment_score'] == 0.8
        assert context['confidence_score'] == 0.9
        assert context['requires_attention'] is False
    
    @pytest.mark.asyncio
    async def test_get_sentiment_context_not_found(self, response_generator):
        """Test sentiment context when not found"""
        message_id = str(uuid.uuid4())
        
        response_generator.db.query.return_value.filter.return_value.first.return_value = None
        
        context = await response_generator._get_sentiment_context(message_id)
        
        assert context == {}


class TestPromptTemplateManager:
    """Test prompt template manager"""
    
    def test_get_system_prompt_default(self):
        """Test default system prompt"""
        manager = get_prompt_template_manager()
        
        prompt = manager.get_system_prompt()
        
        assert "customer service" in prompt.lower()
        assert "professional" in prompt.lower()
        assert "helpful" in prompt.lower()
    
    def test_get_system_prompt_complaint_handling(self):
        """Test complaint handling system prompt"""
        manager = get_prompt_template_manager()
        
        prompt = manager.get_system_prompt(ResponseType.COMPLAINT_RESOLUTION)
        
        assert "complaint resolution" in prompt.lower()
        assert "empathy" in prompt.lower()
        assert "apologize" in prompt.lower()
    
    def test_create_user_prompt(self):
        """Test user prompt creation"""
        manager = get_prompt_template_manager()
        
        # Mock objects
        mock_hotel = MagicMock()
        mock_hotel.name = "Test Hotel"
        
        mock_guest = MagicMock()
        mock_guest.name = "John Doe"
        mock_guest.preferences = {"language": "en"}
        
        prompt = manager.create_user_prompt(
            guest_message="I need help",
            guest=mock_guest,
            hotel=mock_hotel,
            context={"room_type": "suite"}
        )
        
        assert "I need help" in prompt
        assert "John Doe" in prompt
        assert "Test Hotel" in prompt
        assert "room_type" in prompt
    
    def test_detect_response_type(self):
        """Test response type detection"""
        manager = get_prompt_template_manager()
        
        # Test complaint detection
        response_type = manager.detect_response_type("This is terrible and awful!")
        assert response_type == ResponseType.COMPLAINT_RESOLUTION
        
        # Test booking detection
        response_type = manager.detect_response_type("I want to book a room")
        assert response_type == ResponseType.BOOKING_ASSISTANCE
        
        # Test information request
        response_type = manager.detect_response_type("What amenities do you have?")
        assert response_type == ResponseType.INFORMATIONAL
        
        # Test default
        response_type = manager.detect_response_type("Hello")
        assert response_type == ResponseType.HELPFUL


if __name__ == "__main__":
    pytest.main([__file__])
