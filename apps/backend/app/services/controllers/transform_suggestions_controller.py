"""
TransformSuggestionsController — Satellite Controller для подсказок по трансформациям (V2).

Заменяет прямой вызов TransformSuggestionsAgent из route-handler'а:
- analyze_transform_suggestions → handle_request()

Workflow:
1. Получить input_schemas + existing_code + chat_history
2. Сформировать запрос к Orchestrator
3. Извлечь findings[type="recommendation"]
4. Форматировать в UI-теги

Два режима:
- NEW TRANSFORMATION — подсказки на основе схемы данных
- ITERATIVE IMPROVEMENT — подсказки на основе текущего кода

См. docs/MULTI_AGENT_V2_CONCEPT.md → Phase 4.3
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from .base_controller import BaseController, ControllerResult

logger = logging.getLogger("controller.transform_suggestions")

# До CANDIDATE_POOL идей отдаём в LLM/оркестратор; клиенту — top DISPLAY_TOP по relevance
SUGGESTION_CANDIDATE_POOL = 20
SUGGESTION_DISPLAY_TOP = 12

# Фоллбэк-подсказки (если AI недоступен)
FALLBACK_SUGGESTIONS: List[Dict[str, Any]] = [
    {
        "id": "fallback-filter",
        "label": "Фильтрация данных",
        "prompt": "Отфильтровать строки по условию",
        "type": "filter",
        "relevance": 0.7,
        "category": "filter",
        "confidence": 0.7,
        "description": "Базовая рекомендация (AI недоступен)",
        "reasoning": "",
    },
    {
        "id": "fallback-aggregate",
        "label": "Группировка",
        "prompt": "Сгруппировать данные и посчитать агрегаты",
        "type": "aggregation",
        "relevance": 0.65,
        "category": "aggregation",
        "confidence": 0.65,
        "description": "Базовая рекомендация (AI недоступен)",
        "reasoning": "",
    },
    {
        "id": "fallback-sort",
        "label": "Сортировка",
        "prompt": "Отсортировать данные по колонке",
        "type": "sorting",
        "relevance": 0.6,
        "category": "sorting",
        "confidence": 0.6,
        "description": "Базовая рекомендация (AI недоступен)",
        "reasoning": "",
    },
]


class TransformSuggestionsController(BaseController):
    """
    Контроллер подсказок для трансформаций.

    Вызывается из route ``POST /{id}/analyze-transform-suggestions``.
    Формирует запрос к Orchestrator, извлекает ``findings``
    типа ``recommendation``, форматирует для UI.
    """

    controller_name = "transform_suggestions"

    @staticmethod
    def _content_nodes_data_from_input_schemas(
        *,
        content_node_id: str,
        node_name: str,
        input_schemas: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Таблицы и текст для content_nodes_data (как у TransformationController)."""
        tables: List[Dict[str, Any]] = []
        text_chunks: List[str] = []
        for schema in input_schemas:
            if schema.get("is_text_only"):
                ct = (schema.get("content_text") or "").strip()
                if ct:
                    text_chunks.append(ct)
                continue
            name = schema.get("name", "df")
            cols_raw = schema.get("columns", [])
            col_objs: List[Dict[str, Any]] = []
            for c in cols_raw:
                if isinstance(c, dict):
                    col_objs.append(
                        {
                            "name": c.get("name", "?"),
                            "type": c.get("type"),
                        }
                    )
                else:
                    col_objs.append({"name": str(c), "type": None})
            rows = schema.get("sample_rows", [])
            rc = schema.get("row_count", len(rows))
            tables.append(
                {
                    "name": name,
                    "columns": col_objs,
                    "rows": rows,
                    "row_count": int(rc) if isinstance(rc, (int, float)) else len(rows),
                }
            )
        merged_text = "\n\n".join(text_chunks)
        if not merged_text and input_schemas:
            merged_text = (input_schemas[0].get("content_text") or "") or ""
        return [
            {
                "id": content_node_id,
                "node_id": content_node_id,
                "name": node_name,
                "tables": tables,
                "text": merged_text,
            }
        ]

    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Генерирует подсказки по трансформациям.

        Args:
            user_message: Автоматически формируемый запрос
                ("Предложи трансформации для данных с такой схемой")
            context: {
                "board_id": str,
                "user_id": str,
                "input_schemas": list[dict],  # [{name, columns, content_text, ...}]
                "existing_code": str | None,
                "chat_history": list[dict],
            }

        Размер пула для LLM и число подсказок в ответе API — константы
        ``SUGGESTION_CANDIDATE_POOL`` и ``SUGGESTION_DISPLAY_TOP``.

        Returns:
            ControllerResult с suggestions list.
        """
        ctx = context or {}
        start_time = time.time()

        board_id = ctx.get("board_id", "")
        user_id = ctx.get("user_id")
        input_schemas = ctx.get("input_schemas", [])
        existing_code = ctx.get("existing_code")
        chat_history = ctx.get("chat_history", [])

        # Определить режим
        mode = "improve" if existing_code else "new"

        # Сформировать обогащённый запрос
        enriched_request = self._build_suggestions_request(
            input_schemas=input_schemas,
            existing_code=existing_code,
            chat_history=chat_history,
            mode=mode,
        )

        # Формируем input_data_preview в том же формате, что TransformationController
        # — стандартный ключ контекста, который читают Planner и Analyst
        input_data_preview: Dict[str, Any] = {}
        for schema in input_schemas:
            name = schema.get("name", "df")
            columns = schema.get("columns", [])
            sample_rows = schema.get("sample_rows", [])
            row_count = schema.get("row_count", len(sample_rows))
            input_data_preview[name] = {
                "columns": columns,
                "row_count": row_count,
                "sample_rows": sample_rows[:20],
            }

        primary_content_node_id = str(ctx.get("content_node_id") or "").strip()
        selected_ids = [
            str(item).strip()
            for item in (ctx.get("selected_node_ids", []) or [])
            if str(item).strip()
        ]
        if primary_content_node_id and primary_content_node_id not in selected_ids:
            selected_ids.insert(0, primary_content_node_id)
        if not primary_content_node_id and selected_ids:
            primary_content_node_id = selected_ids[0]

        orchestrator_context: Dict[str, Any] = {
            "controller": self.controller_name,
            "mode": f"transform_suggestions_{mode}",
            "input_data_preview": input_data_preview,
            "existing_code": existing_code,
            "chat_history": chat_history,
            "max_suggestions": SUGGESTION_CANDIDATE_POOL,
            "keep_tabular_context_in_prompt": True,
        }
        if primary_content_node_id:
            orchestrator_context["content_node_id"] = primary_content_node_id
            orchestrator_context["transformation_scope"] = {
                "primary_content_node_id": primary_content_node_id,
                "selected_node_ids": selected_ids or [primary_content_node_id],
                "local_content_only": True,
                "prefer_tools_for_tables": True,
                "disallow_external_sources_unless_explicit": True,
            }
        if selected_ids:
            orchestrator_context["selected_node_ids"] = selected_ids
            orchestrator_context["content_node_ids"] = selected_ids
            orchestrator_context["contentNodeIds"] = selected_ids
        if primary_content_node_id and input_schemas:
            orchestrator_context["content_nodes_data"] = (
                TransformSuggestionsController._content_nodes_data_from_input_schemas(
                    content_node_id=primary_content_node_id,
                    node_name=str(ctx.get("content_node_name") or "content_node"),
                    input_schemas=input_schemas,
                )
            )
        if isinstance(ctx.get("content_nodes_data"), list) and ctx.get("content_nodes_data"):
            orchestrator_context["content_nodes_data"] = ctx.get("content_nodes_data")

        # Вызвать Orchestrator
        try:
            orch_result = await self._call_orchestrator(
                user_request=enriched_request,
                board_id=board_id,
                user_id=user_id,
                context=orchestrator_context,
                skip_validation=True,  # Подсказки не требуют QualityGate
            )
        except Exception as e:
            logger.warning(f"Orchestrator call failed, returning fallback: {e}")
            return self._fallback_result(start_time)

        if orch_result.get("status") == "error":
            logger.warning(
                f"Orchestrator error: {orch_result.get('error')}, returning fallback"
            )
            return self._fallback_result(start_time)

        results: Dict[str, Any] = orch_result.get("results", {})

        # DEBUG: Логируем что пришло от агентов
        logger.info(f"🔍 Results from orchestrator: {list(results.keys())}")
        for agent_name, payload in results.items():
            if isinstance(payload, dict):
                findings_count = len(payload.get("findings", []))
                logger.info(f"  • {agent_name}: {findings_count} findings")
                # Логируем типы findings для debug
                for i, f in enumerate(payload.get("findings", [])[:3], 1):
                    if isinstance(f, dict):
                        logger.info(f"    Finding {i}: type={f.get('type')}, title={f.get('title', '')[:50]}")

        # Извлечь findings[type="recommendation"]
        findings = self._extract_findings(results, finding_type="recommendation")
        logger.info(f"📊 Extracted {len(findings)} findings with type='recommendation'")

        if not findings:
            # Попробовать без фильтра — агент мог не выставить type
            findings = self._extract_findings(results)
            logger.info(f"📊 Extracted {len(findings)} findings without type filter")

        if not findings:
            logger.warning("No findings from orchestrator, returning fallback")
            return self._fallback_result(start_time)

        # Форматировать в suggestions для UI
        suggestions = self._format_suggestions(findings, SUGGESTION_DISPLAY_TOP)

        return ControllerResult(
            status="success",
            suggestions=suggestions,
            session_id=orch_result.get("session_id"),
            mode=f"transform_suggestions_{mode}",
            execution_time_ms=self._elapsed_ms(start_time),
        )

    # ══════════════════════════════════════════════════════════════════
    #  Request building
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_suggestions_request(
        input_schemas: List[Dict[str, Any]],
        existing_code: Optional[str],
        chat_history: List[Dict[str, Any]],
        mode: str,
    ) -> str:
        """Формирует текст запроса для Orchestrator."""
        if mode == "improve":
            # Режим "improve": предлагаем СЛЕДУЮЩИЕ трансформации для результата
            request = (
                "Предложи варианты ДАЛЬНЕЙШИХ трансформаций данных.\n\n"
                "Контекст: данные уже прошли трансформацию (код приведён ниже). "
                "Нужны идеи для продолжения анализа — новые группировки, фильтры, вычисления.\n\n"
                f"Применённая трансформация:\n```python\n{existing_code}\n```\n\n"
            )
        else:
            request = "Предложи варианты трансформации данных.\n\n"

        if input_schemas:
            request += "Доступные данные:\n"
            for schema in input_schemas:
                name = schema.get("name", "df")
                columns = schema.get("columns", [])
                text = schema.get("content_text", "")
                is_text = schema.get("is_text_only", False)
                row_count = schema.get("row_count", 0)

                if is_text:
                    request += f"  • Текстовый контент: {len(text)} символов\n"
                else:
                    col_str = ", ".join(columns[:15]) if columns else "(нет колонок)"
                    request += f"  • Таблица '{name}': колонки [{col_str}], {row_count} строк\n"

        if chat_history:
            request += "\nПолная история диалога:\n"
            for i, msg in enumerate(chat_history, 1):
                role = msg.get("role", "user")
                # Ограничиваем длину каждого сообщения (150 символов)
                content = msg.get("content", "")[:150]
                if len(msg.get("content", "")) > 150:
                    content += "..."
                request += f"  {i}. [{role}]: {content}\n"

        request += (
            "\n🎯 ЗАДАЧА: Проанализируй данные и предложи до 20 разнообразных вариантов ТРАНСФОРМАЦИИ "
            "(минимум 12, если данных достаточно):\n"
            "  • filter — фильтрация данных (отбор строк)\n"
            "  • aggregation — группировка и агрегация (сумма, среднее, COUNT)\n"
            "  • calculation — вычисляемые столбцы (новые колонки, формулы)\n"
            "  • sorting — сортировка и ранжирование (TOP N, RANK)\n"
            "  • cleaning — очистка данных (NULL, дубликаты)\n"
            "  • merge — объединение таблиц (JOIN); для связей В ПЕРВУЮ ОЧЕРЕДЬ используй суррогатные ключи из источников: "
            "GUID/UUID и столбцы с суффиксом _id; учитывай имена полей как подсказку: например company_id к таблице company, "
            "product_company_id — возможная связь таблиц product и company; не предлагай join только по «человеческим» полям, "
            "если для тех же сущностей уже есть технический идентификатор\n"
            "  • reshape — изменение структуры (PIVOT, транспонирование)\n\n"
            "⚠️ ОГРАНИЧЕНИЯ:\n"
            "  • НЕ предлагай визуализации (графики, chart, dashboard) — только трансформации данных\n"
            "  • Покрой РАЗНЫЕ типы операций (минимум 1-2 из каждого типа)\n"
            "  • Оцени актуальность каждой рекомендации (0.0-1.0)\n"
        )

        return request

    # ══════════════════════════════════════════════════════════════════
    #  Formatting
    # ══════════════════════════════════════════════════════════════════

    def _format_suggestions(
        self,
        findings: List[Dict[str, Any]],
        max_count: int = 6,
    ) -> List[Dict[str, Any]]:
        """
        Конвертирует findings в формат UI-подсказок.

        Берём все подходящие findings, сортируем по relevance, возвращаем top max_count.

        Finding (AgentPayload) → Suggestion (UI):
            {type, text, severity, confidence, refs, action, metadata}
            → {id, label, prompt, type, relevance, category, confidence, description}
        """
        suggestions: List[Dict[str, Any]] = []

        # Обрабатываем все findings, потом сортируем и берём топ-N
        for i, finding in enumerate(findings):
            # Finding fields: text (описание), action (рекомендуемое действие),
            # confidence, refs (ссылки на колонки), severity
            text = finding.get("text", "")
            action = finding.get("action", "")

            # Фильтруем визуализации — они относятся к widget suggestions
            combined_text = f"{text} {action} {finding.get('title', '')} {finding.get('description', '')}"
            if self._is_visualization_suggestion(combined_text):
                continue

            refs = finding.get("refs", [])
            confidence = finding.get("confidence")

            # Также поддерживаем legacy формат (title, description, metadata)
            # NB: используем `or {}` т.к. finding может содержать {"metadata": None}
            meta = finding.get("metadata") or {}
            
            # Label: используем первое непустое значение
            label = (
                finding.get("title")
                or text
                or action
                or meta.get("action")
                or f"Рекомендация {len(suggestions) + 1}"
            )
            
            # Description: более полное описание
            description = (
                finding.get("description")
                or action
                or text
                or "Нет описания"
            )
            
            # Prompt: что отправить в AI при клике
            prompt = (
                meta.get("prompt")
                or text
                or action
                or label
            )
            
            # Извлекаем тип трансформации и актуальность
            transform_type = meta.get("type") or self._infer_type(text, refs)
            relevance = meta.get("relevance")
            if relevance is None:
                # Fallback: используем confidence как relevance
                relevance = confidence if confidence is not None else meta.get("confidence", 0.5)
            
            # Legacy поля для обратной совместимости
            category = meta.get("category") or transform_type
            
            # DEBUG: логируем если label оказался дефолтным
            if label.startswith("Рекомендация "):
                self.logger.warning(
                    f"⚠️ Suggestion #{len(suggestions) + 1} has default label. "
                    f"Finding data: text={text[:50] if text else 'EMPTY'}, "
                    f"action={action[:50] if action else 'EMPTY'}, "
                    f"title={finding.get('title', 'NONE')}"
                )

            suggestion = {
                "id": f"suggestion-{len(suggestions) + 1}",
                "label": label,
                "prompt": prompt,
                "type": transform_type,  # ← NEW: тип трансформации для цвета/иконки
                "relevance": float(relevance),  # ← NEW: актуальность 0.0-1.0
                "category": category,  # Legacy
                "confidence": confidence if confidence is not None else meta.get("confidence", 0.5),  # Legacy
                "description": description,
                "reasoning": meta.get("reasoning", ""),
            }
            suggestions.append(suggestion)

        # Сортировка по relevance (убывание), затем стабильно по label
        suggestions.sort(
            key=lambda s: (-float(s.get("relevance") or 0), (s.get("label") or "").lower())
        )
        top_suggestions = suggestions[:max_count]
        
        self.logger.info(
            f"📊 Formatted {len(suggestions)} suggestions, returning top {len(top_suggestions)} by relevance"
        )
        return top_suggestions

    @staticmethod
    def _is_visualization_suggestion(text: str) -> bool:
        """Проверяет, является ли рекомендация визуализацией (должна быть отфильтрована)."""
        text_lower = text.lower()
        viz_keywords = [
            "chart", "graph", "plot", "heatmap", "histogram",
            "график", "диаграмм", "гистограмм", "визуализ",
            "dashboard", "построить ", "scatter", "bar chart",
            "line chart", "pie chart", "кругов", "столбчат",
        ]
        return any(kw in text_lower for kw in viz_keywords)

    @staticmethod
    def _infer_type(text: str, refs: List[str]) -> str:
        """Определяет тип трансформации по тексту и ссылкам."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["фильтр", "filter", "отбор", "where", "выбра", "условие"]):
            return "filter"
        if any(w in text_lower for w in ["агрегат", "сумм", "среднее", "группир", "group", "agg", "count", "sum", "avg"]):
            return "aggregation"
        if any(w in text_lower for w in ["столбец", "column", "добавь", "вычисл", "расчёт", "growth", "rate", "процент"]):
            return "calculation"
        if any(w in text_lower for w in ["сортир", "sort", "ранж", "rank", "топ", "top", "order"]):
            return "sorting"
        if any(w in text_lower for w in ["очист", "clean", "пропуск", "null", "nan", "дубл", "duplic", "missing"]):
            return "cleaning"
        if any(w in text_lower for w in ["объедин", "join", "merge", "concat", "слия"]):
            return "merge"
        if any(w in text_lower for w in ["pivot", "unpivot", "melt", "транспон", "широк", "длинн", "reshape"]):
            return "reshape"
        return "calculation"  # Default fallback

    # ══════════════════════════════════════════════════════════════════
    #  Fallback
    # ══════════════════════════════════════════════════════════════════

    def _fallback_result(self, start_time: float) -> ControllerResult:
        """Возвращает fallback-подсказки при недоступности AI."""
        return ControllerResult(
            status="success",
            suggestions=list(FALLBACK_SUGGESTIONS),
            mode="transform_suggestions_fallback",
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={"fallback": True},
        )

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.time() - start_time) * 1000)
