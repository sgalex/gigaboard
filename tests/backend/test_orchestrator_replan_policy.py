import asyncio

from apps.backend.app.services.multi_agent import orchestrator as orchestrator_module
from apps.backend.app.services.multi_agent.execution_policy import ExecutionPolicy
from apps.backend.app.services.multi_agent.orchestrator import Orchestrator
from apps.backend.app.services.multi_agent.schemas.agent_payload import (
    AgentPayload,
    Plan,
    PlanStep,
)


class _FakePlannerAgent:
    async def process_task(self, task, context):
        plan = Plan(
            plan_id="p-replan",
            user_request="replan",
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


def test_replan_uses_execution_policy_and_effective_context(monkeypatch):
    orchestrator = Orchestrator(enable_agents=["planner"])
    orchestrator.is_initialized = True
    orchestrator.agents = {"planner": _FakePlannerAgent()}

    captured = {}
    selected_calls = []

    def _fake_resolve_execution_policy(agent_name, task_type, runtime_options=None):
        assert agent_name == "planner"
        assert task_type == "replan"
        assert runtime_options == {"timeout_sec": 77}
        return ExecutionPolicy(timeout_sec=77, max_retries=2, context_ladder=["compact", "minimal"])

    def _fake_select_context_for_step(
        agent_name,
        pipeline_context,
        task_type=None,
        compaction_level="full",
        runtime_options=None,
    ):
        selected_calls.append((agent_name, task_type, compaction_level, runtime_options))
        return {
            **pipeline_context,
            "_context_selection_compaction_level": compaction_level,
        }

    async def _fake_execute_with_retry(
        agent_name,
        task,
        context,
        *,
        max_retries=None,
        timeout_override=None,
        context_ladder=None,
        context_factory=None,
        on_retry=None,
    ):
        captured["agent_name"] = agent_name
        captured["task"] = task
        captured["context"] = context
        captured["max_retries"] = max_retries
        captured["timeout_override"] = timeout_override
        captured["context_ladder"] = context_ladder
        captured["factory_compact"] = context_factory("compact") if context_factory else None
        captured["factory_minimal"] = context_factory("minimal") if context_factory else None
        plan = Plan(
            plan_id="p-2",
            user_request="replan",
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

    monkeypatch.setattr(
        orchestrator_module,
        "resolve_execution_policy",
        _fake_resolve_execution_policy,
    )
    monkeypatch.setattr(
        orchestrator_module,
        "select_context_for_step",
        _fake_select_context_for_step,
    )
    monkeypatch.setattr(orchestrator, "_execute_with_retry", _fake_execute_with_retry)

    pipeline_context = {
        "user_request": "test",
        "agent_results": [],
        "_agent_runtime_options_map": {"planner": {"timeout_sec": 77}},
    }

    async def _run():
        return await orchestrator._replan(
            current_plan={"plan_id": "old", "steps": []},
            pipeline_context=pipeline_context,
            extra_context={"last_error": "timeout"},
        )

    plan = asyncio.run(_run())

    assert plan is not None
    assert captured["agent_name"] == "planner"
    assert captured["task"]["type"] == "replan"
    assert captured["max_retries"] == 2
    assert captured["timeout_override"] == 77
    assert captured["context_ladder"] == ["compact", "minimal"]
    assert captured["context"]["_context_selection_compaction_level"] == "compact"
    assert captured["factory_compact"]["_context_selection_compaction_level"] == "compact"
    assert captured["factory_minimal"]["_context_selection_compaction_level"] == "minimal"
    assert selected_calls, "select_context_for_step should be used for replan"
