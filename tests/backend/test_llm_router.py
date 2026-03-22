import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from apps.backend.app.schemas import LLMProvider
from apps.backend.app.services.llm_router import LLMCallParams, LLMMessage, LLMRouter


class _DummyDBContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _db_session_factory():
    return _DummyDBContext()


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://llm.cubisio.ru/chat/completions")
    resp = httpx.Response(status_code=status_code, request=req)
    return httpx.HTTPStatusError(
        f"Client error '{status_code}' for url '{req.url}'",
        request=req,
        response=resp,
    )


def _external_config():
    return SimpleNamespace(
        id="test-config",
        provider=LLMProvider.EXTERNAL_OPENAI_COMPAT.value,
        temperature=0.11,
        max_tokens=222,
    )


def test_external_403_falls_back_to_internal_gigachat():
    gigachat = MagicMock()
    gigachat.chat_completion = AsyncMock(return_value="fallback-ok")

    router = LLMRouter(gigachat_service=gigachat, db_session_factory=_db_session_factory)
    router._resolve_llm_config = AsyncMock(return_value=_external_config())

    external_client = MagicMock()
    external_client.chat_completion = AsyncMock(
        side_effect=_http_status_error(403)
    )
    router._get_openai_client_from_config = MagicMock(return_value=external_client)

    params = LLMCallParams(messages=[LLMMessage(role="user", content="hello")])
    result = asyncio.run(
        router.chat_completion(user_id=None, params=params, agent_key="analyst")
    )

    assert result == "fallback-ok"
    external_client.chat_completion.assert_awaited_once()
    gigachat.chat_completion.assert_awaited_once()


def test_external_500_does_not_fallback():
    gigachat = MagicMock()
    gigachat.chat_completion = AsyncMock(return_value="fallback-ok")

    router = LLMRouter(gigachat_service=gigachat, db_session_factory=_db_session_factory)
    router._resolve_llm_config = AsyncMock(return_value=_external_config())

    external_client = MagicMock()
    external_client.chat_completion = AsyncMock(
        side_effect=_http_status_error(500)
    )
    router._get_openai_client_from_config = MagicMock(return_value=external_client)

    params = LLMCallParams(messages=[LLMMessage(role="user", content="hello")])
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(router.chat_completion(user_id=None, params=params, agent_key="analyst"))

    external_client.chat_completion.assert_awaited_once()
    gigachat.chat_completion.assert_not_called()
