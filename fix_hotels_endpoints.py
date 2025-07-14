#!/usr/bin/env python3
"""
Quick fix script for hotels endpoints
"""

import re

def fix_hotels_endpoints():
    """Fix all hotel endpoints to use correct dependency"""
    
    # Read the file
    with open('app/api/v1/endpoints/hotels.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace all occurrences of the old pattern
    patterns = [
        # Pattern 1: Remove db dependency when hotel_service is present
        (
            r'(\s+)db: Session = Depends\(get_db\),\n(\s+)hotel_service: HotelService = Depends\(get_hotel_service\)',
            r'\2hotel_service: HotelService = Depends(get_hotel_service_dep)'
        ),
        # Pattern 2: Replace standalone hotel_service dependency
        (
            r'hotel_service: HotelService = Depends\(get_hotel_service\)',
            r'hotel_service: HotelService = Depends(get_hotel_service_dep)'
        )
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    
    # Write back the file
    with open('app/api/v1/endpoints/hotels.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed hotels endpoints")

if __name__ == "__main__":
    fix_hotels_endpoints()
