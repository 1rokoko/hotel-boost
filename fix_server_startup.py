#!/usr/bin/env python3
"""
Fix server startup issues
"""

import os
import re
from pathlib import Path

def fix_endpoints_only():
    """Fix only endpoint files to get server running"""
    
    endpoints_dir = Path('app/api/v1/endpoints')
    
    for file_path in endpoints_dir.glob('*.py'):
        if file_path.name == '__init__.py':
            continue
            
        print(f"Fixing {file_path}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Fix imports
            content = re.sub(r'from sqlalchemy\.ext\.asyncio import AsyncSession', 'from sqlalchemy.orm import Session', content)
            content = re.sub(r'from sqlalchemy\.ext\.asyncio import Session', 'from sqlalchemy.orm import Session', content)
            content = re.sub(r'AsyncSession', 'Session', content)
            content = re.sub(r'get_async_db', 'get_db', content)
            
            # Remove service dependencies
            content = re.sub(r',\s*\w+_service:\s*\w+\s*=\s*Depends\([^)]+\)', '', content)
            
            # Remove async/await from database operations
            content = re.sub(r'await\s+db\.', 'db.', content)
            content = re.sub(r'await\s+session\.', 'session.', content)
            
            # Fix function signatures - remove async from non-async functions
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                # If line has async def but no await in the function, remove async
                if 'async def ' in line and 'await' not in content[content.find(line):content.find(line) + 1000]:
                    line = line.replace('async def ', 'def ')
                new_lines.append(line)
            
            content = '\n'.join(new_lines)
            
            # Only write if content changed
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  ✅ Fixed {file_path}")
            else:
                print(f"  ⏭️ No changes needed for {file_path}")
                
        except Exception as e:
            print(f"  ❌ Error fixing {file_path}: {e}")
    
    print("✅ Endpoint fixes completed")

def test_import():
    """Test if app can be imported"""
    try:
        import sys
        sys.path.append('.')
        from app.main import app
        print("✅ App imports successfully!")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Fixing server startup issues...")
    fix_endpoints_only()
    print("\n🧪 Testing import...")
    test_import()
