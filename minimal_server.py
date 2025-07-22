from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

# Demo endpoints
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

@app.get("/api/v1/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})

@app.get("/api/v1/admin/dashboard/data")
async def admin_dashboard_data():
    return {
        "status": "success",
        "data": {
            "message": "Admin dashboard ready",
            "features": ["user-management", "analytics", "monitoring", "security"]
        }
    }

@app.get("/")
async def root():
    return {"message": "Minimal server is working!", "status": "ok"}

if __name__ == "__main__":
    print("🚀 Starting minimal server...")
    print("📍 Server will be available at: http://localhost:8002")
    print("📊 Admin Dashboard: http://localhost:8002/api/v1/admin/dashboard")
    print("-" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
