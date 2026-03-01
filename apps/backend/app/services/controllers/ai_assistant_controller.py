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

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from .base_controller import BaseController, ControllerResult

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
        board_context = ctx.get("board_context", {})
        selected_node_ids = ctx.get("selected_node_ids", [])
        selected_nodes_data = ctx.get("selected_nodes_data", [])
        chat_history = ctx.get("chat_history", [])

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
            chat_history=chat_history,
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

        # 3. Пост-обработка: маршрутизация по содержимому ответа
        return self._route_response(
            results=results,
            session_id=returned_session,
            plan=orch_result.get("plan"),
            start_time=start_time,
        )

    # ══════════════════════════════════════════════════════════════════
    #  Response routing
    # ══════════════════════════════════════════════════════════════════

    def _route_response(
        self,
        results: Dict[str, Any],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
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
            )

        # Narrative only (default)
        return self._build_narrative_result(
            narrative=narrative,
            findings=findings,
            session_id=session_id,
            plan=plan,
            start_time=start_time,
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

        return ControllerResult(
            status="success",
            narrative=text,
            narrative_format="markdown",
            suggestions=suggested_actions,
            session_id=session_id,
            plan=plan,
            mode="narrative",
            execution_time_ms=self._elapsed_ms(start_time),
        )

    def _build_board_ops_result(
        self,
        board_ops: List[Dict[str, Any]],
        narrative: Optional[str],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
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
            },
        )

    def _build_widget_result(
        self,
        widget_block: Dict[str, Any],
        narrative: Optional[str],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
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
            metadata={"auto_create_widget": True},
        )

    def _build_transform_suggestion_result(
        self,
        transform_block: Dict[str, Any],
        narrative: Optional[str],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
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
            metadata={"suggest_transform_dialog": True},
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
                    col_str = ", ".join(cols[:10]) if isinstance(cols, list) else ""
                    request += f"\n    Таблица '{t_name}': [{col_str}]"
                if text:
                    request += f"\n    Текст: {len(text)} символов"

        return request

    @staticmethod
    def _build_orchestrator_context(
        board_context: Dict[str, Any],
        selected_node_ids: List[str],
        selected_nodes_data: List[Dict[str, Any]],
        chat_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Строит context для Orchestrator."""
        ctx: Dict[str, Any] = {
            "controller": "ai_assistant",
            "mode": "assistant",
        }

        if board_context:
            ctx["board_context"] = board_context

        if selected_node_ids:
            ctx["selected_node_ids"] = selected_node_ids

        if selected_nodes_data:
            ctx["content_nodes_data"] = selected_nodes_data

        if chat_history:
            ctx["chat_history"] = chat_history

        return ctx

    # ══════════════════════════════════════════════════════════════════
    #  Utility
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.time() - start_time) * 1000)
