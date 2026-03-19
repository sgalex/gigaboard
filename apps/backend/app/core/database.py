import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from .config import settings
from .base import Base

_log = logging.getLogger(__name__)


def _db_host_from_url(url: str) -> str:
    """Извлечь host:port из DATABASE_URL для логов (без пароля)."""
    if not url or "@" not in url or "://" not in url:
        return "?"
    return url.split("@", 1)[1].split("/")[0].split("?")[0]


# Параметры движка: при DB_USE_NULL_POOL=1 пул отключён (новое соединение на запрос) — обход ConnectionResetError на Windows
_engine_kw: dict = {
    "echo": False,
    "future": True,
    "pool_timeout": settings.DB_POOL_TIMEOUT,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
}
if getattr(settings, "DB_USE_NULL_POOL", False):
    _engine_kw["poolclass"] = NullPool
else:
    _engine_kw["pool_size"] = settings.DB_POOL_SIZE
    _engine_kw["max_overflow"] = settings.DB_MAX_OVERFLOW

engine = create_async_engine(settings.DATABASE_URL, **_engine_kw)
_log.info(
    "DB engine created: pool=%s, host=%s",
    "NullPool" if getattr(settings, "DB_USE_NULL_POOL", False) else "QueuePool",
    _db_host_from_url(settings.DATABASE_URL),
)

async def check_postgres_connectivity() -> tuple[bool, str]:
    """
    Проверка доступности PostgreSQL: открыть соединение, выполнить SELECT 1.
    Returns:
        (True, "ok") при успехе, (False, "error message") при ошибке.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        _log.info("PostgreSQL connectivity check: OK (SELECT 1)")
        return True, "ok"
    except Exception as e:
        _log.warning("PostgreSQL connectivity check FAILED: %s", e)
        _log.debug("PostgreSQL check traceback:", exc_info=True)
        return False, str(e)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True,
)

async def get_db():
    """Dependency for getting DB session"""
    async with async_session_maker() as session:
        yield session

async def init_db():
    """Initialize database - create tables if they don't exist"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        # Tables might already exist (created by Alembic migrations)
        # This is fine - we just log it
        import logging
        logging.debug(f"Database init note: {e}")

async def close_db():
    """Close database connection"""
    await engine.dispose()
