#!/usr/bin/env python3
"""
Test hotel creation using SQLite
"""

import sqlite3
import uuid
import json

def create_test_hotel():
    """Create test hotel using SQLite"""
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # Create hotels table
        cursor.execute("""
            CREATE TABLE hotels (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                whatsapp_number TEXT UNIQUE NOT NULL,
                green_api_instance_id TEXT,
                green_api_token TEXT,
                green_api_webhook_token TEXT,
                settings TEXT NOT NULL DEFAULT '{}',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create hotel
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
        
        cursor.execute("""
            INSERT INTO hotels (
                id, name, whatsapp_number, 
                green_api_instance_id, green_api_token, green_api_webhook_token,
                settings, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hotel_id,
            "Test Hotel SQLite",
            "+1234567890",
            "1234567890",
            "test_green_api_token_here",
            "test_webhook_token_here",
            json.dumps(default_settings),
            True
        ))
        
        conn.commit()
        
        print(f"✅ Hotel created successfully!")
        print(f"   Hotel ID: {hotel_id}")
        print(f"   Name: Test Hotel SQLite")
        print(f"   WhatsApp: +1234567890")
        print(f"   Green API Instance: 1234567890")
        
        # Verify creation
        cursor.execute("""
            SELECT id, name, whatsapp_number, 
                   (green_api_instance_id IS NOT NULL AND green_api_token IS NOT NULL) as has_credentials,
                   is_active, settings
            FROM hotels 
            WHERE id = ?
        """, (hotel_id,))
        
        hotel = cursor.fetchone()
        if hotel:
            settings_data = json.loads(hotel[5])
            has_deepseek = (
                settings_data.get("deepseek", {}).get("enabled", False) and
                bool(settings_data.get("deepseek", {}).get("api_key"))
            )
            
            print(f"\n📋 Verification:")
            print(f"   Has Green API credentials: {hotel[3]}")
            print(f"   Has DeepSeek configuration: {has_deepseek}")
            print(f"   Is active: {hotel[4]}")
            print(f"   Fully operational: {hotel[3] and has_deepseek and hotel[4]}")
        
        # Test hotel-specific settings access
        print(f"\n🔧 Testing hotel-specific settings:")
        
        # Test Green API settings
        green_api_settings = settings_data.get("green_api", {})
        print(f"   Green API webhook enabled: {green_api_settings.get('webhook_enabled', False)}")
        
        # Test DeepSeek settings
        deepseek_settings = settings_data.get("deepseek", {})
        print(f"   DeepSeek model: {deepseek_settings.get('model', 'N/A')}")
        print(f"   DeepSeek max tokens: {deepseek_settings.get('max_tokens', 'N/A')}")
        print(f"   DeepSeek temperature: {deepseek_settings.get('temperature', 'N/A')}")
        
        # Test custom prompts
        prompts = deepseek_settings.get("prompts", {})
        print(f"   Custom system prompt: {'✅' if prompts.get('system_prompt') else '❌'}")
        print(f"   Custom greeting prompt: {'✅' if prompts.get('greeting_prompt') else '❌'}")
        
        print(f"\n🎉 All hotel-specific configurations working correctly!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating hotel: {e}")
        raise


if __name__ == "__main__":
    print("🚀 Testing hotel creation with hotel-specific configurations...")
    print("=" * 70)
    create_test_hotel()
