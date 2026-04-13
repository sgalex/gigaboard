# Multi-stage: production frontend (nginx + статический Vite build).
#
# Контекст — корень репозитория: npm workspaces (корневой package-lock + apps/web/package.json),
# copy-libs.cjs тянет echarts/leaflet из корневого node_modules.
#
# Пересборка после правок apps/web:
#   docker compose build frontend && docker compose up -d frontend
#   docker compose build --no-cache frontend   # при «залипании» старых слоёв
#
# Runtime nginx (второй stage):
# - nginx-forwarded-map.conf — X-Forwarded-Proto с внешнего TLS-прокси (не затирать на http между прокси и контейнером)
# - nginx.conf — /api/ → backend, proxy_buffering off для NDJSON-стриминга, Socket.IO, /health
#
# VITE_API_URL в compose build-args: по умолчанию пусто; для прод на HTTPS не задавайте http://
FROM node:20-alpine AS builder

WORKDIR /workspace

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/

RUN npm ci

COPY apps/web ./apps/web

WORKDIR /workspace/apps/web
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine

COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx-forwarded-map.conf /etc/nginx/conf.d/00-forwarded-map.conf
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
