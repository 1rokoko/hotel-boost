# Task 012: Authentication and Authorization

## Описание
Система аутентификации и авторизации пользователей

## Приоритет: HIGH
## Сложность: MEDIUM
## Оценка времени: 12 часов
## Зависимости: Task 002, Task 011

## Детальный план выполнения

### Подзадача 12.1: JWT аутентификация (3 часа)
**Файлы для создания:**
- `app/core/security.py` - основная безопасность
- `app/services/auth_service.py` - сервис аутентификации
- `app/utils/jwt_handler.py` - обработка JWT токенов

**Детали реализации:**
```python
class AuthService:
    async def authenticate_user(self, email: str, password: str) -> User:
        """Аутентификация пользователя"""

    async def create_access_token(self, user: User) -> str:
        """Создание access токена"""

    async def refresh_token(self, refresh_token: str) -> str:
        """Обновление токена"""
```

### Подзадача 12.2: Модели пользователей и ролей (2 часа)
**Файлы для создания:**
- `app/models/user.py` - модель пользователей
- `app/models/role.py` - модель ролей
- `app/schemas/auth.py` - схемы аутентификации

**Роли системы:**
- **super_admin**: Полный доступ ко всей системе
- **hotel_admin**: Администратор отеля
- **hotel_staff**: Персонал отеля
- **viewer**: Только просмотр

### Подзадача 12.3: API аутентификации (2 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/auth.py` - endpoints аутентификации
- `app/schemas/auth_api.py` - схемы API

### Подзадача 12.4: Middleware авторизации (2 часа)
**Файлы для создания:**
- `app/middleware/auth_middleware.py` - middleware авторизации
- `app/utils/permission_checker.py` - проверка прав

### Подзадача 12.5: RBAC система (2 часа)
**Файлы для создания:**
- `app/services/rbac_service.py` - RBAC сервис
- `app/utils/role_manager.py` - управление ролями

### Подзадача 12.6: Детальные тесты авторизации (1 час)
**Файлы для создания:**
- `tests/unit/test_auth_service.py` - тесты аутентификации
- `tests/integration/test_auth_endpoints.py` - интеграционные тесты

## Критерии готовности
- [ ] JWT аутентификация работает
- [ ] RBAC система функционирует
- [ ] API защищено
- [ ] Роли и права настраиваются
- [ ] Все тесты проходят
- [ ] Покрытие тестами >85%
