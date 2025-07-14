"""
Admin API router for WhatsApp Hotel Bot
"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    admin_auth,
    analytics,
    admin_users,
    admin_roles,
    admin_permissions,
    admin_system_settings,
    admin_reports,
    admin_monitoring
)

admin_router = APIRouter()

# Include admin endpoint routers
admin_router.include_router(admin_auth.router, prefix="/auth", tags=["admin-auth"])
admin_router.include_router(analytics.router, prefix="/analytics", tags=["admin-analytics"])
admin_router.include_router(admin_users.router, prefix="/users", tags=["admin-users"])
admin_router.include_router(admin_roles.router, prefix="/roles", tags=["admin-roles"])
admin_router.include_router(admin_permissions.router, prefix="/permissions", tags=["admin-permissions"])
admin_router.include_router(admin_system_settings.router, prefix="/settings", tags=["admin-settings"])
admin_router.include_router(admin_reports.router, prefix="/reports", tags=["admin-reports"])
admin_router.include_router(admin_monitoring.router, prefix="/monitoring", tags=["admin-monitoring"])
