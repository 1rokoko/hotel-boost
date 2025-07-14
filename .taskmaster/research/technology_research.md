# Technology Research для WhatsApp Hotel Bot MVP

## Green API Integration Research

### Лучшие практики интеграции Green API с Python FastAPI

**Ключевые находки:**
- Green API предоставляет REST API для отправки/получения WhatsApp сообщений
- Поддерживает webhook'и для real-time получения сообщений
- Rate limits: 1000 сообщений в день для бесплатного аккаунта
- Требует верификации номера телефона через QR код

**Рекомендуемая архитектура:**
```python
# Структура Green API клиента
class GreenAPIClient:
    def __init__(self, instance_id: str, api_token: str):
        self.base_url = f"https://api.green-api.com/waInstance{instance_id}"
        self.api_token = api_token
        
    async def send_message(self, chat_id: str, message: str):
        # Реализация отправки сообщений
        
    async def get_notifications(self):
        # Получение уведомлений
```

**Важные endpoint'ы:**
- `/sendMessage` - отправка текстовых сообщений
- `/sendFileByUrl` - отправка медиа файлов
- `/receiveNotification` - получение входящих сообщений
- `/deleteNotification` - подтверждение обработки уведомления

## DeepSeek API для анализа настроений

### Интеграция DeepSeek API в реальном времени

**Возможности DeepSeek API:**
- Анализ настроений текста (positive/negative/neutral)
- Генерация ответов на основе контекста
- Поддержка русского и английского языков
- Rate limit: 1000 запросов в час

**Рекомендуемая реализация:**
```python
class SentimentAnalyzer:
    def __init__(self, api_key: str):
        self.client = DeepSeekClient(api_key)
        
    async def analyze_sentiment(self, text: str, context: dict) -> SentimentResult:
        prompt = f"""
        Проанализируй настроение сообщения гостя отеля: "{text}"
        Контекст: {context}
        Верни JSON с полями: sentiment (positive/negative/neutral), 
        confidence (0-1), requires_attention (bool)
        """
        return await self.client.complete(prompt)
```

## Multi-tenant архитектура для WhatsApp ботов

### Паттерны изоляции данных

**Рекомендуемый подход - Row Level Security (RLS):**
```sql
-- Включение RLS для таблицы guests
ALTER TABLE guests ENABLE ROW LEVEL SECURITY;

-- Политика доступа только к данным своего отеля
CREATE POLICY hotel_isolation ON guests
    FOR ALL TO app_user
    USING (hotel_id = current_setting('app.current_hotel_id')::uuid);
```

**Middleware для установки контекста отеля:**
```python
@app.middleware("http")
async def set_hotel_context(request: Request, call_next):
    hotel_id = extract_hotel_id(request)
    await db.execute(f"SET app.current_hotel_id = '{hotel_id}'")
    response = await call_next(request)
    return response
```

## Celery и Redis для обработки сообщений

### Оптимальная конфигурация для высокой нагрузки

**Redis конфигурация:**
```python
# Настройки Redis для Celery
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"

# Оптимизация для WhatsApp сообщений
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Настройки для обработки триггеров
CELERYBEAT_SCHEDULE = {
    'process-triggers': {
        'task': 'app.tasks.process_time_triggers',
        'schedule': crontab(minute='*/5'),  # Каждые 5 минут
    },
}
```

**Структура задач:**
```python
@celery.task(bind=True, max_retries=3)
def send_whatsapp_message(self, hotel_id: str, guest_phone: str, message: str):
    try:
        # Отправка сообщения через Green API
        pass
    except Exception as exc:
        # Retry с exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

## Рекомендации по безопасности

### API Keys и секреты
- Использовать переменные окружения для всех API ключей
- Ротация ключей каждые 90 дней
- Webhook подписи для валидации входящих запросов

### Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/webhook")
@limiter.limit("100/minute")
async def webhook_handler(request: Request):
    # Обработка webhook'а
```

## Мониторинг и логирование

### Структурированное логирование
```python
import structlog

logger = structlog.get_logger()

# В обработчике сообщений
logger.info(
    "message_received",
    hotel_id=hotel_id,
    guest_phone=guest_phone,
    message_length=len(message),
    sentiment_score=sentiment.score
)
```

### Метрики для Prometheus
- Количество обработанных сообщений по отелям
- Время ответа API
- Ошибки интеграции с внешними сервисами
- Sentiment distribution по отелям

## Следующие шаги исследования

1. **Тестирование Green API** - создать тестовый аккаунт и проверить все endpoint'ы
2. **DeepSeek API лимиты** - протестировать реальные лимиты и время ответа
3. **Нагрузочное тестирование** - определить максимальную пропускную способность
4. **Backup стратегии** - план действий при недоступности внешних API
