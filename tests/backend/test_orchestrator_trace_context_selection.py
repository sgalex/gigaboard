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


def test_orchestrator_trace_contains_context_selection_metrics(monkeypatch):
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

    orchestrator = Orchestrator(enable_agents=["planner", "reporter"])
    orchestrator.is_initialized = True
    orchestrator.agents = {
        "planner": _FakePlannerAgent(),
        "reporter": _FakeReporterAgent(),
    }
    orchestrator.message_bus = None

    context = {
        "chat_history": [
            {"role": "user", "content": f"msg-{i}-" + ("z" * 1200)}
            for i in range(25)
        ],
    }

    async def _run():
        return await orchestrator.process_request(
            user_request="build a quick report",
            board_id="board-1",
            context=context,
            skip_validation=True,
        )

    result = asyncio.run(_run())

    assert result["status"] == "success"
    assert captured, "Trace payload was not captured"
    events = captured[-1]["events"]

    planner_start = next(
        e
        for e in events
        if e.get("event") == "agent_call_start"
        and e.get("agent") == "planner"
        and e.get("phase") == "planning"
    )
    selection = planner_start["details"]["context_selection"]
    assert selection["applied_for"] == "planner"
    assert selection["selection_task_type"] == "create_plan"
    assert selection["budget_items"] == 20
    assert selection["budget_chars"] == 70000
    assert selection["chat_history_before"] == 25
    assert selection["chat_history_after"] == 12
    assert selection["agent_results_before"] == 0
    assert selection["agent_results_after"] == 0
