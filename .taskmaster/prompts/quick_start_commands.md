# ⚡ БЫСТРЫЕ КОМАНДЫ ДЛЯ ЗАДАЧ
## WhatsApp Hotel Bot MVP - Команды на основе СУЩЕСТВУЮЩИХ задач

## ⚠️ ВАЖНО: ОСНОВАНО НА РЕАЛЬНЫХ ФАЙЛАХ
Все команды используют задачи из:
- 📋 `.taskmaster/tasks/tasks.json`
- 📄 `.taskmaster/tasks/task_XXX.md`

**НЕ СОЗДАВАЙТЕ НОВЫЕ ЗАДАЧИ** - используйте только существующие!

---

## 🏗️ TASK 001: PROJECT SETUP AND INFRASTRUCTURE

**📂 Источник**: `.taskmaster/tasks/task_001.md` (12ч, подзадачи 1.1-1.8)

```bash
# 1. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 1

# 2. Прочитать детальный план
cat .taskmaster/tasks/task_001.md

# 3. Начать задачу
npx task-master set-status --id=1 --status=in-progress

# 4. Завершить задачу
npx task-master set-status --id=1 --status=done
```

**Промпт**: Выполнить Task 001 точно по файлу `.taskmaster/tasks/task_001.md` - FastAPI структура, Docker, CI/CD, тесты, логирование, мониторинг. Подзадачи 1.1-1.8 из tasks.json.

---

## 🗄️ TASK 002: DATABASE SCHEMA DESIGN AND SETUP

**📂 Источник**: `.taskmaster/tasks/task_002.md` (19ч, подзадачи 2.1-2.8)

```bash
# 1. Проверить зависимости
npx task-master dependencies 2

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 2

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_002.md

# 4. Начать задачу
npx task-master set-status --id=2 --status=in-progress

# 5. Завершить задачу
npx task-master set-status --id=2 --status=done
```

**Промпт**: Выполнить Task 002 точно по файлу `.taskmaster/tasks/task_002.md` - PostgreSQL схема, SQLAlchemy модели, Alembic миграции, Redis. Подзадачи 2.1-2.8.

---

## 📱 TASK 003: GREEN API WHATSAPP INTEGRATION

**📂 Источник**: `.taskmaster/tasks/task_003.md` (16ч, подзадачи 3.1-3.6)

```bash
# 1. Проверить зависимости
npx task-master dependencies 3

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 3

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_003.md

# 4. Начать задачу
npx task-master set-status --id=3 --status=in-progress

# 5. Завершить задачу
npx task-master set-status --id=3 --status=done
```

**Промпт**: Выполнить Task 003 точно по файлу `.taskmaster/tasks/task_003.md` - Green API клиент, webhook обработчик, отправка/получение сообщений. Подзадачи 3.1-3.6.

---

## 🤖 TASK 004: DEEPSEEK AI INTEGRATION

**📂 Источник**: `.taskmaster/tasks/task_004.md` (14ч, подзадачи 4.1-4.6)

```bash
# 1. Проверить зависимости
npx task-master dependencies 4

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 4

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_004.md

# 4. Начать задачу
npx task-master set-status --id=4 --status=in-progress

# 5. Завершить задачу
npx task-master set-status --id=4 --status=done
```

**Промпт**: Выполнить Task 004 точно по файлу `.taskmaster/tasks/task_004.md` - DeepSeek API клиент, анализ настроений, генерация ответов, контекст. Подзадачи 4.1-4.6.

---

## 🏨 TASK 005: HOTEL MANAGEMENT SYSTEM

**📂 Источник**: `.taskmaster/tasks/task_005.md` (подзадачи 5.1-5.X)

```bash
# 1. Проверить зависимости
npx task-master dependencies 5

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 5

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_005.md

# 4. Начать задачу
npx task-master set-status --id=5 --status=in-progress
```

**Промпт**: Выполнить Task 005 точно по файлу `.taskmaster/tasks/task_005.md` - управление отелями, multi-tenant архитектура.

---

## ⚡ TASK 006: TRIGGER MANAGEMENT SYSTEM

**📂 Источник**: `.taskmaster/tasks/task_006.md` (подзадачи 6.1-6.X)

```bash
# 1. Проверить зависимости
npx task-master dependencies 6

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 6

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_006.md

# 4. Начать задачу
npx task-master set-status --id=6 --status=in-progress
```

**Промпт**: Выполнить Task 006 точно по файлу `.taskmaster/tasks/task_006.md` - система триггеров, временные и событийные триггеры.

---

## 💬 TASK 007: GUEST CONVERSATION HANDLER

**📂 Источник**: `.taskmaster/tasks/task_007.md` (подзадачи 7.1-7.X)

```bash
# 1. Проверить зависимости
npx task-master dependencies 7

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 7

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_007.md

# 4. Начать задачу
npx task-master set-status --id=7 --status=in-progress
```

**Промпт**: Выполнить Task 007 точно по файлу `.taskmaster/tasks/task_007.md` - обработка разговоров с гостями, состояния разговора.

---

## 📊 TASK 008: SENTIMENT ANALYSIS AND MONITORING

**📂 Источник**: `.taskmaster/tasks/task_008.md` (подзадачи 8.1-8.X)

```bash
# 1. Проверить зависимости
npx task-master dependencies 8

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 8

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_008.md

# 4. Начать задачу
npx task-master set-status --id=8 --status=in-progress
```

**Промпт**: Выполнить Task 008 точно по файлу `.taskmaster/tasks/task_008.md` - анализ настроений, мониторинг негатива.

---

## 📝 TASK 009: MESSAGE TEMPLATES AND RESPONSES

**📂 Источник**: `.taskmaster/tasks/task_009.md` (подзадачи 9.1-9.X)

```bash
# 1. Проверить зависимости
npx task-master dependencies 9

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 9

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_009.md

# 4. Начать задачу
npx task-master set-status --id=9 --status=in-progress
```

**Промпт**: Выполнить Task 009 точно по файлу `.taskmaster/tasks/task_009.md` - шаблоны сообщений, автоответы.

---

## 🔄 TASK 010: CELERY TASK QUEUE SETUP

**📂 Источник**: `.taskmaster/tasks/task_010.md` (подзадачи 10.1-10.X)

```bash
# 1. Проверить зависимости
npx task-master dependencies 10

# 2. Проверить авторизацию
python .taskmaster/scripts/workflow_enforcer.py 10

# 3. Прочитать детальный план
cat .taskmaster/tasks/task_010.md

# 4. Начать задачу
npx task-master set-status --id=10 --status=in-progress
```

**Промпт**: Выполнить Task 010 точно по файлу `.taskmaster/tasks/task_010.md` - Celery очереди, асинхронные задачи.

---

## 📊 TASKS 011-015: ОСТАЛЬНЫЕ ЗАДАЧИ

Для задач 011-015 используйте тот же паттерн:

```bash
# Общий паттерн для любой задачи
npx task-master dependencies <task_id>
python .taskmaster/scripts/workflow_enforcer.py <task_id>
cat .taskmaster/tasks/task_<task_id>.md
npx task-master set-status --id=<task_id> --status=in-progress
```

**Task 011**: Admin Dashboard API
**Task 012**: Authentication and Authorization
**Task 013**: Error Handling and Logging
**Task 014**: Testing Suite
**Task 015**: Deployment and DevOps

---

## 🔧 УТИЛИТЫ

```bash
# Проверить все задачи
npx task-master list

# Показать конкретную задачу
npx task-master show <task_id>

# Валидация системы
python .taskmaster/scripts/validation_system.py

# Проверить зависимости
npx task-master dependencies <task_id>
```

## 🚨 КРИТИЧЕСКИЕ НАПОМИНАНИЯ

1. **ВСЕГДА** читайте файл `.taskmaster/tasks/task_XXX.md` перед началом
2. **НИКОГДА** не создавайте новые задачи - используйте существующие
3. **ОБНОВЛЯЙТЕ** файлы задач в реальном времени
4. **СЛЕДУЙТЕ** точно подзадачам из tasks.json
5. **ПРОВЕРЯЙТЕ** зависимости перед началом каждой задачи

**Успех зависит от точного следования существующим файлам задач!**