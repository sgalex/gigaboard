from .auth import router as auth_router
from .health import router as health_router
from .users import router as users_router
from .projects import router as projects_router
from .boards import router as boards_router
from .edges import router as edges_router

# Node routes
from .widget_nodes import router as widget_nodes_router
from .comment_nodes import router as comment_nodes_router

# Source-Content Node Architecture routes
from .source_nodes import router as source_nodes_router
from .content_nodes import router as content_nodes_router
from .extraction import router as extraction_router

# AI Assistant routes
from .ai_assistant import router as ai_assistant_router
from .ai_assistant import dashboard_router as ai_assistant_dashboard_router
from .ai_resolver import router as ai_resolver_router
from .research import router as research_router

# Database routes
from .database import router as database_router

# File upload routes
from .files import router as files_router

# Dashboard system routes
from .library import router as library_router
from .dashboards import router as dashboards_router
from .public import router as public_router

# Cross-filter system routes
from .dimensions import router as dimensions_router
from .filters import board_filter_router, dashboard_filter_router, preset_router
from .user_settings import router as user_settings_router
from .admin import router as admin_router

__all__ = [
    "auth_router",
    "health_router",
    "users_router",
    "projects_router",
    "boards_router",
    "edges_router",
    "widget_nodes_router",
    "comment_nodes_router",
    "source_nodes_router",
    "content_nodes_router",
    "extraction_router",
    "ai_assistant_router",
    "ai_assistant_dashboard_router",
    "ai_resolver_router",
    "research_router",
    "database_router",
    "files_router",
    "library_router",
    "dashboards_router",
    "public_router",
    "dimensions_router",
    "board_filter_router",
    "dashboard_filter_router",
    "preset_router",
    "user_settings_router",
    "admin_router",
]
