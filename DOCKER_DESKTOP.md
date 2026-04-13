# 🐳 Запуск GigaBoard в Docker Desktop

Пошаговая инструкция для локального запуска в Docker Desktop (Windows/Mac).

---

## Предварительные требования

1. **Docker Desktop** установлен и запущен
   - Windows: https://docs.docker.com/desktop/install/windows-install/
   - Mac: https://docs.docker.com/desktop/install/mac-install/
   
2. **Git** для клонирования репозитория

3. **Минимум 8GB RAM** выделено для Docker Desktop
   - Настройки → Resources → Advanced → Memory: 8GB

---

## 🚀 Быстрый старт

### 1. Подготовка файла .env

Создайте файл `.env` в корне проекта:

```env
# Database
POSTGRES_USER=gigaboard
POSTGRES_PASSWORD=gigaboard123
POSTGRES_DB=gigaboard
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Backend (порт 8000 на хост не публикуется по умолчанию — только через nginx)
JWT_SECRET_KEY=dev-jwt-secret-key-min-32-characters-random
ENVIRONMENT=development
DEBUG=true

# Frontend (хост:порт → контейнер nginx :80; по умолчанию в compose — 3000, без прав админа на Windows)
FRONTEND_PORT=3000

# CORS (при необходимости; для UI на :3000 добавьте origin с портом)
CORS_ORIGINS=http://localhost,http://127.0.0.1,http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173

# LLM / GigaChat — только в UI после входа (пресеты), не через .env
```

### Локальный Vite + Docker только с FRONTEND_PORT

Если backend в контейнере **не** проброшен на `:8000`, а вы открываете `http://localhost:5173`, Vite по умолчанию проксирует `/api` на `localhost:8000` → запросы падают. Варианты:

- Открывать готовый UI из контейнера: `http://localhost:3000` (или ваш `FRONTEND_PORT`).
- Или запускать Vite так: `.\run-frontend.ps1 -DockerNginx` (прокси на `http://localhost:3000`; при другом порте задайте `VITE_DEV_PROXY_TARGET` вручную).

После исправления **`VITE_API_URL`** пересоберите образ frontend: `docker compose build frontend`.

### 2. Сборка и запуск

Откройте терминал в корне проекта:

```bash
# Сборка всех образов
docker compose build

# Запуск всех сервисов
docker compose up -d

# Просмотр логов
docker compose logs -f
```

**Первый запуск займет 5-10 минут** (загрузка базовых образов, установка зависимостей).

### 3. Проверка работоспособности

После запуска откройте:

- **Frontend**: http://localhost:3000 (или ваш `FRONTEND_PORT`)
- **Swagger**: http://localhost:3000/docs (прокси через nginx; порт backend на хост не обязателен)
- **Health (лёгкий)**: http://localhost:3000/health  
- **Health (API)**: http://localhost:3000/api/v1/health  

Прямой доступ к backend на `:8000` нужен только если подключили `docker-compose.publish-internal-ports.yml`.

Проверьте статус контейнеров:

```bash
docker compose ps
```

Все контейнеры должны быть в статусе `Up (healthy)`.

---

## 🔧 Управление

### Основные команды

```bash
# Запуск сервисов
docker compose up -d

# Остановка сервисов
docker compose down

# Перезапуск конкретного сервиса
docker compose restart backend
docker compose restart frontend

# Просмотр логов
docker compose logs -f                    # Все сервисы
docker compose logs -f backend            # Только backend
docker compose logs -f frontend           # Только frontend

# Остановка с удалением volumes (ОЧИСТКА ДАННЫХ!)
docker compose down -v
```

### Пересборка после изменений кода

```bash
# Пересборка конкретного сервиса
docker compose build backend
docker compose up -d backend

# Пересборка всех сервисов
docker compose build
docker compose up -d

# Пересборка без кэша (полная пересборка)
docker compose build --no-cache
docker compose up -d
```

### Выполнение команд внутри контейнеров

```bash
# Backend: запуск миграций
docker compose exec backend alembic upgrade head

# Backend: создание новой миграции
docker compose exec backend alembic revision --autogenerate -m "описание"

# Backend: Python shell
docker compose exec backend python

# PostgreSQL: psql
docker compose exec postgres psql -U gigaboard -d gigaboard

# Redis: CLI
docker compose exec redis redis-cli

# Bash в контейнере
docker compose exec backend bash
docker compose exec frontend sh
```

---

## 📊 Docker Desktop UI

### Просмотр контейнеров

1. Откройте Docker Desktop
2. Перейдите в раздел "Containers"
3. Найдите группу "gigaboard"
4. Вы увидите 4 контейнера:
   - `gigaboard-postgres`
   - `gigaboard-redis`
   - `gigaboard-backend`
   - `gigaboard-frontend`

### Просмотр логов через UI

1. Кликните на контейнер (например, `gigaboard-backend`)
2. Вкладка "Logs" покажет вывод в реальном времени
3. Можно фильтровать, искать, экспортировать

### Управление через UI

- **Start/Stop**: кнопки запуска/остановки контейнеров
- **Restart**: перезапуск контейнера
- **Delete**: удаление контейнера
- **Exec**: открыть терминал внутри контейнера (CLI)

---

## 🐛 Troubleshooting

### Проблема: Backend не запускается

**Симптомы**: контейнер `gigaboard-backend` постоянно перезапускается

**Решение**:

```bash
# Посмотрите логи
docker compose logs backend

# Частые причины:
# 1. PostgreSQL не успел запуститься
# Подождите 30 секунд и проверьте снова

# 2. Ошибка миграции БД
docker compose exec backend alembic upgrade head

# 3. Ошибки LLM — настройте пресеты в приложении (профиль / админ), не .env
```

### Проблема: Frontend показывает "Cannot connect to API"

**Решение**:

```bash
# 1. Проверьте, что backend запущен
docker compose ps backend

# 2. Проверьте health check
curl http://localhost:3000/api/v1/health

# 3. Проверьте nginx конфигурацию
docker compose exec frontend cat /etc/nginx/conf.d/default.conf
```

### Проблема: "Port is already allocated"

**Симптомы**: Ошибка при запуске `docker compose up`

**Решение**:

```bash
# Найдите процесс, занимающий порт (например, 8000)
# Windows PowerShell:
netstat -ano | findstr :8000

# Завершите процесс по PID или измените порт в .env:
BACKEND_PORT=8001
```

### Проблема: Медленная сборка на Windows

**Решение**:

1. Включите WSL 2 backend в Docker Desktop:
   - Settings → General → Use the WSL 2 based engine

2. Переместите проект в WSL 2 filesystem:
   ```bash
   # В WSL 2 терминале
   cd ~
   git clone <repo>
   cd gigaboard
   ```

3. Увеличьте ресурсы Docker:
   - Settings → Resources → Advanced
   - CPU: 4+ cores
   - Memory: 8+ GB
   - Disk image size: 60+ GB

---

## 🔄 Development режим с hot reload

Для разработки используйте `docker-compose.dev.yml`:

```bash
# Запуск в dev режиме
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Теперь:
# - Backend перезагружается при изменении кода
# - Frontend использует Vite dev server с HMR
# - Доступны pgAdmin (localhost:5050) и Redis Commander (localhost:8081)
```

**Логины для dev tools:**

- **pgAdmin**: `admin@gigaboard.local` / `admin`
- **Redis Commander**: без авторизации

---

## 📦 Объем и производительность

### Размер образов

После первой сборки:

- `gigaboard-backend`: ~800MB
- `gigaboard-frontend`: ~50MB (nginx + static)
- `postgres:16-alpine`: ~230MB
- `redis:7-alpine`: ~40MB

**Общий размер**: ~1.2GB

### Время сборки

- **Первая сборка**: 5-10 минут (загрузка зависимостей)
- **Повторная сборка**: 1-2 минуты (кэш слоёв)
- **Запуск сервисов**: 20-30 секунд

### Использование ресурсов

В idle режиме:

- **CPU**: 2-5%
- **RAM**: 1.5-2GB
- **Disk**: 2-3GB (с данными)

При активной работе AI:

- **CPU**: 20-40%
- **RAM**: 3-4GB

---

## 📝 Полезные ссылки

- Подробная документация: [DEPLOYMENT.md](DEPLOYMENT.md)
- Быстрые команды: [DEPLOY_QUICK.md](DEPLOY_QUICK.md)
- Docker Desktop документация: https://docs.docker.com/desktop/

---

## 💡 Советы для Docker Desktop

1. **Включите BuildKit** для быстрой сборки:
   ```bash
   # В .env или export
   DOCKER_BUILDKIT=1
   COMPOSE_DOCKER_CLI_BUILD=1
   ```

2. **Регулярно чистите неиспользуемые ресурсы**:
   ```bash
   docker system prune -a --volumes
   ```

3. **Используйте Docker Desktop Dashboard** для визуального контроля

4. **Настройте File Sharing** (Settings → Resources → File Sharing)
   - Добавьте путь к проекту, если возникают проблемы с volumes

---

**Вопросы?** Откройте issue в GitHub или обратитесь к [DEPLOYMENT.md](DEPLOYMENT.md)
