import copy

from apps.backend.app.services.multi_agent.context_selection import (
    select_agent_results_for_prompt,
    select_context_for_step,
)


def _make_result(idx: int, content_len: int = 32) -> dict:
    return {
        "agent": "research",
        "status": "success",
        "narrative": {"text": f"result-{idx}"},
        "findings": [{"type": "insight", "text": f"f-{idx}"}],
        "sources": [
            {
                "url": f"https://example.com/{idx}",
                "title": f"title-{idx}",
                "content": "x" * content_len,
            }
        ],
        "tables": [
            {
                "name": f"t-{idx}",
                "columns": [{"name": "c1", "type": "string"}],
                "rows": [{"c1": f"v-{idx}"}],
            }
        ],
        "code_blocks": [{"language": "python", "code": "print('x')"}],
        "step_id": str(idx),
    }


def test_select_agent_results_for_prompt_analyst_keeps_latest_and_strips_code_blocks():
    agent_results = [_make_result(i) for i in range(50)]

    selected = select_agent_results_for_prompt("analyst", agent_results)

    # analyst default budget: max 30 items
    assert len(selected) == 30
    # chronological order is preserved for selected tail
    assert selected[0]["step_id"] == "20"
    assert selected[-1]["step_id"] == "49"
    # analyst profile should not include code blocks
    assert all("code_blocks" not in item for item in selected)


def test_select_agent_results_for_prompt_planner_task_aware_budgets():
    # keep each item tiny so selection is constrained by max_items, not chars
    agent_results = [_make_result(i, content_len=8) for i in range(60)]

    selected_create = select_agent_results_for_prompt(
        "planner",
        agent_results,
        task_type="create_plan",
    )
    selected_replan = select_agent_results_for_prompt(
        "planner",
        agent_results,
        task_type="replan",
    )

    assert len(selected_create) == 20
    assert len(selected_replan) == 40
    assert selected_create[0]["step_id"] == "40"
    assert selected_replan[0]["step_id"] == "20"


def test_select_context_for_step_sanitizes_chat_and_previews():
    pipeline_context = {
        "agent_results": [_make_result(i, content_len=6000) for i in range(5)],
        "chat_history": [{"role": "user", "content": f"m-{i}-" + ("z" * 1000)} for i in range(20)],
        "input_data_preview": {
            f"table_{i}": {
                "node_name": "node",
                "table_name": f"table_{i}",
                "row_count": 100,
                "columns": [{"name": f"c{j}", "type": "string"} for j in range(30)],
                "sample_rows": [
                    {f"c{j}": ("x" * 300) for j in range(30)}
                    for _ in range(10)
                ],
            }
            for i in range(6)
        },
        "catalog_data_preview": {
            f"cat_{i}": {
                "node_name": "node",
                "table_name": f"cat_{i}",
                "row_count": 200,
                "columns": [{"name": f"k{j}", "type": "number"} for j in range(20)],
            }
            for i in range(12)
        },
    }
    original = copy.deepcopy(pipeline_context)

    selected_ctx = select_context_for_step(
        "planner",
        pipeline_context,
        task_type="replan",
    )

    assert selected_ctx["_context_selection_applied_for"] == "planner"
    assert selected_ctx["_context_selection_task_type"] == "replan"
    assert selected_ctx["_context_selection_budget_items"] == 40
    assert selected_ctx["_context_selection_budget_chars"] == 140000
    # chat history limited to tail
    assert len(selected_ctx["chat_history"]) == 12
    assert selected_ctx["chat_history"][0]["content"].endswith("... [truncated]")
    # preview maps are limited
    assert len(selected_ctx["input_data_preview"]) == 3
    assert len(selected_ctx["catalog_data_preview"]) == 8
    # columns are also limited
    first_input = next(iter(selected_ctx["input_data_preview"].values()))
    first_catalog = next(iter(selected_ctx["catalog_data_preview"].values()))
    assert len(first_input["columns"]) == 20
    assert len(first_catalog["columns"]) == 12
    # preview sample rows are preserved (and compacted) for factual QA
    assert 1 <= len(first_input["sample_rows"]) <= 4
    first_row = first_input["sample_rows"][0]
    assert isinstance(first_row, dict)
    assert len(first_row) == 20
    assert all(isinstance(v, str) and v.endswith("... [truncated]") for v in first_row.values())
    # original context should remain untouched
    assert pipeline_context == original


def test_select_context_for_step_planner_task_budget_markers():
    ctx = {"agent_results": [_make_result(i, content_len=8) for i in range(60)]}

    create_ctx = select_context_for_step("planner", ctx, task_type="create_plan")
    replan_ctx = select_context_for_step("planner", ctx, task_type="replan")

    assert create_ctx["_context_selection_budget_items"] == 20
    assert create_ctx["_context_selection_budget_chars"] == 70000
    assert replan_ctx["_context_selection_budget_items"] == 40
    assert replan_ctx["_context_selection_budget_chars"] == 140000
    assert len(create_ctx["agent_results"]) == 20
    assert len(replan_ctx["agent_results"]) == 40


def test_select_context_for_step_compaction_level_minimal_reduces_budget_and_chat():
    ctx = {
        "agent_results": [_make_result(i, content_len=32) for i in range(80)],
        "chat_history": [{"role": "user", "content": "x" * 1200} for _ in range(30)],
    }
    selected = select_context_for_step(
        "planner",
        ctx,
        task_type="replan",
        compaction_level="minimal",
    )

    assert selected["_context_selection_compaction_level"] == "minimal"
    assert selected["_context_selection_budget_items"] < 40
    assert selected["_context_selection_budget_chars"] < 140000
    assert len(selected["chat_history"]) == 6
    assert len(selected["agent_results"]) <= selected["_context_selection_budget_items"]


def test_select_context_for_step_unknown_agent_returns_context_without_selection_marker():
    ctx = {"agent_results": [_make_result(1)], "chat_history": [{"role": "user", "content": "hello"}]}
    selected = select_context_for_step("some_unknown_agent", ctx, task_type="search")

    assert selected == ctx
    assert "_context_selection_applied_for" not in selected


def test_select_context_for_step_discovery_now_uses_budget_profile():
    ctx = {
        "agent_results": [_make_result(i, content_len=16) for i in range(60)],
        "chat_history": [{"role": "user", "content": "hello"} for _ in range(20)],
    }
    selected = select_context_for_step("discovery", ctx, task_type="search")

    assert selected["_context_selection_applied_for"] == "discovery"
    assert selected["_context_selection_budget_items"] == 20
    assert selected["_context_selection_budget_chars"] == 90000
    assert len(selected["agent_results"]) == 20
    assert len(selected["chat_history"]) == 12


def test_select_context_for_step_runtime_options_override_budget():
    ctx = {"agent_results": [_make_result(i, content_len=8) for i in range(40)]}
    selected = select_context_for_step(
        "planner",
        ctx,
        task_type="create_plan",
        runtime_options={"max_items": 7, "max_total_chars": 15000},
    )

    assert selected["_context_selection_budget_items"] == 7
    assert selected["_context_selection_budget_chars"] == 15000
    assert len(selected["agent_results"]) == 7


def test_select_context_for_step_keep_tabular_skips_strip_under_force_tool():
    """Transformation/Widget controllers set keep_tabular_context_in_prompt."""
    ctx = {
        "agent_results": [_make_result(1)],
        "force_tool_data_access": True,
        "keep_tabular_context_in_prompt": True,
        "input_data_preview": {
            "sales": {
                "node_name": "n",
                "table_name": "sales",
                "row_count": 2,
                "columns": [{"name": "a", "type": "string"}],
                "sample_rows": [{"a": "1"}],
            }
        },
        "content_nodes_data": [
            {"id": "u1", "name": "node", "tables": [{"name": "t", "rows": [{"x": 1}]}]}
        ],
    }
    selected = select_context_for_step("analyst", ctx)
    assert selected.get("input_data_preview")
    assert "sales" in selected["input_data_preview"]
    assert selected["content_nodes_data"][0].get("tables")
    assert not selected.get("_tabular_context_stripped")
