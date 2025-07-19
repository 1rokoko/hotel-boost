"""
FastAPI application entry point for WhatsApp Hotel Bot MVP
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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
# Enhanced security headers middleware - temporarily disabled due to CSP header issues
# app.add_middleware(SecurityHeadersMiddleware)

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

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

# Simple API endpoints for admin dashboard (without authentication for demo)
# These MUST be defined BEFORE the main API router to avoid authentication conflicts
# Using /demo/ prefix to avoid conflicts with authenticated endpoints
@app.get("/api/v1/demo/hotels")
async def list_hotels_simple():
    """List hotels endpoint - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "Grand Plaza Hotel",
                "whatsapp_number": "+1234567890",
                "is_active": True,
                "has_green_api_credentials": True,
                "is_operational": True,
                "created_at": "2025-07-12T10:00:00Z"
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "name": "Ocean View Resort",
                "whatsapp_number": "+1234567891",
                "is_active": True,
                "has_green_api_credentials": True,
                "is_operational": True,
                "created_at": "2025-07-12T11:00:00Z"
            }
        ]
    }

@app.get("/api/v1/demo/conversations")
async def list_conversations_simple():
    """List conversations endpoint - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": [
            {
                "id": "conv-001",
                "hotel_id": "550e8400-e29b-41d4-a716-446655440001",
                "guest_phone": "+1234567890",
                "status": "active",
                "last_message": "Thank you for your help!",
                "created_at": "2025-07-19T10:00:00Z"
            },
            {
                "id": "conv-002",
                "hotel_id": "550e8400-e29b-41d4-a716-446655440002",
                "guest_phone": "+1234567891",
                "status": "closed",
                "last_message": "Great service, thank you!",
                "created_at": "2025-07-19T09:00:00Z"
            }
        ]
    }

@app.get("/api/v1/demo/triggers")
async def list_triggers_simple():
    """List triggers endpoint - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": [
            {
                "id": "trigger-001",
                "name": "Welcome Message",
                "type": "first_message",
                "is_active": True,
                "hotel_id": "550e8400-e29b-41d4-a716-446655440001"
            },
            {
                "id": "trigger-002",
                "name": "Check-in Reminder",
                "type": "time_based",
                "is_active": True,
                "hotel_id": "550e8400-e29b-41d4-a716-446655440002"
            }
        ]
    }

@app.get("/api/v1/demo/templates")
async def list_templates_simple():
    """List templates endpoint - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": [
            {
                "id": "template-001",
                "name": "Welcome Template",
                "content": "Welcome to our hotel!",
                "type": "greeting",
                "is_active": True
            },
            {
                "id": "template-002",
                "name": "Check-out Template",
                "content": "Thank you for staying with us!",
                "type": "farewell",
                "is_active": True
            }
        ]
    }

@app.get("/api/v1/demo/sentiment-analytics")
async def get_sentiment_analytics_simple():
    """Get sentiment analytics - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": {
            "overall_sentiment": "positive",
            "positive_percentage": 75.5,
            "neutral_percentage": 20.0,
            "negative_percentage": 4.5,
            "total_analyzed": 1250
        }
    }

@app.get("/api/v1/demo/admin/users")
async def list_users_simple():
    """List users endpoint - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": [
            {
                "id": "user-001",
                "username": "admin",
                "email": "admin@hotel.com",
                "role": "administrator",
                "is_active": True
            },
            {
                "id": "user-002",
                "username": "manager",
                "email": "manager@hotel.com",
                "role": "manager",
                "is_active": True
            }
        ]
    }

@app.get("/api/v1/demo/analytics")
async def get_analytics_simple():
    """Get analytics - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": {
            "messages_today": 127,
            "response_rate": 98.5,
            "average_response_time": "2.3 minutes",
            "guest_satisfaction": 4.7
        }
    }

@app.get("/api/v1/demo/monitoring")
async def get_monitoring_simple():
    """Get monitoring data - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": {
            "system_status": "healthy",
            "uptime": "99.9%",
            "active_connections": 45,
            "memory_usage": "67%",
            "cpu_usage": "23%"
        }
    }

@app.get("/api/v1/demo/security")
async def get_security_simple():
    """Get security data - simple version for admin dashboard"""
    return {
        "status": "success",
        "data": {
            "failed_login_attempts": 3,
            "active_sessions": 12,
            "security_alerts": 0,
            "last_security_scan": "2025-07-19T08:00:00Z"
        }
    }

# Include API router (AFTER simple endpoints to avoid authentication conflicts)
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

# Admin HTML routes
@app.get("/api/v1/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard HTML interface"""
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})

@app.get("/api/v1/admin/dashboard/data")
async def admin_dashboard_data():
    """Admin dashboard data API endpoint"""
    return {
        "status": "success",
        "data": {
            "message": "Admin dashboard ready",
            "features": ["user-management", "analytics", "monitoring", "security"]
        }
    }

@app.get("/api/v1/admin/deepseek-testing", response_class=HTMLResponse)
async def deepseek_testing(request: Request):
    """DeepSeek AI Testing page"""
    return templates.TemplateResponse("deepseek_testing.html", {"request": request})

@app.get("/api/v1/admin/ai-configuration", response_class=HTMLResponse)
async def ai_configuration(request: Request):
    """AI Configuration page"""
    return templates.TemplateResponse("ai_configuration.html", {"request": request})



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
