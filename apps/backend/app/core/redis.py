import redis.asyncio as redis
from .config import settings

redis_client = None

async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    redis_client = await redis.from_url(
        settings.REDIS_URL,
        encoding="utf8",
        decode_responses=True,
        socket_connect_timeout=settings.REDIS_TIMEOUT,
        socket_keepalive=True,
    )
    return redis_client

async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None

def get_redis():
    """Get Redis client instance"""
    global redis_client
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client
