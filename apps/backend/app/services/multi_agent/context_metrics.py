"""
Утилиты оценки объёма контекста для трассировки Multi-Agent pipeline.

Модуль intentionally lightweight: без зависимости от токенизаторов,
чтобы работать быстро и стабильно в runtime.
"""

from __future__ import annotations

import json
from typing import Any, Dict


def estimate_serialized_size(value: Any) -> int:
    """Оценка размера объекта как длины сериализованной строки."""
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return len(str(value))


def summarize_agent_results_stats(agent_results: Any) -> Dict[str, int]:
    """
    Возвращает компактную сводку по agent_results для trace/log.

    Формат:
    - count: число элементов
    - total_chars: оценка общего сериализованного объёма списка
    - largest_item_chars: максимальный размер одного элемента
    """
    if not isinstance(agent_results, list) or not agent_results:
        return {"count": 0, "total_chars": 0, "largest_item_chars": 0}

    total_chars = 0
    largest_item_chars = 0
    for item in agent_results:
        size = estimate_serialized_size(item)
        total_chars += size
        if size > largest_item_chars:
            largest_item_chars = size

    return {
        "count": len(agent_results),
        "total_chars": total_chars,
        "largest_item_chars": largest_item_chars,
    }


def summarize_context_efficiency_snapshot(context: Any) -> Dict[str, Any]:
    """
    Компактные поля для trace/логов: граф, graph-primary, бюджетный список, размер среза.
    Не сериализует полные agent_results.
    """
    if not isinstance(context, dict):
        return {}

    out: Dict[str, Any] = {}
    meta = context.get("_context_graph_slice_meta")
    if isinstance(meta, dict):
        out["graph_slice_meta"] = {
            "nodes_included": meta.get("nodes_included"),
            "chars": meta.get("chars"),
            "skipped": meta.get("skipped"),
            "max_chars": meta.get("max_chars"),
            "compaction_level": meta.get("compaction_level"),
        }
    cg = context.get("_context_graph_slice")
    if isinstance(cg, str):
        out["graph_slice_text_len"] = len(cg)

    out["graph_primary"] = bool(context.get("_context_graph_primary"))
    bud = context.get("_agent_results_selected_budget")
    if isinstance(bud, list):
        out["selected_budget_items"] = len(bud)
        st = summarize_agent_results_stats(bud)
        out["selected_budget_chars_est"] = st.get("total_chars", 0)
        out["selected_budget_largest_item_chars"] = st.get("largest_item_chars", 0)

    out["selection_compaction_level"] = context.get("_context_selection_compaction_level")
    sel_for = context.get("_context_selection_applied_for")
    if sel_for:
        out["selection_applied_for"] = sel_for

    g = context.get("context_graph")
    if isinstance(g, dict) and isinstance(g.get("nodes"), dict):
        out["graph_nodes_total"] = len(g["nodes"])

    cache = context.get("_tool_result_cache")
    if isinstance(cache, dict):
        out["tool_result_cache_entries"] = len(cache)
    dig = context.get("tool_request_cache_digest_lines")
    if isinstance(dig, list):
        out["tool_digest_lines"] = len(dig)

    return out


def summarize_context_estimates(context: Any) -> Dict[str, int]:
    """
    Оценка ключевых контекстных секций, влияющих на размер prompt payload.
    """
    if not isinstance(context, dict):
        return {
            "agent_results_count": 0,
            "agent_results_chars": 0,
            "agent_results_largest_item_chars": 0,
            "chat_history_count": 0,
            "chat_history_chars": 0,
            "context_total_chars": 0,
        }

    agent_stats = summarize_agent_results_stats(context.get("agent_results"))
    chat_history = context.get("chat_history")
    chat_count = len(chat_history) if isinstance(chat_history, list) else 0

    return {
        "agent_results_count": agent_stats["count"],
        "agent_results_chars": agent_stats["total_chars"],
        "agent_results_largest_item_chars": agent_stats["largest_item_chars"],
        "chat_history_count": chat_count,
        "chat_history_chars": estimate_serialized_size(chat_history) if chat_count else 0,
        "context_total_chars": estimate_serialized_size(context),
    }
