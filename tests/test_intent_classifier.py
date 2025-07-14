"""
Unit tests for intent classifier
"""

import pytest
from unittest.mock import Mock, AsyncMock
import json

from app.utils.intent_classifier import IntentClassifier, MessageIntent, IntentClassificationResult
from app.services.deepseek_client import DeepSeekClient


class TestIntentClassifier:
    """Test cases for IntentClassifier"""
    
    @pytest.fixture
    def mock_deepseek_client(self):
        """Create mock DeepSeek client"""
        client = Mock(spec=DeepSeekClient)
        client.generate_response = AsyncMock()
        return client
    
    @pytest.fixture
    def intent_classifier(self, mock_deepseek_client):
        """Create intent classifier with mock client"""
        return IntentClassifier(mock_deepseek_client)
    
    @pytest.mark.asyncio
    async def test_classify_emergency_intent(self, intent_classifier):
        """Test emergency intent classification"""
        message = "HELP! There's a fire in my room!"
        
        result = await intent_classifier.classify_intent(message)
        
        assert isinstance(result, IntentClassificationResult)
        assert result.intent == MessageIntent.EMERGENCY
        assert result.confidence == 1.0
        assert result.urgency_level == 5
        assert 'fire' in result.keywords
    
    @pytest.mark.asyncio
    async def test_classify_complaint_intent_with_rules(self, intent_classifier):
        """Test complaint intent classification using rules"""
        message = "This room is absolutely terrible and I want a refund"
        
        result = await intent_classifier.classify_intent(message)
        
        assert result.intent == MessageIntent.COMPLAINT
        assert result.confidence > 0.5
        assert result.urgency_level >= 3
        assert any(keyword in ['terrible', 'refund'] for keyword in result.keywords)
    
    @pytest.mark.asyncio
    async def test_classify_booking_inquiry_with_rules(self, intent_classifier):
        """Test booking inquiry classification using rules"""
        message = "Do you have any rooms available for next weekend?"
        
        result = await intent_classifier.classify_intent(message)
        
        assert result.intent == MessageIntent.BOOKING_INQUIRY
        assert result.confidence > 0.3
        assert result.urgency_level <= 3
    
    @pytest.mark.asyncio
    async def test_classify_with_ai_success(self, intent_classifier, mock_deepseek_client):
        """Test AI classification success"""
        # Mock AI response
        ai_response = {
            'content': json.dumps({
                'intent': 'room_issue',
                'confidence': 0.9,
                'entities': {'room_number': '205'},
                'sentiment_score': -0.3,
                'urgency_level': 3,
                'reasoning': 'Guest reporting room problem'
            })
        }
        mock_deepseek_client.generate_response.return_value = ai_response
        
        message = "The air conditioning in room 205 is not working"
        result = await intent_classifier.classify_intent(message)
        
        assert result.intent == MessageIntent.ROOM_ISSUE
        assert result.confidence == 0.9
        assert result.entities == {'room_number': '205'}
        assert result.sentiment_score == -0.3
        assert result.urgency_level == 3
    
    @pytest.mark.asyncio
    async def test_classify_with_ai_failure_fallback_to_rules(self, intent_classifier, mock_deepseek_client):
        """Test fallback to rules when AI fails"""
        # Mock AI failure
        mock_deepseek_client.generate_response.side_effect = Exception("API Error")
        
        message = "I need housekeeping to clean my room"
        result = await intent_classifier.classify_intent(message)
        
        assert result.intent == MessageIntent.REQUEST_SERVICE
        assert result.confidence > 0.0
        assert 'housekeeping' in result.keywords
    
    @pytest.mark.asyncio
    async def test_classify_with_context(self, intent_classifier):
        """Test classification with conversation context"""
        message = "Yes, that would be great"
        context = {
            'conversation_state': 'collecting_info',
            'recent_messages': [
                {'content': 'Would you like room service?', 'type': 'text'}
            ]
        }
        
        result = await intent_classifier.classify_intent(message, context)
        
        assert isinstance(result, IntentClassificationResult)
        # Should classify as general question due to ambiguous content
        assert result.intent in [MessageIntent.GENERAL_QUESTION, MessageIntent.REQUEST_SERVICE]
    
    def test_is_emergency_detection(self, intent_classifier):
        """Test emergency detection"""
        emergency_messages = [
            "EMERGENCY! Call 911!",
            "There's a fire in the building",
            "Someone is having a heart attack",
            "Help! I'm being robbed!",
            "Medical emergency in room 301"
        ]
        
        for message in emergency_messages:
            assert intent_classifier._is_emergency(message), f"Failed to detect emergency in: {message}"
    
    def test_non_emergency_detection(self, intent_classifier):
        """Test non-emergency detection"""
        normal_messages = [
            "The room is very nice",
            "Can I get extra towels?",
            "What time is checkout?",
            "The wifi password please",
            "Thank you for your help"
        ]
        
        for message in normal_messages:
            assert not intent_classifier._is_emergency(message), f"False emergency detected in: {message}"
    
    def test_extract_emergency_keywords(self, intent_classifier):
        """Test emergency keyword extraction"""
        message = "EMERGENCY! There's a fire and someone needs medical help!"
        keywords = intent_classifier._extract_emergency_keywords(message)
        
        assert 'emergency' in keywords
        assert 'fire' in keywords
        assert 'medical' in keywords
    
    def test_calculate_urgency_levels(self, intent_classifier):
        """Test urgency level calculation"""
        test_cases = [
            (MessageIntent.EMERGENCY, [], 5),
            (MessageIntent.COMPLAINT, ['urgent'], 5),
            (MessageIntent.COMPLAINT, [], 4),
            (MessageIntent.ROOM_ISSUE, ['broken'], 4),
            (MessageIntent.ROOM_ISSUE, [], 3),
            (MessageIntent.BOOKING_INQUIRY, [], 2),
            (MessageIntent.GENERAL_QUESTION, [], 1),
            (MessageIntent.COMPLIMENT, [], 1),
        ]
        
        for intent, keywords, expected_urgency in test_cases:
            urgency = intent_classifier._calculate_urgency(intent, keywords)
            assert urgency == expected_urgency, f"Wrong urgency for {intent.value} with keywords {keywords}"
    
    def test_keyword_pattern_matching(self, intent_classifier):
        """Test keyword pattern matching for different intents"""
        test_cases = [
            ("I want to book a room", MessageIntent.BOOKING_INQUIRY),
            ("This is a terrible experience", MessageIntent.COMPLAINT),
            ("Can I get room service?", MessageIntent.REQUEST_SERVICE),
            ("The TV is not working", MessageIntent.ROOM_ISSUE),
            ("What's the wifi password?", MessageIntent.AMENITY_QUESTION),
            ("I want to cancel my reservation", MessageIntent.CANCELLATION),
            ("Thank you so much!", MessageIntent.COMPLIMENT),
            ("Hello there", MessageIntent.GREETING),
            ("Goodbye", MessageIntent.GOODBYE),
        ]
        
        for message, expected_intent in test_cases:
            result = intent_classifier._classify_with_rules(message)
            assert result.intent == expected_intent, f"Wrong intent for message: {message}"
    
    @pytest.mark.asyncio
    async def test_parse_ai_response_valid_json(self, intent_classifier):
        """Test parsing valid AI response"""
        response_content = json.dumps({
            'intent': 'booking_inquiry',
            'confidence': 0.85,
            'entities': {'dates': ['2024-01-15']},
            'sentiment_score': 0.1,
            'urgency_level': 2,
            'reasoning': 'Guest asking about availability'
        })
        
        result = intent_classifier._parse_ai_response(response_content, "test message")
        
        assert result.intent == MessageIntent.BOOKING_INQUIRY
        assert result.confidence == 0.85
        assert result.entities == {'dates': ['2024-01-15']}
        assert result.sentiment_score == 0.1
        assert result.urgency_level == 2
    
    @pytest.mark.asyncio
    async def test_parse_ai_response_invalid_json(self, intent_classifier):
        """Test parsing invalid AI response"""
        response_content = "This is not valid JSON"
        
        result = intent_classifier._parse_ai_response(response_content, "test message")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parse_ai_response_invalid_intent(self, intent_classifier):
        """Test parsing AI response with invalid intent"""
        response_content = json.dumps({
            'intent': 'invalid_intent_type',
            'confidence': 0.85,
            'reasoning': 'Test response'
        })
        
        result = intent_classifier._parse_ai_response(response_content, "test message")
        
        assert result.intent == MessageIntent.UNKNOWN
        assert result.confidence == 0.85
    
    def test_build_classification_prompt(self, intent_classifier):
        """Test building classification prompt"""
        message = "Can I book a room?"
        context = {'conversation_state': 'greeting'}
        
        prompt = intent_classifier._build_classification_prompt(message, context)
        
        assert message in prompt
        assert 'booking_inquiry' in prompt
        assert 'JSON' in prompt
        assert 'confidence' in prompt
    
    @pytest.mark.asyncio
    async def test_classify_unknown_intent(self, intent_classifier, mock_deepseek_client):
        """Test classification of unknown/ambiguous messages"""
        # Mock AI failure
        mock_deepseek_client.generate_response.return_value = None
        
        message = "Hmm, okay, sure"
        result = await intent_classifier.classify_intent(message)
        
        # Should default to general question or unknown
        assert result.intent in [MessageIntent.GENERAL_QUESTION, MessageIntent.UNKNOWN]
        assert result.confidence <= 0.5
    
    @pytest.mark.asyncio
    async def test_classify_with_high_confidence_ai_result(self, intent_classifier, mock_deepseek_client):
        """Test that high confidence AI results are preferred over rules"""
        # Mock high confidence AI response
        ai_response = {
            'content': json.dumps({
                'intent': 'general_question',
                'confidence': 0.95,
                'reasoning': 'High confidence classification'
            })
        }
        mock_deepseek_client.generate_response.return_value = ai_response
        
        # Message that would normally be classified as complaint by rules
        message = "This is terrible but I understand"
        result = await intent_classifier.classify_intent(message)
        
        # Should use AI result due to high confidence
        assert result.intent == MessageIntent.GENERAL_QUESTION
        assert result.confidence == 0.95


class TestIntentClassificationResult:
    """Test cases for IntentClassificationResult"""
    
    def test_intent_classification_result_creation(self):
        """Test creating IntentClassificationResult"""
        result = IntentClassificationResult(
            intent=MessageIntent.BOOKING_INQUIRY,
            confidence=0.85,
            entities={'dates': ['2024-01-15']},
            keywords=['book', 'room'],
            sentiment_score=0.2,
            urgency_level=2,
            reasoning="Guest asking about availability"
        )
        
        assert result.intent == MessageIntent.BOOKING_INQUIRY
        assert result.confidence == 0.85
        assert result.entities == {'dates': ['2024-01-15']}
        assert result.keywords == ['book', 'room']
        assert result.sentiment_score == 0.2
        assert result.urgency_level == 2
        assert result.reasoning == "Guest asking about availability"
        assert result.timestamp is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
