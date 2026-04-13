from apps.backend.app.services.multi_agent.context_graph import (
    ensure_context_graph,
    init_context_graph,
    ingest_agent_result_dict,
)
from apps.backend.app.services.multi_agent.context_graph.ingest import build_l0_summary
from apps.backend.app.services.multi_agent.context_graph.compression import resolve_slice_node_body
from apps.backend.app.services.multi_agent.context_graph.slice import build_context_graph_slice
from apps.backend.app.services.multi_agent.context_selection import select_context_for_step


def test_init_context_graph_idempotent():
    ctx: dict = {}
    g1 = init_context_graph(ctx)
    assert g1["version"] == 1
    assert g1["nodes"] == {}
    assert g1["edges"] == []
    g2 = init_context_graph(ctx)
    assert g2 is g1


def test_ensure_context_graph_creates_when_missing():
    ctx: dict = {}
    g = ensure_context_graph(ctx)
    assert "context_graph" in ctx
    assert g["version"] == 1


def test_resolve_slice_node_body_by_compaction_level():
    node = {
        "level": 0,
        "summary_text": "LONG " * 50,
        "l1_summary": "medium summary",
        "l2_one_liner": "Short one-liner.",
    }
    assert resolve_slice_node_body(node, compaction_level="minimal") == "Short one-liner."
    assert resolve_slice_node_body(node, compaction_level="compact") == "Short one-liner."
    full = resolve_slice_node_body(node, compaction_level="full")
    assert "medium summary" in full
    assert "Short one-liner" in full
    assert "LONG" not in full


def test_resolve_slice_node_body_full_falls_back_to_l0_without_l1():
    node = {
        "level": 0,
        "summary_text": "only l0 body",
        "l2_one_liner": "anchor.",
    }
    full = resolve_slice_node_body(node, compaction_level="full")
    assert "only l0 body" in full
    assert "anchor" in full


def test_build_l0_summary_covers_agent_and_narrative():
    r = {
        "agent": "analyst",
        "status": "success",
        "narrative": {"text": "Hello world"},
        "findings": [{"text": "f1"}],
    }
    s = build_l0_summary(r)
    assert "analyst" in s
    assert "Hello world" in s
    assert "f1" in s


def test_ingest_always_adds_l0_node():
    ctx = {"agent_results": []}
    init_context_graph(ctx)
    r = {"agent": "discovery", "status": "success", "narrative": {"text": "x"}}
    nid = ingest_agent_result_dict(ctx, r, agent_result_index=0)
    assert nid is not None
    assert len(ensure_context_graph(ctx)["nodes"]) == 1


def test_ingest_adds_l0_node_with_step_metadata():
    ctx = {"agent_results": []}
    init_context_graph(ctx)
    r = {"agent": "reporter", "status": "success", "narrative": {"text": "Final"}}
    nid = ingest_agent_result_dict(ctx, r, agent_result_index=0, step_id="2", phase="execute_step")
    assert nid is not None
    nodes = ensure_context_graph(ctx)["nodes"]
    assert len(nodes) == 1
    n = next(iter(nodes.values()))
    assert n["level"] == 0
    assert n["agent"] == "reporter"
    assert n["agent_result_index"] == 0
    assert n["step_id"] == "2"
    assert n["phase"] == "execute_step"
    assert "Final" in n["summary_text"]


def test_select_context_for_step_includes_graph_slice():
    ctx = {
        "agent_results": [],
        "chat_history": [],
    }
    init_context_graph(ctx)
    ingest_agent_result_dict(
        ctx,
        {"agent": "planner", "status": "success", "narrative": {"text": "planned"}},
        agent_result_index=0,
    )
    out = select_context_for_step("analyst", ctx, task_type="analysis")
    assert "_context_graph_slice" in out
    assert "_context_graph_slice_meta" in out
    assert "planner" in (out.get("_context_graph_slice") or "")


def test_build_context_graph_slice_newest_first_and_budget(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_GRAPH_SLICE_MAX_CHARS", "2000")
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_GRAPH_SLICE_MAX_NODES", "10")
    ctx = {"agent_results": [{}]}
    init_context_graph(ctx)
    ingest_agent_result_dict(
        ctx,
        {"agent": "discovery", "status": "success", "narrative": {"text": "first"}},
        agent_result_index=0,
    )
    ingest_agent_result_dict(
        ctx,
        {"agent": "analyst", "status": "success", "narrative": {"text": "second"}},
        agent_result_index=1,
    )
    text, meta = build_context_graph_slice(
        consumer_agent="analyst",
        pipeline_context=ctx,
        compaction_level="full",
    )
    assert meta["nodes_included"] >= 1
    assert "analyst" in text or "discovery" in text
    assert meta["chars"] <= 2500


def test_build_l0_summary_includes_tables_digest():
    r = {
        "agent": "structurizer",
        "status": "success",
        "tables": [
            {
                "name": "t1",
                "columns": [{"name": "a"}, {"name": "b"}],
                "rows": [{"a": 1}],
                "row_count": 1,
            }
        ],
    }
    s = build_l0_summary(r)
    assert "tables_digest" in s
    assert "t1" in s


def test_select_context_graph_primary_truncates_tail(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_GRAPH_PRIMARY", "true")
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_GRAPH_PRIMARY_TAIL_ITEMS", "1")
    ctx = {
        "agent_results": [
            {"agent": "discovery", "status": "success", "narrative": {"text": "a"}},
            {"agent": "research", "status": "success", "narrative": {"text": "b"}},
            {"agent": "analyst", "status": "success", "narrative": {"text": "c"}},
        ],
        "chat_history": [],
    }
    init_context_graph(ctx)
    for i, r in enumerate(ctx["agent_results"]):
        ingest_agent_result_dict(ctx, r, agent_result_index=i)
    out = select_context_for_step("analyst", ctx, task_type="analysis")
    assert out.get("_context_graph_primary") is True
    assert len(out.get("agent_results") or []) == 1
    assert (out.get("agent_results") or [{}])[0].get("agent") == "analyst"
    assert len(out.get("_agent_results_selected_budget") or []) >= 1


def test_ingest_respects_max_nodes(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_GRAPH_MAX_NODES", "1")
    ctx = {"agent_results": []}
    init_context_graph(ctx)
    r1 = {"agent": "a", "status": "success"}
    r2 = {"agent": "b", "status": "success"}
    assert ingest_agent_result_dict(ctx, r1, agent_result_index=0) is not None
    assert ingest_agent_result_dict(ctx, r2, agent_result_index=1) is None
    assert len(ensure_context_graph(ctx)["nodes"]) == 1
