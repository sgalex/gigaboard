"""
Проверка пути: тул вызывается из ответа «LLM» (JSON с tool_requests), без force_tool_data_access.

Реальный GigaChat здесь не используется — мокируется AnalystAgent._call_llm:
  1-й ответ — только tool_requests (как будто модель решила догрузить таблицы);
  2-й ответ — обычный JSON с insights после подстановки tool_results.

Live с настоящей моделью:
  - в .env: MULTI_AGENT_ENABLE_TOOLS=true, MULTI_AGENT_FORCE_TOOL_DATA_ACCESS=false
  - отправьте запрос ассистенту/трансформации и смотрите трейс: reason у tool_request
    не должен начинаться с «force_tool_data_access».

Запуск: из корня репозитория
  uv run pytest tests/backend/test_orchestrator_llm_tool_initiative.py -v
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.multi_agent.orchestrator import (  # noqa: E402
    MultiAgentTraceLogger,
    Orchestrator,
)
from app.services.multi_agent.schemas.agent_payload import (  # noqa: E402
    AgentPayload,
    Narrative,
    Plan,
    PlanStep,
    ToolResult,
)
from app.services.multi_agent.agents.analyst import AnalystAgent  # noqa: E402


class _FakePlannerAgent:
    async def process_task(self, task, context):
        return AgentPayload.success(
            agent="planner",
            plan=Plan(
                plan_id="llm-tool-test-plan",
                user_request="test llm tool initiative",
                steps=[
                    PlanStep(
                        step_id="1",
                        agent="analyst",
                        task={"description": "Проанализируй данные (тест LLM-tool)."},
                        depends_on=[],
                    ),
                    PlanStep(
                        step_id="2",
                        agent="reporter",
                        task={
                            "description": "Краткий итог.",
                            "widget_type": "text",
                        },
                        depends_on=["1"],
                    ),
                ],
            ),
        )


class _FakeReporterAgent:
    async def process_task(self, task, context):
        return AgentPayload.success(
            agent="reporter",
            narrative=Narrative(text="ok"),
        )


@pytest.fixture
def env_llm_tool_no_force(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_ENABLE_TOOLS", "true")
    monkeypatch.setenv("MULTI_AGENT_FORCE_TOOL_DATA_ACCESS", "false")


def test_llm_initiated_tool_request_executes_without_force(env_llm_tool_no_force, monkeypatch):
    """
    При force_tool_data_access=false первый ответ «LLM» с tool_requests
    приводит к tool_request в трейсе с reason от модели, не к forced_bootstrap.
    """
    captured: list = []

    async def _fake_write_trace(cls, trace_data, *, force=False):
        captured.append(trace_data)
        return None

    monkeypatch.setattr(MultiAgentTraceLogger, "is_enabled", classmethod(lambda cls: True))
    monkeypatch.setattr(
        MultiAgentTraceLogger,
        "write_trace",
        classmethod(_fake_write_trace),
    )

    llm_responses = [
        json.dumps(
            {
                "tool_requests": [
                    {
                        "tool_name": "readTableListFromContentNodes",
                        "arguments": {
                            "nodeIds": ["11111111-1111-1111-1111-111111111111"],
                        },
                        "reason": "llm-initiated-test: need table list",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "insights": [
                    {
                        "finding": "Insight after mocked tool result",
                        "confidence": 0.9,
                    }
                ],
                "text": "Краткое резюме после тула.",
            },
            ensure_ascii=False,
        ),
    ]

    async def _fake_llm(self, messages, context=None, temperature=None, max_tokens=None):
        if not llm_responses:
            raise AssertionError("unexpected extra _call_llm invocation")
        return llm_responses.pop(0)

    async def _fake_tool(
        self,
        *,
        request,
        pipeline_context,
    ):
        rid = str(request.get("request_id") or "req-1")
        return ToolResult(
            request_id=rid,
            tool_name="readTableListFromContentNodes",
            success=True,
            data={
                "ok": True,
                "content_node_id": "11111111-1111-1111-1111-111111111111",
                "content_node_ids": ["11111111-1111-1111-1111-111111111111"],
                "nodes": [],
                "tables": [],
                "tables_count": 0,
            },
        )

    monkeypatch.setattr(AnalystAgent, "_call_llm", _fake_llm)
    monkeypatch.setattr(Orchestrator, "_execute_orchestrator_tool_request", _fake_tool)

    orchestrator = Orchestrator(enable_agents=["planner", "analyst", "reporter"])
    orchestrator.is_initialized = True
    orchestrator.agents = {
        "planner": _FakePlannerAgent(),
        "analyst": AnalystAgent(
            message_bus=MagicMock(),
            gigachat_service=None,  # type: ignore[arg-type]
            llm_router=None,
        ),
        "reporter": _FakeReporterAgent(),
    }
    orchestrator.message_bus = None

    async def _run():
        return await orchestrator.process_request(
            user_request="test llm tool initiative",
            board_id="board-llm-tool",
            user_id=None,
            context={"content_node_id": "11111111-1111-1111-1111-111111111111"},
            skip_validation=True,
        )

    result = asyncio.run(_run())

    assert result.get("status") == "success"
    assert captured, "trace payload was not captured"
    events = captured[-1]["events"]

    tool_req_events = [e for e in events if e.get("event") == "tool_request"]
    assert len(tool_req_events) >= 1
    reason = (tool_req_events[0].get("details") or {}).get("reason") or ""
    assert "force_tool_data_access" not in reason
    assert "llm-initiated-test" in reason
