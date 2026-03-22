import asyncio

from apps.backend.app.services.multi_agent.orchestrator import (
    MultiAgentTraceLogger,
    Orchestrator,
)
from apps.backend.app.services.multi_agent.schemas.agent_payload import (
    AgentPayload,
    Narrative,
    Plan,
    PlanStep,
)


class _FakePlannerAgent:
    async def process_task(self, task, context):
        plan = Plan(
            plan_id="p-1",
            user_request="test plan",
            steps=[
                PlanStep(
                    step_id="1",
                    agent="reporter",
                    task={"description": "summarize"},
                    depends_on=[],
                )
            ],
        )
        return AgentPayload.success(agent="planner", plan=plan)


class _FakeReporterAgent:
    async def process_task(self, task, context):
        return AgentPayload.success(
            agent="reporter",
            narrative=Narrative(text="ok"),
        )


class _FakeValidatorErrorAgent:
    async def process_task(self, task, context):
        return AgentPayload.make_error(
            agent="validator",
            error_message="Agent 'validator' timeout (30s)",
        )


class _FakeValidatorMissingValidationAgent:
    async def process_task(self, task, context):
        # Успешный envelope без validation-поля — должен считаться fail-closed.
        return AgentPayload.success(
            agent="validator",
            narrative=Narrative(text="validator response without validation"),
        )


def _capture_trace(monkeypatch):
    captured = []

    async def _fake_write_trace(cls, trace_data):
        captured.append(trace_data)
        return None

    monkeypatch.setattr(MultiAgentTraceLogger, "_enabled", True)
    monkeypatch.setattr(
        MultiAgentTraceLogger,
        "write_trace",
        classmethod(_fake_write_trace),
    )
    return captured


def _build_orchestrator(validator_agent):
    orchestrator = Orchestrator(enable_agents=["planner", "reporter", "validator"])
    orchestrator.is_initialized = True
    orchestrator.agents = {
        "planner": _FakePlannerAgent(),
        "reporter": _FakeReporterAgent(),
        "validator": validator_agent,
    }
    orchestrator.message_bus = None
    return orchestrator


def test_validator_error_is_fail_closed_and_traced(monkeypatch):
    captured = _capture_trace(monkeypatch)
    orchestrator = _build_orchestrator(_FakeValidatorErrorAgent())

    async def _run():
        return await orchestrator.process_request(
            user_request="build a quick report",
            board_id="board-1",
            context={},
            skip_validation=False,
        )

    result = asyncio.run(_run())
    assert result["status"] == "failed_quality_gate"
    assert "Validator execution error" in (result.get("quality_gate_message") or "")
    assert result["validator_error_count"] == 1
    assert result["validator_timeout_count"] == 1

    assert captured, "Trace payload was not captured"
    run_finish = next(e for e in captured[-1]["events"] if e.get("event") == "run_finish")
    details = run_finish.get("details") or {}
    assert details.get("validator_error_count") == 1
    assert details.get("validator_timeout_count") == 1

    val_failed = next(
        e for e in captured[-1]["events"]
        if e.get("event") == "validation_failed" and e.get("agent") == "validator"
    )
    assert (val_failed.get("details") or {}).get("reason") == "validator_error"


def test_missing_validation_field_is_fail_closed_and_traced(monkeypatch):
    captured = _capture_trace(monkeypatch)
    orchestrator = _build_orchestrator(_FakeValidatorMissingValidationAgent())

    async def _run():
        return await orchestrator.process_request(
            user_request="build a quick report",
            board_id="board-1",
            context={},
            skip_validation=False,
        )

    result = asyncio.run(_run())
    assert result["status"] == "failed_quality_gate"
    assert result["quality_gate_message"] == "Validator payload missing validation field"
    assert result["validator_missing_validation_field_count"] == 1

    assert captured, "Trace payload was not captured"
    run_finish = next(e for e in captured[-1]["events"] if e.get("event") == "run_finish")
    details = run_finish.get("details") or {}
    assert details.get("validator_missing_validation_field_count") == 1

    val_failed = next(
        e for e in captured[-1]["events"]
        if e.get("event") == "validation_failed" and e.get("agent") == "validator"
    )
    assert (val_failed.get("details") or {}).get("reason") == "missing_validation_field"
