# Multi-stage: production build. Контекст — корень репозитория (npm workspaces + copy-libs).
FROM node:20-alpine AS builder

WORKDIR /workspace

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/

RUN npm ci

COPY apps/web ./apps/web

WORKDIR /workspace/apps/web
# Пусто = REST и Socket.IO с того же origin, что и nginx (см. apps/web/src/config/apiBase.ts)
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine

COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
