"""
Unit тесты core-агентов V2 (Phase 7.2).

Каждый агент тестируется с mock GigaChatService.
Проверяется:
- Формат AgentPayload на выходе
- Чтение agent_results из context
- Обработка ошибок (error payload)
- Основная логика формирования промпта

НЕ требует реальных API ключей / LLM.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from apps.backend.app.services.multi_agent.schemas.agent_payload import (
    AgentPayload,
    CodeBlock,
    Narrative,
    PayloadContentTable,
    Column,
    Finding,
    Plan,
    PlanStep,
    ValidationResult,
    Source,
)


# ============================================================
# Fixtures — Mock GigaChat & MessageBus
# ============================================================

@pytest.fixture
def mock_message_bus():
    """Mock AgentMessageBus — no Redis needed."""
    bus = MagicMock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    bus.wait_for_response = AsyncMock()
    return bus


@pytest.fixture
def mock_gigachat():
    """Mock GigaChatService — returns configurable responses."""
    service = MagicMock()
    service.chat_completion = AsyncMock(return_value="mock response")
    service.chat_completion_raw = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="mock response"))]
    ))
    return service


# ============================================================
# PlannerAgent
# ============================================================

class TestPlannerAgent:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        from apps.backend.app.services.multi_agent.agents.planner import PlannerAgent
        return PlannerAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    @pytest.mark.asyncio
    async def test_process_task_returns_agent_payload(self, agent, mock_gigachat):
        """PlannerAgent should return AgentPayload with plan."""
        # PlannerAgent requires task type='create_plan' and 'user_request'
        plan_json = json.dumps({
            "steps": [
                {"step_id": "1", "agent": "analyst", "task": {"description": "Analyze data"}},
                {"step_id": "2", "agent": "transform_codex", "task": {"description": "Generate code"}, "depends_on": ["1"]},
            ],
            "estimated_total_time": "5s"
        })
        mock_gigachat.chat_completion = AsyncMock(return_value=plan_json)

        task = {
            "type": "create_plan",
            "user_request": "Filter sales by region",
            "description": "Filter sales data by region",
        }
        context = {
            "board_id": "board-1",
            "input_data": {"tables": [{"name": "sales", "columns": [{"name": "region", "type": "string"}], "rows": []}]},
        }

        result = await agent.process_task(task, context)

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.agent == "planner"
        assert result.plan is not None
        assert len(result.plan.steps) >= 1

    @pytest.mark.asyncio
    async def test_process_task_error_handling(self, agent, mock_gigachat):
        """PlannerAgent should return error payload on exception."""
        mock_gigachat.chat_completion = AsyncMock(side_effect=Exception("LLM unavailable"))

        task = {"type": "create_plan", "user_request": "test", "description": "test"}
        result = await agent.process_task(task, {})

        assert isinstance(result, AgentPayload)
        assert result.status == "error"
        assert result.agent == "planner"


# ============================================================
# StructurizerAgent
# ============================================================

class TestStructurizerAgent:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        from apps.backend.app.services.multi_agent.agents.structurizer import StructurizerAgent
        return StructurizerAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    @pytest.mark.asyncio
    async def test_returns_tables(self, agent, mock_gigachat):
        """StructurizerAgent should return PayloadContentTable in result."""
        mock_response = json.dumps({
            "tables": [{
                "name": "companies",
                "columns": [{"name": "name", "type": "string"}, {"name": "stars", "type": "int"}],
                "rows": [["Django", 71000], ["Flask", 65000]],
            }],
            "extraction_confidence": 0.9,
            "notes": "Extracted 1 table"
        })
        mock_gigachat.chat_completion = AsyncMock(return_value=mock_response)

        task = {"description": "Extract data", "raw_content": "Django 71k stars, Flask 65k stars"}
        result = await agent.process_task(task, {})

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.has_tables
        assert len(result.tables) >= 1
        assert result.tables[0].name == "companies"

    @pytest.mark.asyncio
    async def test_no_content(self, agent):
        """Should handle missing content gracefully."""
        result = await agent.process_task({"description": "extract"}, {})

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.metadata.get("extraction_confidence") == 0.0

    @pytest.mark.asyncio
    async def test_reads_previous_results_sources(self, agent, mock_gigachat):
        """Should extract raw_content from previous_results sources."""
        mock_gigachat.chat_completion = AsyncMock(return_value=json.dumps({
            "tables": [],
            "extraction_confidence": 0.5,
        }))

        context = {
            "agent_results": [
                {
                    "agent": "research",
                    "sources": [
                        {"url": "https://example.com", "content": "Some data here", "fetched": True}
                    ]
                }
            ]
        }
        result = await agent.process_task({"description": "parse"}, context)
        assert result.status == "success"
        # Should have called LLM with the source content
        mock_gigachat.chat_completion.assert_called_once()

    def test_extracts_tool_requests_from_json(self):
        from apps.backend.app.services.multi_agent.agents.structurizer import StructurizerAgent

        parsed = {
            "tool_requests": [
                {
                    "tool_name": "readTableData",
                    "arguments": {"jsonDecl": {"contentNodeId": "n1", "tableId": "t1", "offset": 0, "limit": 20}},
                }
            ]
        }
        reqs = StructurizerAgent._extract_tool_requests(parsed)
        assert len(reqs) == 1
        assert reqs[0].tool_name == "readTableData"


# ============================================================
# AnalystAgent
# ============================================================

class TestAnalystAgent:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        from apps.backend.app.services.multi_agent.agents.analyst import AnalystAgent
        return AnalystAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    @pytest.mark.asyncio
    async def test_returns_payload(self, agent, mock_gigachat):
        """AnalystAgent should return AgentPayload."""
        mock_gigachat.chat_completion = AsyncMock(return_value=json.dumps({
            "analysis": "Revenue growing",
            "insights": [{"type": "insight", "text": "Revenue is up 15%"}],
            "recommendations": [{"type": "recommendation", "text": "Focus on EU market"}],
        }))

        task = {
            "description": "Analyze sales trends",
            "data": {"tables": [{"name": "sales", "columns": [{"name": "revenue", "type": "int"}], "rows": [{"revenue": 100}]}]},
        }
        result = await agent.process_task(task, {})

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.agent == "analyst"

    @pytest.mark.asyncio
    async def test_error_returns_error_payload(self, agent, mock_gigachat):
        mock_gigachat.chat_completion = AsyncMock(side_effect=RuntimeError("API error"))
        result = await agent.process_task({"description": "test"}, {})
        assert result.status == "error"

    def test_extracts_tool_requests_from_json(self):
        from apps.backend.app.services.multi_agent.agents.analyst import AnalystAgent

        parsed = {
            "tool_requests": [
                {
                    "tool_name": "readTableListFromContentNode",
                    "arguments": {"contentNodeId": "n1"},
                }
            ]
        }
        reqs = AnalystAgent._extract_tool_requests(parsed)
        assert len(reqs) == 1
        assert reqs[0].tool_name == "readTableListFromContentNode"


# ============================================================
# TransformCodexAgent
# ============================================================

class TestTransformCodexAgent:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        from apps.backend.app.services.multi_agent.agents.transform_codex import TransformCodexAgent
        return TransformCodexAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    @pytest.mark.asyncio
    async def test_returns_code_blocks(self, agent, mock_gigachat):
        """TransformCodexAgent should return code_blocks in AgentPayload."""
        code = "import pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\ndf_filtered = df[df['a'] > 1]"
        # TransformCodexAgent expects JSON with 'transformation_code' key
        mock_gigachat.chat_completion = AsyncMock(return_value=json.dumps({
            "transformation_code": code,
            "description": "Filter rows where a > 1",
            "output_schema": [{"name": "a", "type": "int"}],
        }))

        task = {
            "description": "Filter rows where a > 1",
            "purpose": "transformation",
            "input_schemas": [{"name": "a", "type": "int"}],
        }
        result = await agent.process_task(task, {})

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.has_code
        cb = result.get_code("transformation")
        assert cb is not None
        assert "df_filtered" in cb.code

    @pytest.mark.asyncio
    async def test_widget_purpose(self, agent, mock_gigachat):
        """TransformCodexAgent should handle widget code generation (backward compat)."""
        html_code = "<html><body><h1>Chart</h1></body></html>"
        # TransformCodexAgent expects JSON with 'widget_code' key for widget purpose
        mock_gigachat.chat_completion = AsyncMock(return_value=json.dumps({
            "widget_code": html_code,
            "widget_name": "Sales Chart",
            "widget_type": "chart",
            "description": "Bar chart of sales",
        }))

        task = {
            "description": "Create a bar chart",
            "purpose": "widget",
            "widget_type": "chart",
        }
        result = await agent.process_task(task, {})

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.has_code
        cb = result.get_code("widget")
        assert cb is not None
        assert "<html>" in cb.code

    @pytest.mark.asyncio
    async def test_normalizes_dict_columns_from_input_preview(self, agent, mock_gigachat):
        """TransformCodexAgent should handle input_data_preview columns as list[dict]."""
        code = "import pandas as pd\ndf = df.copy()\ndf_out = df"
        mock_gigachat.chat_completion = AsyncMock(return_value=json.dumps({
            "transformation_code": code,
            "description": "No-op transform",
            "output_schema": [{"name": "route", "type": "string"}],
        }))

        task = {
            "description": "Return input as is",
            "purpose": "transformation",
        }
        context = {
            "input_data_preview": {
                "routes": {
                    "columns": [
                        {"name": "route", "type": "string"},
                        {"name": "distance_km", "type": "float"},
                    ],
                    "dtypes": {"distance_km": "float64"},
                    "row_count": 2,
                    "sample_rows": [
                        {"route": "A-B", "distance_km": 12.5},
                        {"route": "B-C", "distance_km": 8.1},
                    ],
                }
            }
        }

        result = await agent.process_task(task, context)
        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.has_code

    def test_extracts_tool_requests_from_json(self):
        from apps.backend.app.services.multi_agent.agents.transform_codex import TransformCodexAgent

        parsed = {
            "tool_requests": [
                {
                    "tool_name": "readTableListFromContentNode",
                    "arguments": {"contentNodeId": "node-1"},
                },
                {
                    "tool_name": "readTableData",
                    "arguments": {
                        "jsonDecl": {
                            "contentNodeId": "node-1",
                            "tableId": "sales",
                            "offset": 0,
                            "limit": 20,
                        }
                    },
                },
            ]
        }

        reqs = TransformCodexAgent._extract_tool_requests(parsed)
        assert len(reqs) == 2
        assert reqs[0].tool_name == "readTableListFromContentNode"
        assert reqs[1].tool_name == "readTableData"


def test_widget_codex_extracts_tool_requests_from_json():
    from apps.backend.app.services.multi_agent.agents.widget_codex import WidgetCodexAgent

    parsed = {
        "tool_requests": [
            {
                "tool_name": "readTableData",
                "arguments": {"jsonDecl": {"contentNodeId": "n1", "tableId": "sales", "offset": 0, "limit": 10}},
            }
        ]
    }
    reqs = WidgetCodexAgent._extract_tool_requests(parsed)
    assert len(reqs) == 1
    assert reqs[0].tool_name == "readTableData"


# ============================================================
# ReporterAgent
# ============================================================

class TestReporterAgent:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        from apps.backend.app.services.multi_agent.agents.reporter import ReporterAgent
        return ReporterAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    @pytest.mark.asyncio
    async def test_returns_narrative(self, agent, mock_gigachat):
        """ReporterAgent should produce narrative text."""
        mock_gigachat.chat_completion = AsyncMock(
            return_value="## Analysis Report\n\nSales are growing by 15% year-over-year."
        )

        task = {
            "description": "Generate report for sales analysis",
            "data_context": "Sales up 15%",
        }
        context = {
            "agent_results": [
                {
                    "agent": "analyst",
                    "status": "success",
                    "narrative": {"text": "Sales trending up", "format": "markdown"},
                    "findings": [{"type": "insight", "text": "Revenue growing"}],
                }
            ]
        }
        result = await agent.process_task(task, context)

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.agent == "reporter"
        assert result.narrative is not None
        assert len(result.narrative.text) > 0


# ============================================================
# DiscoveryAgent
# ============================================================

class TestDiscoveryAgent:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        from apps.backend.app.services.multi_agent.agents.discovery import DiscoveryAgent
        return DiscoveryAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    @pytest.mark.asyncio
    async def test_returns_sources(self, agent, mock_gigachat):
        """DiscoveryAgent should return sources in AgentPayload."""
        mock_gigachat.chat_completion = AsyncMock(return_value=json.dumps({
            "queries": ["python frameworks popularity 2024"],
            "sources": [
                {"url": "https://example.com/frameworks", "title": "Frameworks", "source_type": "web"},
            ],
        }))

        task = {"description": "Find data about Python framework popularity"}
        result = await agent.process_task(task, {})

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.agent == "discovery"

    @pytest.mark.asyncio
    async def test_error_handling(self, agent, mock_gigachat):
        """DiscoveryAgent should handle errors gracefully (may not raise)."""
        mock_gigachat.chat_completion = AsyncMock(side_effect=Exception("Network error"))
        result = await agent.process_task({"description": "test"}, {})
        # DiscoveryAgent catches errors during summarization gracefully
        assert isinstance(result, AgentPayload)
        assert result.status in ("success", "error")


# ============================================================
# ResearchAgent
# ============================================================

class TestResearchAgent:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        from apps.backend.app.services.multi_agent.agents.research import ResearchAgent
        return ResearchAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    @pytest.mark.asyncio
    async def test_returns_payload(self, agent, mock_gigachat):
        """ResearchAgent should return AgentPayload with sources."""
        mock_gigachat.chat_completion = AsyncMock(return_value="Summarized research content")

        task = {
            "description": "Fetch and summarize content",
            "urls": ["https://example.com"],
        }
        context = {
            "agent_results": [
                {
                    "agent": "discovery",
                    "sources": [
                        {"url": "https://example.com", "title": "Example", "source_type": "web", "fetched": False}
                    ]
                }
            ]
        }
        result = await agent.process_task(task, context)
        assert isinstance(result, AgentPayload)
        assert result.agent == "research"


# ============================================================
# QualityGateAgent
# ============================================================

class TestQualityGateAgent:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        from apps.backend.app.services.multi_agent.agents.quality_gate import QualityGateAgent
        return QualityGateAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    @pytest.mark.asyncio
    async def test_valid_result(self, agent, mock_gigachat):
        """QualityGateAgent should return validation result."""
        mock_gigachat.chat_completion = AsyncMock(return_value=json.dumps({
            "valid": True,
            "confidence": 0.92,
            "message": "Result meets requirements",
            "issues": [],
        }))

        task = {"description": "Validate analysis result"}
        context = {
            "user_request": "Analyze sales",
            "agent_results": [
                {
                    "agent": "analyst",
                    "status": "success",
                    "narrative": {"text": "Sales analysis complete"},
                    "findings": [{"type": "insight", "text": "Revenue up"}],
                }
            ]
        }
        result = await agent.process_task(task, context)

        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.agent == "validator"  # QualityGateAgent uses agent_name='validator'
        assert result.validation is not None
        assert result.validation.valid is True
        assert result.validation.confidence > 0.5

    @pytest.mark.asyncio
    async def test_invalid_result(self, agent, mock_gigachat):
        """QualityGateAgent should report issues when result is invalid."""
        mock_gigachat.chat_completion = AsyncMock(return_value=json.dumps({
            "valid": False,
            "confidence": 0.3,
            "message": "Missing data columns",
            "issues": [{"type": "validation_issue", "text": "Column 'price' not found"}],
        }))

        task = {"description": "Validate"}
        context = {"user_request": "Show prices", "agent_results": []}
        result = await agent.process_task(task, context)

        assert isinstance(result, AgentPayload)
        assert result.validation is not None
        assert result.validation.valid is False

    @pytest.mark.asyncio
    async def test_error_handling(self, agent, mock_gigachat):
        """QualityGateAgent falls back to heuristic on LLM error."""
        mock_gigachat.chat_completion = AsyncMock(side_effect=Exception("LLM down"))
        result = await agent.process_task({"description": "validate"}, {})
        # QualityGateAgent has fallback heuristic — returns success with validation
        assert isinstance(result, AgentPayload)
        assert result.status == "success"
        assert result.validation is not None


# ============================================================
# BaseAgent — общие тесты
# ============================================================

class TestBaseAgentHelpers:
    @pytest.fixture
    def agent(self, mock_message_bus, mock_gigachat):
        """Use PlannerAgent as a concrete BaseAgent subclass."""
        from apps.backend.app.services.multi_agent.agents.planner import PlannerAgent
        return PlannerAgent(message_bus=mock_message_bus, gigachat_service=mock_gigachat)

    def test_success_payload(self, agent):
        p = agent._success_payload(narrative_text="All good")
        assert isinstance(p, AgentPayload)
        assert p.status == "success"
        assert p.agent == "planner"
        assert p.narrative.text == "All good"

    def test_error_payload(self, agent):
        p = agent._error_payload("Something broke", suggestions=["Try again"])
        assert isinstance(p, AgentPayload)
        assert p.status == "error"
        assert p.error == "Something broke"
        assert p.suggestions == ["Try again"]

    def test_validate_task_missing_fields(self, agent):
        with pytest.raises(ValueError, match="Missing required fields"):
            agent._validate_task({"a": 1}, ["a", "b", "c"])

    def test_validate_task_ok(self, agent):
        agent._validate_task({"a": 1, "b": 2}, ["a", "b"])  # should not raise

    def test_stats(self, agent):
        stats = agent.get_stats()
        assert stats["agent_name"] == "planner"
        assert stats["task_count"] == 0
        assert stats["error_count"] == 0
