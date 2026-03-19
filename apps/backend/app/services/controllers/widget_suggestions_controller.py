"""
WidgetSuggestionsController — Satellite Controller для подсказок по виджетам (V2).

Заменяет прямой вызов WidgetSuggestionAgent из route-handler'а:
- analyze_widget_suggestions → handle_request()

Аналогичен TransformSuggestionsController:
- NEW WIDGET — варианты типов визуализаций
- EXISTING WIDGET — улучшения, альтернативы, стилистические правки

См. docs/MULTI_AGENT_V2_CONCEPT.md → Phase 4.5
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .base_controller import BaseController, ControllerResult

logger = logging.getLogger("controller.widget_suggestions")

# Фоллбэк-подсказки (если AI недоступен)
# Формат должен совпадать со схемой Suggestion на фронтенде:
# {id, type, priority, title, description, prompt, reasoning?}
FALLBACK_WIDGET_SUGGESTIONS: List[Dict[str, Any]] = [
    {
        "id": "fallback-bar-chart",
        "type": "improvement",
        "viz_category": "bar",
        "priority": "high",
        "title": "Столбчатая диаграмма",
        "description": "Построить столбчатую диаграмму для сравнения значений по категориям",
        "prompt": "Построй столбчатую диаграмму",
        "reasoning": "Базовая рекомендация (AI недоступен)",
    },
    {
        "id": "fallback-table-view",
        "type": "alternative",
        "viz_category": "table",
        "priority": "high",
        "title": "Интерактивная таблица",
        "description": "Создать таблицу с сортировкой, поиском и пагинацией",
        "prompt": "Создай интерактивную таблицу с сортировкой и поиском",
        "reasoning": "Базовая рекомендация (AI недоступен)",
    },
    {
        "id": "fallback-pie-chart",
        "type": "improvement",
        "viz_category": "pie",
        "priority": "medium",
        "title": "Круговая диаграмма",
        "description": "Показать распределение долей по категориям",
        "prompt": "Построй круговую диаграмму с долями",
        "reasoning": "Базовая рекомендация (AI недоступен)",
    },
    {
        "id": "fallback-line-chart",
        "type": "alternative",
        "viz_category": "line",
        "priority": "medium",
        "title": "Линейный график",
        "description": "Показать тренды и динамику изменений во времени",
        "prompt": "Построй линейный график динамики",
        "reasoning": "Базовая рекомендация (AI недоступен)",
    },
    {
        "id": "fallback-kpi-cards",
        "type": "insight",
        "viz_category": "kpi",
        "priority": "medium",
        "title": "KPI-карточки",
        "description": "Показать ключевые метрики в виде карточек",
        "prompt": "Создай KPI-карточки с ключевыми метриками",
        "reasoning": "Базовая рекомендация (AI недоступен)",
    },
    {
        "id": "fallback-heatmap",
        "type": "alternative",
        "viz_category": "heatmap",
        "priority": "low",
        "title": "Тепловая карта",
        "description": "Визуализировать корреляции или распределение данных",
        "prompt": "Построй тепловую карту данных",
        "reasoning": "Базовая рекомендация (AI недоступен)",
    },
]


class WidgetSuggestionsController(BaseController):
    """
    Контроллер подсказок для виджетов.

    Вызывается из route ``POST /{id}/analyze-suggestions``.
    Формирует запрос к Orchestrator, извлекает ``findings``
    типа ``recommendation``, форматирует для UI.
    """

    controller_name = "widget_suggestions"

    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Генерирует подсказки по виджетам.

        Args:
            user_message: Автоматически формируемый запрос
            context: {
                "board_id": str,
                "user_id": str,
                "content_node_id": str,
                "content_data": dict,  # {tables: [], text: ""}
                "current_widget_code": str | None,
                "chat_history": list[dict],
                "max_suggestions": int,
            }

        Returns:
            ControllerResult с suggestions list.
        """
        ctx = context or {}
        start_time = time.time()

        board_id = ctx.get("board_id", "")
        user_id = ctx.get("user_id")
        content_data = ctx.get("content_data", {})
        current_widget_code = ctx.get("current_widget_code")
        chat_history = ctx.get("chat_history", [])
        max_suggestions = ctx.get("max_suggestions", 6)  # Show top 6 from 10 generated

        mode = "improve" if current_widget_code else "new"

        # Сформировать запрос
        enriched_request = self._build_suggestions_request(
            content_data=content_data,
            current_widget_code=current_widget_code,
            chat_history=chat_history,
            mode=mode,
        )

        # Формируем input_data_preview в стандартном формате для Planner и Analyst
        # content_data имеет формат {tables: [...], text: ""},
        # а агенты читают input_data_preview: {table_name: {columns, row_count, sample_rows}}
        input_data_preview: Dict[str, Any] = {}
        for table in content_data.get("tables", []):
            name = table.get("name", "df")
            raw_columns = table.get("columns", [])
            # Нормализуем колонки: [{name, type}] → ["name1", "name2", ...]
            # Planner использует ', '.join(columns) — нужны строки
            columns: List[str] = []
            for c in raw_columns:
                if isinstance(c, dict):
                    columns.append(c.get("name", str(c)))
                else:
                    columns.append(str(c))
            rows = table.get("rows", [])
            row_count = table.get("row_count", len(rows))
            input_data_preview[name] = {
                "columns": columns,
                "row_count": row_count,
                "sample_rows": rows[:20],
            }

        orchestrator_context = {
            "controller": self.controller_name,
            "mode": f"widget_suggestions_{mode}",
            "content_node_id": ctx.get("content_node_id"),
            "content_data": content_data,
            "input_data_preview": input_data_preview,  # Стандартный ключ для Planner/Analyst
            "existing_widget_code": current_widget_code,
            "chat_history": chat_history,
            "max_suggestions": max_suggestions,
        }

        # Вызвать Orchestrator
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
                for j, f in enumerate(payload.get("findings", [])[:3], 1):
                    if isinstance(f, dict):
                        logger.info(f"    Finding {j}: type={f.get('type')}, title={f.get('title', '')[:50]}")

        # Извлечь findings
        findings = self._extract_findings(results, finding_type="recommendation")
        logger.info(f"📊 Extracted {len(findings)} findings with type='recommendation'")

        if not findings:
            findings = self._extract_findings(results)
            logger.info(f"📊 Extracted {len(findings)} findings without type filter")

        if not findings:
            logger.warning("No findings from orchestrator, returning fallback")
            return self._fallback_result(start_time)

        suggestions = self._format_suggestions(findings, max_suggestions)

        return ControllerResult(
            status="success",
            suggestions=suggestions,
            session_id=orch_result.get("session_id"),
            mode=f"widget_suggestions_{mode}",
            execution_time_ms=self._elapsed_ms(start_time),
        )

    # ══════════════════════════════════════════════════════════════════
    #  Request building
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_suggestions_request(
        content_data: Dict[str, Any],
        current_widget_code: Optional[str],
        chat_history: List[Dict[str, Any]],
        mode: str,
    ) -> str:
        """Формирует текст запроса для Orchestrator."""
        tables = content_data.get("tables", [])
        text = content_data.get("text", "")

        if mode == "improve":
            request = (
                "Предложи улучшения для существующего виджета визуализации.\n\n"
                f"Текущий код:\n```html\n{current_widget_code}\n```\n\n"
            )
        else:
            request = "Предложи варианты визуализации для данных.\n\n"

        if tables:
            request += "Доступные данные:\n"
            for table in tables[:3]:
                name = table.get("name", "таблица")
                columns = table.get("columns", [])
                row_count = table.get("row_count", len(table.get("rows", [])))
                rows = table.get("rows", [])
                # Handle columns as dicts or strings
                col_names = columns[:15] if isinstance(columns, list) else []
                if col_names and isinstance(col_names[0], dict):
                    col_names = [c.get("name", "") for c in col_names]
                col_str = ", ".join(col_names) if col_names else "(нет колонок)"
                request += f"  • Таблица '{name}': {row_count} строк, колонки [{col_str}]\n"
                # Добавляем примеры данных для лучшего контекста
                if rows:
                    request += f"    Примеры строк (первые {min(3, len(rows))}):\n"
                    for row in rows[:3]:
                        row_str = ", ".join(
                            f"{k}={v}" for k, v in (row.items() if isinstance(row, dict) else [])
                        )
                        if row_str:
                            request += f"    {row_str}\n"

        if text:
            request += f"  • Текстовые данные: {len(text)} символов\n"

        # Мало строк — иначе модель часто выдаёт 10 «универсальных» идей (heatmap, map…)
        if tables:
            max_rows = max(
                int(t.get("row_count") or len(t.get("rows") or []))
                for t in tables[:3]
            )
            if max_rows <= 5:
                request += (
                    "\n⚠️ Данных мало (≤5 строк в основной таблице): в первую очередь предлагай "
                    "реалистичные варианты — столбчатая/круговая диаграмма по категориям, "
                    "простая таблица, KPI-карточки. Не рекомендуй heatmap, корреляции или карту "
                    "без геоданных и без достаточного числа наблюдений.\n"
                )

        if chat_history:
            recent = chat_history[-3:]
            request += "\nИстория чата:\n"
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]
                request += f"  [{role}]: {content}\n"

        request += (
            "\n🎯 ЗАДАЧА: Проанализируй данные и предложи 10 разнообразных вариантов ВИЗУАЛИЗАЦИИ:\n"
            "  • chart — графики (столбчатый, линейный, pie, scatter, heatmap)\n"
            "  • table — интерактивные таблицы (с сортировкой, фильтрами)\n"
            "  • kpi — KPI-карточки, метрики, scorecard\n"
            "  • map — карты и геовизуализации\n\n"
            "⚠️ ОГРАНИЧЕНИЯ:\n"
            "  • Покрой РАЗНЫЕ типы визуализаций (минимум 3-4 разных категории)\n"
            "  • Оцени актуальность каждой рекомендации (confidence 0.0-1.0)\n"
            "  • Формат findings с type='recommendation', включи: тип визуализации, описание, "
            "metadata с category, confidence, prompt.\n"
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
        Конвертирует findings в формат UI-подсказок (Suggestion schema).

        Генерируем 10 рекомендаций, возвращаем top 6 по confidence.
        """
        suggestions: List[Dict[str, Any]] = []

        # Обрабатываем ВСЕ findings (до 10), потом отфильтруем топ-N
        for i, finding in enumerate(findings):
            # Finding fields: text, action, confidence, refs, severity
            text = finding.get("text", "")
            action = finding.get("action", "")
            confidence = finding.get("confidence")
            
            # Также поддерживаем legacy формат (title, description, metadata)
            # NB: используем `or {}` т.к. finding может содержать {"metadata": None}
            meta = finding.get("metadata") or {}

            # Confidence: используем первое доступное значение
            if confidence is None:
                confidence = meta.get("confidence", 0.5)

            title = finding.get("title") or text or f"Визуализация {len(suggestions) + 1}"
            description = finding.get("description") or action or text
            prompt = (
                meta.get("prompt")
                or finding.get("description")
                or text
            )
            category = (
                meta.get("category")
                or self._infer_widget_category(text)
            )
            viz_category = self._normalize_viz_category(meta, text, category)

            # Map category to SuggestionType enum
            suggestion_type = self._category_to_suggestion_type(category, text)
            
            # Map confidence to priority
            priority = "high" if confidence >= 0.8 else "medium" if confidence >= 0.5 else "low"
            
            # Truncate title if needed
            if len(title) > 50:
                title = title[:47] + "..."

            # DEBUG: логируем если title оказался дефолтным
            if title.startswith("Визуализация "):
                logger.warning(
                    f"⚠️ Suggestion #{len(suggestions) + 1} has default title. "
                    f"Finding data: text={text[:50] if text else 'EMPTY'}, "
                    f"action={action[:50] if action else 'EMPTY'}, "
                    f"title={finding.get('title', 'NONE')}"
                )
            
            suggestion = {
                "id": f"widget-suggestion-{len(suggestions) + 1}",
                "type": suggestion_type,
                "viz_category": viz_category,
                "priority": priority,
                "title": title,
                "description": description,
                "prompt": prompt,
                "confidence": float(confidence),
                "reasoning": meta.get("reasoning", ""),
            }
            suggestions.append(suggestion)
        
        # Сортировка по confidence (убывание), затем берем top N
        suggestions.sort(key=lambda s: s.get("confidence", 0), reverse=True)
        top_suggestions = suggestions[:max_count]

        logger.info(
            f"📊 Formatted {len(suggestions)} suggestions, returning top {len(top_suggestions)} by confidence"
        )
        return top_suggestions
    
    @staticmethod
    def _category_to_suggestion_type(category: str, text: str) -> str:
        """Maps widget category to SuggestionType enum value."""
        category_lower = category.lower()
        text_lower = text.lower()
        
        # Check for library-specific suggestions
        if any(w in text_lower for w in ["библиотек", "library", "d3", "plotly", "chart.js", "echarts"]):
            return "library"
        
        # Check for style suggestions
        if any(w in text_lower for w in ["стиль", "style", "цвет", "color", "шрифт", "font", "размер", "size"]):
            return "style"
        
        # Check for alternative visualizations
        if any(w in text_lower for w in ["альтернатив", "alternative", "вместо", "instead", "другой", "another"]):
            return "alternative"
        
        # Check for insights
        if any(w in text_lower for w in ["инсайт", "insight", "обнаружен", "discover", "интересн", "interest"]):
            return "insight"
        
        # Default to improvement
        return "improvement"

    @staticmethod
    def _infer_widget_category(text: str) -> str:
        """Определяет категорию виджета по тексту."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["таблиц", "table", "grid", "сводн"]):
            return "table"
        if any(w in text_lower for w in ["карт", "map", "geo"]):
            return "map"
        if any(w in text_lower for w in ["kpi", "метрик", "показател", "индикатор", "scorecard"]):
            return "kpi"
        if any(w in text_lower for w in ["pie", "круг", "долев"]):
            return "pie"
        if any(w in text_lower for w in ["line", "линейн", "динамик", "тренд", "temporal"]):
            return "line"
        if any(w in text_lower for w in ["bar", "гистограмм", "столбч"]):
            return "bar"
        if any(w in text_lower for w in ["scatter", "точечн", "корреляц"]):
            return "scatter"
        if any(w in text_lower for w in ["heatmap", "теплов"]):
            return "heatmap"
        if any(w in text_lower for w in ["воронк", "funnel"]):
            return "funnel"
        if any(w in text_lower for w in ["radar", "радар", "паутин"]):
            return "radar"
        if any(w in text_lower for w in ["treemap", "древовидн", "иерарх"]):
            return "treemap"
        if any(w in text_lower for w in ["gauge", "спидометр", "полукруг"]):
            return "gauge"
        return "chart"

    @staticmethod
    def _normalize_viz_category(
        meta: Dict[str, Any], text: str, category_guess: str
    ) -> str:
        """Ключ типа визуализации для UI (иконка + цвет бейджа)."""
        t = (meta.get("type") or "").lower().replace("-", "_")
        if "histogram" in t or "bar" in t:
            return "bar"
        if "line" in t:
            return "line"
        if "pie" in t or "doughnut" in t:
            return "pie"
        if "scatter" in t:
            return "scatter"
        if "heatmap" in t or t == "heat_map":
            return "heatmap"
        if "table" in t:
            return "table"
        if "funnel" in t:
            return "funnel"
        if "treemap" in t or "tree_map" in t:
            return "treemap"
        if "radar" in t:
            return "radar"
        if "gauge" in t:
            return "gauge"
        if "map" in t or "geo" in t:
            return "map"
        if "kpi" in t or "metric" in t or "scorecard" in t:
            return "kpi"
        cat = (meta.get("category") or "").lower()
        if cat == "table":
            return "table"
        if cat == "kpi":
            return "kpi"
        if cat == "map":
            return "map"
        if cat == "chart":
            return WidgetSuggestionsController._infer_widget_category(text)
        return WidgetSuggestionsController._infer_widget_category(
            text or category_guess or ""
        )

    # ══════════════════════════════════════════════════════════════════
    #  Fallback
    # ══════════════════════════════════════════════════════════════════

    def _fallback_result(self, start_time: float) -> ControllerResult:
        """Возвращает fallback-подсказки при недоступности AI."""
        return ControllerResult(
            status="success",
            suggestions=list(FALLBACK_WIDGET_SUGGESTIONS),
            mode="widget_suggestions_fallback",
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={"fallback": True},
        )

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.time() - start_time) * 1000)
