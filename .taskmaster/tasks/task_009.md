# Task 009: Message Templates and Responses

## Описание
Система шаблонов сообщений и автоматических ответов

## Приоритет: MEDIUM
## Сложность: MEDIUM
## Оценка времени: 12 часов
## Зависимости: Task 004, Task 006

## Детальный план выполнения

### Подзадача 9.1: Модели шаблонов (2 часа)
**Файлы для создания:**
- `app/models/message_template.py` - SQLAlchemy модель шаблонов
- `app/schemas/template.py` - Pydantic схемы
- `app/services/template_service.py` - бизнес-логика шаблонов

**Детали реализации:**
```python
class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID, ForeignKey("hotels.id"), nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(Enum(TemplateCategory), nullable=False)
    content = Column(Text, nullable=False)
    variables = Column(JSONB, default=[])  # ["guest_name", "room_number"]
    language = Column(String(5), default="en")
    is_active = Column(Boolean, default=True)
```

### Подзадача 9.2: Движок шаблонов (3 часа)
**Файлы для создания:**
- `app/services/template_engine.py` - движок рендеринга
- `app/utils/template_renderer.py` - рендерер Jinja2
- `app/utils/variable_resolver.py` - резолвер переменных

**Детали реализации:**
```python
class TemplateEngine:
    async def render_template(self, template: MessageTemplate, context: dict) -> str:
        """Рендеринг шаблона с контекстом"""

    async def validate_template(self, content: str, variables: list) -> bool:
        """Валидация синтаксиса шаблона"""

    async def get_template_variables(self, content: str) -> list:
        """Извлечение переменных из шаблона"""
```

### Подзадача 9.3: API управления шаблонами (2 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/templates.py` - REST API
- `app/schemas/template_api.py` - схемы API

**API endpoints:**
```python
@router.post("/", response_model=TemplateResponse)
async def create_template(template: TemplateCreate):
    """Создание нового шаблона"""

@router.get("/preview")
async def preview_template(template_id: str, context: dict):
    """Предварительный просмотр шаблона"""
```

### Подзадача 9.4: Автоматические ответы (2 часа)
**Файлы для создания:**
- `app/services/auto_responder.py` - автоответчик
- `app/utils/response_matcher.py` - сопоставление
- `app/models/auto_response_rule.py` - правила автоответов

**Логика автоответов:**
- Ключевые слова в сообщении
- Время суток
- Статус разговора
- Предыдущие сообщения

### Подзадача 9.5: Мультиязычность (2 часа)
**Файлы для создания:**
- `app/services/i18n_service.py` - интернационализация
- `app/utils/language_detector.py` - определение языка

**Поддерживаемые языки:**
- Английский (en)
- Русский (ru)
- Испанский (es)
- Французский (fr)

### Подзадача 9.6: Детальные тесты шаблонов (1 час)
**Файлы для создания:**
- `tests/unit/test_template_engine.py` - тесты движка
- `tests/unit/test_auto_responder.py` - тесты автоответов
- `tests/integration/test_template_api.py` - интеграционные тесты

**Тестовые сценарии:**
```python
def test_template_rendering_with_variables():
    """Тест рендеринга с переменными"""

def test_auto_response_matching():
    """Тест сопоставления автоответов"""

def test_multilingual_template_selection():
    """Тест выбора шаблона по языку"""
```

## Критерии готовности
- [ ] Шаблоны создаются и рендерятся
- [ ] Автоответы работают
- [ ] Мультиязычность поддерживается
- [ ] API функционирует
- [ ] Все тесты проходят
- [ ] Покрытие тестами >85%
