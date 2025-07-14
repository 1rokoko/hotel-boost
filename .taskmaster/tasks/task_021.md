# Task 021: Advanced Trigger System with Dynamic Settings

## Описание
Реализация комплексной системы триггеров с динамическими настройками времени, минутными интервалами и интеграцией часового пояса Бангкока

## Приоритет: HIGH
## Сложность: MEDIUM
## Оценка времени: 12 часов
## Зависимости: Task 020

## Детальный план выполнения

### Подзадача 21.1: Global Timezone Update to Bangkok (1 час)
**Файлы для изменения:**
- `app/schemas/hotel_config.py` - обновление default timezone
- `app/schemas/trigger.py` - обновление timezone в trigger схемах

**Детали реализации:**
Изменение default timezone с UTC на Asia/Bangkok во всех конфигурационных файлах и схемах.

**Технические требования:**
- Обновить default timezone в HotelConfig
- Обновить timezone в TriggerCreate/Update схемах
- Обеспечить backward compatibility
- Добавить timezone validation
- Обновить timezone в существующих записях

### Подзадача 21.2: Minutes After First Message Trigger (2 часа)
**Файлы для изменения:**
- `app/templates/admin_dashboard.html` - обновление UI для минутных интервалов

**Детали реализации:**
Изменение типа триггера "Hours After First Message" на "Minutes After First Message" для более быстрого реагирования.

**Технические требования:**
- Изменить UI labels с "hours" на "minutes"
- Обновить validation для минутных интервалов
- Изменить placeholder values
- Обновить help text и tooltips
- Обеспечить корректную обработку в backend

### Подзадача 21.3: Dynamic Trigger Settings Interface (6 часов)
**Файлы для изменения:**
- `app/templates/admin_dashboard.html` - реализация динамических форм

**Детали реализации:**
Создание динамического интерфейса настроек триггеров, который изменяется в зависимости от выбранного типа триггера.

**Технические требования:**
- Функция updateTriggerSettings() для динамического обновления
- Функция buildTriggerConditions() для построения условий
- Dynamic form generation на основе trigger type
- Conditional field visibility
- Real-time form validation
- Settings persistence между изменениями типа

### Подзадача 21.4: Comprehensive Trigger Testing (3 часа)
**Файлы для изменения:**
- `app/templates/admin_dashboard.html` - добавление тестового интерфейса

**Детали реализации:**
Добавление секундных интервалов для быстрого тестирования триггеров в демонстрационных целях.

**Технические требования:**
- Real-time trigger testing interface
- Countdown timers для активных тестов
- Visual feedback system
- Test result logging
- Multiple trigger type testing
- Active trigger management

## Стратегия тестирования

### Функциональные тесты:
- Timezone conversion корректность
- Minutes trigger timing точность
- Dynamic settings обновление
- Trigger creation с новыми настройками
- Backward compatibility с существующими триггерами

### UI тесты:
- Dynamic form behavior
- Field visibility changes
- Validation messages
- User experience flow
- Cross-browser compatibility

### Integration тесты:
- Trigger execution с новыми настройками
- Database timezone handling
- API endpoint compatibility
- Real-time testing functionality

## Критерии завершения

### Функциональные требования:
- [ ] Global timezone изменен на Asia/Bangkok
- [ ] Minutes After First Message trigger реализован
- [ ] Dynamic trigger settings работают корректно
- [ ] Trigger testing interface функционален
- [ ] Все типы триггеров поддерживают новые настройки

### Технические требования:
- [ ] Timezone conversion работает корректно
- [ ] Dynamic forms обновляются без ошибок
- [ ] Validation работает для всех типов триггеров
- [ ] Testing interface показывает real-time результаты
- [ ] Backward compatibility сохранена

### UI/UX требования:
- [ ] Interface интуитивно понятен
- [ ] Dynamic changes плавные и быстрые
- [ ] Error handling user-friendly
- [ ] Testing feedback информативен
- [ ] Mobile responsiveness сохранена

## Связанные документы
- `docs/triggers.md` - trigger system documentation
- `app/schemas/trigger.py` - trigger data models
- `app/services/trigger_service.py` - trigger business logic
- `app/templates/admin_dashboard.html` - admin interface

## Критерии готовности

### Функциональные критерии
- [ ] Bangkok timezone установлен как default
- [ ] Minutes trigger type работает корректно
- [ ] Dynamic settings изменяются в real-time
- [ ] Trigger testing показывает accurate результаты
- [ ] Все существующие триггеры продолжают работать

### Технические критерии
- [ ] Timezone handling корректен во всех компонентах
- [ ] Dynamic form generation без performance issues
- [ ] Trigger validation comprehensive и accurate
- [ ] Testing interface responsive и stable
- [ ] Database migrations выполнены успешно

### Операционные критерии
- [ ] Admin interface user-friendly
- [ ] Testing tools доступны для troubleshooting
- [ ] Documentation обновлена
- [ ] Training materials подготовлены
- [ ] Rollback plan готов

## Примечания
Изменение timezone требует careful testing для обеспечения корректной работы всех time-based операций. Dynamic interface должен быть responsive и intuitive для admin users.
