# Task 019: Hotel-Specific Green API Instance Management

## Overview
Implement individual Green API instance management for each hotel with configuration UI. This allows each hotel to have their own WhatsApp Green API credentials and settings, enabling true multi-tenant WhatsApp integration.

## Status: ✅ COMPLETED

## Priority: High

## Dependencies
- Task 003: Green API WhatsApp Integration
- Task 005: Hotel Management System  
- Task 011: Admin Dashboard API

## Estimated Hours: 14

## Complexity: Medium

## Description
Extend the hotel management system to support individual Green API instances for each hotel. This includes:
- Extending Hotel model with Green API settings methods
- Creating hotel-specific Green API clients
- Adding admin UI endpoints for configuration
- Implementing testing and validation functionality

## Modules
- hotel
- green_api
- admin

## Phase: business

## Test Strategy
- Each hotel can have separate Green API credentials
- Clients work independently without interference
- Admin UI allows easy configuration and testing
- Comprehensive testing covers all scenarios

## Subtasks

### 19.1: Расширение Hotel модели для Green API настроек ✅
**Status:** COMPLETED  
**Estimated Hours:** 2  
**Files:**
- `app/models/hotel.py`
- `app/schemas/hotel.py`

**Details:**
- Добавлены методы `get_green_api_settings()`, `update_green_api_settings()`
- Реализована валидация Green API настроек
- Добавлены свойства `has_green_api_credentials` и `is_operational`

### 19.2: Расширение Hotel схем для Green API ✅
**Status:** COMPLETED  
**Estimated Hours:** 1  
**Files:**
- `app/schemas/hotel.py`

**Details:**
- Создана схема `GreenAPISettings` с валидацией полей
- Интегрирована с `HotelCreate` и `HotelUpdate` схемами
- Добавлена валидация instance_id и token форматов

### 19.3: Модификация Green API Client для multi-instance ✅
**Status:** COMPLETED  
**Estimated Hours:** 3  
**Files:**
- `app/services/green_api_client.py`

**Details:**
- Добавлены factory methods для hotel-specific клиентов
- Реализовано управление множественными инстансами
- Добавлена изоляция между отелями

### 19.4: Расширение Hotel Service для Green API управления ✅
**Status:** COMPLETED  
**Estimated Hours:** 2  
**Files:**
- `app/services/hotel_service.py`

**Details:**
- Добавлены методы `update_green_api_settings()`, `test_green_api_connection()`
- Реализована валидация настроек
- Добавлена обработка ошибок конфигурации

### 19.5: Расширение Hotels API endpoints ✅
**Status:** COMPLETED  
**Estimated Hours:** 2  
**Files:**
- `app/api/v1/endpoints/hotels.py`

**Details:**
- Добавлены endpoints: `PUT /hotels/{id}/green-api`, `POST /hotels/{id}/test-green-api`
- Реализована валидация входных данных
- Добавлена обработка ошибок API

### 19.6: Создание тестового отеля с настройками ✅
**Status:** COMPLETED  
**Estimated Hours:** 2  
**Files:**
- `scripts/add_test_hotel.py`

**Details:**
- Создан скрипт для добавления тестового отеля
- Включена полная конфигурация Green API и DeepSeek
- Добавлена валидация конфигурации

### 19.7: Исправление импортов и relationships ✅
**Status:** COMPLETED  
**Estimated Hours:** 2  
**Files:**
- `app/models/__init__.py`
- `app/models/base.py`
- `app/database.py`

**Details:**
- Решены проблемы с circular imports
- Исправлены SQLAlchemy relationships
- Добавлены недостающие импорты моделей
- Создана синхронная сессия для скриптов

## Implementation Details

### Hotel Model Extensions
```python
def get_green_api_settings(self) -> Dict[str, Any]:
    """Get Green API settings from hotel settings"""
    
def update_green_api_settings(self, settings: Dict[str, Any]) -> None:
    """Update Green API settings"""
    
@hybrid_property
def has_green_api_credentials(self) -> bool:
    """Check if hotel has Green API credentials configured"""
    
@hybrid_property
def is_operational(self) -> bool:
    """Check if hotel is operational (active + has credentials)"""
```

### Green API Client Factory
```python
def create_hotel_green_api_client(hotel_settings: Dict[str, Any]) -> GreenAPIClient:
    """Create hotel-specific Green API client"""
    
async def get_hotel_green_api_client(hotel_id: str) -> GreenAPIClient:
    """Get or create hotel-specific Green API client"""
```

### API Endpoints
- `PUT /api/v1/hotels/{hotel_id}/green-api` - Update Green API settings
- `POST /api/v1/hotels/{hotel_id}/test-green-api` - Test Green API connection
- `GET /api/v1/hotels/{hotel_id}/configuration` - Get hotel configuration

## Files Modified
- `app/models/hotel.py` - Extended with Green API methods
- `app/schemas/hotel.py` - Added Green API schemas
- `app/services/green_api_client.py` - Multi-instance support
- `app/services/hotel_service.py` - Green API management methods
- `app/api/v1/endpoints/hotels.py` - New API endpoints
- `scripts/add_test_hotel.py` - Test hotel creation script
- `app/models/__init__.py` - Fixed imports
- `app/models/base.py` - Fixed TenantBaseModel ForeignKey
- `app/database.py` - Added sync session support

## Testing
- Unit tests for hotel Green API methods
- Integration tests for API endpoints
- Test hotel creation and configuration
- Multi-tenant isolation verification

## Documentation
- API documentation updated with new endpoints
- Hotel configuration guide created
- Green API setup instructions added

## Next Steps
- Task 020: Hotel-Specific DeepSeek AI Configuration
- Integration testing with real Green API instances
- Performance optimization for multiple clients
