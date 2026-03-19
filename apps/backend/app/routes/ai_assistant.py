"""
AI Assistant endpoints для чата с пользователем в контексте доски.

Endpoints:
- POST /api/v1/boards/{board_id}/ai/chat - отправить сообщение AI
- GET /api/v1/boards/{board_id}/ai/chat/history - получить историю чата
- DELETE /api/v1/boards/{board_id}/ai/chat/session/{session_id} - очистить сессию

См. docs/AI_ASSISTANT.md и docs/API.md
"""
import logging
import json
from uuid import UUID
from uuid import uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import get_db
from ..core.redis import get_redis
from ..middleware.auth import get_current_user
from ..models import User
from ..services.ai_service import AIService
from ..services.controllers import AIAssistantController
from ..schemas.ai_chat import (
    AIChatRequest,
    AIChatResponse,
    ChatHistoryResponse,
    ChatMessageSchema,
    SuggestedAction
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/boards", tags=["ai-assistant"])
dashboard_router = APIRouter(prefix="/api/v1/dashboards", tags=["ai-assistant"])

_DASHBOARD_CHAT_HISTORY_MAX = 50


def _dashboard_chat_last_session_key(
    *,
    dashboard_id: UUID,
    user_id: UUID,
) -> str:
    return f"ai:dashboard_chat:last_session:{dashboard_id}:{user_id}"


def _dashboard_chat_history_key(
    *,
    dashboard_id: UUID,
    user_id: UUID,
    session_id: UUID,
) -> str:
    return f"ai:dashboard_chat:{dashboard_id}:{user_id}:{session_id}"


async def _get_dashboard_chat_history(
    *,
    dashboard_id: UUID,
    user_id: UUID,
    session_id: UUID,
    limit: int = 20,
) -> list[dict]:
    """Get dashboard chat history from Redis (fallback empty)."""
    try:
        redis = get_redis()
        key = _dashboard_chat_history_key(
            dashboard_id=dashboard_id,
            user_id=user_id,
            session_id=session_id,
        )
        raw_items = await redis.lrange(key, max(0, -limit), -1)
        out: list[dict] = []
        for item in raw_items:
            try:
                parsed = json.loads(item)
                if isinstance(parsed, dict):
                    role = str(parsed.get("role", "")).strip()
                    content = str(parsed.get("content", "")).strip()
                    if role and content:
                        normalized = {"role": role, "content": content}
                        if parsed.get("id"):
                            normalized["id"] = str(parsed.get("id"))
                        if parsed.get("created_at"):
                            normalized["created_at"] = str(parsed.get("created_at"))
                        out.append(normalized)
            except Exception:
                continue
        return out
    except Exception:
        logger.warning("Failed to load dashboard chat history from Redis", exc_info=True)
        return []


async def _append_dashboard_chat_message(
    *,
    dashboard_id: UUID,
    user_id: UUID,
    session_id: UUID,
    role: str,
    content: str,
) -> None:
    """Append one dashboard chat message to Redis (best-effort)."""
    msg = {
        "id": str(uuid4()),
        "role": str(role),
        "content": str(content),
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        redis = get_redis()
        history_key = _dashboard_chat_history_key(
            dashboard_id=dashboard_id,
            user_id=user_id,
            session_id=session_id,
        )
        last_session_key = _dashboard_chat_last_session_key(
            dashboard_id=dashboard_id,
            user_id=user_id,
        )
        await redis.rpush(history_key, json.dumps(msg, ensure_ascii=False))
        await redis.ltrim(history_key, -_DASHBOARD_CHAT_HISTORY_MAX, -1)
        await redis.expire(history_key, 60 * 60 * 24 * 7)  # 7 days TTL
        await redis.set(last_session_key, str(session_id), ex=60 * 60 * 24 * 7)
    except Exception:
        logger.warning("Failed to append dashboard chat history message to Redis", exc_info=True)


async def _get_dashboard_last_session_id(
    *,
    dashboard_id: UUID,
    user_id: UUID,
) -> UUID | None:
    try:
        redis = get_redis()
        raw = await redis.get(
            _dashboard_chat_last_session_key(
                dashboard_id=dashboard_id,
                user_id=user_id,
            )
        )
        if not raw:
            return None
        return UUID(str(raw))
    except Exception:
        logger.warning("Failed to read dashboard last session id from Redis", exc_info=True)
        return None


def _to_message_role(raw_role: str):
    from ..models.chat_message import MessageRole
    role = str(raw_role or "").strip().lower()
    if role == "user":
        return MessageRole.USER
    if role == "assistant":
        return MessageRole.ASSISTANT
    return MessageRole.SYSTEM


def _to_dashboard_history_schema_messages(
    *,
    dashboard_id: UUID,
    user_id: UUID,
    session_id: UUID,
    raw_history: list[dict],
) -> list[ChatMessageSchema]:
    messages: list[ChatMessageSchema] = []
    for item in raw_history:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        raw_created_at = item.get("created_at")
        created_at: datetime
        if isinstance(raw_created_at, str) and raw_created_at.strip():
            try:
                created_at = datetime.fromisoformat(raw_created_at.strip())
            except Exception:
                created_at = datetime.utcnow()
        else:
            created_at = datetime.utcnow()
        raw_id = item.get("id")
        try:
            message_id = UUID(str(raw_id)) if raw_id else uuid4()
        except Exception:
            message_id = uuid4()
        messages.append(
            ChatMessageSchema(
                id=message_id,
                board_id=dashboard_id,
                user_id=user_id,
                session_id=session_id,
                role=_to_message_role(str(item.get("role", ""))),
                content=content,
                context=None,
                suggested_actions=None,
                created_at=created_at,
            )
        )
    return messages


def _get_orchestrator_or_503():
    """Get Orchestrator V2 or raise 503."""
    from ..main import get_orchestrator
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized. Check backend logs."
        )
    return orch


@router.post("/{board_id}/ai/chat", response_model=AIChatResponse)
async def chat_with_ai(
    board_id: UUID,
    request: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Отправить сообщение AI Assistant в контексте доски (V2 controller).

    Использует AIAssistantController → Orchestrator V2 pipeline.
    Сохраняет историю чата через AIService.
    """
    from uuid import uuid4
    from ..models.chat_message import ChatMessage, MessageRole

    try:
        ai_service = AIService(db)
        session_id = request.session_id or uuid4()

        # 1. Gather board context
        request_context = request.context or {}
        selected_raw_ids = (
            request_context.get("selected_node_ids")
            or request_context.get("selected_nodes")
            or []
        )
        selected_node_ids = None
        if isinstance(selected_raw_ids, list) and selected_raw_ids:
            selected_node_ids = [UUID(str(nid)) for nid in selected_raw_ids]

        board_context = await ai_service.get_board_context(board_id, selected_node_ids)
        chat_history_raw = await ai_service.get_chat_history(board_id, session_id, limit=10)

        # 2. Save user message to DB
        user_msg = ChatMessage(
            board_id=board_id,
            user_id=current_user.id,
            session_id=session_id,
            role=MessageRole.USER,
            content=request.message,
            context=request.context,
        )
        db.add(user_msg)

        # 3. Call V2 controller
        orchestrator = _get_orchestrator_or_503()
        controller = AIAssistantController(orchestrator)

        result = await controller.process_request(
            user_message=request.message,
            context={
                "board_id": str(board_id),
                "user_id": str(current_user.id),
                "session_id": str(session_id),
                "db": db,
                "board_context": board_context,
                "selected_node_ids": [str(nid) for nid in selected_node_ids] if selected_node_ids else [],
                "selected_nodes_data": board_context.get("selected_nodes_data", []),
                "required_tables": request_context.get("required_tables", []),
                "allow_auto_filter": bool(request_context.get("allow_auto_filter", False)),
                "filter_expression": request_context.get("filter_expression"),
                "chat_history": chat_history_raw,
            },
        )

        # 4. Extract response text
        response_text = result.narrative or result.code_description or "Нет ответа от AI"

        # 5. Build suggested_actions from controller metadata
        suggested_actions_payload = []
        if isinstance(result.suggestions, list):
            suggested_actions_payload.extend(result.suggestions)
        if isinstance(result.metadata, dict) and isinstance(result.metadata.get("suggested_actions"), list):
            suggested_actions_payload.extend(result.metadata["suggested_actions"])
        suggested_actions = None
        if suggested_actions_payload:
            suggested_actions = [SuggestedAction(**action) for action in suggested_actions_payload]

        # 6. Save AI response to DB
        assistant_msg = ChatMessage(
            board_id=board_id,
            user_id=current_user.id,
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=response_text,
            context={"board_context": board_context},
            suggested_actions=[a.dict() for a in suggested_actions] if suggested_actions else None,
        )
        db.add(assistant_msg)
        await db.commit()

        context_used = result.metadata.get("context_used") if isinstance(result.metadata, dict) else None
        if not context_used:
            context_used = {
                "scope": "board",
                "board_id": str(board_id),
                "total_nodes": board_context.get("stats", {}).get("total_source_nodes", 0)
                    + board_context.get("stats", {}).get("total_content_nodes", 0)
                    + board_context.get("stats", {}).get("total_widget_nodes", 0),
                "total_data_tables": board_context.get("stats", {}).get("total_data_tables", 0),
                "selected_data_nodes": len(board_context.get("selected_nodes_data", [])),
            }

        return AIChatResponse(
            response=response_text,
            session_id=session_id,
            suggested_actions=suggested_actions,
            context_used=context_used,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error in chat_with_ai: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in chat_with_ai: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process AI request: {str(e)}"
        )


@dashboard_router.post("/{dashboard_id}/ai/chat", response_model=AIChatResponse)
async def chat_with_ai_dashboard(
    dashboard_id: UUID,
    request: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Отправить сообщение AI Assistant в контексте дашборда.

    В отличие от board-chat, история чата для дашбордов пока не персистится в chat_messages,
    т.к. таблица привязана к board_id (FK). Возвращаем session_id и ответ напрямую.
    """
    from uuid import uuid4

    try:
        ai_service = AIService(db)
        session_id = request.session_id or uuid4()
        request_context = request.context or {}
        client_chat_history = request_context.get("chat_history", [])
        if not isinstance(client_chat_history, list):
            client_chat_history = []

        dashboard_context = await ai_service.get_dashboard_context(
            dashboard_id=dashboard_id,
            user_id=current_user.id,
        )
        if dashboard_context.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=dashboard_context["error"],
            )

        orchestrator = _get_orchestrator_or_503()
        controller = AIAssistantController(orchestrator)
        redis_history = await _get_dashboard_chat_history(
            dashboard_id=dashboard_id,
            user_id=current_user.id,
            session_id=session_id,
            limit=20,
        )
        # Prefer backend-managed Redis history; fallback to client-provided history.
        effective_chat_history = redis_history if redis_history else client_chat_history

        result = await controller.process_request(
            user_message=request.message,
            context={
                "board_id": str(dashboard_id),  # technical run id for orchestrator/traces
                "user_id": str(current_user.id),
                "session_id": str(session_id),
                "db": db,
                "board_context": dashboard_context,
                "selected_node_ids": [],
                "selected_nodes_data": dashboard_context.get("selected_nodes_data", []),
                "required_tables": request_context.get("required_tables", []),
                "allow_auto_filter": bool(request_context.get("allow_auto_filter", False)),
                "filter_expression": request_context.get("filter_expression"),
                "chat_history": effective_chat_history,
            },
        )

        response_text = result.narrative or result.code_description or "Нет ответа от AI"
        suggested_actions_payload = []
        if isinstance(result.suggestions, list):
            suggested_actions_payload.extend(result.suggestions)
        if isinstance(result.metadata, dict) and isinstance(result.metadata.get("suggested_actions"), list):
            suggested_actions_payload.extend(result.metadata["suggested_actions"])
        suggested_actions = None
        if suggested_actions_payload:
            suggested_actions = [SuggestedAction(**action) for action in suggested_actions_payload]

        context_used = result.metadata.get("context_used") if isinstance(result.metadata, dict) else None
        if not context_used:
            context_used = {
                "scope": "dashboard",
                "dashboard_id": str(dashboard_id),
                "total_data_tables": dashboard_context.get("stats", {}).get("total_data_tables", 0),
                "selected_data_nodes": len(dashboard_context.get("selected_nodes_data", [])),
            }
        else:
            context_used["scope"] = "dashboard"
            context_used["dashboard_id"] = str(dashboard_id)

        # Persist dashboard chat history for next turns (best-effort, Redis).
        await _append_dashboard_chat_message(
            dashboard_id=dashboard_id,
            user_id=current_user.id,
            session_id=session_id,
            role="user",
            content=request.message,
        )
        await _append_dashboard_chat_message(
            dashboard_id=dashboard_id,
            user_id=current_user.id,
            session_id=session_id,
            role="assistant",
            content=response_text,
        )

        return AIChatResponse(
            response=response_text,
            session_id=session_id,
            suggested_actions=suggested_actions,
            context_used=context_used,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error in chat_with_ai_dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in chat_with_ai_dashboard: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process AI request: {str(e)}"
        )


@dashboard_router.get("/{dashboard_id}/ai/chat/history/me", response_model=ChatHistoryResponse)
async def get_my_chat_history_dashboard(
    dashboard_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="Максимум сообщений"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить историю последней сессии чата дашборда из Redis."""
    session_id = await _get_dashboard_last_session_id(
        dashboard_id=dashboard_id,
        user_id=current_user.id,
    )
    if not session_id:
        return ChatHistoryResponse(messages=[], session_id=None, total_messages=0)

    raw_history = await _get_dashboard_chat_history(
        dashboard_id=dashboard_id,
        user_id=current_user.id,
        session_id=session_id,
        limit=limit,
    )
    messages = _to_dashboard_history_schema_messages(
        dashboard_id=dashboard_id,
        user_id=current_user.id,
        session_id=session_id,
        raw_history=raw_history,
    )
    return ChatHistoryResponse(
        messages=messages,
        session_id=session_id,
        total_messages=len(messages),
    )


@dashboard_router.get("/{dashboard_id}/ai/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history_dashboard(
    dashboard_id: UUID,
    session_id: UUID = Query(..., description="UUID сессии чата"),
    limit: int = Query(50, ge=1, le=200, description="Максимум сообщений"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить историю конкретной сессии чата дашборда из Redis."""
    raw_history = await _get_dashboard_chat_history(
        dashboard_id=dashboard_id,
        user_id=current_user.id,
        session_id=session_id,
        limit=limit,
    )
    messages = _to_dashboard_history_schema_messages(
        dashboard_id=dashboard_id,
        user_id=current_user.id,
        session_id=session_id,
        raw_history=raw_history,
    )
    return ChatHistoryResponse(
        messages=messages,
        session_id=session_id,
        total_messages=len(messages),
    )


@dashboard_router.delete("/{dashboard_id}/ai/chat/session/{session_id}")
async def delete_chat_session_dashboard(
    dashboard_id: UUID,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Очистка сессии чата дашборда в Redis."""
    deleted = 0
    try:
        redis = get_redis()
        history_key = _dashboard_chat_history_key(
            dashboard_id=dashboard_id,
            user_id=current_user.id,
            session_id=session_id,
        )
        deleted = int(await redis.delete(history_key) or 0)
        last_session_key = _dashboard_chat_last_session_key(
            dashboard_id=dashboard_id,
            user_id=current_user.id,
        )
        raw_last_session = await redis.get(last_session_key)
        if raw_last_session and str(raw_last_session) == str(session_id):
            await redis.delete(last_session_key)
    except Exception:
        logger.warning("Failed to delete dashboard chat session from Redis", exc_info=True)
    return {
        "status": "success",
        "deleted_messages": deleted,
        "session_id": str(session_id)
    }


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
