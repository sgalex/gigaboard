# Развёртывание GigaBoard в Docker на виртуальной машине

## Executive Summary

Инструкция описывает **пошаговый запуск полного стека GigaBoard** (PostgreSQL, Redis, FastAPI backend, nginx + frontend) на **виртуальной машине с Linux** через **Docker Engine** и **Docker Compose**. По умолчанию **на хост публикуется только порт веб-интерфейса** (`FRONTEND_PORT`, nginx): REST (`/api/`), Socket.IO (`/socket.io/`) и документация API (`/docs`, `/redoc`) проксируются внутрь сети Compose. PostgreSQL, Redis и backend **не слушают порты на хосте**. Для локального Docker Desktop на Windows/Mac см. также [DOCKER_DESKTOP.md](../DOCKER_DESKTOP.md) в корне репозитория.

**Ключевые файлы:** корневой [`docker-compose.yml`](../docker-compose.yml), опционально [`docker-compose.dev.yml`](../docker-compose.dev.yml) (Vite + `--reload`), [`docker-compose.publish-internal-ports.yml`](../docker-compose.publish-internal-ports.yml), `apps/backend/Dockerfile`, `apps/web/Dockerfile`, шаблон [`.env.example`](../.env.example), вспомогательные ресурсы в [`res/`](../res/) (см. [`res/README.md`](../res/README.md)).

**База данных в контейнере:** сервис `backend` получает `DATABASE_URL` **только** из `docker-compose.yml` (хост `postgres`, не `localhost`). Строка `DATABASE_URL` в корневом `.env` на машине разработчика **не подменяет** подключение внутри контейнера: при старте в логах backend будет строка вида `Database target (DATABASE_URL): postgres:5432/gigaboard`. Локальный `run-backend.ps1` и Docker — это **разные** экземпляры Postgres, если вы не настраиваете общий хост вручную.

### Почему «тот же файл» ведёт себя по-разному (Docker vs локальный uvicorn)

Это **не один и тот же запуск приложения** с точки зрения данных и окружения:

1. **Разные базы и файлы.** Загрузка через UI на `localhost:5173` + `run-backend.ps1` пишет в **Postgres на хосте** (и/или в каталог из `.env`). Загрузка через UI на `localhost:3000` (nginx в Compose) пишет в **Postgres в контейнере** и в том хранилище, которое задано **для backend-контейнера**. Даже один и тот же PDF на диске — это **два разных upload** и два разных `file_id`; сравнивать нужно байты и логи, а не «один URL в браузере».

2. **Корневой `.env` и контейнер.** В контейнере `GIGABOARD_IN_DOCKER=1`, поэтому Python **не читает** корневой `.env` / `.env.local` как при локальном запуске ([`app/core/config.py`](../apps/backend/app/core/config.py)). Переменные в процессе backend в Docker задаёт **только** то, что передано в `docker-compose.yml` (и подстановка `${VAR}` из корневого `.env` **для Compose** — это отдельный механизм: значения из `.env` подставляются в YAML, но файл целиком в приложение не монтируется).

3. **`STORAGE_BACKEND` и путь к файлам.** Если в корневом `.env` для разработки на хосте указано `STORAGE_BACKEND=local`, то при `docker compose up` эта же переменная может **подставиться** в сервис `backend` (`${STORAGE_BACKEND:-database}`). Тогда в контейнере включается файловое хранилище с путём по умолчанию `data/uploads` относительно рабочего каталога — это **`/app/data/uploads`**, тогда как том в Compose смонтирован на **`/app/uploads`**. В `docker-compose.yml` задан дефолт `STORAGE_LOCAL_PATH=/app/uploads`, чтобы при `STORAGE_BACKEND=local` файлы попадали в тот же том, что и ожидается. Проверка: в логах при старте backend есть строка `File storage: STORAGE_BACKEND=... STORAGE_LOCAL_PATH=...`.

4. **Одинаковый код, разные ОС в рантайме.** Образ backend — Linux; локально на Windows — другой event loop и иногда другие версии Python, если venv не синхронизирован с `uv.lock`. Критичные места (BYTEA, `memoryview`) в коде учитываются, но диагностика всё равно должна опираться на лог `analyze-document failed ... detail=...` и на строку `File storage:` при старте.

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
| `FRONTEND_PORT` | `3000` | Только **production**-стек (`docker compose up`): хост → nginx в контейнере `:80`. Нужен HTTP 80 → `80` (на Linux может потребоваться привилегированный порт); иначе любой свободный порт (`8080` и т.д.) |
| `FRONTEND_DEV_PORT` | `5173` | Только **dev**-слияние с [`docker-compose.dev.yml`](../docker-compose.dev.yml): хост → Vite в контейнере. С `FRONTEND_PORT` **не** путается: в dev для `frontend` порты в override заданы через `!override`, чтобы не оставался лишний маппинг `FRONTEND_PORT:80` от базового compose (см. [Merge в Compose](https://docs.docker.com/reference/compose-file/merge/)). |

**Публикация Postgres / Redis / backend на хост** (отладка, pgAdmin с ноутбука и т.п.):

```bash
docker compose -f docker-compose.yml -f docker-compose.publish-internal-ports.yml up -d
```

Файл `docker-compose.publish-internal-ports.yml` добавляет `ports` для `postgres`, `redis`, `backend` (переменные `POSTGRES_PORT`, `REDIS_PORT`, `BACKEND_PORT` из `.env`; см. комментарии в [`.env.example`](../.env.example)).

**Сборка SPA для одного origin с nginx:** не задавайте `VITE_API_URL` в `.env` (или оставьте пустым) — фронт ходит на `/api/...` и Socket.IO на тот же хост.

### (Опционально) Dev-стек на ВМ: Vite + hot reload backend

Из корня репозитория:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- Веб-интерфейс: `http://<VM_IP>:5173` (или значение **`FRONTEND_DEV_PORT`** в `.env`). Прокси API на `backend:8000` задаётся в compose (`VITE_DEV_PROXY_TARGET`).
- **pgAdmin** и **Redis Commander** подключаются только с профилем **`tools`**:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile tools up -d
```

Порты по умолчанию: `PGADMIN_PORT` → 5050, `REDIS_COMMANDER_PORT` → 8081 (см. `docker-compose.dev.yml`).

После смены зависимостей в `package.json` / корневом lockfile пересоберите образ frontend: `docker compose -f docker-compose.yml -f docker-compose.dev.yml build frontend`.

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
# при необходимости подтянуть базовые образы (postgres/redis/node): docker compose build --pull
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
# опционально: docker compose build --pull
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
| **413 при загрузке файла (Excel и др.) или при импорте ZIP проекта** | Nginx по умолчанию режет тело запроса (**1 MB**). В `apps/web/nginx.conf` задано `client_max_body_size` (по умолчанию **100m**; согласуйте с `STORAGE_MAX_FILE_SIZE_MB` и размером архивов импорта). После правки: `docker compose build frontend && docker compose up -d frontend`. Внешний nginx на ВМ — см. `res/nginx-vm-gigaboard.conf` (`client_max_body_size`) |
| **Прогресс ИИ / стрим «застыл» на ВМ** | Внешний nginx перед Docker часто **буферизует** ответ (`proxy_buffering on` по умолчанию) — NDJSON доходит одним куском в конце. В `location /` добавьте `proxy_buffering off; proxy_cache off; proxy_request_buffering off;` (см. актуальный [`res/nginx-vm-gigaboard.conf`](../res/nginx-vm-gigaboard.conf)), затем `sudo nginx -t && sudo systemctl reload nginx`. Внутри образа фронта то же для `/api/` уже в `apps/web/nginx.conf` |
| **Миграции** | Логи старта backend; локально: `cd apps/backend/migrations && uv run alembic heads` |
| **Чистая переустановка БД** | `docker compose down` и удаление тома `*_postgres_data` (**удалит данные**) |

---

## Связанные документы

- [COMMANDS.md](./COMMANDS.md) — команды разработки, production/dev Compose и профиль `tools` (pgAdmin, Redis Commander)  
- [ADMIN_AND_SYSTEM_LLM.md](./ADMIN_AND_SYSTEM_LLM.md) — настройка LLM и админа в UI (не через `GIGACHAT_*` в `.env`)  
- [`.env.example`](../.env.example) — полный перечень переменных с комментариями  
- [`res/nginx-vm-gigaboard.conf`](../res/nginx-vm-gigaboard.conf) — готовый reverse-proxy конфиг nginx для ВМ (перед Docker Compose фронтом)
