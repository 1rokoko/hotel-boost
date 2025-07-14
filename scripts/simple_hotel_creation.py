#!/usr/bin/env python3
"""
Simple hotel creation script using direct database connection
"""

import os
import uuid
import json
import psycopg2
from psycopg2.extras import RealDictCursor

def create_hotel_simple():
    """Create hotel using direct psycopg2 connection"""
    
    # Database connection parameters
    db_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'hotel_boost'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    try:
        # Connect to database
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if hotel exists
        cursor.execute("""
            SELECT id, name, whatsapp_number 
            FROM hotels 
            WHERE whatsapp_number = %s
        """, ('+1234567890',))
        
        existing = cursor.fetchone()
        if existing:
            print(f"✅ Hotel already exists: {existing['name']} (ID: {existing['id']})")
            print(f"   WhatsApp: {existing['whatsapp_number']}")
            
            # Check configuration
            cursor.execute("""
                SELECT 
                    (green_api_instance_id IS NOT NULL AND green_api_token IS NOT NULL) as has_green_api,
                    (settings->>'deepseek' IS NOT NULL) as has_deepseek,
                    is_active
                FROM hotels 
                WHERE id = %s
            """, (existing['id'],))
            
            config = cursor.fetchone()
            if config:
                print(f"   Green API configured: {config['has_green_api']}")
                print(f"   DeepSeek configured: {config['has_deepseek']}")
                print(f"   Is active: {config['is_active']}")
                print(f"   Fully operational: {config['has_green_api'] and config['has_deepseek'] and config['is_active']}")
            
            return
        
        # Create hotel
        hotel_id = str(uuid.uuid4())
        
        default_settings = {
            "notifications": {
                "email_enabled": True,
                "sms_enabled": False,
                "webhook_enabled": False
            },
            "auto_responses": {
                "enabled": True,
                "greeting_message": "Welcome to our hotel! How can we help you today?",
                "business_hours": {
                    "enabled": True,
                    "start": "09:00",
                    "end": "18:00",
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
                "supported": ["en", "es", "fr"]
            },
            "green_api": {
                "webhook_enabled": True,
                "incoming_webhook": True,
                "outgoing_webhook": True,
                "rate_limit": {
                    "requests_per_minute": 50,
                    "requests_per_second": 2,
                    "burst_limit": 10
                },
                "timeouts": {
                    "connect": 10,
                    "read": 30,
                    "write": 10,
                    "pool": 60
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
                    "system_prompt": "You are a helpful hotel assistant. Respond professionally and courteously to guest inquiries.",
                    "greeting_prompt": "Welcome to our hotel! How can I help you today?",
                    "sentiment_prompt": "Analyze the sentiment of this message...",
                    "response_prompt": "Generate a helpful response..."
                }
            }
        }
        
        cursor.execute("""
            INSERT INTO hotels (
                id, name, whatsapp_number, 
                green_api_instance_id, green_api_token, green_api_webhook_token,
                settings, is_active, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
        """, (
            hotel_id,
            "Test Hotel with Full Config",
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
        print(f"   Name: Test Hotel with Full Config")
        print(f"   WhatsApp: +1234567890")
        print(f"   Green API Instance: 1234567890")
        
        # Verify configuration
        cursor.execute("""
            SELECT 
                (green_api_instance_id IS NOT NULL AND green_api_token IS NOT NULL) as has_green_api,
                (settings->>'deepseek' IS NOT NULL) as has_deepseek,
                (settings->'deepseek'->>'enabled')::boolean as deepseek_enabled,
                (settings->'deepseek'->>'api_key' IS NOT NULL) as has_deepseek_key,
                is_active
            FROM hotels 
            WHERE id = %s
        """, (hotel_id,))
        
        config = cursor.fetchone()
        if config:
            print(f"\n📋 Configuration Status:")
            print(f"   Green API configured: {config['has_green_api']}")
            print(f"   DeepSeek configured: {config['has_deepseek'] and config['deepseek_enabled'] and config['has_deepseek_key']}")
            print(f"   Is active: {config['is_active']}")
            print(f"   Fully operational: {config['has_green_api'] and config['has_deepseek'] and config['is_active']}")
        
        print(f"\n🎉 Hotel is ready for use!")
        print(f"   Access admin dashboard: http://localhost:8000/api/v1/admin/dashboard")
        print(f"   Hotel API endpoint: http://localhost:8000/api/v1/hotels/{hotel_id}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating hotel: {e}")
        raise


if __name__ == "__main__":
    print("🚀 Creating hotel with full configuration...")
    print("=" * 60)
    create_hotel_simple()
