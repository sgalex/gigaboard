"""
DocumentExtractionController — Satellite Controller для AI-извлечения данных из документов.

Workflow:
1. Получает текст документа + пользовательский запрос
2. Формирует обогащённый контекст (document_text, existing_tables, document_type)
3. Вызывает orchestrator.process_request()
4. Извлекает tables + narrative из результата
5. Возвращает ControllerResult с таблицами и описанием

Используется в DocumentSourceDialog — итеративный чат для извлечения данных из PDF/DOCX/TXT.

См. docs/SOURCE_NODE_CONCEPT.md → раздел "📄 4. Document Dialog"
"""

import logging
import re
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

        # 1. Сформировать обогащённый запрос с контекстом документа и историей диалога
        enriched_request = self._build_enriched_request(
            user_message=user_message,
            document_text=document_text,
            document_type=document_type,
            filename=filename,
            existing_tables=existing_tables,
            page_count=page_count,
            chat_history=chat_history if isinstance(chat_history, list) else [],
        )

        # 2. Подготовить контекст для Orchestrator
        doc_for_agents = document_text[:20000]
        orchestrator_context: Dict[str, Any] = {
            "controller": self.controller_name,
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

        for key in ("_progress_callback", "_enable_plan_progress"):
            if key in ctx:
                orchestrator_context[key] = ctx[key]

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

        # 4b. Reporter часто отдаёт таблицу в markdown в narrative, а structurizer — только схему без строк
        tables = self._enrich_tables_from_narrative_markdown(tables, narrative or "")
        # 4c. Structurizer в промпте задаёт rows как list[list]; UI/БД ожидают list[dict] по именам колонок
        tables = DocumentExtractionController._normalize_table_rows_to_dicts(tables)
        # 4d. После merge из narrative markdown ключи в row могут не совпадать с columns (Reporter vs structurizer)
        tables = DocumentExtractionController._align_dict_rows_to_schema_columns(tables)

        # 5. Лог трейса мультиагента (JSONL на сервере) + ответ
        trace_fp = orch_result.get("trace_file_path")
        if trace_fp:
            logger.info(
                "document_extraction: session_id=%s trace_file=%s tables=%d",
                orch_result.get("session_id"),
                trace_fp,
                len(tables),
            )

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
                "trace_file_path": trace_fp,
            },
        )

    # ══════════════════════════════════════════════════════════════════
    #  Private helpers
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _column_names_from_table(t: Dict[str, Any]) -> List[str]:
        cols = t.get("columns") or []
        out: List[str] = []
        for c in cols:
            if isinstance(c, dict):
                out.append(str(c.get("name", "")).strip())
            else:
                out.append(str(c).strip())
        return [x for x in out if x]

    @staticmethod
    def _normalize_table_rows_to_dicts(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Приводит rows к list[dict] с ключами по именам колонок (как structurizer._add_row_ids)."""
        out: List[Dict[str, Any]] = []
        for t in tables:
            if not isinstance(t, dict):
                continue
            names = DocumentExtractionController._column_names_from_table(t)
            rows_in = t.get("rows")
            if not isinstance(rows_in, list):
                rows_in = []
            new_rows: List[Dict[str, Any]] = []
            for row in rows_in:
                if isinstance(row, dict):
                    new_rows.append(row)
                elif isinstance(row, list) and names:
                    new_rows.append(
                        {names[j]: row[j] for j in range(min(len(row), len(names)))}
                    )
                elif isinstance(row, str) and names:
                    rdict = {names[0]: row}
                    for c in names[1:]:
                        rdict[c] = None
                    new_rows.append(rdict)
                else:
                    new_rows.append({})

            t2 = dict(t)
            t2["rows"] = new_rows
            t2["row_count"] = len(new_rows)
            out.append(t2)
        return out

    @staticmethod
    def _align_dict_rows_to_schema_columns(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Перекидывает значения row dict на имена из table.columns (exact / trim / по позиции).

        Иначе после _enrich_tables_from_narrative_markdown строки остаются с ключами из markdown,
        а карточка ренерит по structurizer columns — визуально «только заголовки».
        """
        out: List[Dict[str, Any]] = []
        for t in tables:
            if not isinstance(t, dict):
                continue
            names = DocumentExtractionController._column_names_from_table(t)
            rows_in = t.get("rows")
            if not isinstance(rows_in, list) or not names:
                out.append(t)
                continue
            new_rows: List[Dict[str, Any]] = []
            for row in rows_in:
                if not isinstance(row, dict):
                    new_rows.append(row)
                    continue
                rebuilt: Dict[str, Any] = {}
                matched_all = True
                for n in names:
                    if n in row:
                        rebuilt[n] = row[n]
                    elif (sk := next((k for k in row if str(k).strip() == n.strip()), None)) is not None:
                        rebuilt[n] = row[sk]
                    elif (sk2 := next((k for k in row if str(k).strip().lower() == n.lower()), None)) is not None:
                        rebuilt[n] = row[sk2]
                    else:
                        matched_all = False
                        break
                if matched_all and len(rebuilt) == len(names):
                    new_rows.append(rebuilt)
                    continue
                vals = list(row.values())
                if len(vals) == len(names):
                    new_rows.append({names[i]: vals[i] for i in range(len(names))})
                else:
                    new_rows.append(row)
            t2 = dict(t)
            t2["rows"] = new_rows
            t2["row_count"] = len(new_rows)
            out.append(t2)
        return out

    @staticmethod
    def _parse_markdown_pipe_tables(narrative: str) -> List[Dict[str, Any]]:
        """Извлекает pipe-таблицы из markdown (как в ответе Reporter)."""
        if not narrative or "|" not in narrative:
            return []
        lines = narrative.split("\n")
        blocks: List[List[str]] = []
        current: List[str] = []
        for line in lines:
            stripped = line.strip()
            if "|" in stripped and stripped.count("|") >= 2:
                if re.match(r"^[\|\-\s:+\.]+$", stripped):
                    continue
                current.append(stripped)
            else:
                if len(current) >= 2:
                    blocks.append(current)
                current = []
        if len(current) >= 2:
            blocks.append(current)

        parsed: List[Dict[str, Any]] = []
        for block in blocks:
            rows_raw: List[List[str]] = []
            for raw in block:
                cells = [c.strip() for c in raw.split("|")]
                if cells and not cells[0]:
                    cells = cells[1:]
                if cells and not cells[-1]:
                    cells = cells[:-1]
                if cells:
                    rows_raw.append(cells)
            if len(rows_raw) < 2:
                continue
            headers = rows_raw[0]
            col_objs = [{"name": h or f"col_{i + 1}", "type": "string"} for i, h in enumerate(headers)]
            data_rows: List[Dict[str, Any]] = []
            for row_cells in rows_raw[1:]:
                row_dict: Dict[str, Any] = {}
                for i, h in enumerate(headers):
                    key = h or f"col_{i + 1}"
                    row_dict[key] = row_cells[i] if i < len(row_cells) else ""
                data_rows.append(row_dict)
            parsed.append({"columns": col_objs, "rows": data_rows})
        return parsed

    @classmethod
    def _enrich_tables_from_narrative_markdown(
        cls,
        tables: List[Dict[str, Any]],
        narrative: str,
    ) -> List[Dict[str, Any]]:
        """Подставляет строки из markdown-таблиц narrative, если structured tables пустые."""
        md_tables = cls._parse_markdown_pipe_tables(narrative)
        if not md_tables:
            return tables

        def _rows_empty(t: Dict[str, Any]) -> bool:
            r = t.get("rows")
            return not isinstance(r, list) or len(r) == 0

        out: List[Dict[str, Any]] = []
        md_idx = 0

        if not tables:
            for i, md in enumerate(md_tables):
                out.append(
                    {
                        "name": f"extracted_table_{i + 1}",
                        "columns": md["columns"],
                        "rows": md["rows"],
                        "row_count": len(md["rows"]),
                    }
                )
            if out:
                logger.info(
                    "document_extraction: filled %s table(s) from narrative markdown only",
                    len(out),
                )
            return out or tables

        for t in tables:
            t = dict(t) if isinstance(t, dict) else {}
            if not _rows_empty(t) or md_idx >= len(md_tables):
                out.append(t)
                continue

            md = md_tables[md_idx]
            struct_cols = set(c.lower() for c in cls._column_names_from_table(t))
            md_col_set = set()
            for c in md.get("columns", []) or []:
                if isinstance(c, dict):
                    n = (c.get("name") or "").strip().lower()
                    if n:
                        md_col_set.add(n)

            # Порядок: N-я пустая structured ↔ N-я markdown-таблица в narrative (Reporter часто кладёт данные только туда)
            t["rows"] = md["rows"]
            t["row_count"] = len(md["rows"])
            if not t.get("columns") and md.get("columns"):
                t["columns"] = md["columns"]
            md_idx += 1
            if struct_cols and md_col_set and not (struct_cols & md_col_set):
                logger.warning(
                    "document_extraction: column names differ structured=%s markdown=%s — merged by order",
                    struct_cols,
                    md_col_set,
                )
            else:
                logger.info(
                    "document_extraction: merged markdown rows into table %r (%s rows)",
                    t.get("name", "?"),
                    len(md["rows"]),
                )
            out.append(t)

        return out

    def _build_enriched_request(
        self,
        user_message: str,
        document_text: str,
        document_type: str,
        filename: str,
        existing_tables: list,
        page_count: int | None,
        chat_history: list | None = None,
    ) -> str:
        """Формирует обогащённый запрос с контекстом документа и историей диалога.

        История должна попадать в user_request: агенты (structurizer и др.) опираются на этот текст,
        а не только на поле context.chat_history.
        """
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
        ])

        # История как в Transform: в chat_history может быть и текущий user; в блоке «Текущий запрос» — без дубля
        history_lines = self._format_chat_history_for_prompt(
            chat_history or [],
            current_user_message=user_message,
        )
        if history_lines:
            parts.extend(
                [
                    "### История диалога (учитывай при извлечении и уточнениях)",
                    *history_lines,
                    "",
                ]
            )

        parts.extend(
            [
                "### Текущий запрос пользователя",
                f"{user_message}",
                f"",
                f"### Текст документа" + (" (фрагмент)" if truncated else ""),
                f"```",
                doc_preview,
                f"```",
            ]
        )

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
    def _format_chat_history_for_prompt(
        chat_history: list,
        *,
        current_user_message: str = "",
    ) -> list[str]:
        """Строки markdown для блока истории; роли user/assistant, умеренное усечение.

        Если последняя реплика — user с тем же текстом, что и ``current_user_message`` (как в TransformDialog:
        ``fullChatHistory`` включает текущее сообщение), не дублируем её здесь — она в «### Текущий запрос».
        """
        if not chat_history:
            return []
        lines: list[str] = []
        max_msgs = 30
        max_chars_per_msg = 4000
        tail = list(chat_history[-max_msgs:] if len(chat_history) > max_msgs else chat_history)
        if tail and current_user_message:
            last = tail[-1]
            if (
                isinstance(last, dict)
                and str(last.get("role", "")).strip() == "user"
                and str(last.get("content", "") or "").strip() == str(current_user_message).strip()
            ):
                tail = tail[:-1]
        if not tail:
            return []
        for i, msg in enumerate(tail, 1):
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", "")).strip()
            if role not in ("user", "assistant"):
                continue
            content = str(msg.get("content", "") or "")
            if len(content) > max_chars_per_msg:
                content = content[:max_chars_per_msg] + "\n… [сообщение обрезано]"
            label = "Пользователь" if role == "user" else "Ассистент"
            lines.append(f"{i}. **{label}:**")
            lines.append(content)
            lines.append("")
        return lines

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
