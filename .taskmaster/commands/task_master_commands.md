# Task Master Commands для WhatsApp Hotel Bot MVP

## Основные команды для управления проектом

### 1. Просмотр задач

```bash
# Показать все задачи
npx task-master list

# Показать задачи по статусу
npx task-master list --status pending
npx task-master list --status in-progress
npx task-master list --status completed

# Показать задачи по приоритету
npx task-master list --priority high
npx task-master list --priority medium

# Показать задачи по фазе
npx task-master list --phase foundation
npx task-master list --phase core
npx task-master list --phase business
```

### 2. Работа с конкретными задачами

```bash
# Показать детали задачи
npx task-master show 1
npx task-master show 3

# Показать несколько задач
npx task-master show 1,3,5

# Начать работу над задачей
npx task-master start 1

# Завершить задачу
npx task-master complete 1

# Отметить задачу как заблокированную
npx task-master block 3 "Ожидаем API ключи от Green API"
```

### 3. Исследование и планирование

```bash
# Исследовать технологии для задачи
npx task-master research 3 "Green API integration best practices"
npx task-master research 4 "DeepSeek API rate limits and optimization"

# Расширить задачу с подзадачами
npx task-master expand 1
npx task-master expand 2

# Создать план для фазы
npx task-master plan --phase foundation
npx task-master plan --phase core
```

### 4. Управление зависимостями

```bash
# Показать граф зависимостей
npx task-master dependencies

# Показать критический путь
npx task-master critical-path

# Найти следующую доступную задачу
npx task-master next

# Показать заблокированные задачи
npx task-master blocked
```

### 5. Отчеты и аналитика

```bash
# Общий статус проекта
npx task-master status

# Прогресс по фазам
npx task-master progress --by-phase

# Временные оценки
npx task-master estimate

# Отчет по рискам
npx task-master risks
```

### 6. Работа с командой

```bash
# Назначить задачу разработчику
npx task-master assign 1 "developer1"
npx task-master assign 3 "developer2"

# Показать задачи по исполнителям
npx task-master list --assignee developer1

# Создать план для команды
npx task-master team-plan --developers 3
```

## Рекомендуемый workflow

### Ежедневное планирование

```bash
# 1. Проверить статус проекта
npx task-master status

# 2. Найти следующую задачу для работы
npx task-master next

# 3. Начать работу над задачей
npx task-master start [task_id]

# 4. Если нужно исследование
npx task-master research [task_id] "specific topic"
```

### Еженедельное планирование

```bash
# 1. Обзор прогресса
npx task-master progress --by-phase

# 2. Анализ критического пути
npx task-master critical-path

# 3. Проверка заблокированных задач
npx task-master blocked

# 4. Планирование на следующую неделю
npx task-master plan --next-week
```

### При завершении задачи

```bash
# 1. Отметить задачу как завершенную
npx task-master complete [task_id]

# 2. Проверить разблокированные задачи
npx task-master next

# 3. Обновить статус проекта
npx task-master status
```

## Специфичные команды для нашего проекта

### Для Task 1 (Project Setup)

```bash
# Начать настройку проекта
npx task-master start 1

# Исследовать FastAPI best practices
npx task-master research 1 "FastAPI async patterns for WhatsApp bots"

# Показать подзадачи
npx task-master show 1 --subtasks

# Завершить подзадачу
npx task-master complete 1.1
```

### Для Task 3 (Green API Integration)

```bash
# Исследовать Green API
npx task-master research 3 "Green API webhook security and rate limits"

# Создать тестовый план
npx task-master test-plan 3

# Проверить зависимости
npx task-master dependencies 3
```

### Для критических задач

```bash
# Приоритизировать критические задачи
npx task-master prioritize --critical-path

# Создать план для критического пути
npx task-master plan --critical-only

# Мониторинг рисков
npx task-master risks --high-priority
```

## Интеграция с Git

```bash
# Создать ветку для задачи
npx task-master git-branch 1  # создаст ветку feature/task-001-project-setup

# Коммит с привязкой к задаче
npx task-master git-commit 1 "Implement FastAPI basic structure"

# Создать PR для задачи
npx task-master git-pr 1
```

## Уведомления и мониторинг

```bash
# Настроить уведомления о завершении задач
npx task-master notify --on-complete --sound gentle

# Настроить ежедневные отчеты
npx task-master schedule-report --daily --time 09:00

# Экспорт прогресса
npx task-master export --format json
npx task-master export --format csv
```

## Troubleshooting

### Если команды не работают

```bash
# Проверить версию task-master
npx task-master --version

# Переинициализировать проект
npx task-master init --force

# Проверить конфигурацию
npx task-master config --check

# Восстановить из backup
npx task-master restore --from-backup
```

### Если API ключи не работают

```bash
# Проверить API ключи
npx task-master config --check-keys

# Обновить API ключ
npx task-master config --set ANTHROPIC_API_KEY="new-key"

# Тест подключения к AI
npx task-master test-ai
```

## Полезные алиасы

Добавить в `.bashrc` или `.zshrc`:

```bash
alias tm="npx task-master"
alias tms="npx task-master status"
alias tmn="npx task-master next"
alias tml="npx task-master list"
alias tmr="npx task-master research"
```

Использование:
```bash
tm status
tmn
tml --priority high
tmr 3 "Green API best practices"
```
