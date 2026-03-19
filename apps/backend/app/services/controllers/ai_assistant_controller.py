"""
AIAssistantController — Satellite Controller для AI Assistant Panel (V2).

Единый контроллер с внутренней маршрутизацией по типу результата:
1. narrative только → текстовый ответ
2. code_blocks + board ops → auto-execute: create/delete/move nodes/edges
3. code_blocks + transformation → предложить открыть TransformDialog
4. code_blocks + widget → создать WidgetNode auto-execute

Заменяет: AIService.chat() + AIService.chat_stream() + inline board context logic

См. docs/MULTI_AGENT_V2_CONCEPT.md → Phase 4.6
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import select

from .base_controller import BaseController, ControllerResult
from ..context_execution_service import ContextExecutionService
from app.models.content_node import ContentNode

logger = logging.getLogger("controller.ai_assistant")


class AIAssistantController(BaseController):
    """
    Контроллер AI Assistant Panel.

    Единая точка входа для свободного диалога с AI в контексте доски.
    Маршрутизирует ответ в зависимости от содержимого AgentPayload:
    - Только narrative → текстовый ответ
    - code_blocks(board_ops) → auto-execute операции на доске
    - code_blocks(widget) → создание WidgetNode
    - code_blocks(transformation) → предложение TransformDialog

    В отличие от TransformationController / WidgetController,
    AIAssistant не привязан к конкретному ContentNode — он работает
    с доской целиком.
    """

    controller_name = "ai_assistant"

    # Board operation types supported by auto-execute
    BOARD_OPS = {
        "create_node", "delete_node", "move_node",
        "create_edge", "delete_edge", "update_node",
    }

    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Обрабатывает сообщение пользователя в контексте доски.

        Args:
            user_message: Текст сообщения ("Какой средний чек?")
            context: {
                "board_id": str,
                "user_id": str,
                "session_id": str | None,
                "board_context": dict,        # from get_board_context()
                "selected_node_ids": list[str],
                "selected_nodes_data": list[dict],  # ContentTable-like data
                "chat_history": list[dict],
            }

        Returns:
            ControllerResult с narrative, board_ops, widget, или suggested_actions.
        """
        ctx = context or {}
        start_time = time.time()

        board_id = ctx.get("board_id", "")
        user_id = ctx.get("user_id")
        session_id = ctx.get("session_id")
        db = ctx.get("db")
        board_context = ctx.get("board_context", {})
        context_scope = str(board_context.get("scope") or "board")
        selected_node_ids = ctx.get("selected_node_ids", [])
        selected_nodes_data = ctx.get("selected_nodes_data", [])
        all_nodes_data = board_context.get("content_nodes_data", [])
        chat_history = ctx.get("chat_history", [])
        logger.info("💬 AIAssistantController: chat_history messages=%d", len(chat_history) if isinstance(chat_history, list) else 0)
        required_tables = ctx.get("required_tables", [])
        filter_expression = ctx.get("filter_expression")
        allow_auto_filter = bool(ctx.get("allow_auto_filter", False))

        if not selected_nodes_data and selected_node_ids and all_nodes_data:
            selected_id_set = {str(node_id) for node_id in selected_node_ids}
            selected_nodes_data = [
                node for node in all_nodes_data
                if str(node.get("id")) in selected_id_set
            ]

        # 0. Deterministic context execution (table selection + optional sample filtering)
        prepared_context_used: Dict[str, Any] = {}
        catalog_nodes_data: List[Dict[str, Any]] = []
        try:
            context_executor = ContextExecutionService()
            is_board_scope = context_scope == "board"
            board_uuid: Optional[UUID] = None
            db_for_context = db
            if board_id and is_board_scope:
                board_uuid = UUID(str(board_id))
            elif context_scope == "dashboard":
                # Dashboard can be backed by one or more source boards.
                # If exactly one source board is available, use it for full-data
                # filtering/recompute (instead of sample-only filtering).
                source_board_ids = board_context.get("source_board_ids", [])
                if isinstance(source_board_ids, list) and len(source_board_ids) == 1:
                    try:
                        board_uuid = UUID(str(source_board_ids[0]))
                    except Exception:
                        board_uuid = None
                elif isinstance(source_board_ids, list) and len(source_board_ids) > 1:
                    logger.info(
                        "Dashboard context has multiple source boards (%s); "
                        "using multi-board full-data filtering",
                        len(source_board_ids),
                    )
                # Fallback: infer source board from content node ids present in dashboard context.
                if board_uuid is None and db is not None:
                    inferred = await self._infer_board_id_from_dashboard_nodes(
                        db=db,
                        nodes_data=board_context.get("content_nodes_data", []) or [],
                    )
                    if inferred is not None:
                        board_uuid = inferred
            prepared = await context_executor.prepare_board_context(
                board_context=board_context,
                db=db_for_context,
                board_id=board_uuid,
                source_board_ids=board_context.get("source_board_ids", []),
                selected_node_ids=[str(nid) for nid in selected_node_ids],
                required_tables=required_tables if isinstance(required_tables, list) else [],
                user_message=user_message,
                filter_expression=filter_expression if isinstance(filter_expression, dict) else None,
                allow_auto_filter=allow_auto_filter,
            )
            selected_nodes_data = prepared.get("prepared_nodes_data", selected_nodes_data)
            catalog_nodes_data = prepared.get("catalog_nodes_data", [])
            prepared_context_used = prepared.get("context_used", {})
        except Exception as prep_error:
            logger.warning("ContextExecutionService failed, fallback to raw board context: %s", prep_error)

        input_data_preview = self._build_input_data_preview(selected_nodes_data)
        catalog_data_preview = self._build_input_data_preview(
            catalog_nodes_data,
            sample_rows_limit=1,
        )

        # 1. Обогатить запрос контекстом доски
        enriched_request = self._build_assistant_request(
            user_message=user_message,
            board_context=board_context,
            selected_nodes_data=selected_nodes_data,
            chat_history=chat_history,
        )

        orchestrator_context = self._build_orchestrator_context(
            board_context=board_context,
            selected_node_ids=selected_node_ids,
            selected_nodes_data=selected_nodes_data,
            all_nodes_data=all_nodes_data,
            chat_history=chat_history,
            original_user_request=user_message,
            input_data_preview=input_data_preview,
            catalog_data_preview=catalog_data_preview,
            db=db,
        )

        # 2. Вызвать Orchestrator
        orch_result = await self._call_orchestrator(
            user_request=enriched_request,
            board_id=board_id,
            user_id=user_id,
            session_id=session_id,
            context=orchestrator_context,
        )

        if orch_result.get("status") == "error":
            return self._error_result(
                message=orch_result.get("error", "Orchestrator error"),
                execution_time_ms=self._elapsed_ms(start_time),
            )

        results: Dict[str, Any] = orch_result.get("results", {})
        returned_session = orch_result.get("session_id", session_id)
        prepared_context_used = self._merge_context_used_from_results(
            prepared_context_used,
            results,
        )

        # 3. Пост-обработка: маршрутизация по содержимому ответа
        routed = self._route_response(
            results=results,
            session_id=returned_session,
            plan=orch_result.get("plan"),
            start_time=start_time,
            context_used=prepared_context_used,
        )
        return routed

    # ══════════════════════════════════════════════════════════════════
    #  Response routing
    # ══════════════════════════════════════════════════════════════════

    def _route_response(
        self,
        results: Dict[str, Any],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
        context_used: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Маршрутизирует ответ Orchestrator по типу содержимого.

        Приоритет:
        1. Board operations (code_blocks с board_ops metadata)
        2. Widget code (code_blocks с purpose="widget")
        3. Transformation suggestion (code_blocks с purpose="transformation")
        4. Narrative only (текстовый ответ)
        """
        all_code_blocks = self._extract_code_blocks(results)
        narrative = self._extract_narrative(results)
        findings = self._extract_findings(results)

        # Board operations
        board_ops = self._extract_board_ops(all_code_blocks)
        if board_ops:
            return self._build_board_ops_result(
                board_ops=board_ops,
                narrative=narrative,
                session_id=session_id,
                plan=plan,
                start_time=start_time,
                context_used=context_used,
            )

        # Widget code
        widget_blocks = [
            cb for cb in all_code_blocks
            if cb.get("purpose") == "widget"
        ]
        if widget_blocks:
            return self._build_widget_result(
                widget_block=widget_blocks[0],
                narrative=narrative,
                session_id=session_id,
                plan=plan,
                start_time=start_time,
                context_used=context_used,
            )

        # Transformation code
        transform_blocks = [
            cb for cb in all_code_blocks
            if cb.get("purpose") == "transformation"
        ]
        if transform_blocks:
            return self._build_transform_suggestion_result(
                transform_block=transform_blocks[0],
                narrative=narrative,
                session_id=session_id,
                plan=plan,
                start_time=start_time,
                context_used=context_used,
            )

        # Narrative only (default)
        return self._build_narrative_result(
            narrative=narrative,
            findings=findings,
            session_id=session_id,
            plan=plan,
            start_time=start_time,
            context_used=context_used,
        )

    # ══════════════════════════════════════════════════════════════════
    #  Result builders
    # ══════════════════════════════════════════════════════════════════

    def _build_narrative_result(
        self,
        narrative: Optional[str],
        findings: List[Dict[str, Any]],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
        context_used: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """Текстовый ответ (дефолтный режим)."""
        text = narrative or "Не удалось сформировать ответ."

        # Добавить suggested_actions из findings
        suggested_actions: List[Dict[str, Any]] = []
        for f in findings:
            meta = f.get("metadata") or {}
            if meta.get("actionable"):
                suggested_actions.append({
                    "action": meta.get("action", "suggest"),
                    "label": f.get("title", ""),
                    "description": f.get("description", ""),
                })

        if context_used and context_used.get("proposed_filters"):
            suggested_actions.append({
                "action": "apply_filter",
                "description": "Применить предложенный фильтр к данным доски",
                "params": {"filter_expression": context_used.get("proposed_filters")},
            })

        return ControllerResult(
            status="success",
            narrative=text,
            narrative_format="markdown",
            suggestions=suggested_actions,
            session_id=session_id,
            plan=plan,
            mode="narrative",
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={"context_used": context_used or {}},
        )

    def _build_board_ops_result(
        self,
        board_ops: List[Dict[str, Any]],
        narrative: Optional[str],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
        context_used: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """Результат с board operations для auto-execute."""
        return ControllerResult(
            status="success",
            narrative=narrative or "Выполняю операции на доске...",
            narrative_format="markdown",
            session_id=session_id,
            plan=plan,
            mode="board_operations",
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={
                "board_operations": board_ops,
                "auto_execute": True,
                "context_used": context_used or {},
            },
        )

    def _build_widget_result(
        self,
        widget_block: Dict[str, Any],
        narrative: Optional[str],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
        context_used: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """Результат с виджетом для auto-создания."""
        meta = widget_block.get("metadata") or {}
        return ControllerResult(
            status="success",
            narrative=narrative,
            widget_code=widget_block.get("code", ""),
            widget_name=widget_block.get("description", "AI Widget"),
            widget_type=meta.get("widget_type", "custom"),
            session_id=session_id,
            plan=plan,
            mode="widget_creation",
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={
                "auto_create_widget": True,
                "context_used": context_used or {},
            },
        )

    def _build_transform_suggestion_result(
        self,
        transform_block: Dict[str, Any],
        narrative: Optional[str],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
        context_used: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """Результат с предложением открыть TransformDialog."""
        return ControllerResult(
            status="success",
            narrative=narrative or "Предлагаю выполнить трансформацию данных.",
            code=transform_block.get("code", ""),
            code_language="python",
            code_description=transform_block.get("description", ""),
            session_id=session_id,
            plan=plan,
            mode="transformation_suggestion",
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={
                "suggest_transform_dialog": True,
                "context_used": context_used or {},
            },
        )

    # ══════════════════════════════════════════════════════════════════
    #  Board operations extraction
    # ══════════════════════════════════════════════════════════════════

    def _extract_board_ops(
        self, code_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Извлекает board operations из code_blocks.

        Board ops хранятся в metadata code_block'ов:
        {
            "purpose": "board_operation",
            "metadata": {
                "operation": "create_node",
                "params": {...}
            }
        }
        """
        ops: List[Dict[str, Any]] = []
        for cb in code_blocks:
            if cb.get("purpose") == "board_operation":
                meta = cb.get("metadata") or {}
                operation = meta.get("operation", "")
                if operation in self.BOARD_OPS:
                    ops.append({
                        "operation": operation,
                        "params": meta.get("params", {}),
                        "description": cb.get("description", ""),
                    })
        return ops

    @staticmethod
    def _merge_context_used_from_results(
        base_context_used: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prefer runtime context_filter metadata over pre-orchestrator context summary."""
        merged = dict(base_context_used or {})
        if not isinstance(results, dict):
            return merged

        cf_result = results.get("context_filter")
        if not isinstance(cf_result, dict):
            return merged

        cf_meta = cf_result.get("metadata") or {}
        if not isinstance(cf_meta, dict):
            return merged

        runtime_context_used = cf_meta.get("context_used")
        if isinstance(runtime_context_used, dict):
            merged.update(runtime_context_used)

        # Fallbacks for compatibility with older/partial payloads
        if merged.get("filters") is None and isinstance(cf_meta.get("llm_filter_expression"), dict):
            merged["filters"] = cf_meta.get("llm_filter_expression")
        if "filter_applied_for_answer" not in merged and merged.get("filters"):
            merged["filter_applied_for_answer"] = True
        return merged

    # ══════════════════════════════════════════════════════════════════
    #  Request building
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_assistant_request(
        user_message: str,
        board_context: Dict[str, Any],
        selected_nodes_data: List[Dict[str, Any]],
        chat_history: List[Dict[str, Any]],
    ) -> str:
        """Обогащает запрос пользователя контекстом доски."""
        request = user_message

        # High-priority conversation memory summary (placed before board/data context).
        memory_facts = AIAssistantController._extract_conversation_memory(chat_history)
        if memory_facts:
            request += "\n\n[ПАМЯТЬ ДИАЛОГА:"
            for fact in memory_facts:
                request += f"\n- {fact}"
            request += "\n]"

        dialog_focus_facts = AIAssistantController._extract_dialog_referential_focus(
            user_message=user_message,
            chat_history=chat_history,
        )
        if dialog_focus_facts:
            request += "\n\n[ФОКУС ДИАЛОГА:"
            for fact in dialog_focus_facts:
                request += f"\n- {fact}"
            request += "\n]"

        # Board summary
        board_info = board_context.get("board", {})
        stats = board_context.get("stats", {})
        if board_info.get("name"):
            request += f"\n\n[Контекст доски \"{board_info['name']}\": "
            request += f"{stats.get('total_content_nodes', 0)} контент-нод, "
            request += f"{stats.get('total_source_nodes', 0)} источников, "
            request += f"{stats.get('total_widget_nodes', 0)} виджетов, "
            request += f"{stats.get('total_edges', 0)} связей]"

        # Content nodes summary (data available on the board)
        # content_nodes хранятся на верхнем уровне board_context (не внутри nodes)
        content_nodes = board_context.get("content_nodes", [])
        if content_nodes:
            request += "\n\nДанные на доске:"
            for cn in content_nodes[:10]:
                name = cn.get("name", "Узел данных")
                summary = cn.get("content_summary", "")
                request += f"\n  • {name}: {summary}"

        table_catalog = board_context.get("table_catalog", [])
        if table_catalog:
            request += "\n\nТабличный каталог доски (схемы):"
            for table_info in table_catalog[:20]:
                node_name = table_info.get("node_name", "node")
                table_name = table_info.get("table_name", "table")
                columns = table_info.get("columns", [])
                if isinstance(columns, list):
                    column_str = ", ".join(
                        c.get("name", "col") if isinstance(c, dict) else str(c)
                        for c in columns[:12]
                    )
                else:
                    column_str = ""
                row_count = table_info.get("row_count", 0)
                request += (
                    f"\n  • {node_name}.{table_name}: "
                    f"{row_count} строк, колонки [{column_str}]"
                )

        # Selected nodes data
        if selected_nodes_data:
            request += "\n\nВыбранные узлы:"
            for node in selected_nodes_data[:5]:
                name = node.get("name", node.get("node_name", "Node"))
                tables = node.get("tables", [])
                text = node.get("text", "")
                request += f"\n  • {name}"
                for t in tables:
                    t_name = t.get("name", "таблица")
                    cols = t.get("columns", [])
                    if isinstance(cols, list):
                        col_str = ", ".join(
                            c.get("name", "col") if isinstance(c, dict) else str(c)
                            for c in cols[:10]
                        )
                    else:
                        col_str = ""
                    row_count = t.get("row_count", 0)
                    request += (
                        f"\n    Таблица '{t_name}': {row_count} строк, [{col_str}]"
                    )
                    sample_rows = t.get("sample_rows", [])
                    if isinstance(sample_rows, list) and sample_rows:
                        compact_rows = sample_rows[:2]
                        request += f"\n      Примеры строк: {json.dumps(compact_rows, ensure_ascii=False)}"
                if text:
                    request += f"\n    Текст: {len(text)} символов"

        # Conversation memory (previous turns in this session)
        if isinstance(chat_history, list) and chat_history:
            request += "\n\nИстория диалога (предыдущие сообщения):"
            for msg in chat_history[-12:]:
                if not isinstance(msg, dict):
                    continue
                role = str(msg.get("role", "")).strip().lower()
                content = str(msg.get("content", "")).strip()
                if not content:
                    continue
                label = "Пользователь" if role == "user" else "Ассистент"
                request += f"\n  {label}: {content[:800]}"

        return request

    @staticmethod
    def _extract_conversation_memory(chat_history: List[Dict[str, Any]]) -> List[str]:
        """Extract compact user-profile facts from previous turns."""
        if not isinstance(chat_history, list) or not chat_history:
            return []

        name_value: Optional[str] = None
        patterns = (
            r"\bменя\s+зовут\s+([A-Za-zА-Яа-яЁё0-9_\-]{2,40})",
            r"\bmy\s+name\s+is\s+([A-Za-z0-9_\-]{2,40})",
            r"\bi\s+am\s+([A-Za-z0-9_\-]{2,40})",
        )

        for msg in chat_history:
            if not isinstance(msg, dict):
                continue
            if str(msg.get("role", "")).lower() != "user":
                continue
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            for pat in patterns:
                m = re.search(pat, content, flags=re.IGNORECASE)
                if m:
                    name_value = m.group(1).strip(".,!?;:()[]{}\"'")

        out: List[str] = []
        if name_value:
            out.append(f"Имя пользователя: {name_value}")
        return out

    @staticmethod
    def _extract_dialog_referential_focus(
        *,
        user_message: str,
        chat_history: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Resolve referential follow-up questions ("она", "у них", etc.) to the latest entity.
        This reduces context-loss when users ask short pronoun-based follow-ups.
        """
        if not AIAssistantController._is_referential_query(user_message):
            return []
        if not isinstance(chat_history, list) or not chat_history:
            return []

        user_entities = AIAssistantController._extract_entities_from_user_history(chat_history)
        assistant_entities = AIAssistantController._extract_entities_from_assistant_history(chat_history)
        if not user_entities or not assistant_entities:
            return []

        assistant_norm = {AIAssistantController._normalize_entity_key(v) for v in assistant_entities}
        primary: Optional[str] = None
        for candidate in user_entities:
            if AIAssistantController._normalize_entity_key(candidate) in assistant_norm:
                primary = candidate
                break
        if not primary:
            return []

        return [
            (
                f"Текущий вопрос содержит местоименную ссылку; "
                f"интерпретируй ее как «{primary}», если пользователь явно не сменил объект."
            )
        ]

    @staticmethod
    def _extract_entities_from_user_history(chat_history: List[Dict[str, Any]]) -> List[str]:
        """
        Extract candidate entities from user turns only.
        """
        candidates: List[str] = []

        for msg in reversed(chat_history):
            if not isinstance(msg, dict):
                continue
            if str(msg.get("role", "")).strip().lower() != "user":
                continue
            content = str(msg.get("content", "")).strip()
            if not content:
                continue

            for candidate in AIAssistantController._extract_entities_from_text(content):
                if candidate not in candidates:
                    candidates.append(candidate)
            if len(candidates) >= 4:
                break
        return candidates

    @staticmethod
    def _extract_entities_from_assistant_history(chat_history: List[Dict[str, Any]]) -> List[str]:
        candidates: List[str] = []
        for msg in reversed(chat_history):
            if not isinstance(msg, dict):
                continue
            if str(msg.get("role", "")).strip().lower() != "assistant":
                continue
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            for candidate in AIAssistantController._extract_entities_from_text(content):
                if candidate not in candidates:
                    candidates.append(candidate)
            if len(candidates) >= 3:
                break
        return candidates

    @staticmethod
    def _normalize_entity_key(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    @staticmethod
    def _is_referential_query(user_message: str) -> bool:
        if not user_message:
            return False
        text = user_message.lower()
        referential_patterns = (
            r"\bона\b",
            r"\bон\b",
            r"\bони\b",
            r"\bу\s+них\b",
            r"\bу\s+него\b",
            r"\bу\s+нее\b",
            r"\bо\s+нем\b",
            r"\bо\s+ней\b",
            r"\bо\s+них\b",
            r"\bего\b",
            r"\bе[её]\b",
            r"\bих\b",
            r"\bэт(от|а|о|и)\b",
            r"\bт(от|а|о|е)\b",
        )
        return any(re.search(pat, text, flags=re.IGNORECASE) for pat in referential_patterns)

    @staticmethod
    def _extract_entities_from_text(text: str) -> List[str]:
        """
        Extract entity candidates from recent chat turns.
        Prioritizes quoted entities and proper-name tokens.
        """
        if not text:
            return []
        candidates: List[str] = []

        def _push(raw: str) -> None:
            cleaned = raw.strip().strip(".,!?;:()[]{}")
            if not cleaned or len(cleaned) < 2:
                return
            # Ignore obvious non-entities.
            lowered = cleaned.lower()
            if lowered in {
                "пользователь", "ассистент", "данные", "контекст", "таблица",
                "giga", "gigaboard", "ai", "ии",
            }:
                return
            if cleaned not in candidates:
                candidates.append(cleaned)

        # 1) Explicit quotes: «Колонизаторы», "Hobby World"
        for m in re.finditer(r"[«\"]([^\"»\n]{2,80})[»\"]", text):
            _push(m.group(1))

        # 2) Latin title-cased sequences (e.g., Hobby World, Philips, Dfc)
        for m in re.finditer(
            r"\b([A-Z][A-Za-z0-9&'’\-.]{1,}(?:\s+[A-Z][A-Za-z0-9&'’\-.]{1,}){0,2})\b",
            text,
        ):
            _push(m.group(1))

        # 3) Cyrillic title-cased sequences (e.g., Колонизаторы)
        for m in re.finditer(
            r"\b([А-ЯЁ][А-Яа-яЁё0-9&'’\-.]{1,}(?:\s+[А-ЯЁ][А-Яа-яЁё0-9&'’\-.]{1,}){0,2})\b",
            text,
        ):
            _push(m.group(1))

        return candidates[:5]

    @staticmethod
    def _build_orchestrator_context(
        board_context: Dict[str, Any],
        selected_node_ids: List[str],
        selected_nodes_data: List[Dict[str, Any]],
        all_nodes_data: List[Dict[str, Any]],
        chat_history: List[Dict[str, Any]],
        original_user_request: str,
        input_data_preview: Optional[Dict[str, Any]] = None,
        catalog_data_preview: Optional[Dict[str, Any]] = None,
        db: Any = None,
    ) -> Dict[str, Any]:
        """Строит context для Orchestrator."""
        ctx: Dict[str, Any] = {
            "controller": "ai_assistant",
            "mode": "assistant",
            "original_user_request": original_user_request,
        }

        if board_context:
            ctx["board_context"] = board_context

        if selected_node_ids:
            ctx["selected_node_ids"] = selected_node_ids

        if selected_nodes_data:
            ctx["content_nodes_data"] = selected_nodes_data
            ctx["selected_content_nodes_data"] = selected_nodes_data
        elif all_nodes_data:
            ctx["content_nodes_data"] = all_nodes_data

        if chat_history:
            ctx["chat_history"] = chat_history

        if input_data_preview:
            ctx["input_data_preview"] = input_data_preview
        if catalog_data_preview:
            ctx["catalog_data_preview"] = catalog_data_preview
        if db is not None:
            ctx["db"] = db

        return ctx

    @staticmethod
    def _build_input_data_preview(
        prepared_nodes_data: List[Dict[str, Any]],
        *,
        sample_rows_limit: int = 8,
    ) -> Dict[str, Dict[str, Any]]:
        """Build compact table preview for Planner/Analyst prompt context."""
        preview: Dict[str, Dict[str, Any]] = {}
        max_tables = 32

        for node in prepared_nodes_data:
            node_name = str(node.get("name") or node.get("id") or "node")
            node_id = str(node.get("id") or node_name)
            tables = node.get("tables", []) or []
            for table in tables:
                if len(preview) >= max_tables:
                    return preview
                table_name = str(table.get("name", "table"))
                table_key = f"{node_id}:{table_name}"
                columns = table.get("columns", []) or []
                sample_rows = table.get("sample_rows", []) or []
                preview[table_key] = {
                    "node_id": node_id,
                    "node_name": node_name,
                    "table_name": table_name,
                    "columns": columns,
                    "row_count": int(table.get("row_count", len(sample_rows))),
                    "sample_rows": sample_rows[:sample_rows_limit],
                }

        return preview

    # ══════════════════════════════════════════════════════════════════
    #  Utility
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.time() - start_time) * 1000)

    @staticmethod
    async def _infer_board_id_from_dashboard_nodes(
        *,
        db: Any,
        nodes_data: List[Dict[str, Any]],
    ) -> Optional[UUID]:
        """
        Infer a single source board_id from real content node ids in dashboard context.
        Ignores synthetic ids like "project_table:...".
        """
        node_uuids: List[UUID] = []
        for node in nodes_data:
            raw_id = str(node.get("id", "")).strip()
            if not raw_id or ":" in raw_id:
                continue
            try:
                node_uuids.append(UUID(raw_id))
            except Exception:
                continue
        if not node_uuids:
            return None

        result = await db.execute(
            select(ContentNode.board_id).where(ContentNode.id.in_(node_uuids))
        )
        board_ids = {row[0] for row in result.all() if row and row[0]}
        if len(board_ids) == 1:
            return next(iter(board_ids))
        return None
