# File Storage Configuration

## Текущая стратегия хранения файлов

### 🏗️ Архитектура

**Два режима работы:**
1. **Local Storage** (по умолчанию, для разработки и self-hosted)
2. **S3 Storage** (для продакшна, масштабируемость)

### 📁 Локальное хранилище

**Структура директорий:**
```
data/uploads/
  {user_id}/
    {year}/
      {month}/
        {file_id}.{ext}
```

**Пример:**
```
data/uploads/
  550e8400-e29b-41d4-a716-446655440000/
    2026/
      01/
        779da9a7-f048-4b42-b1ac-dfa81ad0f6ed.pdf
        a1b2c3d4-e5f6-7890-abcd-ef1234567890.xlsx
```

**Преимущества:**
- ✅ Простота настройки (нет зависимостей)
- ✅ Быстрая разработка
- ✅ Self-hosted деплой без внешних сервисов
- ✅ Контроль над данными

**Недостатки:**
- ❌ Не масштабируется горизонтально
- ❌ Backup вручную
- ❌ Нет CDN

---

### ☁️ S3-совместимое хранилище

**Поддерживаемые сервисы:**
- AWS S3
- MinIO (self-hosted S3-совместимый)
- Yandex Object Storage
- DigitalOcean Spaces
- Любой S3-совместимый сервис

**Структура ключей:**
```
{user_id}/{year}/{month}/{file_id}.{ext}
```

**Преимущества:**
- ✅ Масштабируемость (петабайты)
- ✅ Встроенный backup и репликация
- ✅ CDN интеграция
- ✅ Presigned URLs (временный доступ)

**Требования:**
```bash
pip install boto3
```

---

## 🚀 Конфигурация

### Environment Variables

```bash
# Storage Backend
STORAGE_BACKEND=local                    # 'local' или 's3'
STORAGE_LOCAL_PATH=data/uploads          # Путь для локального хранилища
STORAGE_MAX_FILE_SIZE_MB=100             # Макс. размер файла (МБ)

# S3 Configuration (только для STORAGE_BACKEND=s3)
S3_ENDPOINT_URL=https://s3.amazonaws.com # Пусто для AWS S3, URL для MinIO
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET_NAME=gigaboard-uploads
S3_REGION=us-east-1
```

### Локальная разработка (по умолчанию)

```bash
# .env
STORAGE_BACKEND=local
STORAGE_LOCAL_PATH=data/uploads
STORAGE_MAX_FILE_SIZE_MB=100
```

Файлы сохраняются в `data/uploads/` относительно корня проекта.

### Продакшн с AWS S3

```bash
# .env
STORAGE_BACKEND=s3
S3_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
S3_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_BUCKET_NAME=gigaboard-prod-uploads
S3_REGION=eu-west-1
STORAGE_MAX_FILE_SIZE_MB=500
```

### Продакшн с MinIO (self-hosted)

```bash
# .env
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://minio.yourdomain.com
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=gigaboard-uploads
S3_REGION=us-east-1
```

---

## 📝 API Endpoints

### POST /api/v1/files/upload

**Загрузка файла:**
```bash
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf"
```

**Response:**
```json
{
  "file_id": "779da9a7-f048-4b42-b1ac-dfa81ad0f6ed",
  "filename": "document.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 26030489,
  "storage_path": "550e8400.../2026/01/779da9a7...pdf"
}
```

### GET /api/v1/files/download/{file_id}

**Скачивание файла:**

**Local Storage:**
- Прямой файл через `FileResponse`

**S3 Storage:**
- Redirect на presigned URL (действует 1 час)

---

## 🔐 Безопасность

1. **Аутентификация:** Требуется JWT токен для upload/download
2. **Размер файла:** Ограничение через `STORAGE_MAX_FILE_SIZE_MB`
3. **Изоляция пользователей:** Файлы хранятся в отдельных директориях `{user_id}/`
4. **Уникальные ID:** UUID v4 для предотвращения коллизий
5. **S3 Presigned URLs:** Временный доступ (1 час) без постоянных публичных ссылок

---

## 🗂️ Управление файлами

### Очистка старых файлов

**Для local storage** (добавить в cron):
```bash
# Удалить файлы старше 90 дней
find data/uploads -type f -mtime +90 -delete
```

**Для S3** - настроить Lifecycle Policy:
```json
{
  "Rules": [{
    "Id": "Delete old files",
    "Status": "Enabled",
    "Expiration": { "Days": 90 }
  }]
}
```

### Backup

**Local storage:**
```bash
# Backup директории
tar -czf uploads-backup-$(date +%Y%m%d).tar.gz data/uploads/
```

**S3 storage:**
- Включить versioning bucket
- Настроить cross-region replication
- S3 автоматически обеспечивает 99.999999999% durability

---

## 🔄 Миграция Local → S3

```python
# Скрипт миграции (будущая задача)
from app.services.file_storage import LocalFileStorage, S3FileStorage

local = LocalFileStorage("data/uploads")
s3 = S3FileStorage()

# Перенос всех файлов
for file_path in local.base_path.rglob("*"):
    if file_path.is_file():
        file_id = file_path.stem
        with open(file_path, "rb") as f:
            await s3.save(file_id, f, user_id, file_path.name)
```

---

## 📊 Мониторинг

**Метрики для отслеживания:**
- Общий размер хранилища
- Количество файлов на пользователя
- Скорость загрузки/скачивания
- Процент успешных/неуспешных загрузок

**Local storage:**
```bash
du -sh data/uploads/*
```

**S3 storage:**
- CloudWatch (AWS)
- MinIO Console (self-hosted)

---

## 🛠️ Рекомендации по деплою

### Development
```bash
STORAGE_BACKEND=local
STORAGE_LOCAL_PATH=data/uploads
```

### Staging
```bash
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://minio-staging.local
```

### Production
```bash
STORAGE_BACKEND=s3
# AWS S3 или Yandex Object Storage
```

---

## ❓ FAQ

**Q: Можно ли использовать оба хранилища одновременно?**
A: Нет, выбирается один backend через `STORAGE_BACKEND`. Но можно реализовать гибридную стратегию: горячие данные в local, холодные в S3.

**Q: Что делать с `data/uploads/` в Git?**
A: Добавить в `.gitignore`. Файлы пользователей не должны быть в репозитории.

**Q: Как обеспечить CDN для local storage?**
A: Разместить nginx reverse proxy с кешированием или использовать S3 + CloudFront/Cloudflare.

**Q: Поддержка других storage backend (Azure Blob, Google Cloud Storage)?**
A: Можно добавить, расширив `FileStorage` абстрактный класс.
