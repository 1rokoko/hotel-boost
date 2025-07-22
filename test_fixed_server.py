#!/usr/bin/env python3
"""
Test script for the fixed server
"""

import subprocess
import time
import requests
import json
import sys

def start_server():
    """Start the fixed server"""
    print("🚀 Starting fixed server...")
    try:
        # Start server in background
        process = subprocess.Popen(
            [sys.executable, "app_fixed.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        time.sleep(5)
        
        return process
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None

def test_endpoints():
    """Test all endpoints"""
    base_url = "http://localhost:8002"
    
    tests = [
        ("Health Check", "GET", "/health"),
        ("Hotels List", "GET", "/api/v1/hotels"),
        ("Triggers List", "GET", "/api/v1/triggers"),
        ("Admin Dashboard", "GET", "/api/v1/admin/dashboard"),
    ]
    
    results = []
    
    for name, method, endpoint in tests:
        try:
            url = f"{base_url}{endpoint}"
            print(f"🔍 Testing {name}: {method} {endpoint}")
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ {name}: SUCCESS")
                results.append((name, True, response.status_code))
            else:
                print(f"❌ {name}: FAILED ({response.status_code})")
                results.append((name, False, response.status_code))
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {name}: CONNECTION ERROR")
            results.append((name, False, "Connection Error"))
        except Exception as e:
            print(f"❌ {name}: ERROR - {e}")
            results.append((name, False, str(e)))
    
    return results

def test_hotel_creation():
    """Test hotel creation"""
    print("\n🏨 Testing Hotel Creation...")
    
    try:
        url = "http://localhost:8002/api/v1/hotels"
        data = {
            "name": f"Test Hotel {int(time.time())}",
            "whatsapp_number": "+1234567890",
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "deepseek_api_key": "sk-6678b3438d024f27a0543615f02c6dda"
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Hotel created: {result['data']['name']}")
            return True, result['data']['id']
        else:
            print(f"❌ Hotel creation failed: {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"❌ Hotel creation error: {e}")
        return False, None

def test_trigger_templates(hotel_id):
    """Test trigger template creation"""
    print(f"\n🎯 Testing Trigger Templates for hotel {hotel_id}...")
    
    try:
        url = f"http://localhost:8002/api/v1/hotels/{hotel_id}/triggers/templates"
        response = requests.post(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Triggers created: {result['message']}")
            return True
        else:
            print(f"❌ Trigger creation failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Trigger creation error: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 HOTEL BOOST FIXED SERVER TESTING")
    print("=" * 50)
    
    # Start server
    server_process = start_server()
    
    if not server_process:
        print("❌ Failed to start server")
        return
    
    try:
        # Test basic endpoints
        print("\n📡 Testing Basic Endpoints...")
        results = test_endpoints()
        
        # Test hotel creation
        success, hotel_id = test_hotel_creation()
        
        # Test trigger templates if hotel was created
        if success and hotel_id:
            test_trigger_templates(hotel_id)
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        
        passed = sum(1 for _, success, _ in results if success)
        total = len(results)
        
        print(f"Basic Endpoints: {passed}/{total} passed")
        print(f"Hotel Creation: {'✅ PASSED' if success else '❌ FAILED'}")
        
        if passed == total and success:
            print("\n🎉 ALL TESTS PASSED! Server is working correctly.")
        else:
            print("\n⚠️ Some tests failed. Check the output above.")
    
    finally:
        # Stop server
        if server_process:
            print("\n🛑 Stopping server...")
            server_process.terminate()
            server_process.wait()

if __name__ == "__main__":
    main()
