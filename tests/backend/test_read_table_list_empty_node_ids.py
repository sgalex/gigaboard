"""
readTableListFromContentNodes / readTableData: ошибки как структурированный data (ok=false) для LLM.
"""

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.multi_agent.orchestrator import Orchestrator  # noqa: E402


@pytest.mark.asyncio
async def test_read_table_list_from_content_nodes_missing_node_ids_llm_error_payload():
    orch = Orchestrator()
    out = await orch._tool_read_table_list_from_content_node(
        arguments={},
        pipeline_context={},
    )
    assert out.get("ok") is False
    assert out.get("tool") == "readTableListFromContentNodes"
    assert out.get("message")
    assert out["tables_count"] == 0
    assert out["tables"] == []
    assert out["nodes"] == []


@pytest.mark.asyncio
async def test_read_table_list_from_content_nodes_empty_node_ids_list_llm_error_payload():
    orch = Orchestrator()
    out = await orch._tool_read_table_list_from_content_node(
        arguments={"nodeIds": []},
        pipeline_context={},
    )
    assert out.get("ok") is False
    assert out["tables_count"] == 0
    assert out["tables"] == []
    assert out["nodes"] == []


@pytest.mark.asyncio
async def test_read_table_data_missing_content_node_id_llm_error_payload():
    orch = Orchestrator()
    out = await orch._tool_read_table_data(
        arguments={"jsonDecl": {"table_id": "t1"}},
        pipeline_context={},
    )
    assert out.get("ok") is False
    assert out.get("tool") == "readTableData"
    assert "contentNodeId" in (out.get("message") or "")
    assert out.get("rows") == []
