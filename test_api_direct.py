#!/usr/bin/env python3
"""
Direct API testing script for hotel-boost project
"""

import requests
import json
import sys
import time

def test_api_endpoint(url, method="GET", data=None, headers=None):
    """Test an API endpoint"""
    try:
        if headers is None:
            headers = {"Content-Type": "application/json"}
        
        print(f"\n🔍 Testing {method} {url}")
        
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            print(f"❌ Unsupported method: {method}")
            return False
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"✅ Success: {json.dumps(result, indent=2)[:200]}...")
                return True
            except:
                print(f"✅ Success: {response.text[:200]}...")
                return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Server not running on {url}")
        return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def main():
    """Main testing function"""
    base_url = "http://localhost:8002"
    
    print("🚀 Hotel Boost API Testing")
    print("=" * 50)
    
    # Test basic health
    print("\n1. Testing Health Check")
    test_api_endpoint(f"{base_url}/health")
    
    # Test hotels endpoint
    print("\n2. Testing Hotels List")
    test_api_endpoint(f"{base_url}/api/v1/hotels")
    
    # Test admin dashboard
    print("\n3. Testing Admin Dashboard")
    test_api_endpoint(f"{base_url}/api/v1/admin/dashboard")
    
    # Test triggers
    print("\n4. Testing Triggers")
    test_api_endpoint(f"{base_url}/api/v1/triggers")
    
    # Test DeepSeek demo
    print("\n5. Testing DeepSeek Demo")
    test_api_endpoint(f"{base_url}/api/v1/demo/sentiment-analytics")
    
    # Test creating a hotel
    print("\n6. Testing Hotel Creation")
    hotel_data = {
        "name": "Test Hotel API",
        "whatsapp_number": "+1234567890",
        "green_api_instance_id": "test123",
        "green_api_token": "token123",
        "deepseek_api_key": "sk-test123"
    }
    test_api_endpoint(f"{base_url}/api/v1/hotels", method="POST", data=hotel_data)
    
    print("\n" + "=" * 50)
    print("🏁 Testing Complete")

if __name__ == "__main__":
    main()
