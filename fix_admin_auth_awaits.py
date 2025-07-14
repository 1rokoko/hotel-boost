#!/usr/bin/env python3
"""
Fix await issues in admin_auth.py
"""

import re

def fix_admin_auth_awaits():
    """Remove all await statements from admin_auth.py"""
    
    with open('app/api/v1/endpoints/admin_auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove await from audit_logger calls
    content = re.sub(r'await audit_logger\.', 'audit_logger.', content)
    
    # Remove await from auth_service calls
    content = re.sub(r'await auth_service\.', 'auth_service.', content)
    
    # Remove async from function definitions that don't need it
    content = re.sub(r'async def admin_login\(', 'def admin_login(', content)
    content = re.sub(r'async def admin_logout\(', 'def admin_logout(', content)
    content = re.sub(r'async def change_password\(', 'def change_password(', content)
    
    with open('app/api/v1/endpoints/admin_auth.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed admin auth awaits")

if __name__ == "__main__":
    fix_admin_auth_awaits()
