#!/usr/bin/env python3
"""
SQLite Database Initialization Script for WhatsApp Hotel Bot

This script creates the necessary tables for the hotel bot system
using SQLite-compatible SQL statements.
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def create_sqlite_database():
    """Create SQLite database with all necessary tables"""
    
    # Database file path
    db_path = project_root / "test.db"
    
    print(f"Creating SQLite database at: {db_path}")
    
    # Connect to SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create hotels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hotels (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                name TEXT NOT NULL,
                whatsapp_number TEXT NOT NULL UNIQUE,
                green_api_instance_id TEXT,
                green_api_token TEXT,
                settings TEXT DEFAULT '{}',
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # Create guests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guests (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hotel_id TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                name TEXT,
                preferences TEXT DEFAULT '{}',
                last_interaction TIMESTAMP,
                FOREIGN KEY (hotel_id) REFERENCES hotels (id),
                UNIQUE(hotel_id, phone_number)
            )
        """)
        
        # Create conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hotel_id TEXT NOT NULL,
                guest_id TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                context TEXT DEFAULT '{}',
                FOREIGN KEY (hotel_id) REFERENCES hotels (id),
                FOREIGN KEY (guest_id) REFERENCES guests (id)
            )
        """)
        
        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                conversation_id TEXT NOT NULL,
                sender_type TEXT NOT NULL,
                content TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """)
        
        # Create triggers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triggers (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hotel_id TEXT NOT NULL,
                name TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                conditions TEXT DEFAULT '{}',
                actions TEXT DEFAULT '{}',
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (hotel_id) REFERENCES hotels (id)
            )
        """)
        
        # Create users table for admin authentication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                full_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                is_superuser BOOLEAN DEFAULT 0
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guests_hotel_phone ON guests (hotel_id, phone_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_hotel ON conversations (hotel_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages (created_at)")
        
        # Insert sample data for testing
        cursor.execute("""
            INSERT OR IGNORE INTO hotels (id, name, whatsapp_number, is_active)
            VALUES ('test-hotel-1', 'Test Hotel', '+1234567890', 1)
        """)
        
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, email, hashed_password, full_name, is_superuser)
            VALUES ('admin-1', 'admin@hotel.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6hsxq5/Qe2', 'Admin User', 1)
        """)
        # Note: The password above is 'secret' hashed with bcrypt
        
        conn.commit()
        print("✅ Database created successfully!")
        print("✅ Sample data inserted")
        print(f"✅ Database location: {db_path}")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"✅ Created tables: {[table[0] for table in tables]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def main():
    """Main function"""
    print("WhatsApp Hotel Bot - SQLite Database Initialization")
    print("=" * 50)
    
    if create_sqlite_database():
        print("\n🎉 Database initialization completed successfully!")
        print("\nNext steps:")
        print("1. Start the application: python -m uvicorn app_full:app --reload")
        print("2. Visit: http://localhost:8000/docs")
        print("3. Test admin login with: admin@hotel.com / secret")
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
