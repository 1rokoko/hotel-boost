#!/usr/bin/env python3
"""
Simple script to test hotel creation without complex relationships
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_sync_db_session
from app.models.hotel import Hotel
import structlog

logger = structlog.get_logger(__name__)


def create_simple_hotel() -> None:
    """Create a simple test hotel"""
    
    # Get database session
    db = get_sync_db_session()
    
    try:
        # Check if hotel already exists
        existing_hotel = db.query(Hotel).filter(Hotel.whatsapp_number == "+1234567890").first()
        if existing_hotel:
            print(f"✅ Hotel already exists: {existing_hotel.name} (ID: {existing_hotel.id})")
            return
        
        # Create hotel instance directly
        hotel = Hotel(
            name="Simple Test Hotel",
            whatsapp_number="+1234567890",
            green_api_instance_id="1234567890",
            green_api_token="test_green_api_token_here",
            green_api_webhook_token="test_webhook_token_here",
            is_active=True,
            settings={
                "notifications": {
                    "email_enabled": True,
                    "sms_enabled": False
                },
                "deepseek": {
                    "api_key": "sk-test-deepseek-api-key-here",
                    "model": "deepseek-chat"
                }
            }
        )
        
        # Add to database
        db.add(hotel)
        db.commit()
        db.refresh(hotel)
        
        print(f"✅ Hotel created successfully!")
        print(f"   Hotel ID: {hotel.id}")
        print(f"   Name: {hotel.name}")
        print(f"   WhatsApp: {hotel.whatsapp_number}")
        print(f"   Green API configured: {hotel.has_green_api_credentials}")
        print(f"   Operational: {hotel.is_operational}")
        
    except Exception as e:
        logger.error("Failed to create hotel", error=str(e))
        print(f"❌ Error creating hotel: {e}")
        raise
    finally:
        db.close()


def main():
    """Main function"""
    print("🚀 Creating simple test hotel...")
    print("=" * 50)
    
    try:
        create_simple_hotel()
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Failed to create hotel: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
