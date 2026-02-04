"""
Search Agent - Web Search with DuckDuckGo
Выполняет поиск информации в интернете через DuckDuckGo.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для Search Agent
SEARCH_SYSTEM_PROMPT = '''
Вы — Search Agent (Агент-Поисковик) в системе GigaBoard Multi-Agent.

**ОСНОВНАЯ РОЛЬ**: Поиск информации в интернете через DuckDuckGo для ответа на вопросы пользователя.

**ВОЗМОЖНОСТИ**:
1. Веб-поиск через DuckDuckGo (текстовые результаты)
2. Поиск новостей
3. Извлечение релевантных фактов и данных
4. Суммаризация найденной информации
5. Предоставление источников

**ТИПЫ ПОИСКА**:
- **web**: Общий веб-поиск (дефолт)
- **news**: Поиск новостей
- **quick**: Быстрый ответ (instant answers)

**ПРОЦЕСС РАБОТЫ**:
1. Получить поисковый запрос
2. Выполнить поиск через DuckDuckGo
3. Проанализировать результаты
4. Извлечь релевантную информацию
5. Структурировать данные для пользователя

**ФОРМАТ ВЫВОДА**:
```json
{
  "query": "original search query",
  "results": [
    {
      "title": "Article Title",
      "url": "https://example.com/article",
      "snippet": "Short description...",
      "relevance": "high|medium|low"
    }
  ],
  "summary": "Краткое резюме найденной информации",
  "sources": ["https://source1.com", "https://source2.com"],
  "timestamp": "2026-01-28T10:00:00Z"
}
```

**BEST PRACTICES**:
- Всегда указывать источники информации
- Фильтровать нерелевантные результаты
- Предоставлять краткое резюме вместе с деталями
- Ограничивать количество результатов (макс. 5-10)
- Проверять свежесть информации для новостей

**ОГРАНИЧЕНИЯ**:
- Не делать предположений — только факты из результатов
- Не комбинировать информацию из разных источников без явного указания
- Всегда предупреждать если информация устарела
- Соблюдать rate limits DuckDuckGo

**БЕЗОПАСНОСТЬ**:
- Никогда не показывать рекламные результаты
- Фильтровать вредоносный контент
- Проверять репутацию источников

Be factual, cite sources, and always provide fresh information.
'''


class SearchAgent(BaseAgent):
    """
    Search Agent - поиск информации в интернете через DuckDuckGo.
    
    Основные функции:
    - Веб-поиск (текстовые результаты)
    - Поиск новостей
    - Извлечение instant answers
    - Суммаризация результатов
    """
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        super().__init__(
            agent_name="search",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        self._ddg_client = None
        
    def _get_default_system_prompt(self) -> str:
        return SEARCH_SYSTEM_PROMPT
    
    def _get_ddg_client(self):
        """Ленивая инициализация DuckDuckGo клиента."""
        if self._ddg_client is None:
            try:
                # Новый пакет ddgs вместо duckduckgo_search
                try:
                    from ddgs import DDGS
                    # DDGS 9.x принимает только proxy, timeout, verify (без headers)
                    self._ddg_client = DDGS(
                        timeout=20,
                        verify=True  # SSL verification
                    )
                    self.logger.info("✅ DuckDuckGo client initialized (ddgs 9.x)")
                except ImportError:
                    # Fallback на старый пакет для обратной совместимости
                    from duckduckgo_search import DDGS
                    self._ddg_client = DDGS()
                    self.logger.warning("⚠️ Using deprecated duckduckgo_search package. Consider upgrading to ddgs")
            except ImportError:
                self.logger.error("❌ ddgs or duckduckgo-search not installed. Install: pip install ddgs")
                raise ImportError("ddgs or duckduckgo-search package is required. Install with: pip install ddgs")
        return self._ddg_client
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает задачу поиска.
        
        Агент самостоятельно понимает тип поиска на основе:
        - Описания задачи (task.description)
        - Параметров задачи (query, search_type)
        - Контекста
        
        Не требует явного указания типа задачи.
        """
        try:
            description = task.get("description", "")
            query = task.get("query", "")
            
            # Если query не указан явно, пытаемся извлечь из description
            if not query and description:
                query = description
            
            if not query:
                return self._format_error_response("Search query is required (provide 'query' or 'description')")
            
            # Определяем тип поиска
            search_type = task.get("search_type", "web")
            
            # Умная определение типа из описания, если search_type не задан явно
            if search_type == "web":
                description_lower = description.lower()
                if any(keyword in description_lower for keyword in ["news", "новости", "latest news", "recent news"]):
                    search_type = "news"
                elif any(keyword in description_lower for keyword in ["instant", "quick answer", "быстрый ответ", "что такое", "define"]):
                    search_type = "quick"
            
            self.logger.info(f"🔍 Processing {search_type} search: {query[:100]}...")
            
            # Выполняем соответствующий тип поиска
            if search_type == "news":
                return await self._news_search(task, context)
            elif search_type == "quick":
                return await self._instant_answer(task, context)
            else:  # default: web
                return await self._web_search(task, context)
                
        except Exception as e:
            self.logger.error(f"Error processing search task: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _web_search(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет веб-поиск через DuckDuckGo.
        """
        try:
            # Получаем query из task (может быть query или description)
            query = task.get("query") or task.get("description", "")
            if not query:
                return self._format_error_response("Search query is required")
            
            max_results = task.get("max_results", 5)
            region = task.get("region", "ru-ru")
            
            self.logger.info(f"🔍 Web search: {query[:100]}...")
            
            # Выполняем поиск
            ddg = self._get_ddg_client()
            results = []
            
            try:
                # DuckDuckGo text search (ddgs 9.x: query - позиционный аргумент)
                search_results = ddg.text(
                    query,  # Позиционный аргумент
                    region=region,
                    max_results=max_results
                )
                
                for result in search_results:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("href", ""),
                        "snippet": result.get("body", ""),
                        "relevance": "unknown"  # DuckDuckGo не предоставляет relevance score
                    })
                
                self.logger.info(f"✅ Found {len(results)} results")
                
            except Exception as e:
                self.logger.error(f"DuckDuckGo search failed: {e}")
                return self._format_error_response(
                    f"Search failed: {str(e)}",
                    suggestions=["Try a different query", "Check internet connection"]
                )
            
            # Используем GigaChat для суммаризации результатов
            summary = await self._summarize_results(query, results)
            
            # Формируем ответ
            response = {
                "status": "success",
                "query": query,
                "results": results,
                "summary": summary,
                "sources": [r["url"] for r in results],
                "timestamp": datetime.now().isoformat(),
                "result_count": len(results),
                "agent": self.agent_name
            }
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in web search: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _news_search(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет поиск новостей через DuckDuckGo.
        """
        try:
            # Получаем query из task (может быть query или description)
            query = task.get("query") or task.get("description", "")
            if not query:
                return self._format_error_response("Search query is required")
            
            max_results = task.get("max_results", 5)
            region = task.get("region", "ru-ru")
            
            self.logger.info(f"📰 News search: {query[:100]}...")
            
            # Выполняем поиск новостей
            ddg = self._get_ddg_client()
            results = []
            
            try:
                # DuckDuckGo news search (ddgs 9.x: query - позиционный аргумент)
                news_results = ddg.news(
                    query,  # Позиционный аргумент
                    region=region,
                    max_results=max_results
                )
                
                for result in news_results:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "snippet": result.get("body", ""),
                        "date": result.get("date", ""),
                        "source": result.get("source", "")
                    })
                
                self.logger.info(f"✅ Found {len(results)} news articles")
                
            except Exception as e:
                self.logger.error(f"DuckDuckGo news search failed: {e}")
                return self._format_error_response(
                    f"News search failed: {str(e)}",
                    suggestions=["Try a different query", "Check internet connection"]
                )
            
            # Суммаризация новостей
            summary = await self._summarize_news(query, results)
            
            response = {
                "status": "success",
                "query": query,
                "results": results,
                "summary": summary,
                "sources": [r["url"] for r in results],
                "timestamp": datetime.now().isoformat(),
                "result_count": len(results),
                "search_type": "news",
                "agent": self.agent_name
            }
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in news search: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _instant_answer(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Получает быстрый ответ на вопрос (instant answer).
        Примечание: DuckDuckGo instant answers API устарел в версии 8+.
        Используем обычный поиск с небольшим количеством результатов.
        """
        try:
            # Получаем query из task (может быть query или description)
            query = task.get("query") or task.get("description", "")
            if not query:
                return self._format_error_response("Search query is required")
            
            self.logger.info(f"⚡ Instant answer: {query[:100]}...")
            self.logger.info("ℹ️ Using web search for instant answers (ddgs 8+ doesn't support answers API)")
            
            # Используем обычный веб-поиск с 3 результатами
            search_task = {
                "query": query,
                "max_results": 3
            }
            
            search_result = await self._web_search(search_task, context)
            
            if search_result.get("status") == "success" and search_result.get("results"):
                # Извлекаем краткий ответ из summary
                return {
                    "status": "success",
                    "query": query,
                    "answer": search_result.get("summary", "No direct answer available"),
                    "results": search_result.get("results", []),
                    "sources": search_result.get("sources", []),
                    "timestamp": datetime.now().isoformat(),
                    "note": "Using web search results (instant answers API deprecated in ddgs 8+)"
                }
            else:
                return self._format_error_response(
                    "Could not find instant answer",
                    suggestions=["Try rephrasing your question", "Use web_search for more results"]
                )
            
        except Exception as e:
            self.logger.error(f"Error in instant answer: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _summarize_results(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Суммаризирует результаты поиска с помощью GigaChat.
        """
        try:
            # Формируем контекст из результатов
            context_parts = []
            for i, result in enumerate(results[:5], 1):  # Берем топ-5
                context_parts.append(f"{i}. {result['title']}\n{result['snippet']}\nИсточник: {result['url']}")
            
            context_text = "\n\n".join(context_parts)
            
            # Prompt для суммаризации
            prompt = f"""На основе следующих результатов поиска, дай краткое резюме (2-3 предложения) по запросу: "{query}"

РЕЗУЛЬТАТЫ ПОИСКА:
{context_text}

Твой ответ должен быть:
- Кратким (2-3 предложения)
- Фактическим (только информация из результатов)
- На русском языке
- Со ссылкой на источники если нужно
"""
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            
            # Извлекаем текст ответа
            if isinstance(response, dict) and "choices" in response:
                summary = response["choices"][0]["message"]["content"]
            elif isinstance(response, dict) and "content" in response:
                summary = response["content"]
            else:
                summary = str(response)
            
            return summary.strip()
            
        except Exception as e:
            self.logger.error(f"Failed to summarize results: {e}")
            # Fallback: просто берем первый snippet
            if results:
                return results[0].get("snippet", "")
            return ""
    
    async def _summarize_news(
        self,
        query: str,
        news: List[Dict[str, Any]]
    ) -> str:
        """
        Суммаризирует новостные результаты.
        """
        try:
            # Формируем контекст из новостей
            context_parts = []
            for i, item in enumerate(news[:5], 1):
                date_str = item.get("date", "Дата неизвестна")
                source_str = item.get("source", "Неизвестный источник")
                context_parts.append(
                    f"{i}. {item['title']} ({source_str}, {date_str})\n"
                    f"{item['snippet']}\n"
                    f"Источник: {item['url']}"
                )
            
            context_text = "\n\n".join(context_parts)
            
            # Prompt для суммаризации новостей
            prompt = f"""На основе следующих новостей, дай краткий обзор (2-3 предложения) по теме: "{query}"

НОВОСТИ:
{context_text}

Твой ответ должен:
- Отразить основные тенденции или события
- Упомянуть даты если важно
- Быть на русском языке
- Быть кратким (2-3 предложения)
"""
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            
            # Извлекаем текст ответа
            if isinstance(response, dict) and "choices" in response:
                summary = response["choices"][0]["message"]["content"]
            elif isinstance(response, dict) and "content" in response:
                summary = response["content"]
            else:
                summary = str(response)
            
            return summary.strip()
            
        except Exception as e:
            self.logger.error(f"Failed to summarize news: {e}")
            # Fallback
            if news:
                return news[0].get("snippet", "")
            return ""
