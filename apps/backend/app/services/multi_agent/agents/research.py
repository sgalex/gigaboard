"""
ResearchAgent — загрузка контента по URL, API-вызовы, извлечение текста.

V2 агент, рефакторинг из ResearcherAgent.
Читает sources из agent_results, загружает контент, возвращает
AgentPayload(sources=[Source(fetched=True, content=...)]).
См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import logging
import json
import re as _re
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import AgentPayload, Narrative, Source
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


RESEARCH_SYSTEM_PROMPT = """
Вы — ResearchAgent в системе GigaBoard Multi-Agent V2.

ОСНОВНАЯ РОЛЬ: Загрузка полного содержимого из URL, API-вызовы, извлечение текста из HTML.

ВХОДНЫЕ ДАННЫЕ:
- sources из agent_results (от DiscoveryAgent) с fetched=False
- Или явные URL/API параметры в task

ВЫХОДНЫЕ ДАННЫЕ:
- sources с fetched=True и заполненным content

ВОЗМОЖНОСТИ:
- HTTP GET/POST запросы к REST API
- Базовый веб-скрапинг
- Парсинг JSON, CSV, HTML → текст
- SQL SELECT к БД (placeholder)

ОГРАНИЧЕНИЯ:
- Таймаут: 15с для веб-страниц, 30с для API
- Максимум 5000 символов контента на страницу
- Только SELECT для БД
- Макс. 10 URLs за один запуск
"""


class ResearchAgent(BaseAgent):
    """
    ResearchAgent — получение данных из внешних источников (V2).

    Рефакторинг из ResearcherAgent.
    Читает sources из agent_results, загружает контент по URL.
    Возвращает AgentPayload(sources=[Source(fetched=True)]).
    """

    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None,
    ):
        super().__init__(
            agent_name="research",
            message_bus=message_bus,
            system_prompt=system_prompt,
        )
        self.gigachat = gigachat_service

        # HTTP client с User-Agent и отключённой SSL верификацией
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10),
            verify=False,
            headers=headers,
        )

    def _get_default_system_prompt(self) -> str:
        return RESEARCH_SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # process_task — единая точка входа (V2)
    # ------------------------------------------------------------------

    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Загружает контент по URL / API. Возвращает AgentPayload.

        Логика:
        1. Собирает unfetched sources из agent_results
        2. Если есть явные URL в task — добавляет их
        3. Загружает контент, заполняет fetched=True
        """
        try:
            # 1. Собираем sources из agent_results и task
            unfetched = self._collect_unfetched_sources(task, context)

            # 2. Если передан явный URL/urls — добавляем
            explicit_url = task.get("url")
            explicit_urls = task.get("urls", [])
            if explicit_url and isinstance(explicit_url, str):
                unfetched.append(Source(url=explicit_url, fetched=False))
            if explicit_urls and isinstance(explicit_urls, list):
                for u in explicit_urls:
                    if isinstance(u, str) and u.startswith("http"):
                        unfetched.append(Source(url=u, fetched=False))
                    elif isinstance(u, dict) and u.get("url"):
                        unfetched.append(Source(url=u["url"], title=u.get("title"), fetched=False))

            # 3. SQL-запрос (fallback)
            if not unfetched and task.get("query") and task.get("database"):
                return await self._query_database(task)

            if not unfetched:
                return self._error_payload(
                    "No URLs to fetch — no unfetched sources in agent_results and no URL in task.",
                    suggestions=[
                        "Ensure DiscoveryAgent ran successfully",
                        "Provide 'url' or 'urls' in task",
                    ],
                )

            # 4. Лимитируем
            max_urls = task.get("max_urls", 10)
            unfetched = unfetched[:max_urls]

            self.logger.info(f"🌐 Fetching content from {len(unfetched)} URLs...")

            # 5. Загружаем
            fetched_sources: List[Source] = []
            errors: List[str] = []

            for i, src in enumerate(unfetched, 1):
                result_src = await self._fetch_single(src, i, len(unfetched))
                if result_src.fetched:
                    fetched_sources.append(result_src)
                else:
                    fetched_sources.append(result_src)
                    if not result_src.content:
                        errors.append(f"{src.url}: failed to fetch")

            ok_count = sum(1 for s in fetched_sources if s.fetched)
            self.logger.info(
                f"✅ Fetched {ok_count}/{len(unfetched)} pages "
                f"({len(errors)} errors)"
            )

            if ok_count == 0:
                return self._error_payload(
                    f"Failed to fetch any pages. Errors: {'; '.join(errors[:3])}",
                    suggestions=["Check URL availability", "Verify network connection"],
                )

            # 6. Narrative — краткая сводка
            summary_parts = [
                f"Загружено {ok_count} из {len(unfetched)} страниц."
            ]
            if errors:
                summary_parts.append(f"Ошибки: {len(errors)}.")

            return self._success_payload(
                sources=fetched_sources,
                narrative=Narrative(
                    text="\n".join(summary_parts), format="markdown"
                ),
                metadata={
                    "pages_fetched": ok_count,
                    "pages_failed": len(errors),
                    "total_content_chars": sum(
                        len(s.content or "") for s in fetched_sources
                    ),
                },
            )

        except Exception as e:
            self.logger.error(f"Error in research: {e}", exc_info=True)
            return self._error_payload(str(e))

    # ------------------------------------------------------------------
    # Source collection from agent_results
    # ------------------------------------------------------------------

    def _collect_unfetched_sources(
        self, task: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> List[Source]:
        """
        Собирает unfetched Source объекты из agent_results.

        V2: agent_results — list[dict] (хронологический список AgentPayload).
        Ищет sources[] с fetched=False в каждом AgentPayload.
        Также поддерживает V1 формат (results[], pages[]).
        """
        unfetched: List[Source] = []

        if not context or "agent_results" not in context:
            return unfetched

        # Изменение #2: agent_results — list (см. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md)
        agent_results = context["agent_results"]
        for result in agent_results:
            if not isinstance(result, dict):
                continue

            # V2 формат: AgentPayload.sources[]
            sources_raw = result.get("sources", [])
            if isinstance(sources_raw, list):
                for s in sources_raw:
                    if isinstance(s, dict):
                        if not s.get("fetched", False) and s.get("url"):
                            unfetched.append(Source(
                                url=s["url"],
                                title=s.get("title"),
                                snippet=s.get("snippet"),
                                fetched=False,
                                source_type=s.get("source_type", "web"),  # type: ignore[arg-type]
                            ))
                    elif isinstance(s, str) and s.startswith("http"):
                        unfetched.append(Source(url=s, fetched=False))

            # V1 fallback: results[] с url
            results_raw = result.get("results", [])
            if isinstance(results_raw, list) and not sources_raw:
                for r in results_raw:
                    if isinstance(r, dict) and r.get("url"):
                        unfetched.append(Source(
                            url=r["url"],
                            title=r.get("title"),
                            snippet=r.get("snippet"),
                            fetched=False,
                        ))

        self.logger.info(
            f"📦 Collected {len(unfetched)} unfetched sources from agent_results"
        )
        return unfetched

    # ------------------------------------------------------------------
    # Single URL fetch
    # ------------------------------------------------------------------

    async def _fetch_single(
        self, src: Source, idx: int, total: int
    ) -> Source:
        """Загружает одну страницу и возвращает обновлённый Source."""
        url = src.url
        try:
            self.logger.info(f"   [{idx}/{total}] Fetching: {url}")

            response = await self.http_client.get(
                url, timeout=15.0, follow_redirects=True
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "text/html" in content_type:
                text = self._extract_text_from_html(response.text)
                content = text[:5000]
                title = self._extract_title_from_html(response.text) or src.title
            elif "application/json" in content_type:
                content = response.text[:5000]
                title = src.title
            else:
                content = response.text[:5000]
                title = src.title

            self.logger.info(f"   ✅ OK: {len(content)} chars extracted")

            return Source(
                url=url,
                title=title or src.title,
                snippet=src.snippet,
                content=content,
                source_type=src.source_type,
                status_code=response.status_code,
                fetched=True,
                content_size=len(response.content),
            )

        except httpx.TimeoutException:
            self.logger.warning(f"   ⏱️ Timeout: {url}")
            return Source(
                url=url, title=src.title, snippet=src.snippet,
                fetched=False, source_type=src.source_type,
            )
        except httpx.HTTPStatusError as e:
            self.logger.warning(f"   ❌ HTTP {e.response.status_code}: {url}")
            return Source(
                url=url, title=src.title, snippet=src.snippet,
                fetched=False, source_type=src.source_type,
                status_code=e.response.status_code,
            )
        except Exception as e:
            self.logger.warning(f"   ❌ {type(e).__name__}: {url}")
            return Source(
                url=url, title=src.title, snippet=src.snippet,
                fetched=False, source_type=src.source_type,
            )

    # ------------------------------------------------------------------
    # HTML helpers
    # ------------------------------------------------------------------

    def _extract_text_from_html(self, html: str) -> str:
        """Базовая очистка HTML — убираем теги, оставляем текст."""
        html = _re.sub(
            r"<script[^>]*>.*?</script>", "", html,
            flags=_re.DOTALL | _re.IGNORECASE,
        )
        html = _re.sub(
            r"<style[^>]*>.*?</style>", "", html,
            flags=_re.DOTALL | _re.IGNORECASE,
        )
        text = _re.sub(r"<[^>]+>", " ", html)
        text = _re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_title_from_html(self, html: str) -> Optional[str]:
        """Извлекает <title> из HTML."""
        m = _re.search(
            r"<title[^>]*>(.*?)</title>", html,
            _re.IGNORECASE | _re.DOTALL,
        )
        return m.group(1).strip()[:200] if m else None

    # ------------------------------------------------------------------
    # Database (placeholder)
    # ------------------------------------------------------------------

    async def _query_database(self, task: Dict[str, Any]):
        """SQL SELECT — placeholder."""
        query = task.get("query", "")
        if not query.strip().lower().startswith("select"):
            return self._error_payload(
                "Only SELECT queries allowed",
                suggestions=["Use SELECT statement"],
            )

        self.logger.warning("⚠️ Database query not implemented yet (placeholder)")
        return self._success_payload(
            narrative_text=f"Database query placeholder: {query[:100]}",
            metadata={"database_query": query, "note": "Not implemented"},
        )

    # ------------------------------------------------------------------
    # Schema helpers (from V1)
    # ------------------------------------------------------------------

    def _infer_schema(self, data: Any) -> Dict[str, Any]:
        """Определяет schema из данных."""
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict):
                cols = list(first.keys())
                return {"columns": cols, "types": [self._infer_type(first[c]) for c in cols]}
        elif isinstance(data, dict):
            cols = list(data.keys())
            return {"columns": cols, "types": [self._infer_type(data[c]) for c in cols]}
        return {"columns": [], "types": []}

    @staticmethod
    def _infer_type(value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "unknown"

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()
