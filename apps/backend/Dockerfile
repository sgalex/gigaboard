# Backend Dockerfile for GigaBoard
# Сборка из корня репозитория: docker build -f apps/backend/Dockerfile .
#
# В docker-compose.yml (production) код app/ КОПИРУЕТСЯ в образ — bind-mount нет.
# Изменения в apps/backend/app попадут в контейнер только после:
#   docker compose build backend && docker compose up -d backend
# В docker-compose.dev.yml каталог ./apps/backend/app смонтирован в /app/app — там код обновляется без пересборки.

FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Медленный канал / блокировка pypi.org из VM Docker Desktop — увеличенные таймауты
ENV UV_HTTP_TIMEOUT=300

# Явный индекс (переопределите при сборке: --build-arg PYPI_INDEX_URL=...)
ARG PYPI_INDEX_URL=https://pypi.org/simple
ENV UV_INDEX_URL=${PYPI_INDEX_URL}

# Workspace: корневой uv.lock — единственный актуальный lock (в нём pypdf, python-docx и др.).
# Не использовать только apps/backend/uv.lock: он мог устареть относительно apps/backend/pyproject.toml.
COPY pyproject.toml ./
COPY uv.lock ./
COPY apps/backend/pyproject.toml ./apps/backend/

# Сначала основной индекс; при сбое — публичные зеркала (удобно, если pypi.org недоступен из Docker VM)
RUN uv export --frozen --no-dev --no-hashes --no-emit-package gigaboard-backend -o /tmp/requirements.txt \
    && ( UV_INDEX_URL="${PYPI_INDEX_URL}" uv pip install --system --no-cache -r /tmp/requirements.txt \
    || UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv pip install --system --no-cache -r /tmp/requirements.txt \
    || UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ uv pip install --system --no-cache -r /tmp/requirements.txt ) \
    && rm /tmp/requirements.txt \
    && ( UV_INDEX_URL="${PYPI_INDEX_URL}" uv pip install --system --no-cache "python-multipart>=0.0.6" \
    || UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv pip install --system --no-cache "python-multipart>=0.0.6" \
    || UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ uv pip install --system --no-cache "python-multipart>=0.0.6" )

# Явно: PDF/DOCX (если образ собран со старым кэшем или export без этих строк — иначе ModuleNotFoundError в runtime)
RUN ( UV_INDEX_URL="${PYPI_INDEX_URL}" uv pip install --system --no-cache "pypdf>=4.0" "python-docx>=1.1.0" \
    || UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv pip install --system --no-cache "pypdf>=4.0" "python-docx>=1.1.0" \
    || UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ uv pip install --system --no-cache "pypdf>=4.0" "python-docx>=1.1.0" )

COPY apps/backend/app ./app
COPY apps/backend/migrations ./migrations
COPY apps/backend/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

RUN mkdir -p /app/uploads && chmod 755 /app/uploads

ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]

# Dev-образ (docker-compose.dev.yml задаёт target: development и CMD с --reload)
FROM base AS development
# За nginx: корректные Location при 307 (trailing slash), иначе клиент уходит на backend:8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

# Продакшен — последняя стадия по умолчанию при docker build без --target
FROM base AS production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
