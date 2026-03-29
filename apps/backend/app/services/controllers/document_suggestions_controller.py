"""
DocumentSuggestionsController — подсказки-промпты для чата извлечения данных из документа (V2).

Аналог TransformSuggestionsController, но контекст — текст/таблицы документа, а не ContentNode-трансформация.
Вызывается из ``POST /api/v1/files/{file_id}/analyze-document-suggestions``.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .base_controller import ControllerResult
from .document_extraction_controller import (
    DOCUMENT_PLACEHOLDER_BOARD_ID,
    DocumentExtractionController,
)
from .transform_suggestions_controller import (
    SUGGESTION_CANDIDATE_POOL,
    SUGGESTION_DISPLAY_TOP,
    TransformSuggestionsController,
)

logger = logging.getLogger("controller.document_suggestions")

# Фрагмент текста в user_request для аналитика (оркестратор режет description; см. document_suggestions в orchestrator)
_EXCERPT_MAX_TOTAL = 50_000
# При документе длиннее _EXCERPT_MAX_TOTAL: начало + хвост (в сумме не больше ~50k с разделителем)
_EXCERPT_HEAD_CHARS = 39_500
_EXCERPT_TAIL_CHARS = 9_500

# Fallback при недоступности оркестратора / LLM
DOCUMENT_FALLBACK_SUGGESTIONS: List[Dict[str, Any]] = [
    {
        "id": "doc-fb-1",
        "label": "Финансовые таблицы",
        "prompt": "Извлеки все таблицы с финансовыми показателями; укажи период и единицы измерения.",
        "type": "aggregation",
        "relevance": 0.72,
        "category": "aggregation",
        "confidence": 0.72,
        "description": "Базовая рекомендация (AI недоступен)",
        "reasoning": "",
    },
    {
        "id": "doc-fb-2",
        "label": "KPI и метрики",
        "prompt": "Найди ключевые KPI и собери их в одну таблицу: показатель, значение, период.",
        "type": "calculation",
        "relevance": 0.7,
        "category": "calculation",
        "confidence": 0.7,
        "description": "Базовая рекомендация (AI недоступен)",
        "reasoning": "",
    },
    {
        "id": "doc-fb-3",
        "label": "Структура разделов",
        "prompt": "Извлеки иерархию разделов и подразделов с номерами страниц.",
        "type": "reshape",
        "relevance": 0.65,
        "category": "reshape",
        "confidence": 0.65,
        "description": "Базовая рекомендация (AI недоступен)",
        "reasoning": "",
    },
]


class DocumentSuggestionsController(TransformSuggestionsController):
    """
    Рекомендации — это готовые промпты для чата извлечения (как клик по тегу в TransformDialog).
    """

    controller_name = "document_suggestions"

    def _fallback_result(self, start_time: float) -> ControllerResult:
        return ControllerResult(
            status="success",
            suggestions=list(DOCUMENT_FALLBACK_SUGGESTIONS),
            mode="document_suggestions_fallback",
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={"fallback": True},
        )

    @staticmethod
    def _document_text_excerpt_for_prompt(document_text: str) -> str:
        """
        Включает в промпт реальный извлечённый текст (начало + при длинном документе хвост),
        чтобы рекомендации опирались на содержание, а не на общие шаблоны.
        """
        text = (document_text or "").strip()
        if not text:
            return ""
        n = len(text)
        if n <= _EXCERPT_MAX_TOTAL:
            return text
        head = text[:_EXCERPT_HEAD_CHARS]
        tail = text[-_EXCERPT_TAIL_CHARS:]
        return (
            head
            + "\n\n… — — — [пропущена средняя часть текста: всего символов в документе: "
            + f"{n:,}] — — — …\n\n"
            + tail
        )

    @staticmethod
    def _build_document_suggestions_request(
        *,
        document_text: str,
        document_excerpt: str,
        document_type: str,
        filename: str,
        existing_tables: List[Dict[str, Any]],
        chat_history: List[Dict[str, Any]],
        page_count: Optional[int],
        mode: str,
    ) -> str:
        if mode == "iter":
            intro = (
                "Режим: дальнейшее извлечение (у пользователя уже есть начальные таблицы).\n"
                "Сформулируй промпты, опираясь на **фрагмент текста документа** ниже и на список уже извлечённых таблиц.\n\n"
            )
        else:
            intro = (
                "Сформулируй промпты для чата извлечения, опираясь на **фрагмент текста документа** ниже.\n\n"
            )

        request = intro
        request += (
            "### Фрагмент извлечённого текста документа (основа для рекомендаций)\n"
            "```text\n"
            f"{document_excerpt}\n"
            "```\n\n"
        )

        request += "Мета: "
        request += f"файл **{filename}** ({document_type.upper()})"
        if page_count is not None:
            request += f", страниц: {page_count}"
        request += f", всего символов в полном тексте: {len(document_text):,}\n\n"

        if existing_tables:
            request += f"Уже извлечённые таблицы ({len(existing_tables)}):\n"
            for t in existing_tables[:8]:
                nm = t.get("name", "?")
                rc = t.get("row_count", len(t.get("rows", []) or []))
                cols = t.get("columns", []) or []
                cnames = [
                    c.get("name", "?") if isinstance(c, dict) else str(c) for c in cols[:12]
                ]
                request += f"  • {nm}: {len(cnames)} колонок, ~{rc} строк [{', '.join(cnames)}]\n"
            request += "\n"

        chat_tail = chat_history[-10:] if isinstance(chat_history, list) else []
        if chat_tail:
            request += "Последние реплики диалога:\n"
            for i, msg in enumerate(chat_tail, 1):
                role = msg.get("role", "user")
                raw = msg.get("content", "") or ""
                content = raw[:120]
                if len(raw) > 120:
                    content += "..."
                request += f"  {i}. [{role}]: {content}\n"
            request += "\n"

        request += (
            "🎯 ЗАДАЧА: до 20 **коротких промптов на русском** для чата извлечения; каждый должен быть осмысленным "
            "именно для этого документа (сущности, разделы, числа из фрагмента выше). "
            "Типы для UI: filter, aggregation, calculation, sorting, cleaning, merge, reshape — в смысле извлечения из текста. "
            "Без графиков и дашбордов.\n"
        )
        return request

    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        ctx = context or {}
        start_time = time.time()

        board_id = str(ctx.get("board_id") or DOCUMENT_PLACEHOLDER_BOARD_ID)
        user_id = ctx.get("user_id")
        document_text = str(ctx.get("document_text", "") or "")
        document_type = str(ctx.get("document_type", "txt") or "txt")
        filename = str(ctx.get("filename", "document") or "document")
        existing_tables = ctx.get("existing_tables") or []
        if not isinstance(existing_tables, list):
            existing_tables = []
        chat_history = ctx.get("chat_history") or []
        if not isinstance(chat_history, list):
            chat_history = []
        page_count = ctx.get("page_count")

        if not document_text.strip():
            return self._error_result(
                message="Пустой текст документа: сначала выполните анализ файла (analyze-document).",
                execution_time_ms=self._elapsed_ms(start_time),
            )

        mode = "iter" if existing_tables else "new"
        document_excerpt = self._document_text_excerpt_for_prompt(document_text)
        enriched_request = self._build_document_suggestions_request(
            document_text=document_text,
            document_excerpt=document_excerpt,
            document_type=document_type,
            filename=filename,
            existing_tables=existing_tables,
            chat_history=chat_history,
            page_count=page_count,
            mode=mode,
        )

        doc_for_agents = document_text[:50_000]
        orchestrator_context: Dict[str, Any] = {
            "controller": self.controller_name,
            "mode": f"document_suggestions_{mode}",
            "chat_history": chat_history,
            "max_suggestions": SUGGESTION_CANDIDATE_POOL,
            "task_type": "document_extraction",
            "document_type": document_type,
            "filename": filename,
            "document_text_chars": len(document_text),
            "document_excerpt_preview": document_excerpt[:10_000],
            "input_data_preview": {
                "document_text": {
                    "columns": ["document_text"],
                    "sample_rows": [{"document_text": doc_for_agents}],
                }
            },
            "content_nodes_data": [
                {
                    "name": filename,
                    "content": {"text": doc_for_agents},
                }
            ],
        }
        if existing_tables:
            orchestrator_context["existing_tables_summary"] = (
                DocumentExtractionController._format_existing_tables(existing_tables)
            )

        try:
            orch_result = await self._call_orchestrator(
                user_request=enriched_request,
                board_id=board_id,
                user_id=user_id,
                context=orchestrator_context,
                skip_validation=True,
            )
        except Exception as e:
            logger.warning(f"Orchestrator call failed, returning fallback: {e}")
            return self._fallback_result(start_time)

        if orch_result.get("status") == "error":
            logger.warning(
                "Orchestrator error: %s, returning fallback",
                orch_result.get("error"),
            )
            return self._fallback_result(start_time)

        results: Dict[str, Any] = orch_result.get("results", {})
        findings = self._extract_findings(results, finding_type="recommendation")
        if not findings:
            findings = self._extract_findings(results)

        if not findings:
            logger.warning("No findings from orchestrator, returning fallback")
            return self._fallback_result(start_time)

        suggestions = self._format_suggestions(findings, SUGGESTION_DISPLAY_TOP)

        return ControllerResult(
            status="success",
            suggestions=suggestions,
            session_id=orch_result.get("session_id"),
            mode=f"document_suggestions_{mode}",
            execution_time_ms=self._elapsed_ms(start_time),
        )
