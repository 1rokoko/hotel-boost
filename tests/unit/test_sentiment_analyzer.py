"""
Unit tests for sentiment analyzer service
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.sentiment_analyzer import SentimentAnalyzer
from app.schemas.deepseek import SentimentAnalysisResult, SentimentType
from app.models.sentiment import SentimentAnalysis
from app.models.message import Message, MessageType
from app.models.guest import Guest
from app.models.hotel import Hotel


class TestSentimentAnalyzer:
    """Test sentiment analyzer functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return MagicMock()
    
    @pytest.fixture
    def mock_hotel(self):
        """Mock hotel object"""
        hotel = MagicMock(spec=Hotel)
        hotel.id = uuid.uuid4()
        hotel.name = "Test Hotel"
        hotel.settings = {"brand_voice": "friendly"}
        return hotel
    
    @pytest.fixture
    def mock_guest(self):
        """Mock guest object"""
        guest = MagicMock(spec=Guest)
        guest.id = uuid.uuid4()
        guest.name = "John Doe"
        guest.phone = "+1234567890"
        guest.preferences = {"language": "en"}
        return guest
    
    @pytest.fixture
    def mock_message(self, mock_hotel, mock_guest):
        """Mock message object"""
        message = MagicMock(spec=Message)
        message.id = uuid.uuid4()
        message.hotel_id = mock_hotel.id
        message.guest_id = mock_guest.id
        message.conversation_id = uuid.uuid4()
        message.content = "The room was terrible and the service was awful!"
        message.message_type = MessageType.INCOMING
        message.created_at = datetime.utcnow()
        return message
    
    @pytest.fixture
    def sentiment_analyzer(self, mock_db_session):
        """Create sentiment analyzer instance"""
        return SentimentAnalyzer(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_analyze_message_sentiment_success(
        self,
        sentiment_analyzer,
        mock_message,
        mock_hotel,
        mock_guest
    ):
        """Test successful sentiment analysis"""
        # Mock database queries
        sentiment_analyzer.db.query.return_value.filter.return_value.first.side_effect = [
            mock_hotel,  # Hotel query
            mock_guest   # Guest query
        ]
        
        # Mock AI analysis
        expected_result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.8,
            confidence=0.9,
            requires_attention=True,
            reason="Guest expressed dissatisfaction with room and service",
            keywords=["terrible", "awful"]
        )
        
        with patch.object(sentiment_analyzer, '_analyze_sentiment_with_ai', new_callable=AsyncMock) as mock_ai:
            with patch.object(sentiment_analyzer, '_store_sentiment_analysis', new_callable=AsyncMock) as mock_store:
                mock_ai.return_value = expected_result
                mock_store.return_value = MagicMock()
                
                result = await sentiment_analyzer.analyze_message_sentiment(mock_message)
                
                assert result == expected_result
                mock_ai.assert_called_once()
                mock_store.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_message_sentiment_hotel_not_found(
        self,
        sentiment_analyzer,
        mock_message
    ):
        """Test sentiment analysis when hotel not found"""
        # Mock database query to return None for hotel
        sentiment_analyzer.db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="Hotel or guest not found"):
            await sentiment_analyzer.analyze_message_sentiment(mock_message)
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_with_ai_success(
        self,
        sentiment_analyzer
    ):
        """Test AI sentiment analysis success"""
        from app.schemas.deepseek import SentimentAnalysisRequest
        
        request = SentimentAnalysisRequest(
            text="The service was excellent!",
            hotel_id=str(uuid.uuid4()),
            guest_id=str(uuid.uuid4())
        )
        
        # Mock DeepSeek client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"sentiment": "positive", "score": 0.8, "confidence": 0.9, "requires_attention": false, "reason": "Positive feedback", "keywords": ["excellent"]}'
        mock_client.chat_completion.return_value = mock_response
        
        with patch('app.services.sentiment_analyzer.get_deepseek_client', new_callable=AsyncMock) as mock_get_client:
            mock_get_client.return_value = mock_client
            
            result = await sentiment_analyzer._analyze_sentiment_with_ai(request, "test-correlation-id")
            
            assert result.sentiment == SentimentType.POSITIVE
            assert result.score == 0.8
            assert result.confidence == 0.9
            assert result.requires_attention is False
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_with_ai_json_parse_error(
        self,
        sentiment_analyzer
    ):
        """Test AI sentiment analysis with JSON parse error"""
        from app.schemas.deepseek import SentimentAnalysisRequest
        
        request = SentimentAnalysisRequest(
            text="Test message",
            hotel_id=str(uuid.uuid4()),
            guest_id=str(uuid.uuid4())
        )
        
        # Mock DeepSeek client with invalid JSON response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Invalid JSON response'
        mock_client.chat_completion.return_value = mock_response
        
        with patch('app.services.sentiment_analyzer.get_deepseek_client', new_callable=AsyncMock) as mock_get_client:
            with patch.object(sentiment_analyzer, '_extract_json_from_response') as mock_extract:
                mock_extract.return_value = {
                    'sentiment': 'neutral',
                    'score': 0.0,
                    'confidence': 0.5,
                    'requires_attention': False,
                    'reason': 'Failed to parse',
                    'keywords': []
                }
                mock_get_client.return_value = mock_client
                
                result = await sentiment_analyzer._analyze_sentiment_with_ai(request, "test-correlation-id")
                
                assert result.sentiment == SentimentType.NEUTRAL
                assert result.score == 0.0
                mock_extract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_with_ai_api_error(
        self,
        sentiment_analyzer
    ):
        """Test AI sentiment analysis with API error"""
        from app.schemas.deepseek import SentimentAnalysisRequest
        
        request = SentimentAnalysisRequest(
            text="Test message",
            hotel_id=str(uuid.uuid4()),
            guest_id=str(uuid.uuid4())
        )
        
        # Mock DeepSeek client to raise exception
        mock_client = AsyncMock()
        mock_client.chat_completion.side_effect = Exception("API Error")
        
        with patch('app.services.sentiment_analyzer.get_deepseek_client', new_callable=AsyncMock) as mock_get_client:
            with patch.object(sentiment_analyzer, '_create_fallback_sentiment_result') as mock_fallback:
                mock_fallback.return_value = SentimentAnalysisResult(
                    sentiment=SentimentType.NEUTRAL,
                    score=0.0,
                    confidence=0.3,
                    requires_attention=False,
                    reason="Fallback analysis",
                    keywords=[]
                )
                mock_get_client.return_value = mock_client
                
                result = await sentiment_analyzer._analyze_sentiment_with_ai(request, "test-correlation-id")
                
                assert result.sentiment == SentimentType.NEUTRAL
                assert result.confidence == 0.3
                mock_fallback.assert_called_once()
    
    def test_create_sentiment_system_prompt(self, sentiment_analyzer):
        """Test sentiment system prompt creation"""
        prompt = sentiment_analyzer._create_sentiment_system_prompt()
        
        assert "sentiment analyzer" in prompt.lower()
        assert "positive" in prompt
        assert "negative" in prompt
        assert "neutral" in prompt
        assert "requires_attention" in prompt
        assert "json" in prompt.lower()
    
    def test_create_sentiment_user_prompt(self, sentiment_analyzer):
        """Test sentiment user prompt creation"""
        from app.schemas.deepseek import SentimentAnalysisRequest
        
        request = SentimentAnalysisRequest(
            text="The room was great!",
            context={"room_type": "deluxe"},
            language="en",
            hotel_id=str(uuid.uuid4()),
            guest_id=str(uuid.uuid4())
        )
        
        prompt = sentiment_analyzer._create_sentiment_user_prompt(request)
        
        assert "The room was great!" in prompt
        assert "room_type" in prompt
        assert "Language: en" in prompt
        assert "JSON" in prompt
    
    def test_extract_json_from_response(self, sentiment_analyzer):
        """Test JSON extraction from response"""
        # Valid JSON in response
        response_with_json = 'Here is the analysis: {"sentiment": "positive", "score": 0.8}'
        result = sentiment_analyzer._extract_json_from_response(response_with_json)
        
        assert result["sentiment"] == "positive"
        assert result["score"] == 0.8
        
        # Invalid response
        invalid_response = "No JSON here"
        result = sentiment_analyzer._extract_json_from_response(invalid_response)
        
        assert result["sentiment"] == "neutral"
        assert result["confidence"] == 0.5
    
    def test_validate_sentiment_result(self, sentiment_analyzer):
        """Test sentiment result validation"""
        # Test positive sentiment with negative score (should be corrected)
        result = SentimentAnalysisResult(
            sentiment=SentimentType.POSITIVE,
            score=-0.5,
            confidence=0.8,
            requires_attention=False,
            reason="Test",
            keywords=[]
        )
        
        sentiment_analyzer._validate_sentiment_result(result)
        
        assert result.score == 0.5  # Should be corrected to positive
        
        # Test very negative score (should set requires_attention)
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.8,
            confidence=0.9,
            requires_attention=False,
            reason="Test",
            keywords=[]
        )
        
        sentiment_analyzer._validate_sentiment_result(result)
        
        assert result.requires_attention is True
        assert result.sentiment == SentimentType.REQUIRES_ATTENTION
    
    def test_create_fallback_sentiment_result(self, sentiment_analyzer):
        """Test fallback sentiment result creation"""
        # Negative text
        negative_result = sentiment_analyzer._create_fallback_sentiment_result("This is terrible and awful")
        assert negative_result.sentiment == SentimentType.NEGATIVE
        assert negative_result.score < 0
        
        # Positive text
        positive_result = sentiment_analyzer._create_fallback_sentiment_result("This is great and excellent")
        assert positive_result.sentiment == SentimentType.POSITIVE
        assert positive_result.score > 0
        
        # Neutral text
        neutral_result = sentiment_analyzer._create_fallback_sentiment_result("This is okay")
        assert neutral_result.sentiment == SentimentType.NEUTRAL
        assert neutral_result.score == 0
    
    @pytest.mark.asyncio
    async def test_store_sentiment_analysis_success(
        self,
        sentiment_analyzer,
        mock_message
    ):
        """Test successful sentiment analysis storage"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.POSITIVE,
            score=0.8,
            confidence=0.9,
            requires_attention=False,
            reason="Positive feedback",
            keywords=["great", "excellent"]
        )
        
        mock_sentiment_record = MagicMock()
        sentiment_analyzer.db.add = MagicMock()
        sentiment_analyzer.db.commit = MagicMock()
        sentiment_analyzer.db.refresh = MagicMock()
        
        with patch('app.services.sentiment_analyzer.SentimentAnalysis', return_value=mock_sentiment_record):
            stored_record = await sentiment_analyzer._store_sentiment_analysis(
                message=mock_message,
                result=result,
                processing_time_ms=500,
                correlation_id="test-correlation-id"
            )
            
            assert stored_record == mock_sentiment_record
            sentiment_analyzer.db.add.assert_called_once_with(mock_sentiment_record)
            sentiment_analyzer.db.commit.assert_called_once()
            sentiment_analyzer.db.refresh.assert_called_once_with(mock_sentiment_record)
    
    @pytest.mark.asyncio
    async def test_get_message_sentiment(self, sentiment_analyzer):
        """Test getting existing sentiment for message"""
        mock_sentiment = MagicMock()
        sentiment_analyzer.db.query.return_value.filter.return_value.first.return_value = mock_sentiment
        
        result = await sentiment_analyzer.get_message_sentiment("test-message-id")
        
        assert result == mock_sentiment
    
    @pytest.mark.asyncio
    async def test_get_guest_sentiment_history(self, sentiment_analyzer):
        """Test getting guest sentiment history"""
        mock_sentiments = [MagicMock(), MagicMock()]
        sentiment_analyzer.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_sentiments
        
        result = await sentiment_analyzer.get_guest_sentiment_history("test-guest-id", limit=5)
        
        assert result == mock_sentiments


if __name__ == "__main__":
    pytest.main([__file__])
