"""
Socket.IO server instance and event handlers for real-time collaboration.
Combines socketio_instance.py + socketio_events.py into single module.
"""
import logging
from typing import Any, Dict, Optional
import socketio

logger = logging.getLogger(__name__)

# Socket.IO server instance
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)


def register_socketio_events(sio_instance: socketio.AsyncServer):
    """Register all Socket.IO event handlers"""

    @sio_instance.event
    async def connect(sid, environ, auth: Optional[Any] = None):
        """Handle client connection.

        python-socketio передаёт третий аргумент `auth` (данные из клиента `io({ auth: {...} })`).
        """
        logger.info(f"🔗 Socket.IO client connected: {sid}")
        await sio_instance.emit("connected", {"sid": sid}, to=sid)

    @sio_instance.event
    async def disconnect(sid):
        """Handle client disconnection"""
        session = await sio_instance.get_session(sid)
        board_id = session.get("board_id") if session else None
        if board_id:
            logger.info(f"🔌 Client {sid} disconnected from board {board_id}")
        else:
            logger.info(f"🔌 Client {sid} disconnected")

    @sio_instance.event
    async def join_board(sid, data: Dict[str, Any]):
        """Join a board room for real-time updates"""
        board_id = data.get("board_id")
        if not board_id:
            await sio_instance.emit("error", {"message": "board_id is required"}, to=sid)
            return

        room = f"board:{board_id}"
        await sio_instance.enter_room(sid, room)
        await sio_instance.save_session(sid, {"board_id": board_id})
        
        # Debug: list all clients in room
        room_sids = list(sio_instance.manager.get_participants(namespace='/', room=room))
        logger.info(f"📌 Client {sid} joined board {board_id}, room now has {len(room_sids)} clients: {room_sids}")
        
        await sio_instance.emit("joined_board", {"board_id": board_id}, to=sid)

    @sio_instance.event
    async def leave_board(sid, data: Dict[str, Any]):
        """Leave a board room"""
        board_id = data.get("board_id")
        if not board_id:
            return

        room = f"board:{board_id}"
        await sio_instance.leave_room(sid, room)
        await sio_instance.save_session(sid, {})
        
        await sio_instance.emit("left_board", {"board_id": board_id}, to=sid)
        logger.info(f"📌 Client {sid} left board {board_id}")

    # ============================================
    # DataNode Events
    # ============================================

    @sio_instance.event
    async def data_node_created(sid, data: Dict[str, Any]):
        """Broadcast DataNode creation to all clients in the board"""
        board_id = data.get("board_id")
        node_data = data.get("node")
        
        if board_id and node_data:
            room = f"board:{board_id}"
            await sio_instance.emit("data_node_created", node_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast data_node_created to board {board_id}")

    @sio_instance.event
    async def data_node_updated(sid, data: Dict[str, Any]):
        """Broadcast DataNode update to all clients in the board"""
        board_id = data.get("board_id")
        node_data = data.get("node")
        
        if board_id and node_data:
            room = f"board:{board_id}"
            await sio_instance.emit("data_node_updated", node_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast data_node_updated to board {board_id}")

    @sio_instance.event
    async def data_node_deleted(sid, data: Dict[str, Any]):
        """Broadcast DataNode deletion to all clients in the board"""
        board_id = data.get("board_id")
        node_id = data.get("node_id")
        
        if board_id and node_id:
            room = f"board:{board_id}"
            await sio_instance.emit("data_node_deleted", {"id": node_id}, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast data_node_deleted to board {board_id}")

    # ============================================
    # WidgetNode Events
    # ============================================

    @sio_instance.event
    async def widget_node_created(sid, data: Dict[str, Any]):
        """Broadcast WidgetNode creation to all clients in the board"""
        board_id = data.get("board_id")
        node_data = data.get("node")
        
        if board_id and node_data:
            room = f"board:{board_id}"
            await sio_instance.emit("widget_node_created", node_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast widget_node_created to board {board_id}")

    @sio_instance.event
    async def widget_node_updated(sid, data: Dict[str, Any]):
        """Broadcast WidgetNode update to all clients in the board"""
        board_id = data.get("board_id")
        node_data = data.get("node")
        
        if board_id and node_data:
            room = f"board:{board_id}"
            await sio_instance.emit("widget_node_updated", node_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast widget_node_updated to board {board_id}")

    @sio_instance.event
    async def widget_node_deleted(sid, data: Dict[str, Any]):
        """Broadcast WidgetNode deletion to all clients in the board"""
        board_id = data.get("board_id")
        node_id = data.get("node_id")
        
        if board_id and node_id:
            room = f"board:{board_id}"
            await sio_instance.emit("widget_node_deleted", {"id": node_id}, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast widget_node_deleted to board {board_id}")

    # ============================================
    # CommentNode Events
    # ============================================

    @sio_instance.event
    async def comment_node_created(sid, data: Dict[str, Any]):
        """Broadcast CommentNode creation to all clients in the board"""
        board_id = data.get("board_id")
        node_data = data.get("node")
        
        if board_id and node_data:
            room = f"board:{board_id}"
            await sio_instance.emit("comment_node_created", node_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast comment_node_created to board {board_id}")

    @sio_instance.event
    async def comment_node_updated(sid, data: Dict[str, Any]):
        """Broadcast CommentNode update to all clients in the board"""
        board_id = data.get("board_id")
        node_data = data.get("node")
        
        if board_id and node_data:
            room = f"board:{board_id}"
            await sio_instance.emit("comment_node_updated", node_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast comment_node_updated to board {board_id}")

    @sio_instance.event
    async def comment_node_deleted(sid, data: Dict[str, Any]):
        """Broadcast CommentNode deletion to all clients in the board"""
        board_id = data.get("board_id")
        node_id = data.get("node_id")
        
        if board_id and node_id:
            room = f"board:{board_id}"
            await sio_instance.emit("comment_node_deleted", {"id": node_id}, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast comment_node_deleted to board {board_id}")

    # ============================================
    # Edge Events
    # ============================================

    @sio_instance.event
    async def edge_created(sid, data: Dict[str, Any]):
        """Broadcast Edge creation to all clients in the board"""
        board_id = data.get("board_id")
        edge_data = data.get("edge")
        
        if board_id and edge_data:
            room = f"board:{board_id}"
            await sio_instance.emit("edge_created", edge_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast edge_created to board {board_id}")

    @sio_instance.event
    async def edge_updated(sid, data: Dict[str, Any]):
        """Broadcast Edge update to all clients in the board"""
        board_id = data.get("board_id")
        edge_data = data.get("edge")
        
        if board_id and edge_data:
            room = f"board:{board_id}"
            await sio_instance.emit("edge_updated", edge_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast edge_updated to board {board_id}")

    @sio_instance.event
    async def edge_deleted(sid, data: Dict[str, Any]):
        """Broadcast Edge deletion to all clients in the board"""
        board_id = data.get("board_id")
        edge_id = data.get("edge_id")
        
        if board_id and edge_id:
            room = f"board:{board_id}"
            await sio_instance.emit("edge_deleted", {"id": edge_id}, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast edge_deleted to board {board_id}")

    # ============================================
    # Board Events
    # ============================================

    @sio_instance.event
    async def board_updated(sid, data: Dict[str, Any]):
        """Broadcast board update to all clients"""
        board_id = data.get("board_id")
        board_data = data.get("board")
        
        if board_id and board_data:
            room = f"board:{board_id}"
            await sio_instance.emit("board_updated", board_data, room=room, skip_sid=sid)
            logger.debug(f"📡 Broadcast board_updated to board {board_id}")

    # ============================================
    # AI Assistant Events
    # ============================================

    @sio_instance.event
    async def ai_chat_stream(sid, data: Dict[str, Any]):
        """
        Streaming AI chat responses.
        
        Client sends:
        {
            "board_id": "...",
            "session_id": "...",
            "message": "...",
            "selected_node_ids": [...]  # optional
        }
        
        Server emits back to client:
        - ai:stream:start - начало streaming
        - ai:stream:chunk - кусочки ответа
        - ai:stream:end - конец streaming
        - ai:stream:error - ошибка
        """
        session_id = data.get("session_id")
        try:
            import asyncio
            from uuid import UUID, uuid4
            from sqlalchemy import select

            from ..core.database import get_db
            from ..models.board import Board
            from ..models.chat_message import ChatMessage, MessageRole
            from ..services.ai_service import AIService
            from ..services.controllers import AIAssistantController
            from ..main import get_orchestrator

            board_id = data.get("board_id")
            message = data.get("message")
            selected_node_ids = data.get("selected_node_ids", [])
            required_tables = data.get("required_tables", [])
            allow_auto_filter = bool(data.get("allow_auto_filter", False))
            filter_expression = data.get("filter_expression")

            if not board_id or not message:
                await sio_instance.emit("ai:stream:error", {
                    "error": "board_id and message are required"
                }, to=sid)
                return

            scope = str(data.get("scope") or "board").strip().lower()
            entity_uuid = UUID(str(board_id))
            session_uuid = UUID(str(session_id)) if session_id else uuid4()
            session_id = str(session_uuid)

            # --- Dashboard: как в POST .../dashboards/{id}/ai/chat, но со стримом прогресса (нужен JWT в payload).
            if scope == "dashboard":
                from ..services.auth_service import AuthService
                from ..routes.ai_assistant import (
                    _append_dashboard_chat_message,
                    _get_dashboard_chat_history,
                )

                access_token = data.get("access_token") or data.get("token")
                if not access_token:
                    await sio_instance.emit("ai:stream:error", {
                        "error": "access_token is required for dashboard streaming",
                        "session_id": session_id,
                    }, to=sid)
                    return

                payload = AuthService.verify_token(str(access_token))
                if not payload or not payload.get("sub"):
                    await sio_instance.emit("ai:stream:error", {
                        "error": "Invalid or expired token",
                        "session_id": session_id,
                    }, to=sid)
                    return

                user_id = UUID(str(payload["sub"]))

                await sio_instance.emit("ai:stream:start", {
                    "session_id": session_id,
                    "board_id": str(entity_uuid),
                }, to=sid)

                logger.info(
                    "🤖 Starting AI stream via Multi-Agent for dashboard %s, message: %s",
                    entity_uuid,
                    str(message)[:80],
                )

                async for db in get_db():
                    try:
                        ai_service = AIService(db)
                        dashboard_context = await ai_service.get_dashboard_context(
                            dashboard_id=entity_uuid,
                            user_id=user_id,
                        )
                        if dashboard_context.get("error"):
                            await sio_instance.emit("ai:stream:error", {
                                "error": str(dashboard_context["error"]),
                                "session_id": session_id,
                            }, to=sid)
                            break

                        redis_history = await _get_dashboard_chat_history(
                            dashboard_id=entity_uuid,
                            user_id=user_id,
                            session_id=session_uuid,
                            limit=20,
                        )
                        effective_chat_history = redis_history

                        orchestrator = get_orchestrator()
                        if not orchestrator:
                            await sio_instance.emit("ai:stream:error", {
                                "error": "Orchestrator not initialized. Check backend logs.",
                                "session_id": session_id,
                            }, to=sid)
                            break

                        controller = AIAssistantController(orchestrator)

                        async def emit_progress_dash(progress_payload: Dict[str, Any]) -> None:
                            await sio_instance.emit("ai:stream:progress", {
                                "session_id": session_id,
                                **(progress_payload or {}),
                            }, to=sid)

                        result = await controller.process_request(
                            user_message=str(message),
                            context={
                                "board_id": str(entity_uuid),
                                "user_id": str(user_id),
                                "session_id": session_id,
                                "db": db,
                                "board_context": dashboard_context,
                                "selected_node_ids": [],
                                "selected_nodes_data": dashboard_context.get("selected_nodes_data", []),
                                "required_tables": required_tables if isinstance(required_tables, list) else [],
                                "allow_auto_filter": allow_auto_filter,
                                "filter_expression": filter_expression if isinstance(filter_expression, dict) else None,
                                "chat_history": effective_chat_history,
                                "_progress_callback": emit_progress_dash,
                                "_enable_plan_progress": True,
                            },
                        )

                        response_text = (
                            result.narrative
                            or result.code_description
                            or "Нет ответа от AI"
                        )

                        suggested_actions: list = []
                        if isinstance(result.suggestions, list):
                            suggested_actions.extend(result.suggestions)
                        meta_actions = result.metadata.get("suggested_actions") if isinstance(result.metadata, dict) else None
                        if isinstance(meta_actions, list):
                            suggested_actions.extend(meta_actions)

                        await _append_dashboard_chat_message(
                            dashboard_id=entity_uuid,
                            user_id=user_id,
                            session_id=session_uuid,
                            role="user",
                            content=str(message),
                        )
                        await _append_dashboard_chat_message(
                            dashboard_id=entity_uuid,
                            user_id=user_id,
                            session_id=session_uuid,
                            role="assistant",
                            content=response_text,
                        )

                        chunk_size = 120
                        for i in range(0, len(response_text), chunk_size):
                            chunk = response_text[i:i + chunk_size]
                            await sio_instance.emit("ai:stream:chunk", {
                                "session_id": session_id,
                                "chunk": chunk,
                            }, to=sid)
                            await asyncio.sleep(0)

                        await sio_instance.emit("ai:stream:end", {
                            "session_id": session_id,
                            "full_response": response_text,
                            "suggested_actions": suggested_actions or None,
                        }, to=sid)

                        logger.info("🤖 AI stream completed (dashboard) for session %s", session_id)

                    except Exception as inner_e:
                        await db.rollback()
                        logger.error(
                            "❌ Error in AI streaming loop (dashboard): %s",
                            inner_e,
                            exc_info=True,
                        )
                        raise
                    finally:
                        break
                return

            board_uuid = entity_uuid

            # Уведомление о начале streaming с уже нормализованным session_id.
            await sio_instance.emit("ai:stream:start", {
                "session_id": session_id,
                "board_id": str(board_uuid),
            }, to=sid)

            logger.info(
                "🤖 Starting AI stream via Multi-Agent for board %s, message: %s",
                board_uuid,
                str(message)[:80],
            )

            # Получить DB session
            async for db in get_db():
                try:
                    ai_service = AIService(db)

                    # Получить user_id из доски
                    board_query = select(Board).where(Board.id == board_uuid)
                    board_result = await db.execute(board_query)
                    board = board_result.scalar_one_or_none()

                    if not board:
                        await sio_instance.emit("ai:stream:error", {
                            "error": "Board not found",
                            "session_id": session_id,
                        }, to=sid)
                        break

                    user_id = board.user_id

                    # Validate selected node ids from client.
                    selected_node_uuids = []
                    for raw_id in selected_node_ids or []:
                        try:
                            selected_node_uuids.append(UUID(str(raw_id)))
                        except (TypeError, ValueError):
                            logger.warning("Invalid selected_node_id ignored: %s", raw_id)

                    board_context = await ai_service.get_board_context(
                        board_uuid,
                        selected_node_uuids or None,
                    )
                    chat_history_raw = await ai_service.get_chat_history(
                        board_uuid,
                        session_uuid,
                        limit=10,
                    )

                    # Save user message before AI response.
                    user_msg = ChatMessage(
                        board_id=board_uuid,
                        user_id=user_id,
                        session_id=session_uuid,
                        role=MessageRole.USER,
                        content=str(message),
                        context={
                            "selected_nodes": [str(nid) for nid in selected_node_uuids]
                        } if selected_node_uuids else None,
                    )
                    db.add(user_msg)

                    orchestrator = get_orchestrator()
                    if not orchestrator:
                        await sio_instance.emit("ai:stream:error", {
                            "error": "Orchestrator not initialized. Check backend logs.",
                            "session_id": session_id,
                        }, to=sid)
                        break

                    controller = AIAssistantController(orchestrator)
                    async def emit_progress(progress_payload: Dict[str, Any]) -> None:
                        await sio_instance.emit("ai:stream:progress", {
                            "session_id": session_id,
                            **(progress_payload or {}),
                        }, to=sid)

                    result = await controller.process_request(
                        user_message=str(message),
                        context={
                            "board_id": str(board_uuid),
                            "user_id": str(user_id),
                            "session_id": session_id,
                            "db": db,
                            "board_context": board_context,
                            "selected_node_ids": [str(nid) for nid in selected_node_uuids],
                            "selected_nodes_data": board_context.get("selected_nodes_data", []),
                            "required_tables": required_tables if isinstance(required_tables, list) else [],
                            "allow_auto_filter": allow_auto_filter,
                            "filter_expression": filter_expression if isinstance(filter_expression, dict) else None,
                            "chat_history": chat_history_raw,
                            "_progress_callback": emit_progress,
                            "_enable_plan_progress": True,
                        },
                    )

                    response_text = (
                        result.narrative
                        or result.code_description
                        or "Нет ответа от AI"
                    )

                    suggested_actions = []
                    if isinstance(result.suggestions, list):
                        suggested_actions.extend(result.suggestions)
                    meta_actions = result.metadata.get("suggested_actions") if isinstance(result.metadata, dict) else None
                    if isinstance(meta_actions, list):
                        suggested_actions.extend(meta_actions)

                    # Save assistant message to DB.
                    assistant_msg = ChatMessage(
                        board_id=board_uuid,
                        user_id=user_id,
                        session_id=session_uuid,
                        role=MessageRole.ASSISTANT,
                        content=response_text,
                        context={"board_context": board_context},
                        suggested_actions=suggested_actions or None,
                    )
                    db.add(assistant_msg)
                    await db.commit()

                    # Imitate stream by chunking final text from Multi-Agent response.
                    chunk_size = 120
                    for i in range(0, len(response_text), chunk_size):
                        chunk = response_text[i:i + chunk_size]
                        await sio_instance.emit("ai:stream:chunk", {
                            "session_id": session_id,
                            "chunk": chunk,
                        }, to=sid)
                        await asyncio.sleep(0)

                    await sio_instance.emit("ai:stream:end", {
                        "session_id": session_id,
                        "full_response": response_text,
                        "suggested_actions": suggested_actions or None,
                    }, to=sid)

                    logger.info("🤖 AI stream completed via Multi-Agent for session %s", session_id)

                except Exception as inner_e:
                    await db.rollback()
                    logger.error(f"❌ Error in AI streaming loop: {inner_e}", exc_info=True)
                    raise
                finally:
                    # DB session будет автоматически закрыта при выходе из async for get_db()
                    break

        except Exception as e:
            logger.error(f"❌ AI stream error: {e}", exc_info=True)
            await sio_instance.emit("ai:stream:error", {
                "error": str(e),
                "session_id": session_id,
            }, to=sid)


async def broadcast_event(sio_instance: socketio.AsyncServer, board_id: str, event_name: str, data: Any):
    """
    Helper function to broadcast events from route handlers
    
    Args:
        sio_instance: Socket.IO server instance
        board_id: Board ID to broadcast to
        event_name: Name of the event
        data: Event data
    """
    room = f"board:{board_id}"
    await sio_instance.emit(event_name, data, room=room)
    logger.debug(f"📡 Broadcast {event_name} to board {board_id}")
