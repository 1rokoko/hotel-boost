#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting server...")
try:
    import uvicorn
    print("Uvicorn imported successfully")
    
    from app.main import app
    print("App imported successfully")
    
    print("🚀 Starting WhatsApp Hotel Bot server...")
    print("📍 Server will be available at: http://localhost:8002")
    print("📊 Admin Dashboard: http://localhost:8002/api/v1/admin/dashboard")
    print("-" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Try installing required packages:")
    print("   pip install fastapi uvicorn jinja2")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error starting server: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
