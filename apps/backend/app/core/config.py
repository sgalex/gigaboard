import os
from pathlib import Path

from dotenv import load_dotenv


def _running_in_docker() -> bool:
    """В контейнере не читаем .env с хоста — только переменные окружения (Compose / k8s)."""
    if os.getenv("GIGABOARD_IN_DOCKER", "").lower() in ("1", "true", "yes"):
        return True
    return Path("/.dockerenv").exists()


# Единственный источник env — корень репозитория (GigaBoard). apps/backend/.env не используется.
_project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
_env_root = _project_root / ".env"
_env_local = _project_root / ".env.local"
if not _running_in_docker():
    if _env_root.is_file():
        load_dotenv(_env_root)
    if _env_local.is_file():
        load_dotenv(_env_local, override=True)  # переопределения для локального запуска (без Docker)

class Settings:
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost:5432/gigaboard_db"
    )
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    # NullPool = новое соединение на каждый запрос (обход сбоев пула на Windows при ConnectionResetError)
    DB_USE_NULL_POOL: bool = os.getenv("DB_USE_NULL_POOL", "").lower() in ("1", "true", "yes")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_POOL_SIZE: int = int(os.getenv("REDIS_POOL_SIZE", "10"))
    REDIS_TIMEOUT: int = int(os.getenv("REDIS_TIMEOUT", "5"))
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    
    # Server
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # GigaChat
    GIGACHAT_API_KEY: str = os.getenv("GIGACHAT_API_KEY", "")
    GIGACHAT_MODEL: str = os.getenv("GIGACHAT_MODEL", "GigaChat")
    GIGACHAT_TEMPERATURE: float = float(os.getenv("GIGACHAT_TEMPERATURE", "0.7"))
    GIGACHAT_MAX_TOKENS: int = int(os.getenv("GIGACHAT_MAX_TOKENS", "2048"))
    GIGACHAT_VERIFY_SSL: bool = os.getenv("GIGACHAT_VERIFY_SSL", "False").lower() == "true"
    GIGACHAT_SCOPE: str = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_CORP")
    
    # File Storage
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "database")  # 'database', 'local' or 's3'
    STORAGE_LOCAL_PATH: str = os.getenv("STORAGE_LOCAL_PATH", "data/uploads")
    STORAGE_MAX_FILE_SIZE_MB: int = int(os.getenv("STORAGE_MAX_FILE_SIZE_MB", "100"))
    
    # S3 Storage (optional, for production)
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "")  # MinIO or S3
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "gigaboard-uploads")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # CORS (через запятую). Для Docker с фронтом на :80 добавьте http://localhost и http://127.0.0.1
    _cors_default = (
        "http://localhost:5173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:3000,"
        "http://localhost,http://127.0.0.1"
    )
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", _cors_default).split(",")
        if o.strip()
    ]

    # Admin (опционально): если заданы оба — при старте создаётся/обновляется пользователь с role=admin
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

settings = Settings()
