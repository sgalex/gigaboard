# Multi-Agent Message Bus - Phase 1 Complete ✅

## Что реализовано

### 1. Redis Pub/Sub Infrastructure
- ✅ `message_types.py` - MessageType enum (11 типов), AgentMessage schema
- ✅ `redis_config.py` - Redis connection, channel patterns
- ✅ `exceptions.py` - Custom exceptions

### 2. AgentMessageBus
- ✅ `message_bus.py` - Полная реализация Message Bus
  - `publish()` - публикация сообщений
  - `subscribe()` - подписка агентов
  - `request_response()` - синхронные запросы
  - Message history с TTL в Redis
  - Статистика (sent/received/errors)

### 3. Timeout & Retry Management
- ✅ `config.py` - TimeoutConfig, RetryConfig
- ✅ `timeout_monitor.py` - TimeoutMonitor для отслеживания застрявших сообщений
- ✅ `retry_logic.py` - Exponential backoff retry (1s → 2s → 4s)

### 4. Monitoring & Metrics
- ✅ `metrics.py` - MessageBusMetrics, MessageBusMonitor
  - Метрики по типам сообщений
  - Метрики по агентам (sender/receiver)
  - Delivery time (avg/max)
  - Error tracking
  - Alert thresholds

---

## Структура файлов

```
apps/backend/app/services/multi_agent/
├── __init__.py                # Public exports
├── message_types.py           # MessageType, AgentMessage
├── redis_config.py            # Redis connection & channels
├── message_bus.py             # AgentMessageBus (core)
├── exceptions.py              # Custom exceptions
├── config.py                  # TimeoutConfig, RetryConfig
├── timeout_monitor.py         # TimeoutMonitor
├── retry_logic.py             # send_with_retry, retry_async_operation
├── metrics.py                 # MessageBusMetrics, MessageBusMonitor
└── test_message_bus.py        # Тесты
```

---

## Quick Start

### 1. Тестирование Message Bus

```bash
# Убедитесь, что Redis запущен
# Windows:
redis-server

# Запустите тесты
cd apps/backend
python -m app.services.multi_agent.test_message_bus
```

### 2. Использование в коде

```python
from app.services.multi_agent import AgentMessageBus, MessageType, AgentMessage
from uuid import uuid4

# Создать и подключить Message Bus
bus = AgentMessageBus()
await bus.connect()

# Публикация сообщения
message = AgentMessage(
    message_id=str(uuid4()),
    message_type=MessageType.USER_REQUEST,
    sender="orchestrator",
    receiver="broadcast",
    session_id="session_123",
    board_id="board_456",
    payload={"message": "Создай график продаж"}
)
await bus.publish(message)

# Подписка на сообщения
async def handle_message(msg: AgentMessage):
    print(f"Received: {msg.message_type} from {msg.sender}")

await bus.subscribe("planner", handle_message)

# Получить статистику
stats = await bus.get_stats()
print(f"Messages sent: {stats['messages_sent']}")

# Отключиться
await bus.disconnect()
```

---

## Типы сообщений (MessageType)

| Type                | Sender       | Receiver             | Description             |
| ------------------- | ------------ | -------------------- | ----------------------- |
| `USER_REQUEST`      | Orchestrator | Broadcast            | Запрос пользователя     |
| `TASK_REQUEST`      | Planner      | Agent                | Делегирование задачи    |
| `TASK_RESULT`       | Agent        | Orchestrator/Planner | Результат выполнения    |
| `TASK_PROGRESS`     | Agent        | UI                   | Прогресс выполнения     |
| `AGENT_QUERY`       | Agent        | Agent                | Межагентный запрос      |
| `AGENT_RESPONSE`    | Agent        | Agent                | Ответ на запрос         |
| `ACKNOWLEDGEMENT`   | Any          | Any                  | Подтверждение получения |
| `ERROR`             | Agent        | Orchestrator         | Ошибка                  |
| `SUGGESTED_ACTIONS` | Agent        | UI                   | Предложения действий    |
| `NODE_CREATED`      | Agent        | UI                   | Создан новый узел       |
| `UI_NOTIFICATION`   | Orchestrator | UI                   | Уведомление             |

---

## Redis Channels

### Broadcast
```
gigaboard:board:{board_id}:agents:broadcast
```
Все агенты подписаны, получают USER_REQUEST.

### Agent Inbox (Direct)
```
gigaboard:agents:{agent_name}:inbox
```
Личные сообщения для конкретного агента.

### UI Events
```
gigaboard:board:{board_id}:agents:ui_events
```
События для фронтенда (NODE_CREATED, UI_NOTIFICATION).

### Session Results
```
gigaboard:sessions:{session_id}:results
```
Orchestrator подписан, получает TASK_RESULT.

### Errors
```
gigaboard:agents:errors
```
Централизованный канал ошибок.

---

## Timeout Configuration

### По типам сообщений
- `USER_REQUEST`: 30s
- `TASK_REQUEST`: 60s
- `TASK_RESULT`: 120s
- `AGENT_QUERY`: 10s

### По агентам (переопределяют тип)
- `planner`: 30s
- `researcher`: 120s (долгие SQL/HTTP запросы)
- `executor`: 300s (долгое выполнение кода)

---

## Retry Logic

### Exponential Backoff
- 1st retry: 1s delay
- 2nd retry: 2s delay
- 3rd retry: 4s delay
- Max retries: 3

### Пример
```python
from app.services.multi_agent.retry_logic import send_with_retry

# Отправить с retry
success = await send_with_retry(
    message_bus=bus,
    message=message,
    max_retries=3
)
```

---

## Metrics & Monitoring

### Сбор метрик
```python
from app.services.multi_agent.metrics import MessageBusMetrics

metrics = MessageBusMetrics()
metrics.record_message_sent(MessageType.TASK_REQUEST, "planner", "researcher")
metrics.record_delivery_time(1250)  # microseconds

summary = metrics.get_summary()
print(f"Total messages: {summary['total_messages']}")
print(f"Avg delivery time: {summary['delivery_time_avg_ms']}ms")
```

### Мониторинг с алертами
```python
from app.services.multi_agent.metrics import MessageBusMonitor

monitor = MessageBusMonitor(
    latency_threshold_ms=100,
    error_rate_threshold=0.05
)

alerts = monitor.check_thresholds(metrics)
if alerts:
    for alert in alerts:
        logger.warning(f"ALERT: {alert}")
```

---

## Next Steps (Phase 2)

- [ ] Создать AgentSession model (SQLAlchemy)
- [ ] Реализовать AgentSessionManager
- [ ] Реализовать MultiAgentOrchestrator
- [ ] Интегрировать с AIService

См. `docs/MULTI_AGENT_SYSTEM.md` для полного roadmap.

---

## Troubleshooting

### Redis connection failed
```bash
# Убедитесь, что Redis запущен
redis-cli ping
# Должен вернуть PONG

# Проверьте настройки в config.py
REDIS_HOST = "localhost"
REDIS_PORT = 6379
```

### Сообщения не доставляются
```python
# Проверьте статистику
stats = await bus.get_stats()
print(stats)

# Проверьте Redis каналы
# redis-cli
# > PUBSUB CHANNELS gigaboard:*
```

### Timeouts
```python
# Увеличьте timeout для конкретного типа
from app.services.multi_agent.config import TimeoutConfig
TimeoutConfig.MESSAGE_TIMEOUTS[MessageType.TASK_REQUEST] = 120
```
