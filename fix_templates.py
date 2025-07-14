#!/usr/bin/env python3
"""
Fix templates endpoints
"""

import re

def fix_templates():
    """Fix templates async/sync issues"""
    
    with open('app/api/v1/endpoints/templates.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace AsyncSession with Session
    content = re.sub(r'AsyncSession', 'Session', content)
    
    # Replace get_async_db with get_db
    content = re.sub(r'get_async_db', 'get_db', content)
    
    # Add Session import
    if 'from sqlalchemy.orm import Session' not in content:
        content = re.sub(
            r'from sqlalchemy\.ext\.asyncio import AsyncSession',
            'from sqlalchemy.orm import Session',
            content
        )
    
    with open('app/api/v1/endpoints/templates.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed templates endpoints")

if __name__ == "__main__":
    fix_templates()
