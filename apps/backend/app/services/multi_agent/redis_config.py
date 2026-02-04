"""
Redis connection configuration для Message Bus.
"""
import logging
from typing import Optional
from redis import asyncio as aioredis
from ...core import settings

logger = logging.getLogger(__name__)


class RedisConfig:
    """Redis configuration для Multi-Agent Message Bus."""
    
    # Parse Redis URL from settings
    # Используем тот же REDIS_URL что и основное приложение, но с другой DB
    REDIS_URL: str = settings.REDIS_URL
    REDIS_AGENT_DB: int = getattr(settings, 'REDIS_AGENT_DB', 1)  # Отдельная DB для агентов
    
    # Connection pool settings
    MAX_CONNECTIONS: int = 50
    SOCKET_CONNECT_TIMEOUT: int = 5
    SOCKET_TIMEOUT: int = None  # No timeout for PubSub connections
    SOCKET_KEEPALIVE: bool = True
    SOCKET_KEEPALIVE_OPTIONS: Optional[dict] = None  # Не используем platform-specific опции
    
    # Message TTL settings
    MESSAGE_HISTORY_TTL: int = 3600  # 1 час
    SESSION_TTL: int = 3600          # 1 час
    
    @classmethod
    def get_redis_url(cls) -> str:
        """Получить Redis URL для подключения с нужной DB."""
        # Заменяем DB в URL если нужно
        base_url = cls.REDIS_URL.rsplit('/', 1)[0]  # Убираем /0 или /1 в конце
        return f"{base_url}/{cls.REDIS_AGENT_DB}"
    
    @classmethod
    async def create_redis_client(cls) -> aioredis.Redis:
        """
        Создать Redis client для Message Bus.
        
        Returns:
            aioredis.Redis: Async Redis client
        """
        try:
            client = await aioredis.from_url(
                cls.get_redis_url(),
                max_connections=cls.MAX_CONNECTIONS,
                socket_connect_timeout=cls.SOCKET_CONNECT_TIMEOUT,
                socket_timeout=cls.SOCKET_TIMEOUT,
                socket_keepalive=cls.SOCKET_KEEPALIVE,
                socket_keepalive_options=cls.SOCKET_KEEPALIVE_OPTIONS,
                decode_responses=True,  # Автоматически декодировать в strings
            )
            
            # Проверить подключение
            await client.ping()
            logger.info(f"✅ Connected to Redis for Message Bus: {cls.get_redis_url()}")
            
            return client
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise


# Channel patterns для pub/sub
class ChannelPatterns:
    """Redis channel patterns для различных типов сообщений."""
    
    # Broadcast канал - все агенты подписаны
    BROADCAST = "gigaboard:board:{board_id}:agents:broadcast"
    
    # Direct inbox для каждого агента
    AGENT_INBOX = "gigaboard:agents:{agent_name}:inbox"
    
    # UI events - для фронтенда
    UI_EVENTS = "gigaboard:board:{board_id}:agents:ui_events"
    
    # Results канал - для Orchestrator
    SESSION_RESULTS = "gigaboard:sessions:{session_id}:results"
    
    # Errors канал - централизованный
    ERRORS = "gigaboard:agents:errors"
    
    @staticmethod
    def get_broadcast_channel(board_id: str) -> str:
        """Получить broadcast канал для доски."""
        return ChannelPatterns.BROADCAST.format(board_id=board_id)
    
    @staticmethod
    def get_agent_inbox(agent_name: str) -> str:
        """Получить inbox канал для агента."""
        return ChannelPatterns.AGENT_INBOX.format(agent_name=agent_name)
    
    @staticmethod
    def get_ui_events_channel(board_id: str) -> str:
        """Получить UI events канал для доски."""
        return ChannelPatterns.UI_EVENTS.format(board_id=board_id)
    
    @staticmethod
    def get_session_results_channel(session_id: str) -> str:
        """Получить results канал для сессии."""
        return ChannelPatterns.SESSION_RESULTS.format(session_id=session_id)
