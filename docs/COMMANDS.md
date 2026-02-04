# 🚀 Команды запуска GigaBoard

## Быстрый старт (всё сразу)

**Запустить Backend + Frontend одной командой:**
```powershell
.\run-dev.ps1
```

Это запустит:
- Backend на http://localhost:8000
- Frontend на http://localhost:5173

Нажмите `Ctrl+C` чтобы остановить все сервисы.

---

## Запуск приложения

### Backend (FastAPI + Python)

**Способ 1: Удобный скрипт (рекомендуется)**
```powershell
.\run-backend.ps1
```

**Способ 2: Из папки backend**
```bash
cd apps/backend
uv run python run_dev.py
```

**Способ 3: Прямой uvicorn**
```bash
cd apps/backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend будет доступен на: http://localhost:8000
API документация: http://localhost:8000/docs

### Frontend (React + Vite)

**Способ 1: Удобный скрипт (рекомендуется)**
```powershell
.\run-frontend.ps1
```

**Способ 2: Через npm workspace**
```bash
npm run -w apps/web dev
```

**Способ 3: Из папки frontend**
```bash
cd apps/web
npm run dev
```

Frontend будет доступен на: http://localhost:5173

---

## Миграции базы данных

```bash
cd apps/backend

# Применить миграции
uv run alembic upgrade head

# Откатить одну миграцию
uv run alembic downgrade -1

# Создать новую миграцию
uv run alembic revision --autogenerate -m "описание изменений"
```

---

## Зависимости

### Backend
```bash
cd apps/backend

# Установить/обновить зависимости
uv sync

# Добавить новую зависимость
uv add package-name

# Добавить dev зависимость
uv add --dev package-name
```

### Frontend
```bash
# Установить зависимости
npm install

# Добавить зависимость
npm install --workspace apps/web package-name

# Добавить dev зависимость
npm install --workspace apps/web -D package-name
```

---

## Тестирование

### Backend
```bash
cd apps/backend
uv run pytest
```

### Frontend
```bash
npm run -w apps/web test
```

---

## Требования

- **Python**: 3.11+ (рекомендуется 3.11 или 3.12)
- **Node.js**: 18+
- **PostgreSQL**: 15+
- **Redis**: 7+
- **UV**: 0.9+ (для управления Python зависимостями)

---

## Сервисы (Docker)

### PostgreSQL
```bash
docker run -d --name gigaboard-postgres \
  -e POSTGRES_USER=gigaboard \
  -e POSTGRES_PASSWORD=gigaboard_password \
  -e POSTGRES_DB=gigaboard_db \
  -p 5432:5432 \
  postgres:15-alpine
```

### Redis
```bash
docker run -d --name gigaboard-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### Остановить контейнеры
```bash
docker stop gigaboard-postgres gigaboard-redis
```

### Удалить контейнеры
```bash
docker rm gigaboard-postgres gigaboard-redis
```

---

## Проверка сервисов

```bash
# Backend health check
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health

# Frontend
curl http://localhost:5173

# PostgreSQL
Test-NetConnection localhost -Port 5432

# Redis
Test-NetConnection localhost -Port 6379
```
