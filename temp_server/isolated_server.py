#!/usr/bin/env python3
"""
Completely isolated server with original admin dashboard template
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

app = FastAPI()

# Demo endpoints with /demo/ prefix to avoid auth conflicts
@app.get("/api/v1/demo/hotels")
async def list_hotels_simple():
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
            }
        ]
    }

@app.get("/api/v1/demo/triggers")
async def list_triggers_simple():
    return {
        "status": "success",
        "data": [
            {
                "id": "trigger-001",
                "name": "Welcome Message",
                "type": "first_message",
                "is_active": True,
                "hotel_id": "550e8400-e29b-41d4-a716-446655440001"
            }
        ]
    }

@app.get("/api/v1/demo/templates")
async def list_templates_simple():
    return {
        "status": "success",
        "data": [
            {
                "id": "template-001",
                "name": "Welcome Template",
                "content": "Welcome to our hotel!",
                "type": "greeting",
                "is_active": True
            }
        ]
    }

@app.get("/api/v1/demo/sentiment-analytics")
async def get_sentiment_analytics_simple():
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
    return {
        "status": "success",
        "data": [
            {
                "id": "user-001",
                "username": "admin",
                "email": "admin@hotel.com",
                "role": "administrator",
                "is_active": True
            }
        ]
    }

@app.get("/api/v1/demo/analytics")
async def get_analytics_simple():
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
    return {
        "status": "success",
        "data": {
            "failed_login_attempts": 3,
            "active_sessions": 12,
            "security_alerts": 0,
            "last_security_scan": "2025-07-19T08:00:00Z"
        }
    }

# Health endpoint
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "whatsapp-hotel-bot", "version": "1.0.0"}

# Missing endpoints that the template expects
@app.get("/api/v1/hotels")
async def list_hotels_old_path():
    """Old path for hotels - redirect to demo"""
    return await list_hotels_simple()

@app.get("/api/v1/sentiment-analytics/alerts")
async def get_sentiment_alerts():
    return {
        "status": "success",
        "data": {
            "alerts": [
                {
                    "id": "alert-001",
                    "type": "negative_sentiment",
                    "message": "High negative sentiment detected in Hotel A",
                    "severity": "medium",
                    "created_at": "2025-07-19T10:00:00Z"
                }
            ]
        }
    }

@app.get("/api/v1/admin/settings")
async def get_admin_settings(category: str = None):
    if category == "deepseek":
        return {
            "status": "success",
            "data": {
                "settings": {
                    "api_key": "sk-****",
                    "model": "deepseek-chat",
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            }
        }
    return {
        "status": "success",
        "data": {
            "settings": {}
        }
    }

@app.get("/api/v1/triggers/{trigger_id}")
async def get_trigger(trigger_id: str):
    return {
        "status": "success",
        "data": {
            "id": trigger_id,
            "name": "Welcome Message",
            "type": "first_message",
            "is_active": True,
            "hotel_id": "550e8400-e29b-41d4-a716-446655440001",
            "content": "Welcome to our hotel!"
        }
    }

@app.get("/api/v1/admin/dashboard/data")
async def admin_dashboard_data():
    return {
        "status": "success",
        "data": {
            "message": "Admin dashboard ready",
            "features": ["user-management", "analytics", "monitoring", "security"]
        }
    }

# Serve the original admin dashboard template
@app.get("/api/v1/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    try:
        # Read the original template file
        template_path = "../hotel-boost/app/templates/admin_dashboard.html"
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return HTMLResponse(content)
        else:
            return HTMLResponse("<h1>Template not found</h1><p>Could not find admin_dashboard.html</p>")
    except Exception as e:
        return HTMLResponse(f"<h1>Error loading template</h1><p>{e}</p>")

@app.get("/")
async def root():
    return {"message": "Isolated server with original admin dashboard!", "status": "ok"}

if __name__ == "__main__":
    print("🚀 Starting isolated server with original admin dashboard...")
    print("📍 Server will be available at: http://localhost:8002")
    print("📊 Admin Dashboard: http://localhost:8002/api/v1/admin/dashboard")
    print("🔗 Demo Hotels API: http://localhost:8002/api/v1/demo/hotels")
    print("-" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
