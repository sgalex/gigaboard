"""
AI Assistant endpoints для чата с пользователем в контексте доски.

Endpoints:
- POST /api/v1/boards/{board_id}/ai/chat - отправить сообщение AI
- GET /api/v1/boards/{board_id}/ai/chat/history - получить историю чата
- DELETE /api/v1/boards/{board_id}/ai/chat/session/{session_id} - очистить сессию

См. docs/AI_ASSISTANT.md и docs/API.md
"""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import get_db
from ..middleware.auth import get_current_user
from ..models import User
from ..services.ai_service import AIService
from ..schemas.ai_chat import (
    AIChatRequest,
    AIChatResponse,
    ChatHistoryResponse,
    ChatMessageSchema,
    SuggestedAction
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/boards", tags=["ai-assistant"])


@router.post("/{board_id}/ai/chat", response_model=AIChatResponse)
async def chat_with_ai(
    board_id: UUID,
    request: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Отправить сообщение AI Assistant в контексте доски.
    
    AI анализирует текущее состояние доски (DataNode, WidgetNode, Edge)
    и отвечает на вопрос пользователя, предлагая действия при необходимости.
    
    Args:
        board_id: UUID доски
        request: Запрос с сообщением и опциональным контекстом
        current_user: Текущий пользователь
        db: Database session
        
    Returns:
        AIChatResponse с ответом AI и suggested_actions
        
    Raises:
        HTTPException: 404 если доска не найдена, 500 при ошибке AI
    """
    try:
        ai_service = AIService(db)
        
        result = await ai_service.chat(
            board_id=board_id,
            user_id=current_user.id,
            message=request.message,
            session_id=request.session_id,
            context=request.context,
        )
        
        # Преобразуем suggested_actions в Pydantic модели
        suggested_actions = None
        if result.get("suggested_actions"):
            suggested_actions = [
                SuggestedAction(**action) 
                for action in result["suggested_actions"]
            ]
        
        return AIChatResponse(
            response=result["response"],
            session_id=UUID(result["session_id"]),
            suggested_actions=suggested_actions,
            context_used=result.get("context_used"),
        )
        
    except ValueError as e:
        logger.error(f"Validation error in chat_with_ai: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in chat_with_ai: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process AI request: {str(e)}"
        )


@router.get("/{board_id}/ai/chat/history/me", response_model=ChatHistoryResponse)
async def get_my_chat_history(
    board_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="Максимум сообщений"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить историю чата текущего пользователя для доски.
    Автоматически находит последнюю сессию пользователя для этой доски.
    
    Args:
        board_id: UUID доски
        limit: Максимальное количество сообщений
        current_user: Текущий пользователь
        db: Database session
        
    Returns:
        ChatHistoryResponse со списком сообщений
    """
    try:
        from ..models.chat_message import ChatMessage
        from sqlalchemy import select, and_, desc
        
        # Находим последнюю сессию пользователя для этой доски
        session_query = (
            select(ChatMessage.session_id)
            .where(
                and_(
                    ChatMessage.board_id == board_id,
                    ChatMessage.user_id == current_user.id
                )
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(1)
        )
        
        session_result = await db.execute(session_query)
        session_id = session_result.scalar_one_or_none()
        
        # Если нет истории - возвращаем пустой список
        if not session_id:
            return ChatHistoryResponse(
                messages=[],
                session_id=None,
                total_messages=0
            )
        
        # Получаем все сообщения из этой сессии
        query = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.board_id == board_id,
                    ChatMessage.session_id == session_id,
                    ChatMessage.user_id == current_user.id
                )
            )
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        
        result = await db.execute(query)
        chat_messages = result.scalars().all()
        
        message_schemas = []
        for msg in chat_messages:
            suggested_actions = None
            if msg.suggested_actions:
                suggested_actions = [
                    SuggestedAction(**action)
                    for action in msg.suggested_actions
                ]
            
            message_schemas.append(
                ChatMessageSchema(
                    id=msg.id,
                    board_id=msg.board_id,
                    user_id=msg.user_id,
                    session_id=msg.session_id,
                    role=msg.role,
                    content=msg.content,
                    context=msg.context,
                    suggested_actions=suggested_actions,
                    created_at=msg.created_at,
                )
            )
        
        return ChatHistoryResponse(
            messages=message_schemas,
            session_id=session_id,
            total_messages=len(message_schemas)
        )
        
    except Exception as e:
        logger.error(f"Error in get_my_chat_history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat history: {str(e)}"
        )


@router.get("/{board_id}/ai/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    board_id: UUID,
    session_id: UUID = Query(..., description="UUID сессии чата"),
    limit: int = Query(50, ge=1, le=200, description="Максимум сообщений"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить историю чата для конкретной сессии.
    
    Args:
        board_id: UUID доски
        session_id: UUID сессии чата
        limit: Максимальное количество сообщений
        current_user: Текущий пользователь
        db: Database session
        
    Returns:
        ChatHistoryResponse со списком сообщений
    """
    try:
        ai_service = AIService(db)
        
        messages = await ai_service.get_chat_history(
            board_id=board_id,
            session_id=session_id,
            limit=limit
        )
        
        # Преобразуем в Pydantic модели
        from ..models.chat_message import ChatMessage
        from sqlalchemy import select, and_
        
        query = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.board_id == board_id,
                    ChatMessage.session_id == session_id
                )
            )
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        
        result = await db.execute(query)
        chat_messages = result.scalars().all()
        
        message_schemas = []
        for msg in chat_messages:
            suggested_actions = None
            if msg.suggested_actions:
                suggested_actions = [
                    SuggestedAction(**action)
                    for action in msg.suggested_actions
                ]
            
            message_schemas.append(
                ChatMessageSchema(
                    id=msg.id,
                    board_id=msg.board_id,
                    user_id=msg.user_id,
                    session_id=msg.session_id,
                    role=msg.role,
                    content=msg.content,
                    context=msg.context,
                    suggested_actions=suggested_actions,
                    created_at=msg.created_at,
                )
            )
        
        return ChatHistoryResponse(
            messages=message_schemas,
            session_id=session_id,
            total_messages=len(message_schemas)
        )
        
    except Exception as e:
        logger.error(f"Error in get_chat_history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat history: {str(e)}"
        )


@router.delete("/{board_id}/ai/chat/session/{session_id}")
async def delete_chat_session(
    board_id: UUID,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Удалить все сообщения из сессии чата.
    
    Используется для "очистки" истории или удаления старых диалогов.
    
    Args:
        board_id: UUID доски
        session_id: UUID сессии для удаления
        current_user: Текущий пользователь
        db: Database session
        
    Returns:
        Количество удаленных сообщений
    """
    try:
        ai_service = AIService(db)
        
        deleted_count = await ai_service.delete_chat_session(
            board_id=board_id,
            session_id=session_id
        )
        
        return {
            "status": "success",
            "deleted_messages": deleted_count,
            "session_id": str(session_id)
        }
        
    except Exception as e:
        logger.error(f"Error in delete_chat_session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chat session: {str(e)}"
        )
