"""
Ingest: каждый результат в agent_results → узел уровня L0 в context_graph.

LLM-сжатие L1/L2 — см. compression.py (после ingest, если включено MULTI_AGENT_CONTEXT_GRAPH_LLM_COMPRESSION).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from ..runtime_overrides import ma_int
from .store import ensure_context_graph

logger = logging.getLogger(__name__)

_MAX_SUMMARY_CHARS = 8000
_MAX_NARRATIVE_IN_SUMMARY = 4000


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _narrative_text(result: Dict[str, Any]) -> str:
    n = result.get("narrative")
    if n is None:
        return ""
    if isinstance(n, str):
        return n
    if isinstance(n, dict):
        t = n.get("text")
        return str(t) if t is not None else ""
    return str(n)


def _findings_preview(result: Dict[str, Any], limit: int = 3) -> str:
    findings = result.get("findings") or []
    if not isinstance(findings, list):
        return ""
    parts: list[str] = []
    for f in findings[:limit]:
        if isinstance(f, dict):
            text = f.get("text") or f.get("message") or ""
        else:
            text = str(f)
        text = str(text).strip()
        if text:
            parts.append(_truncate(text, 400))
    return " | ".join(parts)


def _tables_digest_for_graph(result: Dict[str, Any], *, max_tables: int = 6) -> str:
    """Компактная схема таблиц для L0 — чтобы граф мог заменять длинный PREVIOUS RESULTS."""
    tables = result.get("tables") or []
    if not isinstance(tables, list) or not tables:
        return ""
    lines: list[str] = []
    for tbl in tables[:max_tables]:
        if not isinstance(tbl, dict):
            continue
        name = str(tbl.get("name") or "table")
        rows = tbl.get("rows")
        rc = tbl.get("row_count")
        if isinstance(rows, list) and rc is None:
            rc = len(rows)
        elif rc is None:
            rc = "?"
        cols = tbl.get("columns") or []
        col_names: list[str] = []
        for c in cols[:14]:
            if isinstance(c, dict):
                col_names.append(str(c.get("name") or ""))
            else:
                col_names.append(str(c))
        col_s = ", ".join(col_names) if col_names else "(no columns)"
        lines.append(f"  • {name}: ~{rc} rows; cols: {col_s}")
    if not lines:
        return ""
    return "tables_digest:\n" + "\n".join(lines)


def _sources_digest_for_graph(result: Dict[str, Any], *, max_items: int = 5) -> str:
    sources = result.get("sources") or []
    if not isinstance(sources, list) or not sources:
        return ""
    lines: list[str] = []
    for s in sources[:max_items]:
        if not isinstance(s, dict):
            continue
        url = str(s.get("url") or "")[:200]
        title = str(s.get("title") or "")[:120]
        fetched = s.get("fetched")
        lines.append(f"  • {title or url} — {url}" + (f" (fetched={fetched})" if fetched is not None else ""))
    if not lines:
        return ""
    return "sources_digest:\n" + "\n".join(lines)


def _plan_brief(result: Dict[str, Any]) -> str:
    plan = result.get("plan")
    if not isinstance(plan, dict):
        return ""
    steps = plan.get("steps") or []
    if not isinstance(steps, list):
        return ""
    agents = []
    for s in steps[:20]:
        if isinstance(s, dict) and s.get("agent"):
            agents.append(str(s["agent"]))
    if not agents:
        return ""
    return f"{len(steps)} steps: " + " → ".join(agents)


def build_l0_summary(result: Dict[str, Any]) -> str:
    """Краткое текстовое содержимое узла L0 для списков и будущего retrieval."""
    agent = str(result.get("agent") or "unknown")
    status = str(result.get("status") or "")
    lines = [f"[{agent}] status={status}"]

    err = result.get("error")
    if err:
        lines.append("error: " + _truncate(str(err), 1200))

    pb = _plan_brief(result)
    if pb:
        lines.append("plan: " + pb)

    nar = _truncate(_narrative_text(result), _MAX_NARRATIVE_IN_SUMMARY)
    if nar:
        lines.append("narrative: " + nar)

    fp = _findings_preview(result)
    if fp:
        lines.append("findings: " + fp)

    td = _tables_digest_for_graph(result)
    if td:
        lines.append(td)

    sd = _sources_digest_for_graph(result)
    if sd:
        lines.append(sd)

    val = result.get("validation")
    if isinstance(val, dict):
        msg = val.get("message") or val.get("summary")
        if msg:
            lines.append("validation: " + _truncate(str(msg), 800))

    out = "\n".join(lines)
    return _truncate(out, _MAX_SUMMARY_CHARS)


def _estimate_payload_chars(result: Dict[str, Any]) -> int:
    try:
        return len(json.dumps(result, ensure_ascii=False, default=str))
    except Exception:
        return len(str(result))


def ingest_agent_result_dict(
    pipeline_context: Dict[str, Any],
    result_dict: Dict[str, Any],
    *,
    agent_result_index: int,
    step_id: Optional[str] = None,
    phase: Optional[str] = None,
) -> Optional[str]:
    """
    Добавляет узел L0 в context_graph. Возвращает id узла или None при невалидном result_dict
    или при достижении MULTI_AGENT_CONTEXT_GRAPH_MAX_NODES.

    result_dict — тот же объект, что лежит в agent_results[agent_result_index].
    """
    if not isinstance(result_dict, dict):
        return None

    max_nodes = ma_int("MULTI_AGENT_CONTEXT_GRAPH_MAX_NODES", 2048)
    graph = ensure_context_graph(pipeline_context)
    nodes: Dict[str, Any] = graph.setdefault("nodes", {})
    if not isinstance(nodes, dict):
        nodes = {}
        graph["nodes"] = nodes

    if len(nodes) >= max_nodes:
        logger.warning(
            "context_graph: node limit reached (%s), skipping ingest for index %s",
            max_nodes,
            agent_result_index,
        )
        return None

    node_id = str(uuid4())
    seq = int(graph.get("ingest_seq") or 0) + 1
    graph["ingest_seq"] = seq

    agent = str(result_dict.get("agent") or "unknown")
    node: Dict[str, Any] = {
        "id": node_id,
        "level": 0,
        "agent": agent,
        "status": result_dict.get("status"),
        "agent_result_index": agent_result_index,
        "step_id": step_id,
        "phase": phase,
        "summary_text": build_l0_summary(result_dict),
        "estimated_chars": _estimate_payload_chars(result_dict),
        "ingest_seq": seq,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    nodes[node_id] = node

    logger.debug(
        "context_graph ingest: node %s agent=%s index=%s seq=%s",
        node_id,
        agent,
        agent_result_index,
        seq,
    )
    return node_id
