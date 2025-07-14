#!/usr/bin/env python3
"""
Fix await issues in sentiment_metrics.py
"""

import re

def fix_sentiment_metrics():
    """Remove all await statements from sentiment_metrics.py"""
    
    with open('app/api/v1/endpoints/sentiment_metrics.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove await from function calls
    content = re.sub(r'await _check_system_health\(', '_check_system_health(', content)
    content = re.sub(r'await _get_performance_metrics\(', '_get_performance_metrics(', content)
    content = re.sub(r'await _get_alert_metrics\(', '_get_alert_metrics(', content)
    content = re.sub(r'await _get_ai_model_performance\(', '_get_ai_model_performance(', content)
    
    # Remove async from function definitions
    content = re.sub(r'async def _check_system_health\(', 'def _check_system_health(', content)
    content = re.sub(r'async def _get_performance_metrics\(', 'def _get_performance_metrics(', content)
    content = re.sub(r'async def _get_alert_metrics\(', 'def _get_alert_metrics(', content)
    content = re.sub(r'async def _get_ai_model_performance\(', 'def _get_ai_model_performance(', content)
    
    with open('app/api/v1/endpoints/sentiment_metrics.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed sentiment metrics awaits")

if __name__ == "__main__":
    fix_sentiment_metrics()
