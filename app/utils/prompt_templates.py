"""
Prompt templates for DeepSeek AI response generation
"""

from typing import Dict, Any, List, Optional
from enum import Enum
import json

from app.models.hotel import Hotel
from app.models.guest import Guest
from app.models.message import Message


class ResponseType(str, Enum):
    """Types of responses that can be generated"""
    HELPFUL = "helpful"
    APOLOGETIC = "apologetic"
    INFORMATIONAL = "informational"
    ESCALATION = "escalation"
    BOOKING_ASSISTANCE = "booking_assistance"
    COMPLAINT_RESOLUTION = "complaint_resolution"
    GENERAL_INQUIRY = "general_inquiry"
    AMENITY_INFO = "amenity_info"
    LOCATION_INFO = "location_info"


class PromptTemplateManager:
    """Manager for AI prompt templates"""
    
    def __init__(self):
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict[str, str]]:
        """Load prompt templates"""
        return {
            "system_prompts": {
                "base": """You are a professional hotel customer service AI assistant. Your role is to help guests with their inquiries, provide information, and ensure excellent customer service.

Guidelines:
- Always be polite, professional, and helpful
- Provide accurate information about hotel services and amenities
- If you don't know something, admit it and offer to connect them with staff
- Keep responses concise but informative
- Use the guest's name when available
- Maintain the hotel's brand voice and standards
- For complaints, be empathetic and solution-focused
- For urgent issues, escalate to staff immediately

Response format:
- Write in a conversational, friendly tone
- Use proper grammar and punctuation
- Keep responses between 50-300 words unless more detail is needed
- End with a helpful offer or question when appropriate""",
                
                "complaint_handling": """You are a hotel customer service specialist focused on complaint resolution. Your primary goal is to address guest concerns with empathy and find solutions.

Key principles:
- Acknowledge the guest's feelings and frustration
- Apologize sincerely for any inconvenience
- Take ownership of the issue
- Offer specific solutions or alternatives
- Follow up to ensure satisfaction
- Escalate to management when necessary

Always:
- Listen actively to understand the full issue
- Respond with empathy and understanding
- Provide clear next steps
- Offer compensation when appropriate
- Ensure the guest feels heard and valued""",
                
                "booking_assistance": """You are a hotel booking specialist AI. Help guests with reservations, room information, and booking-related inquiries.

Your expertise includes:
- Room types and availability
- Pricing and packages
- Booking modifications and cancellations
- Special requests and accommodations
- Hotel policies and procedures
- Payment and confirmation processes

Always:
- Provide accurate booking information
- Explain policies clearly
- Offer alternatives when requested dates aren't available
- Assist with special needs or requests
- Confirm important details
- Direct to booking systems or staff when needed"""
            },
            
            "response_templates": {
                "greeting": """Hello {guest_name}! Welcome to {hotel_name}. How can I assist you today?""",
                
                "acknowledgment": """Thank you for contacting {hotel_name}, {guest_name}. I understand you're asking about {topic}.""",
                
                "apology": """I sincerely apologize for the inconvenience you've experienced, {guest_name}. This is not the level of service we strive to provide at {hotel_name}.""",
                
                "escalation": """I understand this is important to you, {guest_name}. Let me connect you with our {department} team who can provide more specialized assistance.""",
                
                "information_request": """I'd be happy to help you with information about {topic}, {guest_name}. Here's what I can tell you:""",
                
                "booking_inquiry": """Regarding your booking inquiry, {guest_name}, I can help you with {booking_details}.""",
                
                "amenity_info": """Our {amenity} is available {availability_info}. {additional_details}""",
                
                "closing": """Is there anything else I can help you with today, {guest_name}? We're here to make your stay at {hotel_name} exceptional."""
            },
            
            "context_templates": {
                "guest_history": """Guest History:
- Previous stays: {stay_count}
- Loyalty status: {loyalty_status}
- Preferences: {preferences}
- Previous issues: {previous_issues}""",
                
                "current_stay": """Current Stay Information:
- Check-in: {checkin_date}
- Check-out: {checkout_date}
- Room: {room_number}
- Room type: {room_type}
- Special requests: {special_requests}""",
                
                "hotel_context": """Hotel Information:
- Hotel: {hotel_name}
- Location: {location}
- Star rating: {rating}
- Key amenities: {amenities}
- Contact: {contact_info}"""
            }
        }
    
    def get_system_prompt(
        self,
        response_type: ResponseType = ResponseType.HELPFUL,
        hotel: Optional[Hotel] = None,
        custom_instructions: Optional[str] = None
    ) -> str:
        """Get system prompt for response generation"""
        
        # Select base prompt based on response type
        if response_type in [ResponseType.COMPLAINT_RESOLUTION, ResponseType.APOLOGETIC]:
            base_prompt = self.templates["system_prompts"]["complaint_handling"]
        elif response_type == ResponseType.BOOKING_ASSISTANCE:
            base_prompt = self.templates["system_prompts"]["booking_assistance"]
        else:
            base_prompt = self.templates["system_prompts"]["base"]
        
        # Add hotel-specific context if available
        if hotel:
            hotel_context = f"\n\nHotel Context:\n- Hotel Name: {hotel.name}"
            if hotel.settings:
                settings = hotel.settings if isinstance(hotel.settings, dict) else {}
                if settings.get('brand_voice'):
                    hotel_context += f"\n- Brand Voice: {settings['brand_voice']}"
                if settings.get('service_standards'):
                    hotel_context += f"\n- Service Standards: {settings['service_standards']}"
            base_prompt += hotel_context
        
        # Add custom instructions if provided
        if custom_instructions:
            base_prompt += f"\n\nAdditional Instructions:\n{custom_instructions}"
        
        return base_prompt
    
    def create_user_prompt(
        self,
        guest_message: str,
        guest: Optional[Guest] = None,
        hotel: Optional[Hotel] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create user prompt for response generation"""
        
        prompt_parts = []
        
        # Add hotel context
        if hotel:
            hotel_info = self.templates["context_templates"]["hotel_context"].format(
                hotel_name=hotel.name,
                location=getattr(hotel, 'location', 'Not specified'),
                rating=getattr(hotel, 'rating', 'Not specified'),
                amenities=getattr(hotel, 'amenities', 'Standard hotel amenities'),
                contact_info=getattr(hotel, 'contact_info', 'Available at front desk')
            )
            prompt_parts.append(hotel_info)
        
        # Add guest context
        if guest:
            guest_preferences = guest.preferences if isinstance(guest.preferences, dict) else {}
            guest_history = self.templates["context_templates"]["guest_history"].format(
                stay_count=guest_preferences.get('stay_count', 'First time'),
                loyalty_status=guest_preferences.get('loyalty_status', 'Standard'),
                preferences=json.dumps(guest_preferences.get('preferences', {})),
                previous_issues=guest_preferences.get('previous_issues', 'None recorded')
            )
            prompt_parts.append(guest_history)
        
        # Add conversation history
        if conversation_history:
            history_text = "Recent Conversation:\n"
            for msg in conversation_history[-5:]:  # Last 5 messages
                role = "Guest" if msg.get('type') == 'incoming' else "Hotel"
                history_text += f"- {role}: {msg.get('content', '')}\n"
            prompt_parts.append(history_text)
        
        # Add additional context
        if context:
            context_text = "Additional Context:\n"
            for key, value in context.items():
                context_text += f"- {key}: {value}\n"
            prompt_parts.append(context_text)
        
        # Add the current guest message
        guest_name = guest.name if guest and guest.name else "Guest"
        prompt_parts.append(f"Current Guest Message from {guest_name}:\n\"{guest_message}\"")
        
        # Add instruction
        prompt_parts.append("Please provide a helpful, professional response to the guest's message.")
        
        return "\n\n".join(prompt_parts)
    
    def get_response_template(
        self,
        template_type: str,
        **kwargs
    ) -> str:
        """Get and format a response template"""
        
        if template_type not in self.templates["response_templates"]:
            return ""
        
        template = self.templates["response_templates"][template_type]
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # Return template with missing variables as placeholders
            return template
    
    def detect_response_type(self, guest_message: str, context: Optional[Dict[str, Any]] = None) -> ResponseType:
        """Detect the appropriate response type based on message content"""
        
        message_lower = guest_message.lower()
        
        # Complaint indicators
        complaint_keywords = [
            'complaint', 'problem', 'issue', 'wrong', 'bad', 'terrible', 'awful',
            'disappointed', 'unsatisfied', 'unhappy', 'frustrated', 'angry'
        ]
        
        # Booking indicators
        booking_keywords = [
            'book', 'reservation', 'room', 'availability', 'check-in', 'check-out',
            'cancel', 'modify', 'change', 'price', 'rate'
        ]
        
        # Information request indicators
        info_keywords = [
            'information', 'details', 'tell me', 'what', 'where', 'when', 'how',
            'amenities', 'facilities', 'services'
        ]
        
        # Check for complaint indicators
        if any(keyword in message_lower for keyword in complaint_keywords):
            return ResponseType.COMPLAINT_RESOLUTION
        
        # Check for booking indicators
        if any(keyword in message_lower for keyword in booking_keywords):
            return ResponseType.BOOKING_ASSISTANCE
        
        # Check for information requests
        if any(keyword in message_lower for keyword in info_keywords):
            return ResponseType.INFORMATIONAL
        
        # Check context for sentiment
        if context and context.get('sentiment_score', 0) < -0.5:
            return ResponseType.APOLOGETIC
        
        # Default to helpful response
        return ResponseType.HELPFUL
    
    def create_escalation_prompt(
        self,
        guest_message: str,
        issue_type: str,
        urgency_level: str = "normal"
    ) -> str:
        """Create prompt for escalation scenarios"""
        
        return f"""This guest message requires escalation to hotel staff:

Issue Type: {issue_type}
Urgency Level: {urgency_level}
Guest Message: "{guest_message}"

Please provide a professional response that:
1. Acknowledges the guest's concern
2. Apologizes for any inconvenience
3. Explains that you're connecting them with the appropriate staff member
4. Sets expectations for follow-up timing
5. Provides any immediate assistance possible

The response should be empathetic and reassuring while clearly indicating that specialized help is on the way."""


# Global template manager instance
_template_manager: Optional[PromptTemplateManager] = None


def get_prompt_template_manager() -> PromptTemplateManager:
    """Get global prompt template manager instance"""
    global _template_manager
    if _template_manager is None:
        _template_manager = PromptTemplateManager()
    return _template_manager


# Export main components
__all__ = [
    'ResponseType',
    'PromptTemplateManager',
    'get_prompt_template_manager'
]
