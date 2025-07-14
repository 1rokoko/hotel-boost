"""
Unit tests for sentiment analysis functionality
"""

import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.sentiment_analyzer import SentimentAnalyzer
from app.services.realtime_sentiment import RealtimeSentimentAnalyzer
from app.utils.sentiment_processor import SentimentProcessor
from app.schemas.deepseek import SentimentAnalysisResult, SentimentType
from app.models.message import Message, MessageType
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.models.sentiment import SentimentAnalysis


class TestSentimentAnalyzer:
    """Test cases for SentimentAnalyzer"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def sentiment_analyzer(self, mock_db):
        """Create SentimentAnalyzer instance"""
        return SentimentAnalyzer(mock_db)
    
    @pytest.fixture
    def sample_message(self):
        """Create sample message"""
        return Message(
            id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            guest_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            content="The room was dirty and the service was terrible!",
            message_type=MessageType.TEXT,
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def negative_sentiment_result(self):
        """Create negative sentiment result"""
        return SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.7,
            confidence=0.85,
            requires_attention=True,
            reason="Guest expressed dissatisfaction with room cleanliness and service quality",
            keywords=["dirty", "terrible", "service"]
        )
    
    @pytest.fixture
    def positive_sentiment_result(self):
        """Create positive sentiment result"""
        return SentimentAnalysisResult(
            sentiment=SentimentType.POSITIVE,
            score=0.8,
            confidence=0.9,
            requires_attention=False,
            reason="Guest expressed satisfaction with the experience",
            keywords=["excellent", "amazing", "perfect"]
        )
    
    @pytest.mark.asyncio
    async def test_analyze_message_sentiment_negative(
        self,
        sentiment_analyzer,
        sample_message,
        negative_sentiment_result
    ):
        """Test sentiment analysis for negative message"""
        # Mock the AI analysis
        with patch.object(sentiment_analyzer, '_analyze_sentiment_with_ai', return_value=negative_sentiment_result):
            with patch.object(sentiment_analyzer, '_store_sentiment_analysis') as mock_store:
                mock_store.return_value = Mock()
                
                result = await sentiment_analyzer.analyze_message_sentiment(
                    message=sample_message,
                    correlation_id="test-correlation-id"
                )
                
                assert result.sentiment == SentimentType.NEGATIVE
                assert result.score == -0.7
                assert result.confidence == 0.85
                assert result.requires_attention is True
                assert "dirty" in result.keywords
                mock_store.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_message_sentiment_positive(
        self,
        sentiment_analyzer,
        sample_message,
        positive_sentiment_result
    ):
        """Test sentiment analysis for positive message"""
        sample_message.content = "The hotel was amazing and the staff was excellent!"
        
        with patch.object(sentiment_analyzer, '_analyze_sentiment_with_ai', return_value=positive_sentiment_result):
            with patch.object(sentiment_analyzer, '_store_sentiment_analysis') as mock_store:
                mock_store.return_value = Mock()
                
                result = await sentiment_analyzer.analyze_message_sentiment(
                    message=sample_message,
                    correlation_id="test-correlation-id"
                )
                
                assert result.sentiment == SentimentType.POSITIVE
                assert result.score == 0.8
                assert result.confidence == 0.9
                assert result.requires_attention is False
                assert "excellent" in result.keywords
    
    @pytest.mark.asyncio
    async def test_analyze_message_sentiment_fallback(
        self,
        sentiment_analyzer,
        sample_message
    ):
        """Test sentiment analysis fallback when AI fails"""
        with patch.object(sentiment_analyzer, '_analyze_sentiment_with_ai', side_effect=Exception("AI service unavailable")):
            with patch.object(sentiment_analyzer, '_fallback_sentiment_analysis') as mock_fallback:
                mock_fallback.return_value = SentimentAnalysisResult(
                    sentiment=SentimentType.NEGATIVE,
                    score=-0.5,
                    confidence=0.3,
                    requires_attention=False,
                    reason="Fallback analysis",
                    keywords=[]
                )
                with patch.object(sentiment_analyzer, '_store_sentiment_analysis'):
                    
                    result = await sentiment_analyzer.analyze_message_sentiment(
                        message=sample_message,
                        correlation_id="test-correlation-id"
                    )
                    
                    assert result.confidence == 0.3  # Low confidence for fallback
                    mock_fallback.assert_called_once()
    
    def test_fallback_sentiment_analysis_negative_keywords(self, sentiment_analyzer):
        """Test fallback analysis with negative keywords"""
        text = "This is terrible, awful, and horrible service!"
        
        result = sentiment_analyzer._fallback_sentiment_analysis(text)
        
        assert result.sentiment == SentimentType.NEGATIVE
        assert result.score < 0
        assert result.confidence == 0.3
        assert result.reason == "Fallback analysis due to AI service unavailability"
    
    def test_fallback_sentiment_analysis_positive_keywords(self, sentiment_analyzer):
        """Test fallback analysis with positive keywords"""
        text = "This is excellent, amazing, and wonderful service!"
        
        result = sentiment_analyzer._fallback_sentiment_analysis(text)
        
        assert result.sentiment == SentimentType.POSITIVE
        assert result.score > 0
        assert result.confidence == 0.3
    
    def test_fallback_sentiment_analysis_neutral(self, sentiment_analyzer):
        """Test fallback analysis with neutral text"""
        text = "I would like to check in please."
        
        result = sentiment_analyzer._fallback_sentiment_analysis(text)
        
        assert result.sentiment == SentimentType.NEUTRAL
        assert abs(result.score) < 0.1
        assert result.confidence == 0.3


class TestRealtimeSentimentAnalyzer:
    """Test cases for RealtimeSentimentAnalyzer"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def realtime_analyzer(self, mock_db):
        """Create RealtimeSentimentAnalyzer instance"""
        with patch('app.services.realtime_sentiment.SentimentAnalyzer'):
            with patch('app.services.realtime_sentiment.StaffNotificationService'):
                return RealtimeSentimentAnalyzer(mock_db)
    
    @pytest.fixture
    def sample_message(self):
        """Create sample message"""
        return Message(
            id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            guest_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            content="The service was disappointing",
            message_type=MessageType.TEXT,
            created_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_analyze_message_triggers_alert(
        self,
        realtime_analyzer,
        sample_message
    ):
        """Test that negative sentiment triggers alert"""
        negative_result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.6,
            confidence=0.8,
            requires_attention=True,
            reason="Negative sentiment detected",
            keywords=["disappointing"]
        )
        
        with patch.object(realtime_analyzer.sentiment_analyzer, 'analyze_message_sentiment', return_value=negative_result):
            with patch.object(realtime_analyzer, 'should_trigger_alert', return_value=True):
                with patch.object(realtime_analyzer, 'trigger_alerts_if_needed') as mock_trigger:
                    
                    result = await realtime_analyzer.analyze_message(
                        message=sample_message,
                        conversation_id=str(sample_message.conversation_id),
                        correlation_id="test-correlation-id"
                    )
                    
                    assert result.score == -0.6
                    mock_trigger.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_should_trigger_alert_requires_attention(
        self,
        realtime_analyzer,
        sample_message
    ):
        """Test alert triggering when requires_attention is True"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.2,  # Not very negative
            confidence=0.8,
            requires_attention=True,  # But flagged for attention
            reason="AI flagged for attention",
            keywords=[]
        )
        
        should_alert = await realtime_analyzer.should_trigger_alert(result, sample_message)
        assert should_alert is True
    
    @pytest.mark.asyncio
    async def test_should_trigger_alert_negative_score(
        self,
        realtime_analyzer,
        sample_message
    ):
        """Test alert triggering for negative score"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.5,  # Negative score
            confidence=0.8,
            requires_attention=False,
            reason="Negative sentiment",
            keywords=[]
        )
        
        should_alert = await realtime_analyzer.should_trigger_alert(result, sample_message)
        assert should_alert is True
    
    @pytest.mark.asyncio
    async def test_should_not_trigger_alert_positive(
        self,
        realtime_analyzer,
        sample_message
    ):
        """Test that positive sentiment doesn't trigger alert"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.POSITIVE,
            score=0.7,
            confidence=0.8,
            requires_attention=False,
            reason="Positive sentiment",
            keywords=[]
        )
        
        with patch.object(realtime_analyzer, '_count_recent_negative_messages', return_value=0):
            should_alert = await realtime_analyzer.should_trigger_alert(result, sample_message)
            assert should_alert is False
    
    def test_calculate_urgency_level_critical(self, realtime_analyzer):
        """Test urgency calculation for critical sentiment"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.REQUIRES_ATTENTION,
            score=-0.9,
            confidence=0.9,
            requires_attention=True,
            reason="Critical issue",
            keywords=[]
        )
        
        urgency = realtime_analyzer._calculate_urgency_level(result)
        assert urgency == 5  # Critical
    
    def test_calculate_urgency_level_medium(self, realtime_analyzer):
        """Test urgency calculation for medium sentiment"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.4,
            confidence=0.8,
            requires_attention=False,
            reason="Negative sentiment",
            keywords=[]
        )
        
        urgency = realtime_analyzer._calculate_urgency_level(result)
        assert urgency == 2  # Low-Medium


class TestSentimentProcessor:
    """Test cases for SentimentProcessor"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def sentiment_processor(self, mock_db):
        """Create SentimentProcessor instance"""
        return SentimentProcessor(mock_db)
    
    @pytest.fixture
    def sample_message(self):
        """Create sample message"""
        return Message(
            id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            guest_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            content="The room was not clean",
            message_type=MessageType.TEXT,
            created_at=datetime.utcnow()
        )
    
    def test_classify_sentiment_level_very_positive(self, sentiment_processor):
        """Test sentiment level classification for very positive"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.POSITIVE,
            score=0.8,
            confidence=0.9,
            requires_attention=False,
            reason="Very positive",
            keywords=["excellent"]
        )
        
        classification = sentiment_processor._classify_sentiment_level(result)
        assert classification["level"] == "very_positive"
        assert classification["score"] == 0.8
    
    def test_classify_sentiment_level_critical(self, sentiment_processor):
        """Test sentiment level classification for critical"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.9,
            confidence=0.9,
            requires_attention=True,
            reason="Critical issue",
            keywords=["terrible"]
        )
        
        classification = sentiment_processor._classify_sentiment_level(result)
        assert classification["level"] == "critical"
        assert classification["requires_attention"] is True
    
    def test_assess_urgency_high_score(self, sentiment_processor, sample_message):
        """Test urgency assessment for high negative score"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.8,
            confidence=0.9,
            requires_attention=True,
            reason="Very negative",
            keywords=[]
        )
        
        with patch.object(sentiment_processor, '_count_recent_negative_messages', return_value=1):
            urgency = sentiment_processor._assess_urgency(result, sample_message)
            assert urgency["level"] in ["critical", "high"]
            assert "critical_sentiment" in urgency["factors"]
    
    def test_recommend_actions_negative_sentiment(self, sentiment_processor, sample_message):
        """Test action recommendations for negative sentiment"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.6,
            confidence=0.8,
            requires_attention=True,
            reason="Negative feedback",
            keywords=[]
        )
        
        with patch.object(sentiment_processor, '_count_recent_negative_messages', return_value=1):
            actions = sentiment_processor._recommend_actions(result, sample_message)
            
            action_types = [action["action"] for action in actions]
            assert "immediate_staff_notification" in action_types
            assert "manager_review" in action_types
    
    def test_should_escalate_critical_score(self, sentiment_processor, sample_message):
        """Test escalation decision for critical score"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.8,
            confidence=0.9,
            requires_attention=False,
            reason="Very negative",
            keywords=[]
        )
        
        should_escalate = sentiment_processor._should_escalate(result, sample_message)
        assert should_escalate is True
    
    def test_should_escalate_requires_attention(self, sentiment_processor, sample_message):
        """Test escalation decision when requires attention"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.4,
            confidence=0.8,
            requires_attention=True,
            reason="Flagged for attention",
            keywords=[]
        )
        
        should_escalate = sentiment_processor._should_escalate(result, sample_message)
        assert should_escalate is True
    
    def test_should_not_escalate_mild_negative(self, sentiment_processor, sample_message):
        """Test no escalation for mild negative sentiment"""
        result = SentimentAnalysisResult(
            sentiment=SentimentType.NEGATIVE,
            score=-0.2,
            confidence=0.8,
            requires_attention=False,
            reason="Mild negative",
            keywords=[]
        )
        
        with patch.object(sentiment_processor, '_count_recent_negative_messages', return_value=1):
            should_escalate = sentiment_processor._should_escalate(result, sample_message)
            assert should_escalate is False
