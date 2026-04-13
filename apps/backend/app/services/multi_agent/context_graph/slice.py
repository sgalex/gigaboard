"""
Сборка текстового среза по узлам L0 context_graph для подмешивания в промпт.

MVP: недавние узлы (по ingest_seq), бюджет по символам, без эмбеддингов.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..runtime_overrides import ma_int
from .compression import resolve_slice_node_body
from .store import ensure_context_graph

logger = logging.getLogger(__name__)

# Какие исходные агенты учитывать в срезе для данного шага (None = все).
# Сужает шум для специализированных ролей.
_SLICE_SOURCE_FILTER: Dict[str, Optional[set[str]]] = {
    "planner": None,
    "analyst": None,
    "reporter": None,
    "discovery": None,
    "research": None,
    "structurizer": None,
    "transform_codex": None,
    "widget_codex": None,
    "context_filter": None,
    "validator": None,
}


def _compaction_slice_factor(compaction_level: str) -> float:
    lvl = (compaction_level or "full").lower()
    if lvl == "minimal":
        return 0.35
    if lvl == "compact":
        return 0.65
    return 1.0


def _sorted_nodes_newest_first(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes_raw = graph.get("nodes") or {}
    if not isinstance(nodes_raw, dict):
        return []
    out: List[Dict[str, Any]] = []
    for _nid, node in nodes_raw.items():
        if isinstance(node, dict) and int(node.get("level") or 0) == 0:
            out.append(node)
    out.sort(key=lambda n: int(n.get("ingest_seq") or 0), reverse=True)
    return out


def build_context_graph_slice(
    *,
    consumer_agent: str,
    pipeline_context: Optional[Dict[str, Any]],
    compaction_level: str = "full",
) -> Tuple[str, Dict[str, Any]]:
    """
    Формирует markdown-блок с текстом узлов графа (тело узла — L1/L2/L0 по ``compaction_level``,
    см. ``resolve_slice_node_body``; при ``full`` по умолчанию не пушим полный L0, если есть L1).

    Возвращает (text, meta) где meta: nodes_included, chars, skipped_reason.
    """
    empty_meta: Dict[str, Any] = {"nodes_included": 0, "chars": 0, "skipped": "no_graph"}
    if not pipeline_context:
        return "", {**empty_meta, "skipped": "no_context"}

    graph = ensure_context_graph(pipeline_context)
    nodes_list = _sorted_nodes_newest_first(graph)
    if not nodes_list:
        return "", {**empty_meta, "skipped": "no_nodes"}

    base_max = ma_int("MULTI_AGENT_CONTEXT_GRAPH_SLICE_MAX_CHARS", 14000)
    max_nodes = ma_int("MULTI_AGENT_CONTEXT_GRAPH_SLICE_MAX_NODES", 40)
    max_chars = max(
        800,
        int(base_max * _compaction_slice_factor(compaction_level)),
    )

    allowed = _SLICE_SOURCE_FILTER.get(consumer_agent)
    if allowed is None:
        filtered = nodes_list
    else:
        filtered = [n for n in nodes_list if str(n.get("agent") or "") in allowed]

    if not filtered:
        return "", {
            "nodes_included": 0,
            "chars": 0,
            "skipped": "filter_excluded_all",
        }

    lines: List[str] = [
        "### Pipeline context graph (primary step memory, newest first)",
        "",
        "Текст узла: при уровне **full** в срез попадает прежде всего **L1** (или L0, если сжатия ещё нет); "
        "при **compact** — короче (L2 приоритетно); детали шага — через expand*-тулы. "
        "PREVIOUS RESULTS при graph-primary — только хвост последних шагов.",
        "",
    ]
    total_chars = 0
    included = 0
    for node in filtered[:max_nodes]:
        st = resolve_slice_node_body(node, compaction_level=compaction_level).strip()
        if not st:
            continue
        agent = str(node.get("agent") or "?")
        seq = node.get("ingest_seq")
        step_id = node.get("step_id")
        phase = node.get("phase")
        head = f"**{agent}** · seq={seq}"
        if step_id is not None:
            head += f" · step={step_id}"
        if phase:
            head += f" · {phase}"
        block = f"{head}\n{st}"
        add_len = len(block) + 4
        if total_chars + add_len > max_chars:
            lines.append("… *[context graph slice truncated by budget]*")
            break
        lines.append(block)
        lines.append("")
        total_chars += add_len
        included += 1

    text = "\n".join(lines).strip()
    if not text or included == 0:
        return "", {
            "nodes_included": 0,
            "chars": 0,
            "skipped": "empty_after_filter",
        }

    return text, {
        "nodes_included": included,
        "chars": len(text),
        "max_chars": max_chars,
        "compaction_level": compaction_level,
    }
