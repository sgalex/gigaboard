"""
ResearchAgent — загрузка контента по URL, API-вызовы, извлечение текста.

V2 агент, рефакторинг из ResearcherAgent.
Читает sources из agent_results, загружает контент, возвращает
AgentPayload(sources=[Source(fetched=True, content=...)]).
См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import asyncio
import logging
import json
import re as _re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[misc, assignment]

from app.services.multi_agent.runtime_overrides import ma_bool, ma_float, ma_int
from app.services.multi_agent.source_url_meta import (
    classify_resource_from_http,
    infer_resource_kind_from_url,
)

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import (
    AgentPayload,
    DiscoveredResource,
    Narrative,
    Source,
)
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)

# Не тратить HTTP на заведомо нерелевантные справочные порталы (совпадает с DiscoveryAgent).
_SKIP_FETCH_DOMAIN_FRAGMENTS = (
    "support.google.com",
    "support.google.ru",
    "play.google.com",
    "maps.google.com",
    "accounts.google.com",
)

# Пути и паттерны, которые обычно не ведут к контенту для аналитики
_JUNK_PATH_SUBSTRINGS = (
    "/login",
    "/signin",
    "/signup",
    "/register",
    "/cart",
    "/checkout",
    "/account",
    "/password",
    "/logout",
    "mailto:",
    "javascript:",
)

_MAX_ANCHOR_CHARS = 160
# Фрагмент текста страницы в промпт LLM для оценки релевантности задаче
_MAX_PAGE_RELEVANCE_LLM_EXCERPT_DEFAULT = 1600

# Отрезаем хвост «[Формат ответа: …]» из research-чата — он мешает релевантности краулера.
_FORMAT_HINT_SPLIT = _re.compile(r"\n\n\[Формат ответа:", _re.MULTILINE)

# Стоп-слова для токенов запроса (релевантность ссылок).
_CRAWL_QUERY_STOPWORDS = frozenset(
    {
        "для",
        "при",
        "как",
        "это",
        "все",
        "год",
        "года",
        "году",
        "лет",
        "или",
        "был",
        "было",
        "были",
        "есть",
        "что",
        "так",
        "она",
        "они",
        "без",
        "под",
        "над",
        "про",
        "где",
        "вас",
        "его",
        "ему",
        "них",
        "том",
        "туда",
        "тут",
        "там",
        "какой",
        "какая",
        "какие",
        "который",
        "которая",
        "самые",
        "самый",
        "сама",
        "само",
        "очень",
        "более",
        "мне",
        "вот",
        "ещё",
        "еще",
        "тоже",
        "уже",
        "только",
        "можно",
        "нужно",
        "если",
        "чтобы",
        "представь",
        "данные",
        "виде",
        "таблиц",
        "таблицы",
        "колонки",
        "строки",
        "краткий",
        "итог",
    }
)

# Запрос похож на развлечения / людей — штрафуем типичные нерелевантные рубрики порталов.
_ENTERTAINMENT_TOPIC_MARKERS: tuple[str, ...] = (
    "актрис",
    "актер",
    "актеров",
    "фото",
    "звезд",
    "знаменит",
    "кино",
    "сериал",
    "музык",
    "модел",
    "шоу",
    "бьюти",
    "красив",
    "celebrit",
)

_OFFTOPIC_PATH_MARKERS: tuple[str, ...] = (
    "/games/",
    "/sport/",
    "/army/",
    "/tech/",
    "/auto/",
    "/finance/",
    "/realty/",
    "/business/",
    "/politics/",
    "/crime/",
    "/horoscope/",
)


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
- Макс. 10 URLs за один запуск (корневая волна; при crawl_max_depth>1 — волны + LLM-отбор ссылок)
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
        llm_router: Optional[Any] = None,
    ):
        super().__init__(
            agent_name="research",
            message_bus=message_bus,
            system_prompt=system_prompt,
        )
        self.gigachat = gigachat_service
        self.llm_router = llm_router

        # HTTP client with Firefox-like browser headers.
        # Some sites aggressively block generic bot/default clients.
        headers = self._build_firefox_headers()

        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10),
            verify=False,
            headers=headers,
        )

    @staticmethod
    def _build_firefox_headers() -> Dict[str, str]:
        """Return browser-like headers that emulate a regular Firefox request."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
                "Gecko/20100101 Firefox/124.0"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "TE": "trailers",
            "DNT": "1",
        }

    def _get_default_system_prompt(self) -> str:
        return RESEARCH_SYSTEM_PROMPT

    @staticmethod
    def _should_skip_url(url: str) -> Tuple[bool, Optional[str]]:
        """Пропуск загрузки для доменов-справок — экономия времени и трафика."""
        if not url or not url.startswith("http"):
            return False, None
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            return False, None
        for frag in _SKIP_FETCH_DOMAIN_FRAGMENTS:
            if frag in host:
                return True, f"skipped low-value domain ({frag})"
        return False, None

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

        При crawl_max_depth > 1 — волновой обход: корень (Discovery) → извлечение ссылок
        → LLM-отбор релевантных → следующая волна (см. metadata.crawl_waves).
        """
        try:
            unfetched = self._collect_unfetched_sources(task, context)

            explicit_url = task.get("url")
            explicit_urls = task.get("urls", [])
            if explicit_url and isinstance(explicit_url, str):
                _, rk_e = infer_resource_kind_from_url(explicit_url)
                unfetched.append(
                    Source(
                        url=explicit_url,
                        fetched=False,
                        resource_kind=rk_e,  # type: ignore[arg-type]
                    )
                )
            if explicit_urls and isinstance(explicit_urls, list):
                for u in explicit_urls:
                    if isinstance(u, str) and u.startswith("http"):
                        _, rk_u = infer_resource_kind_from_url(u)
                        unfetched.append(
                            Source(
                                url=u,
                                fetched=False,
                                resource_kind=rk_u,  # type: ignore[arg-type]
                            )
                        )
                    elif isinstance(u, dict) and u.get("url"):
                        _, rk_d = infer_resource_kind_from_url(u["url"])
                        unfetched.append(
                            Source(
                                url=u["url"],
                                title=u.get("title"),
                                fetched=False,
                                resource_kind=rk_d,  # type: ignore[arg-type]
                            )
                        )

            if context and isinstance(context.get("agent_results"), list):
                history_results = context.get("agent_results") or []
                already_fetched, already_failed = self._collect_research_url_history(history_results)
                deduped: List[Source] = []
                seen_now: set[str] = set()
                skipped_failed = 0
                for src in unfetched:
                    nu = self._normalize_url(src.url)
                    if nu in seen_now:
                        continue
                    if nu in already_fetched or nu in already_failed:
                        if nu in already_failed:
                            skipped_failed += 1
                        continue
                    seen_now.add(nu)
                    deduped.append(src)
                if skipped_failed:
                    self.logger.info(
                        "♻️ Skip %s previously failed URL(s) in current session",
                        skipped_failed,
                    )
                unfetched = deduped

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

            crawl_max = self._resolve_crawl_max_depth(task, context)
            if crawl_max <= 1:
                return await self._process_flat_fetch(task, unfetched, context)

            return await self._process_wave_crawl(task, unfetched, context, crawl_max)

        except Exception as e:
            self.logger.error(f"Error in research: {e}", exc_info=True)
            return self._error_payload(str(e))

    def _resolve_crawl_max_depth(
        self, task: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> int:
        """Число волн загрузки: 1 = только корень (старое поведение)."""
        raw = task.get("crawl_max_depth")
        if raw is not None:
            try:
                return max(1, int(raw))
            except (TypeError, ValueError):
                pass
        ctx = context or {}
        if ctx.get("mode") == "research" and ctx.get("controller") == "research":
            return ma_int("MULTI_AGENT_RESEARCH_CRAWL_MAX_DEPTH", 3)
        return ma_int("MULTI_AGENT_RESEARCH_CRAWL_MAX_DEPTH", 1)

    async def _process_flat_fetch(
        self,
        task: Dict[str, Any],
        unfetched: List[Source],
        context: Optional[Dict[str, Any]],
    ) -> AgentPayload:
        """Один проход загрузки (без внутренних волн)."""
        max_urls = task.get("max_urls", 10)
        unfetched = unfetched[:max_urls]

        self.logger.info(f"🌐 Fetching content from {len(unfetched)} URLs (flat)...")

        fetched_sources: List[Source] = []
        errors: List[str] = []

        for i, src in enumerate(unfetched, 1):
            skip, skip_reason = self._should_skip_url(src.url or "")
            if skip:
                self.logger.info(
                    "⏭️ Skip fetch [%s/%s]: %s — %s",
                    i,
                    len(unfetched),
                    (src.url or "")[:80],
                    skip_reason,
                )
                _, rk_skip = infer_resource_kind_from_url(src.url or "")
                rk_use = (
                    src.resource_kind
                    if src.resource_kind != "unknown"
                    else rk_skip
                )
                fetched_sources.append(
                    Source(
                        url=src.url,
                        title=src.title,
                        snippet=src.snippet,
                        fetched=False,
                        source_type=src.source_type,
                        status_code=None,
                        mime_type=src.mime_type,
                        resource_kind=rk_use,  # type: ignore[arg-type]
                        metadata={
                            **(src.metadata or {}),
                            "skipped": True,
                            "reason": skip_reason,
                        },
                    )
                )
                errors.append(f"{src.url}: {skip_reason}")
                continue
            result_src = await self._fetch_single(src, i, len(unfetched), crawl_depth=0)
            fetched_sources.append(result_src)
            if not result_src.fetched or not result_src.content:
                errors.append(f"{src.url}: failed to fetch")

        ok_count = sum(1 for s in fetched_sources if s.fetched)
        self.logger.info(
            f"✅ Fetched {ok_count}/{len(unfetched)} pages ({len(errors)} errors)"
        )

        if ok_count == 0:
            return self._error_payload(
                f"Failed to fetch any pages. Errors: {'; '.join(errors[:3])}",
                suggestions=["Check URL availability", "Verify network connection"],
            )

        user_request, goal = self._research_task_text_from_context(context)
        filtered, tr_meta = await self._filter_fetched_sources_by_task_relevance(
            user_request, goal, fetched_sources, context
        )
        if filtered is None:
            return self._error_payload(
                "По оценке модели ни одна из загруженных страниц не признана релевантной задаче.",
                suggestions=[
                    "Уточните формулировку запроса",
                    "Повторите запуск — оркестратор может перепланировать Discovery",
                ],
                metadata=tr_meta,
            )
        fetched_sources = filtered
        ok_count = sum(1 for s in fetched_sources if s.fetched)

        summary_parts = [f"Загружено {ok_count} из {len(unfetched)} страниц."]
        if errors:
            summary_parts.append(f"Ошибки: {len(errors)}.")

        discovered, disc_probe = await self._finalize_discovered_resources(fetched_sources)
        success_meta: Dict[str, Any] = {
            "pages_fetched": ok_count,
            "pages_failed": len(errors),
            "total_content_chars": sum(len(s.content or "") for s in fetched_sources),
            "crawl_max_depth": 1,
            "discovered_resources_count": len(discovered),
            "discovered_resources_probe": disc_probe,
        }
        success_meta.update(tr_meta)
        return self._success_payload(
            sources=fetched_sources,
            discovered_resources=discovered,
            narrative=Narrative(text="\n".join(summary_parts), format="markdown"),
            metadata=success_meta,
        )

    async def _process_wave_crawl(
        self,
        task: Dict[str, Any],
        unfetched: List[Source],
        context: Optional[Dict[str, Any]],
        crawl_max_depth: int,
    ) -> AgentPayload:
        """
        Волны: wave 0 — корневые URL; далее извлечение ссылок + LLM + загрузка.
        """
        max_total = task.get("max_total_pages")
        if max_total is None:
            max_total = ma_int("MULTI_AGENT_RESEARCH_MAX_TOTAL_PAGES", 30)
        else:
            try:
                max_total = max(1, int(max_total))
            except (TypeError, ValueError):
                max_total = ma_int("MULTI_AGENT_RESEARCH_MAX_TOTAL_PAGES", 30)

        root_cap = task.get("max_urls", 10)
        try:
            root_cap = max(1, int(root_cap))
        except (TypeError, ValueError):
            root_cap = 10

        per_wave_cap = task.get("crawl_max_urls_per_wave")
        if per_wave_cap is None:
            per_wave_cap = ma_int("MULTI_AGENT_RESEARCH_CRAWL_MAX_URLS_PER_WAVE", 8)
        else:
            try:
                per_wave_cap = max(1, int(per_wave_cap))
            except (TypeError, ValueError):
                per_wave_cap = 8

        max_llm_candidates = task.get("crawl_max_llm_candidates")
        if max_llm_candidates is None:
            max_llm_candidates = ma_int("MULTI_AGENT_RESEARCH_CRAWL_MAX_LLM_CANDIDATES", 40)
        else:
            try:
                max_llm_candidates = max(5, int(max_llm_candidates))
            except (TypeError, ValueError):
                max_llm_candidates = 40

        visited: set[str] = set()
        if context and isinstance(context.get("agent_results"), list):
            af, afail = self._collect_research_url_history(context["agent_results"])
            visited |= af
            visited |= afail

        all_sources: List[Source] = []
        wave_logs: List[Dict[str, Any]] = []
        total_pages = 0
        errors: List[str] = []

        user_request, goal = self._research_task_text_from_context(context)

        queue: List[Tuple[Source, int]] = [
            (src, 0) for src in unfetched[:root_cap]
        ]

        for wave in range(crawl_max_depth):
            if not queue or total_pages >= max_total:
                break

            wave_sources: List[Source] = []
            html_by_norm: Dict[str, str] = {}

            batch = queue[:]
            queue = []

            for j, (src, depth) in enumerate(batch, 1):
                if total_pages >= max_total:
                    break
                nu = self._normalize_url(src.url or "")
                if nu in visited:
                    continue
                skip, skip_reason = self._should_skip_url(src.url or "")
                if skip:
                    _, rk_skip = infer_resource_kind_from_url(src.url or "")
                    rk_use = (
                        src.resource_kind
                        if src.resource_kind != "unknown"
                        else rk_skip
                    )
                    wave_sources.append(
                        Source(
                            url=src.url,
                            title=src.title,
                            snippet=src.snippet,
                            fetched=False,
                            source_type=src.source_type,
                            crawl_depth=depth,
                            mime_type=src.mime_type,
                            resource_kind=rk_use,  # type: ignore[arg-type]
                            metadata={
                                **(src.metadata or {}),
                                "skipped": True,
                                "reason": skip_reason,
                            },
                        )
                    )
                    errors.append(f"{src.url}: {skip_reason}")
                    continue

                res, raw_html = await self._fetch_single_with_html(
                    src, j, len(batch), crawl_depth=depth
                )
                visited.add(nu)
                wave_sources.append(res)
                if res.fetched and raw_html:
                    html_by_norm[nu] = raw_html
                if res.fetched:
                    total_pages += 1
                elif not res.content:
                    errors.append(f"{src.url}: failed to fetch")

            all_sources.extend(wave_sources)

            wave_logs.append(
                {
                    "wave_index": wave,
                    "fetched_ok": sum(1 for s in wave_sources if s.fetched),
                    "queued_next": 0,
                }
            )

            if wave >= crawl_max_depth - 1:
                break
            if total_pages >= max_total:
                break

            qtext = self._query_text_for_crawl(user_request, goal)
            q_lower = qtext.lower()
            hints = self._relevance_tokens_from_query(qtext)

            raw_candidates: List[Dict[str, Any]] = []
            seen_cand_norm: set[str] = set()
            for ws in wave_sources:
                if not ws.fetched:
                    continue
                nu = self._normalize_url(ws.url or "")
                html = html_by_norm.get(nu)
                if not html:
                    continue
                for link in self._extract_links_from_html(html, ws.url or ""):
                    lnu = self._normalize_url(link["url"])
                    if lnu in visited or lnu in seen_cand_norm:
                        continue
                    if not self._prefilter_follow_url(
                        link["url"], ws.url or ""
                    ):
                        continue
                    seen_cand_norm.add(lnu)
                    raw_candidates.append(
                        {
                            "url": link["url"],
                            "anchor": link.get("anchor"),
                            "parent_url": ws.url,
                            "resource_kind": link.get("resource_kind", "unknown"),
                        }
                    )

            if not raw_candidates:
                break

            raw_candidates.sort(
                key=lambda c: self._score_link_for_crawl(
                    hints,
                    q_lower,
                    c["url"],
                    c.get("anchor") or "",
                ),
                reverse=True,
            )
            raw_max = ma_int("MULTI_AGENT_RESEARCH_CRAWL_RAW_CANDIDATES_MAX", 200)
            raw_candidates = raw_candidates[:raw_max]

            candidates: List[Dict[str, Any]] = []
            for i, c in enumerate(raw_candidates[:max_llm_candidates], start=1):
                candidates.append({**c, "id": i})

            if not candidates:
                break

            budget = min(per_wave_cap, max_total - total_pages)
            if budget <= 0:
                break

            selected = await self._llm_select_follow_urls(
                user_request=user_request,
                goal=goal,
                candidates=candidates[:max_llm_candidates],
                max_pick=budget,
                context=context,
            )
            wave_logs[-1]["queued_next"] = len(selected)

            pending_norm: set[str] = set()
            for item in selected:
                u = item.get("url")
                if not u or not isinstance(u, str):
                    continue
                nu = self._normalize_url(u)
                if nu in visited or nu in pending_norm:
                    continue
                pending_norm.add(nu)
                _, rk_url = infer_resource_kind_from_url(u)
                rk_item = item.get("resource_kind") or "unknown"
                rk_use = rk_item if rk_item != "unknown" else rk_url
                queue.append(
                    (
                        Source(
                            url=u,
                            title=item.get("anchor") or None,
                            fetched=False,
                            source_type="web",
                            resource_kind=rk_use,  # type: ignore[arg-type]
                        ),
                        wave + 1,
                    )
                )

        ok_count = sum(1 for s in all_sources if s.fetched)
        if ok_count == 0:
            return self._error_payload(
                f"Failed to fetch any pages. Errors: {'; '.join(errors[:3])}",
                suggestions=["Check URL availability", "Verify network connection"],
            )

        filtered, tr_meta = await self._filter_fetched_sources_by_task_relevance(
            user_request, goal, all_sources, context
        )
        if filtered is None:
            return self._error_payload(
                "По оценке модели ни одна из загруженных страниц не признана релевантной задаче.",
                suggestions=[
                    "Уточните формулировку запроса",
                    "Повторите запуск — оркестратор может перепланировать Discovery",
                ],
                metadata=tr_meta,
            )
        all_sources = filtered
        ok_count = sum(1 for s in all_sources if s.fetched)

        summary_parts = [
            f"Волновой обход: загружено {ok_count} страниц, "
            f"волн: {len(wave_logs)}, макс. глубина: {crawl_max_depth}."
        ]
        if errors:
            summary_parts.append(f"Ошибки/пропуски: {len(errors)}.")

        discovered, disc_probe = await self._finalize_discovered_resources(all_sources)
        success_meta: Dict[str, Any] = {
            "pages_fetched": ok_count,
            "pages_failed": len(errors),
            "total_content_chars": sum(
                len(s.content or "") for s in all_sources if s.fetched
            ),
            "crawl_max_depth": crawl_max_depth,
            "crawl_waves": wave_logs,
            "max_total_pages": max_total,
            "discovered_resources_count": len(discovered),
            "discovered_resources_probe": disc_probe,
        }
        success_meta.update(tr_meta)
        return self._success_payload(
            sources=all_sources,
            discovered_resources=discovered,
            narrative=Narrative(text="\n".join(summary_parts), format="markdown"),
            metadata=success_meta,
        )

    @staticmethod
    def _build_discovered_resources_list(sources: List[Source]) -> List[DiscoveredResource]:
        """Единый дедуплицированный каталог URL (страницы + embedded_media) до проверки доступности."""
        max_items = ma_int("MULTI_AGENT_RESEARCH_MAX_DISCOVERED_RESOURCES", 200)
        by_key: Dict[str, DiscoveredResource] = {}

        def upsert(dr: DiscoveredResource) -> None:
            key = ResearchAgent._normalize_url(dr.url)
            if not key:
                return
            prev = by_key.get(key)
            if prev is None:
                by_key[key] = dr
                return
            if dr.origin == "embedded" and prev.origin == "page":
                by_key[key] = dr

        for src in sources:
            u = (src.url or "").strip()
            if not u:
                continue
            if src.fetched:
                upsert(
                    DiscoveredResource(
                        url=u,
                        resource_kind=src.resource_kind,
                        mime_type=src.mime_type,
                        parent_url=None,
                        origin="page",
                        title=src.title,
                        tag=None,
                    )
                )
            meta = src.metadata or {}
            em = meta.get("embedded_media")
            if not isinstance(em, list):
                continue
            for item in em:
                if not isinstance(item, dict):
                    continue
                eu = item.get("url")
                if not eu or not isinstance(eu, str):
                    continue
                eu = eu.strip()
                rk = item.get("resource_kind") or "unknown"
                tag = item.get("tag")
                mt = item.get("mime_type")
                upsert(
                    DiscoveredResource(
                        url=eu,
                        resource_kind=rk,  # type: ignore[arg-type]
                        mime_type=mt if isinstance(mt, str) else None,
                        parent_url=u,
                        origin="embedded",
                        title=None,
                        tag=tag if isinstance(tag, str) else None,
                    )
                )

        out = list(by_key.values())
        out.sort(key=lambda d: (0 if d.origin == "page" else 1, d.url or ""))
        if len(out) > max_items:
            out = out[:max_items]
        return out

    async def _filter_discovered_embedded_reachable(
        self,
        resources: List[DiscoveredResource],
    ) -> tuple[List[DiscoveredResource], Dict[str, Any]]:
        """
        Убирает из каталога embedded-ресурсы с недоступным URL (HEAD / GET Range).
        Страницы (origin=page) уже загружены в этом запуске — не дублируем запросы.
        """
        meta: Dict[str, Any] = {
            "enabled": ma_bool("MULTI_AGENT_RESEARCH_DISCOVERED_RESOURCE_PROBE_ENABLED", True),
        }
        if not meta["enabled"]:
            meta["skipped"] = "probe_disabled"
            return resources, meta

        pages = [r for r in resources if r.origin == "page"]
        embedded = [r for r in resources if r.origin == "embedded"]
        meta["page_entries"] = len(pages)
        meta["embedded_before"] = len(embedded)

        http_embedded = [
            r for r in embedded if (r.url or "").strip().lower().startswith("http")
        ]
        other_embedded = [
            r for r in embedded if not (r.url or "").strip().lower().startswith("http")
        ]
        meta["embedded_non_http_kept"] = len(other_embedded)

        if not http_embedded:
            meta["embedded_checked"] = 0
            meta["embedded_dropped"] = 0
            return pages + other_embedded, meta

        conc = ma_int("MULTI_AGENT_RESEARCH_DISCOVERED_RESOURCE_PROBE_CONCURRENCY", 8)
        conc = max(1, min(conc, 32))
        sem = asyncio.Semaphore(conc)

        async def _one(
            dr: DiscoveredResource,
        ) -> tuple[DiscoveredResource, bool, Optional[int], str]:
            async with sem:
                ok, code, detail = await self._probe_http_url_for_discovered(dr.url or "")
            return dr, ok, code, detail

        results = await asyncio.gather(
            *(_one(r) for r in http_embedded),
            return_exceptions=True,
        )
        kept_http: List[DiscoveredResource] = []
        dropped_detail: List[Dict[str, Any]] = []
        for i, res in enumerate(results):
            if isinstance(res, BaseException):
                dr = http_embedded[i]
                self.logger.info(
                    "Research: discovered probe error for %s: %s",
                    (dr.url or "")[:100],
                    res,
                )
                if len(dropped_detail) < 20:
                    dropped_detail.append(
                        {"url": (dr.url or "")[:180], "detail": type(res).__name__}
                    )
                continue
            dr, ok, code, detail = res
            if ok:
                kept_http.append(dr)
            elif len(dropped_detail) < 20:
                dropped_detail.append(
                    {"url": (dr.url or "")[:180], "status": code, "detail": detail}
                )
        meta["embedded_checked"] = len(http_embedded)
        meta["embedded_dropped"] = len(http_embedded) - len(kept_http)
        meta["embedded_dropped_samples"] = dropped_detail[:12]
        out = pages + other_embedded + kept_http
        out.sort(key=lambda d: (0 if d.origin == "page" else 1, d.url or ""))
        return out, meta

    async def _finalize_discovered_resources(
        self,
        sources: List[Source],
    ) -> tuple[List[DiscoveredResource], Dict[str, Any]]:
        built = self._build_discovered_resources_list(sources)
        filtered, probe_meta = await self._filter_discovered_embedded_reachable(built)
        return filtered, probe_meta

    @staticmethod
    def _same_site_or_subdomain(a: str, b: str) -> bool:
        try:
            ha = (urlparse(a).hostname or "").lower()
            hb = (urlparse(b).hostname or "").lower()
        except ValueError:
            return False
        if not ha or not hb:
            return False
        if ha == hb:
            return True
        return ha.endswith("." + hb) or hb.endswith("." + ha)

    def _prefilter_follow_url(self, target: str, parent: str) -> bool:
        if not target.startswith("http"):
            return False
        if not self._same_site_or_subdomain(target, parent):
            return False
        low = target.lower()
        for junk in _JUNK_PATH_SUBSTRINGS:
            if junk in low:
                return False
        skip, _ = self._should_skip_url(target)
        if skip:
            return False
        return True

    async def _probe_http_url_for_discovered(self, url: str) -> tuple[bool, Optional[int], str]:
        """
        Проверка доступности URL для embedded в discovered_resources.
        HEAD; при 405 — GET с Range (часть серверов не отдаёт HEAD).
        """
        if not ma_bool("MULTI_AGENT_RESEARCH_DISCOVERED_RESOURCE_PROBE_ENABLED", True):
            return True, None, "probe_disabled"
        u = (url or "").strip()
        if not u.startswith("http"):
            return False, None, "invalid_scheme"
        timeout = float(ma_int("MULTI_AGENT_RESEARCH_DISCOVERED_RESOURCE_PROBE_TIMEOUT_SEC", 5))
        timeout = max(2.0, min(timeout, 30.0))
        headers = self._build_firefox_headers()

        async def _range_get() -> tuple[bool, int, str]:
            r = await self.http_client.get(
                u,
                timeout=timeout,
                follow_redirects=True,
                headers={**headers, "Range": "bytes=0-0"},
            )
            code = r.status_code
            if code < 400 or code == 206:
                return True, code, "range_get_ok"
            if code in (401, 403):
                return True, code, "range_get_auth"
            return False, code, "range_get_http_error"

        try:
            r = await self.http_client.head(
                u,
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
            )
            code = r.status_code
            if code < 400:
                return True, code, "head_ok"
            if code in (401, 403):
                return True, code, "head_auth"
            if code == 405:
                ok, c2, reason = await _range_get()
                return ok, c2, reason
            if code >= 400:
                return False, code, "head_http_error"
        except httpx.TimeoutException:
            return False, None, "timeout"
        except httpx.RequestError as e:
            return False, None, f"request_error:{type(e).__name__}"

    @staticmethod
    def _query_text_for_crawl(user_request: str, goal: str) -> str:
        """Текст задачи без форматного хвоста; цель плана добавляем отдельной строкой."""
        u = (user_request or "").strip()
        if u:
            u = _FORMAT_HINT_SPLIT.split(u, maxsplit=1)[0].strip()
        g = (goal or "").strip()
        if u and g:
            return f"{u}\n{g}"
        return u or g

    @staticmethod
    def _relevance_tokens_from_query(text: str) -> set[str]:
        if not text:
            return set()
        low = text.lower()
        return {
            w
            for w in _re.findall(r"[a-zа-яё0-9]{3,}", low)
            if w not in _CRAWL_QUERY_STOPWORDS
        }

    @staticmethod
    def _offtopic_path_penalty(query_lower: str, url_lower: str) -> float:
        """Штраф за нерелевантные рубрики, если запрос про entertainment/людей."""
        if not query_lower or not url_lower:
            return 0.0
        if not any(m in query_lower for m in _ENTERTAINMENT_TOPIC_MARKERS):
            return 0.0
        pen = 0.0
        for frag in _OFFTOPIC_PATH_MARKERS:
            if frag in url_lower:
                pen += 4.0
        return min(pen, 36.0)

    def _score_link_for_crawl(
        self,
        hints: set[str],
        query_lower: str,
        url: str,
        anchor: str,
    ) -> float:
        """Выше = релевантнее задаче (лексика + anchor, штраф за чужие рубрики)."""
        if not url:
            return -1000.0
        u_low = url.lower()
        a_low = (anchor or "").lower()
        score = 0.0
        if hints:
            for h in hints:
                if h in a_low:
                    score += 3.0
                elif h in u_low:
                    score += 2.0
        score -= self._offtopic_path_penalty(query_lower, u_low)
        # Лёгкий бонус за непустой anchor (часто тема ссылки)
        if a_low and len(a_low) > 5:
            score += 0.3
        return score

    @staticmethod
    def _research_task_text_from_context(
        context: Optional[Dict[str, Any]],
    ) -> tuple[str, str]:
        if not context:
            return "", ""
        ur = str(context.get("user_request") or "").strip()
        goal = ""
        pm = context.get("pipeline_memory")
        if isinstance(pm, dict) and pm.get("goal"):
            goal = str(pm["goal"]).strip()
        return ur, goal

    async def _llm_relevance_keep_ids_for_batch(
        self,
        *,
        task_text: str,
        batch: List[Tuple[int, Source]],
        context: Optional[Dict[str, Any]],
    ) -> tuple[set[int], bool, Dict[str, Any]]:
        """
        Один вызов LLM: какие локальные id (0..len(batch)-1) оставить.
        Возвращает (локальные id для оставления, llm_failed, meta_batch).
        """
        excerpt_n = ma_int(
            "MULTI_AGENT_RESEARCH_PAGE_RELEVANCE_LLM_EXCERPT_CHARS",
            _MAX_PAGE_RELEVANCE_LLM_EXCERPT_DEFAULT,
        )
        excerpt_n = max(400, min(excerpt_n, 8000))
        pages: List[Dict[str, Any]] = []
        for j, (_src_i, src) in enumerate(batch):
            pages.append(
                {
                    "id": j,
                    "url": (src.url or "")[:600],
                    "title": (src.title or "")[:400],
                    "snippet": (src.snippet or "")[:500],
                    "text_excerpt": (src.content or "")[:excerpt_n],
                }
            )
        user_block = (
            f"Задача пользователя (и цель плана, если есть):\n{task_text}\n\n"
            f"Страницы (id — только внутри этого списка, с 0 по {len(batch) - 1}):\n"
            + json.dumps(pages, ensure_ascii=False)
        )
        system = (
            "Ты отбираешь веб-страницы для аналитического отчёта. "
            "Оставь только те id, чей заголовок, сниппет и фрагмент текста реально "
            "помогают ответить на задачу (тема, сущности, период). "
            "Отбрасывай обзорные подборки «не в тему», чужие рубрики портала, "
            "страницы без связи с запросом. "
            "Ответь ТОЛЬКО JSON вида "
            '{"keep_ids":[числа,...]} '
            f"где числа — id из списка (0…{len(batch) - 1}). "
            'Если ни одна страница не подходит — {"keep_ids":[]}.'
        )
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_block},
        ]
        bl = len(batch)

        def _parse(raw: str) -> set[int]:
            txt = (raw or "").strip()
            if txt.startswith("```"):
                txt = _re.sub(r"^```[a-zA-Z]*\s*", "", txt)
                txt = _re.sub(r"\s*```$", "", txt).strip()
            data = json.loads(txt)
            if not isinstance(data, dict):
                raise ValueError("expected JSON object")
            ids = data.get("keep_ids")
            if ids is None:
                ids = data.get("relevant_ids")
            if not isinstance(ids, list):
                raise ValueError("keep_ids must be a list")
            out: set[int] = set()
            for x in ids:
                try:
                    xi = int(x)
                except (TypeError, ValueError):
                    continue
                if 0 <= xi < bl:
                    out.add(xi)
            return out

        max_tok = ma_int("MULTI_AGENT_RESEARCH_PAGE_RELEVANCE_LLM_MAX_TOKENS", 1200)
        max_tok = max(256, min(max_tok, 8000))
        temp = ma_float("MULTI_AGENT_RESEARCH_PAGE_RELEVANCE_LLM_TEMPERATURE", 0.12)

        try:
            keep_local = await self._call_llm_with_json_retry(
                messages,
                parse_fn=_parse,
                context=context,
                temperature=temp,
                max_tokens=max_tok,
                max_retries=1,
            )
            return keep_local, False, {"keep_local_count": len(keep_local)}
        except Exception as e:
            self.logger.warning(
                "Research: LLM page relevance batch failed: %s — keeping whole batch",
                e,
            )
            return {j for j in range(bl)}, True, {"error": str(e)[:240]}

    async def _filter_fetched_sources_by_task_relevance(
        self,
        user_request: str,
        goal: str,
        sources: List[Source],
        context: Optional[Dict[str, Any]],
    ) -> tuple[Optional[List[Source]], Dict[str, Any]]:
        """
        LLM отбирает загруженные страницы по смыслу задачи.
        Если все отклонены — None (вызывающий вернёт error для replan).
        """
        meta: Dict[str, Any] = {}
        if not ma_bool("MULTI_AGENT_RESEARCH_TASK_RELEVANCE_FILTER_ENABLED", True):
            meta["task_relevance"] = {"enabled": False}
            return sources, meta

        task_text = (self._query_text_for_crawl(user_request, goal) or "").strip()
        if not task_text:
            meta["task_relevance"] = {"enabled": True, "skipped": "no_task_text"}
            return sources, meta

        fetched_pairs: List[Tuple[int, Source]] = [
            (i, s) for i, s in enumerate(sources) if s.fetched
        ]
        if not fetched_pairs:
            meta["task_relevance"] = {"enabled": True, "skipped": "no_fetched_pages"}
            return sources, meta

        batch_size = ma_int("MULTI_AGENT_RESEARCH_PAGE_RELEVANCE_LLM_BATCH_SIZE", 12)
        batch_size = max(1, min(batch_size, 40))

        keep_source_indices: set[int] = set()
        batch_traces: List[Dict[str, Any]] = []
        any_llm_failed = False

        for b_start in range(0, len(fetched_pairs), batch_size):
            batch = fetched_pairs[b_start : b_start + batch_size]
            keep_local, failed, bmeta = await self._llm_relevance_keep_ids_for_batch(
                task_text=task_text,
                batch=batch,
                context=context,
            )
            if failed:
                any_llm_failed = True
            for lid in keep_local:
                if 0 <= lid < len(batch):
                    src_idx = batch[lid][0]
                    keep_source_indices.add(src_idx)
            batch_traces.append(
                {
                    "start": b_start,
                    "size": len(batch),
                    "kept_in_batch": len(keep_local),
                    **bmeta,
                }
            )

        if not any_llm_failed and not keep_source_indices and fetched_pairs:
            meta["task_relevance"] = {
                "all_rejected": True,
                "llm": True,
                "batches": batch_traces,
            }
            meta["task_relevance"]["urls"] = [
                (sources[i].url or "")[:220] for i, _ in fetched_pairs[:20]
            ]
            return None, meta

        dropped = sum(1 for i, _ in fetched_pairs if i not in keep_source_indices)
        tr: Dict[str, Any] = {
            "llm": True,
            "dropped": dropped,
            "kept": len(keep_source_indices),
            "batches": batch_traces,
        }
        if any_llm_failed:
            tr["llm_batch_failure_fallback"] = True
        if dropped:
            tr["dropped_urls"] = [
                (sources[i].url or "")[:200]
                for i, _ in fetched_pairs
                if i not in keep_source_indices
            ][:16]
        meta["task_relevance"] = tr

        out: List[Source] = []
        for i, s in enumerate(sources):
            if not s.fetched:
                out.append(s)
                continue
            if i in keep_source_indices:
                out.append(s)
            else:
                self.logger.info(
                    "Research: drop LLM low-relevance page: %s",
                    (s.url or "")[:100],
                )
        return out, meta

    @staticmethod
    def _first_url_from_srcset(srcset: str) -> Optional[str]:
        """Первый URL из srcset (часто lazy / responsive)."""
        if not srcset or not isinstance(srcset, str):
            return None
        first = srcset.split(",")[0].strip()
        if not first:
            return None
        token = first.split()[0].strip()
        if token.startswith("data:"):
            return None
        if token.startswith("http") or token.startswith("//"):
            return token
        return None

    def _href_from_media_tag(self, tag: Any, tag_name: str) -> str:
        """src, затем типичные lazy-атрибуты, затем srcset (для img)."""
        try_attrs = (
            "src",
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-lazy",
            "data-url",
            "data-defer-src",
        )
        for a in try_attrs:
            v = (tag.get(a) or "").strip()
            if v and not v.startswith("data:") and not v.startswith("#"):
                return v
        if tag_name == "img":
            ss = (tag.get("srcset") or "").strip()
            u = self._first_url_from_srcset(ss)
            if u:
                return u
        return ""

    def _extract_embedded_media_from_html(
        self, html: str, base_url: str
    ) -> List[Dict[str, Any]]:
        """
        Изображения/медиа с страницы с эвристикой resource_kind для downstream-агентов.
        """
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        max_items = 24
        if BeautifulSoup is None:
            return out
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            self.logger.warning("BeautifulSoup parse (embedded media): %s", e)
            return out

        for tag_name in ("img", "video", "source"):
            for tag in soup.find_all(tag_name):
                href = self._href_from_media_tag(tag, tag_name)
                if not href:
                    continue
                if href.startswith("//"):
                    href = "https:" + href
                try:
                    abs_url = urljoin(base_url, href)
                except ValueError:
                    continue
                if not abs_url.startswith("http"):
                    continue
                nu = self._normalize_url(abs_url)
                if nu in seen:
                    continue
                seen.add(nu)
                _mh, rk_url = infer_resource_kind_from_url(abs_url)
                if tag_name == "img":
                    rk = "image"
                elif tag_name == "video":
                    rk = "video" if rk_url == "unknown" else rk_url
                else:
                    rk = rk_url if rk_url != "unknown" else "video"
                out.append(
                    {
                        "url": abs_url,
                        "resource_kind": rk,
                        "tag": tag_name,
                    }
                )
                if len(out) >= max_items:
                    return out
        return out

    def _extract_links_from_html(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        if BeautifulSoup is not None:
            return self._extract_links_from_html_bs4(html, base_url)
        return self._extract_links_from_html_regex(html, base_url)

    def _extract_links_from_html_bs4(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            self.logger.warning("BeautifulSoup parse failed: %s", e)
            return out

        for tag in soup.find_all("a", href=True):
            href = (tag.get("href") or "").strip()
            if not href or href.startswith("#"):
                continue
            try:
                abs_url = urljoin(base_url, href)
            except ValueError:
                continue
            abs_url = abs_url.split("#")[0]
            if not abs_url.startswith("http"):
                continue
            nu = self._normalize_url(abs_url)
            if nu in seen:
                continue
            seen.add(nu)
            anchor = tag.get_text(" ", strip=True)[:_MAX_ANCHOR_CHARS]
            _mh, rk = infer_resource_kind_from_url(abs_url)
            out.append(
                {
                    "url": abs_url,
                    "anchor": anchor,
                    "resource_kind": rk,
                }
            )
        return out

    def _extract_links_from_html_regex(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """Fallback без bs4: упрощённый разбор <a href>."""
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for m in _re.finditer(
            r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>',
            html,
            _re.IGNORECASE,
        ):
            href = (m.group(1) or "").strip()
            if not href or href.startswith("#"):
                continue
            try:
                abs_url = urljoin(base_url, href)
            except ValueError:
                continue
            abs_url = abs_url.split("#")[0]
            if not abs_url.startswith("http"):
                continue
            nu = self._normalize_url(abs_url)
            if nu in seen:
                continue
            seen.add(nu)
            _mh, rk = infer_resource_kind_from_url(abs_url)
            out.append({"url": abs_url, "anchor": "", "resource_kind": rk})
        return out

    async def _llm_select_follow_urls(
        self,
        *,
        user_request: str,
        goal: str,
        candidates: List[Dict[str, Any]],
        max_pick: int,
        context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """LLM выбирает до max_pick URL по релевантности задаче. Только id из списка."""
        if not candidates or max_pick <= 0:
            return []

        task_text = (
            self._query_text_for_crawl(user_request, goal)
            or "исследование и сбор данных с сайта"
        )
        lines = []
        for c in candidates:
            lines.append(
                json.dumps(
                    {
                        "id": c["id"],
                        "url": c["url"],
                        "anchor": (c.get("anchor") or "")[:120],
                        "parent_url": ((c.get("parent_url") or "")[:160]),
                        "resource_kind": c.get("resource_kind", "unknown"),
                    },
                    ensure_ascii=False,
                )
            )
        user_block = (
            f"Задача пользователя (и цель плана, если есть):\n{task_text}\n\n"
            f"Кандидаты ссылок со страницы-родителя (выбери не более {max_pick}, "
            f"только id из списка):\n"
            + "\n".join(lines)
        )
        system = (
            "Ты отбираешь ссылки для следующего шага веб-исследования. "
            "Предпочитай URL и anchor, которые явно соответствуют теме запроса "
            "(ключевые слова в пути, заголовке ссылки). "
            "Старайся не выбирать разделы портала, очевидно не по теме "
            "(например игры, армия, авто, пароли, политика), если запрос про другое "
            "(люди, кино, фото, шоу-бизнес и т.п.). "
            "Ответь ТОЛЬКО JSON вида "
            '{"selected_ids":[числа,...]} '
            f"где числа — id из списка, не больше {max_pick} элементов. "
            "Не добавляй URL вне списка. Если ни одна ссылка не подходит — {\"selected_ids\":[]}."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_block},
        ]

        def _parse(raw: str) -> List[int]:
            txt = (raw or "").strip()
            if txt.startswith("```"):
                txt = _re.sub(r"^```[a-zA-Z]*\s*", "", txt)
                txt = _re.sub(r"\s*```$", "", txt).strip()
            data = json.loads(txt)
            if not isinstance(data, dict):
                raise ValueError("expected JSON object")
            ids = data.get("selected_ids")
            if ids is None:
                ids = data.get("ids")
            if not isinstance(ids, list):
                raise ValueError("selected_ids must be a list")
            out_ids: List[int] = []
            for x in ids:
                try:
                    out_ids.append(int(x))
                except (TypeError, ValueError):
                    continue
            return out_ids

        valid_ids = {int(c["id"]) for c in candidates}

        try:
            ids = await self._call_llm_with_json_retry(
                messages,
                parse_fn=_parse,
                context=context,
                temperature=0.2,
                max_tokens=800,
                max_retries=1,
            )
        except Exception as e:
            self.logger.warning("LLM follow-url selection failed: %s — using fallback", e)
            ids = []

        id_to_cand = {int(c["id"]): c for c in candidates}
        picked: List[Dict[str, Any]] = []
        for i in ids:
            if i not in valid_ids:
                continue
            c = id_to_cand[i]
            picked.append(
                {
                    "url": c["url"],
                    "anchor": c.get("anchor"),
                    "resource_kind": c.get("resource_kind", "unknown"),
                }
            )
            if len(picked) >= max_pick:
                break

        if not picked:
            for c in candidates:
                picked.append(
                    {
                        "url": c["url"],
                        "anchor": c.get("anchor"),
                        "resource_kind": c.get("resource_kind", "unknown"),
                    }
                )
                if len(picked) >= max_pick:
                    break

        return picked

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

        already_fetched, already_failed = self._collect_research_url_history(agent_results)

        seen_in_batch: set[str] = set()
        for result in agent_results:
            if not isinstance(result, dict):
                continue

            # V2 формат: AgentPayload.sources[]
            sources_raw = result.get("sources", [])
            if isinstance(sources_raw, list):
                for s in sources_raw:
                    if isinstance(s, dict):
                        if not s.get("fetched", False) and s.get("url"):
                            nu = self._normalize_url(s["url"])
                            if nu in already_fetched or nu in already_failed or nu in seen_in_batch:
                                continue
                            seen_in_batch.add(nu)
                            _, rk_inf = infer_resource_kind_from_url(s["url"])
                            rk = s.get("resource_kind") or rk_inf
                            unfetched.append(Source(
                                url=s["url"],
                                title=s.get("title"),
                                snippet=s.get("snippet"),
                                fetched=False,
                                source_type=s.get("source_type", "web"),  # type: ignore[arg-type]
                                mime_type=s.get("mime_type"),
                                resource_kind=rk,  # type: ignore[arg-type]
                                metadata=s.get("metadata"),
                            ))
                    elif isinstance(s, str) and s.startswith("http"):
                        nu = self._normalize_url(s)
                        if nu in already_fetched or nu in already_failed or nu in seen_in_batch:
                            continue
                        seen_in_batch.add(nu)
                        _, rk_inf = infer_resource_kind_from_url(s)
                        unfetched.append(
                            Source(
                                url=s,
                                fetched=False,
                                resource_kind=rk_inf,  # type: ignore[arg-type]
                            )
                        )

            # V1 fallback: results[] с url
            results_raw = result.get("results", [])
            if isinstance(results_raw, list) and not sources_raw:
                for r in results_raw:
                    if isinstance(r, dict) and r.get("url"):
                        nu = self._normalize_url(r["url"])
                        if nu in already_fetched or nu in already_failed or nu in seen_in_batch:
                            continue
                        seen_in_batch.add(nu)
                        _, rk_inf = infer_resource_kind_from_url(r["url"])
                        rk = r.get("resource_kind") or rk_inf
                        unfetched.append(Source(
                            url=r["url"],
                            title=r.get("title"),
                            snippet=r.get("snippet"),
                            fetched=False,
                            mime_type=r.get("mime_type"),
                            resource_kind=rk,  # type: ignore[arg-type]
                            metadata=r.get("metadata"),
                        ))

        self.logger.info(
            f"📦 Collected {len(unfetched)} unfetched sources from agent_results"
        )
        return unfetched

    @staticmethod
    def _normalize_url(url: str) -> str:
        return (url or "").split("#")[0].rstrip("/").lower()

    def _collect_research_url_history(
        self, agent_results: List[Dict[str, Any]]
    ) -> tuple[set[str], set[str]]:
        """
        Собирает URL-историю из уже выполненных шагов research:
        - already_fetched: успешно загруженные URL
        - already_failed: URL с неуспешной загрузкой (fetched=False)
        """
        already_fetched: set[str] = set()
        already_failed: set[str] = set()

        for result in agent_results:
            if not isinstance(result, dict):
                continue
            if result.get("agent") != "research":
                continue
            # Учитываем также error-результаты research: они содержат sources c fetched=False
            # и должны блокировать бессмысленные повторные попытки в рамках сессии.
            if result.get("status") not in ("success", "error", None):
                continue

            for s in result.get("sources") or []:
                if not isinstance(s, dict) or not s.get("url"):
                    continue
                nu = self._normalize_url(s["url"])
                if s.get("fetched"):
                    already_fetched.add(nu)
                    already_failed.discard(nu)
                else:
                    already_failed.add(nu)

        return already_fetched, already_failed

    # ------------------------------------------------------------------
    # Single URL fetch
    # ------------------------------------------------------------------

    async def _fetch_single(
        self,
        src: Source,
        idx: int,
        total: int,
        crawl_depth: int = 0,
    ) -> Source:
        """Загружает одну страницу и возвращает обновлённый Source."""
        out, _ = await self._fetch_single_with_html(src, idx, total, crawl_depth=crawl_depth)
        return out

    async def _fetch_single_with_html(
        self,
        src: Source,
        idx: int,
        total: int,
        crawl_depth: int = 0,
    ) -> Tuple[Source, Optional[str]]:
        """Загружает страницу; для HTML возвращает raw HTML для извлечения ссылок."""
        url = src.url
        try:
            self.logger.info(f"   [{idx}/{total}] Fetching: {url}")

            response = await self.http_client.get(
                url,
                timeout=15.0,
                follow_redirects=True,
                headers=self._build_firefox_headers(),
            )
            response.raise_for_status()

            content_type_hdr = response.headers.get("content-type", "")
            mime_norm, kind = classify_resource_from_http(content_type_hdr, url)
            raw_html: Optional[str] = None
            meta: Dict[str, Any] = {}
            title = src.title
            content: Optional[str] = None

            if kind == "html_page":
                raw_html = response.text
                text = self._extract_text_from_html(response.text)
                content = text[:5000]
                title = self._extract_title_from_html(response.text) or src.title
                embedded = self._extract_embedded_media_from_html(response.text, url)
                if embedded:
                    meta["embedded_media"] = embedded
            elif kind == "image" and (
                "svg" in mime_norm
                or (mime_norm.startswith("image/") and "svg" in mime_norm)
            ):
                # SVG как текст — пригодно для structurizer
                content = response.text[:5000]
                meta["vector_image"] = True
            elif kind in ("image", "video", "audio"):
                size = len(response.content)
                content = (
                    f"[Бинарный ресурс ({kind}), {size} байт. "
                    f"Прямой URL для ссылки/предпросмотра: {url}]"
                )
                meta["binary_body"] = True
            elif kind == "pdf":
                content = (
                    f"[PDF-документ, {len(response.content)} байт. URL: {url}]"
                )
                meta["binary_body"] = True
            elif kind in ("json", "xml", "text", "feed"):
                content = response.text[:5000]
            else:
                # document / other — пробуем как текст с ограничением
                try:
                    content = response.text[:5000]
                except Exception:
                    content = (
                        f"[Ресурс ({kind}), {len(response.content)} байт. URL: {url}]"
                    )
                    meta["decode_as_text_failed"] = True

            final_md: Dict[str, Any] = {**(src.metadata or {}), **meta}
            final_md_opt: Optional[Dict[str, Any]] = final_md if final_md else None
            mime_use = mime_norm or src.mime_type
            rk_use = kind

            self.logger.info(
                f"   ✅ OK: kind={rk_use} mime={mime_use or '?'} "
                f"content={len(content or '')} chars"
            )

            return (
                Source(
                    url=url,
                    title=title or src.title,
                    snippet=src.snippet,
                    content=content,
                    source_type=src.source_type,
                    mime_type=mime_use,
                    resource_kind=rk_use,  # type: ignore[arg-type]
                    metadata=final_md_opt,
                    status_code=response.status_code,
                    fetched=True,
                    content_size=len(response.content),
                    crawl_depth=crawl_depth,
                ),
                raw_html,
            )

        except httpx.TimeoutException:
            self.logger.warning(f"   ⏱️ Timeout: {url}")
            _, _k = infer_resource_kind_from_url(url)
            return (
                Source(
                    url=url,
                    title=src.title,
                    snippet=src.snippet,
                    fetched=False,
                    source_type=src.source_type,
                    mime_type=src.mime_type,
                    resource_kind=src.resource_kind
                    if src.resource_kind != "unknown"
                    else _k,  # type: ignore[arg-type]
                    metadata={**(src.metadata or {}), "error": "timeout"},
                    crawl_depth=crawl_depth,
                ),
                None,
            )
        except httpx.HTTPStatusError as e:
            self.logger.warning(f"   ❌ HTTP {e.response.status_code}: {url}")
            _, _k = infer_resource_kind_from_url(url)
            return (
                Source(
                    url=url,
                    title=src.title,
                    snippet=src.snippet,
                    fetched=False,
                    source_type=src.source_type,
                    mime_type=src.mime_type,
                    resource_kind=src.resource_kind
                    if src.resource_kind != "unknown"
                    else _k,  # type: ignore[arg-type]
                    metadata={**(src.metadata or {}), "error": "http_error"},
                    status_code=e.response.status_code,
                    crawl_depth=crawl_depth,
                ),
                None,
            )
        except Exception as e:
            self.logger.warning(f"   ❌ {type(e).__name__}: {url}")
            _, _k = infer_resource_kind_from_url(url)
            return (
                Source(
                    url=url,
                    title=src.title,
                    snippet=src.snippet,
                    fetched=False,
                    source_type=src.source_type,
                    mime_type=src.mime_type,
                    resource_kind=src.resource_kind
                    if src.resource_kind != "unknown"
                    else _k,  # type: ignore[arg-type]
                    metadata={**(src.metadata or {}), "error": type(e).__name__},
                    crawl_depth=crawl_depth,
                ),
                None,
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
