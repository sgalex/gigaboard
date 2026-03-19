"""
WidgetController — Satellite Controller для генерации виджетов (V2).

Заменяет прямые вызовы ReporterAgent из route-handler'ов:
- create_visualization       → handle_create()   (с сохранением в DB)
- visualize_content_iterative → handle_iterative() (preview без сохранения)
- visualize_content_multiagent → handle_request() (полный pipeline)

Аналогичен TransformationController, но:
- Извлекает code_blocks[purpose="widget"]
- widget_type из metadata["widget_type"]
- Имя из metadata widget_codex (и код только из widget_codex, не из reporter)
- Вместо PythonExecutor → preview HTML

См. docs/MULTI_AGENT_V2_CONCEPT.md → Phase 4.4
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

from .base_controller import BaseController, ControllerResult

logger = logging.getLogger("controller.widget")


class WidgetController(BaseController):
    """
    Контроллер генерации виджетов (HTML визуализаций).

    Вызывается из route-handler'ов ``/visualize*`` endpoints.
    Инкапсулирует логику подготовки контекста, вызова
    Orchestrator V2 и извлечения кода виджета.
    """

    controller_name = "widget"

    # ══════════════════════════════════════════════════════════════════
    #  Public interface
    # ══════════════════════════════════════════════════════════════════

    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Генерирует код виджета (HTML/CSS/JS).

        Не сохраняет в БД — только возвращает код.
        Сохранение WidgetNode + Edge делает route-handler
        (или вызов handle_create).

        Args:
            user_message: Запрос ("Построй гистограмму продаж")
            context: {
                "board_id": str,
                "user_id": str,
                "content_node_id": str,
                "content_data": dict,  # {tables: [], text: ""}
                "content_node_metadata": dict,
                "existing_widget_code": str | None,
                "chat_history": list[dict],
                "is_refinement": bool,
            }

        Returns:
            ControllerResult с widget_code, widget_name, widget_type.
        """
        ctx = context or {}
        start_time = time.time()

        board_id = ctx.get("board_id", "")
        user_id = ctx.get("user_id")
        session_id = ctx.get("session_id")
        content_node_id = ctx.get("content_node_id")
        content_data = ctx.get("content_data", {})
        existing_widget_code = ctx.get("existing_widget_code")
        is_refinement = ctx.get("is_refinement", bool(existing_widget_code))
        chat_history = ctx.get("chat_history", [])

        # 1. Обогатить запрос контекстом данных
        enriched_request = self._build_widget_request(
            user_message=user_message,
            content_data=content_data,
            existing_widget_code=existing_widget_code,
            is_refinement=is_refinement,
        )

        orchestrator_context = self._build_orchestrator_context(
            ctx=ctx,
            content_data=content_data,
            content_node_id=content_node_id,
            existing_widget_code=existing_widget_code,
            chat_history=chat_history,
            is_refinement=is_refinement,
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

        # 3. Извлечь code_blocks только из widget_codex (не из reporter — иначе
        # последний блок может быть копией с искажённым description / именем)
        code_blocks = self._extract_code_blocks_from_widget_codex(
            results, purpose="widget"
        )
        if not code_blocks:
            code_blocks = self._extract_code_blocks_from_widget_codex(
                results, purpose=None
            )
        if not code_blocks:
            code_blocks = self._extract_code_blocks(results, purpose="widget")
        if not code_blocks:
            code_blocks = self._extract_code_blocks(results)

        if not code_blocks:
            # Discussion mode
            return self._build_discussion_result(
                results=results,
                session_id=returned_session,
                plan=orch_result.get("plan"),
                start_time=start_time,
            )

        # 4. Извлечь widget-специфичные поля (последний блок последнего прогона widget_codex)
        best_block = code_blocks[-1]
        widget_code = best_block.get("code", "")
        code_language = best_block.get("language", "html")

        payload_meta = self._extract_widget_codex_metadata(results)
        block_desc = best_block.get("description")
        meta_name = payload_meta.get("widget_name")
        logger.info(
            f"🏷️ WidgetController name sources: "
            f"block.description={block_desc!r}, "
            f"meta.widget_name={meta_name!r}"
        )
        # Имя из metadata виджет-кодекса надёжнее, чем description в CodeBlock (меньше опечаток LLM)
        widget_name = (
            meta_name
            or block_desc
            or "AI Visualization"
        )
        widget_type = payload_meta.get("widget_type", "custom")
        widget_description = payload_meta.get("widget_description", widget_name)
        logger.info(
            f"🏷️ WidgetController FINAL: widget_name={widget_name!r}, "
            f"widget_description={widget_description[:80]!r}"
        )

        if not widget_code.strip():
            return self._error_result(
                message="Агент вернул пустой код виджета",
                execution_time_ms=self._elapsed_ms(start_time),
            )

        return ControllerResult(
            status="success",
            widget_code=widget_code,
            widget_name=widget_name,
            widget_type=widget_type,
            code=widget_code,
            code_language=code_language,
            code_description=widget_description,
            validation=self._extract_validation(results),
            session_id=returned_session,
            plan=orch_result.get("plan"),
            mode="widget",
            execution_time_ms=self._elapsed_ms(start_time),
        )

    # ══════════════════════════════════════════════════════════════════
    #  Metadata extraction
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _widget_codex_result_keys(results: Dict[str, Any]) -> List[str]:
        """Ключи результатов оркестратора для прогонов widget_codex (порядок по номеру)."""
        keys: List[str] = []
        for k in results:
            if k == "widget_codex" or re.match(r"^widget_codex_\d+$", k):
                keys.append(k)

        def order(k: str) -> tuple:
            if k == "widget_codex":
                return (0, 0)
            return (1, int(k.rsplit("_", 1)[-1]))

        return sorted(keys, key=order)

    @classmethod
    def _extract_code_blocks_from_widget_codex(
        cls,
        results: Dict[str, Any],
        purpose: Optional[str],
    ) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        for agent_key in cls._widget_codex_result_keys(results):
            payload = results.get(agent_key)
            if not isinstance(payload, dict):
                continue
            for cb in payload.get("code_blocks", []):
                if not isinstance(cb, dict):
                    continue
                if purpose is None or cb.get("purpose") == purpose:
                    blocks.append(cb)
        return blocks

    @classmethod
    def _extract_widget_codex_metadata(cls, results: Dict[str, Any]) -> Dict[str, Any]:
        """Metadata только от последнего widget_codex (имя/тип без подмеса от reporter/plan)."""
        for agent_key in reversed(cls._widget_codex_result_keys(results)):
            payload = results.get(agent_key)
            if not isinstance(payload, dict):
                continue
            meta = payload.get("metadata")
            if isinstance(meta, dict) and meta.get("widget_name"):
                return meta
        return {}

    @staticmethod
    def _extract_widget_metadata(results: Dict[str, Any]) -> Dict[str, Any]:
        """Устаревший обход всех агентов — для совместимости; предпочтительно _extract_widget_codex_metadata."""
        for _agent, payload in results.items():
            if not isinstance(payload, dict):
                continue
            meta = payload.get("metadata")
            if isinstance(meta, dict) and meta.get("widget_name"):
                return meta
        return {}

    # ══════════════════════════════════════════════════════════════════
    #  Request building
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_widget_request(
        user_message: str,
        content_data: Dict[str, Any],
        existing_widget_code: Optional[str],
        is_refinement: bool,
    ) -> str:
        """Формирует обогащённый запрос для Orchestrator."""
        tables = content_data.get("tables", [])
        text = content_data.get("text", "")

        if is_refinement:
            # НЕ включаем existing_widget_code в user_request —
            # он передаётся отдельно через context["existing_widget_code"]
            # и обрабатывается в _build_widget_prompt с извлечением render_body.
            request = (
                f"Обнови визуализацию виджета.\n\n"
                f"Запрос: {user_message}\n\n"
            )
        else:
            request = (
                f"Создай визуализацию (HTML виджет) для данных.\n\n"
                f"Запрос: {user_message}\n\n"
            )

        request += "Доступные данные:\n"
        if tables:
            for table in tables:
                name = table.get("name", "таблица")
                columns = table.get("columns", [])
                row_count = table.get("row_count", len(table.get("rows", [])))
                col_names = columns[:15] if isinstance(columns, list) else []
                # Handle columns that are dicts: [{"name": "col"}]
                if col_names and isinstance(col_names[0], dict):
                    col_names = [c.get("name", "") for c in col_names]
                col_str = ", ".join(col_names) if col_names else "(нет колонок)"
                request += f"  • Таблица '{name}': {row_count} строк, колонки [{col_str}]\n"
        if text:
            request += f"  • Текстовые данные: {len(text)} символов\n"

        if not is_refinement:
            request += (
                "\nСгенерируй полный HTML-код виджета с встроенными CSS и JS. "
                "Виджет должен использовать window.fetchContentData() для получения данных."
            )
        return request

    @staticmethod
    def _build_orchestrator_context(
        ctx: Dict[str, Any],
        content_data: Dict[str, Any],
        content_node_id: Optional[str],
        existing_widget_code: Optional[str],
        chat_history: List[Dict[str, Any]],
        is_refinement: bool,
    ) -> Dict[str, Any]:
        """Строит context для Orchestrator."""
        orch_ctx: Dict[str, Any] = {
            "controller": "widget",
            "mode": "widget",
            "is_refinement": is_refinement,
        }

        if content_node_id:
            orch_ctx["content_node_id"] = content_node_id

        if content_data:
            orch_ctx["content_node"] = {
                "content": content_data,
                "metadata": ctx.get("content_node_metadata", {}),
            }
            orch_ctx["data"] = {
                "tables": content_data.get("tables", []),
                "text": content_data.get("text", ""),
            }

        if existing_widget_code:
            orch_ctx["existing_widget_code"] = existing_widget_code

        if chat_history:
            orch_ctx["chat_history"] = chat_history

        return orch_ctx

    # ══════════════════════════════════════════════════════════════════
    #  Discussion mode
    # ══════════════════════════════════════════════════════════════════

    def _build_discussion_result(
        self,
        results: Dict[str, Any],
        session_id: Optional[str],
        plan: Optional[Dict[str, Any]],
        start_time: float,
    ) -> ControllerResult:
        """Формирует ControllerResult для discussion mode."""
        narrative = self._extract_narrative(results)
        if not narrative:
            narrative = "Не удалось сформировать ответ. Попробуйте переформулировать запрос."

        return ControllerResult(
            status="success",
            narrative=narrative,
            narrative_format="markdown",
            session_id=session_id,
            plan=plan,
            mode="discussion",
            execution_time_ms=self._elapsed_ms(start_time),
        )

    # ══════════════════════════════════════════════════════════════════
    #  Utility
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.time() - start_time) * 1000)
