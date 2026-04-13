import asyncio
import logging
import os
import sys
import io
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
import socketio

# Windows: SelectorEventLoop может стабильнее работать с сокетами (asyncpg, Redis)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        sys.stdout.reconfigure(encoding='utf-8', write_through=True)
        sys.stderr.reconfigure(encoding='utf-8', write_through=True)
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)

from .core import settings, init_db, close_db, init_redis, close_redis, check_postgres_connectivity, sio, register_socketio_events
from .core.database import async_session_maker
from .services.auth_service import AuthService
from .routes import (
    auth_router,
    health_router,
    users_router,
    projects_router,
    boards_router,
    edges_router,
    widget_nodes_router,
    comment_nodes_router,
    ai_assistant_router,
    ai_assistant_dashboard_router,
    ai_resolver_router,
    research_router,
    source_nodes_router,
    content_nodes_router,
    database_router,
    files_router,
    extraction_router,
    library_router,
    dashboards_router,
    public_router,
    dimensions_router,
    board_filter_router,
    dashboard_filter_router,
    preset_router,
    user_settings_router,
    admin_router,
)
from .services.multi_agent.orchestrator import Orchestrator

# Setup logging (force=True ensures handler is added even if uvicorn pre-configured root)
logging.basicConfig(level=logging.INFO, force=True, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Отключаем излишнее логирование SQLAlchemy
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)  # Root SQLAlchemy logger
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool.impl').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

# Отключаем излишнее Socket.IO логирование
logging.getLogger('app.core.socketio').setLevel(logging.WARNING)
logging.getLogger('socketio.server').setLevel(logging.WARNING)
logging.getLogger('engineio.server').setLevel(logging.WARNING)

# Отключаем успешные GET запросы uvicorn (200 OK)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)

# Structurizer: DEBUG для отладки парсинга (дамп в logs/structurizer_last_response.txt при ошибке)
logging.getLogger("app.services.multi_agent.agents.structurizer").setLevel(logging.DEBUG)

# Global Orchestrator V2 singleton
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator | None:
    """Get the global Orchestrator V2 instance."""
    return _orchestrator


def _db_target_for_log(url: str) -> str:
    """host:port/db без учётных данных — для проверки, куда смотрит контейнер."""
    try:
        u = urlparse(url)
        host = u.hostname or "?"
        port = u.port or 5432
        db = (u.path or "/").strip("/").split("/")[0] or "?"
        return f"{host}:{port}/{db}"
    except Exception:
        return "?"


# FastAPI app initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting GigaBoard Backend...")
    logger.info("Database target (DATABASE_URL): %s", _db_target_for_log(settings.DATABASE_URL))
    logger.info(
        "File storage: STORAGE_BACKEND=%s STORAGE_LOCAL_PATH=%s GIGABOARD_IN_DOCKER=%s",
        settings.STORAGE_BACKEND,
        settings.STORAGE_LOCAL_PATH,
        os.getenv("GIGABOARD_IN_DOCKER", ""),
    )
    
    # Track initialization status
    redis_ok = False

    # Сначала init_db (разогрев пула — часто первое подключение на Windows падает, второе проходит)
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error("❌ Failed to initialize database: %s", e, exc_info=True)
    # Затем проверка доступности (использует соединение из пула)
    pg_ok, pg_msg = await check_postgres_connectivity()
    if pg_ok:
        logger.info("✅ PostgreSQL is reachable (SELECT 1)")
    else:
        logger.warning("⚠️ PostgreSQL connectivity check failed (pool may still work): %s", pg_msg)

    # Создать/обновить учётную запись администратора из env (ADMIN_EMAIL, ADMIN_PASSWORD)
    _admin_email = (getattr(settings, "ADMIN_EMAIL", "") or "").strip()
    _admin_pass = getattr(settings, "ADMIN_PASSWORD", "") or ""
    logger.info("Startup: ADMIN_EMAIL set=%s (from .env)", bool(_admin_email))
    if _admin_email and _admin_pass:
        try:
            async with async_session_maker() as db:
                await AuthService.ensure_admin_user(db)
            logger.info("✅ Admin user ensured from ADMIN_EMAIL")
        except Exception as e:
            logger.warning(f"⚠️ Could not ensure admin user: {e}")
    
    try:
        await init_redis()
        redis_ok = True
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.error(f"❌ Failed to connect Redis: {e}")
        logger.warning("⚠️  Multi-Agent features will be disabled")
    
    # LLM (GigaChat и др.) настраивается только в панели администратора — модели в Настройках LLM.

    # Initialize Orchestrator V2 (требуется только Redis; LLM — из моделей в панели администратора)
    global _orchestrator
    if redis_ok:
        try:
            _orchestrator = Orchestrator(
                # Env-key остаётся резервным fallback для LLMRouter
                # (например, если внешний OpenAI-compatible провайдер вернул 401/403).
                gigachat_api_key=(settings.GIGACHAT_API_KEY or None),
                enable_agents=[
                    "planner", "discovery", "research",
                    "structurizer", "analyst", "transform_codex",
                    "widget_codex", "context_filter", "reporter",
                ],
                adaptive_planning=True,
                db_session_factory=async_session_maker,
            )
            await _orchestrator.initialize()
            logger.info("✅ Orchestrator V2 initialized with all agents")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Orchestrator V2: {e}", exc_info=True)
            logger.warning("⚠️  Multi-Agent features will not be available")
            _orchestrator = None
    else:
        logger.warning("⚠️  Orchestrator V2 disabled (requires Redis)")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    try:
        # Shutdown Orchestrator V2
        if _orchestrator:
            try:
                await _orchestrator.shutdown()
                logger.info("✅ Orchestrator V2 shut down")
            except Exception as e:
                logger.error(f"❌ Failed to shutdown Orchestrator V2: {e}")
        
        try:
            await close_db()
            logger.info("✅ Database closed")
        except Exception as e:
            logger.error(f"❌ Failed to close database: {e}")
        
        try:
            await close_redis()
            logger.info("✅ Redis closed")
        except Exception as e:
            logger.error(f"❌ Failed to close Redis: {e}")
    except KeyboardInterrupt:
        logger.info("⚠️  Shutdown interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error during shutdown: {e}")

fastapi_app = FastAPI(
    title="GigaBoard API",
    description="AI-Powered Analytics Dashboard",
    version="0.1.0",
    lifespan=lifespan,
    # Иначе 307 при несовпадении trailing slash: браузер/axios может повторить POST без Authorization → 403 «Not authenticated».
    redirect_slashes=False,
)

# CORS middleware (при allow_credentials=True нельзя использовать "*" — указываем явные origins)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
fastapi_app.include_router(health_router)
fastapi_app.include_router(auth_router)
fastapi_app.include_router(users_router)
fastapi_app.include_router(projects_router)
fastapi_app.include_router(boards_router)
fastapi_app.include_router(edges_router)

# Node routes
fastapi_app.include_router(widget_nodes_router)
fastapi_app.include_router(comment_nodes_router)

# Source-Content Node Architecture routes
fastapi_app.include_router(source_nodes_router)
fastapi_app.include_router(content_nodes_router)
fastapi_app.include_router(extraction_router)

# AI Assistant routes
fastapi_app.include_router(ai_assistant_router)
fastapi_app.include_router(ai_assistant_dashboard_router)
fastapi_app.include_router(ai_resolver_router)
fastapi_app.include_router(research_router)

# Database routes
fastapi_app.include_router(database_router)

# File upload routes
fastapi_app.include_router(files_router)

# Dashboard system routes
fastapi_app.include_router(library_router)
fastapi_app.include_router(dashboards_router)
fastapi_app.include_router(public_router)

# Cross-filter system routes
fastapi_app.include_router(dimensions_router)
fastapi_app.include_router(board_filter_router)
fastapi_app.include_router(dashboard_filter_router)
fastapi_app.include_router(preset_router)

# User profile & AI settings routes
fastapi_app.include_router(user_settings_router)

# Admin routes (system LLM settings, playground)
fastapi_app.include_router(admin_router)

# Register Socket.IO event handlers
register_socketio_events(sio)

# Create Socket.IO ASGI app (handles /socket.io/* internally)
socket_io_asgi = socketio.ASGIApp(sio)

# Combine Socket.IO and FastAPI using ASGI router class
class CombinedASGI:
    def __init__(self, fastapi_app, socket_io_app):
        self.fastapi_app = fastapi_app
        self.socket_io_app = socket_io_app
        logger.info("🔧 CombinedASGI router initialized")
    
    async def __call__(self, scope, receive, send):
        """
        Route requests to Socket.IO or FastAPI based on path.
        Socket.IO handles /socket.io/* paths, everything else goes to FastAPI.
        """
        if scope["type"] in ("http", "websocket"):
            logger.info(f"[ROUTER] {scope['type'].upper()} {scope['path']}")
        
        if scope["type"] in ("http", "websocket") and scope["path"].startswith("/socket.io"):
            logger.info(f"[ROUTER] -> Socket.IO")
            await self.socket_io_app(scope, receive, send)
        else:
            logger.info(f"[ROUTER] -> FastAPI")
            await self.fastapi_app(scope, receive, send)

# Export combined app and sio for use in routes
app = CombinedASGI(fastapi_app, socket_io_asgi)
__all__ = ["app", "sio"]
