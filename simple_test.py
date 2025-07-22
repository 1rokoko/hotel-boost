#!/usr/bin/env python3
"""
Simple test server to verify demo endpoints work
"""
from fastapi import FastAPI
import uvicorn

app = FastAPI()

# Demo endpoints
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

@app.get("/")
async def root():
    return {"message": "Test server is running!", "endpoints": ["/api/v1/demo/hotels"]}

if __name__ == "__main__":
    print("🚀 Starting test server...")
    print("📍 Server will be available at: http://localhost:8004")
    print("🔗 Hotels endpoint: http://localhost:8004/api/v1/demo/hotels")
    print("-" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8004, log_level="info")
