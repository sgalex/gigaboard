"""Оркестратор: финальный Quality Gate отключён (раньше — fail-closed тесты валидатора)."""

import asyncio

from apps.backend.app.services.multi_agent.orchestrator import Orchestrator
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


def _build_orchestrator():
    orchestrator = Orchestrator(enable_agents=["planner", "reporter"])
    orchestrator.is_initialized = True
    orchestrator.agents = {
        "planner": _FakePlannerAgent(),
        "reporter": _FakeReporterAgent(),
    }
    orchestrator.message_bus = None
    return orchestrator


def test_no_final_quality_gate_returns_success():
    orchestrator = _build_orchestrator()

    async def _run():
        return await orchestrator.process_request(
            user_request="build a quick report",
            board_id="board-1",
            context={},
            skip_validation=False,
        )

    result = asyncio.run(_run())
    assert result["status"] == "success"
    assert result.get("quality_gate_failed") is False
    assert result.get("validator_error_count") == 0
    assert result.get("validator_missing_validation_field_count") == 0
