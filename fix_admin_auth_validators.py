#!/usr/bin/env python3
"""
Fix admin auth validators for Pydantic v2
"""

import re

def fix_admin_auth_validators():
    """Fix all validator decorators in admin_auth.py"""
    
    with open('app/schemas/admin_auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add field_validator import if not present
    if 'field_validator' not in content:
        content = re.sub(
            r'from pydantic import ([^)]+)',
            r'from pydantic import \1, field_validator',
            content
        )
    
    # Replace @validator with @field_validator and add @classmethod
    content = re.sub(
        r'@validator\(([^)]+)\)\s*\n(\s+)def (\w+)\(cls, v',
        r'@field_validator(\1)\n\2@classmethod\n\2def \3(cls, v',
        content
    )
    
    # Handle validators with values parameter (for password confirmation)
    content = re.sub(
        r'@field_validator\(([^)]+)\)\s*\n(\s+)@classmethod\s*\n(\s+)def (\w+)\(cls, v, values\)',
        r'@field_validator(\1)\n\2@classmethod\n\3def \4(cls, v, info)',
        content
    )
    
    # Update values access to info.data
    content = re.sub(
        r"'([^']+)' in values and v != values\['([^']+)'\]",
        r"'\1' in info.data and v != info.data['\2']",
        content
    )
    
    with open('app/schemas/admin_auth.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed admin auth validators")

if __name__ == "__main__":
    fix_admin_auth_validators()
