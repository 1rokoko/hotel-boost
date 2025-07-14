#!/usr/bin/env python3
"""
Fix triggers endpoints dependency injection
"""

import re

def fix_triggers_endpoints():
    """Fix all trigger endpoints to use correct dependency injection"""
    
    with open('app/api/v1/endpoints/triggers.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern 1: Remove trigger_service dependency from function signatures
    content = re.sub(
        r',\s*trigger_service: TriggerService = Depends\(get_trigger_service\)',
        '',
        content
    )
    
    # Pattern 2: Add trigger_service creation at the beginning of try blocks
    # Find all functions that use trigger_service
    functions_with_trigger_service = [
        'get_trigger', 'update_trigger', 'delete_trigger', 'list_triggers',
        'test_trigger', 'get_trigger_statistics', 'bulk_trigger_operation'
    ]
    
    for func_name in functions_with_trigger_service:
        # Find the function and add trigger_service creation
        pattern = rf'(async def {func_name}\([^)]+\):[^{{]*?try:\s*)'
        replacement = r'\1\n        trigger_service = TriggerService(db)'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Pattern 3: Remove unused import
    content = re.sub(
        r'from app\.services\.trigger_service import \(\s*TriggerService,\s*get_trigger_service,([^)]+)\)',
        r'from app.services.trigger_service import (\n    TriggerService,\1)',
        content
    )
    
    # Write back
    with open('app/api/v1/endpoints/triggers.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed triggers endpoints")

if __name__ == "__main__":
    fix_triggers_endpoints()
