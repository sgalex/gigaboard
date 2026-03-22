"""
DiscoveryAgent — поиск информации в интернете и публичных датасетах.

V2 агент, рефакторинг из SearchAgent.
Возвращает AgentPayload(sources=[Source(fetched=False)], narrative=...).
См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlparse

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import Source, Narrative
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


DISCOVERY_SYSTEM_PROMPT = '''
Вы — DiscoveryAgent (Агент-Исследователь) в системе GigaBoard Multi-Agent V2.

**ОСНОВНАЯ РОЛЬ**: Поиск информации в интернете через DuckDuckGo для ответа на вопросы пользователя.

**ВОЗМОЖНОСТИ**:
1. Веб-поиск через DuckDuckGo (текстовые результаты)
2. Поиск новостей
3. Поиск публичных датасетов (Kaggle, data.gov и др.)
4. Извлечение релевантных фактов и данных
5. Суммаризация найденной информации
6. Предоставление источников

**ТИПЫ ПОИСКА**:
- **web**: Общий веб-поиск (дефолт)
- **news**: Поиск новостей
- **quick**: Быстрый ответ (instant answers)

**ВЫХОДНЫЕ ДАННЫЕ**:
- sources: список Source(url, title, snippet, fetched=False)
- narrative: краткое резюме найденного

**ВАЖНО**:
- Поиск только находит и ранжирует результаты
- НЕ загружает полный контент — это задача ResearchAgent
- Предоставляй только факты из результатов
- Указывай источники информации

Be factual, cite sources, and always provide fresh information.
'''


class DiscoveryAgent(BaseAgent):
    """
    DiscoveryAgent — поиск информации в интернете через DuckDuckGo.

    V2 рефакторинг из SearchAgent.
    Возвращает AgentPayload(sources=[Source(fetched=False)], narrative=...).
    """

    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None,
        llm_router: Optional[Any] = None,
    ):
        super().__init__(
            agent_name="discovery",
            message_bus=message_bus,
            system_prompt=system_prompt,
        )
        self.gigachat = gigachat_service
        self.llm_router = llm_router
        self._ddg_client = None

    def _get_default_system_prompt(self) -> str:
        return DISCOVERY_SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # DuckDuckGo client
    # ------------------------------------------------------------------

    def _get_ddg_client(self):
        """Ленивая инициализация DuckDuckGo клиента."""
        if self._ddg_client is None:
            try:
                try:
                    from ddgs import DDGS
                    self._ddg_client = DDGS(timeout=20, verify=True)
                    self.logger.info("✅ DuckDuckGo client initialized (ddgs 9.x)")
                except ImportError:
                    from duckduckgo_search import DDGS
                    self._ddg_client = DDGS()
                    self.logger.warning(
                        "⚠️ Using deprecated duckduckgo_search. Install ddgs."
                    )
            except ImportError:
                self.logger.error("❌ ddgs not installed. pip install ddgs")
                raise ImportError("ddgs package required. pip install ddgs")
        return self._ddg_client

    # ------------------------------------------------------------------
    # process_task — единая точка входа (V2)
    # ------------------------------------------------------------------

    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Обрабатывает задачу поиска. Возвращает AgentPayload.

        Агент самостоятельно определяет тип поиска на основе:
        - task.description / task.query
        - task.search_type (web | news | quick)
        """
        try:
            description = task.get("description", "")
            query = task.get("query", "") or description
            if not query:
                return self._error_payload(
                    "Search query is required (provide 'query' or 'description')"
                )

            # Определяем тип поиска
            search_type = task.get("search_type", "web")
            if search_type == "web":
                desc_lower = description.lower()
                if any(kw in desc_lower for kw in ["news", "новости", "latest", "recent"]):
                    search_type = "news"
                elif any(kw in desc_lower for kw in ["instant", "quick", "что такое", "define"]):
                    search_type = "quick"

            self.logger.info(f"🔍 Processing {search_type} search: {query[:100]}...")

            max_results = task.get("max_results", 5)
            region = task.get("region", "ru-ru")
            multi_query = task.get("multi_query", True)
            max_queries = min(int(task.get("max_search_queries", 4) or 4), 6)
            per_query_fetch = min(int(task.get("per_query_results", 8) or 8), 15)

            # Запрашиваем больше результатов, чтобы после фильтрации осталось достаточно
            fetch_count = max(max_results + 5, 10) if search_type == "web" else max_results

            queries_used: List[str] = [query]

            # Выполняем поиск (при пустом news — fallback на web)
            if search_type == "news":
                raw_results = self._search_news(query, max_results, region)
                if not raw_results:
                    self.logger.warning(
                        "DuckDuckGo news returned no results, falling back to web search"
                    )
                    raw_results = self._search_web(query, fetch_count, region)
                    if raw_results:
                        search_type = "web"  # метка: фактически использован web
            elif (
                multi_query
                and self._should_use_multi_query_web(query, description)
                and max_queries >= 2
            ):
                heuristic = self._expand_queries_for_discovery(
                    query, description, max_variants=max_queries
                )
                llm_extra: List[str] = []
                if task.get("llm_query_expansion", True):
                    try:
                        llm_extra = await self._llm_suggest_search_queries(
                            query, description, context, max_suggestions=4
                        )
                    except Exception as e:
                        self.logger.warning("LLM query expansion skipped: %s", e)
                variants = self._merge_query_variants(
                    heuristic, llm_extra, max_queries
                )
                raw_results = self._search_web_multi(
                    variants, per_query_fetch, region
                )
                raw_results = self._prioritize_results_by_url(raw_results)
                queries_used = variants
                self.logger.info(
                    "🔍 Multi-query DDG: %s вариантов → %s URL (после приоритизации доменов)",
                    len(variants),
                    len(raw_results),
                )
            else:
                raw_results = self._search_web(query, fetch_count, region)

            # Убираем заведомо нерелевантные URL; при multi-query сначала держим шире пул, потом top-N
            filter_cap = (
                min(len(raw_results), max(max_results * 5, 24))
                if len(queries_used) > 1
                else max_results
            )
            raw_results = self._filter_off_topic_results(query, raw_results, filter_cap)
            raw_results = self._filter_low_value_help_domains(query, raw_results, max_results)
            if len(queries_used) > 1:
                raw_results = raw_results[:max_results]

            if not raw_results:
                return self._error_payload(
                    f"No results found for query: {query}",
                    suggestions=["Try a different query", "Broaden search terms"],
                )

            # Конвертируем в Source модели (fetched=False)
            sources = self._results_to_sources(raw_results, search_type)

            # Суммаризация через LLM (роутер или GigaChat)
            summary = await self._summarize_results(query, raw_results, context)

            self.logger.info(f"✅ Found {len(sources)} results for '{query[:60]}'")

            meta: Dict[str, Any] = {
                "query": query,
                "search_type": search_type,
                "result_count": len(sources),
            }
            if len(queries_used) > 1:
                meta["search_queries_used"] = queries_used

            return self._success_payload(
                sources=sources,
                narrative=Narrative(text=summary, format="markdown"),
                metadata=meta,
            )

        except Exception as e:
            self.logger.error(f"Error in discovery: {e}", exc_info=True)
            return self._error_payload(str(e))

    # ------------------------------------------------------------------
    # Несколько вариантов запроса к DDG → объединение по URL
    # ------------------------------------------------------------------

    _MULTI_QUERY_KEYWORDS = (
        "найди",
        "find ",
        "search",
        "топ",
        "top ",
        "рейтинг",
        "продаж",
        "sales",
        "статистик",
        "данные",
        "compare",
        "список",
        "сколько",
        "where",
        "how many",
        "research",
        "источник",
        "рынок",
        "market",
    )

    def _should_use_multi_query_web(self, query: str, description: str) -> bool:
        """Имеет смысл только для «исследовательских» запросов, не для «привет»."""
        q = f"{query} {description}".strip()
        if len(q) < 28:
            return False
        low = q.lower()
        return any(k in low for k in self._MULTI_QUERY_KEYWORDS)

    def _expand_queries_for_discovery(
        self, query: str, description: str, max_variants: int
    ) -> List[str]:
        """
        Строит до max_variants разных строк для DuckDuckGo (эвристики, без LLM).
        Цель — разнообразить выдачу: RU/EN, отраслевые источники, укороченный запрос.
        """
        seen: set[str] = set()
        out: List[str] = []

        def add(text: str) -> None:
            t = (text or "").strip()
            if len(t) < 4:
                return
            key = t.lower()
            if key in seen:
                return
            seen.add(key)
            out.append(t)

        add(query)
        desc = (description or "").strip()
        if desc and desc.lower() != query.lower() and len(desc) < 220:
            add(desc[:140])

        combined = f"{query} {desc}".lower()
        words = query.split()
        if len(words) > 8:
            add(" ".join(words[:8]))

        ru_ctx = any(
            x in combined
            for x in (
                "russia",
                "росси",
                "россии",
                "россий",
                "рф",
                "rf ",
            )
        )
        if ru_ctx and any(
            x in combined
            for x in (
                "electric",
                "электро",
                " ev ",
                "ev ",
                "car",
                "авто",
                "модел",
                "vehicle",
            )
        ):
            add("Автостат электромобили продажи Россия")
            add("продажи электромобилей Россия рейтинг моделей")

        if "2025" in query or "2025" in desc:
            add(query.replace("2025", "2024"))
            if desc:
                add(desc.replace("2025", "2024")[:140])

        if ru_ctx and not any(ord(c) > 127 for c in query):
            add(f"{query} site:ru OR россия")

        return out[:max_variants]

    def _search_web_multi(
        self,
        queries: List[str],
        per_query: int,
        region: str,
    ) -> List[Dict[str, Any]]:
        """
        Несколько вызовов ddg.text; URL дедуплицируются, порядок — round-robin по
        запросам, чтобы в начале списка были ссылки из разных формулировок.
        """
        ddg = self._get_ddg_client()
        buckets: List[List[Dict[str, Any]]] = []
        for q in queries:
            bucket: List[Dict[str, Any]] = []
            try:
                for r in ddg.text(q, region=region, max_results=per_query):
                    url = (r.get("href") or "").strip()
                    if not url:
                        continue
                    bucket.append({
                        "title": r.get("title", ""),
                        "url": url,
                        "snippet": r.get("body", ""),
                    })
            except Exception as e:
                self.logger.warning("DuckDuckGo web search failed for %r: %s", q[:80], e)
            buckets.append(bucket)

        seen_url: set[str] = set()
        merged: List[Dict[str, Any]] = []
        max_len = max((len(b) for b in buckets), default=0)
        for i in range(max_len):
            for b in buckets:
                if i >= len(b):
                    continue
                url = b[i]["url"]
                if url in seen_url:
                    continue
                seen_url.add(url)
                merged.append(b[i])
        return merged

    def _merge_query_variants(
        self, heuristic: List[str], llm_extra: List[str], max_queries: int
    ) -> List[str]:
        """Эвристики первыми, затем варианты от LLM; дедуп, лимит."""
        seen: set[str] = set()
        out: List[str] = []
        for q in heuristic + llm_extra:
            k = q.strip().lower()
            if len(k) < 4 or k in seen:
                continue
            seen.add(k)
            out.append(q.strip())
            if len(out) >= max_queries:
                break
        return out if out else heuristic[:1]

    async def _llm_suggest_search_queries(
        self,
        query: str,
        description: str,
        context: Optional[Dict[str, Any]],
        max_suggestions: int,
    ) -> List[str]:
        """
        Короткий вызов LLM: альтернативные строки для DuckDuckGo (другой язык, синонимы, отраслевые источники).
        """
        user = (
            f"Основной поисковый запрос:\n{query[:600]}\n\n"
            f"Описание задачи:\n{(description or '')[:500]}\n\n"
            f"Верни ТОЛЬКО JSON-массив из 1–{max_suggestions} коротких запросов для веб-поиска "
            "(разные формулировки: RU/EN, регион, год, названия аналитиков вроде Автостат). "
            "Без markdown, только массив строк."
        )
        messages = [
            {
                "role": "system",
                "content": "Ты помощник поиска. Отвечай только валидным JSON-массивом строк.",
            },
            {"role": "user", "content": user},
        ]
        raw = await self._call_llm(
            messages, context=context, temperature=0.25, max_tokens=280
        )
        text = raw if isinstance(raw, str) else str(raw)
        m = re.search(r"\[[\s\S]*\]", text)
        if not m:
            return []
        try:
            arr = json.loads(m.group())
        except json.JSONDecodeError:
            return []
        if not isinstance(arr, list):
            return []
        out: List[str] = []
        for x in arr:
            if isinstance(x, str) and len(x.strip()) > 3:
                out.append(x.strip())
            if len(out) >= max_suggestions:
                break
        return out

    def _url_priority_score(self, url: str) -> int:
        """Эвристический приоритет домена для региональных/данных запросов."""
        u = (url or "").lower()
        score = 0
        if "autostat.ru" in u:
            score += 100
        elif any(
            d in u
            for d in (
                "rbc.ru",
                "vedomosti.ru",
                "kommersant.ru",
                "tass.com",
                "interfax.ru",
                "ria.ru",
                "lenta.ru",
            )
        ):
            score += 38
        try:
            host = urlparse(u).netloc.lower()
            if host.endswith(".ru") or host.endswith(".рф"):
                score += 20
        except Exception:
            pass
        if "wikipedia.org" in u:
            score += 12
        if "gov.ru" in u or "minpromtorg" in u or "rosstat" in u:
            score += 28
        if "statista.com" in u:
            score -= 28
        if "ceoworld.biz" in u or "buzzfeed" in u:
            score -= 10
        if any(
            x in u
            for x in (
                "pinterest.",
                "facebook.com",
                "instagram.com",
                "tiktok.com",
            )
        ):
            score -= 40
        return score

    def _prioritize_results_by_url(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Стабильная сортировка: выше score домена, внутри — исходный порядок round-robin."""
        scored = [
            (i, self._url_priority_score(r.get("url", "")), r)
            for i, r in enumerate(results)
        ]
        scored.sort(key=lambda t: (-t[1], t[0]))
        return [t[2] for t in scored]

    # ------------------------------------------------------------------
    # Off-topic filter (поиск вернул кино/сериалы при запросе про авто и т.д.)
    # ------------------------------------------------------------------

    # Домены/пути, не релевантные для запросов про автомобили/продажи/данные
    _ENTERTAINMENT_URL_PATTERNS = (
        "kinopoisk", "imdb.com", "/film", "/movie", "/series", "/serial",
        "сериал", "фильм", "кино", "топ-250", "top-250", "top10-hd",
    )

    def _filter_off_topic_results(
        self, query: str, raw_results: List[Dict[str, Any]], max_keep: int
    ) -> List[Dict[str, Any]]:
        """
        Отфильтровывает URL, заведомо нерелевантные запросу (например кино при запросе про авто).
        """
        q_lower = query.lower()
        # Признаки запроса про автомобили/данные/продажи
        is_auto_or_data = any(
            kw in q_lower
            for kw in [
                "электромобил", "авто", "автомобил", "марок", "бренд", "машины",
                "продаж", "sales", "car", "ev ", "electric car", "топ-20", "топ 20",
                "рейтинг", "статистик", "данные",
            ]
        )
        if not is_auto_or_data:
            return raw_results[:max_keep]

        filtered = []
        for r in raw_results:
            url = (r.get("url") or "").lower()
            title = (r.get("title") or "").lower()
            if any(p in url or p in title for p in self._ENTERTAINMENT_URL_PATTERNS):
                self.logger.debug("Filtered off-topic URL: %s", r.get("url", "")[:80])
                continue
            filtered.append(r)
            if len(filtered) >= max_keep:
                break
        if len(filtered) < len(raw_results):
            self.logger.info(
                "Filtered %s off-topic results, kept %s",
                len(raw_results) - len(filtered),
                len(filtered),
            )
        # Если всё отфильтровалось — возвращаем исходный список, чтобы пайплайн не падал
        return filtered[:max_keep] if filtered else raw_results[:max_keep]

    # Домены справок/маркетплейсов, часто всплывающие при «широких» запросах и бесполезные для research
    _LOW_VALUE_DOMAIN_FRAGMENTS = (
        "support.google.com",
        "support.google.ru",
        "play.google.com",
        "maps.google.com",
        "accounts.google.com",
    )

    def _looks_like_finance_or_commodity_query(self, query: str) -> bool:
        q = (query or "").lower()
        return any(
            kw in q
            for kw in (
                "нефт",
                "oil",
                "brent",
                "wti",
                "crude",
                "commodit",
                "сырь",
                "финанс",
                "finance",
                "бирж",
                "stock",
                "акци",
                "курс",
                "цен",
                "тренд",
                "invest",
                "инвест",
                "котиров",
                "форекс",
                "forex",
            )
        )

    def _filter_low_value_help_domains(
        self,
        query: str,
        raw_results: List[Dict[str, Any]],
        max_keep: int,
    ) -> List[Dict[str, Any]]:
        """
        Убирает очевидно нерелевантные URL (справки Google Play/Карт и т.п.) для финансовых/товарных запросов.
        Если после фильтра список пуст — возвращаем исходный (как в off-topic фильтре).
        """
        if not raw_results or not self._looks_like_finance_or_commodity_query(query):
            return raw_results[:max_keep]

        filtered: List[Dict[str, Any]] = []
        for r in raw_results:
            url = (r.get("url") or "").lower()
            if any(dom in url for dom in self._LOW_VALUE_DOMAIN_FRAGMENTS):
                self.logger.debug("Filtered low-value help URL: %s", r.get("url", "")[:90])
                continue
            filtered.append(r)
            if len(filtered) >= max_keep:
                break

        if len(filtered) < len(raw_results):
            self.logger.info(
                "Discovery: removed %s low-value portal URLs (finance/commodity query)",
                len(raw_results) - len(filtered),
            )
        return filtered[:max_keep] if filtered else raw_results[:max_keep]

    # ------------------------------------------------------------------
    # Search implementations
    # ------------------------------------------------------------------

    def _search_web(
        self, query: str, max_results: int, region: str
    ) -> List[Dict[str, Any]]:
        """Выполняет веб-поиск через DuckDuckGo."""
        ddg = self._get_ddg_client()
        results = []
        try:
            for r in ddg.text(query, region=region, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        except Exception as e:
            self.logger.error(f"DuckDuckGo web search failed: {e}")
        return results

    def _search_news(
        self, query: str, max_results: int, region: str
    ) -> List[Dict[str, Any]]:
        """Выполняет поиск новостей через DuckDuckGo."""
        ddg = self._get_ddg_client()
        results = []
        try:
            for r in ddg.news(query, region=region, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("body", ""),
                    "date": r.get("date", ""),
                    "source_name": r.get("source", ""),
                })
        except Exception as e:
            self.logger.error(f"DuckDuckGo news search failed: {e}")
        return results

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _results_to_sources(
        self, raw_results: List[Dict[str, Any]], search_type: str
    ) -> List[Source]:
        """Конвертирует raw dict результаты в список Source (fetched=False)."""
        source_type_map = {"web": "web", "news": "news", "quick": "web"}
        src_type = source_type_map.get(search_type, "web")  # type: ignore[arg-type]

        sources: List[Source] = []
        for r in raw_results:
            source = Source(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("snippet", ""),
                fetched=False,
                content=None,
                source_type=src_type,  # type: ignore[arg-type]
            )
            sources.append(source)
        return sources

    # ------------------------------------------------------------------
    # Summarization
    # ------------------------------------------------------------------

    async def _summarize_results(
        self, query: str, results: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Суммаризирует результаты поиска с помощью GigaChat."""
        try:
            parts = []
            for i, r in enumerate(results[:5], 1):
                parts.append(
                    f"{i}. {r['title']}\n{r['snippet']}\nИсточник: {r['url']}"
                )
            context_text = "\n\n".join(parts)

            prompt = (
                f'На основе результатов поиска, дай краткое резюме '
                f'(2-3 предложения) по запросу: "{query}"\n\n'
                f"РЕЗУЛЬТАТЫ ПОИСКА:\n{context_text}\n\n"
                "Ответ: кратко, фактически, на русском языке."
            )

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]

            resp = await self._call_llm(
                messages, context=context, temperature=0.3, max_tokens=300
            )
            # _call_llm всегда возвращает str
            return str(resp).strip()

        except Exception as e:
            self.logger.error(f"Summarization failed: {e}")
            return results[0].get("snippet", "") if results else ""
