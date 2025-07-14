#!/usr/bin/env python3
"""
Test database connection without importing models
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def test_connection():
    """Test database connection"""
    
    try:
        # Create engine
        engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""))
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"✅ Database connection successful!")
            print(f"   Result: {result.fetchone()}")
            
            # Check if hotels table exists
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'hotels'
            """))
            
            if result.fetchone():
                print("✅ Hotels table exists")
                
                # Count hotels
                result = conn.execute(text("SELECT COUNT(*) FROM hotels"))
                count = result.fetchone()[0]
                print(f"   Hotels count: {count}")
            else:
                print("❌ Hotels table does not exist")
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise


if __name__ == "__main__":
    print("🚀 Testing database connection...")
    test_connection()
