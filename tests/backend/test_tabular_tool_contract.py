"""Unit-тесты enrich_task_for_tabular_tools / planner_tools_hint_block."""

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.multi_agent.tabular_tool_contract import (  # noqa: E402
    enrich_task_for_tabular_tools,
    planner_tools_hint_block,
)


def test_enrich_appends_when_tools_and_nodes():
    task = {"description": "Проанализируй маршруты"}
    ctx = {
        "tools_enabled": True,
        "selected_node_ids": ["uuid-1"],
    }
    out = enrich_task_for_tabular_tools("analyst", task, ctx)
    assert out is not task
    assert out.get("_tabular_tool_contract_applied") is True
    assert "readTableListFromContentNodes" in out["description"]
    assert "Проанализируй маршруты" in out["description"]


def test_enrich_skips_without_tools():
    task = {"description": "X"}
    ctx = {"tools_enabled": False, "selected_node_ids": ["a"]}
    out = enrich_task_for_tabular_tools("analyst", task, ctx)
    assert out["description"] == "X"


def test_enrich_skips_reporter():
    task = {"description": "Y"}
    ctx = {"tools_enabled": True, "content_node_id": "n1"}
    out = enrich_task_for_tabular_tools("reporter", task, ctx)
    assert out["description"] == "Y"


def test_planner_hint_empty_without_tools():
    assert planner_tools_hint_block({"tools_enabled": False}) == ""


def test_planner_hint_non_empty():
    text = planner_tools_hint_block(
        {
            "tools_enabled": True,
            "selected_node_ids": ["x"],
        }
    )
    assert "readTableData" in text or "readTableListFromContentNodes" in text
