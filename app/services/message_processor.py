"""
Message processor service for incoming WhatsApp messages
"""

from typing import Dict, Any, Optional, List
import structlog
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message, Conversation, MessageType, SentimentType
from app.models.notification import StaffNotification
from app.utils.message_parser import parse_whatsapp_message, assess_message_urgency
from app.services.green_api_service import extract_message_content

logger = structlog.get_logger(__name__)


class MessageProcessor:
    """Service for processing incoming WhatsApp messages"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def process_incoming_message(
        self,
        hotel: Hotel,
        message: Message
    ) -> Dict[str, Any]:
        """
        Process incoming message with parsing, analysis, and triggers
        
        Args:
            hotel: Hotel instance
            message: Message instance
            
        Returns:
            Dict with processing results
        """
        try:
            # Parse message content
            parsed_data = self._parse_message_content(message)
            
            # Update message with parsed data
            message.set_metadata('parsed_data', parsed_data)
            
            # Analyze sentiment (basic implementation)
            sentiment_result = self._analyze_sentiment(message.content, parsed_data)
            if sentiment_result:
                message.set_sentiment(
                    sentiment_result['score'],
                    sentiment_result['type']
                )
            
            # Check for urgent messages
            urgency_level = parsed_data.get('urgency_level', 'low')
            if urgency_level in ['high', 'medium']:
                await self._handle_urgent_message(hotel, message, urgency_level)
            
            # Check for negative sentiment
            if message.has_negative_sentiment:
                await self._handle_negative_sentiment(hotel, message)
            
            # Process intent-based actions
            intent = parsed_data.get('intent', 'general')
            await self._process_intent_actions(hotel, message, intent)
            
            # Update conversation
            conversation = message.conversation
            conversation.update_last_message_time()
            
            # Commit changes
            self.db.commit()
            
            result = {
                'status': 'processed',
                'message_id': str(message.id),
                'parsed_data': parsed_data,
                'sentiment': {
                    'score': float(message.sentiment_score) if message.sentiment_score else None,
                    'type': message.sentiment_type.value if message.sentiment_type else None
                },
                'urgency_level': urgency_level,
                'intent': intent,
                'actions_triggered': []
            }
            
            logger.info("Incoming message processed",
                       hotel_id=hotel.id,
                       message_id=message.id,
                       intent=intent,
                       urgency=urgency_level,
                       sentiment_type=message.sentiment_type.value if message.sentiment_type else None)
            
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error("Error processing incoming message",
                        hotel_id=hotel.id,
                        message_id=message.id,
                        error=str(e))
            raise
    
    def _parse_message_content(self, message: Message) -> Dict[str, Any]:
        """Parse message content and extract structured information"""
        try:
            # Get raw message data
            raw_data = message.get_metadata('raw_message_data', {})
            
            # Parse using message parser
            parsed_data = parse_whatsapp_message(message.content, raw_data)
            
            return parsed_data
            
        except Exception as e:
            logger.error("Error parsing message content",
                        message_id=message.id,
                        error=str(e))
            return {
                'error': str(e),
                'original_content': message.content
            }
    
    def _analyze_sentiment(self, content: str, parsed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze message sentiment (basic implementation)
        
        In production, this would integrate with DeepSeek API or other AI service
        """
        try:
            sentiment_indicators = parsed_data.get('sentiment_indicators', {})
            positive_words = sentiment_indicators.get('positive', [])
            negative_words = sentiment_indicators.get('negative', [])
            
            # Simple scoring based on word counts
            positive_score = len(positive_words) * 0.3
            negative_score = len(negative_words) * -0.4
            
            # Adjust for urgency
            urgency = parsed_data.get('urgency_level', 'low')
            if urgency == 'high':
                negative_score -= 0.2
            
            # Adjust for intent
            intent = parsed_data.get('intent', 'general')
            if intent == 'complaint':
                negative_score -= 0.3
            elif intent == 'compliment':
                positive_score += 0.3
            
            # Calculate final score
            final_score = positive_score + negative_score
            
            # Clamp to [-1, 1] range
            final_score = max(-1.0, min(1.0, final_score))
            
            # Determine sentiment type
            if final_score >= 0.3:
                sentiment_type = SentimentType.POSITIVE
            elif final_score <= -0.3:
                sentiment_type = SentimentType.NEGATIVE
            elif final_score <= -0.7:
                sentiment_type = SentimentType.REQUIRES_ATTENTION
            else:
                sentiment_type = SentimentType.NEUTRAL
            
            return {
                'score': final_score,
                'type': sentiment_type,
                'positive_words': positive_words,
                'negative_words': negative_words
            }
            
        except Exception as e:
            logger.error("Error analyzing sentiment", error=str(e))
            return None
    
    async def _handle_urgent_message(
        self,
        hotel: Hotel,
        message: Message,
        urgency_level: str
    ) -> None:
        """Handle urgent messages with immediate notifications"""
        try:
            # Create staff notification
            notification = StaffNotification(
                hotel_id=hotel.id,
                guest_id=message.conversation.guest_id,
                notification_type='urgent_message',
                title=f'Urgent Message from Guest',
                message=f'Urgent {urgency_level} priority message: {message.content[:100]}...',
                metadata={
                    'message_id': str(message.id),
                    'conversation_id': str(message.conversation_id),
                    'urgency_level': urgency_level,
                    'guest_phone': message.conversation.guest.phone_number
                }
            )
            
            self.db.add(notification)
            
            logger.info("Urgent message notification created",
                       hotel_id=hotel.id,
                       message_id=message.id,
                       urgency_level=urgency_level)
            
        except Exception as e:
            logger.error("Error handling urgent message",
                        hotel_id=hotel.id,
                        message_id=message.id,
                        error=str(e))
    
    async def _handle_negative_sentiment(
        self,
        hotel: Hotel,
        message: Message
    ) -> None:
        """Handle messages with negative sentiment"""
        try:
            # Create staff notification for negative sentiment
            notification = StaffNotification(
                hotel_id=hotel.id,
                guest_id=message.conversation.guest_id,
                notification_type='negative_sentiment',
                title='Negative Sentiment Detected',
                message=f'Guest message with negative sentiment: {message.content[:100]}...',
                metadata={
                    'message_id': str(message.id),
                    'conversation_id': str(message.conversation_id),
                    'sentiment_score': float(message.sentiment_score) if message.sentiment_score else None,
                    'sentiment_type': message.sentiment_type.value if message.sentiment_type else None,
                    'guest_phone': message.conversation.guest.phone_number
                }
            )
            
            self.db.add(notification)
            
            # Mark conversation for attention if sentiment is very negative
            if message.sentiment_type == SentimentType.REQUIRES_ATTENTION:
                conversation = message.conversation
                conversation.status = 'escalated'
            
            logger.info("Negative sentiment notification created",
                       hotel_id=hotel.id,
                       message_id=message.id,
                       sentiment_type=message.sentiment_type.value)
            
        except Exception as e:
            logger.error("Error handling negative sentiment",
                        hotel_id=hotel.id,
                        message_id=message.id,
                        error=str(e))
    
    async def _process_intent_actions(
        self,
        hotel: Hotel,
        message: Message,
        intent: str
    ) -> None:
        """Process intent-based actions and triggers"""
        try:
            # This is where we would integrate with the trigger system
            # For now, just log the intent
            
            logger.info("Processing intent-based actions",
                       hotel_id=hotel.id,
                       message_id=message.id,
                       intent=intent)
            
            # Example intent handling
            if intent == 'booking':
                # Extract booking information
                parsed_data = message.get_metadata('parsed_data', {})
                booking_info = parsed_data.get('extracted_data', {})
                
                if booking_info:
                    message.set_metadata('booking_info', booking_info)
                    logger.info("Booking information extracted",
                               hotel_id=hotel.id,
                               message_id=message.id,
                               booking_info=booking_info)
            
            elif intent == 'complaint':
                # Ensure complaint is escalated
                conversation = message.conversation
                if conversation.status == 'active':
                    conversation.status = 'escalated'
                
                logger.info("Complaint message escalated",
                           hotel_id=hotel.id,
                           message_id=message.id)
            
            elif intent == 'emergency':
                # Create high-priority notification
                notification = StaffNotification(
                    hotel_id=hotel.id,
                    guest_id=message.conversation.guest_id,
                    notification_type='emergency',
                    title='EMERGENCY: Immediate Attention Required',
                    message=f'Emergency message from guest: {message.content}',
                    metadata={
                        'message_id': str(message.id),
                        'conversation_id': str(message.conversation_id),
                        'guest_phone': message.conversation.guest.phone_number,
                        'priority': 'emergency'
                    }
                )
                
                self.db.add(notification)
                
                # Escalate conversation immediately
                conversation = message.conversation
                conversation.status = 'escalated'
                
                logger.warning("Emergency message detected",
                              hotel_id=hotel.id,
                              message_id=message.id)
            
        except Exception as e:
            logger.error("Error processing intent actions",
                        hotel_id=hotel.id,
                        message_id=message.id,
                        intent=intent,
                        error=str(e))
    
    def get_conversation_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get summary of conversation for staff"""
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                raise ValueError(f"Conversation not found: {conversation_id}")
            
            # Get recent messages
            recent_messages = self.db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at.desc()).limit(10).all()
            
            # Analyze conversation
            total_messages = len(conversation.messages)
            incoming_count = sum(1 for msg in conversation.messages if msg.is_incoming)
            outgoing_count = total_messages - incoming_count
            
            # Get sentiment distribution
            sentiment_counts = {}
            for msg in conversation.messages:
                if msg.sentiment_type:
                    sentiment_type = msg.sentiment_type.value
                    sentiment_counts[sentiment_type] = sentiment_counts.get(sentiment_type, 0) + 1
            
            # Get common intents
            intent_counts = {}
            for msg in conversation.messages:
                parsed_data = msg.get_metadata('parsed_data', {})
                intent = parsed_data.get('intent', 'general')
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
            
            summary = {
                'conversation_id': str(conversation.id),
                'guest_id': str(conversation.guest_id),
                'guest_name': conversation.guest.name,
                'guest_phone': conversation.guest.phone_number,
                'status': conversation.status,
                'created_at': conversation.created_at.isoformat(),
                'last_message_at': conversation.last_message_at.isoformat(),
                'message_counts': {
                    'total': total_messages,
                    'incoming': incoming_count,
                    'outgoing': outgoing_count
                },
                'sentiment_distribution': sentiment_counts,
                'intent_distribution': intent_counts,
                'recent_messages': [
                    {
                        'id': str(msg.id),
                        'type': msg.message_type.value,
                        'content': msg.content[:100] + '...' if len(msg.content) > 100 else msg.content,
                        'created_at': msg.created_at.isoformat(),
                        'sentiment_type': msg.sentiment_type.value if msg.sentiment_type else None
                    }
                    for msg in recent_messages
                ]
            }
            
            return summary
            
        except Exception as e:
            logger.error("Error getting conversation summary",
                        conversation_id=conversation_id,
                        error=str(e))
            raise


# Export main class
__all__ = ['MessageProcessor']
