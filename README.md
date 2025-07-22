# WhatsApp Hotel Bot MVP

MVP система WhatsApp-ботов для отелей с фокусом на управление отзывами и автоматизацию коммуникации.

## 🚀 Особенности

- **Multi-tenant архитектура** для поддержки 50+ отелей
- **Интеграция с Green API** для WhatsApp сообщений
- **AI-анализ настроений** через DeepSeek API
- **Система триггеров** для автоматических сообщений
- **Мониторинг негативных отзывов** с уведомлениями персонала
- **Масштабируемая архитектура** с Celery и Redis

## 🏗️ Архитектура

### Основные модули:
- **Core Bot Engine** - ядро для обработки сообщений WhatsApp
- **Trigger Management** - система настройки триггеров для отелей
- **AI Response Module** - интеграция с DeepSeek API
- **Hotel Management** - управление отелями и их спецификой
- **Analytics & Monitoring** - отслеживание негатива и уведомления
- **Database Layer** - хранение данных по отелям и гостям

### Технологический стек:
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL + Redis
- **Queue**: Celery для асинхронных задач
- **AI**: DeepSeek API
- **WhatsApp**: Green API
- **Мониторинг**: Prometheus + Grafana

## 🛠️ Установка и запуск

### 🚀 Быстрый запуск после перезагрузки компьютера

**Если проект уже работал ранее, используйте эти команды для быстрого запуска:**

#### Вариант 1: Рекомендуемый (стабильный)
```bash
python run_server.py
```
*Основной сервер с полной функциональностью*

#### Вариант 2: Для отладки (если есть проблемы с базой данных)
```bash
python simple_working_server.py
```
*Упрощенный сервер для тестирования*

#### Вариант 3: Минимальная версия
```bash
python app_minimal.py
```
*Базовая версия без сложных зависимостей*

#### Вариант 4: Полная версия (может требовать установки зависимостей)
```bash
python app_full.py
```
*Полная версия со всеми функциями*

### 📍 Доступ к приложению
После запуска любого из серверов:
- **Админ панель**: http://localhost:8000/api/v1/admin/dashboard
- **API документация**: http://localhost:8000/docs
- **Альтернативная документация**: http://localhost:8000/redoc

### ⚠️ Решение проблем при запуске

**Ошибка "ModuleNotFoundError: No module named 'fastapi'":**
```bash
# Установите зависимости
pip install -r requirements.txt
```

**Ошибка с базой данных:**
```bash
# Используйте упрощенный сервер
python simple_working_server.py
```

**Ошибка с миграциями:**
```bash
# Запустите миграции правильно
python -m alembic upgrade head
```

### Предварительные требования

- Python 3.11+
- Docker и Docker Compose
- PostgreSQL 15+
- Redis 7+

### Локальная разработка

1. **Клонирование репозитория**
```bash
git clone https://github.com/your-org/whatsapp-hotel-bot.git
cd whatsapp-hotel-bot
```

2. **Настройка окружения**
```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

3. **Настройка переменных окружения**
```bash
cp .env.example .env
# Отредактируйте .env файл с вашими настройками
```

4. **Запуск с Docker Compose**
```bash
docker-compose up -d
```

5. **Применение миграций**
```bash
alembic upgrade head
```

6. **Запуск приложения**
```bash
uvicorn app.main:app --reload
```

Приложение будет доступно по адресу: http://localhost:8000

### API документация

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 Конфигурация

### Основные переменные окружения

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hotel_bot

# Redis
REDIS_URL=redis://localhost:6379

# Green API (WhatsApp)
GREEN_API_INSTANCE_ID=your_instance_id
GREEN_API_TOKEN=your_api_token

# DeepSeek AI
DEEPSEEK_API_KEY=your_deepseek_api_key

# Security
SECRET_KEY=your-super-secret-key
```

### Green API настройка

1. Зарегистрируйтесь на [Green API](https://green-api.com)
2. Создайте инстанс и получите Instance ID и API Token
3. Настройте webhook URL: `https://your-domain.com/api/v1/webhooks/green-api`

### DeepSeek API настройка

1. Зарегистрируйтесь на [DeepSeek](https://platform.deepseek.com)
2. Получите API ключ
3. Добавьте ключ в переменные окружения

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# Запуск с покрытием
pytest --cov=app --cov-report=html

# Запуск конкретного теста
pytest tests/test_main.py -v
```

## 📊 Мониторинг

### Health Check

```bash
curl http://localhost:8000/health
```

### Метрики

- **Prometheus**: http://localhost:9090 (если включен)
- **Grafana**: http://localhost:3000 (если включен)

## 🚀 Развертывание

### Docker

```bash
# Сборка образа
docker build -t whatsapp-hotel-bot .

# Запуск контейнера
docker run -p 8000:8000 whatsapp-hotel-bot
```

### Docker Compose (Production)

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 📝 API Endpoints

### Основные endpoints

- `GET /` - Корневой endpoint
- `GET /health` - Health check
- `GET /api/v1/health/detailed` - Детальный health check
- `POST /api/v1/webhooks/green-api` - Webhook для Green API
- `GET /api/v1/hotels` - Список отелей
- `POST /api/v1/hotels` - Создание отеля

## 🤝 Разработка

### Структура проекта

```
app/
├── api/                 # API endpoints
│   └── v1/
│       ├── endpoints/   # Endpoint handlers
│       └── api.py       # API router
├── core/                # Core functionality
│   ├── config.py        # Configuration
│   ├── database.py      # Database connection
│   └── security.py      # Security utilities
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── services/            # Business logic
└── utils/               # Utility functions
```

### Стандарты кода

- **Форматирование**: Black
- **Импорты**: isort
- **Линтинг**: flake8
- **Типизация**: mypy

```bash
# Форматирование кода
black app/
isort app/

# Проверка кода
flake8 app/
mypy app/
```

## 📋 Roadmap

### Фаза 1 (MVP) ✅
- [x] Базовая интеграция с Green API
- [x] Простые триггеры (время после заезда)
- [x] Готовые шаблоны вопросов
- [x] Базовый анализ негатива через DeepSeek

### Фаза 2 (В разработке)
- [ ] Расширенная аналитика настроений
- [ ] Уведомления персонала
- [ ] Детальная настройка триггеров
- [ ] Интеграция с PMS отелей

### Фаза 3 (Планируется)
- [ ] Персонализация по истории гостей
- [ ] Мультиязычность
- [ ] Расширенная аналитика и отчеты

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE) файл для деталей.

## 🆘 Поддержка

- **Issues**: [GitHub Issues](https://github.com/your-org/whatsapp-hotel-bot/issues)
- **Документация**: [Wiki](https://github.com/your-org/whatsapp-hotel-bot/wiki)
- **Email**: support@hotelbot.com


Архитектура ✅ ГОТОВА
✅ FastAPI + SQLAlchemy + Alembic
✅ PostgreSQL/SQLite + Redis
✅ Celery + Green API + DeepSeek AI
✅ Multi-tenant поддержка
✅ Comprehensive security
✅ Performance optimization
🌐 ДОСТУПНЫЕ ЭНДПОИНТЫ
Основные API:
GET /health - Health check
GET /api/v1/system/info - Информация о системе
GET /api/v1/hotels - Управление отелями
GET /api/v1/conversations - Управление разговорами
POST /api/v1/webhooks/green-api - Webhook обработка
GET /api/v1/triggers - Управление триггерами
GET /api/v1/templates - Управление шаблонами
GET /api/v1/admin/dashboard - Админ панель
Performance Monitoring:
GET /api/v1/performance/status - Статус оптимизаций
GET /api/v1/performance/metrics - Метрики производительности
Документация:
GET /docs - Swagger UI
GET /redoc - ReDoc