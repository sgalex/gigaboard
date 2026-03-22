import asyncio

from apps.backend.app.services.multi_agent.orchestrator import (
    MultiAgentTraceLogger,
    Orchestrator,
)
from apps.backend.app.services.multi_agent.schemas.agent_payload import AgentPayload


class _FailingPlannerAgent:
    async def process_task(self, task, context):
        return AgentPayload.make_error(
            agent="planner",
            error_message="planner failed to build plan",
        )


def test_trace_never_stays_unknown_when_planner_fails(monkeypatch):
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

    orchestrator = Orchestrator(enable_agents=["planner"])
    orchestrator.is_initialized = True
    orchestrator.agents = {"planner": _FailingPlannerAgent()}
    orchestrator.message_bus = None

    async def _run():
        return await orchestrator.process_request(
            user_request="build plan",
            board_id="board-1",
            context={},
            skip_validation=True,
        )

    result = asyncio.run(_run())
    assert result["status"] == "error"
    assert captured, "Trace payload was not captured"
    assert captured[-1]["status"] == "error"

    run_finish = next(
        e for e in captured[-1]["events"] if e.get("event") == "run_finish"
    )
    assert run_finish.get("status") == "error"
