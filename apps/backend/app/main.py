import logging
import sys
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
import socketio

# Fix Windows console encoding for emoji support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7 fallback
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from .core import settings, init_db, close_db, init_redis, close_redis, sio, register_socketio_events
from .routes import (
    auth_router,
    health_router,
    projects_router,
    boards_router,
    edges_router,
    widget_nodes_router,
    comment_nodes_router,
    ai_assistant_router,
    source_nodes_router,
    content_nodes_router,
    database_router,
    files_router,
    extraction_router,
    ai_resolver_router,
)
from .services.gigachat_service import initialize_gigachat_service, get_gigachat_service
from .services.multi_agent.engine import MultiAgentEngine

# Setup logging
logging.basicConfig(level=logging.INFO)
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

# Global MultiAgentEngine singleton
_multi_agent_engine: MultiAgentEngine | None = None

def get_multi_agent_engine() -> MultiAgentEngine | None:
    """Get the global MultiAgentEngine instance."""
    return _multi_agent_engine

# FastAPI app initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting GigaBoard Backend...")
    
    # Track initialization status
    redis_ok = False
    gigachat_ok = False
    
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
    
    try:
        await init_redis()
        redis_ok = True
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.error(f"❌ Failed to connect Redis: {e}")
        logger.warning("⚠️  Multi-Agent features will be disabled")
    
    # Initialize GigaChat service
    if settings.GIGACHAT_API_KEY:
        try:
            initialize_gigachat_service(
                api_key=settings.GIGACHAT_API_KEY,
                model=settings.GIGACHAT_MODEL,
                temperature=settings.GIGACHAT_TEMPERATURE,
                max_tokens=settings.GIGACHAT_MAX_TOKENS,
                scope=settings.GIGACHAT_SCOPE,
                verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
            )
            gigachat_ok = True
            logger.info(f"✅ GigaChat service initialized (model: {settings.GIGACHAT_MODEL}, scope: {settings.GIGACHAT_SCOPE})")
        except Exception as e:
            logger.error(f"❌ Failed to initialize GigaChat: {e}")
            logger.warning("⚠️  AI features will be disabled")
    else:
        logger.warning("⚠️  GIGACHAT_API_KEY not set - AI features will be disabled")
    
    # Initialize MultiAgentEngine (requires both Redis and GigaChat)
    global _multi_agent_engine
    if redis_ok and gigachat_ok:
        try:
            _multi_agent_engine = MultiAgentEngine(
                gigachat_api_key=settings.GIGACHAT_API_KEY,
                enable_agents=["planner", "search", "analyst", "reporter", "researcher", "transformation", "suggestions"],
                adaptive_planning=True
            )
            await _multi_agent_engine.initialize()
            logger.info("✅ MultiAgentEngine initialized with suggestions agent")
        except Exception as e:
            logger.error(f"❌ Failed to initialize MultiAgentEngine: {e}", exc_info=True)
            logger.warning("⚠️  Widget Suggestions and Multi-Agent features will not be available")
            _multi_agent_engine = None
    else:
        logger.warning("⚠️  MultiAgentEngine disabled (requires Redis and GigaChat)")
        if not redis_ok:
            logger.warning("   - Redis: ❌ Not connected")
        if not gigachat_ok:
            logger.warning("   - GigaChat: ❌ Not initialized")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    try:
        # Shutdown MultiAgentEngine first
        if _multi_agent_engine:
            try:
                await _multi_agent_engine.shutdown()
                logger.info("✅ MultiAgentEngine shut down")
            except Exception as e:
                logger.error(f"❌ Failed to shutdown MultiAgentEngine: {e}")
        
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
    lifespan=lifespan
)

# CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
fastapi_app.include_router(health_router)
fastapi_app.include_router(auth_router)
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
fastapi_app.include_router(ai_resolver_router)

# Database routes
fastapi_app.include_router(database_router)

# File upload routes
fastapi_app.include_router(files_router)

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
        # Debug logging
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
