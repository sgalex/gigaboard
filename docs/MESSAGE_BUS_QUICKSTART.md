# Message Bus Quick Start Guide

**Для разработчиков GigaBoard Multi-Agent System**

Этот документ — краткая справка по работе с Message Bus. Полная документация: [MULTI_AGENT_SYSTEM.md](./MULTI_AGENT_SYSTEM.md#agent-communication-protocol)

---

## 🚀 Быстрый старт

### 1. Инициализация Message Bus

```python
from apps.backend.app.services.multi_agent.message_bus import AgentMessageBus

# В FastAPI lifespan (при старте приложения)
async def startup():
    message_bus = AgentMessageBus(redis_url="redis://localhost:6379")
    await message_bus.connect()
    return message_bus
```

### 2. Подписка агента на сообщения

```python
from apps.backend.app.services.multi_agent.message_bus import AgentMessage, MessageType

async def my_agent_callback(message: AgentMessage):
    """Обработчик сообщений для агента"""
    
    if message.message_type == MessageType.TASK_REQUEST:
        # Обработать задачу
        print(f"Received task: {message.payload}")
        
        # Отправить результат
        result = AgentMessage(
            message_type=MessageType.TASK_RESULT,
            sender="my_agent",
            receiver="orchestrator",
            session_id=message.session_id,
            board_id=message.board_id,
            parent_message_id=message.message_id,
            success=True,
            payload={"result": "Task completed"}
        )
        await message_bus.publish(result)

# Подписываемся
await message_bus.subscribe("my_agent", my_agent_callback)
```

### 3. Отправка сообщения

```python
# Простая отправка (fire-and-forget)
message = AgentMessage(
    message_type=MessageType.TASK_REQUEST,
    sender="planner",
    receiver="researcher",
    session_id="session_123",
    board_id="board_456",
    payload={"task": "fetch_data"}
)
await message_bus.publish(message)

# Отправка с ожиданием ACK
message.requires_acknowledgement = True
await message_bus.publish(message, wait_for_ack=True)

# Request-Response паттерн (блокирующий)
response = await message_bus.request_response(message, timeout=30)
print(f"Got response: {response.payload}")
```

---

## 📡 Redis Channels — Шпаргалка

| Канал                                         | Когда использовать                                |
| --------------------------------------------- | ------------------------------------------------- |
| `gigaboard:board:{board_id}:agents:broadcast` | Новый user request, нужно чтобы все агенты узнали |
| `gigaboard:agents:{agent_name}:inbox`         | Отправить задачу конкретному агенту               |
| `gigaboard:board:{board_id}:agents:ui_events` | Отправить событие в UI (progress, node created)   |
| `gigaboard:sessions:{session_id}:results`     | Вернуть результат orchestrator'у                  |
| `gigaboard:agents:errors`                     | Ошибка, которую должен видеть monitoring          |

**Message Bus сам выбирает канал** на основе `receiver` в `AgentMessage`.

---

## 📬 MessageType — Когда что использовать

| Тип                 | От кого            | Кому         | Когда                            |
| ------------------- | ------------------ | ------------ | -------------------------------- |
| `USER_REQUEST`      | Orchestrator       | broadcast    | Новый запрос пользователя        |
| `TASK_REQUEST`      | Любой агент        | Другой агент | Делегировать задачу              |
| `TASK_RESULT`       | Агент              | Orchestrator | Задача выполнена                 |
| `TASK_PROGRESS`     | Агент              | UI           | Показать прогресс пользователю   |
| `AGENT_QUERY`       | Агент              | Агент        | Запросить информацию             |
| `AGENT_RESPONSE`    | Агент              | Агент        | Ответ на AGENT_QUERY             |
| `ACKNOWLEDGEMENT`   | Агент              | Sender       | "Я получил твоё сообщение"       |
| `ERROR`             | Агент              | Orchestrator | Ошибка выполнения                |
| `SUGGESTED_ACTIONS` | Reporter/Developer | UI           | Предложить действия пользователю |
| `NODE_CREATED`      | Агент              | UI           | Нода создана на canvas           |

---

## ⏱️ Таймауты

```python
from apps.backend.app.services.multi_agent.message_bus import TimeoutConfig

# Получить рекомендуемый таймаут
timeout = TimeoutConfig.get_timeout(
    message_type=MessageType.TASK_REQUEST,
    agent_name="researcher"
)
# → 120 секунд (researcher может долго скачивать данные)

# Дефолтные таймауты:
# - USER_REQUEST: 120s
# - TASK_REQUEST: 60s
# - AGENT_QUERY: 10s
# - ACKNOWLEDGEMENT: 5s
# - HEARTBEAT: 3s
```

---

## 🔄 Retry Logic

```python
from apps.backend.app.services.multi_agent.message_bus import send_with_retry

# Автоматический retry с exponential backoff
success = await send_with_retry(
    message_bus,
    message,
    max_retries=3,
    backoff_factor=2.0  # 1s, 2s, 4s
)

if not success:
    logger.error("Failed to send message after 3 retries")
```

---

## 📊 Мониторинг и метрики

```python
from apps.backend.app.services.multi_agent.metrics import MessageBusMonitor

# Создать монитор
monitor = MessageBusMonitor(message_bus)
await monitor.start()

# Получить метрики
metrics = monitor.get_metrics()
print(metrics)
# {
#   "messages_sent": 1234,
#   "messages_received": 1200,
#   "success_rate": 0.97,
#   "avg_delivery_time_ms": 45.2,
#   ...
# }
```

---

## 🎯 Типичные паттерны

### Паттерн 1: Простая делегация задачи

```python
# Planner → Researcher
task = AgentMessage(
    message_type=MessageType.TASK_REQUEST,
    sender="planner",
    receiver="researcher",
    session_id=session_id,
    board_id=board_id,
    payload={"task": "fetch_sales_data", "date_from": "2026-01-01"}
)
await message_bus.publish(task)
```

### Паттерн 2: Progress updates для UI

```python
# Researcher → UI (во время работы)
progress = AgentMessage(
    message_type=MessageType.TASK_PROGRESS,
    sender="researcher",
    receiver="orchestrator",  # Orchestrator пробросит в UI
    session_id=session_id,
    board_id=board_id,
    parent_message_id=task.message_id,
    payload={
        "progress_percent": 50,
        "status": "Fetching data from PostgreSQL...",
        "rows_fetched": 5000
    },
    ui_display={
        "agent_name": "Researcher",
        "message": "📊 Получено 5,000 записей (50%)",
        "progress_bar": 50
    }
)
await message_bus.publish(progress)
```

### Паттерн 3: Suggested Actions

```python
# Reporter → UI (предложить создать виджет)
suggested = AgentMessage(
    message_type=MessageType.SUGGESTED_ACTIONS,
    sender="reporter",
    receiver="orchestrator",
    session_id=session_id,
    board_id=board_id,
    payload={
        "actions": [
            {
                "id": "action_1",
                "type": "create_widget",
                "title": "Создать линейный график продаж",
                "params": {
                    "widget_type": "chart",
                    "source_datanode_id": datanode_id,
                    "chart_config": {...}
                }
            }
        ]
    }
)
await message_bus.publish(suggested)
```

### Паттерн 4: Error handling

```python
# Agent → Orchestrator (ошибка)
error = AgentMessage(
    message_type=MessageType.ERROR,
    sender="researcher",
    receiver="orchestrator",
    session_id=session_id,
    board_id=board_id,
    parent_message_id=task_message_id,
    success=False,
    error_message="Database connection timeout",
    payload={
        "error_type": "timeout",
        "error_code": "DB_TIMEOUT",
        "retryable": True
    },
    ui_display={
        "message": "❌ Не удалось подключиться к базе данных",
        "show_retry_button": True
    }
)
await message_bus.publish(error)
```

---

## 🧪 Тестирование

```python
import pytest
from apps.backend.app.services.multi_agent.message_bus import AgentMessageBus, AgentMessage

@pytest.mark.asyncio
async def test_message_delivery():
    """Тест доставки сообщений"""
    
    # Setup
    message_bus = AgentMessageBus("redis://localhost:6379")
    await message_bus.connect()
    
    received_messages = []
    
    async def callback(msg: AgentMessage):
        received_messages.append(msg)
    
    # Subscribe
    await message_bus.subscribe("test_agent", callback)
    
    # Send message
    test_msg = AgentMessage(
        message_type=MessageType.TASK_REQUEST,
        sender="test_sender",
        receiver="test_agent",
        session_id="test_session",
        board_id="test_board",
        payload={"test": "data"}
    )
    
    await message_bus.publish(test_msg)
    
    # Wait for delivery
    await asyncio.sleep(0.5)
    
    # Assert
    assert len(received_messages) == 1
    assert received_messages[0].payload["test"] == "data"
    
    # Cleanup
    await message_bus.disconnect()
```

---

## ⚠️ Best Practices

### DO ✅

- **Всегда заполняй `session_id` и `board_id`** — это нужно для трекинга
- **Используй `parent_message_id`** для связывания ответов с запросами
- **Отправляй ACK** когда `requires_acknowledgement=True`
- **Обрабатывай ошибки** — оборачивай callback в try/except
- **Закрывай соединения** — вызывай `await message_bus.disconnect()` при shutdown
- **Проверяй `message_type`** перед обработкой payload
- **Логируй** все важные события (отправка, получение, ошибки)

### DON'T ❌

- **Не блокируй callback** — используй async, не sync код
- **Не игнорируй таймауты** — всегда проверяй, что сообщение доставлено
- **Не отправляй огромные payload** — >1MB будет медленно, используй ссылки на данные
- **Не подписывайся на один inbox дважды** — один агент = одна подписка
- **Не забывай про cleanup** — отписывайся при shutdown агента
- **Не hardcode receiver names** — используй константы или конфиг

---

## 🔗 Дополнительные ресурсы

- [Полная документация Message Bus](./MULTI_AGENT_SYSTEM.md#agent-communication-protocol)
- [Sequence diagrams](./MULTI_AGENT_SYSTEM.md#message-bus-communication-flow-sequence-diagram)
- [Примеры использования](./MULTI_AGENT_SYSTEM.md#example-complete-message-bus-setup)
- [Timeout и retry logic](./MULTI_AGENT_SYSTEM.md#timeout-management)
- [Мониторинг и метрики](./MULTI_AGENT_SYSTEM.md#message-bus-monitoring--metrics)

---

**Вопросы?** См. [MULTI_AGENT_SYSTEM.md](./MULTI_AGENT_SYSTEM.md) или обратись к команде.
