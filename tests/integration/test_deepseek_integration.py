"""
Integration tests for DeepSeek AI functionality
"""

import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.deepseek_client import get_deepseek_client
from app.services.sentiment_analyzer import SentimentAnalyzer
from app.services.response_generator import ResponseGenerator
from app.schemas.deepseek import SentimentType
from app.models.message import Message, MessageType
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.models.sentiment import SentimentAnalysis


class TestDeepSeekIntegration:
    """Integration tests for DeepSeek AI services"""
    
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
    def mock_positive_message(self, mock_hotel, mock_guest):
        """Mock positive message"""
        message = MagicMock(spec=Message)
        message.id = uuid.uuid4()
        message.hotel_id = mock_hotel.id
        message.guest_id = mock_guest.id
        message.conversation_id = uuid.uuid4()
        message.content = "The room is absolutely wonderful and the staff is amazing!"
        message.message_type = MessageType.INCOMING
        message.created_at = datetime.utcnow()
        return message
    
    @pytest.fixture
    def mock_negative_message(self, mock_hotel, mock_guest):
        """Mock negative message"""
        message = MagicMock(spec=Message)
        message.id = uuid.uuid4()
        message.hotel_id = mock_hotel.id
        message.guest_id = mock_guest.id
        message.conversation_id = uuid.uuid4()
        message.content = "This is terrible! The room is dirty and the service is awful!"
        message.message_type = MessageType.INCOMING
        message.created_at = datetime.utcnow()
        return message
    
    @pytest.mark.asyncio
    async def test_end_to_end_positive_sentiment_flow(
        self,
        mock_db_session,
        mock_positive_message,
        mock_hotel,
        mock_guest
    ):
        """Test complete flow for positive sentiment message"""
        # Setup database mocks
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_hotel,  # Hotel query for sentiment analysis
            mock_guest,  # Guest query for sentiment analysis
            mock_hotel,  # Hotel query for response generation
            mock_guest   # Guest query for response generation
        ]
        
        # Mock sentiment analysis storage
        mock_sentiment_record = MagicMock()
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        # Mock DeepSeek API responses
        sentiment_response = MagicMock()
        sentiment_response.choices = [MagicMock()]
        sentiment_response.choices[0].message.content = '''
        {
            "sentiment": "positive",
            "score": 0.9,
            "confidence": 0.95,
            "requires_attention": false,
            "reason": "Guest expressed high satisfaction with room and staff",
            "keywords": ["wonderful", "amazing"]
        }
        '''
        
        response_generation_response = MagicMock()
        response_generation_response.choices = [MagicMock()]
        response_generation_response.choices[0].message.content = "Thank you so much for your wonderful feedback, Alice! We're delighted to hear that you're enjoying your stay at Grand Test Hotel. Our team works hard to provide exceptional service, and it's heartwarming to know we've exceeded your expectations. Please don't hesitate to reach out to our 24/7 concierge service if there's anything else we can do to make your stay even more memorable!"
        
        with patch('app.services.deepseek_client.get_deepseek_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = [
                sentiment_response,
                response_generation_response
            ]
            mock_get_client.return_value = mock_client
            
            with patch('app.services.sentiment_analyzer.SentimentAnalysis', return_value=mock_sentiment_record):
                # Test sentiment analysis
                sentiment_analyzer = SentimentAnalyzer(mock_db_session)
                sentiment_result = await sentiment_analyzer.analyze_message_sentiment(mock_positive_message)
                
                assert sentiment_result.sentiment == SentimentType.POSITIVE
                assert sentiment_result.score == 0.9
                assert sentiment_result.confidence == 0.95
                assert sentiment_result.requires_attention is False
                assert "wonderful" in sentiment_result.keywords
                assert "amazing" in sentiment_result.keywords
                
                # Test response generation
                response_generator = ResponseGenerator(mock_db_session)
                
                # Mock conversation history query
                mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
                
                # Mock sentiment context query
                mock_db_session.query.return_value.filter.return_value.first.return_value = None
                
                response_result = await response_generator.generate_response(mock_positive_message)
                
                assert "Alice" in response_result.response
                assert "Grand Test Hotel" in response_result.response
                assert "24/7 concierge service" in response_result.response
                assert response_result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_end_to_end_negative_sentiment_flow(
        self,
        mock_db_session,
        mock_negative_message,
        mock_hotel,
        mock_guest
    ):
        """Test complete flow for negative sentiment message"""
        # Setup database mocks
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_hotel,  # Hotel query for sentiment analysis
            mock_guest,  # Guest query for sentiment analysis
            mock_hotel,  # Hotel query for response generation
            mock_guest   # Guest query for response generation
        ]
        
        # Mock sentiment analysis storage
        mock_sentiment_record = MagicMock()
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()
        
        # Mock DeepSeek API responses
        sentiment_response = MagicMock()
        sentiment_response.choices = [MagicMock()]
        sentiment_response.choices[0].message.content = '''
        {
            "sentiment": "requires_attention",
            "score": -0.8,
            "confidence": 0.9,
            "requires_attention": true,
            "reason": "Guest expressed strong dissatisfaction with room cleanliness and service quality",
            "keywords": ["terrible", "dirty", "awful"]
        }
        '''
        
        response_response = MagicMock()
        response_response.choices = [MagicMock()]
        response_response.choices[0].message.content = "I sincerely apologize for the unacceptable experience you've had, Alice. This is absolutely not the standard we maintain at Grand Test Hotel, and I understand your frustration. I'm immediately escalating this to our management team for urgent attention. We will have someone from our team contact you within the next 30 minutes to address these issues and make this right. Your satisfaction is our top priority."
        
        with patch('app.services.deepseek_client.get_deepseek_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = [
                sentiment_response,
                response_response
            ]
            mock_get_client.return_value = mock_client
            
            with patch('app.services.sentiment_analyzer.SentimentAnalysis', return_value=mock_sentiment_record):
                # Test sentiment analysis
                sentiment_analyzer = SentimentAnalyzer(mock_db_session)
                sentiment_result = await sentiment_analyzer.analyze_message_sentiment(mock_negative_message)
                
                assert sentiment_result.sentiment == SentimentType.REQUIRES_ATTENTION
                assert sentiment_result.score == -0.8
                assert sentiment_result.confidence == 0.9
                assert sentiment_result.requires_attention is True
                assert "terrible" in sentiment_result.keywords
                
                # Test response generation
                response_generator = ResponseGenerator(mock_db_session)
                
                # Mock conversation history and sentiment context
                mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
                mock_db_session.query.return_value.filter.return_value.first.return_value = None
                
                response_result = await response_generator.generate_response(mock_negative_message)
                
                assert "apologize" in response_result.response.lower()
                assert "Alice" in response_result.response
                assert "Grand Test Hotel" in response_result.response
                assert response_result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_api_error_handling_with_fallback(
        self,
        mock_db_session,
        mock_positive_message,
        mock_hotel,
        mock_guest
    ):
        """Test error handling and fallback mechanisms"""
        # Setup database mocks
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_hotel,  # Hotel query
            mock_guest   # Guest query
        ]
        
        # Mock API error
        with patch('app.services.deepseek_client.get_deepseek_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = Exception("API Error")
            mock_get_client.return_value = mock_client
            
            # Test sentiment analysis fallback
            sentiment_analyzer = SentimentAnalyzer(mock_db_session)
            
            with patch.object(sentiment_analyzer, '_store_sentiment_analysis', new_callable=AsyncMock):
                sentiment_result = await sentiment_analyzer.analyze_message_sentiment(mock_positive_message)
                
                # Should get fallback result
                assert sentiment_result.sentiment in [SentimentType.POSITIVE, SentimentType.NEUTRAL]
                assert sentiment_result.confidence < 0.5  # Lower confidence for fallback
                assert "fallback" in sentiment_result.reason.lower()
    
    @pytest.mark.asyncio
    async def test_rate_limiting_behavior(self, mock_db_session):
        """Test rate limiting behavior"""
        with patch('app.services.deepseek_client.get_global_deepseek_config') as mock_config:
            # Set very low rate limits for testing
            mock_config.return_value.max_requests_per_minute = 1
            mock_config.return_value.max_tokens_per_minute = 100
            
            client = await get_deepseek_client()
            
            # Mock rate limiter to simulate limit exceeded
            with patch.object(client.rate_limiter, 'acquire', new_callable=AsyncMock) as mock_acquire:
                with patch.object(client.rate_limiter, 'get_wait_time', return_value=0.1):
                    # First call denied, second call allowed
                    mock_acquire.side_effect = [False, False, False, False, False, True]
                    
                    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
                        mock_response = MagicMock()
                        mock_response.id = "test-id"
                        mock_response.choices = [MagicMock()]
                        mock_response.choices[0].message.content = "Test response"
                        mock_create.return_value = mock_response
                        
                        from app.schemas.deepseek import ChatCompletionRequest, ChatMessage, MessageRole
                        
                        request = ChatCompletionRequest(
                            model="deepseek-chat",
                            messages=[ChatMessage(role=MessageRole.USER, content="Hello")]
                        )
                        
                        # Should eventually succeed after rate limit waits
                        with pytest.raises(Exception, match="Rate limit exceeded"):
                            await client._make_request(request)
    
    @pytest.mark.asyncio
    async def test_conversation_context_integration(
        self,
        mock_db_session,
        mock_positive_message,
        mock_hotel,
        mock_guest
    ):
        """Test integration with conversation context"""
        # Setup database mocks
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_hotel,  # Hotel query
            mock_guest   # Guest query
        ]
        
        # Mock conversation history
        mock_history_messages = [
            MagicMock(content="Hello, I'd like to check in", message_type=MessageType.INCOMING, created_at=datetime.utcnow()),
            MagicMock(content="Welcome! I'll help you with check-in", message_type=MessageType.OUTGOING, created_at=datetime.utcnow())
        ]
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_history_messages
        
        # Mock sentiment context
        mock_sentiment = MagicMock()
        mock_sentiment.sentiment_type = "positive"
        mock_sentiment.sentiment_score = 0.8
        mock_sentiment.confidence_score = 0.9
        mock_sentiment.requires_attention = False
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_sentiment
        
        # Mock DeepSeek response
        response_response = MagicMock()
        response_response.choices = [MagicMock()]
        response_response.choices[0].message.content = "Thank you for the positive feedback about your check-in experience, Alice! I'm glad we could make the process smooth for you."
        
        with patch('app.services.deepseek_client.get_deepseek_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = response_response
            mock_get_client.return_value = mock_client
            
            response_generator = ResponseGenerator(mock_db_session)
            response_result = await response_generator.generate_response(mock_positive_message)
            
            # Verify that context was used in generation
            assert "Alice" in response_result.response
            assert response_result.confidence > 0.5
            
            # Verify that the AI client was called with context
            mock_client.chat_completion.assert_called_once()
            call_args = mock_client.chat_completion.call_args
            messages = call_args[1]['messages']
            
            # Should have system and user messages
            assert len(messages) >= 2
            assert any("conversation" in msg.content.lower() for msg in messages if hasattr(msg, 'content'))


if __name__ == "__main__":
    pytest.main([__file__])
