import asyncio
from unittest.mock import AsyncMock, MagicMock

from apps.backend.app.services.multi_agent.agents.research import ResearchAgent
from apps.backend.app.services.multi_agent.schemas.agent_payload import Source


def _make_agent() -> ResearchAgent:
    message_bus = MagicMock()
    message_bus.subscribe = AsyncMock()
    message_bus.publish = AsyncMock()

    gigachat = MagicMock()
    gigachat.chat_completion = AsyncMock(return_value="ok")

    return ResearchAgent(message_bus=message_bus, gigachat_service=gigachat)


def test_collect_unfetched_skips_already_failed_and_fetched_urls():
    agent = _make_agent()

    context = {
        "agent_results": [
            {
                "agent": "discovery",
                "sources": [
                    {"url": "https://example.com/a", "fetched": False},
                    {"url": "https://example.com/b", "fetched": False},
                    {"url": "https://example.com/c", "fetched": False},
                ],
            },
            {
                "agent": "research",
                "status": "success",
                "sources": [
                    {"url": "https://example.com/a", "fetched": True, "content": "ok"},
                    {"url": "https://example.com/b", "fetched": False},
                ],
            },
        ]
    }

    unfetched = agent._collect_unfetched_sources({}, context)
    urls = [s.url for s in unfetched]

    assert urls == ["https://example.com/c"]


def test_process_task_does_not_retry_previous_failed_explicit_url():
    agent = _make_agent()

    failed_url = "https://example.com/failed"
    new_url = "https://example.com/new"

    context = {
        "agent_results": [
            {
                "agent": "research",
                "status": "success",
                "sources": [
                    {"url": failed_url, "fetched": False},
                ],
            }
        ]
    }

    agent._fetch_single = AsyncMock(
        return_value=Source(url=new_url, fetched=True, content="content")
    )

    task = {"urls": [failed_url, new_url], "max_urls": 10}
    result = asyncio.run(agent.process_task(task, context))

    assert result.status == "success"
    assert (result.metadata or {}).get("pages_fetched") == 1
    assert len(result.sources or []) == 1
    assert result.sources[0].url == new_url

    called_urls = [call.args[0].url for call in agent._fetch_single.await_args_list]
    assert called_urls == [new_url]


def test_collect_unfetched_skips_failed_urls_from_research_error_status():
    agent = _make_agent()

    context = {
        "agent_results": [
            {
                "agent": "discovery",
                "sources": [
                    {"url": "https://example.com/failed", "fetched": False},
                    {"url": "https://example.com/new", "fetched": False},
                ],
            },
            {
                "agent": "research",
                "status": "error",
                "sources": [
                    {"url": "https://example.com/failed", "fetched": False},
                ],
            },
        ]
    }

    unfetched = agent._collect_unfetched_sources({}, context)
    urls = [s.url for s in unfetched]

    assert urls == ["https://example.com/new"]
