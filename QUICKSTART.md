# 🎯 Быстрая справка по командам

## Запуск разработки

```powershell
# Всё сразу (Backend + Frontend)
.\run-dev.ps1

# Только Backend (порт 8000)
.\run-backend.ps1

# Только Frontend (порт 5173)
.\run-frontend.ps1
```

## Проверка работы

- Backend API: http://localhost:8000
- API документация: http://localhost:8000/docs
- Frontend: http://localhost:5173
- Health check: http://localhost:8000/health

## Миграции БД

```bash
cd apps/backend
uv run alembic upgrade head      # Применить миграции
uv run alembic downgrade -1      # Откатить одну миграцию
```

## Полная документация

- [COMMANDS.md](COMMANDS.md) - Все команды проекта
- [README.md](README.md) - Основная документация
- [docs/](docs/) - Техническая документация

## Первый запуск

1. Убедитесь что запущены PostgreSQL (5432) и Redis (6379)
2. Установите зависимости: `npm install` и `cd apps/backend && uv sync`
3. Запустите: `.\run-dev.ps1`
4. Откройте: http://localhost:5173
