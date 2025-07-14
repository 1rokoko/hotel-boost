"""
Intent classification system for guest messages
"""

from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import re
import structlog
from datetime import datetime

from app.services.deepseek_client import DeepSeekClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class MessageIntent(str, Enum):
    """Enumeration of message intents"""
    BOOKING_INQUIRY = "booking_inquiry"
    COMPLAINT = "complaint"
    REQUEST_SERVICE = "request_service"
    GENERAL_QUESTION = "general_question"
    EMERGENCY = "emergency"
    COMPLIMENT = "compliment"
    CANCELLATION = "cancellation"
    ROOM_ISSUE = "room_issue"
    BILLING_QUESTION = "billing_question"
    AMENITY_QUESTION = "amenity_question"
    GREETING = "greeting"
    GOODBYE = "goodbye"
    UNKNOWN = "unknown"


class IntentClassificationResult:
    """Result of intent classification"""
    
    def __init__(
        self,
        intent: MessageIntent,
        confidence: float,
        entities: Dict[str, Any] = None,
        keywords: List[str] = None,
        sentiment_score: Optional[float] = None,
        urgency_level: int = 1,
        reasoning: str = ""
    ):
        self.intent = intent
        self.confidence = confidence
        self.entities = entities or {}
        self.keywords = keywords or []
        self.sentiment_score = sentiment_score
        self.urgency_level = urgency_level  # 1-5 scale
        self.reasoning = reasoning
        self.timestamp = datetime.utcnow()


class IntentClassifier:
    """
    Intent classifier using DeepSeek AI and rule-based fallbacks
    """
    
    def __init__(self, deepseek_client: DeepSeekClient):
        self.deepseek_client = deepseek_client
        self.keyword_patterns = self._setup_keyword_patterns()
        self.emergency_keywords = {
            'fire', 'emergency', 'help', 'urgent', 'police', 'ambulance',
            'medical', 'accident', 'danger', 'security', 'break-in', 'theft'
        }
    
    def _setup_keyword_patterns(self) -> Dict[MessageIntent, List[str]]:
        """Setup keyword patterns for rule-based classification"""
        return {
            MessageIntent.BOOKING_INQUIRY: [
                'book', 'reservation', 'available', 'vacancy', 'check-in',
                'check-out', 'dates', 'price', 'rate', 'cost'
            ],
            MessageIntent.COMPLAINT: [
                'complaint', 'complain', 'problem', 'issue', 'terrible',
                'awful', 'bad', 'worst', 'disappointed', 'angry', 'upset'
            ],
            MessageIntent.REQUEST_SERVICE: [
                'room service', 'housekeeping', 'maintenance', 'towels',
                'cleaning', 'repair', 'fix', 'broken', 'need', 'request'
            ],
            MessageIntent.ROOM_ISSUE: [
                'room', 'air conditioning', 'heating', 'tv', 'wifi',
                'bathroom', 'shower', 'bed', 'noise', 'temperature'
            ],
            MessageIntent.BILLING_QUESTION: [
                'bill', 'charge', 'payment', 'invoice', 'receipt',
                'refund', 'money', 'cost', 'fee', 'credit card'
            ],
            MessageIntent.AMENITY_QUESTION: [
                'pool', 'gym', 'spa', 'restaurant', 'bar', 'parking',
                'wifi', 'breakfast', 'amenities', 'facilities'
            ],
            MessageIntent.CANCELLATION: [
                'cancel', 'cancellation', 'refund', 'change booking',
                'modify reservation', 'reschedule'
            ],
            MessageIntent.COMPLIMENT: [
                'thank', 'thanks', 'great', 'excellent', 'wonderful',
                'amazing', 'perfect', 'love', 'appreciate', 'fantastic'
            ],
            MessageIntent.GREETING: [
                'hello', 'hi', 'hey', 'good morning', 'good evening',
                'greetings', 'howdy'
            ],
            MessageIntent.GOODBYE: [
                'goodbye', 'bye', 'see you', 'farewell', 'thanks again',
                'have a good', 'take care'
            ]
        }
    
    async def classify_intent(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentClassificationResult:
        """
        Classify the intent of a message
        
        Args:
            message: Message text to classify
            context: Additional context (conversation history, guest info, etc.)
            
        Returns:
            IntentClassificationResult: Classification result
        """
        try:
            # First check for emergency
            if self._is_emergency(message):
                return IntentClassificationResult(
                    intent=MessageIntent.EMERGENCY,
                    confidence=1.0,
                    urgency_level=5,
                    keywords=self._extract_emergency_keywords(message),
                    reasoning="Emergency keywords detected"
                )
            
            # Try AI classification first
            ai_result = await self._classify_with_ai(message, context)
            if ai_result and ai_result.confidence > 0.7:
                return ai_result
            
            # Fallback to rule-based classification
            rule_result = self._classify_with_rules(message)
            
            # Combine results if both available
            if ai_result and rule_result:
                # Use AI result but adjust confidence based on rule agreement
                if ai_result.intent == rule_result.intent:
                    ai_result.confidence = min(ai_result.confidence + 0.2, 1.0)
                else:
                    ai_result.confidence = max(ai_result.confidence - 0.1, 0.1)
                return ai_result
            
            # Return whichever result we have
            return ai_result or rule_result or IntentClassificationResult(
                intent=MessageIntent.UNKNOWN,
                confidence=0.1,
                reasoning="No classification method succeeded"
            )
            
        except Exception as e:
            logger.error("Intent classification failed", error=str(e), message=message[:100])
            return IntentClassificationResult(
                intent=MessageIntent.UNKNOWN,
                confidence=0.1,
                reasoning=f"Classification error: {str(e)}"
            )
    
    async def _classify_with_ai(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[IntentClassificationResult]:
        """Classify using DeepSeek AI"""
        try:
            # Prepare prompt for intent classification
            prompt = self._build_classification_prompt(message, context)
            
            # Call DeepSeek API
            response = await self.deepseek_client.generate_response(
                prompt=prompt,
                max_tokens=200,
                temperature=0.1  # Low temperature for consistent classification
            )
            
            if not response or not response.get('content'):
                return None
            
            # Parse AI response
            return self._parse_ai_response(response['content'], message)
            
        except Exception as e:
            logger.warning("AI classification failed", error=str(e))
            return None
    
    def _classify_with_rules(self, message: str) -> IntentClassificationResult:
        """Classify using rule-based approach"""
        message_lower = message.lower()
        
        # Calculate scores for each intent
        intent_scores = {}
        matched_keywords = {}
        
        for intent, keywords in self.keyword_patterns.items():
            score = 0
            matches = []
            
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
                    matches.append(keyword)
            
            if score > 0:
                intent_scores[intent] = score / len(keywords)  # Normalize by keyword count
                matched_keywords[intent] = matches
        
        if not intent_scores:
            return IntentClassificationResult(
                intent=MessageIntent.GENERAL_QUESTION,
                confidence=0.3,
                reasoning="No specific keywords found, defaulting to general question"
            )
        
        # Get best match
        best_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k])
        confidence = min(intent_scores[best_intent] * 2, 1.0)  # Scale confidence
        
        # Determine urgency
        urgency = self._calculate_urgency(best_intent, matched_keywords.get(best_intent, []))
        
        return IntentClassificationResult(
            intent=best_intent,
            confidence=confidence,
            keywords=matched_keywords.get(best_intent, []),
            urgency_level=urgency,
            reasoning=f"Rule-based classification based on keywords: {matched_keywords.get(best_intent, [])}"
        )
    
    def _build_classification_prompt(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for AI classification"""
        
        intent_descriptions = {
            MessageIntent.BOOKING_INQUIRY: "Questions about making reservations, availability, pricing",
            MessageIntent.COMPLAINT: "Complaints, problems, negative feedback",
            MessageIntent.REQUEST_SERVICE: "Requests for hotel services (room service, housekeeping, etc.)",
            MessageIntent.GENERAL_QUESTION: "General questions about the hotel",
            MessageIntent.EMERGENCY: "Emergency situations requiring immediate attention",
            MessageIntent.COMPLIMENT: "Positive feedback, compliments, thanks",
            MessageIntent.CANCELLATION: "Requests to cancel or modify bookings",
            MessageIntent.ROOM_ISSUE: "Problems with the room (AC, TV, cleanliness, etc.)",
            MessageIntent.BILLING_QUESTION: "Questions about charges, payments, bills",
            MessageIntent.AMENITY_QUESTION: "Questions about hotel facilities and amenities"
        }
        
        prompt = f"""
Classify the intent of this hotel guest message. Respond with JSON format only.

Message: "{message}"

Available intents:
{chr(10).join([f"- {intent.value}: {desc}" for intent, desc in intent_descriptions.items()])}

Respond with JSON containing:
- "intent": one of the intent values above
- "confidence": float between 0.0 and 1.0
- "entities": object with extracted entities (dates, room numbers, amounts, etc.)
- "sentiment_score": float between -1.0 (negative) and 1.0 (positive)
- "urgency_level": integer 1-5 (1=low, 5=emergency)
- "reasoning": brief explanation

Example response:
{{"intent": "booking_inquiry", "confidence": 0.9, "entities": {{"dates": ["2024-01-15"]}}, "sentiment_score": 0.2, "urgency_level": 2, "reasoning": "Guest asking about room availability"}}
"""
        
        return prompt
    
    def _parse_ai_response(self, response: str, original_message: str) -> Optional[IntentClassificationResult]:
        """Parse AI response into classification result"""
        try:
            import json
            
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                return None
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Validate intent
            intent_str = data.get('intent', 'unknown')
            try:
                intent = MessageIntent(intent_str)
            except ValueError:
                intent = MessageIntent.UNKNOWN
            
            return IntentClassificationResult(
                intent=intent,
                confidence=float(data.get('confidence', 0.5)),
                entities=data.get('entities', {}),
                sentiment_score=data.get('sentiment_score'),
                urgency_level=int(data.get('urgency_level', 1)),
                reasoning=data.get('reasoning', 'AI classification')
            )
            
        except Exception as e:
            logger.warning("Failed to parse AI response", error=str(e), response=response[:200])
            return None
    
    def _is_emergency(self, message: str) -> bool:
        """Check if message indicates emergency"""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.emergency_keywords)
    
    def _extract_emergency_keywords(self, message: str) -> List[str]:
        """Extract emergency keywords from message"""
        message_lower = message.lower()
        return [kw for kw in self.emergency_keywords if kw in message_lower]
    
    def _calculate_urgency(self, intent: MessageIntent, keywords: List[str]) -> int:
        """Calculate urgency level based on intent and keywords"""
        base_urgency = {
            MessageIntent.EMERGENCY: 5,
            MessageIntent.COMPLAINT: 4,
            MessageIntent.ROOM_ISSUE: 3,
            MessageIntent.REQUEST_SERVICE: 2,
            MessageIntent.BOOKING_INQUIRY: 2,
            MessageIntent.CANCELLATION: 3,
            MessageIntent.BILLING_QUESTION: 2,
            MessageIntent.GENERAL_QUESTION: 1,
            MessageIntent.AMENITY_QUESTION: 1,
            MessageIntent.COMPLIMENT: 1,
            MessageIntent.GREETING: 1,
            MessageIntent.GOODBYE: 1,
            MessageIntent.UNKNOWN: 1
        }.get(intent, 1)
        
        # Increase urgency for certain keywords
        urgent_keywords = ['urgent', 'immediately', 'asap', 'emergency', 'broken', 'not working']
        if any(kw in ' '.join(keywords) for kw in urgent_keywords):
            base_urgency = min(base_urgency + 1, 5)
        
        return base_urgency


# Export classifier
__all__ = ['IntentClassifier', 'MessageIntent', 'IntentClassificationResult']
