#!/usr/bin/env python3
"""
Simple HTTP server for testing hotel-boost functionality
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import uuid
from datetime import datetime

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

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        path = urllib.parse.urlparse(self.path).path
        
        # Add CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        
        if path == '/health':
            response = {"status": "healthy", "timestamp": datetime.now().isoformat()}
        elif path == '/api/v1/hotels':
            response = {"status": "success", "data": mock_hotels, "total": len(mock_hotels)}
        elif path.startswith('/api/v1/hotels/') and path.endswith('/deepseek/test'):
            hotel_id = path.split('/')[-3]
            response = {"success": True, "message": "DeepSeek connection test successful"}
        elif path.startswith('/api/v1/hotels/'):
            hotel_id = path.split('/')[-1]
            hotel = next((h for h in mock_hotels if h["id"] == hotel_id), None)
            if hotel:
                response = hotel
            else:
                response = {"error": "Hotel not found"}
        elif path == '/api/v1/triggers':
            response = {
                "status": "success",
                "data": [
                    {"id": "trigger-001", "name": "Welcome Message", "type": "event_based"},
                    {"id": "trigger-002", "name": "Quick Response", "type": "time_based"}
                ],
                "total": 2
            }
        elif path == '/api/v1/demo/sentiment-analytics':
            response = {
                "sentiment": "NEGATIVE",
                "confidence": 0.62,
                "emotion": "Frustrated",
                "urgency": "High"
            }
        elif path == '/api/v1/admin/dashboard':
            # Serve HTML dashboard
            try:
                with open("app/templates/admin_dashboard.html", "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
                return
            except FileNotFoundError:
                response = {"error": "Dashboard template not found"}
        else:
            response = {"error": "Endpoint not found", "path": path}
        
        self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
    
    def do_POST(self):
        """Handle POST requests"""
        path = urllib.parse.urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        
        # Add CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except:
                data = {}
        else:
            data = {}
        
        if path == '/api/v1/hotels':
            # Create new hotel
            new_hotel = {
                "id": str(uuid.uuid4()),
                "name": data.get("name", "New Hotel"),
                "whatsapp_number": data.get("whatsapp_number", ""),
                "green_api_instance_id": data.get("green_api_instance_id", ""),
                "green_api_token": data.get("green_api_token", ""),
                "is_active": True,
                "settings": {
                    "deepseek": {
                        "api_key": data.get("deepseek_api_key", ""),
                        "model": "deepseek-chat",
                        "max_tokens": 4096,
                        "temperature": 0.7,
                        "travel_memory": ""
                    }
                }
            }
            mock_hotels.append(new_hotel)
            response = {"status": "success", "data": new_hotel}
        elif path.endswith('/triggers/templates'):
            # Create triggers from templates
            response = {
                "status": "success",
                "message": "Created 4 trigger templates",
                "triggers": [
                    {"id": f"trigger-{uuid.uuid4()}", "name": "Welcome Message", "created": True},
                    {"id": f"trigger-{uuid.uuid4()}", "name": "Quick Response", "created": True},
                    {"id": f"trigger-{uuid.uuid4()}", "name": "Check-in Welcome", "created": True},
                    {"id": f"trigger-{uuid.uuid4()}", "name": "Review Request", "created": True}
                ]
            }
        else:
            response = {"error": "POST endpoint not found", "path": path}
        
        self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
    
    def do_PUT(self):
        """Handle PUT requests"""
        path = urllib.parse.urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        
        # Add CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except:
                data = {}
        else:
            data = {}
        
        if '/deepseek' in path:
            # Update DeepSeek settings
            response = {"status": "success", "message": "DeepSeek settings updated"}
        else:
            response = {"error": "PUT endpoint not found", "path": path}
        
        self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

def run_server():
    """Run the test server"""
    server_address = ('', 8002)
    httpd = HTTPServer(server_address, TestHandler)
    
    print("🚀 Hotel Boost Test Server Starting...")
    print(f"📊 Server running on http://localhost:8002")
    print(f"📊 Mock data loaded: {len(mock_hotels)} hotels")
    print("🔧 Available endpoints:")
    print("   - GET  /health")
    print("   - GET  /api/v1/hotels")
    print("   - POST /api/v1/hotels")
    print("   - GET  /api/v1/triggers")
    print("   - GET  /api/v1/admin/dashboard")
    print("=" * 50)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
