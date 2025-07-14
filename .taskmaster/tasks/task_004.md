# Task 004: DeepSeek AI Integration

## Описание
Интеграция с DeepSeek API для анализа настроений и генерации ответов

## Приоритет: HIGH
## Сложность: MEDIUM
## Оценка времени: 14 часов
## Зависимости: Task 001

## Детальный план выполнения

### Подзадача 4.1: Настройка DeepSeek API клиента (3 часа)
**Файлы для создания:**
- `app/services/deepseek_client.py` - основной клиент DeepSeek API
- `app/schemas/deepseek.py` - Pydantic схемы для DeepSeek
- `app/core/deepseek_config.py` - конфигурация DeepSeek

**Детали реализации:**
- HTTP клиент для взаимодействия с DeepSeek API
- Обработка rate limiting и retry логика
- Валидация API ключей
- Поддержка различных моделей DeepSeek

### Подзадача 4.2: Анализ настроений (4 часа)
**Файлы для создания:**
- `app/services/sentiment_analyzer.py` - сервис анализа настроений
- `app/models/sentiment.py` - модель для хранения результатов
- `app/tasks/analyze_sentiment.py` - Celery задачи

**Детали реализации:**
- Анализ текста сообщений на позитив/негатив
- Определение уровня уверенности
- Сохранение результатов в БД
- Автоматические уведомления при негативе

### Подзадача 4.3: Генерация ответов (3 часа)
**Файлы для создания:**
- `app/services/response_generator.py` - генерация ответов
- `app/utils/prompt_templates.py` - шаблоны промптов
- `app/tasks/generate_response.py` - Celery задачи

**Детали реализации:**
- Контекстно-зависимая генерация ответов
- Шаблоны промптов для разных сценариев
- Персонализация по истории гостя
- Мультиязычная поддержка

### Подзадача 4.4: Детальные тесты DeepSeek (2 часа)
**Файлы для создания:**
- `tests/unit/test_deepseek_client.py` - тесты клиента
- `tests/unit/test_sentiment_analyzer.py` - тесты анализа
- `tests/integration/test_deepseek_integration.py` - интеграционные тесты
- `tests/mocks/deepseek_mock.py` - мок для DeepSeek API

**Детали реализации:**
```python
# tests/unit/test_deepseek_client.py
def test_sentiment_analysis_positive():
    """Тест анализа позитивного сообщения"""

def test_sentiment_analysis_negative():
    """Тест анализа негативного сообщения"""

def test_api_rate_limiting():
    """Тест обработки rate limiting"""

def test_api_error_handling():
    """Тест обработки ошибок API"""

def test_token_optimization():
    """Тест оптимизации использования токенов"""

def test_response_generation():
    """Тест генерации ответов"""

def test_cache_functionality():
    """Тест кэширования результатов"""
```

**Критерии тестирования:**
- Покрытие кода >90%
- Тесты всех сценариев ошибок
- Проверка производительности
- Валидация входных/выходных данных

### Подзадача 4.5: Логирование DeepSeek операций (1 час)
**Файлы для создания:**
- `app/core/deepseek_logging.py` - логирование DeepSeek
- `app/middleware/deepseek_middleware.py` - middleware

**Детали реализации:**
- Логирование всех запросов к DeepSeek API
- Мониторинг использования токенов
- Алерты при ошибках API
- Метрики производительности

### Подзадача 4.6: Кэширование и оптимизация (1 час)
**Файлы для создания:**
- `app/utils/deepseek_cache.py` - кэширование результатов
- `app/services/token_optimizer.py` - оптимизация токенов

**Детали реализации:**
- Redis кэш для повторяющихся запросов
- Оптимизация промптов для экономии токенов
- Batch обработка запросов
- Rate limiting для API

## Критерии готовности
- [ ] DeepSeek API клиент работает корректно
- [ ] Анализ настроений функционирует
- [ ] Генерация ответов работает
- [ ] Все тесты проходят (unit + integration)
- [ ] Логирование настроено
- [ ] Кэширование работает
- [ ] Rate limiting обрабатывается
- [ ] Покрытие тестами >85%

## Детальные тесты

### Unit тесты DeepSeek:
```python
def test_sentiment_analysis():
    """Тест анализа настроений"""
    
def test_response_generation():
    """Тест генерации ответов"""
    
def test_api_error_handling():
    """Тест обработки ошибок API"""
    
def test_token_optimization():
    """Тест оптимизации токенов"""
```

### Integration тесты:
- Тест полного цикла анализа настроений
- Тест генерации ответов с контекстом
- Тест обработки ошибок API
- Тест кэширования результатов

## Логирование DeepSeek

### Структура логов:
```json
{
  "timestamp": "2025-07-11T05:00:00Z",
  "level": "INFO",
  "service": "whatsapp-hotel-bot",
  "component": "deepseek",
  "operation": "sentiment_analysis",
  "hotel_id": "uuid-here",
  "message_id": "msg-123",
  "tokens_used": 150,
  "api_response_time_ms": 800,
  "sentiment_score": 0.8,
  "confidence": 0.9,
  "correlation_id": "req-123456"
}
```

### Мониторинг:
- Использование токенов
- Время ответа DeepSeek API
- Точность анализа настроений
- Rate limit статус
- Ошибки API

## Связанные задачи
- **Предыдущие задачи:** Task 001 (Project Setup)
- **Следующие задачи:** Task 007 (Conversation Handler), Task 008 (Sentiment Analysis)
- **Блокирует:** Tasks 007, 008, 009, 014

## Заметки
- Обязательно тестировать с реальным DeepSeek API в staging
- Настроить мониторинг использования токенов
- Кэшировать результаты для экономии API вызовов
- Все операции должны быть асинхронными
- Обязательно логировать все взаимодействия с API
