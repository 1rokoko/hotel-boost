"""
Mock objects for DeepSeek API testing
"""

import asyncio
import random
import time
import re
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from app.schemas.deepseek import (
    SentimentAnalysisRequest, SentimentAnalysisResult, SentimentType,
    ChatCompletionRequest, ChatCompletionResponse, ChatMessage, ChatRole,
    ResponseGenerationRequest, ResponseGenerationResult
)


class DeepSeekMock:
    """Mock DeepSeek API responses and behavior"""

    def __init__(self):
        self.request_counter = 0
        self.total_tokens_used = 0

        # Simulate network delays
        self.simulate_delays = True
        self.min_delay = 0.1
        self.max_delay = 0.8

        # Simulate failures
        self.failure_rate = 0.0
        self.rate_limit_enabled = False
        self.daily_token_limit = 100000

        # Sentiment analysis patterns
        self.sentiment_patterns = {
            SentimentType.POSITIVE: [
                r'\b(great|excellent|amazing|wonderful|fantastic|love|perfect|happy|satisfied|thank)\b',
                r'\b(good|nice|pleased|comfortable|enjoy|appreciate|recommend)\b'
            ],
            SentimentType.NEGATIVE: [
                r'\b(terrible|awful|horrible|hate|worst|disappointed|angry|frustrated|complain)\b',
                r'\b(bad|poor|unacceptable|disgusting|rude|slow|dirty|broken|problem)\b'
            ],
            SentimentType.NEUTRAL: [
                r'\b(okay|fine|average|normal|standard|regular|usual)\b',
                r'\b(question|inquiry|information|help|assistance|booking|reservation)\b'
            ]
        }

        # Response templates for different scenarios
        self.response_templates = {
            "greeting": [
                "Hello! Welcome to our hotel. How can I assist you today?",
                "Hi there! Thank you for contacting us. What can I help you with?",
                "Good day! I'm here to help with any questions about your stay."
            ],
            "booking": [
                "I'd be happy to help you with your booking. Could you please provide your reservation details?",
                "Let me assist you with your reservation. What specific information do you need?",
                "I can help you with booking inquiries. What would you like to know?"
            ],
            "complaint": [
                "I sincerely apologize for any inconvenience. Let me help resolve this issue immediately.",
                "I'm sorry to hear about this problem. I'll make sure to address it right away.",
                "Thank you for bringing this to our attention. I'll ensure this is resolved promptly."
            ],
            "amenities": [
                "I'd be happy to provide information about our hotel amenities. What specifically interests you?",
                "Our hotel offers various amenities. Which ones would you like to know more about?",
                "Let me share details about our facilities. What amenities are you curious about?"
            ],
            "checkout": [
                "I can assist you with checkout procedures. What do you need help with?",
                "Let me help you with the checkout process. Do you have any specific questions?",
                "I'm here to make your checkout smooth. How can I assist you?"
            ]
        }

    async def _simulate_delay(self):
        """Simulate API response delay"""
        if self.simulate_delays:
            delay = random.uniform(self.min_delay, self.max_delay)
            await asyncio.sleep(delay)

    def _should_fail(self) -> bool:
        """Determine if request should fail"""
        return random.random() < self.failure_rate

    def _check_rate_limit(self) -> bool:
        """Check if rate limit is exceeded"""
        if self.rate_limit_enabled and self.total_tokens_used > self.daily_token_limit:
            return True
        return False

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        # Rough estimation: ~4 characters per token
        return max(1, len(text) // 4)

    def _analyze_sentiment_by_patterns(self, text: str) -> tuple[SentimentType, float, str]:
        """Analyze sentiment using pattern matching"""
        text_lower = text.lower()

        # Count matches for each sentiment
        sentiment_scores = {
            SentimentType.POSITIVE: 0,
            SentimentType.NEGATIVE: 0,
            SentimentType.NEUTRAL: 0
        }

        for sentiment, patterns in self.sentiment_patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                sentiment_scores[sentiment] += matches

        # Determine dominant sentiment
        max_score = max(sentiment_scores.values())
        if max_score == 0:
            # Default to neutral if no patterns match
            return SentimentType.NEUTRAL, 0.6, "No clear sentiment indicators found"

        dominant_sentiment = max(sentiment_scores, key=sentiment_scores.get)
        confidence = min(0.95, 0.5 + (max_score * 0.1))  # Scale confidence based on matches

        reasoning_map = {
            SentimentType.POSITIVE: "Message contains positive language and expressions",
            SentimentType.NEGATIVE: "Message contains negative language and complaints",
            SentimentType.NEUTRAL: "Message appears to be informational or neutral inquiry"
        }

        return dominant_sentiment, confidence, reasoning_map[dominant_sentiment]

    def _categorize_message(self, text: str) -> str:
        """Categorize message type for response generation"""
        text_lower = text.lower()

        if any(word in text_lower for word in ['hello', 'hi', 'good morning', 'good evening']):
            return "greeting"
        elif any(word in text_lower for word in ['book', 'reservation', 'room', 'availability']):
            return "booking"
        elif any(word in text_lower for word in ['problem', 'issue', 'complaint', 'wrong', 'broken']):
            return "complaint"
        elif any(word in text_lower for word in ['amenities', 'facilities', 'pool', 'gym', 'restaurant']):
            return "amenities"
        elif any(word in text_lower for word in ['checkout', 'check out', 'leaving', 'bill']):
            return "checkout"
        else:
            return "general"

    async def analyze_sentiment(self, request: SentimentAnalysisRequest) -> SentimentAnalysisResult:
        """Mock sentiment analysis"""
        await self._simulate_delay()

        if self._should_fail():
            raise Exception("Mock DeepSeek API failure")

        if self._check_rate_limit():
            raise Exception("Rate limit exceeded")

        self.request_counter += 1
        tokens_used = self._estimate_tokens(request.text)
        self.total_tokens_used += tokens_used

        # Analyze sentiment using patterns
        sentiment, confidence, reasoning = self._analyze_sentiment_by_patterns(request.text)

        # Determine if requires attention (negative sentiment with high confidence)
        requires_attention = (
            sentiment == SentimentType.NEGATIVE and confidence > 0.7
        ) or any(word in request.text.lower() for word in [
            'emergency', 'urgent', 'immediately', 'serious', 'dangerous'
        ])

        return SentimentAnalysisResult(
            sentiment=sentiment,
            confidence=confidence,
            requires_attention=requires_attention,
            reasoning=reasoning,
            categories=self._extract_categories(request.text),
            tokens_used=tokens_used
        )

    def _extract_categories(self, text: str) -> List[str]:
        """Extract categories from text"""
        categories = []
        text_lower = text.lower()

        category_keywords = {
            "room_service": ["room service", "food", "meal", "order", "delivery"],
            "housekeeping": ["clean", "towel", "bed", "housekeeping", "maintenance"],
            "front_desk": ["check in", "check out", "key", "reception", "lobby"],
            "amenities": ["pool", "gym", "spa", "restaurant", "wifi", "parking"],
            "billing": ["bill", "charge", "payment", "invoice", "cost", "price"],
            "complaint": ["problem", "issue", "complaint", "wrong", "broken", "dirty"]
        }

        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                categories.append(category)

        return categories if categories else ["general"]

    async def generate_response(self, request: ResponseGenerationRequest) -> ResponseGenerationResult:
        """Mock response generation"""
        await self._simulate_delay()

        if self._should_fail():
            raise Exception("Mock DeepSeek API failure")

        if self._check_rate_limit():
            raise Exception("Rate limit exceeded")

        self.request_counter += 1
        tokens_used = self._estimate_tokens(request.message + (request.context or ""))
        self.total_tokens_used += tokens_used

        # Categorize message and generate appropriate response
        category = self._categorize_message(request.message)

        if category in self.response_templates:
            response_text = random.choice(self.response_templates[category])
        else:
            response_text = "Thank you for your message. How can I assist you today?"

        # Personalize response if guest name is provided
        if request.guest_name:
            response_text = f"Hello {request.guest_name}! " + response_text

        # Add hotel-specific context if provided
        if request.hotel_context:
            if "name" in request.hotel_context:
                response_text = response_text.replace("our hotel", request.hotel_context["name"])

        return ResponseGenerationResult(
            response=response_text,
            confidence=random.uniform(0.7, 0.95),
            suggested_actions=self._generate_suggested_actions(category),
            tokens_used=tokens_used
        )

    def _generate_suggested_actions(self, category: str) -> List[str]:
        """Generate suggested actions based on message category"""
        action_map = {
            "greeting": ["send_welcome_message", "offer_assistance"],
            "booking": ["check_availability", "send_booking_form", "transfer_to_reservations"],
            "complaint": ["escalate_to_manager", "send_apology", "schedule_follow_up"],
            "amenities": ["send_amenities_list", "provide_hours", "send_location_map"],
            "checkout": ["send_checkout_instructions", "prepare_bill", "arrange_transportation"],
            "general": ["offer_assistance", "ask_for_clarification"]
        }

        return action_map.get(category, ["offer_assistance"])

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Mock chat completion"""
        await self._simulate_delay()

        if self._should_fail():
            raise Exception("Mock DeepSeek API failure")

        if self._check_rate_limit():
            raise Exception("Rate limit exceeded")

        self.request_counter += 1

        # Calculate tokens for all messages
        total_input_tokens = sum(self._estimate_tokens(msg.content) for msg in request.messages)

        # Generate response based on last message
        last_message = request.messages[-1] if request.messages else None
        if last_message:
            category = self._categorize_message(last_message.content)
            if category in self.response_templates:
                response_content = random.choice(self.response_templates[category])
            else:
                response_content = "I understand. How can I help you further?"
        else:
            response_content = "Hello! How can I assist you today?"

        output_tokens = self._estimate_tokens(response_content)
        total_tokens = total_input_tokens + output_tokens
        self.total_tokens_used += total_tokens

        return ChatCompletionResponse(
            id=f"chatcmpl-mock-{self.request_counter}",
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": total_input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens
            }
        )

    def set_failure_rate(self, rate: float):
        """Set failure rate for testing error scenarios"""
        self.failure_rate = max(0.0, min(1.0, rate))

    def enable_rate_limiting(self, enabled: bool = True, daily_limit: int = 100000):
        """Enable/disable rate limiting simulation"""
        self.rate_limit_enabled = enabled
        self.daily_token_limit = daily_limit

    def reset_usage(self):
        """Reset usage counters"""
        self.request_counter = 0
        self.total_tokens_used = 0

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "request_count": self.request_counter,
            "total_tokens_used": self.total_tokens_used,
            "remaining_tokens": max(0, self.daily_token_limit - self.total_tokens_used),
            "rate_limit_enabled": self.rate_limit_enabled,
            "failure_rate": self.failure_rate
        }


class MockDeepSeekClient:
    """Mock DeepSeek client for testing"""

    def __init__(self, config=None):
        self.config = config
        self.mock_api = DeepSeekMock()
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

    async def analyze_sentiment(self, request: SentimentAnalysisRequest) -> SentimentAnalysisResult:
        """Mock sentiment analysis"""
        await self._track_request()
        try:
            return await self.mock_api.analyze_sentiment(request)
        except Exception as e:
            self.error_count += 1
            raise

    async def generate_response(self, request: ResponseGenerationRequest) -> ResponseGenerationResult:
        """Mock response generation"""
        await self._track_request()
        try:
            return await self.mock_api.generate_response(request)
        except Exception as e:
            self.error_count += 1
            raise

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Mock chat completion"""
        await self._track_request()
        try:
            return await self.mock_api.chat_completion(request)
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
            "api_usage": self.mock_api.get_usage_stats()
        }


# Export main components
__all__ = [
    'DeepSeekMock',
    'MockDeepSeekClient'
]