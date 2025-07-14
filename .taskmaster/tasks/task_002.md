# Task 002: Database Schema Design and Setup

## Описание
Создание полной схемы базы данных для multi-tenant архитектуры с отелями, гостями, триггерами

## Приоритет: HIGH
## Сложность: HIGH
## Оценка времени: 12 часов
## Зависимости: Task 001

## Детальный план выполнения

### Подзадача 2.1: Настройка SQLAlchemy и Alembic (2 часа)
**Файлы для создания:**
- `app/database.py` - конфигурация БД
- `alembic.ini` - настройки миграций
- `alembic/env.py` - окружение Alembic

**Детали реализации:**
```python
# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/hotelbot")

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=True if os.getenv("DEBUG") == "true" else False
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Подзадача 2.2: Модель Hotels (2 часа)
**Файлы для создания:**
- `app/models/hotel.py` - модель отелей
- `alembic/versions/001_create_hotels.py` - миграция

**Схема таблицы:**
```sql
CREATE TABLE hotels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    whatsapp_number VARCHAR(20) UNIQUE NOT NULL,
    green_api_instance_id VARCHAR(50),
    green_api_token VARCHAR(255),
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Подзадача 2.3: Модель Guests (2 часа)
**Файлы для создания:**
- `app/models/guest.py` - модель гостей
- `alembic/versions/002_create_guests.py` - миграция

**Схема таблицы:**
```sql
CREATE TABLE guests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id UUID NOT NULL REFERENCES hotels(id) ON DELETE CASCADE,
    phone VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    preferences JSONB DEFAULT '{}',
    last_interaction TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(hotel_id, phone)
);

-- Индексы для производительности
CREATE INDEX idx_guests_hotel_phone ON guests(hotel_id, phone);
CREATE INDEX idx_guests_last_interaction ON guests(last_interaction);
```

### Подзадача 2.4: Модель Triggers (3 часа)
**Файлы для создания:**
- `app/models/trigger.py` - модель триггеров
- `alembic/versions/003_create_triggers.py` - миграция

**Схема таблицы:**
```sql
CREATE TYPE trigger_type AS ENUM ('time_based', 'condition_based', 'event_based');

CREATE TABLE triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id UUID NOT NULL REFERENCES hotels(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    trigger_type trigger_type NOT NULL,
    conditions JSONB NOT NULL DEFAULT '{}',
    message_template TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Примеры условий в JSONB:
-- Временной триггер: {"hours_after_checkin": 2}
-- Условный триггер: {"room_type": "suite", "booking_status": "confirmed"}
```

### Подзадача 2.5: Модель Messages и Conversations (2 часа)
**Файлы для создания:**
- `app/models/message.py` - модели сообщений
- `alembic/versions/004_create_messages.py` - миграция

**Схемы таблиц:**
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id UUID NOT NULL REFERENCES hotels(id) ON DELETE CASCADE,
    guest_id UUID NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'active',
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TYPE message_type AS ENUM ('incoming', 'outgoing', 'system');
CREATE TYPE sentiment_type AS ENUM ('positive', 'negative', 'neutral', 'requires_attention');

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_type message_type NOT NULL,
    content TEXT NOT NULL,
    sentiment_score DECIMAL(3,2),
    sentiment_type sentiment_type,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Подзадача 2.6: Модель Staff Notifications (1 час)
**Файлы для создания:**
- `app/models/notification.py` - модель уведомлений
- `alembic/versions/005_create_notifications.py` - миграция

**Схема таблицы:**
```sql
CREATE TYPE notification_type AS ENUM ('negative_sentiment', 'urgent_request', 'system_alert');
CREATE TYPE notification_status AS ENUM ('pending', 'sent', 'failed', 'acknowledged');

CREATE TABLE staff_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id UUID NOT NULL REFERENCES hotels(id) ON DELETE CASCADE,
    guest_id UUID REFERENCES guests(id) ON DELETE SET NULL,
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    notification_type notification_type NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    status notification_status DEFAULT 'pending',
    sent_at TIMESTAMP WITH TIME ZONE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Row Level Security (RLS) для Multi-tenant

```sql
-- Включение RLS для всех таблиц
ALTER TABLE guests ENABLE ROW LEVEL SECURITY;
ALTER TABLE triggers ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_notifications ENABLE ROW LEVEL SECURITY;

-- Политики доступа
CREATE POLICY hotel_isolation_guests ON guests
    FOR ALL TO app_user
    USING (hotel_id = current_setting('app.current_hotel_id')::uuid);
```

### Подзадача 2.7: Детальные тесты моделей (3 часа)
**Файлы для создания:**
- `tests/unit/test_models_hotel.py` - тесты модели Hotel
- `tests/unit/test_models_guest.py` - тесты модели Guest
- `tests/unit/test_models_trigger.py` - тесты модели Trigger
- `tests/unit/test_models_message.py` - тесты моделей Message/Conversation
- `tests/integration/test_database_operations.py` - интеграционные тесты БД

**Детали реализации:**
- Тесты создания, обновления, удаления записей
- Тесты валидации данных
- Тесты связей между моделями
- Тесты уникальных ограничений
- Тесты каскадного удаления
- Тесты RLS политик

### Подзадача 2.8: Логирование операций БД (2 часа)
**Файлы для создания:**
- `app/core/database_logging.py` - логирование БД операций
- `app/utils/db_monitor.py` - мониторинг производительности БД
- `app/middleware/db_middleware.py` - middleware для БД

**Детали реализации:**
- Логирование всех SQL запросов в development
- Мониторинг времени выполнения запросов
- Логирование ошибок подключения к БД
- Метрики использования connection pool

### Подзадача 2.9: Тесты производительности БД (2 часа)
**Файлы для создания:**
- `tests/performance/test_db_performance.py` - тесты производительности
- `tests/load/test_concurrent_operations.py` - тесты конкурентности
- `scripts/db_benchmark.py` - скрипт для бенчмарков

**Детали реализации:**
- Тесты производительности запросов
- Тесты нагрузки на БД
- Тесты конкурентного доступа
- Бенчмарки индексов

## Критерии готовности
- [ ] Все миграции выполняются без ошибок
- [ ] Модели SQLAlchemy созданы и протестированы
- [ ] RLS политики работают корректно
- [ ] Индексы созданы для оптимизации запросов
- [ ] Все тесты моделей проходят (unit + integration)
- [ ] Логирование БД операций настроено
- [ ] Тесты производительности проходят
- [ ] Покрытие тестами моделей >90%
- [ ] Connection pooling настроен корректно

## Детальные тесты

### Unit тесты моделей:
```python
# Пример тестов для модели Hotel
def test_hotel_creation():
    """Тест создания отеля"""

def test_hotel_validation():
    """Тест валидации полей отеля"""

def test_hotel_unique_constraints():
    """Тест уникальных ограничений"""

def test_hotel_relationships():
    """Тест связей с другими моделями"""
```

### Integration тесты БД:
- Тесты транзакций
- Тесты rollback операций
- Тесты connection pooling
- Тесты миграций

### Performance тесты:
- Тест времени выполнения запросов
- Тест производительности индексов
- Тест нагрузки на БД
- Тест memory usage

## Логирование БД

### Структура логов БД:
```json
{
  "timestamp": "2025-07-11T04:50:00Z",
  "level": "DEBUG",
  "service": "whatsapp-hotel-bot",
  "component": "database",
  "operation": "SELECT",
  "table": "hotels",
  "query_time_ms": 25,
  "rows_affected": 1,
  "correlation_id": "req-123456",
  "sql": "SELECT * FROM hotels WHERE id = $1",
  "params": ["uuid-here"]
}
```

### Мониторинг БД:
- Время выполнения запросов
- Количество активных соединений
- Использование индексов
- Размер таблиц
- Deadlock'и и блокировки

## Связанные задачи
- **Предыдущая задача:** Task 001 (Project Setup)
- **Следующие задачи:** Task 003 (Green API), Task 005 (Hotel Management)
- **Блокирует:** Tasks 003, 005, 006, 007, 008

## Заметки
- Использовать UUID для всех первичных ключей
- JSONB поля для гибкости настроек
- Обязательные индексы для производительности
- Каскадное удаление для связанных данных
- Все операции БД должны логироваться
- Тесты должны использовать отдельную тестовую БД
- Миграции должны быть обратимыми
