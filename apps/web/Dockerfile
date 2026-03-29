# Multi-stage: production build.
# Контекст сборки — корень репозитория (npm workspaces: package.json + apps/web/package.json;
# node_modules и lockfile на корне; copy-libs.cjs читает echarts/leaflet из корневого node_modules).
#
# После изменений в apps/web ОБЯЗАТЕЛЬНО пересоберите образ, иначе в nginx останется старый dist:
#   docker compose build frontend && docker compose up -d frontend
# При подозрении на кэш слоёв: docker compose build --no-cache frontend
#
# VITE_API_URL: по умолчанию пусто — в бандле относительные /api (nginx проксирует на backend).
# Задавайте в .env только если API на другом origin; после смены — пересборка frontend.
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
