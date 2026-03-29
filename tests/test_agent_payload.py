"""
Unit тесты AgentPayload и вложенных моделей (Phase 7.1).

Проверяет:
- Сериализацию/десериализацию всех моделей
- Валидацию обязательных полей
- Factory methods (success, error, partial)
- Accessor helpers (get_code, get_table, get_findings_by_type)
- Properties (is_valid, has_code, has_tables)
- merge_from
- PayloadContentTable.from_dict
- Edge cases (пустые списки, None, границы)
"""

import pytest
from datetime import datetime
from uuid import UUID

from apps.backend.app.services.multi_agent.schemas.agent_payload import (
    AgentPayload,
    CodeBlock,
    Column,
    Finding,
    Narrative,
    PayloadContentTable,
    Plan,
    PlanStep,
    Source,
    SuggestedReplan,
    ValidationResult,
)


# ============================================================
# Narrative
# ============================================================

class TestNarrative:
    def test_basic(self):
        n = Narrative(text="Hello world")
        assert n.text == "Hello world"
        assert n.format == "markdown"

    def test_formats(self):
        for fmt in ("markdown", "plain", "html"):
            n = Narrative(text="x", format=fmt)
            assert n.format == fmt

    def test_empty_text_allowed(self):
        n = Narrative(text="")
        assert n.text == ""

    def test_serialization(self):
        n = Narrative(text="# Title", format="html")
        d = n.model_dump()
        assert d == {"text": "# Title", "format": "html"}
        n2 = Narrative.model_validate(d)
        assert n2 == n


# ============================================================
# Column
# ============================================================

class TestColumn:
    def test_defaults(self):
        c = Column(name="age")
        assert c.name == "age"
        assert c.type == "string"

    def test_custom_type(self):
        c = Column(name="price", type="float")
        assert c.type == "float"


# ============================================================
# PayloadContentTable
# ============================================================

class TestPayloadContentTable:
    def _make_table(self) -> PayloadContentTable:
        return PayloadContentTable(
            name="sales",
            columns=[Column(name="region"), Column(name="amount", type="float")],
            rows=[{"region": "US", "amount": 100.0}, {"region": "EU", "amount": 200.0}],
            row_count=2,
            column_count=2,
            preview_row_count=2,
        )

    def test_basic(self):
        t = self._make_table()
        assert t.name == "sales"
        assert len(t.columns) == 2
        assert len(t.rows) == 2
        UUID(t.id)

    def test_to_content_table_dict(self):
        t = self._make_table()
        d = t.to_content_table_dict()
        assert d["name"] == "sales"
        assert len(d["columns"]) == 2
        assert d["row_count"] == 2

    def test_from_dict(self):
        """Unified format: rows as dicts with column name keys."""
        data = {
            "name": "users",
            "columns": [{"name": "id", "type": "int"}, {"name": "name", "type": "string"}],
            "rows": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            "row_count": 2,
            "column_count": 2,
        }
        t = PayloadContentTable.from_dict(data)
        assert t.name == "users"
        assert len(t.columns) == 2
        assert t.columns[0].type == "int"
        assert t.columns[1].type == "string"
        assert len(t.rows) == 2
        assert t.rows[0] == {"id": 1, "name": "Alice"}

    def test_from_dict_empty(self):
        t = PayloadContentTable.from_dict({})
        assert t.name == "без названия"
        assert t.columns == []
        assert t.rows == []

    def test_serialization_roundtrip(self):
        t = self._make_table()
        d = t.model_dump()
        t2 = PayloadContentTable.model_validate(d)
        assert t2.name == t.name
        assert len(t2.rows) == len(t.rows)


# ============================================================
# CodeBlock
# ============================================================

class TestCodeBlock:
    def test_basic(self):
        cb = CodeBlock(code="df.head()", language="python", purpose="transformation")
        assert cb.code == "df.head()"
        assert cb.language == "python"
        assert cb.purpose == "transformation"
        assert cb.syntax_valid is None
        assert cb.warnings == []

    def test_full(self):
        cb = CodeBlock(
            code="<div>Hi</div>",
            language="html",
            purpose="widget",
            variable_name="widget_html",
            syntax_valid=True,
            warnings=["Large DOM"],
            description="Sales Chart",
        )
        assert cb.variable_name == "widget_html"
        assert cb.syntax_valid is True
        assert cb.description == "Sales Chart"

    def test_serialization(self):
        cb = CodeBlock(code="x=1", language="python", purpose="utility")
        d = cb.model_dump()
        cb2 = CodeBlock.model_validate(d)
        assert cb2.code == cb.code


# ============================================================
# Source
# ============================================================

class TestSource:
    def test_defaults(self):
        s = Source(url="https://example.com")
        assert s.source_type == "web"
        assert s.fetched is False
        assert s.content is None

    def test_full(self):
        s = Source(
            url="https://api.example.com/data",
            title="Example API",
            snippet="...",
            content="full text",
            source_type="api",
            status_code=200,
            fetched=True,
            content_size=1024,
        )
        assert s.fetched is True
        assert s.content_size == 1024


# ============================================================
# Finding
# ============================================================

class TestFinding:
    def test_basic(self):
        f = Finding(type="insight", text="Revenue growing")
        assert f.severity == "medium"  # default
        assert f.confidence is None
        assert f.refs == []

    def test_full(self):
        f = Finding(
            type="data_quality_issue",
            text="NULL values in column 'age'",
            severity="high",
            confidence=0.95,
            refs=["age", "users"],
            action="Fill with median",
        )
        assert f.confidence == 0.95
        assert f.action == "Fill with median"

    def test_confidence_bounds(self):
        f = Finding(type="warning", text="x", confidence=0.0)
        assert f.confidence == 0.0
        f2 = Finding(type="warning", text="x", confidence=1.0)
        assert f2.confidence == 1.0

    def test_confidence_out_of_range(self):
        with pytest.raises(Exception):
            Finding(type="warning", text="x", confidence=1.5)
        with pytest.raises(Exception):
            Finding(type="warning", text="x", confidence=-0.1)


# ============================================================
# PlanStep & Plan
# ============================================================

class TestPlanStep:
    def test_basic(self):
        ps = PlanStep(step_id="1", agent="analyst", task={"action": "analyze"})
        assert ps.step_id == "1"
        assert ps.depends_on == []

    def test_with_deps(self):
        ps = PlanStep(step_id="3", agent="transform_codex", task={}, depends_on=["1", "2"])
        assert ps.depends_on == ["1", "2"]


class TestPlan:
    def test_basic(self):
        p = Plan(
            user_request="Analyze sales",
            steps=[
                PlanStep(step_id="1", agent="analyst", task={"sql": "SELECT *"}),
                PlanStep(step_id="2", agent="reporter", task={}, depends_on=["1"]),
            ],
        )
        assert len(p.steps) == 2
        UUID(p.plan_id)

    def test_empty_plan(self):
        p = Plan(user_request="test")
        assert p.steps == []


# ============================================================
# ValidationResult & SuggestedReplan
# ============================================================

class TestValidationResult:
    def test_valid(self):
        vr = ValidationResult(valid=True, confidence=0.9, message="OK")
        assert vr.valid is True
        assert vr.issues == []

    def test_invalid_with_issues(self):
        vr = ValidationResult(
            valid=False,
            confidence=0.3,
            issues=[
                Finding(type="validation_issue", text="Missing column", severity="critical")
            ],
            suggested_replan=SuggestedReplan(
                reason="Need more data",
                additional_steps=[PlanStep(step_id="4", agent="discovery", task={})],
            ),
        )
        assert vr.valid is False
        assert len(vr.issues) == 1
        assert vr.suggested_replan.reason == "Need more data"


class TestSuggestedReplan:
    def test_basic(self):
        sr = SuggestedReplan(reason="Insufficient data")
        assert sr.additional_steps == []


# ============================================================
# AgentPayload — Factory Methods
# ============================================================

class TestAgentPayloadFactories:
    def test_success_minimal(self):
        p = AgentPayload.success(agent="analyst")
        assert p.status == "success"
        assert p.agent == "analyst"
        assert p.tables == []
        assert p.code_blocks == []
        assert p.error is None

    def test_success_full(self):
        p = AgentPayload.success(
            agent="reporter",
            narrative=Narrative(text="Report ready"),
            tables=[PayloadContentTable(name="t1", columns=[], rows=[])],
            code_blocks=[CodeBlock(code="<div/>", language="html", purpose="widget")],
            sources=[Source(url="https://x.com")],
            findings=[Finding(type="insight", text="Growing")],
            validation=ValidationResult(valid=True, confidence=1.0),
            plan=Plan(user_request="test"),
            metadata={"widget_type": "chart"},
        )
        assert p.narrative.text == "Report ready"
        assert len(p.tables) == 1
        assert len(p.code_blocks) == 1
        assert p.metadata["widget_type"] == "chart"

    def test_error(self):
        p = AgentPayload.make_error(
            agent="transform_codex",
            error_message="Syntax fail",
            suggestions=["Check imports"],
        )
        assert p.status == "error"
        assert p.agent == "transform_codex"
        assert p.error == "Syntax fail"
        assert p.suggestions == ["Check imports"]

    def test_error_no_suggestions(self):
        p = AgentPayload.make_error(agent="planner", error_message="Timeout")
        assert p.suggestions == []

    def test_error_with_metadata(self):
        p = AgentPayload.make_error(
            agent="research",
            error_message="fail",
            metadata={"task_relevance": {"scores": []}},
        )
        assert p.metadata.get("task_relevance", {}).get("scores") == []

    def test_partial(self):
        p = AgentPayload.partial(
            agent="discovery",
            narrative=Narrative(text="Searching..."),
        )
        assert p.status == "partial"
        assert p.narrative.text == "Searching..."

    def test_timestamp_auto(self):
        p = AgentPayload.success(agent="test")
        # Should be a valid ISO timestamp
        datetime.fromisoformat(p.timestamp)


# ============================================================
# AgentPayload — Accessor Helpers
# ============================================================

class TestAgentPayloadAccessors:
    def _make_rich_payload(self) -> AgentPayload:
        return AgentPayload.success(
            agent="test",
            code_blocks=[
                CodeBlock(code="df.head()", language="python", purpose="transformation"),
                CodeBlock(code="<div/>", language="html", purpose="widget"),
                CodeBlock(code="SELECT 1", language="sql", purpose="analysis"),
            ],
            tables=[
                PayloadContentTable(name="sales", columns=[], rows=[]),
                PayloadContentTable(name="users", columns=[], rows=[]),
            ],
            findings=[
                Finding(type="insight", text="A"),
                Finding(type="insight", text="B"),
                Finding(type="warning", text="C"),
                Finding(type="data_quality_issue", text="D"),
            ],
            validation=ValidationResult(valid=True, confidence=0.95),
        )

    def test_get_code_by_purpose(self):
        p = self._make_rich_payload()
        cb = p.get_code("transformation")
        assert cb is not None
        assert cb.code == "df.head()"

        cb2 = p.get_code("widget")
        assert cb2.code == "<div/>"

        cb3 = p.get_code("nonexistent")
        assert cb3 is None

    def test_get_table_by_name(self):
        p = self._make_rich_payload()
        t = p.get_table("sales")
        assert t is not None
        assert t.name == "sales"

        t2 = p.get_table("nonexistent")
        assert t2 is None

    def test_get_findings_by_type(self):
        p = self._make_rich_payload()
        insights = p.get_findings_by_type("insight")
        assert len(insights) == 2

        warnings = p.get_findings_by_type("warning")
        assert len(warnings) == 1

        recommendations = p.get_findings_by_type("recommendation")
        assert len(recommendations) == 0

    def test_is_valid(self):
        p = self._make_rich_payload()
        assert p.is_valid is True

    def test_is_valid_false(self):
        p = AgentPayload.success(
            agent="test",
            validation=ValidationResult(valid=False, confidence=0.1),
        )
        assert p.is_valid is False

    def test_is_valid_none(self):
        p = AgentPayload.success(agent="test")
        assert p.is_valid is False

    def test_has_code(self):
        p = self._make_rich_payload()
        assert p.has_code is True

    def test_has_code_false(self):
        p = AgentPayload.success(agent="test")
        assert p.has_code is False

    def test_has_tables(self):
        p = self._make_rich_payload()
        assert p.has_tables is True

    def test_has_tables_false(self):
        p = AgentPayload.success(agent="test")
        assert p.has_tables is False


# ============================================================
# AgentPayload — merge_from
# ============================================================

class TestAgentPayloadMerge:
    def test_merge_additive(self):
        p1 = AgentPayload.success(
            agent="analyst",
            tables=[PayloadContentTable(name="t1", columns=[], rows=[])],
            findings=[Finding(type="insight", text="A")],
            metadata={"key1": "v1"},
        )
        p2 = AgentPayload.success(
            agent="reporter",
            code_blocks=[CodeBlock(code="<div/>", language="html", purpose="widget")],
            sources=[Source(url="https://x.com")],
            findings=[Finding(type="warning", text="B")],
            metadata={"key2": "v2"},
        )

        p1.merge_from(p2)

        assert len(p1.tables) == 1  # unchanged
        assert len(p1.code_blocks) == 1  # added from p2
        assert len(p1.sources) == 1  # added from p2
        assert len(p1.findings) == 2  # merged
        assert p1.metadata == {"key1": "v1", "key2": "v2"}

    def test_merge_no_overwrite_metadata(self):
        p1 = AgentPayload.success(agent="a", metadata={"k": "original"})
        p2 = AgentPayload.success(agent="b", metadata={"k": "duplicate"})
        p1.merge_from(p2)
        assert p1.metadata["k"] == "original"  # not overwritten

    def test_merge_empty(self):
        p1 = AgentPayload.success(agent="a")
        p2 = AgentPayload.success(agent="b")
        p1.merge_from(p2)
        assert p1.tables == []
        assert p1.code_blocks == []


# ============================================================
# AgentPayload — Serialization
# ============================================================

class TestAgentPayloadSerialization:
    def test_roundtrip(self):
        p = AgentPayload.success(
            agent="planner",
            narrative=Narrative(text="Plan ready"),
            plan=Plan(
                user_request="Analyze data",
                steps=[PlanStep(step_id="1", agent="analyst", task={"sql": "SELECT *"})],
            ),
        )
        d = p.model_dump()
        p2 = AgentPayload.model_validate(d)
        assert p2.agent == "planner"
        assert p2.plan.user_request == "Analyze data"
        assert len(p2.plan.steps) == 1

    def test_json_roundtrip(self):
        p = AgentPayload.make_error(agent="transform_codex", error_message="fail")
        json_str = p.model_dump_json()
        p2 = AgentPayload.model_validate_json(json_str)
        assert p2.status == "error"
        assert p2.error == "fail"

    def test_none_fields_excluded_from_json(self):
        p = AgentPayload.success(agent="test")
        d = p.model_dump(exclude_none=True)
        assert "narrative" not in d
        assert "validation" not in d
        assert "plan" not in d
        assert "error" not in d


# ============================================================
# Edge Cases
# ============================================================

class TestEdgeCases:
    def test_required_status(self):
        with pytest.raises(Exception):
            AgentPayload(agent="test")  # missing status

    def test_required_agent(self):
        with pytest.raises(Exception):
            AgentPayload(status="success")  # missing agent

    def test_empty_lists_are_default(self):
        p = AgentPayload(status="success", agent="test")
        assert p.tables == []
        assert p.code_blocks == []
        assert p.sources == []
        assert p.findings == []
        assert p.suggestions == []
        assert p.metadata == {}

    def test_narrative_required_text(self):
        with pytest.raises(Exception):
            Narrative()  # missing text

    def test_column_required_name(self):
        with pytest.raises(Exception):
            Column()  # missing name

    def test_finding_required_fields(self):
        with pytest.raises(Exception):
            Finding()  # missing type and text

    def test_code_block_required_fields(self):
        with pytest.raises(Exception):
            CodeBlock()  # missing code, language, purpose

    def test_plan_step_required_fields(self):
        with pytest.raises(Exception):
            PlanStep()  # missing step_id, agent

    def test_source_required_url(self):
        with pytest.raises(Exception):
            Source()  # missing url

    def test_validation_result_required_valid(self):
        with pytest.raises(Exception):
            ValidationResult()  # missing valid
