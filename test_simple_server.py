"""
Simple test server to check if FastAPI works
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Test Server")

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/admin/settings")
async def get_settings():
    return {
        "settings": [
            {
                "key": "deepseek_api_key",
                "value": "sk-test-key",
                "category": "deepseek",
                "description": "DeepSeek API Key"
            }
        ],
        "total": 1
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
