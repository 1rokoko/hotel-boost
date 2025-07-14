#!/usr/bin/env python3
"""
Health check script for WhatsApp Hotel Bot
Can be used for monitoring, load balancer health checks, etc.
"""

import asyncio
import sys
import time
import argparse
from typing import Dict, Any, Optional
import httpx
import json

class HealthChecker:
    """Health check utility for the application"""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def check_basic_health(self) -> Dict[str, Any]:
        """Check basic health endpoint"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "data": response.json() if response.status_code == 200 else None,
                "error": None
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "status_code": None,
                "response_time_ms": None,
                "data": None,
                "error": str(e)
            }
    
    async def check_detailed_health(self) -> Dict[str, Any]:
        """Check detailed health endpoint"""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/health/detailed")
            
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "data": response.json() if response.status_code == 200 else None,
                "error": None
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "status_code": None,
                "response_time_ms": None,
                "data": None,
                "error": str(e)
            }
    
    async def check_api_endpoints(self) -> Dict[str, Any]:
        """Check various API endpoints"""
        endpoints = [
            "/",
            "/health",
            "/api/v1/health/",
            "/api/v1/health/detailed"
        ]
        
        results = {}
        
        for endpoint in endpoints:
            try:
                start_time = time.time()
                response = await self.client.get(f"{self.base_url}{endpoint}")
                duration = (time.time() - start_time) * 1000
                
                results[endpoint] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code,
                    "response_time_ms": round(duration, 2)
                }
            except Exception as e:
                results[endpoint] = {
                    "status": "unhealthy",
                    "status_code": None,
                    "response_time_ms": None,
                    "error": str(e)
                }
        
        return results
    
    async def check_performance(self, requests: int = 10) -> Dict[str, Any]:
        """Check performance with multiple requests"""
        endpoint = "/health"
        response_times = []
        errors = 0
        
        for _ in range(requests):
            try:
                start_time = time.time()
                response = await self.client.get(f"{self.base_url}{endpoint}")
                duration = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    response_times.append(duration)
                else:
                    errors += 1
            except Exception:
                errors += 1
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = min_response_time = max_response_time = None
        
        return {
            "total_requests": requests,
            "successful_requests": len(response_times),
            "failed_requests": errors,
            "success_rate": len(response_times) / requests * 100,
            "avg_response_time_ms": round(avg_response_time, 2) if avg_response_time else None,
            "min_response_time_ms": round(min_response_time, 2) if min_response_time else None,
            "max_response_time_ms": round(max_response_time, 2) if max_response_time else None
        }
    
    async def comprehensive_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        print("Running comprehensive health check...")
        
        results = {
            "timestamp": time.time(),
            "base_url": self.base_url,
            "checks": {}
        }
        
        # Basic health check
        print("  Checking basic health...")
        results["checks"]["basic_health"] = await self.check_basic_health()
        
        # Detailed health check
        print("  Checking detailed health...")
        results["checks"]["detailed_health"] = await self.check_detailed_health()
        
        # API endpoints check
        print("  Checking API endpoints...")
        results["checks"]["api_endpoints"] = await self.check_api_endpoints()
        
        # Performance check
        print("  Checking performance...")
        results["checks"]["performance"] = await self.check_performance()
        
        # Overall status
        all_healthy = all(
            check.get("status") == "healthy" 
            for check_group in results["checks"].values()
            for check in (check_group.values() if isinstance(check_group, dict) else [check_group])
            if isinstance(check, dict) and "status" in check
        )
        
        results["overall_status"] = "healthy" if all_healthy else "unhealthy"
        
        return results
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Health check for WhatsApp Hotel Bot")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL to check")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--check", choices=["basic", "detailed", "endpoints", "performance", "all"], 
                       default="basic", help="Type of check to perform")
    parser.add_argument("--requests", type=int, default=10, help="Number of requests for performance check")
    parser.add_argument("--exit-code", action="store_true", help="Exit with non-zero code if unhealthy")
    
    args = parser.parse_args()
    
    checker = HealthChecker(args.url, args.timeout)
    
    try:
        if args.check == "basic":
            result = await checker.check_basic_health()
        elif args.check == "detailed":
            result = await checker.check_detailed_health()
        elif args.check == "endpoints":
            result = await checker.check_api_endpoints()
        elif args.check == "performance":
            result = await checker.check_performance(args.requests)
        else:  # all
            result = await checker.comprehensive_check()
        
        # Output results
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print_text_result(result, args.check)
        
        # Exit with appropriate code
        if args.exit_code:
            if args.check == "all":
                is_healthy = result.get("overall_status") == "healthy"
            else:
                is_healthy = result.get("status") == "healthy"
            
            sys.exit(0 if is_healthy else 1)
    
    finally:
        await checker.close()

def print_text_result(result: Dict[str, Any], check_type: str):
    """Print result in human-readable text format"""
    if check_type == "all":
        print(f"\n=== Health Check Results ===")
        print(f"Overall Status: {result['overall_status'].upper()}")
        print(f"Base URL: {result['base_url']}")
        print(f"Timestamp: {time.ctime(result['timestamp'])}")
        
        for check_name, check_result in result["checks"].items():
            print(f"\n--- {check_name.replace('_', ' ').title()} ---")
            if isinstance(check_result, dict):
                if "status" in check_result:
                    # Single check result
                    print_single_check(check_result)
                else:
                    # Multiple check results
                    for sub_check, sub_result in check_result.items():
                        print(f"  {sub_check}: ", end="")
                        if isinstance(sub_result, dict) and "status" in sub_result:
                            status = sub_result["status"].upper()
                            response_time = sub_result.get("response_time_ms")
                            if response_time:
                                print(f"{status} ({response_time:.1f}ms)")
                            else:
                                print(status)
                        else:
                            print(sub_result)
    else:
        print_single_check(result)

def print_single_check(result: Dict[str, Any]):
    """Print a single check result"""
    status = result.get("status", "unknown").upper()
    print(f"Status: {status}")
    
    if "response_time_ms" in result and result["response_time_ms"]:
        print(f"Response Time: {result['response_time_ms']:.1f}ms")
    
    if "status_code" in result and result["status_code"]:
        print(f"Status Code: {result['status_code']}")
    
    if "error" in result and result["error"]:
        print(f"Error: {result['error']}")
    
    # Performance metrics
    if "success_rate" in result:
        print(f"Success Rate: {result['success_rate']:.1f}%")
        print(f"Avg Response Time: {result['avg_response_time_ms']:.1f}ms")
        print(f"Min Response Time: {result['min_response_time_ms']:.1f}ms")
        print(f"Max Response Time: {result['max_response_time_ms']:.1f}ms")

if __name__ == "__main__":
    asyncio.run(main())
