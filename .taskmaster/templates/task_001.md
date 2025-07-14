# Task 001: Project Setup and Infrastructure

## Overview
**Priority:** High | **Complexity:** Medium | **Estimated Hours:** 8
**Dependencies:** None | **Phase:** Foundation

## Description
Initialize project structure, setup FastAPI backend, configure development environment for WhatsApp Hotel Bot MVP.

## Detailed Implementation Plan

### 1. Project Structure Setup
```
hotel-whatsapp-bot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration management
│   │   ├── database.py         # Database connection
│   │   └── security.py         # Security utilities
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # Dependencies
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── endpoints/
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── services/               # Business logic
│   └── utils/                  # Utility functions
├── tests/
├── alembic/                    # Database migrations
├── docker/
├── scripts/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

### 2. FastAPI Setup
```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router

app = FastAPI(
    title="WhatsApp Hotel Bot API",
    description="MVP система WhatsApp-ботов для отелей",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### 3. Configuration Management
```python
# app/core/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "WhatsApp Hotel Bot"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str
    
    # External APIs
    GREEN_API_URL: str
    GREEN_API_TOKEN: str
    DEEPSEEK_API_KEY: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 4. Docker Configuration
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/hotel_bot
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    volumes:
      - .:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: hotel_bot
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### 5. Development Dependencies
```txt
# requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
sqlalchemy==2.0.23
alembic==1.13.0
asyncpg==0.29.0
redis==5.0.1
celery==5.3.4
httpx==0.25.2
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pytest==7.4.3
pytest-asyncio==0.21.1
```

## Test Strategy
1. **Project Structure Verification**
   - All directories created correctly
   - Import statements work without errors
   - FastAPI app starts successfully

2. **Docker Verification**
   - Docker build completes without errors
   - All services start with docker-compose
   - Health check endpoint responds

3. **Configuration Testing**
   - Environment variables load correctly
   - Settings validation works
   - Database connection can be established

## Acceptance Criteria
- [ ] Project structure matches specification
- [ ] FastAPI application starts without errors
- [ ] Docker containers build and run successfully
- [ ] Health check endpoint returns 200 status
- [ ] Environment configuration works
- [ ] Git repository initialized with proper .gitignore
- [ ] README.md contains setup instructions

## Related Modules
- Infrastructure
- Setup
- Configuration

## Next Steps
After completion, proceed to Task 002: Database Schema Design and Setup
