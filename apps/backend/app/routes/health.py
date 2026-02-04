from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core import get_db
from ..core import get_redis
from ..services.gigachat_service import get_gigachat_service

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "ok",
        "service": "gigaboard-backend",
        "version": "0.1.0"
    }

@router.get("/api/v1/health")
async def api_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check - checks database and Redis"""
    try:
        # Check database
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    try:
        # Check Redis
        redis = get_redis()
        await redis.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    # Check GigaChat (optional)
    try:
        gigachat = get_gigachat_service()
        gigachat_health = await gigachat.health_check()
        gigachat_status = gigachat_health.get("status", "unknown")
    except RuntimeError:
        # Service not initialized (no API key)
        gigachat_status = "not_configured"
    except Exception as e:
        gigachat_status = f"error: {str(e)}"
    
    if db_status != "ok" or redis_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "database": db_status,
                "redis": redis_status,
                "gigachat": gigachat_status
            }
        )
    
    return {
        "status": "ok",
        "database": db_status,
        "redis": redis_status,
        "gigachat": gigachat_status,
        "service": "gigaboard-backend"
    }
