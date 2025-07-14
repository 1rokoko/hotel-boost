#!/usr/bin/env python3
"""
Fix await issues in sentiment_analytics.py
"""

import re

def fix_sentiment_awaits():
    """Remove all await statements from sentiment_analytics.py"""
    
    with open('app/api/v1/endpoints/sentiment_analytics.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove await from service calls
    content = re.sub(r'await analytics_service\.', 'analytics_service.', content)
    
    # Remove async from function definitions if they don't need it
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        # Remove async from function definitions
        if 'async def ' in line and 'await' not in content:
            line = line.replace('async def ', 'def ')
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    with open('app/api/v1/endpoints/sentiment_analytics.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed sentiment analytics awaits")

if __name__ == "__main__":
    fix_sentiment_awaits()
