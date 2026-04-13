"""
Политики селекции контекста для prompt-level usage.

Фаза 1 context engineering:
- role-aware отбор полей из agent_results;
- бюджет по количеству элементов и общему размеру;
- базовая санитизация тяжёлых секций (sources/tables).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .context_graph.slice import build_context_graph_slice
from .context_metrics import estimate_serialized_size
from .runtime_overrides import ma_bool, ma_int

logger = logging.getLogger(__name__)

DEFAULT_BUDGETS: Dict[str, Tuple[int, int]] = {
    # Planner использует накопленный контекст для revise/replan, но в ограниченном объёме.
    "planner": (35, 120000),
    # сохраняем текущий baseline AnalystAgent (~30 / ~100k chars)
    "analyst": (30, 100000),
    # Reporter синтезирует по множеству шагов — немного шире
    "reporter": (40, 120000),
    # Discovery/Research в основном работают с источниками и narrative.
    "discovery": (20, 90000),
    "research": (20, 100000),
    # Structurizer читает сырой контент и строит таблицы — чуть шире бюджет.
    "structurizer": (20, 110000),
    # Codex-агенты должны видеть релевантные ошибки/контекст, но без лишнего шума.
    "transform_codex": (25, 110000),
    "widget_codex": (25, 110000),
    # ContextFilter и Validator — узкоспециализированные шаги с умеренным бюджетом.
    "context_filter": (20, 80000),
    "validator": (25, 100000),
    # fallback
    "_default": (30, 100000),
}

PLANNER_TASK_BUDGETS: Dict[str, Tuple[int, int]] = {
    # create_plan обычно опирается на user_request и board/input previews, история меньше нужна.
    "create_plan": (20, 70000),
    # expand_step работает локально по одному шагу.
    "expand_step": (20, 70000),
    # revise/replan должны видеть больше аккумулированного контекста.
    "revise_remaining": (35, 120000),
    "replan": (40, 140000),
}


AGENT_ALLOWED_FIELDS: Dict[str, Optional[set[str]]] = {
    "planner": {
        "agent",
        "status",
        "error",
        "narrative",
        "findings",
        "tables",
        "sources",
        "discovered_resources",
        "validation",
        "metadata",
        "step_id",
    },
    # Для аналитика отсекаем code_blocks, чтобы не раздувать prompt кодом.
    "analyst": {
        "agent",
        "status",
        "error",
        "narrative",
        "findings",
        "tables",
        "sources",
        "discovered_resources",
        "validation",
        "metadata",
        "step_id",
    },
    # Reporter может пробрасывать code_blocks дальше.
    "reporter": {
        "agent",
        "status",
        "error",
        "narrative",
        "findings",
        "tables",
        "sources",
        "discovered_resources",
        "code_blocks",
        "validation",
        "metadata",
        "plan",
        "step_id",
    },
    "discovery": {
        "agent",
        "status",
        "error",
        "narrative",
        "sources",
        "discovered_resources",
        "metadata",
        "step_id",
    },
    "research": {
        "agent",
        "status",
        "error",
        "narrative",
        "sources",
        "discovered_resources",
        "metadata",
        "step_id",
    },
    "structurizer": {
        "agent",
        "status",
        "error",
        "narrative",
        "tables",
        "sources",
        "discovered_resources",
        "metadata",
        "step_id",
    },
    "transform_codex": {
        "agent",
        "status",
        "error",
        "narrative",
        "code_blocks",
        "findings",
        "metadata",
        "step_id",
    },
    "widget_codex": {
        "agent",
        "status",
        "error",
        "narrative",
        "code_blocks",
        "findings",
        "metadata",
        "step_id",
    },
    "context_filter": {
        "agent",
        "status",
        "error",
        "narrative",
        "metadata",
        "step_id",
    },
    "validator": {
        "agent",
        "status",
        "error",
        "validation",
        "findings",
        "metadata",
        "step_id",
    },
    # None = без фильтрации ключей
    "_default": None,
}


def _truncate_text(value: Any, max_chars: int) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "... [truncated]"


def _sanitize_sources(sources: Any) -> List[Dict[str, Any]]:
    if not isinstance(sources, list):
        return []
    max_src = ma_int("MULTI_AGENT_CONTEXT_MAX_SOURCES_PER_RESULT", 8)
    max_ch = ma_int("MULTI_AGENT_CONTEXT_MAX_SOURCE_CONTENT_CHARS", 4000)
    sanitized: List[Dict[str, Any]] = []
    for src in sources[:max_src]:
        if not isinstance(src, dict):
            continue
        sanitized.append({
            "url": src.get("url"),
            "title": src.get("title"),
            "snippet": src.get("snippet"),
            "fetched": src.get("fetched"),
            "status": src.get("status"),
            "content": _truncate_text(src.get("content"), max_ch),
            "mime_type": src.get("mime_type"),
            "resource_kind": src.get("resource_kind"),
            "metadata": src.get("metadata"),
        })
    return sanitized


def _sanitize_discovered_resources(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    max_n = ma_int("MULTI_AGENT_CONTEXT_MAX_DISCOVERED_RESOURCES", 64)
    max_url = ma_int("MULTI_AGENT_CONTEXT_MAX_DISCOVERED_RESOURCE_URL_CHARS", 2000)
    out: List[Dict[str, Any]] = []
    for it in items[:max_n]:
        if not isinstance(it, dict):
            continue
        pu = it.get("parent_url")
        out.append({
            "url": _truncate_text(str(it.get("url") or ""), max_url),
            "resource_kind": it.get("resource_kind"),
            "mime_type": it.get("mime_type"),
            "parent_url": _truncate_text(str(pu), max_url) if pu else None,
            "origin": it.get("origin"),
            "tag": it.get("tag"),
            "title": _truncate_text(it.get("title"), 400) if it.get("title") else None,
        })
    return out


def _sanitize_tables(tables: Any) -> List[Dict[str, Any]]:
    if not isinstance(tables, list):
        return []
    max_tbl = ma_int("MULTI_AGENT_CONTEXT_MAX_TABLES_PER_RESULT", 8)
    max_rows = ma_int("MULTI_AGENT_CONTEXT_MAX_TABLE_ROWS", 20)
    sanitized: List[Dict[str, Any]] = []
    for table in tables[:max_tbl]:
        if not isinstance(table, dict):
            continue
        rows = table.get("rows")
        row_count = table.get("row_count")
        if isinstance(rows, list):
            sampled_rows = rows[:max_rows]
            if row_count is None:
                row_count = len(rows)
        else:
            sampled_rows = rows

        sanitized.append({
            "name": table.get("name"),
            "columns": table.get("columns"),
            "rows": sampled_rows,
            "row_count": row_count,
            "metadata": table.get("metadata"),
        })
    return sanitized


def _sanitize_result_item(agent_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    allowed = AGENT_ALLOWED_FIELDS.get(agent_name, AGENT_ALLOWED_FIELDS["_default"])
    if allowed is None:
        item = dict(result)
    else:
        item = {k: result.get(k) for k in allowed if k in result}

    if "sources" in item:
        item["sources"] = _sanitize_sources(item.get("sources"))
    if "discovered_resources" in item:
        item["discovered_resources"] = _sanitize_discovered_resources(
            item.get("discovered_resources")
        )
    if "tables" in item:
        item["tables"] = _sanitize_tables(item.get("tables"))
    if "findings" in item and isinstance(item["findings"], list):
        item["findings"] = item["findings"][: ma_int("MULTI_AGENT_CONTEXT_MAX_FINDINGS_PER_RESULT", 20)]
    if "code_blocks" in item and isinstance(item["code_blocks"], list):
        item["code_blocks"] = item["code_blocks"][: ma_int("MULTI_AGENT_CONTEXT_MAX_CODE_BLOCKS_PER_RESULT", 8)]
    return item


def _sanitize_chat_history(
    history: Any,
    *,
    max_messages: Optional[int] = None,
    max_message_chars: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(history, list):
        return []
    mm = max_messages if max_messages is not None else ma_int("MULTI_AGENT_CONTEXT_MAX_CHAT_MESSAGES", 12)
    mc = max_message_chars if max_message_chars is not None else ma_int("MULTI_AGENT_CONTEXT_MAX_CHAT_MESSAGE_CHARS", 500)
    tail = history[-mm:]
    sanitized: List[Dict[str, Any]] = []
    for msg in tail:
        if not isinstance(msg, dict):
            continue
        sanitized.append({
            "role": msg.get("role", "user"),
            "content": _truncate_text(msg.get("content", ""), mc),
        })
    return sanitized


def _sanitize_preview_columns(columns: Any, max_columns: int) -> List[Dict[str, Any]]:
    if not isinstance(columns, list):
        return []
    out: List[Dict[str, Any]] = []
    for col in columns[:max_columns]:
        if isinstance(col, dict):
            out.append(
                {
                    "name": col.get("name"),
                    "type": col.get("type"),
                }
            )
        else:
            out.append({"name": str(col), "type": None})
    return out


def _sanitize_preview_sample_rows(
    sample_rows: Any,
    *,
    max_rows: int,
    max_columns: int,
    max_cell_chars: int,
) -> List[Any]:
    if not isinstance(sample_rows, list):
        return []
    sanitized_rows: List[Any] = []
    for row in sample_rows[:max_rows]:
        if isinstance(row, dict):
            compact_row: Dict[str, Any] = {}
            for idx, (key, value) in enumerate(row.items()):
                if idx >= max_columns:
                    break
                compact_row[str(key)] = _truncate_text(value, max_cell_chars)
            sanitized_rows.append(compact_row)
        else:
            sanitized_rows.append(_truncate_text(row, max_cell_chars))
    return sanitized_rows


def _sanitize_table_preview_map(
    preview: Any,
    max_tables: int,
    max_columns: int,
) -> Dict[str, Dict[str, Any]]:
    if not isinstance(preview, dict):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    max_sample_rows = ma_int("MULTI_AGENT_CONTEXT_MAX_PREVIEW_SAMPLE_ROWS", 4)
    max_sample_cell_chars = ma_int(
        "MULTI_AGENT_CONTEXT_MAX_PREVIEW_SAMPLE_CELL_CHARS",
        120,
    )
    for table_key, info in list(preview.items())[:max_tables]:
        if not isinstance(info, dict):
            continue
        result[str(table_key)] = {
            "node_name": info.get("node_name"),
            "table_name": info.get("table_name"),
            "row_count": info.get("row_count"),
            "columns": _sanitize_preview_columns(info.get("columns"), max_columns),
            # Важно для QA/анализа: сохраняем небольшой срез строк,
            # иначе агент видит только схему и не может ответить по фактам.
            "sample_rows": _sanitize_preview_sample_rows(
                info.get("sample_rows"),
                max_rows=max_sample_rows,
                max_columns=max_columns,
                max_cell_chars=max_sample_cell_chars,
            ),
        }
    return result


def _strip_tabular_context_for_tool_mode(base_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove all tabular previews/data from prompt context.

    In forced tool mode agents must fetch table metadata/rows via orchestrator tools
    instead of receiving table samples directly in prompt context.
    """
    if "input_data_preview" in base_ctx:
        base_ctx["input_data_preview"] = {}
    if "catalog_data_preview" in base_ctx:
        base_ctx["catalog_data_preview"] = {}
    if "input_tables" in base_ctx:
        base_ctx["input_tables"] = []
    if "text_content" in base_ctx:
        base_ctx["text_content"] = ""

    cn_data = base_ctx.get("content_nodes_data")
    if isinstance(cn_data, list):
        stripped_nodes: List[Dict[str, Any]] = []
        for node in cn_data:
            if not isinstance(node, dict):
                continue
            stripped_nodes.append(
                {
                    "id": node.get("id") or node.get("node_id"),
                    "node_id": node.get("node_id") or node.get("id"),
                    "name": node.get("name") or node.get("node_name"),
                    "node_name": node.get("node_name") or node.get("name"),
                }
            )
        base_ctx["content_nodes_data"] = stripped_nodes

    if isinstance(base_ctx.get("agent_results"), list):
        stripped_results: List[Dict[str, Any]] = []
        for item in base_ctx.get("agent_results", []):
            if not isinstance(item, dict):
                continue
            clone = dict(item)
            clone.pop("tables", None)
            stripped_results.append(clone)
        base_ctx["agent_results"] = stripped_results

    base_ctx["_tabular_context_stripped"] = True
    return base_ctx


def _resolve_budget(
    agent_name: str,
    task_type: Optional[str] = None,
    runtime_options: Optional[Dict[str, Any]] = None,
) -> Tuple[int, int]:
    max_items, max_chars = DEFAULT_BUDGETS.get(agent_name, DEFAULT_BUDGETS["_default"])
    if agent_name == "planner" and task_type:
        t_items, t_chars = PLANNER_TASK_BUDGETS.get(task_type, (max_items, max_chars))
        max_items, max_chars = t_items, t_chars
        task_env_prefix = f"MULTI_AGENT_CONTEXT_PLANNER_{task_type.upper()}"
        max_items = ma_int(f"{task_env_prefix}_MAX_ITEMS", max_items)
        max_chars = ma_int(f"{task_env_prefix}_MAX_TOTAL_CHARS", max_chars)

    env_items = ma_int(
        f"MULTI_AGENT_CONTEXT_{agent_name.upper()}_MAX_ITEMS",
        max_items,
    )
    env_chars = ma_int(
        f"MULTI_AGENT_CONTEXT_{agent_name.upper()}_MAX_TOTAL_CHARS",
        max_chars,
    )
    resolved_items, resolved_chars = env_items, env_chars

    # DB runtime_options в agent_llm_override имеют приоритет над env/default.
    if isinstance(runtime_options, dict):
        if runtime_options.get("max_items") is not None:
            try:
                resolved_items = int(runtime_options.get("max_items"))
            except (TypeError, ValueError):
                pass
        if runtime_options.get("max_total_chars") is not None:
            try:
                resolved_chars = int(runtime_options.get("max_total_chars"))
            except (TypeError, ValueError):
                pass
        task_overrides = runtime_options.get("task_overrides")
        if isinstance(task_overrides, dict) and task_type:
            task_runtime = task_overrides.get(task_type)
            if isinstance(task_runtime, dict):
                if task_runtime.get("max_items") is not None:
                    try:
                        resolved_items = int(task_runtime.get("max_items"))
                    except (TypeError, ValueError):
                        pass
                if task_runtime.get("max_total_chars") is not None:
                    try:
                        resolved_chars = int(task_runtime.get("max_total_chars"))
                    except (TypeError, ValueError):
                        pass
    return resolved_items, resolved_chars


def select_agent_results_for_prompt(
    agent_name: str,
    agent_results: Any,
    task_type: Optional[str] = None,
    max_items: Optional[int] = None,
    max_total_chars: Optional[int] = None,
    runtime_options: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Возвращает срез agent_results для prompt указанного агента.
    """
    if not isinstance(agent_results, list) or not agent_results:
        return []

    default_items, default_chars = _resolve_budget(
        agent_name,
        task_type=task_type,
        runtime_options=runtime_options,
    )
    limit_items = max_items if max_items is not None else default_items
    limit_chars = max_total_chars if max_total_chars is not None else default_chars

    selected_reversed: List[Dict[str, Any]] = []
    total_chars = 0

    for raw in reversed(agent_results):
        if not isinstance(raw, dict):
            continue
        sanitized = _sanitize_result_item(agent_name, raw)
        item_chars = estimate_serialized_size(sanitized)

        # Как и в старом Analyst baseline: первый элемент пропускаем только если уже что-то набрали.
        if total_chars + item_chars > limit_chars and selected_reversed:
            break

        selected_reversed.append(sanitized)
        total_chars += item_chars

        if len(selected_reversed) >= limit_items:
            break

    return list(reversed(selected_reversed))


def _graph_has_nodes(pipeline_context: Optional[Dict[str, Any]]) -> bool:
    if not pipeline_context:
        return False
    g = pipeline_context.get("context_graph")
    if not isinstance(g, dict):
        return False
    nodes = g.get("nodes")
    return isinstance(nodes, dict) and len(nodes) > 0


def _apply_compaction(
    level: str,
    *,
    max_items: int,
    max_chars: int,
) -> Tuple[int, int, int, int]:
    lvl = (level or "full").lower()
    if lvl == "minimal":
        return max(5, max_items // 3), max(20000, max_chars // 3), 6, 300
    if lvl == "compact":
        return max(10, max_items // 2), max(40000, max_chars // 2), 10, 400
    return (
        max_items,
        max_chars,
        ma_int("MULTI_AGENT_CONTEXT_MAX_CHAT_MESSAGES", 12),
        ma_int("MULTI_AGENT_CONTEXT_MAX_CHAT_MESSAGE_CHARS", 500),
    )


def select_context_for_step(
    agent_name: str,
    pipeline_context: Optional[Dict[str, Any]],
    task_type: Optional[str] = None,
    compaction_level: str = "full",
    runtime_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Возвращает копию context, где agent_results уже отфильтрован под роль агента.
    """
    base_ctx: Dict[str, Any] = dict(pipeline_context or {})
    # Применяем роль-специфичный срез только для агентов с явной политикой.
    if agent_name not in DEFAULT_BUDGETS:
        return base_ctx

    limit_items, limit_chars = _resolve_budget(
        agent_name,
        task_type=task_type,
        runtime_options=runtime_options,
    )
    effective_items, effective_chars, max_chat_messages, max_chat_chars = _apply_compaction(
        compaction_level,
        max_items=limit_items,
        max_chars=limit_chars,
    )
    selected_full = select_agent_results_for_prompt(
        agent_name=agent_name,
        agent_results=base_ctx.get("agent_results", []),
        task_type=task_type,
        max_items=effective_items,
        max_total_chars=effective_chars,
        runtime_options=runtime_options,
    )
    base_ctx["_agent_results_selected_budget"] = list(selected_full)

    graph_primary = (
        ma_bool("MULTI_AGENT_CONTEXT_GRAPH_PRIMARY", True) and _graph_has_nodes(base_ctx)
    )
    if graph_primary:
        tail_items = ma_int("MULTI_AGENT_CONTEXT_GRAPH_PRIMARY_TAIL_ITEMS", 2)
        if tail_items <= 0:
            base_ctx["agent_results"] = []
        else:
            base_ctx["agent_results"] = (
                selected_full[-tail_items:]
                if len(selected_full) > tail_items
                else list(selected_full)
            )
        base_ctx["_context_graph_primary"] = True
    else:
        base_ctx["agent_results"] = selected_full
        base_ctx["_context_graph_primary"] = False
    # Дополнительно нормализуем «сырой» контекстные поля,
    # которые напрямую участвуют в prompt-сборке core-агентов.
    if "chat_history" in base_ctx:
        base_ctx["chat_history"] = _sanitize_chat_history(
            base_ctx.get("chat_history"),
            max_messages=max_chat_messages,
            max_message_chars=max_chat_chars,
        )
    if "input_data_preview" in base_ctx:
        base_ctx["input_data_preview"] = _sanitize_table_preview_map(
            base_ctx.get("input_data_preview"),
            max_tables=ma_int("MULTI_AGENT_CONTEXT_MAX_INPUT_PREVIEW_TABLES", 3),
            max_columns=ma_int("MULTI_AGENT_CONTEXT_MAX_INPUT_PREVIEW_COLUMNS", 20),
        )
    if "catalog_data_preview" in base_ctx:
        base_ctx["catalog_data_preview"] = _sanitize_table_preview_map(
            base_ctx.get("catalog_data_preview"),
            max_tables=ma_int("MULTI_AGENT_CONTEXT_MAX_CATALOG_PREVIEW_TABLES", 8),
            max_columns=ma_int("MULTI_AGENT_CONTEXT_MAX_CATALOG_PREVIEW_COLUMNS", 12),
        )
    # Satellite controllers (transformation, widget) передают полные превью таблиц в контекст;
    # не вырезаем их — иначе transform_codex/widget_codex теряют схемы и sample_rows.
    _force_strip = bool(base_ctx.get("force_tool_data_access")) and not bool(
        base_ctx.get("keep_tabular_context_in_prompt")
    )
    if _force_strip:
        base_ctx = _strip_tabular_context_for_tool_mode(base_ctx)

    base_ctx["_context_selection_applied_for"] = agent_name
    if task_type:
        base_ctx["_context_selection_task_type"] = task_type
    base_ctx["_context_selection_budget_items"] = effective_items
    base_ctx["_context_selection_budget_chars"] = effective_chars
    base_ctx["_context_selection_compaction_level"] = compaction_level

    slice_text, slice_meta = build_context_graph_slice(
        consumer_agent=agent_name,
        pipeline_context=base_ctx,
        compaction_level=compaction_level,
    )
    base_ctx["_context_graph_slice"] = slice_text
    base_ctx["_context_graph_slice_meta"] = slice_meta

    trace_fn = base_ctx.get("_trace_event")
    _lvl = (compaction_level or "full").lower()
    if callable(trace_fn) and _lvl != "full":
        trace_fn(
            event="context_compaction_budget",
            phase="context_selection",
            agent=agent_name,
            details={
                "compaction_level": compaction_level,
                "task_type": task_type,
                "budget_items_raw": limit_items,
                "budget_items_effective": effective_items,
                "budget_chars_raw": limit_chars,
                "budget_chars_effective": effective_chars,
                "max_chat_messages": max_chat_messages,
                "max_chat_message_chars": max_chat_chars,
                "graph_slice_text_len": len(slice_text or ""),
                "graph_primary": bool(base_ctx.get("_context_graph_primary")),
            },
        )
    if ma_bool("MULTI_AGENT_CONTEXT_EXPAND_COMPACT_LOG", False) and _lvl != "full":
        logger.info(
            "[context_compaction] agent=%s task=%s level=%s items %s->%s chars %s->%s slice_len=%s primary=%s",
            agent_name,
            task_type,
            compaction_level,
            limit_items,
            effective_items,
            limit_chars,
            effective_chars,
            len(slice_text or ""),
            base_ctx.get("_context_graph_primary"),
        )

    return base_ctx
