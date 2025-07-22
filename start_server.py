#!/usr/bin/env python3
"""
Fixed server runner for hotel-boost project on port 8002
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import uvicorn
    from app.main import app
    
    if __name__ == "__main__":
        print("🚀 Starting WhatsApp Hotel Bot server...")
        print("📍 Server will be available at: http://localhost:8003")
        print("📊 Admin Dashboard: http://localhost:8003/api/v1/admin/dashboard")
        print("📖 API Documentation: http://localhost:8003/docs")
        print("❤️  Health Check: http://localhost:8003/health")
        print("-" * 60)

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8003,
            reload=False,
            log_level="info"
        )
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Try installing required packages:")
    print("   pip install fastapi uvicorn jinja2")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error starting server: {e}")
    sys.exit(1)
