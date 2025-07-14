#!/usr/bin/env python3
"""
Fix all async/sync issues in endpoints
"""

import os
import re
from pathlib import Path

def fix_async_issues():
    """Fix all async/sync issues in endpoint files"""
    
    endpoints_dir = Path('app/api/v1/endpoints')
    
    for file_path in endpoints_dir.glob('*.py'):
        print(f"Processing {file_path}...")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace AsyncSession with Session
        content = re.sub(r'AsyncSession', 'Session', content)
        
        # Replace get_async_db with get_db
        content = re.sub(r'get_async_db', 'get_db', content)
        
        # Fix imports
        content = re.sub(
            r'from sqlalchemy\.ext\.asyncio import AsyncSession',
            'from sqlalchemy.orm import Session',
            content
        )
        
        # Remove async/await from database operations if present
        content = re.sub(r'await db\.', 'db.', content)
        content = re.sub(r'await session\.', 'session.', content)
        
        # Fix dependency injection issues
        content = re.sub(
            r',\s*\w+_service: \w+ = Depends\(get_\w+_service\)',
            '',
            content
        )
        
        # Add service creation in try blocks
        if 'service.' in content and 'service = ' not in content:
            # Find service usage and add creation
            service_matches = re.findall(r'(\w+_service)\.', content)
            for service_name in set(service_matches):
                service_class = service_name.replace('_service', '_Service').replace('_S', 'S')
                pattern = rf'(\s+try:\s*\n)'
                replacement = rf'\1        {service_name} = {service_class}(db)\n'
                content = re.sub(pattern, replacement, content, count=1)
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ Fixed {file_path}")
        else:
            print(f"  ⏭️ No changes needed for {file_path}")
    
    print("✅ All async issues fixed")

if __name__ == "__main__":
    fix_async_issues()
