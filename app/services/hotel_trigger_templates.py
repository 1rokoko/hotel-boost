"""
Hotel Trigger Templates for WhatsApp Hotel Bot

This module provides pre-configured trigger templates that hotels can use
to improve guest experience and increase positive reviews.
"""

import uuid
from typing import Dict, List, Any
from datetime import datetime, timedelta

from app.schemas.trigger import TriggerCreate, TriggerScheduleType, TriggerEventType


class HotelTriggerTemplates:
    """Pre-configured trigger templates for hotels"""
    
    @staticmethod
    def get_welcome_triggers() -> List[Dict[str, Any]]:
        """Welcome and onboarding triggers"""
        return [
            {
                "name": "Welcome Message - Immediate",
                "description": "Send welcome message immediately after first contact",
                "trigger_type": "event_based",
                "conditions": {
                    "event_type": "first_message_received",
                    "delay_seconds": 0
                },
                "message_template": """🏨 Welcome to {{ hotel_name }}! 

We're delighted to have you as our guest. I'm your personal assistant and I'm here to help make your stay exceptional.

Feel free to ask me about:
• Hotel facilities and services
• Local attractions and recommendations  
• Restaurant reservations
• Transportation assistance
• Any special requests

How can I assist you today? 😊""",
                "priority": 1,
                "is_active": True
            },
            {
                "name": "Quick Response - 30 seconds",
                "description": "Follow-up if guest doesn't get immediate response",
                "trigger_type": "time_based",
                "conditions": {
                    "schedule_type": "seconds_after_first_message",
                    "delay_seconds": 30
                },
                "message_template": """Thank you for contacting {{ hotel_name }}! 

I'm processing your message and will respond shortly. In the meantime, here are some quick links:

🍽️ Restaurant menu: {{ restaurant_menu_link }}
🏊‍♂️ Pool hours: 6 AM - 10 PM
📞 Front desk: {{ front_desk_number }}

Your satisfaction is our priority! 🌟""",
                "priority": 2,
                "is_active": True
            }
        ]
    
    @staticmethod
    def get_experience_enhancement_triggers() -> List[Dict[str, Any]]:
        """Triggers to enhance guest experience"""
        return [
            {
                "name": "Check-in Day Welcome",
                "description": "Welcome message on check-in day with useful information",
                "trigger_type": "event_based",
                "conditions": {
                    "event_type": "guest_checkin",
                    "delay_minutes": 30
                },
                "message_template": """🎉 Welcome to {{ hotel_name }}!

Your room is ready and we hope you'll love your stay with us. Here's everything you need to know:

🔑 Your room: {{ room_number }}
📶 WiFi: {{ wifi_name }} / Password: {{ wifi_password }}
🍳 Breakfast: 7 AM - 10 AM at {{ restaurant_name }}
🏊‍♂️ Pool & Gym: 6 AM - 10 PM
🚗 Parking: {{ parking_info }}

Need anything? Just message me! 😊

Enjoy your stay! 🌟""",
                "priority": 1,
                "is_active": True
            },
            {
                "name": "Mid-Stay Check-in",
                "description": "Check how the guest is enjoying their stay",
                "trigger_type": "time_based",
                "conditions": {
                    "schedule_type": "hours_after_checkin",
                    "delay_hours": 24
                },
                "message_template": """Hi there! 👋

How are you enjoying your stay at {{ hotel_name }} so far? 

We want to make sure everything is perfect for you. If there's anything we can improve or if you need any assistance, please let me know right away.

Some guests love:
🌅 Our rooftop terrace (perfect for sunset!)
🍹 Happy hour at the bar (5-7 PM)
🏖️ Beach towel service
🚲 Complimentary bike rentals

Is there anything special we can arrange for you? 😊""",
                "priority": 3,
                "is_active": True
            }
        ]
    
    @staticmethod
    def get_review_optimization_triggers() -> List[Dict[str, Any]]:
        """Triggers to increase positive reviews and handle negative feedback"""
        return [
            {
                "name": "Pre-Checkout Satisfaction Check",
                "description": "Check satisfaction before checkout to address issues",
                "trigger_type": "time_based",
                "conditions": {
                    "schedule_type": "hours_after_checkin",
                    "delay_hours": 48  # 2 days before typical 3-day stay ends
                },
                "message_template": """Hi! 😊

We hope you've had a wonderful time at {{ hotel_name }}! 

Before you check out, we'd love to know:
• How has your experience been so far?
• Is there anything we could improve?
• Any special memories you'd like to share?

If anything hasn't met your expectations, please let us know immediately so we can make it right! 

Your feedback helps us serve you and future guests better. 🌟""",
                "priority": 2,
                "is_active": True
            },
            {
                "name": "Negative Sentiment Response",
                "description": "Immediate response to negative sentiment detection",
                "trigger_type": "event_based",
                "conditions": {
                    "event_type": "negative_sentiment_detected",
                    "delay_seconds": 60
                },
                "message_template": """I'm sorry to hear you're having concerns! 😔

Your satisfaction is extremely important to us. Let me connect you with our Guest Relations Manager immediately to resolve this.

📞 Direct line: {{ guest_relations_number }}
👤 Manager on duty: {{ manager_name }}

We're committed to making this right and ensuring the rest of your stay is exceptional.

Thank you for giving us the opportunity to improve! 🙏""",
                "priority": 1,
                "is_active": True
            },
            {
                "name": "Post-Stay Review Request",
                "description": "Request review after positive experience",
                "trigger_type": "event_based",
                "conditions": {
                    "event_type": "guest_checkout",
                    "delay_hours": 2
                },
                "message_template": """Thank you for staying with us at {{ hotel_name }}! 🏨

We hope you had an amazing experience and created wonderful memories.

If you enjoyed your stay, we'd be incredibly grateful if you could share your experience with others:

⭐ Google Review: {{ google_review_link }}
⭐ TripAdvisor: {{ tripadvisor_link }}
⭐ Booking.com: {{ booking_review_link }}

Your positive review helps other travelers discover our hotel and motivates our team to continue providing exceptional service.

We can't wait to welcome you back! 😊

Safe travels! ✈️""",
                "priority": 3,
                "is_active": True
            }
        ]
    
    @staticmethod
    def get_complaint_handling_triggers() -> List[Dict[str, Any]]:
        """Triggers for handling complaints and issues"""
        return [
            {
                "name": "Complaint Escalation",
                "description": "Escalate complaints to management",
                "trigger_type": "event_based",
                "conditions": {
                    "event_type": "guest_complaint",
                    "delay_seconds": 30
                },
                "message_template": """I understand your concern and I want to help resolve this immediately! 🚨

I'm escalating this to our management team right now:

👤 General Manager: {{ gm_name }}
📞 Direct line: {{ gm_number }}
📧 Email: {{ gm_email }}

Expected response time: Within 15 minutes

We take all feedback seriously and will work to resolve this to your complete satisfaction.

Thank you for bringing this to our attention. 🙏""",
                "priority": 1,
                "is_active": True
            }
        ]
    
    @staticmethod
    def get_all_templates() -> Dict[str, List[Dict[str, Any]]]:
        """Get all trigger templates organized by category"""
        return {
            "welcome": HotelTriggerTemplates.get_welcome_triggers(),
            "experience": HotelTriggerTemplates.get_experience_enhancement_triggers(),
            "reviews": HotelTriggerTemplates.get_review_optimization_triggers(),
            "complaints": HotelTriggerTemplates.get_complaint_handling_triggers()
        }
    
    @staticmethod
    def create_triggers_for_hotel(hotel_id: str) -> List[TriggerCreate]:
        """Create TriggerCreate objects for a specific hotel"""
        triggers = []
        all_templates = HotelTriggerTemplates.get_all_templates()
        
        for category, template_list in all_templates.items():
            for template in template_list:
                trigger_create = TriggerCreate(
                    name=template["name"],
                    trigger_type=template["trigger_type"],
                    message_template=template["message_template"],
                    conditions=template["conditions"],
                    is_active=template["is_active"],
                    priority=template["priority"]
                )
                triggers.append(trigger_create)
        
        return triggers
