#!/usr/bin/env python3
"""
Simple server test
"""

import requests
import time

def test_server():
    """Test if server is running"""
    try:
        response = requests.get("http://localhost:8002/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running!")
            print(f"📊 Response: {response.json()}")
            return True
        else:
            print(f"❌ Server returned status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server not running on localhost:8002")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testing server connection...")
    test_server()
