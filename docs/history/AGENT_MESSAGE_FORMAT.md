# Единый формат обмена данными между агентами

**Дата создания**: 28 января 2026  
**Статус**: Production Ready

## 📋 Обзор

Все агенты в GigaBoard Multi-Agent System обмениваются данными через **AgentMessage** - единый формат сообщений, передаваемых через Redis Message Bus.

## 🔄 Архитектура коммуникации

```
┌─────────────┐                                    ┌─────────────┐
│             │    AgentMessage (TASK_REQUEST)     │             │
│ Orchestrator├────────────────────────────────────>│   Planner   │
│             │                                    │             │
│             │    AgentMessage (TASK_RESULT)      │             │
│             │<────────────────────────────────────┤             │
└─────────────┘                                    └─────────────┘
       │                                                  │
       │                                                  │
       │            AgentMessage (TASK_REQUEST)          │
       ├─────────────────────────────────────────────────>┤
       │                                                  │
       │                                            ┌─────▼──────┐
       │                                            │            │
       │                                            │  Search    │
       │                                            │            │
       │            AgentMessage (TASK_RESULT)      └─────┬──────┘
       │<──────────────────────────────────────────────────┘
       │
       │            AgentMessage (TASK_REQUEST)
       ├───────────────────────────────────────>┌─────────────┐
       │                                        │             │
       │                                        │  Analyst    │
       │        AgentMessage (TASK_RESULT)      │             │
       │<───────────────────────────────────────┤             │
                                                └─────────────┘
```

## 📦 AgentMessage - Единый формат

### Структура

```python
class AgentMessage(BaseModel):
    """Универсальное сообщение для всех агентов."""
    
    # Идентификация
    message_id: str              # UUID сообщения
    message_type: MessageType    # Тип: TASK_REQUEST, TASK_RESULT, etc.
    parent_message_id: Optional[str]  # Для связывания запрос-ответ
    
    # Маршрутизация
    sender: str                  # Имя отправителя (agent name или "orchestrator")
    receiver: str                # Имя получателя (agent name или "broadcast")
    
    # Контекст
    session_id: str              # ID сессии пользователя
    board_id: str                # ID доски
    
    # Данные
    payload: Dict[str, Any]      # Полезная нагрузка (см. ниже)
    
    # Метаданные
    timestamp: str               # ISO timestamp
    requires_acknowledgement: bool
    timeout_seconds: Optional[int]
    retry_count: int
    max_retries: int
```

### Типы сообщений (MessageType)

```python
class MessageType(str, Enum):
    USER_REQUEST = "user_request"           # Orchestrator → Planner
    TASK_REQUEST = "task_request"           # Любой агент → Любой агент
    TASK_RESULT = "task_result"             # Агент → Orchestrator/Planner
    TASK_PROGRESS = "task_progress"         # Агент → UI
    AGENT_QUERY = "agent_query"             # Агент → Агент (запрос данных)
    AGENT_RESPONSE = "agent_response"       # Агент → Агент (ответ)
    ACKNOWLEDGEMENT = "acknowledgement"     # Подтверждение получения
    ERROR = "error"                         # Сообщение об ошибке
    SUGGESTED_ACTIONS = "suggested_actions" # Агент → UI
    NODE_CREATED = "node_created"           # Агент → UI
    UI_NOTIFICATION = "ui_notification"     # Orchestrator → UI
```

## 📤 Payload - Структура полезной нагрузки

### 1. TASK_REQUEST (Orchestrator → Agent)

```json
{
  "task": {
    "type": "web_search|analyze_data|create_plan|...",
    "description": "Human-readable описание задачи",
    // Специфичные для типа задачи параметры
    "query": "статистика кино Москва",
    "max_results": 10
  },
  "context": {
    "pipeline_context": {
      "session_id": "session_123",
      "board_id": "board_456",
      "user_id": "user_789",
      "board_context": { /* компактифицированные данные доски */ }
    },
    "agent_results": [
      {"step_id": "step_1", "agent": "discovery", "payload": { /* AgentPayload */ }},
      {"step_id": "step_2", "agent": "analyst", "payload": { /* AgentPayload */ }}
    ],
    "execution_context": {
      "input_data": { /* DataFrame, тяжёлые данные — не для промптов */ }
    }
  }
}
```

**Важно**: `context.agent_results` — хронологический list результатов от предыдущих агентов. Агенты используют хелперы `_last_result()` / `_all_results()` для доступа.

### 2. TASK_RESULT (Agent → Orchestrator/другой агент)

```json
{
  "status": "success|error|completed",
  "result": {
    // Результат выполнения задачи
    // Формат зависит от агента (см. ниже)
  },
  "execution_time": 2.5,  // секунды
  "agent": "search"
}
```

## 🎯 Форматы результатов от разных агентов

### SearchAgent

```json
{
  "status": "success",
  "query": "статистика кино Москва",
  "results": [
    {
      "title": "Заголовок",
      "url": "https://...",
      "snippet": "Описание..."
    }
  ],
  "summary": "GigaChat суммаризация результатов",
  "sources": ["https://...", "https://..."],
  "timestamp": "2026-01-28T...",
  "result_count": 5,
  "agent": "search"
}
```

### AnalystAgent

```json
{
  "status": "success",
  "analysis_type": "descriptive",
  "insights": [
    {
      "title": "Инсайт 1",
      "description": "Детальное описание"
    }
  ],
  "statistics": {
    "mean": 42,
    "median": 40
  },
  "recommendations": ["Рекомендация 1", "Рекомендация 2"],
  "agent": "analyst"
}
```

### PlannerAgent

```json
{
  "status": "success",
  "plan_id": "uuid",
  "user_request": "Найди статистику...",
  "steps": [
    {
      "step_id": "1",
      "agent": "search",
      "task": {
        "type": "web_search",
        "query": "...",
        "max_results": 10
      },
      "description": "Поиск в интернете",
      "depends_on": [],
      "expected_output": "список результатов поиска"
    }
  ],
  "reasoning": "Почему выбрана эта стратегия",
  "estimated_time": 30,
  "agent": "planner"
}
```

### ReporterAgent

```json
{
  "status": "success",
  "visualization_type": "chart|table|map|custom",
  "widget_node": {
    "html": "<html>...</html>",
    "css": "...",
    "javascript": "..."
  },
  "data_bindings": {
    "dataNodeId": "node_123",
    "fields": ["name", "value"]
  },
  "agent": "reporter"
}
```

## 🔗 Передача данных между агентами

### Паттерн 1: Последовательная цепочка (через Orchestrator)

```python
# Orchestrator отправляет SearchAgent
search_message = AgentMessage(
    message_type=MessageType.TASK_REQUEST,
    sender="orchestrator",
    receiver="search",
    payload={
        "task": {"type": "web_search", "query": "..."},
        "context": {"session_id": "..."}
    }
)

# Получает результат от SearchAgent
search_result = {
    "status": "success",
    "results": [...],
    "summary": "..."
}

# Передаёт AnalystAgent через context.agent_results
analyst_message = AgentMessage(
    message_type=MessageType.TASK_REQUEST,
    sender="orchestrator",
    receiver="analyst",
    payload={
        "task": {"type": "analyze_data"},
        "context": {
            "pipeline_context": {"session_id": "..."},
            "agent_results": [
                {"step_id": "step_1", "agent": "search", "payload": search_result}
            ]
        }
    }
)
```

### Паттерн 2: Прямая коммуникация (Agent → Agent)

```python
# AnalystAgent запрашивает данные у ResearcherAgent
query_message = AgentMessage(
    message_type=MessageType.AGENT_QUERY,
    sender="analyst",
    receiver="researcher",
    payload={
        "query_type": "fetch_from_database",
        "table": "sales",
        "filters": {"region": "Moscow"}
    }
)

# ResearcherAgent отвечает
response_message = AgentMessage(
    message_type=MessageType.AGENT_RESPONSE,
    sender="researcher",
    receiver="analyst",
    parent_message_id=query_message.message_id,
    payload={
        "status": "success",
        "data": [{"region": "Moscow", "sales": 100}]
    }
)
```

## 📋 Правила обработки в BaseAgent

```python
class BaseAgent(ABC):
    async def _handle_message(self, message: AgentMessage):
        """Обрабатывает входящее сообщение."""
        
        # 1. Проверяем тип
        if message.message_type != MessageType.TASK_REQUEST:
            return
            
        # 2. Проверяем адресата
        if message.receiver != self.agent_name:
            return
            
        # 3. Извлекаем task и context
        task = message.payload.get("task", {})
        context = message.payload.get("context", {})
        
        # 4. Обрабатываем задачу
        result = await self.process_task(task, context)
        
        # 5. Отправляем результат обратно
        response = AgentMessage(
            message_id=str(uuid4()),
            message_type=MessageType.TASK_RESULT,
            sender=self.agent_name,
            receiver=message.sender,
            session_id=message.session_id,
            board_id=message.board_id,
            parent_message_id=message.message_id,  # ← Связываем с запросом
            payload={
                "status": "success",
                "result": result,
                "execution_time": ...,
                "agent": self.agent_name
            }
        )
        
        await self.message_bus.publish(response)
```

## ✅ Ключевые преимущества единого формата

1. **Универсальность** - все агенты используют одинаковую структуру
2. **Трассируемость** - `parent_message_id` связывает запросы с ответами
3. **Контекст** - `context.agent_results` (хронологический list) передаёт данные между агентами
4. **Типобезопасность** - Pydantic валидирует все сообщения
5. **Асинхронность** - Redis Pub/Sub для неблокирующей коммуникации
6. **Масштабируемость** - агенты могут работать на разных машинах

## 🔍 Debugging

### Просмотр сообщений в Redis

```bash
# Подписаться на все каналы агентов
redis-cli
PSUBSCRIBE gigaboard:*

# Посмотреть историю (если включена)
LRANGE gigaboard:message_history 0 100
```

### Логирование в коде

```python
logger.info(f"📤 Sending TASK_REQUEST to {agent_name}")
logger.info(f"   message_id: {message.message_id}")
logger.info(f"   parent_id: {message.parent_message_id}")
logger.info(f"   payload: {json.dumps(message.payload, indent=2)}")
```

## 📚 См. также

- [MULTI_AGENT_SYSTEM.md](./MULTI_AGENT_SYSTEM.md) - Полная архитектура
- [apps/backend/app/services/multi_agent/message_types.py](../apps/backend/app/services/multi_agent/message_types.py) - Код
- [apps/backend/app/services/multi_agent/message_bus.py](../apps/backend/app/services/multi_agent/message_bus.py) - MessageBus
- [tests/test_cinema_with_messagebus.py](../apps/backend/tests/test_cinema_with_messagebus.py) - Пример использования
