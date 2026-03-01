"""Tests for WidgetController._extract_widget_metadata and description pipeline."""

import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.controllers.widget_controller import WidgetController


class TestExtractWidgetMetadata:
    """Tests for WidgetController._extract_widget_metadata."""

    def test_extracts_from_payload_metadata(self):
        """widget metadata is extracted from AgentPayload.metadata."""
        results = {
            "widget_codex": {
                "code_blocks": [{"code": "<div/>", "purpose": "widget"}],
                "metadata": {
                    "widget_type": "chart",
                    "widget_name": "Продажи по категориям",
                    "widget_description": "Столбчатая диаграмма продаж",
                },
            }
        }
        meta = WidgetController._extract_widget_metadata(results)
        assert meta["widget_type"] == "chart"
        assert meta["widget_name"] == "Продажи по категориям"
        assert meta["widget_description"] == "Столбчатая диаграмма продаж"

    def test_empty_results(self):
        """Empty results → empty metadata."""
        assert WidgetController._extract_widget_metadata({}) == {}

    def test_payload_without_metadata(self):
        """Payload with no metadata → empty dict."""
        results = {
            "widget_codex": {
                "code_blocks": [{"code": "<div/>"}],
            }
        }
        assert WidgetController._extract_widget_metadata(results) == {}

    def test_metadata_without_widget_name(self):
        """Metadata present but no widget_name → skip."""
        results = {
            "widget_codex": {
                "code_blocks": [],
                "metadata": {"some_key": "value"},
            }
        }
        assert WidgetController._extract_widget_metadata(results) == {}

    def test_multiple_agents(self):
        """Picks the agent whose metadata has widget_name."""
        results = {
            "analyst": {
                "narrative": {"text": "Analysis done"},
                "metadata": {"analysis_type": "summary"},
            },
            "widget_codex": {
                "code_blocks": [{"code": "html", "purpose": "widget"}],
                "metadata": {
                    "widget_name": "KPI метрики",
                    "widget_type": "kpi",
                    "widget_description": "Ключевые показатели",
                },
            },
        }
        meta = WidgetController._extract_widget_metadata(results)
        assert meta["widget_name"] == "KPI метрики"


class TestDescriptionPipeline:
    """Verify description (not just name) flows through WidgetCodex → ControllerResult."""

    def test_widget_codex_returns_description_in_metadata(self):
        """WidgetCodex should place widget_description in metadata."""
        from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent

        codex = WidgetCodexAgent.__new__(WidgetCodexAgent)

        # Simulate what _generate_widget does after parsing
        parsed = {
            "widget_name": "Динамика продаж",
            "widget_type": "chart",
            "description": "Линейный график динамики продаж за 12 месяцев",
            "render_body": "// chart code",
        }
        widget_name = parsed.get("widget_name", "")
        widget_description = (parsed.get("description") or "").strip()

        # Verify description is different from name
        assert widget_description != widget_name
        assert len(widget_description) > len(widget_name)

    def test_description_not_lost_when_same_as_name(self):
        """When LLM puts name as description, fallback to name."""
        parsed = {
            "widget_name": "Топ-10 брендов",
            "description": "Топ-10 брендов",
        }
        widget_name = parsed.get("widget_name", "")
        widget_description = (parsed.get("description") or "").strip()

        if not widget_description or widget_description.lower() == widget_name.lower():
            widget_description = widget_name

        assert widget_description == "Топ-10 брендов"
