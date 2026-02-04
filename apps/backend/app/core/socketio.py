"""
Socket.IO server instance and event handlers for real-time collaboration.
Combines socketio_instance.py + socketio_events.py into single module.
"""
import logging
from typing import Any, Dict
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
    async def connect(sid, environ):
        """Handle client connection"""
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
        try:
            from ..services.ai_service import AIService
            from ..core.database import get_db
            from uuid import UUID
            
            board_id = data.get("board_id")
            session_id = data.get("session_id")
            message = data.get("message")
            selected_node_ids = data.get("selected_node_ids", [])
            
            if not board_id or not message:
                await sio_instance.emit("ai:stream:error", {
                    "error": "board_id and message are required"
                }, to=sid)
                return
            
            # Уведомление о начале streaming
            await sio_instance.emit("ai:stream:start", {
                "session_id": session_id,
                "board_id": board_id
            }, to=sid)
            
            logger.info(f"🤖 Starting AI stream for board {board_id}, message: {message[:50]}...")
            
            # Получить DB session
            async for db in get_db():
                try:
                    logger.info(f"🤖 Got DB session, creating AIService...")
                    ai_service = AIService(db)
                    
                    # Получить user_id из доски
                    from ..models.board import Board
                    from sqlalchemy import select
                    board_query = select(Board).where(Board.id == UUID(board_id))
                    board_result = await db.execute(board_query)
                    board = board_result.scalar_one_or_none()
                    
                    if not board:
                        await sio_instance.emit("ai:stream:error", {
                            "error": "Board not found"
                        }, to=sid)
                        break
                    
                    user_id = board.user_id
                    logger.info(f"🤖 Board user_id: {user_id}")
                    
                    logger.info(f"🤖 Starting chat_stream...")
                    # Streaming ответ
                    full_response = ""
                    async for chunk in ai_service.chat_stream(
                        board_id=UUID(board_id),
                        user_message=message,
                        session_id=session_id,
                        user_id=user_id,
                        selected_node_ids=[UUID(nid) for nid in selected_node_ids] if selected_node_ids else None
                    ):
                        full_response += chunk
                        logger.debug(f"🤖 Chunk received: {len(chunk)} chars")
                        await sio_instance.emit("ai:stream:chunk", {
                            "session_id": session_id,
                            "chunk": chunk
                        }, to=sid)
                    
                    # Уведомление о завершении
                    await sio_instance.emit("ai:stream:end", {
                        "session_id": session_id,
                        "full_response": full_response
                    }, to=sid)
                    
                    logger.info(f"🤖 AI stream completed for session {session_id}")
                    
                except Exception as inner_e:
                    logger.error(f"❌ Error in AI streaming loop: {inner_e}", exc_info=True)
                    raise
                finally:
                    # DB session будет автоматически закрыта при выходе из async for get_db()
                    break
                    
        except Exception as e:
            logger.error(f"❌ AI stream error: {e}", exc_info=True)
            await sio_instance.emit("ai:stream:error", {
                "error": str(e),
                "session_id": session_id
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
