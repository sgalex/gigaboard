from apps.backend.app.services.multi_agent.context_expand_tools import (
    run_expand_agent_result,
    run_expand_context_graph_node,
    run_expand_research_source_content,
)
from apps.backend.app.services.multi_agent.context_graph import init_context_graph, ingest_agent_result_dict


def test_expand_research_source_content_returns_body(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_EXPAND_TOOLS", "true")
    ctx = {
        "agent_results": [
            {
                "agent": "research",
                "status": "success",
                "sources": [
                    {"url": "https://ex.test/a", "title": "A", "content": "X" * 100},
                    {"url": "https://ex.test/b", "title": "B", "content": "hello page"},
                ],
            }
        ]
    }
    data, err = run_expand_research_source_content(
        ctx,
        {"agent_result_index": 0, "source_index": 1, "max_chars": 500},
    )
    assert err is None
    assert data is not None
    assert data["content"] == "hello page"
    assert data["source_index"] == 1


def test_expand_research_source_content_by_url(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_EXPAND_TOOLS", "true")
    ctx = {
        "agent_results": [
            {
                "agent": "research",
                "sources": [
                    {"url": "https://a.com", "content": "no"},
                    {"url": "https://b.com/page", "content": "yes"},
                ],
            }
        ]
    }
    data, err = run_expand_research_source_content(
        ctx,
        {"agent_result_index": 0, "url": "b.com"},
    )
    assert err is None
    assert data["content"] == "yes"


def test_expand_agent_result_json(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_EXPAND_TOOLS", "true")
    ctx = {
        "agent_results": [
            {
                "agent": "analyst",
                "status": "success",
                "narrative": {"text": "n1"},
                "findings": [{"text": "f"}],
            }
        ]
    }
    data, err = run_expand_agent_result(ctx, {"agent_result_index": 0})
    assert err is None
    assert data and "json" in data
    assert "analyst" in data["json"]


def test_expand_context_graph_node(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_EXPAND_TOOLS", "true")
    ctx: dict = {"agent_results": []}
    init_context_graph(ctx)
    ingest_agent_result_dict(
        ctx,
        {"agent": "planner", "status": "success", "narrative": {"text": "p"}},
        agent_result_index=0,
    )
    graph = ctx["context_graph"]
    nid = next(iter(graph["nodes"].keys()))
    data, err = run_expand_context_graph_node(ctx, {"node_id": nid, "body_level": "full"})
    assert err is None
    assert data["node_id"] == nid
    assert "body" in data


def test_expand_tools_respect_disable_flag(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_CONTEXT_EXPAND_TOOLS", "false")
    ctx = {"agent_results": [{"agent": "x", "sources": [{"content": "z"}]}]}
    _, err = run_expand_research_source_content(ctx, {"agent_result_index": 0})
    assert err and "disabled" in err.lower()
