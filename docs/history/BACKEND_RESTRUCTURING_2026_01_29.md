# Backend Restructuring - 2026-01-29

## Что было сделано

### 1. Создана структура `core/` для инфраструктуры

Создана папка `apps/backend/app/core/` с модулями:

- **`__init__.py`** - экспорты всех core компонентов
- **`config.py`** - Settings (перемещён из `app/config.py`)
- **`database.py`** - SQLAlchemy setup (перемещён из `app/database.py`)
- **`redis.py`** - Redis client (перемещён из `app/redis_client.py`)
- **`socketio.py`** - Socket.IO server + event handlers (объединены `socketio_instance.py` + `socketio_events.py`)

### 2. Удалены старые файлы

Из корня `app/` удалены:
- `config.py`
- `database.py`
- `redis_client.py`
- `socketio_instance.py`
- `socketio_events.py`

### 3. Удалены deprecated файлы

Удалены устаревшие файлы:
- `models/_widget_deprecated.py`
- `routes/_widgets_deprecated.py`
- `schemas/_widget_deprecated.py`
- `services/_widget_service_deprecated.py`
- `services/_edge_service_deprecated.py`

### 4. Обновлены все импорты

#### Импорты через `app.core`:
```python
# Было:
from app.database import get_db, Base
from app.config import settings
from app.redis_client import get_redis
from app.socketio_instance import sio

# Стало:
from app.core import get_db, Base, settings, get_redis, sio
```

#### Относительные импорты:
```python
# Было:
from ..database import get_db
from ..config import settings

# Стало:
from ..core import get_db, settings
```

#### Файлы с обновлёнными импортами:
- `app/main.py` - основной файл приложения
- `app/routes/*.py` - все route handlers (9 файлов)
- `app/models/*.py` - все SQLAlchemy модели (7 файлов)
- `app/services/auth_service.py`
- `app/middleware/auth.py`

### 5. Объединение Socket.IO модулей

Два файла (`socketio_instance.py` + `socketio_events.py`) объединены в `core/socketio.py`:
- Создание сервера `sio`
- Регистрация всех event handlers
- Helper функция `broadcast_event()`

**Важно**: В `socketio_events.py` был импорт `from .database import get_db`, который изменён на `from ..core.database import get_db` в новом файле.

## Проверка

### 1. Проверка импортов
```bash
cd apps/backend
uv run python -c "from app.main import app; print('✅ Import successful')"
# Результат: ✅ Import successful
```

### 2. Проверка Message Bus (Phase 1)
```bash
cd apps/backend
uv run python -m app.services.multi_agent.test_message_bus
# Результат: 
# ✅ Test 1 passed: Message published and received
# ⚠️  Test 2 failed: Known issue - multiple agents sharing Redis client
```

**Статус**: Базовая функциональность Message Bus работает (publish/subscribe). Тесты с несколькими агентами требуют доработки (каждый агент должен иметь свой Redis client).

### 3. Запуск dev сервера
```bash
cd apps/backend
uv run uvicorn app.main:app --reload
# Сервер должен запуститься без ошибок
```

## Следующие шаги

1. Запустить тесты Phase 1:
   ```bash
   cd apps/backend
   uv run python -m app.services.multi_agent.test_message_bus
   ```

2. Запустить dev сервер:
   ```bash
   cd apps/backend
   uv run uvicorn app.main:app --reload
   ```

3. Приступить к Phase 2 (Orchestrator & Session Management)

## Преимущества новой структуры

- ✅ **Чёткое разделение**: Инфраструктура (core/) отделена от бизнес-логики
- ✅ **Единая точка входа**: Все core компоненты импортируются из `app.core`
- ✅ **Упрощённые импорты**: `from app.core import get_db, settings, sio`
- ✅ **Лучшая поддерживаемость**: Легко найти инфраструктурные модули
- ✅ **Удалён устаревший код**: 5 deprecated файлов удалены

## Структура после рефакторинга

```
apps/backend/app/
├── core/                    # 🆕 Инфраструктура
│   ├── __init__.py
│   ├── config.py           # Settings
│   ├── database.py         # SQLAlchemy setup
│   ├── redis.py            # Redis client
│   └── socketio.py         # Socket.IO server + events
├── models/                 # SQLAlchemy модели
├── routes/                 # FastAPI endpoints
├── schemas/                # Pydantic schemas
├── services/               # Бизнес-логика
│   └── multi_agent/       # Phase 1 - Message Bus
├── middleware/             # Middleware
└── main.py                # FastAPI app entry point
```

## См. также

- [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - Архитектура системы
- [docs/MULTI_AGENT_SYSTEM.md](../../docs/MULTI_AGENT_SYSTEM.md) - Multi-Agent система
- [apps/backend/app/services/multi_agent/README.md](../app/services/multi_agent/README.md) - Message Bus документация
