"""
Unit tests for StructurizerAgent: parsing, sanitization, content extraction.
См. docs/MULTI_AGENT.md — StructurizerAgent, docs/CONTEXT_ENGINEERING.md — усечение тяжёлых полей.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.backend.app.services.multi_agent.agents.structurizer import StructurizerAgent


@pytest.fixture
def mock_message_bus():
    bus = MagicMock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_gigachat():
    service = MagicMock()
    service.chat_completion = AsyncMock(return_value="{}")
    return service


@pytest.fixture
def agent(mock_message_bus, mock_gigachat):
    return StructurizerAgent(
        message_bus=mock_message_bus,
        gigachat_service=mock_gigachat,
    )


class TestStructurizerParseResponse:
    def test_empty_response_returns_empty_result(self, agent):
        r = agent._parse_response("")
        assert r["tables"] == []
        assert r["extraction_confidence"] == 0.0
        assert "non-JSON" in (r.get("notes") or "")

    def test_no_json_object_returns_empty_result(self, agent):
        r = agent._parse_response("Sorry, I cannot help with that.")
        assert r["tables"] == []
        assert r["extraction_confidence"] == 0.0

    def test_plain_json_parses(self, agent):
        payload = {
            "tables": [
                {
                    "name": "t1",
                    "columns": [{"name": "a", "type": "int"}],
                    "rows": [[1]],
                }
            ],
            "extraction_confidence": 0.9,
            "notes": "ok",
        }
        r = agent._parse_response(json.dumps(payload, ensure_ascii=False))
        assert len(r["tables"]) == 1
        assert r["extraction_confidence"] == 0.9

    def test_markdown_fenced_json_parses(self, agent):
        inner = json.dumps(
            {"tables": [], "extraction_confidence": 0.5, "notes": "fenced"},
            ensure_ascii=False,
        )
        r = agent._parse_response(f"Here you go:\n```json\n{inner}\n```")
        assert r["notes"] == "fenced"
        assert r["extraction_confidence"] == 0.5

    def test_trailing_comma_repaired(self, agent):
        bad = '{"tables": [], "entities": [], "key_value_pairs": {}, "extraction_confidence": 0.8,}'
        r = agent._parse_response(bad)
        assert r["extraction_confidence"] == 0.8


class TestStructurizerSanitize:
    def test_truncates_long_content(self, agent):
        long_text = "x" * 20000
        out = agent._sanitize_content_for_llm(long_text)
        assert len(out) <= 10000 + len("\n\n... (truncated)")
        assert "truncated" in out

    def test_replaces_urls(self, agent):
        s = "See https://example.com/path and http://t.ru/a?q=1 for more"
        out = agent._sanitize_content_for_llm(s)
        assert "https://" not in out
        assert "[URL]" in out


class TestStructurizerExtractRawContent:
    def test_joins_fetched_sources_from_agent_results(self, agent):
        ctx = {
            "agent_results": [
                {
                    "agent": "research",
                    "sources": [
                        {
                            "url": "https://a.example/page",
                            "fetched": True,
                            "content": "First article body",
                        },
                        {
                            "url": "https://b.example/page",
                            "fetched": True,
                            "content": "Second article body",
                        },
                    ],
                }
            ]
        }
        raw = agent._extract_raw_content({"description": "x"}, ctx)
        assert "=== Source: https://a.example/page ===" in raw
        assert "First article body" in raw
        assert "Second article body" in raw

    def test_task_raw_content_priority(self, agent):
        ctx = {
            "agent_results": [
                {
                    "agent": "research",
                    "sources": [
                        {"url": "https://x.com", "fetched": True, "content": "ignored"},
                    ],
                }
            ]
        }
        raw = agent._extract_raw_content(
            {"description": "x", "raw_content": "direct payload"},
            ctx,
        )
        assert raw == "direct payload"


class TestStructurizerProcessTaskIntegration:
    """Поведение process_task при типичных ответах LLM (без реального API)."""

    def test_empty_llm_response_yields_zero_confidence_tables(
        self, agent, mock_gigachat
    ):
        """Как в прод-логах: длина ответа 0 → парсер возвращает пустой результат."""
        mock_gigachat.chat_completion = AsyncMock(return_value="")

        ctx = {
            "agent_results": [
                {
                    "agent": "research",
                    "sources": [
                        {
                            "url": "https://example.com/a",
                            "fetched": True,
                            "content": "Some text about sales 2025",
                        },
                    ],
                }
            ]
        }

        async def _run():
            return await agent.process_task(
                {"description": "Extract table"},
                ctx,
            )

        result = asyncio.run(_run())
        assert result.status == "success"
        assert not result.has_tables
        assert (result.metadata or {}).get("extraction_confidence") == 0.0
        assert result.narrative is not None
        assert "non-json" in (result.narrative.text or "").lower()

    def test_valid_llm_json_returns_tables(self, agent, mock_gigachat):
        mock_gigachat.chat_completion = AsyncMock(
            return_value=json.dumps(
                {
                    "tables": [
                        {
                            "name": "sales",
                            "columns": [{"name": "year", "type": "int"}],
                            "rows": [[2025]],
                        }
                    ],
                    "extraction_confidence": 0.88,
                    "notes": "ok",
                },
                ensure_ascii=False,
            )
        )

        async def _run():
            return await agent.process_task(
                {
                    "description": "Extract",
                    "raw_content": "dummy",
                },
                {},
            )

        result = asyncio.run(_run())
        assert result.status == "success"
        assert result.has_tables
        assert (result.metadata or {}).get("extraction_confidence") == 0.88


class TestStructurizerConvert:
    def test_entities_and_kv_become_tables(self, agent):
        raw = {
            "tables": [],
            "entities": [
                {"type": "company", "value": "Acme", "confidence": 0.9},
            ],
            "key_value_pairs": {"total": 100},
            "extraction_confidence": 0.7,
        }
        tables = agent._convert_to_content_tables(raw)
        names = {t.name for t in tables}
        assert "entities" in names
        assert "metadata" in names
