#!/usr/bin/env python3
"""
Script to check cache status and provide clearing instructions
"""

import redis
import os
import sys
from pathlib import Path

def check_redis_connection():
    """Check Redis connection and cache status"""
    try:
        # Try to connect to Redis
        redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True,
            socket_timeout=5
        )
        
        # Test connection
        redis_client.ping()
        
        # Get cache info
        info = redis_client.info()
        db_info = redis_client.info('keyspace')
        
        print("✅ Redis Connection: OK")
        print(f"📊 Redis Memory Used: {info.get('used_memory_human', 'Unknown')}")
        print(f"🔑 Total Keys: {db_info.get('db0', {}).get('keys', 0) if 'db0' in db_info else 0}")
        
        # Check for specific cache patterns
        patterns_to_check = [
            'deepseek:*',
            'hotel:*',
            'template:*',
            'session:*',
            'analytics:*'
        ]
        
        print("\n🔍 Cache Patterns:")
        for pattern in patterns_to_check:
            keys = redis_client.keys(pattern)
            print(f"  {pattern}: {len(keys)} keys")
        
        return True
        
    except redis.ConnectionError:
        print("❌ Redis Connection: FAILED")
        print("   Redis server is not running or not accessible")
        return False
    except Exception as e:
        print(f"❌ Redis Error: {e}")
        return False


def check_file_timestamps():
    """Check when key files were last modified"""
    files_to_check = [
        'app/templates/admin_dashboard.html',
        'minimal_server.py',
        'main.py'
    ]
    
    print("\n📁 File Modification Times:")
    for file_path in files_to_check:
        if os.path.exists(file_path):
            mtime = os.path.getmtime(file_path)
            import datetime
            mod_time = datetime.datetime.fromtimestamp(mtime)
            print(f"  {file_path}: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"  {file_path}: NOT FOUND")


def provide_clearing_instructions():
    """Provide cache clearing instructions"""
    print("\n" + "="*60)
    print("🧹 CACHE CLEARING INSTRUCTIONS")
    print("="*60)
    
    print("\n1. STOP THE SERVER:")
    print("   - Close the terminal running the server")
    print("   - Or press Ctrl+C in the server terminal")
    
    print("\n2. CLEAR REDIS CACHE:")
    print("   redis-cli")
    print("   > FLUSHDB")
    print("   > EXIT")
    
    print("\n3. RESTART SERVER:")
    print("   python minimal_server.py")
    
    print("\n4. CLEAR BROWSER CACHE:")
    print("   - Press Ctrl+Shift+R (hard refresh)")
    print("   - Or open DevTools (F12) → Network → check 'Disable cache'")
    
    print("\n5. TEST THE CHANGES:")
    print("   - Go to http://localhost:8002/api/v1/admin/dashboard")
    print("   - Test all menu sections")


def main():
    """Main function"""
    print("🔍 CACHE STATUS CHECK")
    print("="*40)
    
    # Check Redis
    redis_ok = check_redis_connection()
    
    # Check file timestamps
    check_file_timestamps()
    
    # Provide instructions
    provide_clearing_instructions()
    
    if not redis_ok:
        print("\n⚠️  WARNING: Redis is not accessible!")
        print("   Make sure Redis server is running:")
        print("   - Windows: Start Redis service")
        print("   - Linux/Mac: redis-server")


if __name__ == "__main__":
    main()
