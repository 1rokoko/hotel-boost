"""
API v1 router
"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    health, webhooks, conversations, monitoring, hotels, triggers, trigger_monitoring,
    sentiment_analytics, sentiment_metrics, templates, auth, admin_reliability, performance
)
from app.api.v1 import deepseek_monitoring, admin

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(deepseek_monitoring.router, prefix="/deepseek", tags=["deepseek"])
api_router.include_router(sentiment_analytics.router, prefix="/sentiment-analytics", tags=["sentiment-analytics"])
api_router.include_router(sentiment_metrics.router, prefix="/sentiment-metrics", tags=["sentiment-metrics"])

# Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Hotel management endpoints
api_router.include_router(hotels.router, prefix="/hotels", tags=["hotels"])
api_router.include_router(triggers.router, prefix="/triggers", tags=["triggers"])
api_router.include_router(trigger_monitoring.router, prefix="/triggers/monitoring", tags=["trigger-monitoring"])

# Template management endpoints
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])

# Include admin router
api_router.include_router(admin.admin_router, prefix="/admin", tags=["admin"])

# Include reliability admin endpoints
api_router.include_router(admin_reliability.router, tags=["admin", "reliability"])

# Include performance monitoring endpoints
api_router.include_router(performance.router, prefix="/performance", tags=["performance", "admin"])

# Placeholder for future endpoints
# api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
