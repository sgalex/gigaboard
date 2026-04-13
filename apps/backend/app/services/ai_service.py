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
from sqlalchemy.orm import selectinload

from .gigachat_service import get_gigachat_service
from ..models import (
    Board,
    BaseNode,
    ContentNode,
    SourceNode,
    WidgetNode,
    CommentNode,
    Edge,
    Dashboard,
    Project,
    ProjectTable,
    ProjectWidget,
)
from ..models.chat_message import ChatMessage, MessageRole
from .project_access_service import ProjectAccessService

logger = logging.getLogger(__name__)


class AIService:
    """
    Сервис для работы с AI Assistant в контексте доски.
    
    Интегрирован с Multi-Agent Orchestrator (Phase 2):
    - Простые запросы -> прямой GigaChat
    - Сложные запросы -> Multi-Agent обработка через Orchestrator
    """
    
    SYSTEM_PROMPT = """Ты ИИ-ассистент в GigaBoard — платформе для создания аналитических дашбордов.

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
    MAX_CONTEXT_NODES = 30
    MAX_CONTEXT_TABLES_PER_NODE = 4
    MAX_SAMPLE_ROWS_PER_TABLE = 8
    MAX_SAMPLE_COLUMNS_PER_TABLE = 12
    
    def __init__(self, db: AsyncSession):
        """
        Args:
            db: SQLAlchemy async session
        """
        self.db = db
        # AIService используется не только для прямого чата с GigaChat,
        # но и как helper для board context/history в мультиагентном пайплайне.
        # Поэтому не падаем на инициализации, если глобальный singleton не поднят.
        try:
            self.gigachat = get_gigachat_service()
        except RuntimeError:
            self.gigachat = None
            logger.info(
                "GigaChat singleton is not initialized; AIService will use context/history helpers only."
            )
    
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
        source_nodes = [n for n in all_nodes if isinstance(n, SourceNode)]
        content_nodes = [
            n for n in all_nodes
            if isinstance(n, ContentNode) and not isinstance(n, SourceNode)
        ]
        # SourceNode наследует ContentNode — в табличный payload попадают и источники, и ноды аналитики.
        # Приоритет ответа (ContentNode vs первоисточник) задаётся в промпте AIAssistantController.
        data_nodes = [
            n for n in all_nodes
            if isinstance(n, ContentNode)
        ][:self.MAX_CONTEXT_NODES]
        widget_nodes = [n for n in all_nodes if isinstance(n, WidgetNode)]
        comment_nodes = [n for n in all_nodes if isinstance(n, CommentNode)]
        
        # Получить edges
        edges_query = select(Edge).where(Edge.board_id == board_id)
        edges_result = await self.db.execute(edges_query)
        edges = edges_result.scalars().all()
        
        # Подготовка табличного каталога и data payload для LLM-контекста.
        content_nodes_data = [self._build_node_data_payload(n) for n in data_nodes]
        table_catalog: List[Dict[str, Any]] = []
        for node_payload in content_nodes_data:
            for table in node_payload.get("tables", []):
                table_catalog.append({
                    "node_id": node_payload["id"],
                    "node_name": node_payload["name"],
                    "node_type": node_payload["node_type"],
                    "table_name": table.get("name", "table"),
                    "columns": table.get("columns", []),
                    "row_count": table.get("row_count", 0),
                })

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
            "content_nodes_data": content_nodes_data,
            "table_catalog": table_catalog,
            "stats": {
                "total_source_nodes": len(source_nodes),
                "total_content_nodes": len(content_nodes),
                "total_widget_nodes": len(widget_nodes),
                "total_comment_nodes": len(comment_nodes),
                "total_edges": len(edges),
                "total_data_tables": len(table_catalog),
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
            selected_set = {str(n.id) for n in selected_nodes}
            context["selected_nodes_data"] = [
                node_payload
                for node_payload in content_nodes_data
                if node_payload["id"] in selected_set
            ]
        else:
            context["selected_nodes_data"] = []
        
        return context

    async def get_dashboard_context(
        self,
        dashboard_id: UUID,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Build AI context for dashboard mode from dashboard items and project library sources.

        Notes:
        - Tables are taken from ProjectTable items directly.
        - Widget items with `source_content_node_id` contribute ContentNode tables.
        """
        dashboard_query = (
            select(Dashboard)
            .where(Dashboard.id == dashboard_id)
            .options(selectinload(Dashboard.items))
        )
        dashboard_result = await self.db.execute(dashboard_query)
        dashboard = dashboard_result.scalar_one_or_none()
        if not dashboard:
            return {"error": "Dashboard not found"}
        if not await ProjectAccessService.get_project_if_accessible(
            self.db, dashboard.project_id, user_id
        ):
            return {"error": "Dashboard not found"}

        item_list = list(getattr(dashboard, "items", []) or [])
        table_source_ids = {
            item.source_id
            for item in item_list
            if item.item_type == "table" and item.source_id
        }
        widget_source_ids = {
            item.source_id
            for item in item_list
            if item.item_type == "widget" and item.source_id
        }

        project_tables_by_id: Dict[str, ProjectTable] = {}
        if table_source_ids:
            pt_result = await self.db.execute(
                select(ProjectTable).where(ProjectTable.id.in_(table_source_ids))
            )
            project_tables_by_id = {str(t.id): t for t in pt_result.scalars().all()}

        project_widgets_by_id: Dict[str, ProjectWidget] = {}
        if widget_source_ids:
            pw_result = await self.db.execute(
                select(ProjectWidget).where(ProjectWidget.id.in_(widget_source_ids))
            )
            project_widgets_by_id = {str(w.id): w for w in pw_result.scalars().all()}

        content_node_ids: set[UUID] = set()
        for ptable in project_tables_by_id.values():
            if ptable.source_content_node_id:
                content_node_ids.add(ptable.source_content_node_id)
        for widget in project_widgets_by_id.values():
            if widget.source_content_node_id:
                content_node_ids.add(widget.source_content_node_id)

        linked_content_nodes: Dict[str, ContentNode] = {}
        if content_node_ids:
            cn_result = await self.db.execute(
                select(ContentNode).where(ContentNode.id.in_(content_node_ids))
            )
            linked_content_nodes = {str(n.id): n for n in cn_result.scalars().all()}

        content_nodes_data: List[Dict[str, Any]] = []
        source_board_ids: set[str] = set()
        seen_node_ids: set[str] = set()

        # 1) Direct dashboard table items (project library snapshots)
        for item in item_list:
            if item.item_type != "table" or not item.source_id:
                continue
            ptable = project_tables_by_id.get(str(item.source_id))
            if not ptable:
                continue
            synthetic_id = f"project_table:{ptable.id}"
            if synthetic_id in seen_node_ids:
                continue
            seen_node_ids.add(synthetic_id)
            if ptable.source_board_id:
                source_board_ids.add(str(ptable.source_board_id))

            columns = ptable.columns if isinstance(ptable.columns, list) else []
            sample_rows = ptable.sample_data if isinstance(ptable.sample_data, list) else []
            content_nodes_data.append({
                "id": synthetic_id,
                "name": ptable.name or f"ProjectTable-{ptable.id}",
                "node_type": "project_table",
                "text": ptable.description or "",
                "tables": [{
                    "name": ptable.table_name_in_node or ptable.name or "table",
                    "columns": columns[: self.MAX_SAMPLE_COLUMNS_PER_TABLE],
                    "sample_rows": sample_rows[: self.MAX_SAMPLE_ROWS_PER_TABLE],
                    "row_count": int(ptable.row_count or len(sample_rows)),
                }],
            })

        # 2) Widget items mapped to source content nodes
        for widget in project_widgets_by_id.values():
            node_id = str(widget.source_content_node_id) if widget.source_content_node_id else None
            if not node_id:
                continue
            content_node = linked_content_nodes.get(node_id)
            if not content_node:
                continue
            if str(content_node.id) in seen_node_ids:
                continue
            seen_node_ids.add(str(content_node.id))
            if widget.source_board_id:
                source_board_ids.add(str(widget.source_board_id))
            elif getattr(content_node, "board_id", None):
                source_board_ids.add(str(content_node.board_id))

            content_nodes_data.append(self._build_node_data_payload(content_node))

        # 3) If no source board ids from library links, infer from linked content nodes.
        if not source_board_ids and linked_content_nodes:
            for cn in linked_content_nodes.values():
                if getattr(cn, "board_id", None):
                    source_board_ids.add(str(cn.board_id))

        table_catalog: List[Dict[str, Any]] = []
        for node_payload in content_nodes_data:
            for table in node_payload.get("tables", []):
                table_catalog.append({
                    "node_id": node_payload["id"],
                    "node_name": node_payload["name"],
                    "node_type": node_payload.get("node_type", "content"),
                    "table_name": table.get("name", "table"),
                    "columns": table.get("columns", []),
                    "row_count": table.get("row_count", 0),
                })

        return {
            "board": {
                "id": str(dashboard.id),
                "name": dashboard.name,
                "description": dashboard.description,
            },
            "scope": "dashboard",
            "dashboard_id": str(dashboard.id),
            "content_nodes": [
                {
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "content_summary": f"{len(node.get('tables', []))} tables",
                }
                for node in content_nodes_data
            ],
            "content_nodes_data": content_nodes_data,
            "table_catalog": table_catalog,
            "selected_nodes_data": [],
            "source_board_ids": sorted(list(source_board_ids)),
            "stats": {
                "total_source_nodes": 0,
                "total_content_nodes": len(content_nodes_data),
                "total_widget_nodes": len([i for i in item_list if i.item_type == "widget"]),
                "total_comment_nodes": 0,
                "total_edges": 0,
                "total_data_tables": len(table_catalog),
                "total_dashboard_items": len(item_list),
            },
        }

    def _build_node_data_payload(self, node: ContentNode) -> Dict[str, Any]:
        """Build compact data payload for AI context (schema + sample rows)."""
        content = getattr(node, "content", None) or {}
        tables = content.get("tables", []) if isinstance(content, dict) else []

        compact_tables: List[Dict[str, Any]] = []
        for table in tables[: self.MAX_CONTEXT_TABLES_PER_NODE]:
            table_name = table.get("name") or table.get("id") or "table"
            raw_columns = table.get("columns", []) if isinstance(table, dict) else []
            raw_rows = table.get("rows", []) if isinstance(table, dict) else []

            columns: List[Dict[str, Any]] = []
            column_names: List[str] = []
            for col in raw_columns[: self.MAX_SAMPLE_COLUMNS_PER_TABLE]:
                if isinstance(col, dict):
                    col_name = str(col.get("name", "column"))
                    col_type = str(col.get("type", "unknown"))
                else:
                    col_name = str(col)
                    col_type = "unknown"
                columns.append({"name": col_name, "type": col_type})
                column_names.append(col_name)

            sample_rows: List[Dict[str, Any]] = []
            for row in raw_rows[: self.MAX_SAMPLE_ROWS_PER_TABLE]:
                if not isinstance(row, dict):
                    continue
                sample_rows.append({k: row.get(k) for k in column_names if k in row})

            row_count = table.get("row_count")
            if not isinstance(row_count, int):
                row_count = len(raw_rows) if isinstance(raw_rows, list) else 0

            compact_tables.append({
                "name": str(table_name),
                "columns": columns,
                "row_count": row_count,
                "sample_rows": sample_rows,
            })

        node_name = getattr(node, "name", None)
        if not node_name:
            node_name = f"{getattr(node, 'node_type', 'node')}-{node.id}"

        return {
            "id": str(node.id),
            "name": str(node_name),
            "node_type": str(getattr(node, "node_type", "content_node")),
            "text": (content.get("text", "") if isinstance(content, dict) else "")[:500],
            "tables": compact_tables,
        }

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
            if self.gigachat is None:
                raise RuntimeError(
                    "GigaChat service is not configured. "
                    "Use Multi-Agent chat endpoint or configure LLM in admin settings."
                )

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
            if self.gigachat is None:
                raise RuntimeError(
                    "GigaChat service is not configured. "
                    "Streaming via direct GigaChat is unavailable."
                )

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
