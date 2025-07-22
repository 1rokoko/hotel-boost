#!/usr/bin/env python3
"""
Minimal test server for hotel-boost functionality testing
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI(title="Hotel Boost Test Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock data
mock_hotels = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Grand Plaza Hotel",
        "whatsapp_number": "+1234567890",
        "green_api_instance_id": "instance123",
        "green_api_token": "token123",
        "is_active": True,
        "settings": {
            "deepseek": {
                "api_key": "sk-test123",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "travel_memory": "PHUKET - FIRST TIME:\n- Patong Beach for nightlife\n- Kata Beach for families\n- Big Buddha - must visit"
            }
        }
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "Ocean View Resort",
        "whatsapp_number": "+1234567891",
        "green_api_instance_id": "instance456",
        "green_api_token": "token456",
        "is_active": True,
        "settings": {
            "deepseek": {
                "api_key": "sk-test456",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "travel_memory": "PHUKET - COUPLES:\n- Romantic sunset at Promthep Cape\n- Couples spa at luxury resorts\n- Private beach dinners"
            }
        }
    }
]

mock_triggers = [
    {
        "id": "trigger-001",
        "name": "Welcome Message - Immediate",
        "trigger_type": "event_based",
        "conditions": {"event_type": "first_message_received", "delay_seconds": 0},
        "message_template": "🏨 Welcome to {{ hotel_name }}! We're delighted to have you as our guest.",
        "is_active": True,
        "priority": 1
    },
    {
        "id": "trigger-002", 
        "name": "Quick Response - 30 seconds",
        "trigger_type": "time_based",
        "conditions": {"schedule_type": "seconds_after_first_message", "delay_seconds": 30},
        "message_template": "Thank you for contacting {{ hotel_name }}! I'm processing your message.",
        "is_active": True,
        "priority": 2
    }
]

# Pydantic models
class HotelCreate(BaseModel):
    name: str
    whatsapp_number: str
    green_api_instance_id: str
    green_api_token: str
    deepseek_api_key: Optional[str] = None

class DeepSeekSettings(BaseModel):
    enabled: bool = True
    api_key: str
    model: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60
    max_requests_per_minute: int = 50
    max_tokens_per_minute: int = 100000
    max_retries: int = 3
    travel_memory: str = ""

# Routes
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/v1/hotels")
async def get_hotels():
    return {
        "status": "success",
        "data": mock_hotels,
        "total": len(mock_hotels)
    }

@app.post("/api/v1/hotels")
async def create_hotel(hotel_data: HotelCreate):
    new_hotel = {
        "id": str(uuid.uuid4()),
        "name": hotel_data.name,
        "whatsapp_number": hotel_data.whatsapp_number,
        "green_api_instance_id": hotel_data.green_api_instance_id,
        "green_api_token": hotel_data.green_api_token,
        "is_active": True,
        "settings": {
            "deepseek": {
                "api_key": hotel_data.deepseek_api_key or "",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "travel_memory": ""
            }
        }
    }
    mock_hotels.append(new_hotel)
    return {"status": "success", "data": new_hotel}

@app.get("/api/v1/hotels/{hotel_id}")
async def get_hotel(hotel_id: str):
    hotel = next((h for h in mock_hotels if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel

@app.put("/api/v1/hotels/{hotel_id}/deepseek")
async def update_hotel_deepseek(hotel_id: str, settings: DeepSeekSettings):
    hotel = next((h for h in mock_hotels if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    hotel["settings"]["deepseek"] = settings.dict()
    return {"status": "success", "message": "DeepSeek settings updated"}

@app.post("/api/v1/hotels/{hotel_id}/deepseek/test")
async def test_hotel_deepseek(hotel_id: str):
    hotel = next((h for h in mock_hotels if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    return {"success": True, "message": "DeepSeek connection test successful"}

@app.get("/api/v1/triggers")
async def get_triggers():
    return {
        "status": "success",
        "data": mock_triggers,
        "total": len(mock_triggers)
    }

@app.post("/api/v1/hotels/{hotel_id}/triggers/templates")
async def create_triggers_from_templates(hotel_id: str):
    # Simulate creating triggers from templates
    new_triggers = [
        {"id": f"trigger-{uuid.uuid4()}", "name": "Welcome Message", "created": True},
        {"id": f"trigger-{uuid.uuid4()}", "name": "Quick Response", "created": True},
        {"id": f"trigger-{uuid.uuid4()}", "name": "Check-in Welcome", "created": True},
        {"id": f"trigger-{uuid.uuid4()}", "name": "Review Request", "created": True}
    ]
    
    return {
        "status": "success",
        "message": f"Created {len(new_triggers)} trigger templates",
        "triggers": new_triggers
    }

@app.post("/api/v1/demo/sentiment-analytics")
async def analyze_sentiment():
    return {
        "sentiment": "NEGATIVE",
        "confidence": 0.62,
        "emotion": "Frustrated",
        "urgency": "High"
    }

@app.post("/api/v1/demo/generate-response")
async def generate_response():
    return {
        "content": "Thank you for contacting us about your booking. I'd be happy to help you with any questions or changes you need. Could you please provide your booking reference number?",
        "generated_in": "1.2s",
        "language": "English",
        "temperature": 0.7
    }

@app.get("/api/v1/admin/dashboard")
async def admin_dashboard():
    # Serve the admin dashboard HTML
    try:
        with open("app/templates/admin_dashboard.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Admin Dashboard</h1><p>Dashboard template not found</p>")

if __name__ == "__main__":
    print("🚀 Starting Hotel Boost Test Server on http://localhost:8002")
    print("📊 Mock data loaded:")
    print(f"   - {len(mock_hotels)} hotels")
    print(f"   - {len(mock_triggers)} triggers")
    print("🔧 Available endpoints:")
    print("   - GET  /health")
    print("   - GET  /api/v1/hotels")
    print("   - POST /api/v1/hotels")
    print("   - GET  /api/v1/triggers")
    print("   - GET  /api/v1/admin/dashboard")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
