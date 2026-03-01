"""
AI Service - бизнес-логика для AI Assistant Panel.

Отвечает за:
- Извлечение контекста доски (nodes, edges, data)
- Форматирование промптов для GigaChat
- Парсинг ответов и извлечение suggested actions
- Управление историей чата

См. docs/AI_ASSISTANT.md и docs/MULTI_AGENT_SYSTEM.md
"""
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from .gigachat_service import get_gigachat_service
from ..models import Board, BaseNode, ContentNode, WidgetNode, CommentNode, Edge
from ..models.chat_message import ChatMessage, MessageRole

logger = logging.getLogger(__name__)


class AIService:
    """
    Сервис для работы с AI Assistant в контексте доски.
    
    Интегрирован с Multi-Agent Orchestrator (Phase 2):
    - Простые запросы -> прямой GigaChat
    - Сложные запросы -> Multi-Agent обработка через Orchestrator
    """
    
    SYSTEM_PROMPT = """Ты AI-помощник в GigaBoard — платформе для создания аналитических дашбордов.

Твоя роль:
- Помогать пользователям анализировать данные на доске
- Предлагать визуализации и инсайты
- Отвечать на вопросы о данных
- Давать рекомендации по улучшению дашборда

Структура GigaBoard:
- DataNode: источники данных (SQL, CSV, API и т.д.)
- WidgetNode: визуализации данных (графики, таблицы)
- CommentNode: комментарии и аннотации
- Edge: связи между нодами (трансформации, визуализации)

Формат ответов:
- Будь кратким и конкретным
- Предлагай практические действия
- Ссылайся на конкретные ноды по их названию
- Если можешь предложить действие (создать виджет, трансформировать данные), делай это

Не:
- Не придумывай данные, которых нет на доске
- Не предлагай действия, которые невозможно выполнить
- Не используй технический жаргон без объяснений
"""
    
    def __init__(self, db: AsyncSession):
        """
        Args:
            db: SQLAlchemy async session
        """
        self.db = db
        self.gigachat = get_gigachat_service()
    
    async def get_board_context(
        self,
        board_id: UUID,
        selected_node_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """
        Извлечь контекст доски для AI.
        
        Args:
            board_id: UUID доски
            selected_node_ids: Список UUID выбранных нод (если есть)
            
        Returns:
            Словарь с контекстом доски
        """
        # Получить доску
        board_query = select(Board).where(Board.id == board_id)
        board_result = await self.db.execute(board_query)
        board = board_result.scalar_one_or_none()
        
        if not board:
            return {"error": "Board not found"}
        
        # Получить все ноды доски
        nodes_query = select(BaseNode).where(BaseNode.board_id == board_id)
        nodes_result = await self.db.execute(nodes_query)
        all_nodes = nodes_result.scalars().all()
        
        # Разделить по типам
        content_nodes = [n for n in all_nodes if isinstance(n, ContentNode)]
        source_nodes = []  # TODO: добавить SourceNode когда потребуется
        widget_nodes = [n for n in all_nodes if isinstance(n, WidgetNode)]
        comment_nodes = [n for n in all_nodes if isinstance(n, CommentNode)]
        
        # Получить edges
        edges_query = select(Edge).where(Edge.board_id == board_id)
        edges_result = await self.db.execute(edges_query)
        edges = edges_result.scalars().all()
        
        # Формируем контекст
        context = {
            "board": {
                "id": str(board.id),
                "name": board.name,
                "description": board.description,
            },
            "nodes": {
                "source_nodes": [
                    {
                        "id": str(n.id),
                        "name": n.name if hasattr(n, 'name') else f"SourceNode-{n.id}",
                        "source_type": getattr(n, 'source_type', None),
                        "config": getattr(n, 'config', None),
                    }
                    for n in source_nodes
                ],
                "widget_nodes": [
                    {
                        "id": str(n.id),
                        "name": n.name if hasattr(n, 'name') else f"Widget-{n.id}",
                        "description": n.description if hasattr(n, 'description') else None,
                    }
                    for n in widget_nodes
                ],
                "comment_nodes": [
                    {
                        "id": str(n.id),
                        "content": n.content if hasattr(n, 'content') else "",
                    }
                    for n in comment_nodes
                ],
            },
            "edges": [
                {
                    "from": str(e.source_node_id),
                    "to": str(e.target_node_id),
                    "type": e.edge_type.value if hasattr(e.edge_type, 'value') else str(e.edge_type),
                }
                for e in edges
            ],
            "content_nodes": [
                {
                    "id": str(n.id),
                    "name": n.name if hasattr(n, 'name') else f"ContentNode-{n.id}",
                    "content_summary": self._summarize_content(n),
                }
                for n in content_nodes
            ],
            "stats": {
                "total_source_nodes": len(source_nodes),
                "total_content_nodes": len(content_nodes),
                "total_widget_nodes": len(widget_nodes),
                "total_comment_nodes": len(comment_nodes),
                "total_edges": len(edges),
            }
        }
        
        # Если указаны выбранные ноды, добавляем их в контекст
        if selected_node_ids:
            selected_nodes = [n for n in all_nodes if n.id in selected_node_ids]
            context["selected_nodes"] = [
                {
                    "id": str(n.id),
                    "name": n.name if hasattr(n, 'name') else f"Node-{n.id}",
                    "type": n.node_type if hasattr(n, 'node_type') else "unknown",
                }
                for n in selected_nodes
            ]
        
        return context

    @staticmethod
    def _summarize_content(node) -> str:
        """Краткое описание содержимого ContentNode для контекста AI."""
        try:
            content = getattr(node, "content", None)
            if not content or not isinstance(content, dict):
                return "empty"
            tables = content.get("tables", [])
            text = content.get("text", "")
            parts = []
            if text:
                parts.append(f"text: {text[:100]}")
            for t in tables:
                tname = t.get("name", "таблица")
                cols = t.get("columns", [])
                col_names = [c["name"] for c in cols]
                row_count = t.get("row_count", len(t.get("rows", [])))
                parts.append(f"table '{tname}': {row_count} rows, columns [{', '.join(col_names)}]")
            return "; ".join(parts) if parts else "empty"
        except Exception:
            return "unknown"

    async def chat(
        self,
        board_id: UUID,
        user_id: UUID,
        message: str,
        session_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Обработать сообщение пользователя и получить ответ от AI.
        
        Args:
            board_id: UUID доски
            user_id: UUID пользователя
            message: Текст сообщения от пользователя
            session_id: UUID сессии чата (создается, если не указан)
            context: Дополнительный контекст (выбранные ноды и т.д.)
            
        Returns:
            Словарь с ответом AI и метаданными
        """
        # Создать или использовать существующий session_id
        if not session_id:
            session_id = uuid4()
        
        # Получить контекст доски
        selected_node_ids = None
        if context and "selected_nodes" in context:
            selected_node_ids = [UUID(nid) for nid in context["selected_nodes"]]
        
        board_context = await self.get_board_context(board_id, selected_node_ids)
        
        # Получить историю чата для этой сессии
        history = await self.get_chat_history(board_id, session_id, limit=10)
        
        # Формируем контекст доски
        context_message = f"""
Текущий контекст доски "{board_context['board']['name']}":
- Источников данных (SourceNode): {board_context['stats']['total_source_nodes']}
- Визуализаций (WidgetNode): {board_context['stats']['total_widget_nodes']}
- Комментариев: {board_context['stats']['total_comment_nodes']}
- Связей между нодами: {board_context['stats']['total_edges']}

Доступные источники данных:
{self._format_source_nodes(board_context['nodes']['source_nodes'])}

Доступные визуализации:
{self._format_widget_nodes(board_context['nodes']['widget_nodes'])}
"""
        
        # Формируем сообщения для GigaChat
        # GigaChat требует, чтобы system message был первым и единственным
        full_system_prompt = self.SYSTEM_PROMPT + context_message
        messages = [
            {"role": "system", "content": full_system_prompt}
        ]
        
        # Добавляем историю чата
        for hist_msg in history:
            messages.append({
                "role": hist_msg["role"],
                "content": hist_msg["content"]
            })
        
        # Добавляем новое сообщение пользователя
        messages.append({"role": "user", "content": message})
        
        # Сохраняем сообщение пользователя в БД
        user_message = ChatMessage(
            board_id=board_id,
            user_id=user_id,
            session_id=session_id,
            role=MessageRole.USER,
            content=message,
            context=context,
        )
        self.db.add(user_message)
        
        try:
            # Получаем ответ от GigaChat
            logger.info(f"Sending chat request to GigaChat for board {board_id}")
            ai_response = await self.gigachat.chat_completion(messages, temperature=0.7)
            
            # TODO: Парсинг suggested_actions из ответа (в будущем)
            suggested_actions = None
            
            # Сохраняем ответ AI в БД
            assistant_message = ChatMessage(
                board_id=board_id,
                user_id=user_id,
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=ai_response,
                context={"board_context": board_context},
                suggested_actions=suggested_actions,
            )
            self.db.add(assistant_message)
            
            await self.db.commit()
            
            logger.info(f"Chat response saved for session {session_id}")
            
            return {
                "response": ai_response,
                "session_id": str(session_id),
                "suggested_actions": suggested_actions,
                "context_used": {
                    "board_id": str(board_id),
                    "total_nodes": board_context['stats']['total_source_nodes'] + 
                                  board_context['stats']['total_widget_nodes'],
                }
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error in chat: {e}")
            raise
    
    async def chat_stream(
        self,
        board_id: UUID,
        user_message: str,
        session_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
        selected_node_ids: Optional[List[UUID]] = None
    ) -> AsyncIterator[str]:
        """
        Streaming версия chat() - возвращает chunks ответа.
        Uses direct GigaChat (V2 controller integration is non-streaming).
        """
        if not session_id:
            session_id = uuid4()
        else:
            session_id = UUID(session_id) if isinstance(session_id, str) else session_id
        
        logger.info(f"[chat_stream] Starting, session_id={session_id}, board_id={board_id}")
        
        # Get board context
        board_context = await self.get_board_context(board_id, selected_node_ids)
        
        # Получить историю чата
        logger.info(f"🤖 [chat_stream] Getting chat history...")
        history = await self.get_chat_history(board_id, session_id, limit=1000)  # Все сообщения в диалоге
        logger.info(f"🤖 [chat_stream] History received: {len(history)} messages")
        
        # Формируем контекст доски
        context_message = f"""
Текущий контекст доски "{board_context['board']['name']}":
- Источников данных (SourceNode): {board_context['stats']['total_source_nodes']}
- Визуализаций (WidgetNode): {board_context['stats']['total_widget_nodes']}
- Комментариев: {board_context['stats']['total_comment_nodes']}
- Связей между нодами: {board_context['stats']['total_edges']}

Доступные источники данных:
{self._format_source_nodes(board_context['nodes']['source_nodes'])}

Доступные визуализации:
{self._format_widget_nodes(board_context['nodes']['widget_nodes'])}
"""
        
        # Формируем сообщения для GigaChat
        full_system_prompt = self.SYSTEM_PROMPT + context_message
        messages = [
            {"role": "system", "content": full_system_prompt}
        ]
        
        # Добавляем историю
        for hist_msg in history:
            messages.append({
                "role": hist_msg["role"],
                "content": hist_msg["content"]
            })
        
        # Добавляем новое сообщение
        messages.append({"role": "user", "content": user_message})
        
        # Сохраняем сообщение пользователя
        logger.info(f"🤖 [chat_stream] Saving user message to DB...")
        user_msg = ChatMessage(
            board_id=board_id,
            user_id=user_id,
            session_id=session_id,
            role=MessageRole.USER,
            content=user_message,
            context={"selected_nodes": [str(nid) for nid in selected_node_ids]} if selected_node_ids else None,
        )
        self.db.add(user_msg)
        await self.db.commit()  # Коммитим сообщение пользователя сразу
        logger.info(f"🤖 [chat_stream] User message saved and committed")
        
        try:
            # Streaming от GigaChat
            logger.info(f"🤖 [chat_stream] Calling GigaChat API with {len(messages)} messages...")
            logger.info(f"🤖 [chat_stream] GigaChat instance: {self.gigachat}")
            full_response = ""
            
            logger.info(f"🤖 [chat_stream] Starting async iteration over chat_completion_stream...")
            async for chunk in self.gigachat.chat_completion_stream(messages, temperature=0.7):
                logger.info(f"🤖 [chat_stream] Got chunk: {chunk[:50] if len(chunk) > 50 else chunk}")
                full_response += chunk
                yield chunk
            
            logger.info(f"🤖 [chat_stream] Streaming completed, total response length: {len(full_response)}")
            
            # Сохраняем полный ответ AI
            logger.info(f"🤖 [chat_stream] Saving AI response to DB...")
            assistant_msg = ChatMessage(
                board_id=board_id,
                user_id=user_id,
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=full_response,
                context={"board_context": board_context},
                suggested_actions=None,  # TODO: парсинг suggested_actions
            )
            self.db.add(assistant_msg)
            await self.db.commit()
            logger.info(f"🤖 [chat_stream] AI response saved and committed")
            
            logger.info(f"Streaming chat completed for session {session_id}")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error in streaming chat: {e}", exc_info=True)
            raise
    
    async def get_chat_history(
        self,
        board_id: UUID,
        session_id: UUID,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получить историю чата для сессии.
        
        Args:
            board_id: UUID доски
            session_id: UUID сессии
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений
        """
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
        
        result = await self.db.execute(query)
        messages = result.scalars().all()
        
        return [
            {
                "id": str(msg.id),
                "role": msg.role.value,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ]
    
    async def delete_chat_session(
        self,
        board_id: UUID,
        session_id: UUID
    ) -> int:
        """
        Удалить все сообщения сессии чата.
        
        Args:
            board_id: UUID доски
            session_id: UUID сессии
            
        Returns:
            Количество удаленных сообщений
        """
        query = select(ChatMessage).where(
            and_(
                ChatMessage.board_id == board_id,
                ChatMessage.session_id == session_id
            )
        )
        
        result = await self.db.execute(query)
        messages = result.scalars().all()
        
        count = len(messages)
        for msg in messages:
            await self.db.delete(msg)
        
        await self.db.commit()
        logger.info(f"Deleted {count} messages from session {session_id}")
        
        return count
    
    def _format_source_nodes(self, source_nodes: List[Dict]) -> str:
        """Форматирование списка SourceNode для контекста"""
        if not source_nodes:
            return "Нет источников данных"
        
        lines = []
        for node in source_nodes:
            source_type = node.get('source_type', 'unknown')
            label = node.get('label', 'Без названия')
            lines.append(f"- {label} (тип: {source_type})")
        
        return "\n".join(lines)
    
    def _format_widget_nodes(self, widget_nodes: List[Dict]) -> str:
        """Форматирование списка WidgetNode для контекста"""
        if not widget_nodes:
            return "Нет визуализаций"
        
        lines = []
        for node in widget_nodes:
            widget_type = node.get('widget_type', 'unknown')
            label = node.get('label', 'Без названия')
            lines.append(f"- {label} (тип: {widget_type})")
        
        return "\n".join(lines)
