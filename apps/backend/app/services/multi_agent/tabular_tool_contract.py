"""
Единый контракт «задача шага ↔ доступ к таблицам через тулы оркестратора».

Проблема: system prompt агента и description шага от планировщика описывают «проанализируй»,
но не упоминают readTableListFromContentNodes / readTableData — LLM не связывает запрос с тулами.

Решение: оркестратор дополняет task.description для tool-агентов; планировщик получает отдельный блок в
user-промпт при tools_enabled.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet

TOOL_AGENTS: FrozenSet[str] = frozenset(
    {"analyst", "transform_codex", "widget_codex", "structurizer"}
)

_MARK = "[КОНТРАКТ ДОСТУПА К ТАБЛИЦАМ]"


def _has_tabular_scope(ctx: Dict[str, Any]) -> bool:
    if not isinstance(ctx, dict):
        return False
    if ctx.get("content_node_id"):
        return True
    for key in ("selected_node_ids", "content_node_ids", "contentNodeIds"):
        raw = ctx.get(key)
        if isinstance(raw, list) and any(str(x).strip() for x in raw):
            return True
    if ctx.get("input_data_preview") or ctx.get("catalog_data_preview"):
        return True
    if isinstance(ctx.get("content_nodes_data"), list) and ctx.get("content_nodes_data"):
        return True
    return False


def enrich_task_for_tabular_tools(
    agent_name: str,
    task: Dict[str, Any],
    pipeline_context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Возвращает копию task с дополненным description, если включены тулы и есть табличный контекст.

    Идемпотентно: повторный вызов не дублирует блок (по _tabular_tool_contract_applied или маркеру).
    """
    if not isinstance(task, dict):
        return task
    if not pipeline_context.get("tools_enabled"):
        return task
    if agent_name not in TOOL_AGENTS:
        return task
    if not _has_tabular_scope(pipeline_context):
        return task
    if task.get("_tabular_tool_contract_applied"):
        return task

    desc = str(task.get("description") or "").strip()
    if _MARK in desc or "readTableListFromContentNodes" in desc:
        out = dict(task)
        out["_tabular_tool_contract_applied"] = True
        return out

    appendix = (
        f"\n\n{_MARK}\n"
        "Табличные данные с доски могут быть недоступны в этом промпте целиком (или урезаны). "
        "Чтобы опереться на факты из таблиц ContentNode, используй инструменты оркестратора: "
        "сначала readTableListFromContentNodes (arguments.nodeIds из контекста pipeline), "
        "при необходимости значений из строк — readTableData с jsonDecl.table_id из ответа первого тула. "
        "Если вопрос пользователя требует конкретных значений из строк, не завершай ответ без "
        "нужных данных, полученных через эти инструменты."
    )
    out = dict(task)
    out["description"] = (desc + appendix).strip()
    out["_tabular_tool_contract_applied"] = True
    return out


TOOL_MODE_AGENT_SYSTEM_APPENDIX_RU = """
## Режим инструментов (tools) — как корректно завершить шаг
Если в этом запуске доступны инструменты оркестратора (например readTableListFromContentNodes, readTableData):
- Ты можешь **полностью выполнить** инструкцию пользователя и вернуть обычный ожидаемый ответ (JSON / код / структура), **если** данных в контексте достаточно для честного ответа.
- Либо ты можешь **остановиться и запросить инструмент** — верни JSON с полем `tool_requests`, когда без этого нельзя выполнить задачу (нет нужных таблиц, нужны строки, нужны метаданные таблиц с доски).
- **Важно:** если возникла необходимость вызвать инструмент — **вызови его и на этом заверши ответ**; оркестратор выполнит тул и вызовет тебя снова с результатами. Это **штатное и правильное** поведение, а не ошибка. Не подменяй отсутствующие данные выдуманными значениями ради «полного» ответа пользователю.
"""


def planner_task_summary_hint_block() -> str:
    """Инструкция планировщику: у каждого шага description + summary для прогресса."""
    return (
        "\n**ПОЛЯ ЗАДАЧИ ШАГА (task):**\n"
        "В каждом `steps[].task` укажи:\n"
        "- `description` (обязательно): **полное** техническое задание для агента — контекст, критерии, ограничения.\n"
        "- `summary` (обязательно): **короткая** строка для отображения прогресса в UI (до ~120 символов, одна строка без переносов; "
        "например: «Поиск источников в сети», «Загрузка страниц», «Анализ таблицы продаж»). "
        "По `summary` пользователь видит ход пайплайна; по `description` работает агент.\n"
    )


def planner_tools_hint_block(pipeline_context: Dict[str, Any]) -> str:
    """Фрагмент для _build_planning_prompt планировщика (русский текст)."""
    if not isinstance(pipeline_context, dict) or not pipeline_context.get("tools_enabled"):
        return ""
    if not _has_tabular_scope(pipeline_context):
        return ""
    return (
        "\n**ИНСТРУМЕНТЫ ДОСТУПА К ТАБЛИЦАМ (оркестратор):**\n"
        "Если в плане есть шаги analyst, transform_codex, widget_codex или structurizer "
        "и речь о данных с доски (ContentNode), в поле task.description этого шага явно укажи, "
        "что для чтения метаданных/строк таблиц агент должен использовать инструменты "
        "readTableListFromContentNodes и при необходимости readTableData, а не ограничиваться "
        "общими формулировками вроде «проанализируй данные» без опоры на эти инструменты.\n"
    )
