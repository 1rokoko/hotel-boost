#!/usr/bin/env python3
"""
Comprehensive Health Check for WhatsApp Hotel Bot System

This script performs a complete health check of all system components
and provides detailed status information.
"""

import requests
import json
import sys
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint, expected_status=200, description=""):
    """Test a single endpoint and return results"""
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
        success = response.status_code == expected_status
        
        return {
            "endpoint": endpoint,
            "description": description,
            "status_code": response.status_code,
            "expected": expected_status,
            "success": success,
            "response_time": response.elapsed.total_seconds(),
            "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else None
        }
    except Exception as e:
        return {
            "endpoint": endpoint,
            "description": description,
            "success": False,
            "error": str(e)
        }

def run_health_checks():
    """Run comprehensive health checks"""
    
    print("🏥 WhatsApp Hotel Bot - Comprehensive Health Check")
    print("=" * 60)
    
    # Define test endpoints
    endpoints = [
        ("/health", 200, "System Health Check"),
        ("/docs", 200, "API Documentation"),
        ("/redoc", 200, "Alternative API Documentation"),
        ("/api/v1/admin/dashboard", 200, "Admin Dashboard"),
        ("/api/v1/hotels", 200, "Hotels API"),
        ("/api/v1/webhooks/green-api", 405, "Green API Webhook (Method Not Allowed is expected)"),
    ]
    
    results = []
    total_tests = len(endpoints)
    passed_tests = 0
    
    print(f"\n🧪 Running {total_tests} endpoint tests...\n")
    
    for endpoint, expected_status, description in endpoints:
        print(f"Testing: {endpoint} - {description}")
        result = test_endpoint(endpoint, expected_status, description)
        results.append(result)
        
        if result["success"]:
            print(f"  ✅ PASS - Status: {result['status_code']}, Time: {result.get('response_time', 0):.3f}s")
            passed_tests += 1
        else:
            error_msg = result.get('error', f'Status: {result.get("status_code", "unknown")}')
            print(f"  ❌ FAIL - {error_msg}")
        print()
    
    # Summary
    print("📊 HEALTH CHECK SUMMARY")
    print("=" * 30)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    # Detailed results for important endpoints
    print("\n📋 DETAILED RESULTS")
    print("=" * 30)
    
    for result in results:
        if result["success"] and result.get("data"):
            print(f"\n🔍 {result['endpoint']} - {result['description']}")
            if result["endpoint"] == "/health":
                health_data = result["data"]
                print(f"  Service: {health_data.get('service', 'unknown')}")
                print(f"  Version: {health_data.get('version', 'unknown')}")
                print(f"  Environment: {health_data.get('environment', 'unknown')}")
                print(f"  Status: {health_data.get('status', 'unknown')}")
                
                features = health_data.get('features', {})
                if features:
                    print("  Features:")
                    for feature, status in features.items():
                        print(f"    - {feature}: {status}")
            
            elif result["endpoint"] == "/api/v1/admin/dashboard":
                dashboard_data = result["data"]
                print(f"  Status: {dashboard_data.get('status', 'unknown')}")
                data = dashboard_data.get('data', {})
                print(f"  Message: {data.get('message', 'unknown')}")
                features = data.get('features', [])
                if features:
                    print(f"  Available Features: {', '.join(features)}")
    
    # Database check
    print("\n💾 DATABASE CHECK")
    print("=" * 20)
    db_path = Path("test.db")
    if db_path.exists():
        print(f"  ✅ Database file exists: {db_path}")
        print(f"  📏 Database size: {db_path.stat().st_size} bytes")
    else:
        print(f"  ❌ Database file not found: {db_path}")
    
    # Configuration check
    print("\n⚙️  CONFIGURATION CHECK")
    print("=" * 25)
    env_path = Path(".env")
    if env_path.exists():
        print(f"  ✅ Environment file exists: {env_path}")
        with open(env_path) as f:
            lines = f.readlines()
            print(f"  📝 Configuration lines: {len(lines)}")
    else:
        print(f"  ❌ Environment file not found: {env_path}")
    
    # Final assessment
    print("\n🎯 FINAL ASSESSMENT")
    print("=" * 20)
    
    if passed_tests == total_tests:
        print("🎉 ALL SYSTEMS OPERATIONAL!")
        print("✅ The WhatsApp Hotel Bot is ready for use")
        print("\n🚀 Next Steps:")
        print("1. Visit http://localhost:8000/docs to explore the API")
        print("2. Test the admin dashboard at http://localhost:8000/api/v1/admin/dashboard")
        print("3. Review the setup guide in docs/setup_guide.md")
        return True
    elif passed_tests >= total_tests * 0.8:
        print("⚠️  MOSTLY OPERATIONAL")
        print("🟡 Most systems are working, but some issues detected")
        print("📝 Review the failed tests above for details")
        return True
    else:
        print("❌ SYSTEM ISSUES DETECTED")
        print("🔴 Multiple failures detected - system may not be ready")
        print("🛠️  Please review the errors and fix issues before proceeding")
        return False

def main():
    """Main function"""
    try:
        success = run_health_checks()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Health check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Unexpected error during health check: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
