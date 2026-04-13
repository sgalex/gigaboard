from apps.backend.app.services.multi_agent.context_metrics import (
    summarize_context_efficiency_snapshot,
)


def test_summarize_context_efficiency_snapshot_basic():
    ctx = {
        "_context_graph_slice": "x" * 100,
        "_context_graph_slice_meta": {
            "nodes_included": 2,
            "chars": 100,
            "skipped": None,
            "max_chars": 5000,
            "compaction_level": "full",
        },
        "_context_graph_primary": True,
        "_agent_results_selected_budget": [{"agent": "a", "narrative": {"text": "hi"}}],
        "_context_selection_compaction_level": "full",
        "_context_selection_applied_for": "analyst",
        "context_graph": {"nodes": {"u1": {"id": "u1"}}},
        "_tool_result_cache": {"k": {}},
        "tool_request_cache_digest_lines": ["a", "b"],
    }
    s = summarize_context_efficiency_snapshot(ctx)
    assert s["graph_slice_text_len"] == 100
    assert s["graph_primary"] is True
    assert s["selected_budget_items"] == 1
    assert s["graph_nodes_total"] == 1
    assert s["tool_result_cache_entries"] == 1
    assert s["tool_digest_lines"] == 2
    assert "selected_budget_chars_est" in s
