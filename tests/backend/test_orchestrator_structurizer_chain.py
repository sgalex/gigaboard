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
    Source,
)


class _ScenarioPlannerAgent:
    def __init__(self):
        self.calls: list[str] = []

    async def process_task(self, task, context):
        task_type = task.get("type", "")
        self.calls.append(task_type)

        if task_type == "create_plan":
            plan = Plan(
                plan_id="p-struct-chain",
                user_request="test",
                steps=[
                    PlanStep(
                        step_id="1",
                        agent="research",
                        task={"description": "fetch"},
                        depends_on=[],
                    ),
                    PlanStep(
                        step_id="2",
                        agent="structurizer",
                        task={"description": "extract tables"},
                        depends_on=["1"],
                    ),
                    PlanStep(
                        step_id="3",
                        agent="reporter",
                        task={"description": "finalize"},
                        depends_on=["2"],
                    ),
                ],
            )
            return AgentPayload.success(agent="planner", plan=plan)

        if task_type == "expand_step":
            return AgentPayload.success(
                agent="planner",
                metadata={"expand_step_result": {"atomic": True, "sub_steps": []}},
            )

        if task_type == "revise_remaining":
            return AgentPayload.success(
                agent="planner",
                metadata={"remaining_steps": task.get("remaining_steps", [])},
            )

        return AgentPayload.success(agent="planner")


class _FakeResearchAgent:
    async def process_task(self, task, context):
        return AgentPayload.success(
            agent="research",
            sources=[
                Source(
                    url="https://example.com/source",
                    fetched=True,
                    content="raw page content",
                )
            ],
            narrative=Narrative(text="fetched"),
        )


class _FakeStructurizerEmptyAgent:
    async def process_task(self, task, context):
        # Ключевой кейс: structurizer формально success, но без таблиц.
        return AgentPayload.success(
            agent="structurizer",
            tables=[],
            narrative=Narrative(
                text="LLM returned non-JSON (possible content filter/blacklist)."
            ),
            metadata={"extraction_confidence": 0.0},
        )


class _FakeReporterAgent:
    async def process_task(self, task, context):
        return AgentPayload.success(
            agent="reporter",
            narrative=Narrative(text="final summary"),
        )


def test_structurizer_empty_tables_triggers_revise_remaining(monkeypatch):
    captured = []

    async def _fake_write_trace(cls, trace_data, **kwargs):
        captured.append(trace_data)
        return None

    monkeypatch.setenv("MULTI_AGENT_TRACE_ENABLED", "true")
    monkeypatch.setattr(
        MultiAgentTraceLogger,
        "write_trace",
        classmethod(_fake_write_trace),
    )

    planner = _ScenarioPlannerAgent()
    orchestrator = Orchestrator(
        enable_agents=["planner", "research", "structurizer", "reporter"]
    )
    orchestrator.is_initialized = True
    orchestrator.agents = {
        "planner": planner,
        "research": _FakeResearchAgent(),
        "structurizer": _FakeStructurizerEmptyAgent(),
        "reporter": _FakeReporterAgent(),
    }
    orchestrator.message_bus = None

    async def _run():
        return await orchestrator.process_request(
            user_request="extract data and summarize",
            board_id="board-1",
            context={},
            skip_validation=False,
        )

    result = asyncio.run(_run())

    assert result["status"] == "success"
    assert "revise_remaining" in planner.calls

    assert captured, "Trace payload was not captured"
    events = captured[-1]["events"]

    revise_req = next(
        e for e in events if e.get("event") == "revise_remaining_requested"
    )
    reason_suboptimal = (revise_req.get("details") or {}).get("reason_suboptimal", "")
    assert "Structurizer вернул пустые таблицы" in reason_suboptimal

    structurizer_end = next(
        e
        for e in events
        if e.get("event") == "agent_call_end"
        and e.get("phase") == "execute_step"
        and e.get("agent") == "structurizer"
    )
    assert (structurizer_end.get("details") or {}).get("tables") == 0

    assert not any(e.get("event") == "validation_passed" for e in events)
