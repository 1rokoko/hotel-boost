# 🧹 Инструкции по очистке кеша

## Проблема
В проекте есть многоуровневая система кеширования, которая может показывать старые версии файлов после обновления:

1. **Redis кеш** - основной кеш с TTL от 15 минут до 24 часов
2. **Memory кеш** - локальный кеш в памяти приложения  
3. **Template кеш** - кеширование HTML шаблонов на 1 час
4. **DeepSeek кеш** - кеш AI ответов на 1 час
5. **Browser кеш** - кеш браузера

## 🔧 Пошаговая очистка всех кешей

### 1. Остановить сервер
```bash
# Найти процесс сервера и остановить его
# В Windows:
tasklist | findstr python
taskkill /PID <номер_процесса> /F

# Или просто закрыть терминал с сервером
```

### 2. Очистить Redis кеш
```bash
# Подключиться к Redis и очистить базу
redis-cli
> FLUSHDB
> EXIT

# Или если Redis на другом хосте:
redis-cli -h localhost -p 6379
> FLUSHDB
> EXIT
```

### 3. Удалить файлы кеша (если есть)
```bash
# Удалить временные файлы кеша
rm -rf __pycache__/
rm -rf .pytest_cache/
rm -rf app/__pycache__/
rm -rf app/*/__pycache__/

# В Windows:
del /s /q __pycache__
del /s /q .pytest_cache
```

### 4. Перезапустить сервер
```bash
python minimal_server.py
```

### 5. Очистить кеш браузера
**Вариант 1 - Жесткое обновление:**
- `Ctrl+Shift+R` (Windows/Linux)
- `Cmd+Shift+R` (Mac)

**Вариант 2 - Отключить кеш в DevTools:**
1. Нажать `F12` для открытия DevTools
2. Перейти на вкладку `Network`
3. Поставить галочку `Disable cache`
4. Обновить страницу

**Вариант 3 - Полная очистка кеша:**
1. Chrome: `Settings` → `Privacy and security` → `Clear browsing data`
2. Выбрать `Cached images and files`
3. Нажать `Clear data`

### 6. Проверить изменения
1. Открыть `http://localhost:8002/api/v1/admin/dashboard`
2. Проверить все разделы меню:
   - ✅ Dashboard
   - ✅ Hotels  
   - ✅ Conversations
   - ✅ Triggers
   - ✅ Templates
   - ✅ Sentiment Analytics
   - ✅ Users
   - ✅ Analytics
   - ✅ Monitoring
   - ✅ Security
   - ✅ DeepSeek Testing
   - ✅ DeepSeek Settings
   - ✅ AI Configuration

## 🚨 Если проблема остается

### Проверить, что сервер перезапущен
```bash
# Проверить, что процесс действительно новый
ps aux | grep python  # Linux/Mac
tasklist | findstr python  # Windows
```

### Проверить порт сервера
```bash
# Убедиться, что сервер работает на правильном порту
netstat -an | findstr 8002  # Windows
netstat -an | grep 8002     # Linux/Mac
```

### Использовать режим инкогнито
- Открыть браузер в режиме инкогнито/приватном режиме
- Перейти на `http://localhost:8002/api/v1/admin/dashboard`

### Проверить консоль браузера
1. Нажать `F12`
2. Перейти на вкладку `Console`
3. Искать ошибки JavaScript

## 📝 Что было исправлено

1. **Menu/Section ID Mismatches** - исправлены несоответствия между `data-section` и `id`
2. **Hotels API Format** - исправлена обработка формата данных `{status: 'success', data: Array}`
3. **Monitoring Fallback** - добавлены fallback данные для мониторинга
4. **Missing Functions** - добавлены функции `loadUsers()`, `loadAnalytics()`, `loadMonitoring()`, `loadSecurity()`, `loadAIConfiguration()`

## 🎯 Ожидаемый результат

После очистки всех кешей все 13 разделов админ-панели должны работать корректно и показывать актуальный функционал.
