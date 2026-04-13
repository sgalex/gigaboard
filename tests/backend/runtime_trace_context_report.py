"""
Сводка по JSONL-трейсам оркестратора для исследования эффективности контекста.

Запуск (из корня репозитория, после live-прогона с включённым MULTI_AGENT_TRACE_ENABLED):
  uv run python tests/backend/runtime_trace_context_report.py
  uv run python tests/backend/runtime_trace_context_report.py --file c:/Work/GigaBoard/apps/backend/logs/multi_agent_traces/orchestrator_trace_....jsonl

Смотрит события agent_call_start (context_estimates + context_efficiency),
tool_request / tool_result (в т.ч. expand* и context_pull_*).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter
from typing import Any, Dict, List


TRACE_DIR_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "apps",
    "backend",
    "logs",
    "multi_agent_traces",
)


def _iter_events(rows: List[Dict[str, Any]]):
    for row in rows:
        sid = row.get("session_id")
        for ev in row.get("events") or []:
            yield sid, ev


def analyze_rows(rows: List[Dict[str, Any]]) -> None:
    starts = 0
    max_ctx_total = 0
    max_ctx_agent = ""
    graph_slice_chars_samples: List[int] = []
    primary_true = 0
    budget_items_samples: List[int] = []
    tool_names = Counter()
    pull_kinds = Counter()
    pull_chars_total = 0
    expand_evaluated = 0
    expand_skipped = 0
    compaction_budget_events = 0
    graph_llm_compressed = 0
    graph_compress_partial = 0
    step_acceptance = 0
    step_acceptance_fail = 0
    step_acceptance_warn = 0

    for sid, ev in _iter_events(rows):
        if ev.get("event") == "agent_call_start":
            starts += 1
            d = ev.get("details") or {}
            ce = d.get("context_estimates") or {}
            ct = int(ce.get("context_total_chars") or 0)
            if ct > max_ctx_total:
                max_ctx_total = ct
                max_ctx_agent = str(ev.get("agent") or "")
            eff = d.get("context_efficiency") or {}
            gsl = eff.get("graph_slice_text_len")
            if isinstance(gsl, int):
                graph_slice_chars_samples.append(gsl)
            if eff.get("graph_primary"):
                primary_true += 1
            bi = eff.get("selected_budget_items")
            if isinstance(bi, int):
                budget_items_samples.append(bi)
        elif ev.get("event") == "tool_request":
            tn = (ev.get("details") or {}).get("tool_name") or ""
            if tn:
                tool_names[tn] += 1
        elif ev.get("event") == "tool_result" and (ev.get("details") or {}).get("success"):
            det = ev.get("details") or {}
            kind = det.get("context_pull_kind")
            if kind:
                pull_kinds[kind] += 1
                pull_chars_total += int(
                    det.get("context_pull_content_chars")
                    or det.get("context_pull_json_chars")
                    or det.get("context_pull_body_chars")
                    or 0
                )
        elif ev.get("event") == "expand_step_evaluated":
            expand_evaluated += 1
        elif ev.get("event") == "expand_step_skipped":
            expand_skipped += 1
        elif ev.get("event") == "context_compaction_budget":
            compaction_budget_events += 1
        elif ev.get("event") == "context_graph_llm_compressed":
            graph_llm_compressed += 1
            if (ev.get("details") or {}).get("partial"):
                graph_compress_partial += 1
        elif ev.get("event") == "step_acceptance":
            step_acceptance += 1
            det = ev.get("details") or {}
            st = det.get("level") or ev.get("status")
            if st == "fail":
                step_acceptance_fail += 1
            elif st == "warn":
                step_acceptance_warn += 1

    print("SESSIONS_IN_FILE", len(rows))
    print("AGENT_CALL_START_EVENTS", starts)
    print("MAX_CONTEXT_TOTAL_CHARS", max_ctx_total, "agent", max_ctx_agent)
    if graph_slice_chars_samples:
        print(
            "GRAPH_SLICE_TEXT_LEN avg",
            int(sum(graph_slice_chars_samples) / len(graph_slice_chars_samples)),
            "max",
            max(graph_slice_chars_samples),
        )
    print("GRAPH_PRIMARY_TRUE_COUNT", primary_true)
    if budget_items_samples:
        print(
            "SELECTED_BUDGET_ITEMS avg",
            round(sum(budget_items_samples) / len(budget_items_samples), 2),
            "max",
            max(budget_items_samples),
        )
    print("TOOL_REQUESTS_BY_NAME", dict(tool_names.most_common(20)))
    if pull_kinds:
        print("CONTEXT_PULL_BY_KIND", dict(pull_kinds))
        print("CONTEXT_PULL_EST_CHARS_SUM", pull_chars_total)
    print("EXPAND_STEP_EVALUATED", expand_evaluated)
    print("EXPAND_STEP_SKIPPED", expand_skipped)
    print("CONTEXT_COMPACTION_BUDGET_EVENTS", compaction_budget_events)
    print("CONTEXT_GRAPH_LLM_COMPRESSED", graph_llm_compressed)
    if graph_compress_partial:
        print("CONTEXT_GRAPH_LLM_COMPRESSED_PARTIAL", graph_compress_partial)
    if step_acceptance:
        print("STEP_ACCEPTANCE_EVENTS", step_acceptance)
        print("STEP_ACCEPTANCE_FAIL", step_acceptance_fail)
        print("STEP_ACCEPTANCE_WARN", step_acceptance_warn)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="конкретный JSONL", default=None)
    parser.add_argument(
        "--dir",
        help="каталог с orchestrator_trace_*.jsonl",
        default=TRACE_DIR_DEFAULT,
    )
    parser.add_argument(
        "--session-id",
        help="оставить только одну сессию (UUID из ответа API / SESSION_ID в live-скриптах)",
        default=None,
    )
    args = parser.parse_args()

    if args.file:
        paths = [args.file]
    else:
        paths = sorted(glob.glob(os.path.join(args.dir, "orchestrator_trace_*.jsonl")))
    if not paths:
        raise SystemExit(f"no trace files in {args.dir}")

    path = paths[-1]
    print("USING_TRACE", path)
    rows = [json.loads(x) for x in open(path, "r", encoding="utf-8") if x.strip()]
    if args.session_id:
        sid = args.session_id.strip()
        rows = [r for r in rows if str(r.get("session_id")) == sid]
        if not rows:
            raise SystemExit(f"no trace row for session_id={sid!r} in {path}")
        print("FILTER_SESSION", sid)
    analyze_rows(rows)


if __name__ == "__main__":
    main()
