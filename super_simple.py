from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

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

@app.get("/api/v1/admin/dashboard", response_class=HTMLResponse)
async def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .card { background: #f5f5f5; padding: 20px; margin: 10px 0; border-radius: 8px; }
            .stats { display: flex; gap: 20px; }
            .stat { background: white; padding: 15px; border-radius: 5px; text-align: center; }
            button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>WhatsApp Hotel Bot - Admin Dashboard</h1>
        
        <div class="card">
            <h2>System Status: <span style="color: green;">Online</span></h2>
            <button onclick="loadData()">Refresh Data</button>
        </div>
        
        <div class="stats">
            <div class="stat">
                <h3 id="hotels-count">2</h3>
                <p>Total Hotels</p>
            </div>
            <div class="stat">
                <h3 id="messages-count">127</h3>
                <p>Messages Today</p>
            </div>
            <div class="stat">
                <h3 id="guests-count">45</h3>
                <p>Active Guests</p>
            </div>
            <div class="stat">
                <h3 id="ai-responses">98</h3>
                <p>AI Responses</p>
            </div>
        </div>
        
        <div class="card">
            <h3>Hotels</h3>
            <div id="hotels-list">Loading...</div>
        </div>
        
        <script>
            async function loadData() {
                try {
                    const response = await fetch('/api/v1/demo/hotels');
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        document.getElementById('hotels-count').textContent = data.data.length;
                        
                        const hotelsList = data.data.map(hotel => 
                            `<p><strong>${hotel.name}</strong> - ${hotel.whatsapp_number} (${hotel.is_active ? 'Active' : 'Inactive'})</p>`
                        ).join('');
                        
                        document.getElementById('hotels-list').innerHTML = hotelsList;
                    }
                } catch (error) {
                    console.error('Error loading data:', error);
                    document.getElementById('hotels-list').innerHTML = 'Error loading data';
                }
            }
            
            // Load data on page load
            loadData();
        </script>
    </body>
    </html>
    """

@app.get("/")
async def root():
    return {"message": "Super simple server is working!", "status": "ok"}

if __name__ == "__main__":
    print("🚀 Starting super simple server...")
    print("📍 Server: http://localhost:8002")
    print("📊 Dashboard: http://localhost:8002/api/v1/admin/dashboard")
    print("🔗 Hotels API: http://localhost:8002/api/v1/demo/hotels")
    print("-" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
