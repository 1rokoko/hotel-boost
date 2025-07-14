# Task 007: Guest Conversation Handler

## Описание
Обработчик разговоров с гостями, управление состояниями диалогов

## Приоритет: HIGH
## Сложность: HIGH
## Оценка времени: 20 часов
## Зависимости: Task 003, Task 004

## Детальный план выполнения

### Подзадача 7.1: Модели разговоров (3 часа)
**Файлы для создания:**
- `app/models/conversation.py` - SQLAlchemy модель разговоров
- `app/schemas/conversation.py` - Pydantic схемы для API
- `app/services/conversation_service.py` - бизнес-логика разговоров

**Детали реализации:**
```python
# app/models/conversation.py
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID, ForeignKey("hotels.id"), nullable=False)
    guest_id = Column(UUID, ForeignKey("guests.id"), nullable=False)
    status = Column(Enum(ConversationStatus), default=ConversationStatus.ACTIVE)
    current_state = Column(String(50), default="greeting")
    context = Column(JSONB, default={})
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Состояния разговора:**
- **greeting**: Приветствие гостя
- **collecting_info**: Сбор информации
- **processing_request**: Обработка запроса
- **waiting_response**: Ожидание ответа
- **escalated**: Передано персоналу
- **completed**: Завершено

### Подзадача 7.2: Машина состояний (4 часа)
**Файлы для создания:**
- `app/services/conversation_state_machine.py` - FSM для диалогов
- `app/utils/state_transitions.py` - правила переходов
- `app/schemas/state_machine.py` - схемы состояний

**Детали реализации:**
```python
# app/services/conversation_state_machine.py
class ConversationStateMachine:
    def __init__(self, conversation: Conversation):
        self.conversation = conversation
        self.current_state = conversation.current_state

    async def process_message(self, message: str) -> StateTransition:
        """Обработка сообщения и переход состояния"""

    async def transition_to(self, new_state: str, context: dict = None):
        """Переход в новое состояние"""

    def can_transition_to(self, target_state: str) -> bool:
        """Проверка возможности перехода"""
```

**Правила переходов:**
- greeting → collecting_info (при получении сообщения)
- collecting_info → processing_request (при достаточной информации)
- processing_request → waiting_response (при отправке ответа)
- any_state → escalated (при негативном настроении)

### Подзадача 7.3: Обработчик сообщений (4 часа)
**Файлы для создания:**
- `app/services/message_handler.py` - основной обработчик
- `app/utils/message_parser.py` - парсинг сообщений
- `app/tasks/process_message.py` - Celery задачи
- `app/utils/intent_classifier.py` - классификация намерений

**Детали реализации:**
```python
# app/services/message_handler.py
class MessageHandler:
    async def handle_incoming_message(self, webhook_data: dict):
        """Обработка входящего сообщения"""

    async def classify_intent(self, message: str) -> MessageIntent:
        """Классификация намерения сообщения"""

    async def route_to_handler(self, intent: MessageIntent, conversation: Conversation):
        """Маршрутизация к соответствующему обработчику"""
```

**Типы намерений:**
- **booking_inquiry**: Вопросы о бронировании
- **complaint**: Жалобы
- **request_service**: Запросы услуг
- **general_question**: Общие вопросы
- **emergency**: Экстренные ситуации

### Подзадача 7.4: Контекстная память (3 часа)
**Файлы для создания:**
- `app/services/conversation_memory.py` - управление контекстом
- `app/utils/context_manager.py` - менеджер контекста
- `app/models/conversation_context.py` - модель контекста

**Детали реализации:**
```python
# app/services/conversation_memory.py
class ConversationMemory:
    async def store_context(self, conversation_id: str, key: str, value: any):
        """Сохранение контекста разговора"""

    async def get_context(self, conversation_id: str, key: str = None):
        """Получение контекста разговора"""

    async def update_guest_preferences(self, guest_id: str, preferences: dict):
        """Обновление предпочтений гостя"""
```

**Типы контекста:**
- **current_request**: Текущий запрос
- **guest_preferences**: Предпочтения гостя
- **conversation_history**: История разговора
- **pending_actions**: Ожидающие действия

### Подзадача 7.5: API разговоров (2 часа)
**Файлы для создания:**
- `app/api/v1/endpoints/conversations.py` - REST API endpoints
- `app/schemas/conversation_api.py` - схемы для API

**Детали реализации:**
```python
@router.get("/", response_model=List[ConversationResponse])
async def get_conversations(hotel_id: str, status: ConversationStatus = None):
    """Получение списка разговоров отеля"""

@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str):
    """Получение детальной информации о разговоре"""

@router.post("/{conversation_id}/escalate")
async def escalate_conversation(conversation_id: str):
    """Эскалация разговора к персоналу"""
```

### Подзадача 7.6: Детальные тесты разговоров (2 часа)
**Файлы для создания:**
- `tests/unit/test_conversation_handler.py` - тесты обработчика
- `tests/unit/test_state_machine.py` - тесты машины состояний
- `tests/integration/test_conversation_flow.py` - интеграционные тесты

**Детали реализации:**
```python
def test_conversation_state_transitions():
    """Тест переходов между состояниями"""

def test_message_intent_classification():
    """Тест классификации намерений"""

def test_context_preservation():
    """Тест сохранения контекста"""

def test_escalation_triggers():
    """Тест триггеров эскалации"""
```

### Подзадача 7.7: Логирование разговоров (1 час)
**Файлы для создания:**
- `app/core/conversation_logging.py` - логирование диалогов
- `app/utils/conversation_analytics.py` - аналитика разговоров

**Структура логов:**
```json
{
  "timestamp": "2025-07-11T07:00:00Z",
  "component": "conversation_handler",
  "operation": "process_message",
  "conversation_id": "uuid-here",
  "guest_id": "uuid-here",
  "state_transition": "greeting -> collecting_info",
  "intent": "booking_inquiry",
  "response_time_ms": 150
}
```

### Подзадача 7.8: Эскалация к персоналу (1 час)
**Файлы для создания:**
- `app/services/escalation_service.py` - сервис эскалации
- `app/utils/escalation_rules.py` - правила эскалации

**Правила эскалации:**
- Негативное настроение (score < -0.5)
- Ключевые слова жалоб
- Повторные запросы без решения
- Экстренные ситуации

## Критерии готовности
- [ ] Разговоры обрабатываются корректно
- [ ] Машина состояний работает
- [ ] Контекст сохраняется
- [ ] Эскалация функционирует
- [ ] Все тесты проходят
- [ ] Покрытие тестами >85%
