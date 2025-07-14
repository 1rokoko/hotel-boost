"""
AI response generation service for WhatsApp Hotel Bot
"""

import time
from typing import Optional, Dict, Any, List
import uuid
import json

import structlog
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.deepseek_client import get_deepseek_client
from app.services.deepseek_cache import get_cache_service
from app.services.token_optimizer import get_token_optimizer
from app.core.deepseek_config import get_global_response_config
from app.schemas.deepseek import (
    ResponseGenerationRequest,
    ResponseGenerationResult,
    ChatMessage,
    MessageRole
)
from app.utils.prompt_templates import (
    get_prompt_template_manager,
    ResponseType
)
from app.models.message import Message, Conversation
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.models.sentiment import SentimentAnalysis
from app.core.deepseek_logging import log_deepseek_operation

logger = structlog.get_logger(__name__)


class ResponseGenerator:
    """Service for generating AI-powered responses to guest messages"""
    
    def __init__(self, db: Session):
        self.db = db
        self.config = get_global_response_config()
        self.template_manager = get_prompt_template_manager()
        self.cache_service = get_cache_service()
        self.token_optimizer = get_token_optimizer()
    
    async def generate_response(
        self,
        message: Message,
        response_type: Optional[ResponseType] = None,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> ResponseGenerationResult:
        """
        Generate AI response to a guest message
        
        Args:
            message: Guest message to respond to
            response_type: Type of response to generate
            context: Additional context for generation
            correlation_id: Correlation ID for tracking
            
        Returns:
            ResponseGenerationResult with generated response
        """
        start_time = time.time()
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            # Get related entities
            hotel = self.db.query(Hotel).filter(Hotel.id == message.hotel_id).first()
            guest = self.db.query(Guest).filter(Guest.id == message.guest_id).first()
            conversation = None
            if message.conversation_id:
                conversation = self.db.query(Conversation).filter(
                    Conversation.id == message.conversation_id
                ).first()
            
            if not hotel or not guest:
                raise ValueError("Hotel or guest not found for message")
            
            # Get conversation history
            conversation_history = await self._get_conversation_history(
                message.conversation_id,
                limit=self.config.max_context_messages
            )
            
            # Get guest sentiment context
            sentiment_context = await self._get_sentiment_context(message.id)
            
            # Detect response type if not provided
            if not response_type:
                response_type = self.template_manager.detect_response_type(
                    message.content,
                    context={**(context or {}), **sentiment_context}
                )
            
            # Prepare generation request
            request = ResponseGenerationRequest(
                message=message.content,
                context=context or {},
                hotel_id=str(message.hotel_id),
                guest_id=str(message.guest_id),
                conversation_history=conversation_history,
                guest_preferences=guest.preferences if isinstance(guest.preferences, dict) else {},
                hotel_settings=hotel.settings if isinstance(hotel.settings, dict) else {},
                language=self.config.default_language if hasattr(self.config, 'default_language') else 'en',
                response_type=response_type.value
            )

            # Create context hash for caching
            context_hash = self.token_optimizer.create_context_hash({
                'hotel_id': str(message.hotel_id),
                'guest_preferences': guest.preferences if isinstance(guest.preferences, dict) else {},
                'conversation_history': conversation_history,
                'sentiment_context': sentiment_context,
                'response_type': response_type.value
            })

            # Check cache first
            cached_result = await self.cache_service.get_response_cache(
                message=message.content,
                context_hash=context_hash,
                response_type=response_type.value
            )

            if cached_result:
                logger.info("Response generation cache hit",
                           message_id=str(message.id),
                           response_type=response_type.value,
                           correlation_id=correlation_id)
                return cached_result
            
            # Generate response
            result = await self._generate_response_with_ai(
                request=request,
                hotel=hotel,
                guest=guest,
                response_type=response_type,
                context_hash=context_hash,
                correlation_id=correlation_id
            )
            
            # Validate and post-process response
            result = self._post_process_response(result, hotel, guest)
            
            logger.info("Response generation completed",
                       message_id=str(message.id),
                       response_type=response_type.value,
                       response_length=len(result.response),
                       confidence=result.confidence,
                       correlation_id=correlation_id)
            
            return result
            
        except Exception as e:
            logger.error("Response generation failed",
                        message_id=str(message.id),
                        error=str(e),
                        correlation_id=correlation_id)
            raise
    
    async def _generate_response_with_ai(
        self,
        request: ResponseGenerationRequest,
        hotel: Hotel,
        guest: Guest,
        response_type: ResponseType,
        context_hash: str,
        correlation_id: str
    ) -> ResponseGenerationResult:
        """Generate response using DeepSeek AI"""
        
        client = await get_deepseek_client()
        
        # Create prompts
        system_prompt = self.template_manager.get_system_prompt(
            response_type=response_type,
            hotel=hotel,
            custom_instructions=request.hotel_settings.get('ai_instructions') if request.hotel_settings else None
        )
        
        user_prompt = self.template_manager.create_user_prompt(
            guest_message=request.message,
            guest=guest,
            hotel=hotel,
            conversation_history=request.conversation_history,
            context=request.context
        )

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
                max_tokens=self.config.max_response_tokens,
                temperature=self.config.response_temperature,
                correlation_id=correlation_id
            )
            
            # Extract response content
            if not response.choices or not response.choices[0].message.content:
                raise ValueError("No response content from DeepSeek API")
            
            response_content = response.choices[0].message.content.strip()
            
            # Create result object
            result = ResponseGenerationResult(
                response=response_content,
                confidence=0.8,  # Default confidence for AI responses
                response_type=response_type.value,
                reasoning=f"Generated {response_type.value} response using DeepSeek AI",
                suggested_actions=self._extract_suggested_actions(response_content, response_type)
            )

            # Cache the result
            await self.cache_service.set_response_cache(
                message=request.message,
                context_hash=context_hash,
                result=result,
                response_type=response_type.value
            )

            return result
            
        except Exception as e:
            logger.error("AI response generation failed",
                        guest_message=request.message[:100],
                        error=str(e),
                        correlation_id=correlation_id)
            
            # Return fallback response
            return self._create_fallback_response(request.message, response_type, hotel, guest)
    
    def _extract_suggested_actions(self, response: str, response_type: ResponseType) -> List[str]:
        """Extract suggested follow-up actions from response"""
        
        actions = []
        
        if response_type == ResponseType.COMPLAINT_RESOLUTION:
            actions.extend([
                "Follow up with guest within 24 hours",
                "Document issue in guest profile",
                "Consider compensation if appropriate"
            ])
        elif response_type == ResponseType.BOOKING_ASSISTANCE:
            actions.extend([
                "Confirm booking details",
                "Send confirmation email",
                "Update guest preferences"
            ])
        elif response_type == ResponseType.ESCALATION:
            actions.extend([
                "Notify appropriate department",
                "Set follow-up reminder",
                "Monitor resolution progress"
            ])
        
        # Check for specific action indicators in response
        response_lower = response.lower()
        if "follow up" in response_lower:
            actions.append("Schedule follow-up contact")
        if "manager" in response_lower or "supervisor" in response_lower:
            actions.append("Escalate to management")
        if "compensation" in response_lower or "refund" in response_lower:
            actions.append("Review compensation options")
        
        return list(set(actions))  # Remove duplicates
    
    def _create_fallback_response(
        self,
        guest_message: str,
        response_type: ResponseType,
        hotel: Hotel,
        guest: Guest
    ) -> ResponseGenerationResult:
        """Create fallback response when AI generation fails"""
        
        guest_name = guest.name if guest.name else "Guest"
        hotel_name = hotel.name
        
        fallback_responses = {
            ResponseType.HELPFUL: f"Thank you for contacting {hotel_name}, {guest_name}. I've received your message and will make sure you get the assistance you need. A member of our team will respond shortly.",
            
            ResponseType.APOLOGETIC: f"I sincerely apologize for any inconvenience, {guest_name}. Your experience is important to us at {hotel_name}, and we want to make this right. Please allow me to connect you with a team member who can assist you immediately.",
            
            ResponseType.COMPLAINT_RESOLUTION: f"I understand your concern, {guest_name}, and I apologize for the issue you've experienced. This is not the standard we maintain at {hotel_name}. I'm escalating this to our management team for immediate attention.",
            
            ResponseType.BOOKING_ASSISTANCE: f"Thank you for your booking inquiry, {guest_name}. I'd be happy to help you with your reservation at {hotel_name}. Let me connect you with our reservations team for personalized assistance.",
            
            ResponseType.ESCALATION: f"I understand this requires special attention, {guest_name}. I'm connecting you with our specialized team at {hotel_name} who can provide the detailed assistance you need."
        }
        
        response_text = fallback_responses.get(
            response_type,
            f"Thank you for contacting {hotel_name}, {guest_name}. I've received your message and will ensure you receive proper assistance shortly."
        )
        
        return ResponseGenerationResult(
            response=response_text,
            confidence=0.6,  # Lower confidence for fallback
            response_type=response_type.value,
            reasoning="Fallback response due to AI service unavailability",
            suggested_actions=["Connect guest with human agent"]
        )
    
    def _post_process_response(
        self,
        result: ResponseGenerationResult,
        hotel: Hotel,
        guest: Guest
    ) -> ResponseGenerationResult:
        """Post-process and validate generated response"""
        
        # Validate response length
        if len(result.response) < self.config.min_response_length:
            result.response += f" Is there anything else I can help you with?"
        
        if len(result.response) > self.config.max_response_length:
            # Truncate and add continuation
            result.response = result.response[:self.config.max_response_length-50] + "... Please let me know if you need more information."
        
        # Ensure guest name is used appropriately
        guest_name = guest.name if guest.name else "Guest"
        if guest_name not in result.response and len(result.response) > 50:
            # Add guest name if not present in longer responses
            if result.response.endswith('.') or result.response.endswith('!') or result.response.endswith('?'):
                result.response = result.response[:-1] + f", {guest_name}."
        
        # Ensure hotel branding if enabled
        if self.config.use_hotel_branding and hotel.name not in result.response:
            if "hotel" in result.response.lower() and hotel.name not in result.response:
                result.response = result.response.replace("hotel", hotel.name, 1)
        
        return result
    
    async def _get_conversation_history(
        self,
        conversation_id: Optional[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        
        if not conversation_id:
            return []
        
        try:
            messages = self.db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at.desc()).limit(limit).all()
            
            history = []
            for msg in reversed(messages):  # Reverse to get chronological order
                history.append({
                    'type': msg.message_type.value,
                    'content': msg.content,
                    'timestamp': msg.created_at.isoformat()
                })
            
            return history
            
        except SQLAlchemyError as e:
            logger.error("Failed to get conversation history",
                        conversation_id=conversation_id,
                        error=str(e))
            return []
    
    async def _get_sentiment_context(self, message_id: str) -> Dict[str, Any]:
        """Get sentiment context for the message"""
        
        try:
            sentiment = self.db.query(SentimentAnalysis).filter(
                SentimentAnalysis.message_id == message_id
            ).first()
            
            if sentiment:
                return {
                    'sentiment_type': sentiment.sentiment_type,
                    'sentiment_score': sentiment.sentiment_score,
                    'confidence_score': sentiment.confidence_score,
                    'requires_attention': sentiment.requires_attention
                }
            
            return {}
            
        except SQLAlchemyError as e:
            logger.error("Failed to get sentiment context",
                        message_id=message_id,
                        error=str(e))
            return {}


# Export main components
__all__ = [
    'ResponseGenerator'
]
