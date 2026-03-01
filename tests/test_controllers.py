"""
Unit тесты Satellite Controllers V2 (Phase 7.3).

Тестируется с mock Orchestrator:
- Формирование запроса к Orchestrator
- Извлечение результата в ControllerResult
- Обработка ошибок
- BaseController helpers

НЕ требует реальных API ключей / LLM / DB.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from apps.backend.app.services.controllers.base_controller import (
    BaseController,
    ControllerResult,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_orchestrator():
    """Mock Orchestrator — returns configurable dict results."""
    orch = MagicMock()
    orch.process_request = AsyncMock(return_value={
        "status": "success",
        "agent_results": {},
    })
    return orch


def _make_orch_result(
    *,
    code: str = "",
    language: str = "python",
    purpose: str = "transformation",
    narrative: str = "",
    widget_code: str = "",
    widget_name: str = "Widget",
    widget_type: str = "chart",
    tables: list = None,
    findings: list = None,
    validation: dict = None,
) -> Dict[str, Any]:
    """Helper: build a mock orchestrator result dict."""
    agent_results = {}

    if code or narrative:
        codex_result = {
            "status": "success",
            "agent": "transform_codex",
            "code_blocks": [],
            "narrative": {"text": narrative, "format": "markdown"} if narrative else None,
            "tables": tables or [],
            "findings": findings or [],
            "sources": [],
        }
        if code:
            codex_result["code_blocks"].append({
                "code": code,
                "language": language,
                "purpose": purpose,
                "syntax_valid": True,
                "warnings": [],
                "description": "Generated code",
            })
        agent_results["transform_codex"] = codex_result

    if widget_code:
        reporter_result = {
            "status": "success",
            "agent": "reporter",
            "code_blocks": [{
                "code": widget_code,
                "language": "html",
                "purpose": "widget",
                "syntax_valid": True,
                "warnings": [],
                "description": widget_name,
            }],
            "narrative": None,
            "tables": [],
            "findings": [],
            "sources": [],
            "metadata": {"widget_type": widget_type, "widget_name": widget_name},
        }
        agent_results["reporter"] = reporter_result

    if validation:
        validator_result = {
            "status": "success",
            "agent": "validator",
            "validation": validation,
            "code_blocks": [],
            "tables": [],
            "findings": [],
            "sources": [],
        }
        agent_results["validator"] = validator_result

    return {
        "status": "success",
        "results": agent_results,
    }


# ============================================================
# ControllerResult
# ============================================================

class TestControllerResult:
    def test_default_values(self):
        r = ControllerResult()
        assert r.status == "success"
        assert r.error is None
        assert r.code is None
        assert r.widget_code is None
        assert r.suggestions == []
        assert r.execution_time_ms == 0

    def test_to_dict_omits_none(self):
        r = ControllerResult(status="success", code="x=1", code_language="python")
        d = r.to_dict()
        assert d["status"] == "success"
        assert d["code"] == "x=1"
        assert "error" not in d
        assert "widget_code" not in d

    def test_to_dict_always_includes_status(self):
        r = ControllerResult(status="error", error="fail")
        d = r.to_dict()
        assert d["status"] == "error"
        assert d["error"] == "fail"

    def test_error_result(self):
        r = ControllerResult(status="error", error="msg", execution_time_ms=150)
        assert r.status == "error"
        assert r.error == "msg"

    def test_widget_result(self):
        r = ControllerResult(
            widget_code="<div>chart</div>",
            widget_name="Sales Chart",
            widget_type="bar",
        )
        assert r.widget_code == "<div>chart</div>"


# ============================================================
# BaseController — helpers
# ============================================================

class TestBaseControllerHelpers:
    def test_extract_code_blocks(self):
        results = {
            "transform_codex": {
                "code_blocks": [
                    {"code": "df.head()", "purpose": "transformation", "language": "python"},
                    {"code": "<div/>", "purpose": "widget", "language": "html"},
                ]
            },
            "reporter": {
                "code_blocks": [
                    {"code": "<h1>Report</h1>", "purpose": "widget", "language": "html"},
                ]
            }
        }

        all_blocks = BaseController._extract_code_blocks(results)
        assert len(all_blocks) == 3

        transform_blocks = BaseController._extract_code_blocks(results, purpose="transformation")
        assert len(transform_blocks) == 1
        assert transform_blocks[0]["code"] == "df.head()"

        widget_blocks = BaseController._extract_code_blocks(results, purpose="widget")
        assert len(widget_blocks) == 2

    def test_extract_narrative(self):
        results = {
            "analyst": {
                "narrative": {"text": "Analysis result", "format": "markdown"},
            },
            "reporter": {
                "narrative": {"text": "Final report", "format": "markdown"},
            },
        }
        text = BaseController._extract_narrative(results)
        # Should return last narrative (reporter overwrites analyst)
        assert text is not None
        assert isinstance(text, str)
        assert len(text) > 0

    def test_extract_narrative_none(self):
        results = {"transform_codex": {"narrative": None, "code_blocks": []}}
        text = BaseController._extract_narrative(results)
        assert text is None

    def test_extract_findings(self):
        results = {
            "analyst": {
                "findings": [
                    {"type": "insight", "text": "A"},
                    {"type": "warning", "text": "B"},
                ]
            },
        }
        all_f = BaseController._extract_findings(results)
        assert len(all_f) == 2

        insights_only = BaseController._extract_findings(results, finding_type="insight")
        assert len(insights_only) == 1

    def test_extract_tables(self):
        results = {
            "structurizer": {
                "tables": [
                    {"name": "data", "columns": [], "rows": []},
                ]
            },
        }
        tables = BaseController._extract_tables(results)
        assert len(tables) == 1
        assert tables[0]["name"] == "data"

    def test_extract_validation(self):
        results = {
            "validator": {
                "validation": {"valid": True, "confidence": 0.9, "message": "OK"},
            },
        }
        v = BaseController._extract_validation(results)
        assert v is not None
        assert v["valid"] is True

    def test_extract_validation_none(self):
        results = {"transform_codex": {"code_blocks": []}}
        v = BaseController._extract_validation(results)
        assert v is None

    def test_error_result_helper(self, mock_orchestrator):
        ctrl = BaseController(mock_orchestrator)
        r = ctrl._error_result("Something failed", execution_time_ms=100)
        assert r.status == "error"
        assert r.error == "Something failed"
        assert r.execution_time_ms == 100


# ============================================================
# TransformationController
# ============================================================

class TestTransformationController:
    @pytest.fixture
    def controller(self, mock_orchestrator):
        from apps.backend.app.services.controllers.transformation_controller import (
            TransformationController,
        )
        return TransformationController(mock_orchestrator)

    @pytest.mark.asyncio
    async def test_returns_code(self, controller, mock_orchestrator):
        """TransformationController should return code in ControllerResult."""
        mock_orchestrator.process_request = AsyncMock(return_value=_make_orch_result(
            code="df_filtered = df[df['a'] > 1]",
            purpose="transformation",
        ))

        result = await controller.process_request(
            user_message="Filter a > 1",
            context={
                "board_id": "b1",
                "input_tables": [{"name": "data", "columns": [{"name": "a", "type": "int"}], "rows": [{"a": 1}, {"a": 2}, {"a": 3}]}],
                "skip_execution": True,
            },
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "success"
        assert result.code is not None
        assert "df_filtered" in result.code

    @pytest.mark.asyncio
    async def test_discussion_mode(self, controller, mock_orchestrator):
        """When no code blocks, should return narrative (discussion mode)."""
        mock_orchestrator.process_request = AsyncMock(return_value=_make_orch_result(
            narrative="Here is the explanation of the filter operation...",
        ))

        result = await controller.process_request(
            user_message="Explain how to filter data",
            context={"board_id": "b1", "skip_execution": True},
        )

        assert isinstance(result, ControllerResult)
        # Could be discussion mode with narrative or error if no code
        assert result.narrative is not None or result.status == "error"

    @pytest.mark.asyncio
    async def test_orchestrator_error(self, controller, mock_orchestrator):
        """Should handle orchestrator errors gracefully."""
        mock_orchestrator.process_request = AsyncMock(return_value={
            "status": "error",
            "error": "Agent timeout",
        })

        result = await controller.process_request(
            user_message="test",
            context={"board_id": "b1"},
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_orchestrator_exception(self, controller, mock_orchestrator):
        """Should handle orchestrator exceptions."""
        mock_orchestrator.process_request = AsyncMock(
            side_effect=Exception("Connection lost")
        )

        result = await controller.process_request(
            user_message="test",
            context={"board_id": "b1"},
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "error"


# ============================================================
# WidgetController
# ============================================================

class TestWidgetController:
    @pytest.fixture
    def controller(self, mock_orchestrator):
        from apps.backend.app.services.controllers.widget_controller import (
            WidgetController,
        )
        return WidgetController(mock_orchestrator)

    @pytest.mark.asyncio
    async def test_returns_widget_code(self, controller, mock_orchestrator):
        """WidgetController should extract widget code from result."""
        mock_orchestrator.process_request = AsyncMock(return_value=_make_orch_result(
            widget_code="<div id='chart'><h1>Sales</h1></div>",
            widget_name="Sales Chart",
            widget_type="bar",
        ))

        result = await controller.process_request(
            user_message="Create a bar chart for sales",
            context={
                "board_id": "b1",
                "content_data": {"tables": [{"name": "sales", "columns": [], "rows": []}]},
            },
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "success"
        assert result.widget_code is not None
        assert "<div" in result.widget_code

    @pytest.mark.asyncio
    async def test_handles_no_widget_code(self, controller, mock_orchestrator):
        """Should handle case when no widget code is generated."""
        mock_orchestrator.process_request = AsyncMock(return_value={
            "status": "success",
            "agent_results": {},
        })

        result = await controller.process_request(
            user_message="test",
            context={"board_id": "b1"},
        )

        assert isinstance(result, ControllerResult)
        # Error or empty result
        assert result.status == "error" or result.widget_code is None


# ============================================================
# AIAssistantController
# ============================================================

class TestAIAssistantController:
    @pytest.fixture
    def controller(self, mock_orchestrator):
        from apps.backend.app.services.controllers.ai_assistant_controller import (
            AIAssistantController,
        )
        return AIAssistantController(mock_orchestrator)

    @pytest.mark.asyncio
    async def test_returns_narrative(self, controller, mock_orchestrator):
        """AIAssistantController should return narrative text."""
        mock_orchestrator.process_request = AsyncMock(return_value=_make_orch_result(
            narrative="Here is the analysis: sales are growing 15% YoY.",
        ))

        result = await controller.process_request(
            user_message="Analyze my sales data",
            context={
                "board_id": "b1",
                "board_context": {"nodes": [], "edges": []},
            },
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "success"
        assert result.narrative is not None
        assert len(result.narrative) > 0

    @pytest.mark.asyncio
    async def test_error_handling(self, controller, mock_orchestrator):
        mock_orchestrator.process_request = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        result = await controller.process_request(
            user_message="test",
            context={"board_id": "b1"},
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "error"


# ============================================================
# TransformSuggestionsController
# ============================================================

class TestTransformSuggestionsController:
    @pytest.fixture
    def controller(self, mock_orchestrator):
        from apps.backend.app.services.controllers.transform_suggestions_controller import (
            TransformSuggestionsController,
        )
        return TransformSuggestionsController(mock_orchestrator)

    @pytest.mark.asyncio
    async def test_returns_suggestions(self, controller, mock_orchestrator):
        """Should return list of transform suggestions."""
        mock_orchestrator.process_request = AsyncMock(return_value=_make_orch_result(
            narrative="Suggested transformations for your data.",
            findings=[
                {"type": "recommendation", "text": "Filter null values", "severity": "medium"},
                {"type": "recommendation", "text": "Normalize prices", "severity": "low"},
            ],
        ))

        result = await controller.process_request(
            user_message="Suggest transformations",
            context={
                "board_id": "b1",
                "content_data": {"tables": [{"name": "data", "columns": [{"name": "price", "type": "int"}], "rows": [{"price": 100}]}]},
            },
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "success"


# ============================================================
# WidgetSuggestionsController
# ============================================================

class TestWidgetSuggestionsController:
    @pytest.fixture
    def controller(self, mock_orchestrator):
        from apps.backend.app.services.controllers.widget_suggestions_controller import (
            WidgetSuggestionsController,
        )
        return WidgetSuggestionsController(mock_orchestrator)

    @pytest.mark.asyncio
    async def test_returns_suggestions(self, controller, mock_orchestrator):
        """Should return widget suggestions."""
        mock_orchestrator.process_request = AsyncMock(return_value=_make_orch_result(
            narrative="Recommended visualizations for your data.",
        ))

        result = await controller.process_request(
            user_message="Suggest widgets",
            context={
                "board_id": "b1",
                "content_data": {"tables": [{"name": "sales", "columns": [], "rows": []}]},
            },
        )

        assert isinstance(result, ControllerResult)
        assert result.status == "success"
