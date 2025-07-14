#!/usr/bin/env python3
"""
Complete fix for admin_auth.py
"""

import re

def fix_admin_auth_complete():
    """Complete fix for admin_auth.py"""
    
    with open('app/api/v1/endpoints/admin_auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove get_admin_auth_service import
    content = re.sub(
        r'from app\.services\.admin_auth_service import \(\s*AdminAuthService,\s*get_admin_auth_service,([^)]+)\)',
        r'from app.services.admin_auth_service import (\n    AdminAuthService,\1)',
        content
    )
    
    # Remove audit_logger dependency from function signatures
    content = re.sub(
        r',\s*audit_logger: AdminAuditLogger = Depends\(\)',
        '',
        content
    )
    
    # Add service creation in functions that need it
    functions_needing_services = [
        'refresh_token', 'admin_logout', 'change_password'
    ]
    
    for func_name in functions_needing_services:
        # Find the function and add service creation
        pattern = rf'(def {func_name}\([^)]+\):[^{{]*?try:\s*)'
        replacement = r'\1\n        audit_logger = AdminAuditLogger(db)\n        auth_service = AdminAuthService(db)'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Fix get_current_admin_user function
    content = re.sub(
        r'(def get_current_admin_user\([^)]+\):[^{{]*?)(\s+try:)',
        r'\1\n    auth_service = AdminAuthService(db)\2',
        content,
        flags=re.DOTALL
    )
    
    # Fix from_orm to model_validate
    content = re.sub(
        r'AdminUserResponse\.from_orm\(([^)]+)\)',
        r'AdminUserResponse.model_validate(\1)',
        content
    )
    
    with open('app/api/v1/endpoints/admin_auth.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Complete fix for admin_auth.py")

if __name__ == "__main__":
    fix_admin_auth_complete()
