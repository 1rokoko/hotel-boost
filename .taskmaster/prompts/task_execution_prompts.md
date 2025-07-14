# 🚀 ПРОМПТЫ ДЛЯ ВЫПОЛНЕНИЯ ЗАДАЧ
## WhatsApp Hotel Bot MVP - Точные промпты по существующим задачам

## ⚠️ ВАЖНО: ОСНОВАНО НА СУЩЕСТВУЮЩИХ ФАЙЛАХ

**ВСЕ ПРОМПТЫ ТОЧНО СООТВЕТСТВУЮТ**:
- 📋 **Основному реестру**: `.taskmaster/tasks/tasks.json`
- 📄 **Детальным файлам**: `.taskmaster/tasks/task_XXX.md`

**НЕ СОЗДАВАЙТЕ НОВЫЕ ЗАДАЧИ** - используйте только то, что уже прописано!

---

## 🏗️ TASK 001: PROJECT SETUP AND INFRASTRUCTURE

**📂 ИСТОЧНИКИ**:
- `.taskmaster/tasks/task_001.md`
- `tasks.json` (ID: 1, подзадачи 1.1-1.8)

```
Выполнить Task 001: Project Setup and Infrastructure для WhatsApp Hotel Bot MVP

🔒 ОБЯЗАТЕЛЬНЫЕ ПРЕДВАРИТЕЛЬНЫЕ ШАГИ:
1. Проверить авторизацию: python .taskmaster/scripts/workflow_enforcer.py 1
2. Прочитать ВЕСЬ файл: .taskmaster/tasks/task_001.md
3. Изучить подзадачи в tasks.json (subtasks 1.1-1.8)
4. Обновить статус: npx task-master set-status --id=1 --status=in-progress

📊 ПАРАМЕТРЫ ИЗ СУЩЕСТВУЮЩИХ ФАЙЛОВ:
- Приоритет: HIGH
- Сложность: MEDIUM
- Время: 12 часов
- Зависимости: Нет
- Фаза: foundation

🎯 ТОЧНЫЕ ПОДЗАДАЧИ (ИЗ tasks.json):

1.1 Создание FastAPI проекта (2ч)
Файлы: main.py, requirements.txt, app/__init__.py, app/api/__init__.py
Детали: FastAPI с роутерами, middleware, CORS настройками

1.2 Настройка виртуального окружения (1ч)
Файлы: requirements.txt, .env.example, pyproject.toml
Детали: Poetry или pip-tools для управления зависимостями

1.3 Docker конфигурация (2ч)
Файлы: Dockerfile, docker-compose.yml, .dockerignore
Детали: Multi-stage build, оптимизация размера образа

1.4 Git репозиторий и CI/CD (2ч)
Файлы: .gitignore, .github/workflows/ci.yml, README.md
Детали: GitHub Actions для тестирования и линтинга

1.5 Базовые тесты инфраструктуры (1ч)
Файлы: tests/__init__.py, tests/test_main.py, pytest.ini
Детали: Тестирование запуска приложения и основных компонентов

1.6 Структурированное логирование (1.5ч)
Файлы: app/core/logging.py, app/core/config.py
Детали: Настройка логирования для разработки и продакшена

1.7 Детальные интеграционные тесты (1.5ч)
Файлы: tests/integration/, тесты подключений
Детали: Тестирование интеграции с базой данных и Redis

1.8 Мониторинг и метрики (2ч)
Файлы: app/core/metrics.py, health endpoints
Детали: Prometheus метрики, health checks

✅ КРИТЕРИИ ГОТОВНОСТИ (ИЗ task_001.md):
- Проект собирается успешно
- API запускается без ошибок
- Docker контейнеры работают правильно
- Все тесты проходят
- Документация обновлена

🔄 WORKFLOW ПРАВИЛА:
- Обновлять .taskmaster/tasks/task_001.md в реальном времени
- Отмечать выполнение каждой подзадачи 1.1-1.8
- Документировать ВСЕ созданные файлы
- Логировать фактическое vs запланированное время
```

---

## 🗄️ TASK 002: DATABASE SCHEMA DESIGN AND SETUP

**📂 ИСТОЧНИКИ**:
- `.taskmaster/tasks/task_002.md`
- `tasks.json` (ID: 2, подзадачи 2.1-2.8)

```
Выполнить Task 002: Database Schema Design and Setup для WhatsApp Hotel Bot MVP

🔒 ОБЯЗАТЕЛЬНЫЕ ПРЕДВАРИТЕЛЬНЫЕ ШАГИ:
1. Проверить зависимости: npx task-master dependencies 2 (Task 001 = done)
2. Проверить авторизацию: python .taskmaster/scripts/workflow_enforcer.py 2
3. Прочитать ВЕСЬ файл: .taskmaster/tasks/task_002.md
4. Изучить подзадачи в tasks.json (subtasks 2.1-2.8)
5. Обновить статус: npx task-master set-status --id=2 --status=in-progress

📊 ПАРАМЕТРЫ ИЗ СУЩЕСТВУЮЩИХ ФАЙЛОВ:
- Приоритет: HIGH
- Сложность: HIGH
- Время: 19 часов
- Зависимости: Task 001
- Фаза: foundation

🎯 ТОЧНЫЕ ПОДЗАДАЧИ (ИЗ task_002.md):

2.1 Настройка SQLAlchemy и Alembic (2ч)
Файлы: app/database.py, alembic.ini, alembic/env.py
Детали: AsyncSession, create_async_engine, миграции

2.2 Модель Hotels (2ч)
Файлы: app/models/hotel.py
Детали: Hotel model с полями name, settings, created_at, is_active

2.3 Модель Guests (2ч)
Файлы: app/models/guest.py
Детали: Guest model с phone, hotel_id, last_interaction

2.4 Модель Conversations (3ч)
Файлы: app/models/conversation.py
Детали: Conversation model с guest_id, messages, status, sentiment

2.5 Модель Triggers (3ч)
Файлы: app/models/trigger.py
Детали: Trigger model с hotel_id, trigger_type, conditions, message_template

2.6 Модели Staff Notifications и Sentiment Analysis (2ч)
Файлы: app/models/notification.py, app/models/sentiment.py
Детали: StaffNotification и SentimentAnalysis models

2.7 Redis настройка и кэширование (2ч)
Файлы: app/core/redis.py, app/core/cache.py
Детали: Redis connection, caching decorators

2.8 Миграции и тестирование (3ч)
Файлы: alembic/versions/, tests/test_database.py
Детали: Создание миграций, тестирование схемы

✅ КРИТЕРИИ ГОТОВНОСТИ (ИЗ task_002.md):
- Миграции базы данных выполняются успешно
- Все таблицы созданы с правильными ограничениями
- Multi-tenant изоляция проверена
- Redis подключение работает
- Тесты базы данных проходят

🔄 WORKFLOW ПРАВИЛА:
- Обновлять .taskmaster/tasks/task_002.md в реальном времени
- Отмечать выполнение каждой подзадачи 2.1-2.8
- Тестировать каждую модель после создания
- Документировать схему базы данных
```

---

## 📱 TASK 003: GREEN API WHATSAPP INTEGRATION

**📂 ИСТОЧНИКИ**:
- `.taskmaster/tasks/task_003.md`
- `tasks.json` (ID: 3, подзадачи 3.1-3.6)

```
Выполнить Task 003: Green API WhatsApp Integration для WhatsApp Hotel Bot MVP

🔒 ОБЯЗАТЕЛЬНЫЕ ПРЕДВАРИТЕЛЬНЫЕ ШАГИ:
1. Проверить зависимости: npx task-master dependencies 3 (Tasks 001, 002 = done)
2. Проверить авторизацию: python .taskmaster/scripts/workflow_enforcer.py 3
3. Прочитать ВЕСЬ файл: .taskmaster/tasks/task_003.md
4. Изучить подзадачи в tasks.json (subtasks 3.1-3.6)
5. Обновить статус: npx task-master set-status --id=3 --status=in-progress

📊 ПАРАМЕТРЫ ИЗ СУЩЕСТВУЮЩИХ ФАЙЛОВ:
- Приоритет: HIGH
- Сложность: HIGH
- Время: 16 часов
- Зависимости: Tasks 001, 002
- Фаза: core

🎯 ТОЧНЫЕ ПОДЗАДАЧИ (ИЗ task_003.md):

3.1 Настройка Green API клиента (3ч)
Файлы: app/services/green_api.py, app/schemas/green_api.py, app/core/green_api_config.py
Детали: HTTP клиент, rate limiting, retry логика, валидация API ключей

3.2 Webhook обработчик (4ч)
Файлы: app/api/v1/endpoints/webhooks.py, app/services/webhook_processor.py, app/schemas/webhook.py
Детали: Webhook endpoints, обработка webhook'ов, валидация

3.3 Отправка сообщений (3ч)
Файлы: app/services/message_sender.py, app/schemas/message.py
Детали: Отправка текстовых сообщений, обработка ошибок, логирование

3.4 Обработка входящих сообщений (3ч)
Файлы: app/services/message_processor.py, app/utils/message_parser.py
Детали: Парсинг входящих сообщений, сохранение в БД, обработка медиа

3.5 Rate limiting и retry логика (2ч)
Файлы: app/utils/rate_limiter.py, app/utils/retry_handler.py
Детали: Ограничение частоты запросов, экспоненциальный backoff

3.6 Тестирование интеграции (1ч)
Файлы: tests/test_green_api.py, tests/integration/test_webhooks.py
Детали: Unit и integration тесты для Green API

✅ КРИТЕРИИ ГОТОВНОСТИ (ИЗ task_003.md):
- Можно отправлять и получать WhatsApp сообщения
- Webhook'и обрабатываются корректно
- Rate limiting работает правильно
- Все тесты проходят
- Логирование всех операций

🔄 WORKFLOW ПРАВИЛА:
- Обновлять .taskmaster/tasks/task_003.md в реальном времени
- Отмечать выполнение каждой подзадачи 3.1-3.6
- Тестировать каждую подзадачу отдельно
- Документировать все API endpoints
```

---

## 🤖 TASK 004: DEEPSEEK AI INTEGRATION

**📂 ИСТОЧНИКИ**:
- `.taskmaster/tasks/task_004.md`
- `tasks.json` (ID: 4, подзадачи 4.1-4.6)

```
Выполнить Task 004: DeepSeek AI Integration для WhatsApp Hotel Bot MVP

🔒 ОБЯЗАТЕЛЬНЫЕ ПРЕДВАРИТЕЛЬНЫЕ ШАГИ:
1. Проверить зависимости: npx task-master dependencies 4 (Task 001 = done)
2. Проверить авторизацию: python .taskmaster/scripts/workflow_enforcer.py 4
3. Прочитать ВЕСЬ файл: .taskmaster/tasks/task_004.md
4. Изучить подзадачи в tasks.json (subtasks 4.1-4.6)
5. Обновить статус: npx task-master set-status --id=4 --status=in-progress

📊 ПАРАМЕТРЫ ИЗ СУЩЕСТВУЮЩИХ ФАЙЛОВ:
- Приоритет: HIGH
- Сложность: HIGH
- Время: 14 часов
- Зависимости: Task 001
- Фаза: core

🎯 ТОЧНЫЕ ПОДЗАДАЧИ (ИЗ task_004.md):

4.1 DeepSeek API клиент (3ч)
Файлы: app/services/deepseek_client.py, app/core/deepseek_config.py
Детали: HTTP клиент для DeepSeek API, обработка ответов

4.2 Анализ настроений (3ч)
Файлы: app/services/sentiment_analyzer.py, app/schemas/sentiment.py
Детали: Анализ настроений сообщений, классификация эмоций

4.3 Генерация ответов (3ч)
Файлы: app/services/response_generator.py, app/utils/prompt_builder.py
Детали: Генерация ответов на основе контекста разговора

4.4 Управление контекстом (2ч)
Файлы: app/services/context_manager.py, app/models/conversation_context.py
Детали: Сохранение и управление контекстом разговора

4.5 Fallback механизмы (2ч)
Файлы: app/services/fallback_handler.py, app/utils/ai_fallback.py
Детали: Обработка сбоев AI, резервные ответы

4.6 Тестирование AI интеграции (1ч)
Файлы: tests/test_deepseek.py, tests/test_sentiment.py
Детали: Unit тесты для AI функций

✅ КРИТЕРИИ ГОТОВНОСТИ (ИЗ task_004.md):
- AI анализ настроений работает корректно
- Генерация ответов соответствует контексту
- Fallback механизмы активируются при сбоях
- Контекст разговора сохраняется
- Все тесты проходят

🔄 WORKFLOW ПРАВИЛА:
- Обновлять .taskmaster/tasks/task_004.md в реальном времени
- Отмечать выполнение каждой подзадачи 4.1-4.6
- Тестировать AI функции с реальными данными
- Документировать все AI промпты и настройки
```