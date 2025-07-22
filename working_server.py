#!/usr/bin/env python3
"""
Working server for hotel-boost project testing
"""

import sys
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi import FastAPI, HTTPException, Depends
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("💡 Installing required packages...")
    os.system("pip install fastapi uvicorn pydantic")
    sys.exit(1)

# Initialize FastAPI app
app = FastAPI(
    title="Hotel Boost Working Server",
    description="Working server for testing hotel-boost functionality",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock data storage
mock_data = {
    "hotels": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "name": "Grand Plaza Hotel",
            "whatsapp_number": "+1234567890",
            "green_api_instance_id": "instance123",
            "green_api_token": "token123",
            "is_active": True,
            "settings": {
                "deepseek": {
                    "enabled": True,
                    "api_key": "sk-test123",
                    "model": "deepseek-chat",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "timeout": 60,
                    "max_requests_per_minute": 50,
                    "max_tokens_per_minute": 100000,
                    "max_retries": 3,
                    "travel_memory": "PHUKET TRAVEL ADVISORY:\n\nFIRST TIME VISITORS:\n- Patong Beach: Vibrant nightlife, restaurants, shopping\n- Kata Beach: Family-friendly, calmer waters\n- Big Buddha: Must-visit cultural landmark\n- Old Phuket Town: Historic architecture, local markets\n\nCOUPLES & ROMANTIC:\n- Promthep Cape: Stunning sunset views\n- Phi Phi Islands: Day trip for snorkeling\n- Luxury spa treatments at resort\n- Private beach dinners\n\nFAMILIES:\n- Phuket Aquarium: Educational and fun\n- Elephant sanctuaries: Ethical wildlife experience\n- Water parks: Splash Jungle, Blue Tree\n- Cable car rides: Scenic mountain views"
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
                    "enabled": True,
                    "api_key": "sk-test456",
                    "model": "deepseek-chat",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "timeout": 60,
                    "max_requests_per_minute": 50,
                    "max_tokens_per_minute": 100000,
                    "max_retries": 3,
                    "travel_memory": "PHUKET LUXURY EXPERIENCES:\n\nVIP SERVICES:\n- Private yacht charters\n- Helicopter tours\n- Personal shopping assistants\n- Michelin-starred dining\n\nEXCLUSIVE LOCATIONS:\n- Private beach clubs\n- Rooftop bars with panoramic views\n- Hidden local gems\n- Exclusive spa treatments"
                }
            }
        }
    ],
    "triggers": [
        {
            "id": "trigger-001",
            "name": "Welcome Message - Immediate",
            "trigger_type": "event_based",
            "conditions": {"event_type": "first_message_received", "delay_seconds": 0},
            "message_template": "🏨 Welcome to {{ hotel_name }}! We're delighted to have you as our guest. How can I assist you today?",
            "is_active": True,
            "priority": 1,
            "hotel_id": "550e8400-e29b-41d4-a716-446655440001"
        },
        {
            "id": "trigger-002",
            "name": "Quick Response - 30 seconds",
            "trigger_type": "time_based",
            "conditions": {"schedule_type": "seconds_after_first_message", "delay_seconds": 30},
            "message_template": "Thank you for contacting {{ hotel_name }}! I'm processing your message and will respond shortly.",
            "is_active": True,
            "priority": 2,
            "hotel_id": "550e8400-e29b-41d4-a716-446655440001"
        },
        {
            "id": "trigger-003",
            "name": "Check-in Day Welcome",
            "trigger_type": "event_based",
            "conditions": {"event_type": "check_in_day", "delay_minutes": 60},
            "message_template": "🎉 Welcome to {{ hotel_name }}! Your room is ready. Need directions or have any questions?",
            "is_active": True,
            "priority": 3,
            "hotel_id": "550e8400-e29b-41d4-a716-446655440001"
        },
        {
            "id": "trigger-004",
            "name": "Mid-Stay Check-in",
            "trigger_type": "time_based",
            "conditions": {"schedule_type": "hours_after_checkin", "delay_hours": 24},
            "message_template": "Hi! How is your stay at {{ hotel_name }} so far? Is there anything we can do to make it even better?",
            "is_active": True,
            "priority": 4,
            "hotel_id": "550e8400-e29b-41d4-a716-446655440001"
        }
    ]
}

# Pydantic models
class HotelCreate(BaseModel):
    name: str
    whatsapp_number: str
    green_api_instance_id: str
    green_api_token: str
    deepseek_api_key: Optional[str] = None

class HotelUpdate(BaseModel):
    name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    green_api_instance_id: Optional[str] = None
    green_api_token: Optional[str] = None
    is_active: Optional[bool] = None

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
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "server": "working_server",
        "version": "1.0.0"
    }

@app.get("/api/v1/hotels")
async def get_hotels():
    return {
        "status": "success",
        "data": mock_data["hotels"],
        "total": len(mock_data["hotels"])
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
                "enabled": True,
                "api_key": hotel_data.deepseek_api_key or "",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout": 60,
                "max_requests_per_minute": 50,
                "max_tokens_per_minute": 100000,
                "max_retries": 3,
                "travel_memory": ""
            }
        }
    }
    mock_data["hotels"].append(new_hotel)
    return {"status": "success", "data": new_hotel}

@app.get("/api/v1/hotels/{hotel_id}")
async def get_hotel(hotel_id: str):
    hotel = next((h for h in mock_data["hotels"] if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return {"status": "success", "data": hotel}

@app.put("/api/v1/hotels/{hotel_id}")
async def update_hotel(hotel_id: str, hotel_data: HotelUpdate):
    hotel = next((h for h in mock_data["hotels"] if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    # Update hotel fields
    for field, value in hotel_data.dict(exclude_unset=True).items():
        hotel[field] = value
    
    return {"status": "success", "data": hotel, "message": "Hotel updated successfully"}

@app.get("/api/v1/hotels/{hotel_id}/deepseek")
async def get_hotel_deepseek_settings(hotel_id: str):
    hotel = next((h for h in mock_data["hotels"] if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    return {
        "status": "success",
        "data": hotel["settings"]["deepseek"]
    }

@app.put("/api/v1/hotels/{hotel_id}/deepseek")
async def update_hotel_deepseek_settings(hotel_id: str, settings: DeepSeekSettings):
    hotel = next((h for h in mock_data["hotels"] if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    hotel["settings"]["deepseek"] = settings.dict()
    return {"status": "success", "message": "DeepSeek settings updated successfully"}

@app.post("/api/v1/hotels/{hotel_id}/deepseek/test")
async def test_hotel_deepseek_connection(hotel_id: str):
    hotel = next((h for h in mock_data["hotels"] if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    return {
        "success": True,
        "message": "DeepSeek connection test successful",
        "api_key_status": "valid",
        "response_time": "1.2s"
    }

@app.get("/api/v1/triggers")
async def get_triggers():
    return {
        "status": "success",
        "data": mock_data["triggers"],
        "total": len(mock_data["triggers"])
    }

@app.post("/api/v1/hotels/{hotel_id}/triggers/templates")
async def create_triggers_from_templates(hotel_id: str):
    hotel = next((h for h in mock_data["hotels"] if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    # Create new triggers from templates
    new_triggers = [
        {
            "id": str(uuid.uuid4()),
            "name": "Welcome Message - Immediate",
            "trigger_type": "event_based",
            "conditions": {"event_type": "first_message_received", "delay_seconds": 0},
            "message_template": f"🏨 Welcome to {hotel['name']}! We're delighted to have you as our guest.",
            "is_active": True,
            "priority": 1,
            "hotel_id": hotel_id,
            "created": True
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Quick Response - 30 seconds",
            "trigger_type": "time_based",
            "conditions": {"schedule_type": "seconds_after_first_message", "delay_seconds": 30},
            "message_template": f"Thank you for contacting {hotel['name']}! I'm processing your message.",
            "is_active": True,
            "priority": 2,
            "hotel_id": hotel_id,
            "created": True
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Pre-Checkout Satisfaction Check",
            "trigger_type": "time_based",
            "conditions": {"schedule_type": "hours_before_checkout", "delay_hours": 2},
            "message_template": f"We hope you enjoyed your stay at {hotel['name']}! How was everything?",
            "is_active": True,
            "priority": 3,
            "hotel_id": hotel_id,
            "created": True
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Post-Stay Review Request",
            "trigger_type": "time_based",
            "conditions": {"schedule_type": "hours_after_checkout", "delay_hours": 24},
            "message_template": f"Thank you for staying with {hotel['name']}! We'd love your feedback.",
            "is_active": True,
            "priority": 4,
            "hotel_id": hotel_id,
            "created": True
        }
    ]
    
    # Add to mock data
    mock_data["triggers"].extend(new_triggers)
    
    return {
        "status": "success",
        "message": f"Created {len(new_triggers)} trigger templates for {hotel['name']}",
        "triggers": new_triggers
    }

@app.post("/api/v1/demo/sentiment-analytics")
async def analyze_sentiment():
    return {
        "sentiment": "NEGATIVE",
        "confidence": 0.62,
        "emotion": "Frustrated",
        "urgency": "High",
        "processing_time": "0.8s"
    }

@app.post("/api/v1/demo/generate-response")
async def generate_response():
    return {
        "content": "Thank you for contacting us about your booking. I'd be happy to help you with any questions or changes you need. Could you please provide your booking reference number?",
        "generated_in": "1.2s",
        "language": "English",
        "temperature": 0.7,
        "model": "deepseek-chat"
    }

@app.get("/api/v1/admin/dashboard")
async def admin_dashboard():
    # Try to serve the actual dashboard HTML
    try:
        with open("app/templates/admin_dashboard.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        # Return a simple dashboard if file not found
        dashboard_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Hotel Boost Admin Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .container { max-width: 1200px; margin: 0 auto; }
                .card { border: 1px solid #ddd; padding: 20px; margin: 10px 0; border-radius: 5px; }
                .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
                .btn:hover { background: #0056b3; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏨 Hotel Boost Admin Dashboard</h1>
                <div class="card">
                    <h2>Server Status</h2>
                    <p>✅ Working Server is running successfully!</p>
                    <p>📊 Mock data loaded: """ + str(len(mock_data["hotels"])) + """ hotels, """ + str(len(mock_data["triggers"])) + """ triggers</p>
                </div>
                <div class="card">
                    <h2>Available Features</h2>
                    <ul>
                        <li>✅ Hotel Management (Create, Read, Update)</li>
                        <li>✅ Hotel-specific DeepSeek Settings</li>
                        <li>✅ Travel Advisory Memory</li>
                        <li>✅ Trigger Templates</li>
                        <li>✅ AI Testing (Sentiment Analysis, Response Generation)</li>
                    </ul>
                </div>
                <div class="card">
                    <h2>Test Actions</h2>
                    <button class="btn" onclick="testAPI()">Test API Endpoints</button>
                    <button class="btn" onclick="createHotel()">Create Test Hotel</button>
                    <button class="btn" onclick="createTriggers()">Create Triggers</button>
                </div>
            </div>
            <script>
                function testAPI() {
                    fetch('/api/v1/hotels')
                        .then(r => r.json())
                        .then(data => alert('Hotels loaded: ' + data.total));
                }
                function createHotel() {
                    fetch('/api/v1/hotels', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            name: 'Test Hotel ' + Date.now(),
                            whatsapp_number: '+1234567890',
                            green_api_instance_id: 'test123',
                            green_api_token: 'token123',
                            deepseek_api_key: 'sk-test123'
                        })
                    })
                    .then(r => r.json())
                    .then(data => alert('Hotel created: ' + data.data.name));
                }
                function createTriggers() {
                    const hotelId = '550e8400-e29b-41d4-a716-446655440001';
                    fetch('/api/v1/hotels/' + hotelId + '/triggers/templates', {method: 'POST'})
                        .then(r => r.json())
                        .then(data => alert(data.message));
                }
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=dashboard_html)

if __name__ == "__main__":
    print("🚀 Starting Hotel Boost Working Server...")
    print(f"📊 Mock data loaded:")
    print(f"   - {len(mock_data['hotels'])} hotels")
    print(f"   - {len(mock_data['triggers'])} triggers")
    print("🌐 Server will be available at: http://localhost:8002")
    print("📖 API docs at: http://localhost:8002/docs")
    print("🎛️ Admin dashboard at: http://localhost:8002/api/v1/admin/dashboard")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )
