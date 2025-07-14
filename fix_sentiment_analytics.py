#!/usr/bin/env python3
"""
Fix sentiment analytics endpoints
"""

import re

def fix_sentiment_analytics():
    """Fix sentiment analytics dependency injection"""
    
    with open('app/api/v1/endpoints/sentiment_analytics.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove get_sentiment_analytics_service import
    content = re.sub(
        r'from app\.services\.sentiment_analytics import \(\s*SentimentAnalyticsService,\s*get_sentiment_analytics_service\s*\)',
        'from app.services.sentiment_analytics import SentimentAnalyticsService',
        content
    )
    
    # Remove analytics_service dependency from function signatures
    content = re.sub(
        r',\s*analytics_service: SentimentAnalyticsService = Depends\(get_sentiment_analytics_service\)',
        '',
        content
    )
    
    # Add analytics_service creation in try blocks
    content = re.sub(
        r'(\s+try:\s*\n)',
        r'\1        analytics_service = SentimentAnalyticsService(db)\n',
        content
    )
    
    with open('app/api/v1/endpoints/sentiment_analytics.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed sentiment analytics endpoints")

if __name__ == "__main__":
    fix_sentiment_analytics()
