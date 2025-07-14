# Task 003: Green API WhatsApp Integration

## Описание
Интеграция с Green API для отправки и получения WhatsApp сообщений с поддержкой webhook'ов

## Приоритет: HIGH
## Сложность: HIGH
## Оценка времени: 16 часов
## Зависимости: Task 001, Task 002

## Детальный план выполнения

### Подзадача 3.1: Настройка Green API клиента (3 часа)
**Файлы для создания:**
- `app/services/green_api.py` - основной клиент Green API
- `app/schemas/green_api.py` - Pydantic схемы для Green API
- `app/core/green_api_config.py` - конфигурация Green API

**Детали реализации:**
- HTTP клиент для взаимодействия с Green API
- Обработка rate limiting и retry логика
- Валидация API ключей и instance ID
- Поддержка различных типов сообщений (text, media, buttons)

### Подзадача 3.2: Webhook обработчик (4 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/webhooks.py` - webhook endpoints
- `app/services/webhook_processor.py` - обработка webhook'ов
- `app/schemas/webhook.py` - схемы для webhook данных
- `app/utils/webhook_validator.py` - валидация webhook'ов

**Детали реализации:**
- Endpoint для получения webhook'ов от Green API
- Валидация подписи webhook'ов для безопасности
- Обработка различных типов событий (incoming message, status update)
- Асинхронная обработка через Celery

### Подзадача 3.3: Отправка сообщений (3 часа)
**Файлы для создания:**
- `app/services/message_sender.py` - сервис отправки сообщений
- `app/models/message_queue.py` - модель очереди сообщений
- `app/tasks/send_message.py` - Celery задачи для отправки

**Детали реализации:**
- Очередь сообщений для надежной доставки
- Retry механизм для неудачных отправок
- Поддержка шаблонов сообщений
- Tracking статуса доставки

### Подзадача 3.4: Обработка входящих сообщений (3 часа)
**Файлы для создания:**
- `app/services/message_processor.py` - обработка входящих сообщений
- `app/utils/message_parser.py` - парсинг сообщений
- `app/tasks/process_incoming.py` - Celery задачи

**Детали реализации:**
- Парсинг различных типов сообщений
- Извлечение метаданных (номер телефона, время, тип)
- Сохранение в базу данных
- Trigger для автоматических ответов

### Подзадача 3.5: Детальные тесты Green API (2 часа)
**Файлы для создания:**
- `tests/unit/test_green_api_client.py` - тесты клиента
- `tests/unit/test_webhook_processor.py` - тесты webhook'ов
- `tests/integration/test_green_api_integration.py` - интеграционные тесты
- `tests/mocks/green_api_mock.py` - мок для Green API

**Детали реализации:**
- Мокирование Green API ответов
- Тесты различных сценариев отправки
- Тесты обработки ошибок API
- Тесты webhook валидации

### Подзадача 3.6: Логирование Green API операций (1 час)
**Файлы для создания:**
- `app/core/green_api_logging.py` - логирование Green API
- `app/middleware/green_api_middleware.py` - middleware для логирования

**Детали реализации:**
- Логирование всех запросов к Green API
- Логирование webhook'ов
- Мониторинг rate limits
- Алерты при ошибках API

### Подзадача 3.7: Интеграционное тестирование Green API (1 час)
**Файлы для создания:**
- `tests/integration/test_green_api_integration.py` - интеграционные тесты
- `tests/fixtures/green_api_responses.py` - фикстуры для тестов

**Детали реализации:**
- End-to-end тестирование с реальным API
- Тестирование webhook обработки
- Тестирование error handling
- Валидация rate limiting
- Проверка логирования и метрик

## Критерии готовности
- [ ] Green API клиент работает корректно
- [ ] Webhook'и принимаются и обрабатываются
- [ ] Сообщения отправляются успешно
- [ ] Входящие сообщения обрабатываются
- [ ] Все тесты проходят (unit + integration)
- [ ] Логирование настроено
- [ ] Rate limiting обрабатывается корректно
- [ ] Retry механизм работает
- [ ] Покрытие тестами >85%

## Детальные тесты

### Unit тесты Green API:
```python
def test_send_text_message():
    """Тест отправки текстового сообщения"""
    
def test_send_message_with_retry():
    """Тест retry механизма"""
    
def test_webhook_validation():
    """Тест валидации webhook'ов"""
    
def test_rate_limit_handling():
    """Тест обработки rate limiting"""
```

### Integration тесты:
- Тест полного цикла отправки/получения
- Тест webhook endpoint'а
- Тест обработки ошибок API
- Тест Celery задач

### Mock тесты:
- Мокирование Green API ответов
- Симуляция различных ошибок
- Тест timeout'ов и network errors

## Логирование Green API

### Структура логов:
```json
{
  "timestamp": "2025-07-11T04:50:00Z",
  "level": "INFO",
  "service": "whatsapp-hotel-bot",
  "component": "green_api",
  "operation": "send_message",
  "hotel_id": "uuid-here",
  "phone": "+1234567890",
  "message_type": "text",
  "api_response_time_ms": 250,
  "status": "success",
  "message_id": "msg-123",
  "correlation_id": "req-123456"
}
```

### Мониторинг:
- Количество отправленных сообщений
- Время ответа Green API
- Rate limit статус
- Ошибки API
- Webhook delivery rate

## Связанные задачи
- **Предыдущие задачи:** Task 001 (Project Setup), Task 002 (Database)
- **Следующие задачи:** Task 007 (Conversation Handler)
- **Блокирует:** Tasks 007, 014

## Заметки
- Обязательно тестировать с реальным Green API в staging
- Настроить мониторинг rate limits
- Webhook'и должны быть идемпотентными
- Все операции должны быть асинхронными
- Обязательно логировать все взаимодействия с API
