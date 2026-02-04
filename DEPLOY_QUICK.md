# Quick Deployment Commands

## Production Deployment

```bash
# 1. Setup environment
cp .env.example .env
nano .env  # Fill in all required values

# 2. Build and start services
docker-compose up -d

# 3. Check status
docker-compose ps
docker-compose logs -f
```

## Health Checks

```bash
# Backend
curl http://localhost:8000/health

# Frontend  
curl http://localhost:80/health

# Database
docker-compose exec postgres pg_isready -U gigaboard

# Redis
docker-compose exec redis redis-cli ping
```

## Management Commands

```bash
# View logs
docker-compose logs -f [service_name]

# Restart service
docker-compose restart [service_name]

# Execute command in container
docker-compose exec [service_name] [command]

# Database migrations
docker-compose exec backend alembic upgrade head

# Create database backup
docker-compose exec postgres pg_dump -U gigaboard gigaboard > backup.sql
```

## Update Procedure

```bash
# 1. Pull changes
git pull origin main

# 2. Rebuild
docker-compose down
docker-compose build --no-cache

# 3. Restart
docker-compose up -d

# 4. Verify
docker-compose ps
```

## Troubleshooting

```bash
# View service logs
docker-compose logs [service_name]

# Restart problematic service
docker-compose restart [service_name]

# Full restart
docker-compose down
docker-compose up -d

# Check resource usage
docker stats
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed documentation.
