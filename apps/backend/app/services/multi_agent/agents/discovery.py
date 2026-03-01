"""
DiscoveryAgent — поиск информации в интернете и публичных датасетах.

V2 агент, рефакторинг из SearchAgent.
Возвращает AgentPayload(sources=[Source(fetched=False)], narrative=...).
См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

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
    ):
        super().__init__(
            agent_name="discovery",
            message_bus=message_bus,
            system_prompt=system_prompt,
        )
        self.gigachat = gigachat_service
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

            # Выполняем поиск
            if search_type == "news":
                raw_results = self._search_news(query, max_results, region)
            else:
                raw_results = self._search_web(query, max_results, region)

            if not raw_results:
                return self._error_payload(
                    f"No results found for query: {query}",
                    suggestions=["Try a different query", "Broaden search terms"],
                )

            # Конвертируем в Source модели (fetched=False)
            sources = self._results_to_sources(raw_results, search_type)

            # Суммаризация через GigaChat
            summary = await self._summarize_results(query, raw_results)

            self.logger.info(f"✅ Found {len(sources)} results for '{query[:60]}'")

            return self._success_payload(
                sources=sources,
                narrative=Narrative(text=summary, format="markdown"),
                metadata={
                    "query": query,
                    "search_type": search_type,
                    "result_count": len(sources),
                },
            )

        except Exception as e:
            self.logger.error(f"Error in discovery: {e}", exc_info=True)
            return self._error_payload(str(e))

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
        self, query: str, results: List[Dict[str, Any]]
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

            resp: Any = await self.gigachat.chat_completion(
                messages=messages, temperature=0.3, max_tokens=300
            )

            if isinstance(resp, dict):
                if "choices" in resp:
                    return resp["choices"][0]["message"]["content"].strip()
                if "content" in resp:
                    return resp["content"].strip()
            return str(resp).strip()

        except Exception as e:
            self.logger.error(f"Summarization failed: {e}")
            return results[0].get("snippet", "") if results else ""
