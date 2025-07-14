#!/usr/bin/env python3
"""
Direct hotel creation script without complex relationships
"""

import sys
import os
import uuid

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import json

def create_hotel_direct():
    """Create hotel directly using SQL"""
    
    try:
        # Create engine with sync driver
        database_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        # Check if hotel exists
        result = session.execute(text("""
            SELECT id, name, whatsapp_number 
            FROM hotels 
            WHERE whatsapp_number = '+1234567890'
        """))
        
        existing = result.fetchone()
        if existing:
            print(f"✅ Hotel already exists: {existing[1]} (ID: {existing[0]})")
            print(f"   WhatsApp: {existing[2]}")
            return
        
        # Create hotel with SQL
        hotel_id = str(uuid.uuid4())
        
        default_settings = {
            "notifications": {
                "email_enabled": True,
                "sms_enabled": False
            },
            "green_api": {
                "webhook_enabled": True,
                "incoming_webhook": True,
                "outgoing_webhook": True
            },
            "deepseek": {
                "enabled": True,
                "api_key": "sk-test-deepseek-api-key-here",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "prompts": {
                    "system_prompt": "You are a helpful hotel assistant.",
                    "greeting_prompt": "Welcome to our hotel! How can I help you today?"
                }
            }
        }
        
        session.execute(text("""
            INSERT INTO hotels (
                id, name, whatsapp_number, 
                green_api_instance_id, green_api_token, green_api_webhook_token,
                settings, is_active, created_at, updated_at
            ) VALUES (
                :id, :name, :whatsapp_number,
                :instance_id, :token, :webhook_token,
                :settings, :is_active, NOW(), NOW()
            )
        """), {
            "id": hotel_id,
            "name": "Test Hotel Direct",
            "whatsapp_number": "+1234567890",
            "instance_id": "1234567890",
            "token": "test_green_api_token_here",
            "webhook_token": "test_webhook_token_here",
            "settings": json.dumps(default_settings),
            "is_active": True
        })
        
        session.commit()
        
        print(f"✅ Hotel created successfully!")
        print(f"   Hotel ID: {hotel_id}")
        print(f"   Name: Test Hotel Direct")
        print(f"   WhatsApp: +1234567890")
        print(f"   Green API Instance: 1234567890")
        print(f"   Settings configured: ✅")
        
        # Verify creation
        result = session.execute(text("""
            SELECT id, name, whatsapp_number, green_api_instance_id, 
                   (green_api_instance_id IS NOT NULL AND green_api_token IS NOT NULL) as has_credentials,
                   is_active
            FROM hotels 
            WHERE id = :hotel_id
        """), {"hotel_id": hotel_id})
        
        hotel = result.fetchone()
        if hotel:
            print(f"\n📋 Verification:")
            print(f"   Has Green API credentials: {hotel[4]}")
            print(f"   Is active: {hotel[5]}")
            print(f"   Operational: {hotel[4] and hotel[5]}")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Error creating hotel: {e}")
        raise


if __name__ == "__main__":
    print("🚀 Creating hotel directly with SQL...")
    print("=" * 50)
    create_hotel_direct()
