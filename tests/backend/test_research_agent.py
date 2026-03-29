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


def test_same_site_or_subdomain():
    agent = _make_agent()
    assert agent._same_site_or_subdomain(
        "https://example.com/a", "https://blog.example.com/b"
    )
    assert agent._same_site_or_subdomain(
        "https://example.com/", "https://sub.example.com/x"
    )
    assert not agent._same_site_or_subdomain(
        "https://evil.com/", "https://example.com/"
    )


def test_extract_links_from_html_regex():
    agent = _make_agent()
    html = (
        '<html><body><a href="/page">P</a>'
        '<a href="https://other.com/x">ext</a></body></html>'
    )
    links = agent._extract_links_from_html(html, "https://example.com/root")
    urls = {x["url"] for x in links}
    assert "https://example.com/page" in urls
    assert "https://other.com/x" in urls


def test_resolve_crawl_max_depth_research_controller():
    agent = _make_agent()
    assert (
        agent._resolve_crawl_max_depth(
            {},
            {"mode": "research", "controller": "research"},
        )
        >= 1
    )
    assert agent._resolve_crawl_max_depth({"crawl_max_depth": 1}, {}) == 1


def test_wave_crawl_fetches_follow_up():
    agent = _make_agent()
    calls = []

    async def fake_llm_select(**kwargs):
        return [{"url": "https://example.com/child", "anchor": "c"}]

    agent._llm_select_follow_urls = fake_llm_select  # type: ignore[method-assign]

    async def fake_fetch(src, idx, total, crawl_depth=0):
        calls.append((src.url, crawl_depth))
        html = (
            '<html><a href="/child">go</a></html>'
            if "root" in (src.url or "")
            else "<html>leaf</html>"
        )
        return (
            Source(
                url=src.url or "",
                title="t",
                content="x",
                fetched=True,
                crawl_depth=crawl_depth,
            ),
            html,
        )

    agent._fetch_single_with_html = fake_fetch  # type: ignore[method-assign]

    task = {"crawl_max_depth": 2, "max_urls": 2, "max_total_pages": 10}
    unfetched = [Source(url="https://example.com/root", fetched=False)]
    ctx = {"user_request": "find data", "pipeline_memory": {}}

    result = asyncio.run(agent._process_wave_crawl(task, unfetched, ctx, 2))
    assert result.status == "success"
    assert len(calls) >= 2
    depths = [c[1] for c in calls]
    assert 0 in depths and 1 in depths
