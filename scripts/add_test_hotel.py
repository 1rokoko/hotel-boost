#!/usr/bin/env python3
"""
Script to add a test hotel with Green API and DeepSeek configuration
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from app.database import get_sync_db_session
from app.models.hotel import Hotel
from app.services.hotel_service import HotelService
from app.schemas.hotel import HotelCreate
import structlog

logger = structlog.get_logger(__name__)


def create_test_hotel() -> None:
    """Create a test hotel with full configuration"""

    # Get database session
    db: Session = get_sync_db_session()
    
    try:
        # Create hotel service
        hotel_service = HotelService(db)

        # Test hotel data
        test_hotel_data = HotelCreate(
                name="Grand Test Hotel",
                whatsapp_number="+1234567890",
                green_api_instance_id="1234567890",
                green_api_token="test_green_api_token_here",
                green_api_webhook_token="test_webhook_token_here",
                deepseek_api_key="sk-test-deepseek-api-key-here",
                is_active=True,
                settings={
                "notifications": {
                    "email_enabled": True,
                    "sms_enabled": False,
                    "webhook_enabled": True
                },
                "auto_responses": {
                    "enabled": True,
                    "greeting_message": "Welcome to Grand Test Hotel! How may I assist you today?",
                    "business_hours": {
                        "enabled": True,
                        "start": "08:00",
                        "end": "22:00",
                        "timezone": "UTC"
                    }
                },
                "sentiment_analysis": {
                    "enabled": True,
                    "threshold": 0.3,
                    "alert_negative": True
                },
                "language": {
                    "primary": "en",
                    "supported": ["en", "es", "fr", "de"]
                },
                "green_api": {
                    "webhook_enabled": True,
                    "incoming_webhook": True,
                    "outgoing_webhook": True,
                    "rate_limit": {
                        "requests_per_minute": 60,
                        "requests_per_second": 3,
                        "burst_limit": 15
                    },
                    "timeouts": {
                        "connect": 10,
                        "read": 30,
                        "write": 10,
                        "pool": 60
                    },
                    "retry": {
                        "max_attempts": 3,
                        "base_delay": 1.0,
                        "max_delay": 60.0,
                        "exponential_base": 2.0
                    }
                },
                "deepseek": {
                    "enabled": True,
                    "api_key": "sk-test-deepseek-api-key-here",
                    "model": "deepseek-chat",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "timeout": 60,
                    "max_requests_per_minute": 50,
                    "max_tokens_per_minute": 100000,
                    "cache_enabled": True,
                    "cache_ttl": 3600,
                    "sentiment_analysis": {
                        "enabled": True,
                        "threshold": 0.3,
                        "confidence_threshold": 0.7
                    },
                    "response_generation": {
                        "max_response_tokens": 500,
                        "response_temperature": 0.8,
                        "max_context_messages": 10,
                        "include_guest_history": True,
                        "use_hotel_branding": True
                    },
                    "prompts": {
                        "system_prompt": "You are a professional hotel assistant for Grand Test Hotel. Respond courteously and helpfully to all guest inquiries. Always maintain a warm, professional tone and provide accurate information about hotel services.",
                        "greeting_prompt": "Welcome to Grand Test Hotel! I'm your AI assistant. How may I help make your stay exceptional today?",
                        "escalation_prompt": "I understand this requires special attention. Let me connect you with our guest services team who will be happy to assist you personally."
                    }
                }
                }
            )
        
        # Check if hotel already exists
        existing_hotel = hotel_service.get_hotel_by_whatsapp_number(test_hotel_data.whatsapp_number)
        if existing_hotel:
            print(f"✅ Test hotel already exists: {existing_hotel.name} (ID: {existing_hotel.id})")
            print(f"   WhatsApp: {existing_hotel.whatsapp_number}")
            print(f"   Green API configured: {existing_hotel.has_green_api_credentials}")

            # Check DeepSeek configuration
            hotel_obj = db.query(Hotel).filter(Hotel.id == existing_hotel.id).first()
            if hotel_obj:
                print(f"   DeepSeek configured: {hotel_obj.is_deepseek_configured()}")
                print(f"   Fully configured: {hotel_obj.is_fully_configured()}")

            return

        # Create the hotel
        print("🏨 Creating test hotel...")
        created_hotel = hotel_service.create_hotel(test_hotel_data)

        print(f"✅ Test hotel created successfully!")
        print(f"   Hotel ID: {created_hotel.id}")
        print(f"   Name: {created_hotel.name}")
        print(f"   WhatsApp: {created_hotel.whatsapp_number}")
        print(f"   Green API Instance: {created_hotel.green_api_instance_id}")
        print(f"   Green API configured: {created_hotel.has_green_api_credentials}")

        # Get the hotel object to check DeepSeek configuration
        hotel_obj = db.query(Hotel).filter(Hotel.id == created_hotel.id).first()
        if hotel_obj:
            print(f"   DeepSeek configured: {hotel_obj.is_deepseek_configured()}")
            print(f"   Fully configured: {hotel_obj.is_fully_configured()}")

            # Print configuration details
            print("\n📋 Configuration Details:")
            print(f"   Green API Settings: {len(hotel_obj.get_green_api_settings())} keys")
            print(f"   DeepSeek Settings: {len(hotel_obj.get_deepseek_settings())} keys")

            deepseek_settings = hotel_obj.get_deepseek_settings()
            if deepseek_settings.get("prompts"):
                print(f"   Custom Prompts: {len(deepseek_settings['prompts'])} prompts configured")

        print("\n🎉 Test hotel is ready for use!")
        print(f"   Access admin dashboard: http://localhost:8000/api/v1/admin/dashboard")
        print(f"   Hotel API endpoint: http://localhost:8000/api/v1/hotels/{created_hotel.id}")

    except Exception as e:
        logger.error("Failed to create test hotel", error=str(e))
        print(f"❌ Error creating test hotel: {e}")
        raise
    finally:
        db.close()


def main():
    """Main function"""
    print("🚀 Adding test hotel with Green API and DeepSeek configuration...")
    print("=" * 60)

    try:
        create_test_hotel()
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Failed to create test hotel: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
