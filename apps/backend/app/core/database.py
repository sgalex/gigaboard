from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.dialects import postgresql
from .config import settings
from .base import Base

# Create async engine with explicit asyncpg dialect
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Disable SQLAlchemy query logging (was settings.DEBUG)
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=3600,
)

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
