"""
Middleware package for WhatsApp Hotel Bot application
"""

from app.middleware.tenant import (
    TenantContextMiddleware,
    DatabaseTenantMiddleware,
    TenantValidationMiddleware,
    add_tenant_middlewares,
    get_current_tenant_id,
    require_tenant_context
)

from app.middleware.database import (
    DatabaseMetricsMiddleware,
    DatabaseHealthMiddleware,
    DatabaseConnectionMiddleware,
    add_database_middlewares
)

from app.middleware.green_api_middleware import (
    GreenAPIMiddleware,
    green_api_metrics
)

__all__ = [
    # Tenant middleware
    'TenantContextMiddleware',
    'DatabaseTenantMiddleware',
    'TenantValidationMiddleware',
    'add_tenant_middlewares',
    'get_current_tenant_id',
    'require_tenant_context',

    # Database middleware
    'DatabaseMetricsMiddleware',
    'DatabaseHealthMiddleware',
    'DatabaseConnectionMiddleware',
    'add_database_middlewares',

    # Green API middleware
    'GreenAPIMiddleware',
    'green_api_metrics'
]
