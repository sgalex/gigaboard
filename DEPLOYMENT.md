# GigaBoard Deployment Guide

Руководство по развертыванию GigaBoard в production с использованием Docker.

---

## 📋 Требования

### Минимальные системные требования
- **CPU**: 2 cores (4+ рекомендуется для AI operations)
- **RAM**: 4GB (8GB+ рекомендуется)
- **Disk**: 20GB свободного места
- **OS**: Linux (Ubuntu 22.04 LTS, Debian 11+, CentOS 8+)

### Установленное ПО
- Docker Engine 24.0+
- Docker Compose 2.20+
- Git

---

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/your-org/gigaboard.git
cd gigaboard
```

### 2. Настройка окружения

Скопируйте `.env.example` в `.env` и заполните значения:

```bash
cp .env.example .env
nano .env  # или vim, code, etc.
```

**Критически важные переменные:**

```env
# Сгенерируйте secure ключи (минимум 32 символа)
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

# Безопасный пароль для PostgreSQL
POSTGRES_PASSWORD=$(openssl rand -hex 16)

# GigaChat API ключ (получите на https://developers.sber.ru/portal)
GIGACHAT_API_KEY=your_actual_api_key_here

# Ваш домен (для CORS)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 3. Запуск сервисов

```bash
# Production режим
docker-compose up -d

# Проверка статуса
docker-compose ps

# Логи
docker-compose logs -f
```

### 4. Проверка работоспособности

```bash
# Backend health check
curl http://localhost:8000/health

# Frontend
curl http://localhost:80/health

# PostgreSQL
docker-compose exec postgres pg_isready -U gigaboard

# Redis
docker-compose exec redis redis-cli ping
```

---

## 🔧 Production настройки

### Nginx как reverse proxy (рекомендуется)

Создайте конфигурацию для Nginx на хосте:

```nginx
# /etc/nginx/sites-available/gigaboard

upstream gigaboard_frontend {
    server localhost:80;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Max upload size (for large files)
    client_max_body_size 100M;

    location / {
        proxy_pass http://gigaboard_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

Активируйте конфигурацию:

```bash
sudo ln -s /etc/nginx/sites-available/gigaboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL сертификаты (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

## 📦 Управление сервисами

### Основные команды

```bash
# Запуск всех сервисов
docker-compose up -d

# Остановка всех сервисов
docker-compose down

# Перезапуск конкретного сервиса
docker-compose restart backend

# Просмотр логов
docker-compose logs -f backend
docker-compose logs -f frontend

# Обновление после pull новых изменений
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Выполнение команд внутри контейнеров

```bash
# Alembic миграции
docker-compose exec backend alembic upgrade head
docker-compose exec backend alembic revision --autogenerate -m "description"

# Python shell
docker-compose exec backend python

# PostgreSQL psql
docker-compose exec postgres psql -U gigaboard -d gigaboard

# Redis CLI
docker-compose exec redis redis-cli
```

---

## 🔐 Безопасность

### Checklist для production

- [ ] Изменены все дефолтные пароли в `.env`
- [ ] `SECRET_KEY` и `JWT_SECRET` сгенерированы криптографически стойкими
- [ ] PostgreSQL не открыт наружу (только через Docker network)
- [ ] Redis не открыт наружу
- [ ] Настроен HTTPS с валидными сертификатами
- [ ] `DEBUG=false` в production
- [ ] CORS настроен только для вашего домена
- [ ] Firewall настроен (открыты только 80, 443, 22)
- [ ] Регулярные бэкапы БД настроены
- [ ] Мониторинг и алерты настроены

### Рекомендуемые firewall правила

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

---

## 💾 Бэкапы

### Автоматический бэкап PostgreSQL

Создайте скрипт `/opt/gigaboard/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/gigaboard/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
POSTGRES_USER="gigaboard"
POSTGRES_DB="gigaboard"

mkdir -p $BACKUP_DIR

docker-compose exec -T postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB | \
    gzip > "$BACKUP_DIR/backup_$TIMESTAMP.sql.gz"

# Удалить бэкапы старше 7 дней
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: backup_$TIMESTAMP.sql.gz"
```

Добавьте в crontab:

```bash
# Бэкап каждый день в 3:00 утра
0 3 * * * /opt/gigaboard/backup.sh >> /var/log/gigaboard-backup.log 2>&1
```

### Восстановление из бэкапа

```bash
# Остановите backend
docker-compose stop backend

# Восстановите данные
gunzip -c /opt/gigaboard/backups/backup_20260204_030000.sql.gz | \
    docker-compose exec -T postgres psql -U gigaboard -d gigaboard

# Запустите backend
docker-compose start backend
```

---

## 📊 Мониторинг

### Health checks

Все сервисы имеют встроенные health checks:

```bash
# Backend
curl http://localhost:8000/health

# Frontend
curl http://localhost:80/health

# PostgreSQL
docker-compose exec postgres pg_isready

# Redis
docker-compose exec redis redis-cli ping
```

### Рекомендуемые инструменты мониторинга

- **Grafana + Prometheus** — метрики и дашборды
- **Loki** — централизованные логи
- **Uptime Kuma** — мониторинг доступности
- **Sentry** — отслеживание ошибок

---

## 🔄 Обновление

### Стандартная процедура обновления

```bash
# 1. Бэкап
/opt/gigaboard/backup.sh

# 2. Pull новых изменений
git pull origin main

# 3. Остановка сервисов
docker-compose down

# 4. Rebuild образов
docker-compose build --no-cache

# 5. Миграции БД
docker-compose run --rm backend alembic upgrade head

# 6. Запуск
docker-compose up -d

# 7. Проверка
docker-compose ps
docker-compose logs -f
```

### Zero-downtime обновление (advanced)

Для критических production систем используйте blue-green deployment или rolling updates через Kubernetes/Docker Swarm.

---

## 🐛 Troubleshooting

### Backend не запускается

```bash
# Проверьте логи
docker-compose logs backend

# Проверьте подключение к БД
docker-compose exec backend python -c "from app.core import get_db; print('DB OK')"

# Проверьте миграции
docker-compose exec backend alembic current
docker-compose exec backend alembic upgrade head
```

### Frontend показывает ошибки API

```bash
# Проверьте nginx конфигурацию
docker-compose exec frontend cat /etc/nginx/conf.d/default.conf

# Проверьте доступность backend
docker-compose exec frontend wget -O- http://backend:8000/health
```

### PostgreSQL connection refused

```bash
# Проверьте статус
docker-compose ps postgres

# Проверьте логи
docker-compose logs postgres

# Перезапустите
docker-compose restart postgres
```

### Проблемы с GigaChat API

```bash
# Проверьте API ключ
docker-compose exec backend python -c "import os; print(os.getenv('GIGACHAT_API_KEY'))"

# Тестовый запрос
docker-compose exec backend python -c "
from app.services.gigachat_service import get_gigachat_service
import asyncio
async def test():
    gc = get_gigachat_service()
    result = await gc.chat_completion([{'role': 'user', 'content': 'Привет!'}])
    print(result)
asyncio.run(test())
"
```

---

## 📞 Поддержка

- **Документация**: [docs/README.md](docs/README.md)
- **Issues**: GitHub Issues
- **Email**: support@gigaboard.local

---

**Автор**: GigaBoard Team  
**Последнее обновление**: 4 февраля 2026
