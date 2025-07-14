# Task 020: Hotel-Specific DeepSeek AI Configuration

## Overview
Implement individual DeepSeek API settings for each hotel with admin interface. This enables each hotel to have custom AI prompts, memory settings, and DeepSeek API configuration for personalized guest interactions.

## Status: ✅ COMPLETED

## Priority: High

## Dependencies
- Task 004: DeepSeek AI Integration
- Task 005: Hotel Management System
- Task 019: Hotel-Specific Green API Instance Management

## Estimated Hours: 12

## Complexity: Medium

## Description
Extend the hotel management system to support individual DeepSeek AI configurations for each hotel. This includes:
- Extending Hotel settings for DeepSeek configuration
- Creating hotel-specific DeepSeek clients
- Implementing custom prompts and memory per hotel
- Adding admin interface for AI configuration

## Modules
- hotel
- deepseek
- admin

## Phase: business

## Test Strategy
- Each hotel can have separate DeepSeek settings
- Custom prompts work correctly for each hotel
- Memory isolation verified between hotels
- Comprehensive testing covers all AI scenarios

## Subtasks

### 20.1: Расширение Hotel settings для DeepSeek ✅
**Status:** COMPLETED  
**Estimated Hours:** 2  
**Files:**
- `app/models/hotel.py`

**Details:**
- Добавлены методы `get_deepseek_settings()`, `update_deepseek_settings()`
- Реализован метод `set_deepseek_api_key()` с шифрованием
- Добавлены проверки `is_deepseek_configured()` и `is_fully_configured()`

### 20.2: Создание Hotel-specific DeepSeek Config ✅
**Status:** COMPLETED  
**Estimated Hours:** 3  
**Files:**
- `app/core/deepseek_config.py`

**Details:**
- Создана функция `create_hotel_deepseek_config()`
- Реализованы `create_hotel_sentiment_config()` и `create_hotel_response_config()`
- Добавлена поддержка custom prompts и memory settings

### 20.3: Модификация DeepSeek Client для hotel-specific настроек ✅
**Status:** COMPLETED  
**Estimated Hours:** 3  
**Files:**
- `app/services/deepseek_client.py`

**Details:**
- Добавлена функция `get_hotel_deepseek_client()`
- Реализовано управление hotel-specific клиентами
- Добавлены метрики и мониторинг для каждого отеля

### 20.4: Расширение Hotel Service для DeepSeek управления ✅
**Status:** COMPLETED  
**Estimated Hours:** 2  
**Files:**
- `app/services/hotel_service.py`

**Details:**
- Добавлены методы `update_deepseek_settings()`, `test_deepseek_connection()`
- Реализован метод `get_hotel_configuration()` для полной конфигурации
- Добавлена валидация DeepSeek настроек

### 20.5: API endpoints для DeepSeek настроек ✅
**Status:** COMPLETED  
**Estimated Hours:** 2  
**Files:**
- `app/api/v1/endpoints/hotels.py`

**Details:**
- Добавлены endpoints: `PUT /hotels/{id}/deepseek`, `POST /hotels/{id}/test-deepseek`
- Реализован endpoint `GET /hotels/{id}/configuration` для полной конфигурации
- Добавлена валидация и обработка ошибок

## Implementation Details

### Hotel Model DeepSeek Extensions
```python
def get_deepseek_settings(self) -> Dict[str, Any]:
    """Get DeepSeek settings from hotel settings"""
    
def update_deepseek_settings(self, settings: Dict[str, Any]) -> None:
    """Update DeepSeek settings"""
    
def set_deepseek_api_key(self, api_key: str) -> None:
    """Set encrypted DeepSeek API key"""
    
def is_deepseek_configured(self) -> bool:
    """Check if DeepSeek is configured for this hotel"""
    
def is_fully_configured(self) -> bool:
    """Check if hotel is fully configured (Green API + DeepSeek)"""
```

### Hotel-Specific DeepSeek Configuration
```python
def create_hotel_deepseek_config(hotel_id: str, hotel_settings: Dict[str, Any]) -> DeepSeekConfig:
    """Create hotel-specific DeepSeek configuration"""
    
def create_hotel_sentiment_config(hotel_settings: Dict[str, Any]) -> Dict[str, Any]:
    """Create hotel-specific sentiment analysis configuration"""
    
def create_hotel_response_config(hotel_settings: Dict[str, Any]) -> Dict[str, Any]:
    """Create hotel-specific response generation configuration"""
```

### DeepSeek Client Management
```python
async def get_hotel_deepseek_client(hotel_id: str, hotel_settings: Dict[str, Any]) -> DeepSeekClient:
    """Get or create hotel-specific DeepSeek client"""
    
def create_hotel_deepseek_client(hotel_id: str, hotel_settings: Dict[str, Any]) -> DeepSeekClient:
    """Create hotel-specific DeepSeek client"""
```

### Default DeepSeek Settings Structure
```python
"deepseek": {
    "api_key": None,  # Encrypted API key
    "model": "deepseek-chat",
    "max_tokens": 1000,
    "temperature": 0.7,
    "prompts": {
        "system_prompt": "You are a helpful hotel assistant...",
        "greeting_prompt": "Welcome to our hotel! How can I help you today?",
        "sentiment_prompt": "Analyze the sentiment of this message...",
        "response_prompt": "Generate a helpful response..."
    },
    "memory": {
        "max_context_length": 4000,
        "conversation_history_limit": 10,
        "remember_guest_preferences": True
    },
    "sentiment": {
        "threshold_negative": -0.3,
        "threshold_positive": 0.3,
        "enable_staff_alerts": True
    }
}
```

### API Endpoints
- `PUT /api/v1/hotels/{hotel_id}/deepseek` - Update DeepSeek settings
- `POST /api/v1/hotels/{hotel_id}/test-deepseek` - Test DeepSeek connection
- `GET /api/v1/hotels/{hotel_id}/configuration` - Get complete hotel configuration

## Files Modified
- `app/models/hotel.py` - Extended with DeepSeek methods
- `app/core/deepseek_config.py` - Hotel-specific configuration functions
- `app/services/deepseek_client.py` - Multi-instance client management
- `app/services/hotel_service.py` - DeepSeek management methods
- `app/api/v1/endpoints/hotels.py` - New DeepSeek API endpoints

## Testing
- Unit tests for hotel DeepSeek methods
- Integration tests for DeepSeek API endpoints
- Custom prompt testing for different hotels
- Memory isolation verification
- Performance testing with multiple clients

## Security Considerations
- DeepSeek API keys are encrypted at rest
- Hotel-specific settings are isolated
- API key validation and rotation support
- Secure transmission of sensitive data

## Documentation
- API documentation updated with DeepSeek endpoints
- Hotel AI configuration guide created
- Custom prompt examples and best practices
- Memory management documentation

## Performance Optimizations
- Client connection pooling per hotel
- Configuration caching
- Lazy loading of hotel-specific clients
- Memory usage optimization

## Next Steps
- Integration testing with real DeepSeek API
- Performance monitoring and optimization
- Advanced prompt engineering features
- Multi-language support for prompts
