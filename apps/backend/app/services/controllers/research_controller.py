"""
ResearchController — Satellite Controller для Research Source и Research Chat.

Вызывает Orchestrator (research pipeline: discovery → research → structurizer
→ analyst → reporter) и извлекает narrative, tables, sources для:
- POST /api/v1/research/chat (чат в ResearchSourceDialog)
- ResearchSource.extract() при создании/refresh источника

См. docs/AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md
"""

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .base_controller import BaseController, ControllerResult


logger = logging.getLogger("controller.research")


# Placeholder board_id для вызова без привязки к доске (orchestrator требует board_id)
RESEARCH_PLACEHOLDER_BOARD_ID = "00000000-0000-0000-0000-000000000001"


class ResearchController(BaseController):
    """
    Контроллер для сценариев Deep Research.

    Единая точка извлечения результатов мультиагента (narrative, tables, sources).
    Используется роутом research/chat и ResearchSource.extract().
    """

    controller_name = "research"

    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Обрабатывает запрос исследования через Orchestrator.

        Args:
            user_message: Текст запроса (например initial_prompt или сообщение из чата).
            context: Опционально session_id, chat_history, user_id.

        Returns:
            ControllerResult с narrative, tables, sources, session_id, plan.
        """
        ctx = context or {}
        start_time = time.time()
        session_id = ctx.get("session_id") or str(uuid4())
        user_id = ctx.get("user_id")
        chat_history = ctx.get("chat_history", [])

        # Промпт для мультиагента: акцент на структурированный результат (таблицы)
        enriched_request = self._build_research_request(user_message)

        orch_context: Dict[str, Any] = {
            "controller": "research",
            "mode": "research",
        }
        if chat_history:
            orch_context["chat_history"] = chat_history
        for key in ("_progress_callback", "_enable_plan_progress"):
            if key in ctx:
                orch_context[key] = ctx[key]

        orch_result = await self._call_orchestrator(
            user_request=enriched_request,
            board_id=RESEARCH_PLACEHOLDER_BOARD_ID,
            user_id=user_id,
            session_id=session_id,
            context=orch_context,
        )

        if orch_result.get("status") == "error":
            return self._error_result(
                message=orch_result.get("error", "Orchestrator error"),
                execution_time_ms=self._elapsed_ms(start_time),
            )

        results: Dict[str, Any] = orch_result.get("results", {})
        returned_session = orch_result.get("session_id", session_id)
        plan = orch_result.get("plan")

        narrative = self._extract_narrative(results)
        tables = self._extract_tables(results)
        sources = self._extract_sources(results)
        discovered_resources = self._extract_discovered_resources(results)

        return ControllerResult(
            status="success",
            narrative=narrative or "",
            tables=tables,
            sources=sources,
            discovered_resources=discovered_resources,
            session_id=returned_session,
            plan=plan,
            mode="research",
            execution_time_ms=self._elapsed_ms(start_time),
        )

    @staticmethod
    def _build_research_request(user_message: str) -> str:
        """
        Формирует промпт для мультиагента с акцентом на структурированный результат.

        Важно: основной запрос пользователя идёт первым, чтобы Planner и Discovery
        строили план и поисковый запрос по сути вопроса (как в Playground). Форматный
        хинт — коротко в конце, чтобы не искажать поиск и не менять план.
        """
        text = user_message.strip()
        format_hint = (
            "\n\n[Формат ответа: по возможности представь данные в виде таблиц "
            "(название, колонки, строки); краткий текстовый итог приложи отдельно.]"
        )
        return text + format_hint

    @staticmethod
    def _extract_sources(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлекает sources из payload агента research (research, research_2, ...).

        Для ответа API возвращаем только url и title (без content).
        """
        out: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        for key, payload in results.items():
            if not isinstance(payload, dict) or not key.startswith("research"):
                continue
            for s in payload.get("sources", []):
                if not isinstance(s, dict):
                    continue
                url = s.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                entry: Dict[str, Any] = {
                    "url": url,
                    "title": s.get("title") or s.get("name") or url,
                }
                if s.get("mime_type"):
                    entry["mime_type"] = s.get("mime_type")
                if s.get("resource_kind"):
                    entry["resource_kind"] = s.get("resource_kind")
                if s.get("metadata") and isinstance(s.get("metadata"), dict):
                    entry["metadata"] = s.get("metadata")
                out.append(entry)
        return out

    @staticmethod
    def _extract_discovered_resources(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Каталог URL из payload research (страницы + embedded и т.д.)."""
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for key, payload in results.items():
            if not isinstance(payload, dict) or not key.startswith("research"):
                continue
            for dr in payload.get("discovered_resources") or []:
                if not isinstance(dr, dict):
                    continue
                url = dr.get("url")
                if not url or not isinstance(url, str) or url in seen:
                    continue
                seen.add(url)
                entry: Dict[str, Any] = {"url": url}
                if dr.get("resource_kind"):
                    entry["resource_kind"] = dr.get("resource_kind")
                if dr.get("mime_type"):
                    entry["mime_type"] = dr.get("mime_type")
                if dr.get("parent_url"):
                    entry["parent_url"] = dr.get("parent_url")
                if dr.get("origin"):
                    entry["origin"] = dr.get("origin")
                if dr.get("tag"):
                    entry["tag"] = dr.get("tag")
                if dr.get("title"):
                    entry["title"] = dr.get("title")
                out.append(entry)
        return out

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.time() - start_time) * 1000)
