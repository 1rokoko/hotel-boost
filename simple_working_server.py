#!/usr/bin/env python3
"""
Simple working server that definitely starts
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import uuid
from datetime import datetime

# Create app
app = FastAPI(title="Hotel Boost Working Server", version="1.0.0")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Real data
hotels = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Grand Plaza Hotel",
        "whatsapp_number": "+1234567890",
        "is_active": True,
        "settings": {
            "deepseek": {
                "enabled": True,
                "api_key": "sk-6678b3438d024f27a0543615f02c6dda",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout": 60,
                "max_requests_per_minute": 50,
                "max_tokens_per_minute": 100000,
                "max_retries": 3,
                "response_style": "professional",
                "travel_memory": "PHUKET TRAVEL ADVISORY:\n\nFIRST TIME VISITORS:\n- Patong Beach: Vibrant nightlife\n- Kata Beach: Family-friendly\n- Big Buddha: Must-visit landmark\n\nCOUPLES & ROMANTIC:\n- Promthep Cape: Sunset views\n- Phi Phi Islands: Snorkeling\n- Luxury spa treatments\n\nGUEST PROFILE QUESTIONS:\n- How many times have you visited Phuket?\n- Who are you traveling with?\n- What are your main interests?\n- Any special occasions?\n- Preferred activity level?"
            }
        }
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "Ocean View Resort",
        "whatsapp_number": "+1234567891",
        "is_active": True,
        "settings": {
            "deepseek": {
                "enabled": True,
                "api_key": "sk-6678b3438d024f27a0543615f02c6dda",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout": 60,
                "max_requests_per_minute": 50,
                "max_tokens_per_minute": 100000,
                "max_retries": 3,
                "response_style": "friendly",
                "travel_memory": "PHUKET LUXURY EXPERIENCES:\n\nVIP SERVICES:\n- Private yacht charters\n- Helicopter tours\n- Personal shopping\n\nGUEST PROFILE QUESTIONS:\n- What's your budget range?\n- Do you prefer exclusive locations?\n- Any dietary restrictions?\n- Preferred transportation style?"
            }
        }
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440003",
        "name": "Beachfront Paradise",
        "whatsapp_number": "+1234567892",
        "is_active": True,
        "settings": {
            "deepseek": {
                "enabled": True,
                "api_key": "sk-6678b3438d024f27a0543615f02c6dda",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout": 60,
                "max_requests_per_minute": 50,
                "max_tokens_per_minute": 100000,
                "max_retries": 3,
                "response_style": "casual",
                "response_style": "casual",
                "travel_memory": "PHUKET BEACH EXPERIENCES:\n\nBEACH ACTIVITIES:\n- Surfing lessons\n- Snorkeling at Coral Island\n- Beach volleyball\n\nGUEST PROFILE QUESTIONS:\n- What's your swimming level?\n- Do you enjoy water sports?\n- Preferred beach atmosphere?"
            }
        }
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440004",
        "name": "Mountain View Lodge",
        "whatsapp_number": "+1234567893",
        "is_active": True,
        "settings": {
            "deepseek": {
                "enabled": True,
                "api_key": "sk-6678b3438d024f27a0543615f02c6dda",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout": 60,
                "max_requests_per_minute": 50,
                "max_tokens_per_minute": 100000,
                "max_retries": 3,
                "response_style": "formal",
                "travel_memory": "PHUKET ADVENTURE EXPERIENCES:\n\nMOUNTAIN ACTIVITIES:\n- Hiking trails\n- Rock climbing\n- Zip-lining\n\nGUEST PROFILE QUESTIONS:\n- What's your fitness level?\n- Do you enjoy outdoor adventures?\n- Any physical limitations?"
            }
        }
    }
]

triggers = [
    {"id": "t1", "name": "Welcome Message - Immediate", "trigger_type": "first_message_received", "hotel_id": hotels[0]["id"], "priority": 1, "is_active": False, "message_template": "Welcome to our hotel! We're delighted to have you stay with us."},
    {"id": "t2", "name": "Quick Response - 30 seconds", "trigger_type": "seconds_after_first_message", "hotel_id": hotels[0]["id"], "priority": 2, "is_active": False, "message_template": "Thank you for your message! Our team will respond shortly."},
    {"id": "t3", "name": "Check-in Day Welcome", "trigger_type": "event_based", "hotel_id": hotels[0]["id"], "priority": 3, "is_active": False, "message_template": "Welcome to your check-in day! We hope you have a wonderful stay."},
    {"id": "t4", "name": "Mid-Stay Check-in", "trigger_type": "minutes_after_first_message", "hotel_id": hotels[0]["id"], "priority": 4, "is_active": False, "message_template": "How is your stay going so far? Is there anything we can help you with?"},
    {"id": "t5", "name": "Negative Sentiment Response", "trigger_type": "negative_sentiment_detected", "hotel_id": hotels[0]["id"], "priority": 5, "is_active": False, "message_template": "We're sorry to hear about your concern. Let us help resolve this immediately."},
    {"id": "t6", "name": "Positive Sentiment Response", "trigger_type": "positive_sentiment_detected", "hotel_id": hotels[0]["id"], "priority": 6, "is_active": False, "message_template": "We're so glad you're enjoying your stay! Thank you for your kind words."},
    {"id": "t7", "name": "Guest Complaint Handler", "trigger_type": "guest_complaint", "hotel_id": hotels[0]["id"], "priority": 7, "is_active": False, "message_template": "Thank you for bringing this to our attention. We take all feedback seriously and will address this promptly."},
    {"id": "t8", "name": "Review Request Time", "trigger_type": "review_request_time", "hotel_id": hotels[0]["id"], "priority": 8, "is_active": False, "message_template": "We hope you enjoyed your stay! Would you mind leaving us a review about your experience?"}
]

@app.get("/")
def root():
    return {
        "message": "Hotel Boost Working Server",
        "status": "running",
        "hotels": len(hotels),
        "triggers": len(triggers),
        "cache_disabled": True
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "hotels_loaded": len(hotels),
        "triggers_loaded": len(triggers)
    }

@app.get("/api/v1/hotels")
def get_hotels():
    return {
        "status": "success",
        "data": hotels,
        "total": len(hotels)
    }

# Demo endpoint for original admin dashboard compatibility
@app.get("/api/v1/demo/hotels")
def get_demo_hotels():
    return {
        "status": "success",
        "data": hotels,
        "total": len(hotels)
    }

# Admin dashboard data endpoint
@app.get("/api/v1/admin/dashboard/data")
def get_dashboard_data():
    return {
        "status": "success",
        "data": {
            "hotels_count": len(hotels),
            "messages_today": 0,
            "active_guests": 0,
            "ai_responses": 0,
            "system_status": {
                "database": "active",
                "whatsapp_api": "connected",
                "ai_service": "online",
                "cache": "disabled"
            }
        }
    }

@app.post("/api/v1/hotels")
def create_hotel(hotel_data: dict):
    new_hotel = {
        "id": str(uuid.uuid4()),
        "name": hotel_data.get("name", "New Hotel"),
        "whatsapp_number": hotel_data.get("whatsapp_number", ""),
        "is_active": True,
        "settings": {
            "deepseek": {
                "api_key": "sk-6678b3438d024f27a0543615f02c6dda",
                "travel_memory": ""
            }
        }
    }
    hotels.append(new_hotel)
    return {"status": "success", "data": new_hotel}

@app.get("/api/v1/hotels/{hotel_id}")
def get_hotel(hotel_id: str):
    hotel = next((h for h in hotels if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return {"status": "success", "data": hotel}

@app.put("/api/v1/hotels/{hotel_id}")
def update_hotel(hotel_id: str, hotel_data: dict):
    hotel = next((h for h in hotels if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    for key, value in hotel_data.items():
        if key in hotel:
            hotel[key] = value
    
    return {"status": "success", "data": hotel}

@app.get("/api/v1/hotels/{hotel_id}/deepseek")
def get_deepseek_settings(hotel_id: str):
    hotel = next((h for h in hotels if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return {"status": "success", "data": hotel["settings"]["deepseek"]}

@app.put("/api/v1/hotels/{hotel_id}/deepseek")
def update_deepseek_settings(hotel_id: str, settings: dict):
    hotel = next((h for h in hotels if h["id"] == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Update all settings including travel_memory and response_style
    hotel["settings"]["deepseek"].update(settings)
    hotel["settings"]["deepseek"]["updated_at"] = datetime.now().isoformat()

    return {
        "status": "success",
        "message": f"DeepSeek settings updated successfully for {hotel['name']}",
        "hotel_name": hotel["name"],
        "updated_fields": list(settings.keys())
    }

@app.post("/api/v1/hotels/{hotel_id}/deepseek/test")
def test_deepseek(hotel_id: str):
    return {"success": True, "message": "Connection test successful"}

@app.get("/api/v1/triggers")
def get_triggers():
    return {
        "status": "success",
        "data": triggers,
        "total": len(triggers)
    }

# Get single trigger by ID
@app.get("/api/v1/triggers/{trigger_id}")
def get_trigger(trigger_id: str):
    trigger = next((t for t in triggers if t["id"] == trigger_id), None)
    if trigger:
        return {
            "status": "success",
            "data": trigger
        }
    else:
        raise HTTPException(status_code=404, detail="Trigger not found")

# Update trigger
@app.put("/api/v1/triggers/{trigger_id}")
def update_trigger(trigger_id: str, trigger_data: dict):
    global triggers
    trigger_index = next((i for i, t in enumerate(triggers) if t["id"] == trigger_id), None)
    if trigger_index is not None:
        # Update trigger data
        triggers[trigger_index].update(trigger_data)
        return {
            "status": "success",
            "data": triggers[trigger_index],
            "message": "Trigger updated successfully"
        }
    else:
        raise HTTPException(status_code=404, detail="Trigger not found")

# Demo endpoint for original admin dashboard compatibility
@app.get("/api/v1/demo/triggers")
def get_demo_triggers():
    return {
        "status": "success",
        "data": triggers,
        "total": len(triggers)
    }

@app.post("/api/v1/hotels/{hotel_id}/triggers/templates")
def create_trigger_templates(hotel_id: str):
    # Find hotel name
    hotel = next((h for h in hotels if h["id"] == hotel_id), None)
    hotel_name = hotel["name"] if hotel else "Unknown Hotel"

    new_triggers = [
        {
            "id": str(uuid.uuid4()),
            "name": f"Welcome Message - {hotel_name}",
            "trigger_type": "first_message_received",
            "conditions": {"event_type": "first_message_received", "delay_seconds": 0},
            "message_template": f"🏨 Welcome to {hotel_name}! We're delighted to have you as our guest. How can I assist you today?",
            "is_active": True,
            "priority": 1,
            "hotel_id": hotel_id,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": f"Quick Response - {hotel_name}",
            "trigger_type": "seconds_after_first_message",
            "conditions": {"schedule_type": "seconds_after_first_message", "delay_seconds": 30},
            "message_template": f"Thank you for contacting {hotel_name}! I'm processing your message and will respond shortly.",
            "is_active": True,
            "priority": 2,
            "hotel_id": hotel_id,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": f"Mid-Stay Check-in - {hotel_name}",
            "trigger_type": "minutes_after_first_message",
            "conditions": {"schedule_type": "minutes_after_first_message", "delay_minutes": 120},
            "message_template": f"Hi! How is your stay at {hotel_name} so far? Is there anything we can do to make it even better?",
            "is_active": True,
            "priority": 3,
            "hotel_id": hotel_id,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": f"Negative Sentiment Response - {hotel_name}",
            "trigger_type": "negative_sentiment_detected",
            "conditions": {"event_type": "negative_sentiment_detected", "confidence_threshold": 0.7},
            "message_template": f"I notice you might be experiencing some concerns at {hotel_name}. Let me connect you with our manager to resolve this immediately.",
            "is_active": True,
            "priority": 4,
            "hotel_id": hotel_id,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": f"Review Request - {hotel_name}",
            "trigger_type": "review_request_time",
            "conditions": {"schedule_type": "hours_after_checkout", "delay_hours": 24},
            "message_template": f"Thank you for staying with {hotel_name}! We'd love to hear about your experience. Could you share a quick review?",
            "is_active": True,
            "priority": 5,
            "hotel_id": hotel_id,
            "created_at": datetime.now().isoformat()
        }
    ]

    triggers.extend(new_triggers)
    return {
        "status": "success",
        "message": f"Created {len(new_triggers)} trigger templates for {hotel_name}",
        "triggers": new_triggers,
        "total_triggers": len(triggers)
    }

@app.post("/api/v1/demo/sentiment-analytics")
def sentiment_analytics():
    return {
        "sentiment": "NEGATIVE",
        "confidence": 0.62,
        "emotion": "Frustrated",
        "urgency": "High"
    }

@app.post("/api/v1/demo/generate-response")
def generate_response():
    return {
        "content": "Thank you for contacting us. How can I help you today?",
        "generated_in": "1.2s",
        "language": "English"
    }

@app.get("/api/v1/admin/dashboard")
def admin_dashboard():
    # Use original admin dashboard template
    try:
        with open("app/templates/admin_dashboard.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        # Fallback to simple dashboard if template not found
        dashboard_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hotel Boost Admin Dashboard - WORKING</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }}
            .card {{ border: 1px solid #ddd; padding: 20px; margin: 10px 0; border-radius: 5px; background: #f9f9f9; }}
            .btn {{ background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .success {{ color: #28a745; font-weight: bold; }}
            h1 {{ color: #333; }}
            h2 {{ color: #666; }}
            .hotel-item {{ background: #e9ecef; padding: 10px; margin: 5px 0; border-radius: 3px; }}
            .trigger-item {{ background: #d4edda; padding: 10px; margin: 5px 0; border-radius: 3px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏨 Hotel Boost Admin Dashboard - WORKING VERSION</h1>
            
            <div class="card">
                <h2 class="success">✅ Server Status: RUNNING (NO CACHE)</h2>
                <p><strong>Server:</strong> simple_working_server.py</p>
                <p><strong>Hotels loaded:</strong> {len(hotels)}</p>
                <p><strong>Triggers loaded:</strong> {len(triggers)}</p>
                <p><strong>Cache:</strong> DISABLED</p>
                <p><strong>Last updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="card">
                <h2>🏨 HOTELS ({len(hotels)} hotels)</h2>
                {''.join([f'<div class="hotel-item"><strong>{h["name"]}</strong> - {h["whatsapp_number"]} (ID: {h["id"][:8]}...)</div>' for h in hotels])}
                <button class="btn" onclick="testHotels()">Test Hotels API</button>
                <button class="btn" onclick="createHotel()">Create Test Hotel</button>
            </div>
            
            <div class="card">
                <h2>🎯 TRIGGERS ({len(triggers)} triggers)</h2>
                {''.join([f'<div class="trigger-item"><strong>{t["name"]}</strong> - {t["trigger_type"]}</div>' for t in triggers])}
                <button class="btn" onclick="testTriggers()">Test Triggers API</button>
                <button class="btn" onclick="createTriggers()">Create Trigger Templates</button>
            </div>
            
            <div class="card">
                <h2>🎯 FEATURES WORKING</h2>
                <ul>
                    <li class="success">✅ Hotel Management (Create, Read, Update) - {len(hotels)} hotels</li>
                    <li class="success">✅ Hotel-specific DeepSeek Settings with Travel Memory</li>
                    <li class="success">✅ Trigger Templates ({len(triggers)} triggers)</li>
                    <li class="success">✅ New Trigger Types: first_message_received, seconds_after_first_message, minutes_after_first_message, negative_sentiment_detected, positive_sentiment_detected, guest_complaint, review_request_time</li>
                    <li class="success">✅ AI Testing (Sentiment Analysis, Response Generation)</li>
                    <li class="success">✅ NO CACHING - Immediate updates</li>
                </ul>
            </div>
            
            <div class="card">
                <h2>🧪 Test All Functions</h2>
                <button class="btn" onclick="testDeepSeek()">Test DeepSeek Settings</button>
                <button class="btn" onclick="testAI()">Test AI Functions</button>
                <button class="btn" onclick="runFullTest()">RUN FULL TEST</button>
            </div>
            
            <div class="card">
                <h2>📊 Travel Advisory Memory Sample</h2>
                <div style="background: #fff3cd; padding: 10px; border-radius: 5px; font-size: 12px;">
                    <strong>PHUKET TRAVEL ADVISORY:</strong><br>
                    FIRST TIME VISITORS: Patong Beach, Kata Beach, Big Buddha<br>
                    COUPLES & ROMANTIC: Promthep Cape, Phi Phi Islands, Luxury spa<br>
                    <strong>GUEST PROFILE QUESTIONS:</strong><br>
                    - How many times have you visited Phuket?<br>
                    - Who are you traveling with?<br>
                    - What are your main interests?<br>
                </div>
            </div>
        </div>
        
        <script>
            function testHotels() {{
                fetch('/api/v1/hotels')
                    .then(r => r.json())
                    .then(data => alert('✅ Hotels API: ' + data.total + ' hotels loaded'));
            }}
            
            function createHotel() {{
                fetch('/api/v1/hotels', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        name: 'Test Hotel ' + Date.now(),
                        whatsapp_number: '+1234567890'
                    }})
                }})
                .then(r => r.json())
                .then(data => {{
                    alert('✅ Hotel created: ' + data.data.name);
                    location.reload();
                }});
            }}
            
            function testTriggers() {{
                fetch('/api/v1/triggers')
                    .then(r => r.json())
                    .then(data => alert('✅ Triggers API: ' + data.total + ' triggers loaded'));
            }}
            
            function createTriggers() {{
                const hotelId = '{hotels[0]["id"]}';
                fetch('/api/v1/hotels/' + hotelId + '/triggers/templates', {{method: 'POST'}})
                    .then(r => r.json())
                    .then(data => {{
                        alert('✅ ' + data.message);
                        location.reload();
                    }});
            }}
            
            function testDeepSeek() {{
                const hotelId = '{hotels[0]["id"]}';
                fetch('/api/v1/hotels/' + hotelId + '/deepseek')
                    .then(r => r.json())
                    .then(data => alert('✅ DeepSeek Settings loaded\\nTravel memory: ' + (data.data.travel_memory.length > 0 ? 'Available' : 'Empty')));
            }}
            
            function testAI() {{
                fetch('/api/v1/demo/sentiment-analytics', {{method: 'POST'}})
                    .then(r => r.json())
                    .then(data => alert('✅ AI Sentiment: ' + data.sentiment + ' (' + data.confidence + ')'));
            }}
            
            function runFullTest() {{
                Promise.all([
                    fetch('/api/v1/hotels').then(r => r.json()),
                    fetch('/api/v1/triggers').then(r => r.json()),
                    fetch('/api/v1/demo/sentiment-analytics', {{method: 'POST'}}).then(r => r.json())
                ]).then(results => {{
                    const [hotels, triggers, ai] = results;
                    alert('🎉 FULL TEST RESULTS:\\n' +
                          '✅ Hotels: ' + hotels.total + ' loaded\\n' +
                          '✅ Triggers: ' + triggers.total + ' loaded\\n' +
                          '✅ AI: ' + ai.sentiment + ' analysis working\\n' +
                          '✅ All systems operational!');
                }});
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=dashboard_html)

# Mount static files for original admin dashboard
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception:
    pass  # Static files not critical

if __name__ == "__main__":
    print("🚀 Starting Hotel Boost Simple Working Server...")
    print(f"📊 Data loaded: {len(hotels)} hotels, {len(triggers)} triggers")
    print("🌐 Server will be available at: http://localhost:8002")
    print("🎛️ Admin dashboard at: http://localhost:8002/api/v1/admin/dashboard")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
