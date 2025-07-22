#!/usr/bin/env python3
"""
Simple server runner - just run the server
"""

import os
import sys

# Change to correct directory
os.chdir(r"c:\Users\Аркадий\Documents\augment-projects\hotel-boost")

print("🚀 Starting Hotel Boost Server...")
print("📂 Working directory:", os.getcwd())

# Import and run the server
try:
    import uvicorn
    from server_final import app
    
    print("✅ Imports successful")
    print("🌐 Starting server on http://localhost:8002")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
