# Task 011: Admin Dashboard API

## Описание
API для административной панели управления системой

## Приоритет: MEDIUM
## Сложность: MEDIUM
## Оценка времени: 16 часов
## Зависимости: Task 005, Task 008

## Детальный план выполнения

### Подзадача 11.1: API аналитики (4 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/analytics.py` - API аналитики
- `app/services/analytics_service.py` - сервис аналитики
- `app/utils/analytics_aggregator.py` - агрегация данных

**API endpoints:**
```python
@router.get("/dashboard/overview")
async def get_dashboard_overview(hotel_id: str):
    """Общая статистика для дашборда"""

@router.get("/messages/stats")
async def get_message_statistics(hotel_id: str, period: str):
    """Статистика сообщений"""
```

### Подзадача 11.2: API управления пользователями (3 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/users.py` - CRUD пользователей
- `app/services/user_management.py` - управление пользователями
- `app/models/admin_user.py` - модель админ пользователей

### Подзадача 11.3: API системных настроек (3 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/system_settings.py` - системные настройки
- `app/services/system_config.py` - конфигурация системы

### Подзадача 11.4: API отчетов (2 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/reports.py` - генерация отчетов
- `app/services/report_generator.py` - сервис отчетов

### Подзадача 11.5: API мониторинга (2 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/monitoring.py` - мониторинг системы
- `app/services/system_monitor.py` - системный монитор

### Подзадача 11.6: Детальные тесты API (1 час)
**Файлы для создания:**
- `tests/unit/test_admin_api.py` - тесты admin API
- `tests/integration/test_dashboard_endpoints.py` - интеграционные тесты

### Подзадача 11.7: Логирование админ операций (1 час)
**Файлы для создания:**
- `app/core/admin_logging.py` - логирование админ операций
- `app/utils/admin_audit.py` - аудит действий

## Критерии готовности
- [ ] Все admin API endpoints работают
- [ ] Аналитика доступна
- [ ] Отчеты генерируются
- [ ] Мониторинг функционирует
- [ ] Все тесты проходят
- [ ] Покрытие тестами >85%
