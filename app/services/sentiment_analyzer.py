"""
Sentiment analysis service for WhatsApp Hotel Bot
"""

import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

import structlog
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.deepseek_client import get_deepseek_client
from app.services.deepseek_cache import get_cache_service
from app.services.token_optimizer import get_token_optimizer
from app.core.deepseek_config import get_global_sentiment_config
from app.schemas.deepseek import (
    SentimentAnalysisRequest,
    SentimentAnalysisResult,
    SentimentType,
    ChatMessage,
    MessageRole
)
from app.models.sentiment import SentimentAnalysis
from app.models.message import Message
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.core.deepseek_logging import log_deepseek_operation

logger = structlog.get_logger(__name__)


class SentimentAnalyzer:
    """Service for analyzing message sentiment using DeepSeek AI"""
    
    def __init__(self, db: Session):
        self.db = db
        self.config = get_global_sentiment_config()
        self.cache_service = get_cache_service()
        self.token_optimizer = get_token_optimizer()
        
    async def analyze_message_sentiment(
        self,
        message: Message,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> SentimentAnalysisResult:
        """
        Analyze sentiment of a message
        
        Args:
            message: Message object to analyze
            context: Additional context for analysis
            correlation_id: Correlation ID for tracking
            
        Returns:
            SentimentAnalysisResult with analysis results
        """
        start_time = time.time()
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            # Get hotel and guest for context
            hotel = self.db.query(Hotel).filter(Hotel.id == message.hotel_id).first()
            guest = self.db.query(Guest).filter(Guest.id == message.guest_id).first()
            
            if not hotel or not guest:
                raise ValueError("Hotel or guest not found for message")
            
            # Prepare analysis request
            request = SentimentAnalysisRequest(
                text=message.content,
                context=context or {},
                language=self.config.default_language,
                hotel_id=str(message.hotel_id),
                guest_id=str(message.guest_id)
            )
            
            # Perform sentiment analysis
            result = await self._analyze_sentiment_with_ai(request, correlation_id)
            
            # Store results in database
            sentiment_record = await self._store_sentiment_analysis(
                message=message,
                result=result,
                processing_time_ms=int((time.time() - start_time) * 1000),
                correlation_id=correlation_id
            )
            
            logger.info("Sentiment analysis completed",
                       message_id=str(message.id),
                       sentiment=result.sentiment.value,
                       score=result.score,
                       confidence=result.confidence,
                       requires_attention=result.requires_attention,
                       correlation_id=correlation_id)
            
            return result
            
        except Exception as e:
            logger.error("Sentiment analysis failed",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def _analyze_sentiment_with_ai(
        self,
        request: SentimentAnalysisRequest,
        correlation_id: str
    ) -> SentimentAnalysisResult:
        """Perform AI-powered sentiment analysis"""

        # Check cache first
        cached_result = await self.cache_service.get_sentiment_cache(
            text=request.text,
            language=request.language,
            hotel_id=request.hotel_id
        )

        if cached_result:
            logger.info("Sentiment analysis cache hit",
                       text_length=len(request.text),
                       sentiment=cached_result.sentiment.value,
                       correlation_id=correlation_id)
            return cached_result

        client = await get_deepseek_client()
        
        # Create prompt for sentiment analysis
        system_prompt = self._create_sentiment_system_prompt()
        user_prompt = self._create_sentiment_user_prompt(request)

        # Optimize prompts for token usage
        optimized_system = self.token_optimizer.optimize_text(system_prompt)
        optimized_user = self.token_optimizer.optimize_text(user_prompt)

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=optimized_system),
            ChatMessage(role=MessageRole.USER, content=optimized_user)
        ]

        # Optimize message list
        messages = self.token_optimizer.optimize_chat_messages(messages)
        
        try:
            # Make API call
            response = await client.chat_completion(
                messages=messages,
                max_tokens=500,
                temperature=0.3,  # Lower temperature for more consistent results
                correlation_id=correlation_id
            )
            
            # Parse response
            if not response.choices or not response.choices[0].message.content:
                raise ValueError("No response content from DeepSeek API")
            
            response_content = response.choices[0].message.content
            
            # Parse JSON response
            try:
                result_data = json.loads(response_content)
            except json.JSONDecodeError:
                # Fallback: try to extract JSON from response
                result_data = self._extract_json_from_response(response_content)
            
            # Create result object
            result = SentimentAnalysisResult(
                sentiment=SentimentType(result_data.get('sentiment', 'neutral')),
                score=float(result_data.get('score', 0.0)),
                confidence=float(result_data.get('confidence', 0.0)),
                requires_attention=bool(result_data.get('requires_attention', False)),
                reason=result_data.get('reason'),
                keywords=result_data.get('keywords', [])
            )
            
            # Validate result
            self._validate_sentiment_result(result)

            # Cache the result
            await self.cache_service.set_sentiment_cache(
                text=request.text,
                result=result,
                language=request.language,
                hotel_id=request.hotel_id
            )

            return result
            
        except Exception as e:
            logger.error("AI sentiment analysis failed",
                        text=request.text[:100],
                        error=str(e),
                        correlation_id=correlation_id)
            
            # Return fallback result
            return self._create_fallback_sentiment_result(request.text)
    
    def _create_sentiment_system_prompt(self) -> str:
        """Create system prompt for sentiment analysis"""
        return """You are an expert sentiment analyzer for hotel guest communications. 
        
Your task is to analyze guest messages and determine:
1. Sentiment: positive, negative, neutral, or requires_attention
2. Score: from -1.0 (very negative) to 1.0 (very positive)
3. Confidence: from 0.0 to 1.0 (how confident you are)
4. Whether it requires staff attention
5. Brief reason for your assessment
6. Key sentiment indicators (keywords)

Guidelines:
- "requires_attention" is for extremely negative sentiment (score < -0.7) or urgent issues
- Consider cultural context and hospitality industry standards
- Be conservative with "requires_attention" - only for serious issues
- Focus on guest satisfaction and service quality

Respond ONLY with valid JSON in this format:
{
  "sentiment": "positive|negative|neutral|requires_attention",
  "score": -1.0 to 1.0,
  "confidence": 0.0 to 1.0,
  "requires_attention": true|false,
  "reason": "brief explanation",
  "keywords": ["keyword1", "keyword2"]
}"""
    
    def _create_sentiment_user_prompt(self, request: SentimentAnalysisRequest) -> str:
        """Create user prompt for sentiment analysis"""
        prompt = f"Analyze the sentiment of this hotel guest message:\n\nMessage: \"{request.text}\""
        
        if request.context:
            prompt += f"\n\nContext: {json.dumps(request.context, indent=2)}"
        
        if request.language and request.language != 'en':
            prompt += f"\n\nLanguage: {request.language}"
        
        prompt += "\n\nProvide your analysis as JSON:"
        
        return prompt
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from response text"""
        # Try to find JSON in the response
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_str = response[start_idx:end_idx]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # Fallback: create basic result
        return {
            'sentiment': 'neutral',
            'score': 0.0,
            'confidence': 0.5,
            'requires_attention': False,
            'reason': 'Failed to parse AI response',
            'keywords': []
        }
    
    def _validate_sentiment_result(self, result: SentimentAnalysisResult):
        """Validate sentiment analysis result"""
        # Check score consistency with sentiment
        if result.sentiment == SentimentType.POSITIVE and result.score < 0:
            result.score = abs(result.score)
        elif result.sentiment in [SentimentType.NEGATIVE, SentimentType.REQUIRES_ATTENTION] and result.score > 0:
            result.score = -abs(result.score)
        
        # Ensure requires_attention is set for very negative scores
        if result.score <= self.config.attention_threshold:
            result.requires_attention = True
            if result.sentiment != SentimentType.REQUIRES_ATTENTION:
                result.sentiment = SentimentType.REQUIRES_ATTENTION
        
        # Clamp values to valid ranges
        result.score = max(-1.0, min(1.0, result.score))
        result.confidence = max(0.0, min(1.0, result.confidence))
    
    def _create_fallback_sentiment_result(self, text: str) -> SentimentAnalysisResult:
        """Create fallback sentiment result when AI analysis fails"""
        # Simple keyword-based fallback
        text_lower = text.lower()
        
        negative_keywords = ['bad', 'terrible', 'awful', 'hate', 'worst', 'horrible', 'disgusting']
        positive_keywords = ['good', 'great', 'excellent', 'love', 'amazing', 'wonderful', 'perfect']
        
        negative_count = sum(1 for word in negative_keywords if word in text_lower)
        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        
        if negative_count > positive_count:
            sentiment = SentimentType.NEGATIVE
            score = -0.5
        elif positive_count > negative_count:
            sentiment = SentimentType.POSITIVE
            score = 0.5
        else:
            sentiment = SentimentType.NEUTRAL
            score = 0.0
        
        return SentimentAnalysisResult(
            sentiment=sentiment,
            score=score,
            confidence=0.3,  # Low confidence for fallback
            requires_attention=negative_count > 2,
            reason="Fallback analysis due to AI service unavailability",
            keywords=[]
        )
    
    async def _store_sentiment_analysis(
        self,
        message: Message,
        result: SentimentAnalysisResult,
        processing_time_ms: int,
        correlation_id: str
    ) -> SentimentAnalysis:
        """Store sentiment analysis results in database"""
        
        try:
            sentiment_record = SentimentAnalysis(
                hotel_id=message.hotel_id,
                message_id=message.id,
                guest_id=message.guest_id,
                conversation_id=message.conversation_id,
                sentiment_type=result.sentiment.value,
                sentiment_score=result.score,
                confidence_score=result.confidence,
                requires_attention=result.requires_attention,
                analyzed_text=message.content,
                language_detected=self.config.default_language,
                keywords=result.keywords,
                reasoning=result.reason,
                model_used="deepseek-chat",
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id
            )
            
            self.db.add(sentiment_record)
            self.db.commit()
            self.db.refresh(sentiment_record)
            
            logger.info("Sentiment analysis stored",
                       sentiment_id=str(sentiment_record.id),
                       message_id=str(message.id),
                       correlation_id=correlation_id)
            
            return sentiment_record
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error("Failed to store sentiment analysis",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def get_message_sentiment(self, message_id: str) -> Optional[SentimentAnalysis]:
        """Get existing sentiment analysis for a message"""
        try:
            return self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.message_id == message_id
            ).first()
        except SQLAlchemyError as e:
            logger.error("Failed to get message sentiment",
                        message_id=message_id,
                        error=str(e))
            return None
    
    async def get_guest_sentiment_history(
        self,
        guest_id: str,
        limit: int = 10
    ) -> List[SentimentAnalysis]:
        """Get sentiment history for a guest"""
        try:
            return self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.guest_id == guest_id
            ).order_by(SentimentAnalysis.created_at.desc()).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error("Failed to get guest sentiment history",
                        guest_id=guest_id,
                        error=str(e))
            return []


# Export main components
__all__ = [
    'SentimentAnalyzer'
]
