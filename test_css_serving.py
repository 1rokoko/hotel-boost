#!/usr/bin/env python3
"""
CSS Serving Test - Check if CSS file is being served correctly
"""

import asyncio
import aiohttp

async def test_css_serving():
    """Test if CSS file is being served correctly"""
    print("🔍 CSS SERVING TEST")
    print("=" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test CSS file serving
            css_url = "http://localhost:8000/static/css/admin_dashboard.css"
            
            async with session.get(css_url) as response:
                print(f"✅ CSS URL: {css_url}")
                print(f"✅ Status Code: {response.status}")
                print(f"✅ Content Type: {response.headers.get('content-type', 'Unknown')}")
                
                if response.status == 200:
                    css_content = await response.text()
                    print(f"✅ CSS Content Length: {len(css_content)} characters")
                    
                    # Check for key CSS rules
                    key_rules = [
                        "nav.sidebar",
                        "position: fixed",
                        "width: 250px",
                        "div.main-content",
                        "margin-left: 250px"
                    ]
                    
                    print("\n🔍 Checking for key CSS rules:")
                    for rule in key_rules:
                        if rule in css_content:
                            print(f"   ✅ Found: {rule}")
                        else:
                            print(f"   ❌ Missing: {rule}")
                    
                    # Show first 500 characters of CSS
                    print(f"\n📄 CSS Content Preview:")
                    print("-" * 50)
                    print(css_content[:500])
                    print("-" * 50)
                    
                else:
                    print(f"❌ Failed to load CSS file: {response.status}")
                    
    except Exception as e:
        print(f"❌ Error testing CSS serving: {e}")

if __name__ == "__main__":
    asyncio.run(test_css_serving())
