"""
TransformationController — Satellite Controller для Python-трансформаций (V2).

Заменяет прямые вызовы agents из route-handler'ов:
- preview_transformation   → handle_preview()
- iterative_transformation → handle_iterative()
- transform_multiagent     → handle_request()

Workflow:
1. Упаковка входных DataFrame → ContentTable
2. Обогащение запроса контекстом данных
3. Вызов orchestrator.process_request()
4. Извлечение code_blocks[purpose="transformation"]
5. Исполнение через PythonExecutor
6. При ошибке — повторный запрос с контекстом ошибки
7. Discussion mode: возврат narrative.text

См. docs/MULTI_AGENT_V2_CONCEPT.md → Phase 4.2
"""

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.services.executors.python_executor import python_executor

from .base_controller import BaseController, ControllerResult

logger = logging.getLogger("controller.transformation")

# Максимум повторных попыток при ошибке исполнения кода
MAX_ERROR_RETRIES = 2

# Лимит строк для preview
PREVIEW_ROW_LIMIT = 50


class TransformationController(BaseController):
    """
    Контроллер трансформаций данных.

    Вызывается из route-handler'ов ``/transform/*`` endpoints.
    Инкапсулирует всю логику подготовки контекста, вызова
    Orchestrator V2 и пост-обработки результата.
    """

    controller_name = "transformation"

    # ══════════════════════════════════════════════════════════════════
    #  Public interface
    # ══════════════════════════════════════════════════════════════════

    async def process_request(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ControllerResult:
        """
        Единый entry-point для трансформации.

        Обрабатывает запрос, автоматически определяя режим
        (TRANSFORMATION или DISCUSSION) на основе ответа ядра.

        Args:
            user_message: Запрос пользователя ("Отфильтруй amount > 100")
            context: {
                "board_id": str,
                "user_id": str,
                "session_id": str | None,
                "input_tables": list[dict],  # ContentNode tables
                "text_content": str | None,  # Raw text content
                "existing_code": str | None,
                "chat_history": list[dict],
                "selected_node_ids": list[str],
                "skip_execution": bool,  # True = preview only (no execute)
            }

        Returns:
            ControllerResult с code + preview_data или narrative.
        """
        ctx = context or {}
        start_time = time.time()

        board_id = ctx.get("board_id", "")
        user_id = ctx.get("user_id")
        session_id = ctx.get("session_id")
        skip_execution = ctx.get("skip_execution", False)

        # 1. Подготовить входные данные
        input_data, enriched_request = await self._prepare_request(
            user_message=user_message,
            input_tables=ctx.get("input_tables", []),
            text_content=ctx.get("text_content"),
            existing_code=ctx.get("existing_code"),
            selected_node_ids=ctx.get("selected_node_ids", []),
            user_id=user_id,
            ctx=ctx,  # Передаём полный контекст
        )

        orchestrator_context = self._build_orchestrator_context(
            ctx,
            input_data,
            user_message=user_message,
        )

        # Изменение #6: input_data передаётся отдельно через execution_context
        execution_context = {"input_data": input_data} if input_data else None

        # 2. Вызвать Orchestrator
        orch_result = await self._call_orchestrator(
            user_request=enriched_request,
            board_id=board_id,
            user_id=user_id,
            session_id=session_id,
            context=orchestrator_context,
            execution_context=execution_context,
        )
        multi_agent_error = self._validate_multi_agent_result(orch_result)
        if multi_agent_error:
            return self._error_result(
                message=multi_agent_error,
                execution_time_ms=self._elapsed_ms(start_time),
            )

        if orch_result.get("status") == "error":
            return self._error_result(
                message=orch_result.get("error", "Orchestrator error"),
                execution_time_ms=self._elapsed_ms(start_time),
            )

        results: Dict[str, Any] = orch_result.get("results", {})
        returned_session = orch_result.get("session_id", session_id)

        # 3. Определить режим ответа
        code_blocks = self._extract_code_blocks(results, purpose="transformation")

        if not code_blocks:
            # Discussion mode — вернуть narrative
            return self._build_discussion_result(
                results=results,
                session_id=returned_session,
                plan=orch_result.get("plan"),
                start_time=start_time,
            )

        # 4. Transformation mode — извлечь код
        # FIX: Берём ПОСЛЕДНИЙ code_block — после replan в raw_results
        # накапливаются результаты всех попыток (transform_codex, transform_codex_2, ...),
        # и первый блок может быть устаревшим/ошибочным кодом из первой попытки.
        best_block = code_blocks[-1]
        code = best_block.get("code", "")
        description = best_block.get("description", "AI-generated transformation")

        if not code.strip():
            return self._error_result(
                message="Агент вернул пустой блок кода",
                execution_time_ms=self._elapsed_ms(start_time),
            )

        if skip_execution:
            # Preview only — вернуть код без исполнения
            return ControllerResult(
                status="success",
                code=code,
                code_language="python",
                code_description=description,
                validation=self._extract_validation(results),
                session_id=returned_session,
                plan=orch_result.get("plan"),
                mode="transformation",
                execution_time_ms=self._elapsed_ms(start_time),
            )

        # 5. Исполнить код через PythonExecutor
        exec_result, preview_data = await self._execute_code(
            code=code,
            input_data=input_data,
            user_id=user_id,
        )

        if exec_result.success:
            self.logger.info(f"✅ Code executed successfully on first attempt")
            
            self.logger.info(f"📤 Returning code ({len(code)} chars): {code[:100]}...")
            return ControllerResult(
                status="success",
                code=code,
                code_language="python",
                code_description=description,
                preview_data=preview_data,
                validation=self._extract_validation(results),
                session_id=returned_session,
                plan=orch_result.get("plan"),
                mode="transformation",
                execution_time_ms=self._elapsed_ms(start_time),
            )

        # 6. Ошибка исполнения — retry с контекстом ошибки
        # FIX: Если Orchestrator уже делал replan (QualityGate нашёл ошибку,
        # planner перепланировал, codex перегенерировал) — controller retry
        # избыточен и только тратит LLM-вызовы. Пропускаем retry.
        plan_data = orch_result.get("plan", {})
        orch_replan_count = plan_data.get("replan_count", 0) if isinstance(plan_data, dict) else 0
        
        if orch_replan_count > 0:
            self.logger.warning(
                f"⚠️ Orchestrator already did {orch_replan_count} replan(s), "
                f"skipping controller retry. Error: {exec_result.error}"
            )
            return ControllerResult(
                status="error",
                error=f"Код не прошёл исполнение после {orch_replan_count} replan(ов) оркестратора: {exec_result.error}",
                code=code,
                code_language="python",
                session_id=returned_session,
                plan=plan_data,
                mode="transformation",
                execution_time_ms=self._elapsed_ms(start_time),
                metadata={"orchestrator_replans": orch_replan_count},
            )
        
        return await self._handle_execution_error(
            original_code=code,
            error_message=exec_result.error or "Unknown execution error",
            user_message=user_message,
            input_data=input_data,
            board_id=board_id,
            user_id=user_id,
            session_id=returned_session,
            orchestrator_context=orchestrator_context,
            start_time=start_time,
        )

    # ══════════════════════════════════════════════════════════════════
    #  Data preparation
    # ══════════════════════════════════════════════════════════════════

    async def _prepare_request(
        self,
        user_message: str,
        input_tables: List[Dict[str, Any]],
        text_content: Optional[str],
        existing_code: Optional[str],
        selected_node_ids: List[str],
        user_id: Optional[str] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Подготавливает входные данные и обогащённый запрос.
        
        ВАЖНО: Input data ВСЕГДА = оригинальные таблицы.
        existing_code передаётся в orchestrator context как РЕФЕРЕНС для LLM.

        Returns:
            (input_data dict для PythonExecutor, enriched_request str)
        """
        # Use pre-built full DataFrames if available, otherwise build from input_tables
        input_data: Dict[str, Any] = ctx.get("input_data", {}) if ctx else {}
        data_description_parts: List[str] = []

        # Build DataFrames from input_tables only if not pre-provided
        for table in input_tables:
            table_name = table.get("name", "таблица")
            columns = table.get("columns", [])
            row_count = table.get("row_count", len(table.get("rows", [])))

            if table_name not in input_data:
                # No pre-built DataFrame — create from table dict (may be truncated)
                try:
                    df = python_executor.table_dict_to_dataframe(table)
                    input_data[table_name] = df
                except Exception as e:
                    logger.warning(f"Failed to convert table '{table_name}' to DataFrame: {e}")
                    continue

            col_names = ", ".join(
                [c["name"] for c in columns]
            ) if columns else "(no columns)"
            data_description_parts.append(
                f"  • Таблица '{table_name}': {len(columns)} колонок, {row_count} строк\n"
                f"    Колонки: {col_names}"
            )

        # Text content (если нет таблиц)
        if not input_data and text_content and text_content.strip():
            input_data["text"] = text_content.strip()
            data_description_parts.append(
                f"  • Текст: {len(text_content)} символов"
            )

        # Формируем обогащённый запрос
        content_node_id = str((ctx or {}).get("content_node_id") or "").strip()
        selected_ids = [
            str(item).strip() for item in (selected_node_ids or []) if str(item).strip()
        ]
        if content_node_id and content_node_id not in selected_ids:
            selected_ids.insert(0, content_node_id)
        if not content_node_id and selected_ids:
            content_node_id = selected_ids[0]
        scope_header = (
            "\nКОНТРАКТ TRANSFORMATIONCONTROLLER:\n"
            "- Цель: сгенерировать Python/pandas-код трансформации по существующим таблицам ContentNode.\n"
            f"- Primary ContentNode ID: {content_node_id or 'unknown'}\n"
            f"- Allowed ContentNode IDs: {', '.join(selected_ids) if selected_ids else (content_node_id or 'unknown')}\n"
            "- Используй ТОЛЬКО данные этих ContentNode.\n"
            "- Не используй внешние источники, если это не запрошено явно пользователем.\n"
            "- Если не хватает данных таблиц — запрашивай через readTableListFromContentNodes (список и table_id), "
            "при необходимости строк — readTableData с jsonDecl.table_id из ответа первого тула.\n"
        )
        # Определяем, является ли запрос дискуссионным (анализ без кода)
        discussion_keywords = [
            "объясни", "расскажи", "опиши", "проанализируй", "какие тренды",
            "не генерируй код", "без кода", "только анализ", "просто проанализируй",
            "что означа", "почему", "в чём причин", "какие выводы",
        ]
        is_discussion = any(kw in user_message.lower() for kw in discussion_keywords)

        if is_discussion:
            enriched = (
                f"{user_message}\n\n"
                f"Доступные данные:\n"
            )
        else:
            enriched = (
                f"Сгенерируй Python код для трансформации данных.\n\n"
                f"Требуемая трансформация: {user_message}\n\n"
                f"ТРЕБОВАНИЯ К КОДУ:\n"
                f"  • ✅ ОБЯЗАТЕЛЬНО: Используй ОПИСАТЕЛЬНЫЕ, ИНФОРМАТИВНЫЕ имена переменных с префиксом 'df_'\n"
                f"    Примеры: df_sales_by_brand, df_top_10_products, df_revenue_monthly, df_customer_segments\n"
                f"  • ❌ ЗАПРЕЩЕНО: Generic имена типа df_result, df_output, df_final, df_data\n"
                f"  • Имя должно отражать СОДЕРЖАНИЕ таблицы, а не факт что это результат\n"
                f"\n"
                f"  🚫 КРИТИЧЕСКИ ВАЖНО — НЕ СОЗДАВАЙ ДУБЛИКАТЫ:\n"
                f"  • Если у тебя уже есть df_sales_by_brand с финальным результатом — это и есть твой ответ\n"
                f"  • ❌ НЕ добавляй df_result = df_sales_by_brand — это создаст ДВЕ одинаковые таблицы!\n"
                f"  • ❌ НЕ добавляй df_final = df_aggregated — пользователь увидит дубликаты!\n"
                f"  • ❌ НЕ добавляй df_output = df_filtered — одна таблица дважды!\n"
                f"  • ✅ ПРАВИЛЬНО: создай ОДНУ таблицу с осмысленным именем и на этом останови\n"
                f"\n"
                f"  • Одна таблица: одно осмысленное имя (df_aggregated_sales)\n"
                f"  • Несколько таблиц OK только если это РАЗНЫЕ данные (df_top_10 + df_bottom_10)\n"
                f"  • Промежуточные вычисления: обычные переменные (grouped = ...) или цепочки методов\n"
                f"  • НЕ включай исходные таблицы (df, df1, df2) в результат\n"
                f"  • Добавь краткие комментарии к ключевым операциям\n\n"
                f"Доступные данные:\n"
            )
        enriched += scope_header
        enriched += "\n".join(data_description_parts) if data_description_parts else "  (нет данных)"

        # Для chain transformations добавляем историю и existing_code как референс
        if existing_code:
            history_summary = ""
            if ctx and ctx.get("chat_history"):
                user_requests = [msg.get("content", "")[:100] for msg in ctx["chat_history"] if msg.get("role") == "user"]
                if user_requests:
                    history_summary = "\n\nИстория запросов:\n" + "\n".join(f"  {i+1}. {req}" for i, req in enumerate(user_requests))
            
            enriched += (
                f"{history_summary}\n\n"
                f"📝 EXISTING CODE (for reference):\n```python\n{existing_code}\n```\n\n"
                f"💡 NEW REQUEST: {user_message}\n"
            )

        return input_data, enriched

    def _build_orchestrator_context(
        self,
        ctx: Dict[str, Any],
        input_data: Dict[str, Any],
        *,
        user_message: str,
    ) -> Dict[str, Any]:
        """Строит context для Orchestrator.process_request()."""
        orch_ctx: Dict[str, Any] = {
            "controller": self.controller_name,
            "mode": "transformation",
            "controller_user_request": str(user_message or "").strip(),
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
        orch_ctx["transformation_scope"] = {
            "primary_content_node_id": primary_content_node_id,
            "selected_node_ids": selected_ids,
            "local_content_only": True,
            "prefer_tools_for_tables": True,
            "disallow_external_sources_unless_explicit": True,
        }
        # Не удалять input_data_preview при MULTI_AGENT_FORCE_TOOL_DATA_ACCESS (см. context_selection).
        orch_ctx["keep_tabular_context_in_prompt"] = True
        if selected_ids:
            # Unified array contract for tool-aware agents.
            orch_ctx["content_node_ids"] = selected_ids
            orch_ctx["contentNodeIds"] = selected_ids

        # Pass through relevant context keys
        for key in (
            "content_node_id",
            "selected_node_ids",
            "content_nodes_data",
            "existing_code",
            "chat_history",
            "transformation_id",
            "_progress_callback",
            "_enable_plan_progress",
        ):
            if key in ctx:
                orch_ctx[key] = ctx[key]

        # Input data preview (schema только, не полные данные)
        input_preview: Dict[str, Any] = {}
        for name, val in input_data.items():
            if isinstance(val, pd.DataFrame):
                input_preview[name] = {
                    "columns": list(val.columns),
                    "dtypes": {col: str(dtype) for col, dtype in val.dtypes.items()},
                    "row_count": len(val),
                    "sample_rows": val.head(20).to_dict("records"),  # Увеличено с 5 до 20 для лучшего понимания агентами
                }
        if input_preview:
            orch_ctx["input_data_preview"] = input_preview
        
        # Изменение #6: input_data передаётся через execution_context, не в orch_ctx
        # см. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md

        return orch_ctx

    # ══════════════════════════════════════════════════════════════════
    #  Code execution
    # ══════════════════════════════════════════════════════════════════

    async def _execute_code(
        self,
        code: str,
        input_data: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """
        Исполняет код через PythonExecutor и строит preview_data.

        Returns:
            (ExecutionResult, preview_data dict | None)
        """
        # Изменение #6: auth_token убран (агенты внутри backend, не нужен)
        exec_result = await python_executor.execute_transformation(
            code=code,
            input_data=input_data,
            user_id=user_id,
        )

        if not exec_result.success:
            return exec_result, None

        preview_tables = self._build_preview_tables(exec_result.result_dfs)
        preview_data = {
            "tables": preview_tables,
            "execution_time_ms": exec_result.execution_time_ms,
        }
        return exec_result, preview_data

    @staticmethod
    def _build_preview_tables(
        result_dfs: Dict[str, "pd.DataFrame"],
    ) -> List[Dict[str, Any]]:
        """Конвертирует result DataFrames в preview table dicts.
        
        ВАЖНО: result_dfs содержит ТОЛЬКО трансформированные таблицы (с префиксом df_).
        Исходные таблицы (df, df1, df2) НЕ попадают сюда - это гарантируется PythonExecutor.
        """
        tables: List[Dict[str, Any]] = []
        for var_name, df in result_dfs.items():
            if not hasattr(df, "to_dict"):
                continue
            row_count = len(df)
            preview_df = df.head(PREVIEW_ROW_LIMIT)
            table_dict = python_executor.dataframe_to_table_dict(
                df=preview_df,
                table_name=var_name,
            )
            table_dict["row_count"] = row_count
            table_dict["preview_row_count"] = len(preview_df)
            tables.append(table_dict)
        return tables

    # ══════════════════════════════════════════════════════════════════
    #  Error retry
    # ══════════════════════════════════════════════════════════════════

    async def _handle_execution_error(
        self,
        original_code: str,
        error_message: str,
        user_message: str,
        input_data: Dict[str, Any],
        board_id: str,
        user_id: Optional[str],
        session_id: Optional[str],
        orchestrator_context: Dict[str, Any],
        start_time: float,
    ) -> ControllerResult:
        """
        Обрабатывает ошибку исполнения: повторно отправляет в Orchestrator
        с контекстом ошибки (заменяет legacy ErrorAnalyzerAgent).

        Attempts up to MAX_ERROR_RETRIES before giving up.
        """
        last_code = original_code
        last_error = error_message

        for attempt in range(1, MAX_ERROR_RETRIES + 1):
            self.logger.warning(
                f"Execution error (attempt {attempt}/{MAX_ERROR_RETRIES}): {last_error}"
            )

            # Добавить подсказки для типичных ошибок pandas
            error_hints = ""
            if "Cannot subset columns" in last_error or "do not exist" in last_error:
                error_hints = (
                    "\n⚠️ ТИПИЧНАЯ ОШИБКА: неправильный синтаксис groupby().agg()\n"
                    "❌ НЕПРАВИЛЬНО: df.groupby('x').agg({'new_name': 'sum'})  ← 'new_name' не существует\n"
                    "✅ ПРАВИЛЬНО:    df.groupby('x').agg({'column_name': 'sum'})  ← используй СУЩЕСТВУЮЩИЕ названия колонок\n"
                    "✅ ПРАВИЛЬНО:    df.groupby('x').agg(new_name=('column_name', 'sum'))  ← named aggregation\n"
                )
            elif "tuple" in last_error.lower() and "list" in last_error.lower():
                error_hints = (
                    "\n⚠️ ТИПИЧНАЯ ОШИБКА: используй список вместо tuple\n"
                    "❌ НЕПРАВИЛЬНО: df['col1', 'col2']  ← это tuple\n"
                    "✅ ПРАВИЛЬНО:    df[['col1', 'col2']]  ← это список колонок\n"
                )

            error_request = (
                f"Исправь ошибку в Python коде трансформации.\n\n"
                f"Исходный запрос: {user_message}\n\n"
                f"Код с ошибкой:\n```python\n{last_code}\n```\n\n"
                f"Ошибка при исполнении:\n```\n{last_error}\n```"
                f"{error_hints}\n\n"
                f"ТРЕБОВАНИЯ К ИСПРАВЛЕННОМУ КОДУ:\n"
                f"  • ✅ Используй ОПИСАТЕЛЬНЫЕ имена переменных: df_sales_by_brand, df_top_products, df_monthly_revenue\n"
                f"  • ❌ НЕ используй generic имена: df_result, df_output, df_final\n"
                f"  • 🚫 КРИТИЧЕСКИ ВАЖНО: НЕ создавай дубликаты:\n"
                f"     ❌ df_result = df_sales_by_brand — создаёт ДВЕ одинаковые таблицы!\n"
                f"     ✅ Используй ОДНУ таблицу с осмысленным именем: df_sales_by_brand\n"
                f"  • Имя должно отражать содержание данных\n\n"
                f"Сгенерируй исправленный код."
            )

            error_ctx = {
                **orchestrator_context,
                "error_retry": True,
                "attempt": attempt,
                "previous_error": last_error,
                "previous_code": last_code,
            }

            orch_result = await self._call_orchestrator(
                user_request=error_request,
                board_id=board_id,
                user_id=user_id,
                session_id=session_id,
                context=error_ctx,
                skip_validation=True,  # Быстрый retry без QualityGate
            )
            if self._validate_multi_agent_result(orch_result):
                continue

            if orch_result.get("status") == "error":
                continue

            results = orch_result.get("results", {})
            code_blocks = self._extract_code_blocks(results, purpose="transformation")

            if not code_blocks:
                continue

            fixed_code = code_blocks[-1].get("code", "")
            if not fixed_code.strip():
                continue

            exec_result, preview_data = await self._execute_code(
                code=fixed_code,
                input_data=input_data,
                user_id=user_id,
            )

            if exec_result.success:
                self.logger.info(f"Error fixed on retry attempt {attempt}")
                
                self.logger.info(f"📤 Returning FIXED code ({len(fixed_code)} chars): {fixed_code[:100]}...")
                return ControllerResult(
                    status="success",
                    code=fixed_code,
                    code_language="python",
                    code_description="AI-fixed transformation (auto-retry)",
                    preview_data=preview_data,
                    session_id=session_id,
                    mode="transformation",
                    execution_time_ms=self._elapsed_ms(start_time),
                    metadata={"error_retries": attempt},
                )

            # Обновить для следующей попытки
            last_code = fixed_code
            last_error = exec_result.error or "Unknown error"

        # Все попытки исчерпаны — вернуть последний код + ошибку
        return ControllerResult(
            status="error",
            error=f"Код не прошёл исполнение после {MAX_ERROR_RETRIES} попыток: {last_error}",
            code=last_code,
            code_language="python",
            session_id=session_id,
            mode="transformation",
            execution_time_ms=self._elapsed_ms(start_time),
            metadata={"error_retries": MAX_ERROR_RETRIES},
        )

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
        """Формирует ControllerResult для discussion mode (без кода)."""
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
    #  Utilities
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        """Вычисляет elapsed time в миллисекундах."""
        return int((time.time() - start_time) * 1000)

    @staticmethod
    def _validate_multi_agent_result(orch_result: Any) -> Optional[str]:
        """
        Ensure TransformationController works strictly through Multi-Agent Orchestrator.
        """
        if not isinstance(orch_result, dict):
            return "TransformationController expects multi-agent orchestrator response (dict)"
        if orch_result.get("status") == "error":
            return None
        if "plan" not in orch_result or "results" not in orch_result:
            return (
                "TransformationController requires multi-agent pipeline result "
                "(missing 'plan' or 'results')."
            )
        if not isinstance(orch_result.get("results"), dict):
            return (
                "TransformationController requires multi-agent pipeline result "
                "with dict 'results'."
            )
        return None

    @staticmethod
    def _extract_output_variables(code: str) -> set:
        """
        Извлекает все переменные с префиксом df_ из Python кода.
        
        Args:
            code: Python код для анализа
            
        Returns:
            Множество имён переменных (например, {'df_sales', 'df_result'})
        """
        if not code:
            return set()
        
        # Ищем присваивания: df_variable = ...
        pattern = r'\b(df_\w+)\s*='
        matches = re.findall(pattern, code)
        return set(matches)

    @staticmethod
    def _extract_column_names(code: str) -> set:
        """
        Извлекает имена колонок, созданных/переименованных в коде.
        
        Args:
            code: Python код для анализа
            
        Returns:
            Множество имён колонок (например, {'total_revenue', 'avg_price'})
        """
        if not code:
            return set()
        
        columns = set()
        
        # Паттерн 1: df.columns = ['col1', 'col2', ...]
        # Извлекаем все строковые литералы из .columns = [...]
        columns_assign = re.findall(r'\.columns\s*=\s*\[([^\]]+)\]', code)
        for match in columns_assign:
            # Извлекаем все строки в одинарных или двойных кавычках
            cols = re.findall(r'["\']([^"\' ]+)["\']', match)
            columns.update(cols)
        
        # Паттерн 2: df.rename(columns={'old': 'new', ...}) или df.rename(columns={...})
        rename_matches = re.findall(r'\.rename\s*\([^)]*columns\s*=\s*\{([^}]+)\}', code, re.DOTALL)
        for match in rename_matches:
            # Извлекаем новые имена (значения после :)
            new_cols = re.findall(r':\s*["\']([^"\' ]+)["\']', match)
            columns.update(new_cols)
        
        # Паттерн 3: df.assign(new_col=..., another_col=...)
        assign_matches = re.findall(r'\.assign\s*\(([^)]+)\)', code)
        for match in assign_matches:
            # Извлекаем имена параметров (до =)
            new_cols = re.findall(r'(\w+)\s*=', match)
            columns.update(new_cols)
        
        return columns

    @staticmethod
    def _check_code_dependencies(existing_code: Optional[str], new_code: str) -> Optional[str]:
        """
        Проверяет тип зависимости между existing_code и new_code.
        
        Args:
            existing_code: Код предыдущей трансформации
            new_code: Новый сгенерированный код
            
        Returns:
            "variable_reference" - если new_code явно ссылается на переменные из existing_code
            "column_reference" - если new_code использует колонки, созданные в existing_code
            None - если зависимостей нет (независимая трансформация)
        """
        if not existing_code or not new_code:
            return None
        
        # ── Проверка 1: Переменные df_* (OPTION A - интеграция) ──
        output_vars = TransformationController._extract_output_variables(existing_code)
        
        used_vars = []
        if output_vars:
            logger.debug(f"🔍 Found {len(output_vars)} output variables in existing_code: {output_vars}")
            
            # Проверяем, используются ли эти переменные в new_code
            for var in output_vars:
                # Ищем использование переменной (не присваивание)
                if re.search(rf'\b{re.escape(var)}\b(?!\s*=)', new_code):
                    used_vars.append(var)
        
        if used_vars:
            logger.info(f"🔗 New code references variables from existing_code: {used_vars}")
            logger.info(f"   → LLM chose OPTION A (integrated code)")
            return "variable_reference"
        
        # ── Проверка 2: Колонки (OPTION B - инкрементальный код с мостом) ──
        created_columns = TransformationController._extract_column_names(existing_code)
        
        used_columns = []
        if created_columns:
            logger.debug(f"🔍 Found {len(created_columns)} columns created in existing_code: {created_columns}")
            
            # Проверяем, обращается ли new_code к этим колонкам
            for col in created_columns:
                # Паттерны использования колонок:
                # - ['column_name'] или ["column_name"]
                # - .column_name (доступ через атрибут)
                # - 'column_name' в контексте операций над df
                patterns = [
                    rf"\[['\"]{re.escape(col)}['\"]\]",  # df['col'] или df["col"]
                    rf"\.{re.escape(col)}\b",  # df.col
                    rf"['\"]{re.escape(col)}['\"]\s*[,\)]",  # 'col', или 'col')
                ]
                
                for pattern in patterns:
                    if re.search(pattern, new_code):
                        used_columns.append(col)
                        break
        
        if used_columns:
            logger.info(f"🔗 New code uses columns from existing_code: {used_columns}")
            logger.info(f"   → LLM chose OPTION B (incremental with bridge needed)")
            return "column_reference"
        
        logger.debug(f"🆕 New code does not depend on existing_code")
        return None

    @staticmethod
    def _merge_transformation_codes(existing_code: str, new_code: str) -> str:
        """
        Объединяет existing_code и new_code в единый исполняемый скрипт.
        
        Добавляет переприсваивание df = df_xxx между шагами, чтобы new_code
        мог обращаться к результату existing_code через стандартное имя 'df'.
        
        Args:
            existing_code: Код предыдущей трансформации
            new_code: Новый код, зависящий от результатов existing_code
            
        Returns:
            Объединённый код с мостом для передачи данных между шагами
        """
        # Удаляем дублирующиеся import pandas as pd
        clean_new_code = new_code
        if 'import pandas as pd' in existing_code:
            clean_new_code = re.sub(r'^\s*import pandas as pd\s*$', '', new_code, flags=re.MULTILINE)
        
        # Извлекаем имя выходной переменной из existing_code (например, df_sales_by_brand)
        var_match = re.search(r'\b(df_\w+)\s*=', existing_code)
        
        if var_match:
            output_var = var_match.group(1)
            # Добавляем переприсваивание для цепочки: df = df_sales_by_brand
            # Это позволяет new_code работать с результатом предыдущего шага через 'df'
            bridge = f"\n# Chain transformation (step 2)\n# Pass result to next step\ndf = {output_var}\n\n"
            logger.debug(f"🔗 Adding bridge: df = {output_var}")
        else:
            # Fallback: переменная не найдена, просто разделитель
            bridge = "\n# Chain transformation (step 2)\n"
            logger.warning("⚠️ Could not find output variable in existing_code for bridge")
        
        # Объединяем: existing_code + bridge + new_code
        merged = existing_code.strip() + bridge + clean_new_code.strip()
        return merged
