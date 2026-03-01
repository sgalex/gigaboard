"""
Integration pipeline тесты V2 (Phase 7.4–7.7).

Тестируют полный pipeline: Orchestrator → Agents → ControllerResult.
Используют реальный Orchestrator с mock GigaChatService (без Redis).

7.4: Research pipeline (structurizer → analyst → reporter)
7.5: Transform pipeline (TransformationController → Orchestrator → TransformCodexAgent)
7.6: Widget pipeline (WidgetController → Orchestrator → WidgetCodexAgent)
7.7: Discussion pipeline (TransformationController с narrative instead of code)
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from apps.backend.app.services.multi_agent.orchestrator import Orchestrator
from apps.backend.app.services.multi_agent.schemas.agent_payload import AgentPayload
from apps.backend.app.services.controllers.base_controller import ControllerResult


# ============================================================
# Helpers
# ============================================================

def _make_mock_gigachat():
    """Create a MagicMock that behaves like GigaChatService."""
    svc = MagicMock()
    svc.chat_completion = AsyncMock(return_value="{}")
    return svc


def _make_mock_message_bus():
    """Create a MagicMock that behaves like AgentMessageBus."""
    bus = MagicMock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    bus.wait_for_response = AsyncMock()
    bus.store_session_result = AsyncMock()
    bus.clear_session_results = AsyncMock()
    return bus


async def _setup_orchestrator(
    gigachat_mock,
    agent_names: list[str],
) -> Orchestrator:
    """Create an Orchestrator with real agents and mocked dependencies.

    Bypasses `initialize()` — no Redis required.
    Injects `gigachat_mock` as `self.gigachat` so all agents receive it.
    """
    orch = Orchestrator(
        gigachat_api_key="test-key",
        enable_agents=agent_names,
        adaptive_planning=False,  # disable replan to simplify test
    )

    # Inject mock dependencies
    orch.gigachat = gigachat_mock
    orch.message_bus = _make_mock_message_bus()

    # Manually initialise real agents (same logic as _initialize_agents but
    # with mocks already in place)
    await orch._initialize_agents()
    orch.is_initialized = True

    return orch


def _setup_gigachat_responses(mock_gigachat, responses: list[str]):
    """Configure mock to return responses sequentially.

    Args:
        responses: ordered list of raw LLM reply strings.
    """
    call_idx = {"n": 0}

    async def _side_effect(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        if idx < len(responses):
            return responses[idx]
        return json.dumps({"status": "success"})

    mock_gigachat.chat_completion = AsyncMock(side_effect=_side_effect)


# ============================================================
# 7.4: Research Pipeline
# ============================================================

class TestResearchPipeline:
    """
    Full research pipeline:
    Planner → structurizer → analyst → reporter → validator
    """

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """Orchestrator should run full research pipeline end-to-end."""
        gc = _make_mock_gigachat()

        # Responses: planner, structurizer, analyst, reporter, validator,
        #            (+ replan query — but adaptive_planning=False skips it)
        _setup_gigachat_responses(gc, [
            # 1. Planner
            json.dumps({
                "steps": [
                    {"step_id": "1", "agent": "structurizer", "task": {"description": "Parse data"}},
                    {"step_id": "2", "agent": "analyst", "task": {"description": "Analyze"}, "depends_on": ["1"]},
                    {"step_id": "3", "agent": "reporter", "task": {"description": "Report"}, "depends_on": ["2"]},
                ],
            }),
            # 2. Structurizer
            json.dumps({
                "tables": [{
                    "name": "data",
                    "columns": [{"name": "region", "type": "string"}, {"name": "sales", "type": "int"}],
                    "rows": [["US", 1000], ["EU", 2000]],
                }],
                "extraction_confidence": 0.9,
                "notes": "Extracted 1 table",
            }),
            # 3. Analyst
            json.dumps({
                "analysis": "Sales in EU are 2x higher than US",
                "insights": [{"type": "insight", "text": "EU leads sales"}],
            }),
            # 4. Reporter
            "## Sales Report\n\nEU sales are 2x higher than US sales.",
            # 5. Validator
            json.dumps({
                "valid": True,
                "confidence": 0.95,
                "message": "Result matches request",
                "issues": [],
            }),
        ])

        orch = await _setup_orchestrator(
            gc,
            ["planner", "structurizer", "analyst", "reporter", "validator"],
        )

        result = await orch.process_request(
            user_request="Analyze sales data by region",
            board_id="test-board",
            context={
                "content_nodes_data": [
                    {"content": "US sales 1000, EU sales 2000"}
                ],
            },
        )

        assert result["status"] == "success"
        assert "results" in result
        assert result.get("plan") is not None
        results = result["results"]
        # Each executed agent should appear in results
        assert "structurizer" in results
        assert "analyst" in results
        assert "reporter" in results


# ============================================================
# 7.5: Transform Pipeline
# ============================================================

class TestTransformPipeline:
    """
    Transform pipeline:
    TransformationController → Orchestrator → planner → codex → validator
    """

    @pytest.mark.asyncio
    async def test_transform_generates_code(self):
        """TransformationController should return executable Python code."""
        gc = _make_mock_gigachat()
        code = "import pandas as pd\ndf_filtered = df[df['amount'] > 100]"

        _setup_gigachat_responses(gc, [
            # 1. Planner
            json.dumps({
                "steps": [
                    {"step_id": "1", "agent": "transform_codex", "task": {
                        "description": "Filter amount > 100",
                        "purpose": "transformation",
                    }},
                ],
            }),
            # 2. TransformCodex
            json.dumps({
                "transformation_code": code,
                "description": "Filter rows where amount > 100",
                "output_schema": [{"name": "amount", "type": "float"}],
            }),
            # 3. Validator
            json.dumps({
                "valid": True,
                "confidence": 0.9,
                "message": "OK",
                "issues": [],
            }),
        ])

        orch = await _setup_orchestrator(gc, ["planner", "transform_codex", "validator"])

        from apps.backend.app.services.controllers.transformation_controller import (
            TransformationController,
        )
        controller = TransformationController(orch)

        result = await controller.process_request(
            user_message="Фильтруй amount > 100",
            context={
                "board_id": "test-board",
                "input_tables": [{
                    "name": "sales",
                    "columns": [{"name": "amount", "type": "float"}],
                    "rows": [[50.0], [150.0], [200.0]],
                    "row_count": 3,
                    "column_count": 1,
                }],
                "skip_execution": True,
            },
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "success"
        assert result.code is not None
        assert "df_filtered" in result.code
        assert result.mode == "transformation"

    @pytest.mark.asyncio
    async def test_transform_error_propagation(self):
        """Should handle agent errors gracefully (empty code → discussion)."""
        gc = _make_mock_gigachat()

        _setup_gigachat_responses(gc, [
            # 1. Planner
            json.dumps({
                "steps": [
                    {"step_id": "1", "agent": "transform_codex", "task": {
                        "description": "test",
                        "purpose": "transformation",
                    }},
                ],
            }),
            # 2. TransformCodex — empty response
            json.dumps({
                "transformation_code": "",
                "description": "",
            }),
        ])

        orch = await _setup_orchestrator(gc, ["planner", "transform_codex"])

        from apps.backend.app.services.controllers.transformation_controller import (
            TransformationController,
        )
        controller = TransformationController(orch)

        result = await controller.process_request(
            user_message="test",
            context={"board_id": "b1", "skip_execution": True},
        )

        assert isinstance(result, ControllerResult)
        # Empty code should result in error or discussion mode
        assert result.status == "error" or result.mode == "discussion"


# ============================================================
# 7.6: Widget Pipeline
# ============================================================

class TestWidgetPipeline:
    """
    Widget pipeline:
    WidgetController → Orchestrator → planner → codex → validator
    """

    @pytest.mark.asyncio
    async def test_widget_generates_html(self):
        """WidgetController should return HTML widget code."""
        gc = _make_mock_gigachat()
        widget_html = (
            "<html><head><title>Sales Chart</title></head>"
            "<body><div id='chart'><h2>Sales by Region</h2>"
            "<canvas id='barChart'></canvas></div></body></html>"
        )

        _setup_gigachat_responses(gc, [
            # 1. Planner
            json.dumps({
                "steps": [
                    {"step_id": "1", "agent": "transform_codex", "task": {
                        "description": "Create bar chart",
                        "purpose": "widget",
                        "widget_type": "chart",
                    }},
                ],
            }),
            # 2. TransformCodex
            json.dumps({
                "widget_code": widget_html,
                "widget_name": "Sales Chart",
                "widget_type": "bar",
                "description": "Bar chart of sales by region",
            }),
            # 3. Validator
            json.dumps({
                "valid": True,
                "confidence": 0.9,
                "message": "OK",
                "issues": [],
            }),
        ])

        orch = await _setup_orchestrator(gc, ["planner", "transform_codex", "validator"])

        from apps.backend.app.services.controllers.widget_controller import (
            WidgetController,
        )
        controller = WidgetController(orch)

        result = await controller.process_request(
            user_message="Построй гистограмму продаж",
            context={
                "board_id": "test-board",
                "content_data": {
                    "tables": [{
                        "name": "sales",
                        "columns": [{"name": "region"}, {"name": "amount"}],
                        "rows": [["US", 1000], ["EU", 2000]],
                    }]
                },
            },
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "success"
        assert result.widget_code is not None
        assert "<html>" in result.widget_code or "<div" in result.widget_code


# ============================================================
# 7.7: Discussion Pipeline
# ============================================================

class TestDiscussionPipeline:
    """
    Discussion mode:
    TransformationController → Orchestrator → planner → analyst → reporter (no code)
    """

    @pytest.mark.asyncio
    async def test_discussion_returns_narrative(self):
        """Discussion should return narrative text without code_blocks."""
        gc = _make_mock_gigachat()

        _setup_gigachat_responses(gc, [
            # 1. Planner
            json.dumps({
                "steps": [
                    {"step_id": "1", "agent": "analyst", "task": {"description": "Explain filtering"}},
                    {"step_id": "2", "agent": "reporter", "task": {"description": "Report"}, "depends_on": ["1"]},
                ],
            }),
            # 2. Analyst
            json.dumps({
                "analysis": "Filtering removes rows that don't match a condition.",
                "insights": [],
            }),
            # 3. Reporter
            "## Filtering Explained\n\nFiltering removes rows that don't match a condition. "
            "You can use `df[df['column'] > value]` in pandas.",
        ])

        orch = await _setup_orchestrator(gc, ["planner", "analyst", "reporter"])

        from apps.backend.app.services.controllers.transformation_controller import (
            TransformationController,
        )
        controller = TransformationController(orch)

        result = await controller.process_request(
            user_message="Объясни, как работает фильтрация данных",
            context={
                "board_id": "b1",
                "skip_execution": True,
            },
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "success"
        assert result.mode == "discussion"
        assert result.narrative is not None
        assert len(result.narrative) > 0
