#!/usr/bin/env python3
"""
Script to clear all caches and restart services
"""

import asyncio
import redis
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from app.core.config import settings
    from app.services.cache_service import get_cache_service
    from app.services.deepseek_cache import DeepSeekCacheService
    from app.utils.template_renderer import TemplateRenderer
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


async def clear_redis_cache():
    """Clear all Redis cache"""
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_DB', 0),
            password=getattr(settings, 'REDIS_PASSWORD', None),
            decode_responses=True
        )
        
        # Test connection
        redis_client.ping()
        
        # Clear all Redis data
        redis_client.flushdb()
        print("✅ Redis cache cleared successfully")
        
    except Exception as e:
        print(f"❌ Error clearing Redis cache: {e}")


async def clear_application_caches():
    """Clear application-level caches"""
    try:
        # Clear main cache service
        cache_service = await get_cache_service()
        if cache_service:
            await cache_service.clear_all()
            print("✅ Application cache service cleared")
        
        # Clear DeepSeek cache
        deepseek_cache = DeepSeekCacheService()
        cleared_count = deepseek_cache.clear_cache()
        print(f"✅ DeepSeek cache cleared ({cleared_count} keys)")
        
        # Clear template cache
        template_renderer = TemplateRenderer()
        template_renderer.clear_cache()
        print("✅ Template cache cleared")
        
    except Exception as e:
        print(f"❌ Error clearing application caches: {e}")


def clear_browser_cache_instructions():
    """Print instructions for clearing browser cache"""
    print("\n🌐 BROWSER CACHE CLEARING INSTRUCTIONS:")
    print("1. Press Ctrl+Shift+R (or Cmd+Shift+R on Mac) to hard refresh")
    print("2. Or press F12 -> Network tab -> check 'Disable cache'")
    print("3. Or in Chrome: Settings -> Privacy -> Clear browsing data")
    print("4. Make sure to clear 'Cached images and files'")


async def main():
    """Main function to clear all caches"""
    print("🧹 Starting cache clearing process...")
    print("=" * 50)
    
    # Clear Redis cache
    print("1. Clearing Redis cache...")
    await clear_redis_cache()
    
    # Clear application caches
    print("\n2. Clearing application caches...")
    await clear_application_caches()
    
    # Browser cache instructions
    clear_browser_cache_instructions()
    
    print("\n" + "=" * 50)
    print("✅ Cache clearing completed!")
    print("\n📝 NEXT STEPS:")
    print("1. Restart the server: python minimal_server.py")
    print("2. Clear your browser cache (see instructions above)")
    print("3. Navigate to http://localhost:8002/api/v1/admin/dashboard")
    print("4. Test all menu sections")


if __name__ == "__main__":
    asyncio.run(main())
