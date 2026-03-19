"""
DocumentExtractionController — Satellite Controller для AI-извлечения данных из документов.

Workflow:
1. Получает текст документа + пользовательский запрос
2. Формирует обогащённый контекст (document_text, existing_tables, document_type)
3. Вызывает orchestrator.process_request()
4. Извлекает tables + narrative из результата
5. Возвращает ControllerResult с таблицами и описанием

Используется в DocumentSourceDialog — итеративный чат для извлечения данных из PDF/DOCX/TXT.

См. docs/SOURCE_NODE_CONCEPT_V2.md → раздел "📄 4. Document Dialog"
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .base_controller import BaseController, ControllerResult

logger = logging.getLogger("controller.document_extraction")

# Placeholder board_id для file-level сценариев (orchestrator требует board_id)
DOCUMENT_PLACEHOLDER_BOARD_ID = "00000000-0000-0000-0000-000000000002"


class DocumentExtractionController(BaseController):
    """
    Контроллер извлечения данных из документов.

    Вызывается из route-handler ``/files/{file_id}/extract-document-chat``.
    Итеративный чат: пользователь описывает, какие данные извлечь,
    AI анализирует текст документа и возвращает таблицы + описание.
    """

    controller_name = "document_extraction"

    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Обрабатывает запрос на извлечение данных из документа.

        Args:
            user_message: Запрос пользователя ("Извлеки таблицу расходов из раздела 3")
            context: {
                "board_id": str,
                "user_id": str,
                "document_text": str,        # Полный текст документа
                "document_type": str,        # pdf | docx | txt
                "filename": str,             # Имя файла
                "existing_tables": list,     # Уже извлечённые таблицы
                "chat_history": list[dict],  # История чата [{role, content}]
                "page_count": int | None,
            }

        Returns:
            ControllerResult с tables в metadata + narrative.
        """
        ctx = context or {}
        start_time = time.time()

        board_id = ctx.get("board_id", "")
        user_id = ctx.get("user_id")
        document_text = ctx.get("document_text", "")
        document_type = ctx.get("document_type", "unknown")
        filename = ctx.get("filename", "document")
        existing_tables = ctx.get("existing_tables", [])
        chat_history = ctx.get("chat_history", [])
        page_count = ctx.get("page_count")

        if not str(document_text or "").strip():
            return self._error_result(
                message="Пустой текст документа: сначала выполните анализ файла (analyze-document).",
                execution_time_ms=self._elapsed_ms(start_time),
            )

        # 1. Сформировать обогащённый запрос с контекстом документа
        enriched_request = self._build_enriched_request(
            user_message=user_message,
            document_text=document_text,
            document_type=document_type,
            filename=filename,
            existing_tables=existing_tables,
            page_count=page_count,
        )

        # 2. Подготовить контекст для Orchestrator
        doc_for_agents = document_text[:20000]
        orchestrator_context: Dict[str, Any] = {
            "task_type": "document_extraction",
            "document_type": document_type,
            "filename": filename,
            "chat_history": chat_history,
            # Важно: Structurizer читает вход именно из input_data_preview/content_nodes_data,
            # а не из user_request. Без этих полей он отвечает "No input content provided...".
            "input_data_preview": {
                "document_text": {
                    "columns": ["document_text"],
                    "sample_rows": [{"document_text": doc_for_agents}],
                }
            },
            "content_nodes_data": [
                {
                    "name": filename,
                    "content": {
                        "text": doc_for_agents,
                    },
                }
            ],
        }

        if existing_tables:
            tables_summary = self._format_existing_tables(existing_tables)
            orchestrator_context["existing_tables_summary"] = tables_summary

        # 3. Вызвать Orchestrator
        orch_result = await self._call_orchestrator(
            user_request=enriched_request,
            board_id=board_id or DOCUMENT_PLACEHOLDER_BOARD_ID,
            user_id=user_id,
            context=orchestrator_context,
        )

        if orch_result.get("status") == "error":
            return self._error_result(
                message=orch_result.get("error", "Orchestrator error"),
                execution_time_ms=self._elapsed_ms(start_time),
            )

        results: Dict[str, Any] = orch_result.get("results", {})

        # 4. Извлечь данные из результатов агентов
        tables = self._extract_tables(results)
        narrative = self._extract_narrative(results)
        findings = self._extract_findings(results)

        # 5. Построить ответ
        return ControllerResult(
            status="success",
            narrative=narrative or "Анализ документа выполнен.",
            narrative_format="markdown",
            mode="document_extraction",
            session_id=orch_result.get("session_id"),
            plan=orch_result.get("plan"),
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={
                "tables": tables,
                "findings": [f for f in findings],
                "document_type": document_type,
                "filename": filename,
            },
        )

    # ══════════════════════════════════════════════════════════════════
    #  Private helpers
    # ══════════════════════════════════════════════════════════════════

    def _build_enriched_request(
        self,
        user_message: str,
        document_text: str,
        document_type: str,
        filename: str,
        existing_tables: list,
        page_count: int | None,
    ) -> str:
        """Формирует обогащённый запрос с контекстом документа."""
        # Ограничиваем текст документа (LLM context window)
        max_doc_chars = 15000
        doc_preview = document_text[:max_doc_chars]
        truncated = len(document_text) > max_doc_chars

        parts = [
            f"## Задача: извлечение данных из документа",
            f"",
            f"**Файл:** {filename} ({document_type.upper()})",
        ]

        if page_count:
            parts.append(f"**Страниц:** {page_count}")

        parts.extend([
            f"**Размер текста:** {len(document_text):,} символов",
            f"",
            f"### Запрос пользователя",
            f"{user_message}",
            f"",
            f"### Текст документа" + (" (фрагмент)" if truncated else ""),
            f"```",
            doc_preview,
            f"```",
        ])

        if truncated:
            parts.append(f"\n_...текст обрезан, полный размер: {len(document_text):,} символов_")

        if existing_tables:
            parts.append(f"\n### Уже извлечённые таблицы ({len(existing_tables)} шт.)")
            for t in existing_tables[:5]:
                name = t.get("name", "?")
                cols = len(t.get("columns", []))
                rows = t.get("row_count", 0)
                parts.append(f"- **{name}**: {cols} столбцов, {rows} строк")

        parts.extend([
            f"",
            f"### Инструкция",
            f"Проанализируй документ и выполни запрос пользователя.",
            f"Если в документе есть таблицы — извлеки их в структурированном виде "
            f"(tables с columns и rows).",
            f"Если запрос про текстовый анализ — опиши результат в narrative.",
            f"Возвращай данные в формате AgentPayload: tables для структурированных данных, "
            f"narrative для текстового описания.",
        ])

        return "\n".join(parts)

    @staticmethod
    def _format_existing_tables(tables: list) -> str:
        """Format existing tables summary for orchestrator context."""
        lines = []
        for t in tables[:5]:
            name = t.get("name", "?")
            columns = t.get("columns", [])
            col_names = [c.get("name", "?") if isinstance(c, dict) else str(c) for c in columns[:8]]
            rows = t.get("row_count", len(t.get("rows", [])))
            lines.append(f"  - {name}: [{', '.join(col_names)}] ({rows} rows)")
        return "\n".join(lines)

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        """Calculate elapsed time in milliseconds."""
        return int((time.time() - start_time) * 1000)
