#!/usr/bin/env python3
"""
Simple test server for Playwright tests
"""

from fastapi import FastAPI, status, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import uuid
import asyncio
from datetime import datetime

app = FastAPI(
    title="WhatsApp Hotel Bot Test",
    description="Test server for Playwright tests",
    version="1.0.0"
)

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

# Security headers middleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["x-xss-protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "WhatsApp Hotel Bot API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "WhatsApp Hotel Bot",
        "version": "1.0.0",
        "environment": "test",
        "features": {
            "database": "active",
            "cache": "active", 
            "webhooks": "active",
            "ai_integration": "active",
            "performance_optimization": "active"
        }
    }

@app.get("/api/v1/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard HTML interface - using original template"""
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})

@app.get("/api/v1/hotels")
async def list_hotels():
    """List hotels endpoint"""
    return hotels_db

class HotelCreate(BaseModel):
    name: str
    whatsapp_number: str
    green_api_instance_id: str = None
    green_api_token: str = None
    deepseek_api_key: str = None

# In-memory storage for demo
hotels_db = [
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

@app.post("/api/v1/hotels", status_code=status.HTTP_201_CREATED)
async def create_hotel(hotel_data: HotelCreate):
    """Create hotel endpoint"""
    new_hotel = {
        "id": str(uuid.uuid4()),
        "name": hotel_data.name,
        "whatsapp_number": hotel_data.whatsapp_number,
        "is_active": True,
        "has_green_api_credentials": bool(hotel_data.green_api_instance_id and hotel_data.green_api_token),
        "is_operational": bool(hotel_data.green_api_instance_id and hotel_data.green_api_token and hotel_data.deepseek_api_key),
        "created_at": datetime.now().isoformat() + "Z"
    }

    hotels_db.append(new_hotel)
    return new_hotel

@app.get("/api/v1/hotels/{hotel_id}")
async def get_hotel(hotel_id: str):
    """Get hotel by ID endpoint"""
    hotel = next((h for h in hotels_db if h["id"] == hotel_id), None)
    if hotel:
        return hotel
    else:
        raise HTTPException(status_code=404, detail="Hotel not found")

@app.get("/api/v1/admin/dashboard/data")
async def admin_dashboard_data():
    """Admin dashboard data endpoint"""
    return {
        "status": "success",
        "data": {
            "message": "Dashboard data loaded successfully",
            "features": [
                "hotel_management",
                "whatsapp_integration",
                "ai_responses",
                "analytics",
                "monitoring"
            ],
            "stats": {
                "total_hotels": 2,
                "active_hotels": 2,
                "messages_today": 127,
                "response_rate": 98.5
            }
        }
    }

@app.post("/api/v1/webhooks/green-api")
async def green_api_webhook():
    """Green API webhook endpoint"""
    raise HTTPException(status_code=404, detail="Webhook endpoint not implemented")

@app.get("/api/v1/non-existent-endpoint")
async def non_existent():
    """Non-existent endpoint for testing 404"""
    raise HTTPException(status_code=404, detail="Not found")

# DeepSeek API Testing Endpoints
class SentimentRequest(BaseModel):
    message: str
    hotel_id: str

class ResponseRequest(BaseModel):
    message: str
    hotel_id: str
    response_type: str = "helpful"

@app.post("/api/v1/deepseek/sentiment")
async def test_sentiment_analysis(request: SentimentRequest):
    """Test sentiment analysis endpoint"""
    import time
    import random

    # Simulate processing time
    await asyncio.sleep(random.uniform(1, 3))

    message = request.message.lower()

    # Simple sentiment analysis simulation
    if any(word in message for word in ['dirty', 'rude', 'disappointed', 'terrible', 'awful', 'bad', 'horrible', 'worst']):
        sentiment = 'negative'
        score = -0.8
        confidence = 0.92
    elif any(word in message for word in ['amazing', 'great', 'excellent', 'wonderful', 'love', 'thank', 'good', 'nice']):
        sentiment = 'positive'
        score = 0.85
        confidence = 0.89
    else:
        sentiment = 'neutral'
        score = 0.1
        confidence = 0.76

    # Extract keywords
    positive_words = [word for word in message.split() if word in ['amazing', 'great', 'excellent', 'wonderful', 'love', 'thank', 'good', 'nice']]
    negative_words = [word for word in message.split() if word in ['dirty', 'rude', 'disappointed', 'terrible', 'awful', 'bad', 'horrible', 'worst']]

    return {
        "sentiment": sentiment,
        "score": score,
        "confidence": confidence,
        "requires_attention": sentiment == 'negative' and score < -0.5,
        "reasoning": f"Detected {sentiment} sentiment based on key phrases and context analysis",
        "keywords": {
            "positive": positive_words,
            "negative": negative_words
        },
        "response_time": random.uniform(1, 3),
        "hotel_id": request.hotel_id,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/deepseek/generate-response")
async def test_response_generation(request: ResponseRequest):
    """Test response generation endpoint"""
    import time
    import random

    # Simulate processing time
    await asyncio.sleep(random.uniform(1.5, 3.5))

    responses = {
        "helpful": [
            "Thank you for reaching out! I'd be happy to help you with that. Let me provide you with the information you need.",
            "I understand your inquiry and I'm here to assist you. Here's what I can tell you about that.",
            "Great question! I'm glad you asked. Let me help you with the details."
        ],
        "booking": [
            "Thank you for your interest in staying with us! I'd be delighted to help you with your booking. Let me check our availability for next weekend and get back to you with our best options.",
            "We'd love to have you stay with us! For next weekend, I can check our available rooms and rates. May I ask how many guests will be staying and what type of room you prefer?",
            "Wonderful! I'm excited to help you plan your stay. Let me look into our weekend availability and I'll provide you with some great options."
        ],
        "complaint": [
            "I sincerely apologize for the issues you've experienced during your stay. This is not the standard we strive for, and I want to make this right immediately. Let me connect you with our manager to resolve this situation.",
            "I'm truly sorry to hear about these problems. Your comfort and satisfaction are our top priorities, and we've clearly fallen short. I'm taking immediate action to address these concerns.",
            "Thank you for bringing this to our attention, and I apologize for the inconvenience. We take all feedback seriously and I want to ensure we resolve this matter promptly and to your satisfaction."
        ],
        "general": [
            "Thank you for contacting us! I'm here to help with any questions or requests you may have about your stay or our services.",
            "Hello! I'm happy to assist you with any information you need about our hotel and services. How can I help you today?",
            "Thank you for reaching out to us. I'm available to help with any questions or assistance you might need during your stay."
        ]
    }

    response_list = responses.get(request.response_type, responses["general"])
    selected_response = random.choice(response_list)

    # Suggested actions based on response type
    actions = {
        "helpful": ["Follow up in 24 hours", "Provide additional resources"],
        "booking": ["Send booking confirmation", "Offer room upgrade", "Provide check-in details"],
        "complaint": ["Escalate to manager", "Offer compensation", "Schedule follow-up call"],
        "general": ["Provide hotel amenities info", "Share local recommendations"]
    }

    return {
        "response": selected_response,
        "confidence": 0.85 + random.random() * 0.1,
        "response_type": request.response_type,
        "reasoning": f"Generated {request.response_type} response using DeepSeek AI with context awareness",
        "suggested_actions": actions.get(request.response_type, []),
        "response_time": random.uniform(1.5, 3.5),
        "hotel_id": request.hotel_id,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/performance/status")
async def performance_status():
    """Performance status endpoint"""
    return {
        "status": "optimal",
        "metrics": {
            "cpu_usage": 25.5,
            "memory_usage": 45.2,
            "response_time_avg": 120,
            "requests_per_second": 15.3
        },
        "services": {
            "database": "healthy",
            "cache": "healthy",
            "green_api": "healthy",
            "deepseek": "healthy"
        }
    }

if __name__ == "__main__":
    print("🚀 Starting Test Server for Playwright Tests")
    print("🌐 Server starting on http://localhost:8000")
    print("📖 API docs available at http://localhost:8000/docs")
    print("🔧 Admin dashboard at http://localhost:8000/api/v1/admin/dashboard")
    
    uvicorn.run(
        "test_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
