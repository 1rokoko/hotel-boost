# Task 008: Sentiment Analysis and Monitoring

## Описание
Система анализа настроений и мониторинга негативных отзывов

## Приоритет: MEDIUM
## Сложность: MEDIUM
## Оценка времени: 14 часов
## Зависимости: Task 004, Task 007

## Детальный план выполнения

### Подзадача 8.1: Анализ настроений в реальном времени (3 часа)
**Файлы для создания:**
- `app/services/realtime_sentiment.py` - анализ в реальном времени
- `app/tasks/analyze_message_sentiment.py` - Celery задачи анализа
- `app/utils/sentiment_processor.py` - обработка результатов

**Детали реализации:**
```python
# app/services/realtime_sentiment.py
class RealtimeSentimentAnalyzer:
    async def analyze_message(self, message: str, conversation_id: str):
        """Анализ настроения сообщения в реальном времени"""

    async def process_sentiment_result(self, result: SentimentResult):
        """Обработка результата анализа"""

    async def trigger_alerts_if_needed(self, sentiment: SentimentResult):
        """Запуск алертов при негативном настроении"""
```

**Классификация настроений:**
- **positive**: 0.1 до 1.0 (радость, удовлетворение)
- **neutral**: -0.1 до 0.1 (нейтральные сообщения)
- **negative**: -1.0 до -0.1 (недовольство, жалобы)
- **critical**: < -0.7 (серьезные проблемы)

### Подзадача 8.2: Система уведомлений персонала (3 часа)
**Файлы для создания:**
- `app/services/staff_notification.py` - сервис уведомлений
- `app/models/staff_alert.py` - модель алертов
- `app/tasks/send_staff_alert.py` - Celery задачи уведомлений
- `app/utils/notification_channels.py` - каналы уведомлений

**Детали реализации:**
```python
# app/services/staff_notification.py
class StaffNotificationService:
    async def send_sentiment_alert(self, hotel_id: str, sentiment: SentimentResult):
        """Отправка алерта о негативном настроении"""

    async def escalate_to_manager(self, alert: StaffAlert):
        """Эскалация к менеджеру"""

    async def send_daily_summary(self, hotel_id: str):
        """Ежедневная сводка по настроениям"""
```

**Каналы уведомлений:**
- **email**: Электронная почта персонала
- **sms**: SMS уведомления
- **webhook**: Webhook в CRM/PMS отеля
- **dashboard**: Уведомления в админ панели

### Подзадача 8.3: Дашборд аналитики настроений (3 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/sentiment_analytics.py` - API аналитики
- `app/services/sentiment_analytics.py` - сервис аналитики
- `app/utils/sentiment_aggregator.py` - агрегация данных

**Детали реализации:**
```python
# API endpoints для аналитики
@router.get("/sentiment/overview")
async def get_sentiment_overview(hotel_id: str, period: str):
    """Общая статистика настроений"""

@router.get("/sentiment/trends")
async def get_sentiment_trends(hotel_id: str, days: int = 30):
    """Тренды настроений за период"""

@router.get("/sentiment/alerts")
async def get_recent_alerts(hotel_id: str, limit: int = 50):
    """Последние алерты по настроениям"""
```

**Метрики аналитики:**
- Распределение настроений (позитив/негатив/нейтрал)
- Тренды по дням/неделям/месяцам
- Топ причины негативных отзывов
- Время реакции персонала на алерты

### Подзадача 8.4: Правила и пороги (2 часа)
**Файлы для создания:**
- `app/services/sentiment_rules.py` - правила обработки
- `app/utils/threshold_manager.py` - управление порогами
- `app/models/sentiment_config.py` - конфигурация настроек

**Детали реализации:**
```python
# app/services/sentiment_rules.py
class SentimentRulesEngine:
    async def evaluate_sentiment_rules(self, sentiment: SentimentResult):
        """Оценка правил для настроения"""

    async def should_alert_staff(self, sentiment: SentimentResult) -> bool:
        """Проверка необходимости алерта"""

    async def get_escalation_level(self, sentiment: SentimentResult) -> EscalationLevel:
        """Определение уровня эскалации"""
```

**Настраиваемые пороги:**
- Порог негативного настроения (-0.3)
- Порог критического настроения (-0.7)
- Количество негативных сообщений подряд (3)
- Время ожидания ответа персонала (30 мин)

### Подзадача 8.5: Детальные тесты анализа (2 часа)
**Файлы для создания:**
- `tests/unit/test_sentiment_analysis.py` - тесты анализа
- `tests/unit/test_staff_notification.py` - тесты уведомлений
- `tests/integration/test_notification_system.py` - интеграционные тесты

**Детали реализации:**
```python
def test_sentiment_classification_accuracy():
    """Тест точности классификации настроений"""

def test_negative_sentiment_alert_trigger():
    """Тест запуска алертов при негативе"""

def test_staff_notification_delivery():
    """Тест доставки уведомлений персоналу"""

def test_sentiment_analytics_aggregation():
    """Тест агрегации данных аналитики"""
```

### Подзадача 8.6: Логирование и метрики (1 час)
**Файлы для создания:**
- `app/core/sentiment_logging.py` - логирование анализа
- `app/utils/sentiment_metrics.py` - метрики Prometheus

**Структура логов:**
```json
{
  "timestamp": "2025-07-11T08:00:00Z",
  "component": "sentiment_analyzer",
  "operation": "analyze_sentiment",
  "message_id": "uuid-here",
  "sentiment_score": -0.6,
  "sentiment_label": "negative",
  "confidence": 0.85,
  "alert_triggered": true,
  "processing_time_ms": 120
}
```

**Метрики мониторинга:**
- Количество проанализированных сообщений
- Распределение настроений
- Время обработки анализа
- Количество отправленных алертов
- Точность классификации

## Критерии готовности
- [ ] Анализ настроений работает в реальном времени
- [ ] Уведомления персонала функционируют
- [ ] Аналитика доступна через API
- [ ] Правила настраиваются
- [ ] Все тесты проходят
- [ ] Покрытие тестами >85%
