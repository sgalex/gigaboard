"""
AI Resolver API endpoints - резолвинг данных через мультиагент.

Используется в сгенерированном Python коде трансформаций.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional
import logging

from ..core import get_db
from ..models import User
from ..middleware import get_current_user
from ..services.multi_agent.agents.resolver import get_resolver_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai-resolver"])


@router.post("/resolve")
async def resolve_batch(
    params: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Резолвит batch значений через AI.
    
    Request body:
    {
        "values": ["Alice", "Bob", "Charlie"],
        "task_description": "определи пол человека по имени",
        "result_format": "string",  // optional
        "chunk_size": 50  // optional
    }
    
    Response:
    {
        "results": ["F", "M", "M"],
        "count": 3,
        "task_description": "..."
    }
    """
    try:
        values = params.get("values")
        task_description = params.get("task_description")
        
        if not values or not isinstance(values, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'values' must be a non-empty list"
            )
        
        if not task_description:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'task_description' is required"
            )
        
        logger.info(f"🔍 AI Resolve request: {len(values)} values, task: '{task_description[:50]}...'")
        
        # Создаем ResolverAgent
        resolver = get_resolver_agent()
        
        # Выполняем резолвинг
        result = await resolver.process_task(
            task={
                "type": "resolve_batch",
                "values": values,
                "task_description": task_description,
                "result_format": params.get("result_format", "string"),
                "chunk_size": params.get("chunk_size", 50)
            },
            context={"user_id": str(current_user.id)}
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI resolver failed: {result['error']}"
            )
        
        logger.info(f"✅ AI Resolve completed: {result.get('count', 0)} results")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ AI Resolve failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI resolver failed: {str(e)}"
        )
