# NOTE: Lazy imports для избежания circular dependencies
# Импортируйте сервисы напрямую там, где они нужны:
# from app.services.auth_service import AuthService

__all__ = [
    "AuthService",
    "ProjectService",
    "BoardService",
    "WidgetNodeService",
    "CommentNodeService",
    "EdgeService",
]
