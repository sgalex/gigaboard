"""Юнит-тесты per-step acceptance (детерминированные эвристики)."""

from apps.backend.app.services.multi_agent.step_acceptance import (
    StepAcceptanceResult,
    evaluate_step_acceptance,
    normalize_step_acceptance_agent_name,
    record_step_acceptance_in_memory,
)


def test_reporter_fail_without_narrative_and_tables():
    r = evaluate_step_acceptance(
        agent_name="reporter",
        task={},
        result={"status": "success", "agent": "reporter"},
    )
    assert r.level == "fail"
    assert "reporter_empty_output" in r.codes


def test_reporter_ok_with_narrative():
    r = evaluate_step_acceptance(
        agent_name="reporter",
        task={},
        result={
            "status": "success",
            "agent": "reporter",
            "narrative": {"text": "Итог для пользователя", "format": "markdown"},
        },
    )
    assert r.level == "ok"


def test_codex_fail_without_code():
    r = evaluate_step_acceptance(
        agent_name="transform_codex",
        task={},
        result={"status": "success", "agent": "transform_codex", "code_blocks": []},
    )
    assert r.level == "fail"
    assert "codex_no_code" in r.codes


def test_codex_ok_with_code():
    r = evaluate_step_acceptance(
        agent_name="transform_codex",
        task={},
        result={
            "status": "success",
            "agent": "transform_codex",
            "code_blocks": [{"code": "x = 1", "language": "python", "purpose": "transformation"}],
        },
    )
    assert r.level == "ok"


def test_partial_downgrades_fail_to_warn():
    r = evaluate_step_acceptance(
        agent_name="reporter",
        task={},
        result={"status": "partial", "agent": "reporter"},
    )
    assert r.level == "warn"


def test_disabled_via_env(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_STEP_ACCEPTANCE_ENABLED", "false")
    r = evaluate_step_acceptance(
        agent_name="reporter",
        task={},
        result={"status": "success", "agent": "reporter"},
    )
    assert r.level == "ok"


def test_task_acceptance_skip():
    r = evaluate_step_acceptance(
        agent_name="reporter",
        task={"acceptance": {"skip": True}},
        result={"status": "success", "agent": "reporter"},
    )
    assert r.level == "ok"
    assert "skipped_task_acceptance" in r.codes


def test_codex_alias_maps_to_transform_codex_rules():
    r = evaluate_step_acceptance(
        agent_name="codex",
        task={},
        result={"status": "success", "agent": "codex", "code_blocks": []},
    )
    assert r.level == "fail"
    assert "codex_no_code" in r.codes


def test_normalize_agent_name_codex():
    assert normalize_step_acceptance_agent_name("codex") == "transform_codex"
    assert normalize_step_acceptance_agent_name("transform_codex") == "transform_codex"


def test_validator_fail_without_validation():
    r = evaluate_step_acceptance(
        agent_name="validator",
        task={},
        result={"status": "success", "agent": "validator"},
    )
    assert r.level == "fail"
    assert "validator_missing_validation" in r.codes


def test_validator_ok_with_validation():
    r = evaluate_step_acceptance(
        agent_name="validator",
        task={},
        result={
            "status": "success",
            "agent": "validator",
            "validation": {"valid": True, "confidence": 0.9, "message": "ok"},
        },
    )
    assert r.level == "ok"


def test_discovery_fail_sources_without_url():
    r = evaluate_step_acceptance(
        agent_name="discovery",
        task={},
        result={
            "status": "success",
            "agent": "discovery",
            "narrative": {"text": "Есть что-то", "format": "markdown"},
            "sources": [{"title": "x", "url": ""}, {"snippet": "y"}],
        },
    )
    assert r.level == "fail"
    assert "discovery_sources_without_url" in r.codes


def test_context_filter_warn_null_filter_short_reason():
    r = evaluate_step_acceptance(
        agent_name="context_filter",
        task={},
        result={
            "status": "success",
            "agent": "context_filter",
            "narrative": {"text": "x", "format": "markdown"},
            "metadata": {"filter_expression": None, "reason": ""},
        },
    )
    assert r.level == "warn"
    assert "context_filter_weak_reason" in r.codes


def test_widget_codex_warn_wrong_language():
    r = evaluate_step_acceptance(
        agent_name="widget_codex",
        task={},
        result={
            "status": "success",
            "agent": "widget_codex",
            "code_blocks": [
                {"code": "<div/>", "language": "python", "purpose": "widget"},
            ],
        },
    )
    assert r.level == "warn"
    assert "widget_codex_language_mismatch" in r.codes


def test_record_memory_appends_open_question():
    ctx: dict = {}
    acc = StepAcceptanceResult(
        level="warn",
        codes=["x"],
        messages=["тестовое предупреждение"],
    )
    record_step_acceptance_in_memory(
        ctx,
        agent_name="analyst",
        step_id="3",
        acceptance=acc,
    )
    pm = ctx.get("pipeline_memory") or {}
    oq = pm.get("open_questions") or []
    assert any("тестовое предупреждение" in str(x) for x in oq)
    log = ctx.get("_step_acceptance_log") or []
    assert len(log) == 1
    assert log[0]["agent"] == "analyst"
