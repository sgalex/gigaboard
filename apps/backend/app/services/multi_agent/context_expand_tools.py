"""
Pull-тулы оркестратора: развёрнуть фрагмент истории пайплайна или полный текст источника.

См. docs/CONTEXT_ENGINEERING.md §3.1.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from .context_graph.compression import resolve_slice_node_body
from .context_selection import _sanitize_result_item
from .runtime_overrides import ma_bool, ma_int


def _agent_results_list(pipeline_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = pipeline_context.get("agent_results")
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def _parse_index(arguments: Dict[str, Any], key: str) -> Optional[int]:
    v = arguments.get(key)
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def run_expand_research_source_content(
    pipeline_context: Dict[str, Any],
    arguments: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Возвращает полный (с лимитом) content одного элемента sources[] из agent_results[i].

    arguments:
      agent_result_index (int, required)
      source_index (int, default 0) — индекс в массиве sources
      url (str, optional) — если задан, выбирается первый source с совпадающим url (substring match)
      max_chars (int, optional)
    """
    if not ma_bool("MULTI_AGENT_CONTEXT_EXPAND_TOOLS", True):
        return None, "expandResearchSourceContent is disabled (MULTI_AGENT_CONTEXT_EXPAND_TOOLS=false)"

    ar = _agent_results_list(pipeline_context)
    idx = _parse_index(arguments, "agent_result_index")
    if idx is None:
        return None, "agent_result_index is required (int)"
    if idx < 0 or idx >= len(ar):
        return None, f"agent_result_index out of range (0..{len(ar) - 1})"

    result = ar[idx]
    sources = result.get("sources")
    if not isinstance(sources, list) or not sources:
        return None, "No sources[] on this agent_result"

    max_chars = arguments.get("max_chars")
    if max_chars is not None:
        try:
            cap = max(256, min(int(max_chars), ma_int("MULTI_AGENT_TOOL_EXPAND_SOURCE_MAX_CHARS", 12000)))
        except (TypeError, ValueError):
            cap = ma_int("MULTI_AGENT_TOOL_EXPAND_SOURCE_MAX_CHARS", 12000)
    else:
        cap = ma_int("MULTI_AGENT_TOOL_EXPAND_SOURCE_MAX_CHARS", 12000)

    url_filter = str(arguments.get("url") or "").strip()
    source_idx = _parse_index(arguments, "source_index")
    if url_filter:
        chosen_i = None
        chosen = None
        for i, s in enumerate(sources):
            if not isinstance(s, dict):
                continue
            u = str(s.get("url") or "")
            if url_filter in u or u in url_filter:
                chosen_i, chosen = i, s
                break
        if chosen is None:
            return None, f"No source matching url filter: {url_filter[:120]!r}"
    else:
        si = 0 if source_idx is None else source_idx
        if si < 0 or si >= len(sources):
            return None, f"source_index out of range (0..{len(sources) - 1})"
        chosen_i, chosen = si, sources[si]
        if not isinstance(chosen, dict):
            return None, "Selected source is not an object"

    content = chosen.get("content")
    text = content if isinstance(content, str) else ("" if content is None else str(content))
    truncated = len(text) > cap
    if truncated:
        text = text[:cap] + "\n... [truncated by expandResearchSourceContent max_chars]"

    return {
        "tool": "expandResearchSourceContent",
        "agent_result_index": idx,
        "source_index": chosen_i,
        "url": chosen.get("url"),
        "title": chosen.get("title"),
        "fetched": chosen.get("fetched"),
        "content": text,
        "content_length": len(text),
        "truncated": truncated,
        "agent": result.get("agent"),
    }, None


def run_expand_agent_result(
    pipeline_context: Dict[str, Any],
    arguments: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Санитизированный срез одной записи agent_results (как для analyst prompt), с общим лимитом сериализации.

    arguments:
      agent_result_index (int, required)
      max_total_chars (int, optional)
    """
    if not ma_bool("MULTI_AGENT_CONTEXT_EXPAND_TOOLS", True):
        return None, "expandAgentResult is disabled (MULTI_AGENT_CONTEXT_EXPAND_TOOLS=false)"

    ar = _agent_results_list(pipeline_context)
    idx = _parse_index(arguments, "agent_result_index")
    if idx is None:
        return None, "agent_result_index is required (int)"
    if idx < 0 or idx >= len(ar):
        return None, f"agent_result_index out of range (0..{len(ar) - 1})"

    max_total = arguments.get("max_total_chars")
    if max_total is not None:
        try:
            cap = max(1024, min(int(max_total), ma_int("MULTI_AGENT_TOOL_EXPAND_AGENT_MAX_CHARS", 32000)))
        except (TypeError, ValueError):
            cap = ma_int("MULTI_AGENT_TOOL_EXPAND_AGENT_MAX_CHARS", 32000)
    else:
        cap = ma_int("MULTI_AGENT_TOOL_EXPAND_AGENT_MAX_CHARS", 32000)

    raw = ar[idx]
    sanitized = _sanitize_result_item("analyst", raw)
    payload = {
        "tool": "expandAgentResult",
        "agent_result_index": idx,
        "record": sanitized,
    }
    try:
        dumped = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception as e:
        return None, f"serialize failed: {e}"

    if len(dumped) <= cap:
        return {"json": dumped, "truncated": False, "chars": len(dumped)}, None

    # Ужимаем: оставляем только «лёгкие» ключи + усечённый narrative
    light = {
        "agent": sanitized.get("agent"),
        "status": sanitized.get("status"),
        "step_id": sanitized.get("step_id"),
        "error": sanitized.get("error"),
    }
    nar = sanitized.get("narrative")
    if nar is not None:
        light["narrative"] = nar
    findings = sanitized.get("findings")
    if isinstance(findings, list):
        light["findings"] = findings[:5]
    retry_payload = {"tool": "expandAgentResult", "agent_result_index": idx, "record": light}
    dumped2 = json.dumps(retry_payload, ensure_ascii=False, default=str)
    if len(dumped2) > cap:
        dumped2 = dumped2[:cap] + "\n... [truncated by max_total_chars]"
    return {"json": dumped2, "truncated": True, "chars": len(dumped2)}, None


def run_expand_context_graph_node(
    pipeline_context: Dict[str, Any],
    arguments: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Детали узла context_graph по id (UUID из среза графа / ingest).

    arguments:
      node_id (str, required)
      body_level (str, optional) — full | compact | minimal для resolve_slice_node_body (default full)
    """
    if not ma_bool("MULTI_AGENT_CONTEXT_EXPAND_TOOLS", True):
        return None, "expandContextGraphNode is disabled (MULTI_AGENT_CONTEXT_EXPAND_TOOLS=false)"

    node_id = str(arguments.get("node_id") or "").strip()
    if not node_id:
        return None, "node_id is required"

    graph = pipeline_context.get("context_graph")
    if not isinstance(graph, dict):
        return None, "No context_graph in pipeline_context"
    nodes = graph.get("nodes")
    if not isinstance(nodes, dict):
        return None, "Invalid context_graph.nodes"

    node = nodes.get(node_id)
    if not isinstance(node, dict):
        return None, f"Node not found: {node_id}"

    lvl = str(arguments.get("body_level") or "full").lower()
    if lvl not in {"full", "compact", "minimal"}:
        lvl = "full"

    body = resolve_slice_node_body(node, compaction_level=lvl)
    return {
        "tool": "expandContextGraphNode",
        "node_id": node_id,
        "agent": node.get("agent"),
        "ingest_seq": node.get("ingest_seq"),
        "agent_result_index": node.get("agent_result_index"),
        "step_id": node.get("step_id"),
        "body_level": lvl,
        "body": body,
        "summary_text": node.get("summary_text"),
        "l1_summary": node.get("l1_summary"),
        "l2_one_liner": node.get("l2_one_liner"),
    }, None
