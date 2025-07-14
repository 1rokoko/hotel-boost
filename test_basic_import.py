#!/usr/bin/env python3
"""
Basic import test for WhatsApp Hotel Bot
Tests core components without complex dependencies
"""

import sys
import traceback

def test_basic_imports():
    """Test basic imports without complex dependencies"""
    
    print("🔍 Testing basic imports...")
    
    # Test 1: Core configuration
    try:
        from app.core.config import settings
        print("✅ Core config imported successfully")
    except Exception as e:
        print(f"❌ Core config failed: {e}")
        return False
    
    # Test 2: Database models
    try:
        from app.models.hotel import Hotel
        from app.models.guest import Guest
        print("✅ Database models imported successfully")
    except Exception as e:
        print(f"❌ Database models failed: {e}")
        return False
    
    # Test 3: Basic schemas
    try:
        from app.schemas.hotel import HotelCreate, HotelResponse
        print("✅ Basic schemas imported successfully")
    except Exception as e:
        print(f"❌ Basic schemas failed: {e}")
        return False
    
    # Test 4: Core logging
    try:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Test log message")
        print("✅ Core logging imported successfully")
    except Exception as e:
        print(f"❌ Core logging failed: {e}")
        return False
    
    # Test 5: Database connection
    try:
        from app.database import get_db
        print("✅ Database connection imported successfully")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    return True

def test_api_components():
    """Test API components"""
    
    print("\n🔍 Testing API components...")
    
    # Test 1: Health endpoint
    try:
        from app.api.v1.endpoints.health import router
        print("✅ Health endpoint imported successfully")
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
        return False
    
    # Test 2: Performance endpoint
    try:
        from app.api.v1.endpoints.performance import router
        print("✅ Performance endpoint imported successfully")
    except Exception as e:
        print(f"❌ Performance endpoint failed: {e}")
        return False
    
    return True

def test_services():
    """Test basic services"""
    
    print("\n🔍 Testing basic services...")
    
    # Test 1: Cache service
    try:
        from app.services.cache_service import CacheService
        print("✅ Cache service imported successfully")
    except Exception as e:
        print(f"❌ Cache service failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    
    print("🚀 Starting WhatsApp Hotel Bot Import Tests")
    print("=" * 50)
    
    success = True
    
    # Run tests
    success &= test_basic_imports()
    success &= test_api_components()
    success &= test_services()
    
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 All basic imports successful!")
        print("✅ System is ready for basic testing")
        return 0
    else:
        print("❌ Some imports failed")
        print("🔧 System needs fixes before full testing")
        return 1

if __name__ == "__main__":
    sys.exit(main())
