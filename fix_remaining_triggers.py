#!/usr/bin/env python3
"""
Fix remaining trigger service calls
"""

import re

def fix_remaining_triggers():
    """Fix remaining trigger service calls"""
    
    with open('app/api/v1/endpoints/triggers.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all lines that call trigger_service without creating it first
    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # If this line has "try:" and the next few lines use trigger_service
        if line.strip() == 'try:':
            # Look ahead to see if trigger_service is used
            for j in range(i+1, min(i+5, len(lines))):
                if 'trigger_service.' in lines[j] and 'trigger_service = TriggerService(db)' not in lines[j]:
                    # Add trigger_service creation
                    indent = len(line) - len(line.lstrip())
                    new_lines.append(' ' * (indent + 4) + 'trigger_service = TriggerService(db)')
                    break
    
    # Write back
    with open('app/api/v1/endpoints/triggers.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    print("✅ Fixed remaining trigger service calls")

if __name__ == "__main__":
    fix_remaining_triggers()
