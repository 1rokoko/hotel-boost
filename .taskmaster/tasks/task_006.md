# Task 006: Trigger Management System

## Описание
Система управления триггерами для автоматических сообщений

## Приоритет: HIGH
## Сложность: HIGH
## Оценка времени: 18 часов
## Зависимости: Task 002, Task 005

## Детальный план выполнения

### Подзадача 6.1: Модели триггеров (3 часа)
**Файлы для создания:**
- `app/models/trigger.py` - SQLAlchemy модель триггеров
- `app/schemas/trigger.py` - Pydantic схемы для API
- `app/services/trigger_service.py` - бизнес-логика триггеров

**Детали реализации:**
```python
# app/models/trigger.py
class Trigger(Base):
    __tablename__ = "triggers"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID, ForeignKey("hotels.id"), nullable=False)
    name = Column(String(255), nullable=False)
    trigger_type = Column(Enum(TriggerType), nullable=False)  # time_based, event_based, condition_based
    conditions = Column(JSONB, nullable=False, default={})
    message_template = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Типы триггеров:**
- **time_based**: Через X часов после заезда
- **event_based**: При получении сообщения
- **condition_based**: При выполнении условий

### Подзадача 6.2: Движок выполнения триггеров (4 часа)
**Файлы для создания:**
- `app/services/trigger_engine.py` - основной движок
- `app/tasks/execute_triggers.py` - Celery задачи
- `app/utils/trigger_evaluator.py` - оценка условий

**Детали реализации:**
```python
# app/services/trigger_engine.py
class TriggerEngine:
    async def evaluate_triggers(self, hotel_id: str, context: dict):
        """Оценка и выполнение триггеров"""

    async def execute_trigger(self, trigger_id: str, guest_id: str):
        """Выполнение конкретного триггера"""

    async def schedule_time_based_trigger(self, trigger: Trigger, guest: Guest):
        """Планирование временного триггера"""
```

**Логика выполнения:**
- Проверка условий триггера
- Рендеринг шаблона сообщения
- Отправка через Green API
- Логирование результата

### Подзадача 6.3: API управления триггерами (3 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/triggers.py` - REST API endpoints
- `app/schemas/trigger_config.py` - схемы конфигурации

**Детали реализации:**
```python
# API endpoints
@router.post("/", response_model=TriggerResponse)
async def create_trigger(trigger: TriggerCreate):
    """Создание нового триггера"""

@router.get("/{trigger_id}", response_model=TriggerResponse)
async def get_trigger(trigger_id: str):
    """Получение триггера по ID"""

@router.put("/{trigger_id}", response_model=TriggerResponse)
async def update_trigger(trigger_id: str, trigger: TriggerUpdate):
    """Обновление триггера"""

@router.post("/{trigger_id}/test")
async def test_trigger(trigger_id: str, test_data: TriggerTestData):
    """Тестирование триггера"""
```

### Подзадача 6.4: Планировщик задач (3 часа)
**Файлы для создания:**
- `app/services/scheduler.py` - планировщик триггеров
- `app/tasks/scheduled_triggers.py` - периодические задачи
- `app/utils/cron_parser.py` - парсер cron выражений

**Детали реализации:**
```python
# app/services/scheduler.py
class TriggerScheduler:
    async def schedule_trigger(self, trigger: Trigger, execute_at: datetime):
        """Планирование выполнения триггера"""

    async def cancel_scheduled_trigger(self, trigger_id: str):
        """Отмена запланированного триггера"""

    async def reschedule_trigger(self, trigger_id: str, new_time: datetime):
        """Перепланирование триггера"""
```

**Типы планирования:**
- Одноразовые задачи (через X часов)
- Повторяющиеся задачи (каждый день в 10:00)
- Условные задачи (при событии)

### Подзадача 6.5: Детальные тесты триггеров (3 часа)
**Файлы для создания:**
- `tests/unit/test_trigger_engine.py` - тесты движка
- `tests/unit/test_trigger_service.py` - тесты сервиса
- `tests/integration/test_trigger_execution.py` - интеграционные тесты
- `tests/unit/test_scheduler.py` - тесты планировщика

**Детали реализации:**
```python
def test_time_based_trigger_execution():
    """Тест выполнения временного триггера"""

def test_condition_based_trigger_evaluation():
    """Тест оценки условного триггера"""

def test_trigger_priority_handling():
    """Тест обработки приоритетов триггеров"""

def test_trigger_template_rendering():
    """Тест рендеринга шаблонов сообщений"""
```

### Подзадача 6.6: Логирование и мониторинг (2 часа)
**Файлы для создания:**
- `app/core/trigger_logging.py` - логирование триггеров
- `app/utils/trigger_metrics.py` - метрики Prometheus

**Структура логов:**
```json
{
  "timestamp": "2025-07-11T06:00:00Z",
  "component": "trigger_engine",
  "operation": "execute_trigger",
  "trigger_id": "uuid-here",
  "status": "success"
}
```

## Критерии готовности
- [ ] Триггеры создаются и выполняются
- [ ] Планировщик работает корректно
- [ ] API для управления функционирует
- [ ] Все тесты проходят
- [ ] Логирование настроено
- [ ] Покрытие тестами >85%
