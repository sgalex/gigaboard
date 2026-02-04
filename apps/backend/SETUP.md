# GigaBoard Backend Setup Guide

## Prerequisites

- **uv** package manager (install from https://github.com/astral-sh/uv)
- Python 3.11+ (automatically managed by uv)
- PostgreSQL 14+
- Redis 7+

## Quick Start

### 1. Install uv

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy BypassScope -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

### 2. Create virtual environment and install dependencies

```bash
cd apps/backend

# Create .venv with correct Python version
uv venv --python 3.11

# Activate virtual environment
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# Install dependencies from pyproject.toml
uv pip install -e .

# Or with dev dependencies
uv pip install -e ".[dev]"
```

### 3. Setup databases

**PostgreSQL:**
```bash
# Create database
createdb -U postgres gigaboard_db

# Or using psql:
psql -U postgres -c "CREATE DATABASE gigaboard_db;"
```

**Redis:**
```bash
# Start Redis (Docker)
docker run -d -p 6379:6379 redis:7-alpine

# Or if installed locally
redis-server
```

### 4. Environment configuration

Copy `.env.example` to `.env` and update values:
```bash
cp .env.example .env
```

Edit `.env` with your PostgreSQL credentials:
```
DATABASE_URL=postgresql+asyncpg://gigaboard:gigaboard_password@localhost:5432/gigaboard_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secure-secret-key-here
DEBUG=True
ENVIRONMENT=development
JWT_EXPIRATION_HOURS=24
```

### 5. Run migrations

```bash
# Make sure .venv is activated and you're in apps/backend directory
alembic upgrade head
```

### 6. Start backend server

```bash
# Development mode with auto-reload
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Server will be available at: **http://localhost:8000**

## API Documentation

Once server is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Health Checks

### Basic health check
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "service": "gigaboard-backend",
  "version": "0.1.0"
}
```

### Detailed health check (includes DB & Redis)
```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "service": "gigaboard-backend"
}
```

## Authentication API

### Register new user

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "john_doe",
    "password": "secure_password_123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "username": "john_doe",
    "created_at": "2026-01-23T10:00:00",
    "updated_at": "2026-01-23T10:00:00"
  }
}
```

### Login user

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password_123"
  }'
```

### Get current user

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

### Logout

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

## Database Migrations

### Create new migration

```bash
alembic revision --autogenerate -m "Add new column to users table"
```

### Apply migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply N migrations
alembic upgrade +2
```

### Downgrade

```bash
# Downgrade one migration
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade 001
```

### View migration history

```bash
alembic history
```

## 📦 Managing Dependencies

### Add new dependency

```bash
# Using uv pip
uv pip install package-name

# With specific version
uv pip install package-name==1.0.0
```

### Update dependencies

```bash
# Update everything
uv pip install --upgrade .
```

### View installed packages

```bash
uv pip list
```

## 🧪 Running Tests

```bash
# Install dev dependencies if not already installed
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py
```

## Troubleshooting

### Database connection error
- Check PostgreSQL is running: `psql -U postgres -c "SELECT 1;"`
- Verify DATABASE_URL in .env
- Ensure database exists: `createdb gigaboard_db`

### Redis connection error
- Check Redis is running: `redis-cli ping`
- Verify REDIS_URL in .env
- Default: `redis://localhost:6379/0`

### Port already in use
```bash
# Change port in command
python -m uvicorn apps.backend.app.main:app --port 8001
```

### JWT errors
- Update `JWT_SECRET_KEY` in `.env`
- Ensure token hasn't expired
- Token should be in `Authorization: Bearer <token>` header

## Project Structure

```
apps/backend/
├── .venv/                      # Virtual environment (auto-created by uv)
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, Socket.IO
│   ├── config.py               # Settings from .env
│   ├── database.py             # SQLAlchemy setup
│   ├── redis_client.py         # Redis connection
│   ├── models/                 # Database models
│   │   ├── __init__.py
│   │   └── user.py
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── routes/                 # API endpoints
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── health.py
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   └── auth_service.py
│   └── middleware/             # Auth middleware
│       ├── __init__.py
│       └── auth.py
├── migrations/                 # Alembic migrations
│   ├── versions/
│   ├── env.py
│   ├── alembic.ini
│   └── script.py.mako
├── .env                        # Local environment (DO NOT commit)
├── .env.example                # Template for .env
├── pyproject.toml              # Dependencies and project config (uv)
└── requirements.txt            # Legacy (kept for reference)
```

## Next Steps

1. ✅ Backend Core Setup - DONE
2. ⏳ Start implementing ФИЧА 2: FR-1, FR-2 (Boards & Widgets)
   - Create Board and Widget models
   - Implement board CRUD API
   - Create widgets CRUD API
   - Add React Flow frontend

---

**Last updated**: 2026-01-23
