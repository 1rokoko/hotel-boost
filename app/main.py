"""
FastAPI application entry point for WhatsApp Hotel Bot MVP
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.metrics import init_metrics
from app.core.exception_handlers import register_exception_handlers
from app.core.advanced_logging import setup_advanced_logging
from app.middleware.logging_middleware import create_logging_middleware
from app.api.v1.api import api_router
from app.database import init_db, close_db
from app.middleware.monitoring import (
    MonitoringMiddleware,
    HealthCheckMiddleware,
    SecurityHeadersMiddleware,
    RateLimitingMiddleware
)
from app.middleware.circuit_breaker_middleware import add_circuit_breaker_middleware
from app.utils.dependency_checker import dependency_monitor, register_default_dependencies
from app.utils.degradation_handler import get_degradation_handler
from app.core.performance_integration import initialize_performance_optimizations, cleanup_performance_optimizations

# Setup logging
setup_logging()
setup_advanced_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting WhatsApp Hotel Bot application...")

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Initialize metrics
        if settings.PROMETHEUS_ENABLED:
            init_metrics()
            logger.info("Metrics initialized")

        # Initialize performance optimizations
        try:
            await initialize_performance_optimizations()
            logger.info("Performance optimizations initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize performance optimizations: {e}")

        # Initialize reliability components
        logger.info("Initializing reliability components...")

        # Register default dependencies
        register_default_dependencies()
        logger.info("Default dependencies registered")

        # Start dependency monitoring
        await dependency_monitor.start_monitoring(interval=60.0)
        logger.info("Dependency monitoring started")

        # Start degradation monitoring
        degradation_handler = get_degradation_handler()
        await degradation_handler.start_monitoring(interval=30.0)
        logger.info("Degradation monitoring started")

        # Start Green API monitoring
        try:
            from app.services.green_api_monitoring import start_monitoring
            import asyncio
            monitoring_task = asyncio.create_task(start_monitoring())
            logger.info("Green API monitoring started")
        except Exception as e:
            logger.warning(f"Failed to start Green API monitoring: {e}")

        logger.info("Application startup completed")
        yield

    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down application...")

        # Stop reliability monitoring
        try:
            await dependency_monitor.stop_monitoring()
            logger.info("Dependency monitoring stopped")
        except Exception as e:
            logger.warning(f"Error stopping dependency monitoring: {e}")

        try:
            degradation_handler = get_degradation_handler()
            await degradation_handler.stop_monitoring()
            logger.info("Degradation monitoring stopped")
        except Exception as e:
            logger.warning(f"Error stopping degradation monitoring: {e}")

        # Cancel monitoring task
        try:
            if 'monitoring_task' in locals():
                monitoring_task.cancel()
                logger.info("Green API monitoring stopped")
        except Exception as e:
            logger.warning(f"Error stopping monitoring: {e}")

        # Cleanup performance optimizations
        try:
            await cleanup_performance_optimizations()
            logger.info("Performance optimizations cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up performance optimizations: {e}")

        try:
            await close_db()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
        logger.info("Application shutdown completed")

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MVP система WhatsApp-ботов для отелей с фокусом на управление отзывами и автоматизацию коммуникации",
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add middleware (order matters - last added is executed first)
# Enhanced security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Webhook security middleware (for webhook endpoints)
from app.middleware.webhook_security import add_webhook_security_middleware
add_webhook_security_middleware(
    app,
    webhook_paths={
        "/api/v1/webhooks/green-api",
        "/api/v1/webhooks/green-api/",
        "/webhooks/green-api",
        "/webhooks/green-api/"
    },
    environment=settings.ENVIRONMENT
)

# Comprehensive rate limiting middleware (replaces basic rate limiting)
from app.middleware.rate_limiter import add_comprehensive_rate_limiting
add_comprehensive_rate_limiting(
    app,
    environment=settings.ENVIRONMENT,
    storage_backend="redis"
)

# Circuit breaker middleware (for reliability)
add_circuit_breaker_middleware(app)

# Health check middleware (for optimized health check logging)
app.add_middleware(HealthCheckMiddleware)

# Green API monitoring middleware
from app.middleware.green_api_middleware import GreenAPIMiddleware
app.add_middleware(GreenAPIMiddleware)

# User authentication middleware
from app.middleware.auth_middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)

# Hotel tenant middleware (for multi-tenancy support)
from app.middleware.tenant_middleware import add_hotel_tenant_middlewares
add_hotel_tenant_middlewares(
    app,
    hotel_header="X-Hotel-ID",
    require_hotel=False,  # Not required for all endpoints
    excluded_paths=["/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"],
    enable_permissions=True
)

# Logging middleware (should be early in the chain)
logging_middleware = create_logging_middleware(
    enable_request_logging=True,
    enable_response_logging=True,
    enable_body_logging=settings.DEBUG,
    performance_only=settings.ENVIRONMENT == 'production'
)
app.add_middleware(logging_middleware)

# Monitoring middleware (should be early in the chain)
app.add_middleware(MonitoringMiddleware)

# CORS middleware (should be one of the last)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount static files
import pathlib
import os
static_dir = pathlib.Path(__file__).parent / "static"
static_dir_abs = static_dir.resolve()
logger.info(f"Mounting static files from: {static_dir_abs}")
logger.info(f"Static directory exists: {static_dir_abs.exists()}")
logger.info(f"Current working directory: {os.getcwd()}")
app.mount("/static", StaticFiles(directory=str(static_dir_abs)), name="static")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "WhatsApp Hotel Bot API",
        "version": settings.VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "whatsapp-hotel-bot",
        "version": settings.VERSION
    }

# Register exception handlers
register_exception_handlers(app)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
