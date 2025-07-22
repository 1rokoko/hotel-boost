#!/usr/bin/env python3
"""
Clean server without any imports from app module
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# Demo endpoints
@app.get("/api/v1/demo/hotels")
async def list_hotels_simple():
    hotels_data = [
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
    return {
        "status": "success",
        "data": {
            "hotels": hotels_data
        }
    }

@app.get("/api/v1/demo/conversations")
async def list_conversations_simple():
    conversations_data = [
        {
            "id": "conv-001",
            "hotel_id": "550e8400-e29b-41d4-a716-446655440001",
            "guest_phone": "+1234567890",
            "status": "active",
            "last_message": "Thank you for your help!",
            "message_count": 15,
            "created_at": "2025-07-19T10:00:00Z"
        },
        {
            "id": "conv-002",
            "hotel_id": "550e8400-e29b-41d4-a716-446655440002",
            "guest_phone": "+1234567891",
            "status": "closed",
            "last_message": "Room service was excellent.",
            "message_count": 8,
            "created_at": "2025-07-19T09:30:00Z"
        }
    ]
    return {
        "status": "success",
        "data": {
            "conversations": conversations_data
        }
    }

@app.get("/api/v1/demo/triggers")
async def list_triggers_simple():
    triggers_data = [
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
            "type": "scheduled",
            "is_active": True,
            "hotel_id": "550e8400-e29b-41d4-a716-446655440002"
        }
    ]
    return {
        "status": "success",
        "data": {
            "triggers": triggers_data
        }
    }

@app.get("/api/v1/demo/templates")
async def list_templates_simple():
    templates_data = [
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
    return {
        "status": "success",
        "data": {
            "templates": templates_data
        }
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

# Temporary admin dashboard - will be replaced with original template
@app.get("/api/v1/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WhatsApp Hotel Bot - Admin Dashboard</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5; }
            .container { display: flex; min-height: 100vh; }
            .sidebar { width: 250px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px 0; }
            .sidebar h4 { padding: 0 20px 20px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 20px; }
            .sidebar ul { list-style: none; }
            .sidebar li { margin: 5px 0; }
            .sidebar a { color: white; text-decoration: none; padding: 12px 20px; display: block; transition: all 0.3s; }
            .sidebar a:hover { background: rgba(255,255,255,0.1); }
            .main-content { flex: 1; padding: 20px; }
            .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
            .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
            .stat-card h3 { font-size: 2em; margin-bottom: 10px; color: #667eea; }
            .content-section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
            .btn:hover { background: #5a6fd8; }
            .loading { color: #666; font-style: italic; }
        </style>
    </head>
    <body>
        <div class="container">
            <nav class="sidebar">
                <h4><i class="fas fa-robot"></i> Hotel Bot Admin</h4>
                <ul>
                    <li><a href="#dashboard"><i class="fas fa-tachometer-alt"></i> Dashboard</a></li>
                    <li><a href="#hotels-section"><i class="fas fa-building"></i> Hotels</a></li>
                    <li><a href="#conversations"><i class="fas fa-comments"></i> Conversations</a></li>
                    <li><a href="#triggers-section"><i class="fas fa-bolt"></i> Triggers</a></li>
                    <li><a href="#templates"><i class="fas fa-file-alt"></i> Templates</a></li>
                    <li><a href="#sentiment-analytics"><i class="fas fa-chart-line"></i> Sentiment Analytics</a></li>
                    <li><a href="#users"><i class="fas fa-users"></i> Users</a></li>
                    <li><a href="#analytics"><i class="fas fa-analytics"></i> Analytics</a></li>
                    <li><a href="#monitoring"><i class="fas fa-desktop"></i> Monitoring</a></li>
                    <li><a href="#security"><i class="fas fa-shield-alt"></i> Security</a></li>
                    <li><a href="/api/v1/admin/deepseek-testing"><i class="fas fa-brain"></i> DeepSeek Testing</a></li>
                    <li><a href="#deepseek-settings-section"><i class="fas fa-cogs"></i> DeepSeek Settings</a></li>
                    <li><a href="/api/v1/admin/ai-configuration"><i class="fas fa-robot"></i> AI Configuration</a></li>
                </ul>
            </nav>
            
            <main class="main-content">
                <div class="header">
                    <h1>WhatsApp Hotel Bot Dashboard</h1>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                        <span style="color: green;"><i class="fas fa-circle"></i> System Online</span>
                        <button class="btn" onclick="refreshData()"><i class="fas fa-sync"></i> Refresh</button>
                    </div>
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <h3 id="hotels-count">-</h3>
                        <p>Total Hotels</p>
                    </div>
                    <div class="stat-card">
                        <h3 id="messages-count">-</h3>
                        <p>Messages Today</p>
                    </div>
                    <div class="stat-card">
                        <h3 id="guests-count">-</h3>
                        <p>Active Guests</p>
                    </div>
                    <div class="stat-card">
                        <h3 id="ai-responses">-</h3>
                        <p>AI Responses</p>
                    </div>
                </div>
                
                <div class="content-section">
                    <h3>Hotels</h3>
                    <div id="hotels-list" class="loading">Loading...</div>
                </div>
                
                <div class="content-section">
                    <h3>Recent Conversations</h3>
                    <div id="conversations-list" class="loading">Loading...</div>
                </div>
            </main>
        </div>
        
        <script>
            async function refreshData() {
                try {
                    // Load hotels
                    const hotelsResponse = await fetch('/api/v1/demo/hotels');
                    const hotelsData = await hotelsResponse.json();
                    
                    if (hotelsData.status === 'success') {
                        document.getElementById('hotels-count').textContent = hotelsData.data.length;
                        
                        const hotelsList = hotelsData.data.map(hotel => 
                            `<p><strong>${hotel.name}</strong> - ${hotel.whatsapp_number} (${hotel.is_active ? 'Active' : 'Inactive'})</p>`
                        ).join('');
                        
                        document.getElementById('hotels-list').innerHTML = hotelsList;
                    }
                    
                    // Load conversations
                    const conversationsResponse = await fetch('/api/v1/demo/conversations');
                    const conversationsData = await conversationsResponse.json();
                    
                    if (conversationsData.status === 'success') {
                        const conversationsList = conversationsData.data.map(conv => 
                            `<p><strong>${conv.guest_phone}</strong> - ${conv.last_message} (${conv.status})</p>`
                        ).join('');
                        
                        document.getElementById('conversations-list').innerHTML = conversationsList;
                    }
                    
                    // Update other stats
                    document.getElementById('messages-count').textContent = '127';
                    document.getElementById('guests-count').textContent = '45';
                    document.getElementById('ai-responses').textContent = '98';
                    
                } catch (error) {
                    console.error('Error loading data:', error);
                    document.getElementById('hotels-list').innerHTML = 'Error loading data';
                    document.getElementById('conversations-list').innerHTML = 'Error loading data';
                }
            }
            
            // Load data on page load
            refreshData();
        </script>
    </body>
    </html>
    """)

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

@app.get("/")
async def root():
    return {"message": "Clean server with original-style design!", "status": "ok"}

if __name__ == "__main__":
    print("🚀 Starting clean server with original-style admin dashboard...")
    print("📍 Server will be available at: http://localhost:8002")
    print("📊 Admin Dashboard: http://localhost:8002/api/v1/admin/dashboard")
    print("🔗 Demo Hotels API: http://localhost:8002/api/v1/demo/hotels")
    print("-" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
