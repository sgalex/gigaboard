# Развёртывание GigaBoard в Docker на виртуальной машине

## Executive Summary

Инструкция описывает **пошаговый запуск полного стека GigaBoard** (PostgreSQL, Redis, FastAPI backend, nginx + frontend) на **виртуальной машине с Linux** через **Docker Engine** и **Docker Compose**. По умолчанию **на хост публикуется только порт веб-интерфейса** (`FRONTEND_PORT`, nginx): REST (`/api/`), Socket.IO (`/socket.io/`) и документация API (`/docs`, `/redoc`) проксируются внутрь сети Compose. PostgreSQL, Redis и backend **не слушают порты на хосте**. Для локального Docker Desktop на Windows/Mac см. также [DOCKER_DESKTOP.md](../DOCKER_DESKTOP.md) в корне репозитория.

**Ключевые файлы:** корневой `docker-compose.yml`, `apps/backend/Dockerfile`, `apps/web/Dockerfile`, шаблон [`.env.example`](../.env.example), вспомогательные ресурсы в [`res/`](../res/) (см. [`res/README.md`](../res/README.md)).

---

## Требования к ВМ

| Параметр | Рекомендация |
|----------|----------------|
| **ОС** | Ubuntu 22.04 LTS / 24.04 LTS или Debian 12 (x86_64 или arm64) |
| **RAM** | не менее **8 GB** (лучше 16 GB при нагрузке на агентов) |
| **Диск** | **20+ GB** свободно (образы, слои сборки, тома БД) |
| **CPU** | 2+ vCPU |
| **Сеть** | исходящий доступ в интернет для `docker pull` и сборки backend (PyPI/npm) |

---

## Шаг 1. Установить Docker Engine и Compose

На **Ubuntu** (официальный репозиторий Docker):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${VERSION_CODENAME:-$VERSION_ID}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Проверка:

```bash
docker --version
docker compose version
sudo docker run --rm hello-world
```

Чтобы запускать Compose **без `sudo`**, добавьте пользователя в группу `docker` и перелогиньтесь:

```bash
sudo usermod -aG docker "$USER"
# выйти из SSH-сессии и зайти снова
```

Дальше в инструкции команды приведены **без** `sudo` (при необходимости замените на `sudo docker ...`).

---

## Шаг 2. Клонировать репозиторий

```bash
cd /opt   # или домашний каталог
sudo git clone https://github.com/<org>/GigaBoard.git gigaboard
sudo chown -R "$USER:$USER" gigaboard
cd gigaboard
```

(Замените URL на актуальный для вашего форка/организации.)

---

## Шаг 3. Подготовить файл `.env`

```bash
cp .env.example .env
nano .env   # или vim
```

**Обязательно для продакшена:**

1. **`JWT_SECRET_KEY`** — длинная случайная строка (не оставляйте значение по умолчанию).
2. **`POSTGRES_PASSWORD`** — сильный пароль; он же участвует в `DATABASE_URL` внутри Compose для сервиса `backend` (см. `docker-compose.yml`).

**Для первого администратора (опционально):**

- `ADMIN_EMAIL` и `ADMIN_PASSWORD` — при старте backend создаётся/обновляется пользователь с ролью admin.

**Доступ с других машин по IP ВМ — CORS:**

В `docker-compose.yml` для `backend` задаётся `CORS_ORIGINS` через переменную окружения. В `.env` добавьте **реальные Origin** браузера, например:

```env
CORS_ORIGINS=http://10.0.0.5,http://10.0.0.5:80,http://gigaboard.example.com,https://gigaboard.example.com
```

(Подставьте IP или DNS вашей ВМ и схему `http`/`https`.)

**Порт веб-интерфейса на хосте:**

| Переменная | По умолчанию | Когда менять |
|------------|--------------|--------------|
| `FRONTEND_PORT` | `3000` | Нужен стандартный HTTP 80 → `80` (на Linux может потребоваться `sudo`); иначе любой свободный порт (`8080` и т.д.) |

**Публикация Postgres / Redis / backend на хост** (отладка, pgAdmin с ноутбука и т.п.):

```bash
docker compose -f docker-compose.yml -f docker-compose.publish-internal-ports.yml up -d
```

Файл `docker-compose.publish-internal-ports.yml` добавляет `ports` для `postgres`, `redis`, `backend` (переменные `POSTGRES_PORT`, `REDIS_PORT`, `BACKEND_PORT` из `.env`).

**Сборка SPA для одного origin с nginx:** не задавайте `VITE_API_URL` в `.env` (или оставьте пустым) — фронт ходит на `/api/...` и Socket.IO на тот же хост.

**Сборка backend, если с ВМ недоступен `pypi.org`:**

В `.env` можно задать зеркало (передаётся как build-arg):

```env
PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

В `Dockerfile` backend уже есть резервные зеркала, но явный `PYPI_INDEX_URL` ускоряет первую попытку.

---

## Шаг 4. Открыть порты в файрволе (если используется)

Пример **UFW** (Ubuntu):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 3000/tcp    # или ваш FRONTEND_PORT (например 80/tcp, 8080/tcp)
sudo ufw enable
sudo ufw status
```

Если используете **`docker-compose.publish-internal-ports.yml`**, откройте в UFW и на облачном firewall соответствующие `POSTGRES_PORT`, `REDIS_PORT`, `BACKEND_PORT` (в продакшене это обычно **не** делают).

Для **облачных** ВМ дополнительно откройте нужные порты в security group / NSG панели провайдера.

---

## Шаг 5. Собрать образы и запустить стек

Из **корня репозитория** (где лежит `docker-compose.yml`):

```bash
cd /opt/gigaboard   # ваш путь
docker compose build
docker compose up -d
```

Первый запуск может занять **10–20+ минут** (скачивание базовых образов, `npm ci`, установка Python-зависимостей).

Проверка контейнеров:

```bash
docker compose ps
```

Ожидаемые сервисы: `postgres`, `redis`, `backend`, `frontend` — статус `running`, health — `healthy` (после прогрева).

---

## Шаг 6. Проверить работоспособность

С **самой ВМ** (подставьте порт из `FRONTEND_PORT`, по умолчанию **3000**):

```bash
curl -sS http://127.0.0.1:3000/api/v1/health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/health
```

Проверка backend **только изнутри** сети Docker (порт 8000 не на хосте):

```bash
docker compose exec backend curl -sS http://127.0.0.1:8000/health
```

С **рабочей станции** (замените `VM_IP` и порт; по умолчанию `FRONTEND_PORT=3000`):

```text
http://VM_IP:3000/         — веб-интерфейс (nginx)
http://VM_IP:3000/api/v1/... — REST через прокси
http://VM_IP:3000/docs     — Swagger UI (прокси на backend)
http://VM_IP:3000/redoc    — ReDoc
```

При старте **backend** выполняется **`alembic upgrade head`** (миграции БД). Отключить только для отладки: `SKIP_ALEMBIC_UPGRADE=1` в `.env` (не рекомендуется в проде).

---

## Шаг 7. Логи и отладка

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs --tail=100 postgres
```

Перезапуск одного сервиса:

```bash
docker compose restart backend
```

Остановка без удаления томов:

```bash
docker compose down
```

---

## Шаг 8. Обновление версии приложения

```bash
cd /opt/gigaboard
git pull
docker compose build
docker compose up -d
```

При изменениях миграций Alembic новые ревизии применятся при следующем старте `backend` (если не задан `SKIP_ALEMBIC_UPGRADE=1`).

---

## Резервное копирование данных

Тома Compose (имена могут иметь префикс имени проекта каталога):

- **`postgres_data`** — данные PostgreSQL  
- **`redis_data`** — persistence Redis (AOF)  
- **`uploads_data`** — загрузки backend  

Практика: периодический **dump PostgreSQL** из контейнера и бэкап каталога с томами или снимков диска ВМ.

Пример дампа:

```bash
docker compose exec postgres pg_dump -U gigaboard gigaboard > backup_$(date +%Y%m%d).sql
```

(Уточните `POSTGRES_USER` / `POSTGRES_DB` из вашего `.env`.)

---

## Типичные проблемы

| Симптом | Что проверить |
|---------|----------------|
| **Сборка backend падает на PyPI** | `PYPI_INDEX_URL` в `.env`, сеть ВМ, прокси; в образе уже есть fallback-зеркала |
| **Порт занят** | `FRONTEND_PORT` в `.env`; при использовании `docker-compose.publish-internal-ports.yml` — также `POSTGRES_PORT`, `REDIS_PORT`, `BACKEND_PORT` |
| **502 / нет API с браузера** | `docker compose ps`, логи `backend`; CORS — `CORS_ORIGINS` должен включать Origin браузера |
| **307 на POST, затем ERR_CONNECTION_REFUSED** | Редирект trailing slash строил URL на `backend:8000`. В образе включены `uvicorn --proxy-headers`, nginx передаёт `Host` / `X-Forwarded-Host` (`$http_host`). Пересоберите `frontend` + `backend` |
| **Миграции** | Логи старта backend; локально: `cd apps/backend/migrations && uv run alembic heads` |
| **Чистая переустановка БД** | `docker compose down` и удаление тома `*_postgres_data` (**удалит данные**) |

---

## Связанные документы

- [COMMANDS.md](./COMMANDS.md) — команды разработки и кратко про Docker Compose  
- [ADMIN_AND_SYSTEM_LLM.md](./ADMIN_AND_SYSTEM_LLM.md) — настройка LLM и админа в UI (не через `GIGACHAT_*` в `.env`)  
- [`.env.example`](../.env.example) — полный перечень переменных с комментариями  
- [`res/nginx-vm-gigaboard.conf`](../res/nginx-vm-gigaboard.conf) — готовый reverse-proxy конфиг nginx для ВМ (перед Docker Compose фронтом)
