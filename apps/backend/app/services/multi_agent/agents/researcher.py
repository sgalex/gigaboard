"""
Researcher Agent - Data Fetcher & Web Scraper
Получает данные из внешних источников (API, БД, веб).
"""

import logging
import json
from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для Researcher Agent
RESEARCHER_SYSTEM_PROMPT = '''
Вы — Researcher Agent (Агент-Исследователь) в системе GigaBoard Multi-Agent.

**ОСНОВНАЯ РОЛЬ**: Получение данных из внешних источников (API, баз данных, веб-страниц).

**ВОЗМОЖНОСТИ**:
1. Выполнение SQL запросов к PostgreSQL/MySQL
2. HTTP запросы к REST API
3. Парсинг форматов JSON, XML, CSV, HTML
4. Обработка пагинации и ограничений частоты запросов
5. Базовый веб-скрапинг

**ПОДДЕРЖКА ИСТОЧНИКОВ ДАННЫХ**:
- **API**: REST (GET, POST с JSON)
- **Базы данных**: PostgreSQL (только SELECT)
- **Веб**: Парсинг HTML, JSON endpoints
- **Файлы**: Парсинг CSV, JSON

**ФОРМАТ ВЫВОДА**:
Всегда возвращайте структурированные данные в формате ContentNode:
```json
{
  "content_type": "api_response|table|csv|json",
  "data": <raw_data>,
  "schema": {
    "columns": ["name", "age"],
    "types": ["string", "integer"]
  },
  "source": {
    "type": "api|database|web",
    "url": "https://...",
    "query": "SELECT ...",
    "timestamp": "2026-01-27T10:00:00Z"
  },
  "statistics": {
    "row_count": 1000,
    "size_bytes": 45000
  }
}
```

**ОБРАБОТКА ОШИБОК**:
- Таймаут сети → вернуть ошибку с предложением повторить
- 404 Not Found → вернуть ошибку с альтернативными предложениями
- Лимит запросов → вернуть ошибку с меткой времени retry_after
- Ошибка аутентификации → вернуть ошибку с запросом учётных данных
- Неверный формат → вернуть предупреждение с сырыми данными

**БЕЗОПАСНОСТЬ**:
- Никогда не показывать API ключи в логах
- Всегда использовать HTTPS когда доступно
- Проверять SSL сертификаты
- Таймаут: 30с для API вызовов, 60с для веб-скрапинга
- Макс. размер ответа: 10MB

**ОГРАНИЧЕНИЯ**:
- Только SELECT запросы для баз данных
- Никаких деструктивных операций (DELETE, DROP, UPDATE)
- Соблюдать robots.txt для веб-скрапинга
- Следовать лимитам запросов

Be efficient, handle errors gracefully, and always structure data properly.
'''


class ResearcherAgent(BaseAgent):
    """
    Researcher Agent - получение данных из внешних источников.
    
    Основные функции:
    - HTTP GET/POST запросы к REST API
    - Выполнение SQL SELECT запросов
    - Парсинг различных форматов данных
    - Базовый web scraping
    """
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        super().__init__(
            agent_name="researcher",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        
        # HTTP client с timeout и отключённой SSL верификацией для проблемных доменов
        # Добавляем User-Agent чтобы сайты не блокировали запросы
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10),
            verify=False,  # Отключаем SSL verification для проблемных доменов
            headers=headers
        )
        
    def _get_default_system_prompt(self) -> str:
        return RESEARCHER_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает любую задачу получения данных через умный роутинг.
        
        Агент автоматически определяет, что делать, основываясь на параметрах:
        - Если есть `url` → HTTP запрос к API
        - Если есть `urls` (список) → массовая загрузка страниц
        - Если есть `query` + `database` → SQL запрос
        - Иначе использует описание задачи для понимания намерения
        - Автоматически извлекает URLs из previous_results (SearchAgent)
        """
        # Автоматическое извлечение URLs из previous_results (SearchAgent передаёт sources)
        if context and "previous_results" in context:
            prev_results = context["previous_results"]
            self.logger.info(f"🔍 Checking previous_results for URLs: {list(prev_results.keys())}")
            
            # Собираем все sources из всех предыдущих search результатов
            collected_urls = []
            for agent_name, agent_result in prev_results.items():
                # agent_result уже содержит данные напрямую (не вложенные в "result")
                if isinstance(agent_result, dict):
                    self.logger.info(f"📦 Checking {agent_name} result: has_sources={('sources' in agent_result)}, has_results={('results' in agent_result)}")
                    # Пытаемся найти sources
                    if "sources" in agent_result and isinstance(agent_result["sources"], list):
                        collected_urls.extend(agent_result["sources"])
                        self.logger.info(f"✅ Found {len(agent_result['sources'])} sources in {agent_name}")
                    # Или results с URL
                    if "results" in agent_result and isinstance(agent_result["results"], list):
                        for item in agent_result["results"]:
                            if isinstance(item, dict) and "url" in item:
                                collected_urls.append(item["url"])
                        self.logger.info(f"✅ Found {len([r for r in agent_result['results'] if isinstance(r, dict) and 'url' in r])} URLs in {agent_name} results")
            
            self.logger.info(f"🔗 Total collected URLs: {len(collected_urls)}")
            
            # Если нашли URLs и их нет в task - добавляем
            if collected_urls and "urls" not in task and "url" not in task:
                max_urls = task.get("max_urls", 10)
                task["urls"] = collected_urls[:max_urls]
                self.logger.info(f"🔗 Auto-extracted {len(task['urls'])} URLs from previous_results")
        else:
            self.logger.info(f"⚠️ No previous_results in context (context={bool(context)})")
        
        # Умный роутинг на основе параметров
        if "url" in task and not isinstance(task["url"], list):
            # Single URL → fetch_from_api
            return await self._fetch_from_api(task, context)
        elif "urls" in task or (isinstance(task.get("url"), list)):
            # Multiple URLs → fetch_urls
            if "urls" not in task and "url" in task:
                task["urls"] = task["url"]
            return await self._fetch_urls(task, context)
        elif "query" in task and "database" in task:
            # SQL query → query_database
            return await self._query_database(task, context)
        else:
            # Fallback: используем описание для определения действия
            description = task.get("description", "").lower()
            
            # Проверяем ключевые слова для множественной загрузки (ВЫСШИЙ ПРИОРИТЕТ)
            if any(keyword in description for keyword in ["content", "results", "findings", "pages", "websites", "full text"]):
                # Похоже на множественную загрузку, но нет URLs
                if "urls" not in task and "url" not in task:
                    return self._format_error_response(
                        "Multiple page fetch requested but no URLs found in previous results or task",
                        suggestions=[
                            "Ensure previous search step completed successfully",
                            "Or provide 'urls' parameter explicitly"
                        ]
                    )
                return await self._fetch_urls(task, context)
            elif any(keyword in description for keyword in ["database", "sql", "query database", "select from"]):
                # Похоже на SQL запрос (СПЕЦИФИЧНЫЕ ключевые слова, не "query" alone)
                return await self._query_database(task, context)
            elif any(keyword in description for keyword in ["api", "endpoint", "http request"]):
                # Похоже на API запрос
                if "url" not in task:
                    return self._format_error_response(
                        "API fetch requested but no URL provided",
                        suggestions=["Add 'url' parameter to task"]
                    )
                return await self._fetch_from_api(task, context)
            else:
                # Не можем определить - пытаемся fetch_from_api если есть URL
                if "url" in task:
                    return await self._fetch_from_api(task, context)
                else:
                    return self._format_error_response(
                        f"Cannot determine action from task: {task.get('description', 'No description')}",
                        suggestions=[
                            "Provide 'url' for API request",
                            "Provide 'urls' for multiple page fetch",
                            "Provide 'query' + 'database' for SQL"
                        ]
                    )
    
    async def _fetch_from_api(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет HTTP запрос к REST API.
        """
        try:
            self._validate_task(task, ["url"])
            
            url = task["url"]
            method = task.get("method", "GET").upper()
            headers = task.get("headers", {})
            params = task.get("params", {})
            json_data = task.get("json_data")
            
            self.logger.info(f"🌐 Fetching data from API: {url} ({method})")
            
            # Выполняем HTTP запрос
            if method == "GET":
                response = await self.http_client.get(
                    url,
                    headers=headers,
                    params=params
                )
            elif method == "POST":
                response = await self.http_client.post(
                    url,
                    headers=headers,
                    params=params,
                    json=json_data
                )
            else:
                return self._format_error_response(
                    f"Unsupported HTTP method: {method}",
                    suggestions=["Use GET or POST"]
                )
            
            # Проверяем статус
            response.raise_for_status()
            
            # Парсим ответ
            content_type = response.headers.get("content-type", "")
            
            if "application/json" in content_type:
                data = response.json()
                parsed_content_type = "api_response"
            elif "text/csv" in content_type:
                data = response.text
                parsed_content_type = "csv"
            elif "text/html" in content_type:
                data = response.text
                parsed_content_type = "html"
            else:
                data = response.text
                parsed_content_type = "text"
            
            # Определяем schema если это JSON
            schema = None
            if isinstance(data, (list, dict)):
                schema = self._infer_schema(data)
            
            # Формируем результат
            result = {
                "content_type": parsed_content_type,
                "data": data,
                "source": {
                    "type": "api",
                    "url": url,
                    "method": method,
                    "timestamp": datetime.now().isoformat(),
                    "status_code": response.status_code
                },
                "statistics": {
                    "size_bytes": len(response.content),
                    "row_count": len(data) if isinstance(data, list) else 1
                }
            }
            
            if schema:
                result["schema"] = schema
            
            self.logger.info(f"✅ Data fetched successfully: {result['statistics']['size_bytes']} bytes")
            
            return {
                "status": "success",
                **result,
                "agent": self.agent_name
            }
            
        except httpx.TimeoutException:
            self.logger.error(f"⏱️ Request timeout for {url}")
            return self._format_error_response(
                f"Request timeout after 30s",
                suggestions=["Increase timeout", "Check API availability", "Try alternative endpoint"]
            )
        except httpx.HTTPStatusError as e:
            self.logger.error(f"❌ HTTP error {e.response.status_code}: {url}")
            return self._format_error_response(
                f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
                suggestions=[
                    "Check URL correctness",
                    "Verify API key/authentication" if e.response.status_code == 401 else "Check endpoint availability",
                    "Try alternative endpoint"
                ]
            )
        except Exception as e:
            self.logger.error(f"Error fetching from API: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _fetch_urls(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Массовая загрузка содержимого из списка URL.
        Обычно используется после SearchAgent для загрузки полного содержимого найденных страниц.
        """
        try:
            # URLs могут быть в task["urls"] или извлекаться из previous_results["search"]
            urls = task.get("urls", [])
            
            # Игнорируем placeholders типа "<urls_from_step_1>"
            if isinstance(urls, str) and urls.startswith("<") and urls.endswith(">"):
                self.logger.info(f"🔄 Ignoring placeholder: {urls}")
                urls = []
            
            max_urls = task.get("max_urls", 5)  # Лимит для безопасности
            session_id = context.get("session_id") if context else None
            
            self.logger.info(f"🔍 DEBUG: Initial urls from task: {urls}, type: {type(urls)}")
            self.logger.info(f"🔍 DEBUG: context keys: {list(context.keys()) if context else 'None'}")
            self.logger.info(f"🔍 DEBUG: session_id: {session_id}")
            
            # === Приоритет 1: Получить из Redis (централизованное хранилище) ===
            if not urls and session_id:
                self.logger.info(f"📦 Trying to get SearchAgent results from Redis...")
                search_result = await self.get_agent_result(session_id, "search")
                
                if search_result:
                    self.logger.info(f"✅ Got search result from Redis: keys={list(search_result.keys())}")
                    
                    if search_result.get("status") == "success":
                        search_results = search_result.get("results", [])
                        if isinstance(search_results, list):
                            urls = [r.get("url") for r in search_results if isinstance(r, dict) and r.get("url")]
                            self.logger.info(f"📥 Extracted {len(urls)} URLs from Redis SearchAgent results")
                        else:
                            # Fallback: sources
                            sources = search_result.get("sources", [])
                            if isinstance(sources, list):
                                urls = [s for s in sources if isinstance(s, str) and s.startswith("http")]
                                self.logger.info(f"📥 Extracted {len(urls)} URLs from Redis sources")
                else:
                    self.logger.warning(f"⚠️ No search result in Redis for session {session_id}")
            
            # === Приоритет 2: Получить из context.previous_results (fallback) ===
            if not urls and context and "previous_results" in context:
                self.logger.info(f"🔍 DEBUG: Trying previous_results from context...")
                self.logger.info(f"🔍 DEBUG: previous_results keys: {list(context.get('previous_results', {}).keys())}")
                
                search_result = context["previous_results"].get("search", {})
                self.logger.info(f"🔍 DEBUG: search_result status: {search_result.get('status')}")
                
                if search_result.get("status") == "success":
                    search_results = search_result.get("results", [])
                    self.logger.info(f"📋 SearchAgent returned {len(search_results) if isinstance(search_results, list) else 'non-list'} results")
                    
                    if isinstance(search_results, list):
                        urls = [r.get("url") for r in search_results if isinstance(r, dict) and r.get("url")]
                        self.logger.info(f"📥 Extracted {len(urls)} URLs from context previous_results")
                    else:
                        sources = search_result.get("sources", [])
                        if isinstance(sources, list):
                            urls = [s for s in sources if isinstance(s, str) and s.startswith("http")]
                            self.logger.info(f"📥 Extracted {len(urls)} URLs from context sources")
            
            if not urls:
                return self._format_error_response(
                    "No URLs provided for fetching",
                    suggestions=["Provide 'urls' in task", "Ensure SearchAgent ran successfully"]
                )
            
            # Ограничиваем количество URLs
            urls = urls[:max_urls]
            self.logger.info(f"🌐 Fetching content from {len(urls)} URLs...")
            
            # Загружаем содержимое параллельно
            fetched_pages = []
            errors = []
            
            for i, url in enumerate(urls, 1):
                try:
                    self.logger.info(f"   [{i}/{len(urls)}] Fetching: {url}")
                    
                    response = await self.http_client.get(
                        url,
                        timeout=15.0,  # Shorter timeout for web pages
                        follow_redirects=True
                    )
                    response.raise_for_status()
                    
                    # Извлекаем текстовое содержимое
                    content_type = response.headers.get("content-type", "")
                    
                    if "text/html" in content_type:
                        # Базовая очистка HTML (убираем теги, оставляем текст)
                        text = self._extract_text_from_html(response.text)
                        content = text[:5000]  # Первые 5000 символов
                    else:
                        content = response.text[:5000]
                    
                    fetched_pages.append({
                        "url": url,
                        "title": self._extract_title_from_html(response.text) if "text/html" in content_type else url,
                        "content": content,
                        "content_type": content_type,
                        "status_code": response.status_code,
                        "size_bytes": len(response.content)
                    })
                    
                    self.logger.info(f"   ✅ Success: {len(content)} chars extracted")
                    
                except httpx.TimeoutException as e:
                    error_msg = f"Timeout after 15s: {type(e).__name__}"
                    errors.append({"url": url, "error": error_msg})
                    self.logger.warning(f"   ⏱️ {error_msg}: {url}")
                except httpx.HTTPStatusError as e:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
                    errors.append({"url": url, "error": error_msg})
                    self.logger.warning(f"   ❌ {error_msg}: {url}")
                except httpx.ConnectError as e:
                    error_msg = f"Connection failed: {type(e).__name__} - {str(e) or 'No connection'}"
                    errors.append({"url": url, "error": error_msg})
                    self.logger.warning(f"   ❌ {error_msg}: {url}")
                except httpx.TooManyRedirects as e:
                    error_msg = f"Too many redirects: {str(e)}"
                    errors.append({"url": url, "error": error_msg})
                    self.logger.warning(f"   ❌ {error_msg}: {url}")
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e) or 'Unknown error'}"
                    errors.append({"url": url, "error": error_msg})
                    self.logger.warning(f"   ❌ {error_msg}: {url}")
                    self.logger.error(f"   Full traceback for {url}:", exc_info=True)
            
            # Формируем результат
            result = {
                "status": "success" if fetched_pages else "error",
                "pages": fetched_pages,
                "pages_fetched": len(fetched_pages),
                "pages_failed": len(errors),
                "errors": errors,
                "total_content_bytes": sum(p["size_bytes"] for p in fetched_pages),
                "agent": self.agent_name,
                "timestamp": datetime.now().isoformat()
            }
            
            if not fetched_pages:
                result["message"] = "Failed to fetch any pages"
                result["suggestions"] = ["Check URLs availability", "Verify network connection"]
            else:
                self.logger.info(f"✅ Fetched {len(fetched_pages)}/{len(urls)} pages successfully")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in fetch_urls: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    def _extract_text_from_html(self, html: str) -> str:
        """Базовая очистка HTML - убираем теги, оставляем текст."""
        import re
        # Убираем script и style теги с содержимым
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Убираем HTML теги
        text = re.sub(r'<[^>]+>', ' ', html)
        # Убираем множественные пробелы и переносы
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_title_from_html(self, html: str) -> str:
        """Извлекает title из HTML."""
        import re
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()[:200]
        return "Untitled"
    
    async def _query_database(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет SQL запрос к базе данных.
        
        TODO: Требует интеграции с database connection pool.
        Пока возвращаем mock результат.
        """
        try:
            self._validate_task(task, ["query"])
            
            query = task["query"]
            database_type = task.get("database_type", "postgresql")
            
            self.logger.info(f"🗄️ Querying database: {query[:100]}...")
            
            # Валидация: только SELECT
            query_lower = query.lower().strip()
            if not query_lower.startswith("select"):
                return self._format_error_response(
                    "Only SELECT queries are allowed",
                    suggestions=["Use SELECT statement", "Remove DELETE/UPDATE/DROP operations"]
                )
            
            # TODO: Реальное выполнение через database connection
            # Пока возвращаем placeholder
            self.logger.warning("⚠️ Database query execution not implemented yet (mock result)")
            
            result = {
                "content_type": "table",
                "data": {
                    "columns": ["id", "name", "value"],
                    "rows": [
                        [1, "Sample", 100],
                        [2, "Data", 200]
                    ]
                },
                "source": {
                    "type": "database",
                    "database_type": database_type,
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                },
                "schema": {
                    "columns": ["id", "name", "value"],
                    "types": ["integer", "string", "integer"]
                },
                "statistics": {
                    "row_count": 2
                }
            }
            
            return {
                "status": "success",
                **result,
                "agent": self.agent_name,
                "note": "Mock result - real database integration pending"
            }
            
        except Exception as e:
            self.logger.error(f"Error querying database: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _parse_data(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Парсит данные из различных форматов.
        """
        try:
            self._validate_task(task, ["data", "format"])
            
            data_str = task["data"]
            data_format = task["format"].lower()
            
            self.logger.info(f"📄 Parsing data format: {data_format}")
            
            if data_format == "json":
                data = json.loads(data_str)
                schema = self._infer_schema(data)
                
                result = {
                    "content_type": "json",
                    "data": data,
                    "schema": schema,
                    "statistics": {
                        "size_bytes": len(data_str),
                        "row_count": len(data) if isinstance(data, list) else 1
                    }
                }
                
            elif data_format == "csv":
                # Простой парсинг CSV (без pandas для легковесности)
                lines = data_str.strip().split('\n')
                if len(lines) < 2:
                    return self._format_error_response("CSV must have at least header and one data row")
                
                headers = lines[0].split(',')
                rows = [line.split(',') for line in lines[1:]]
                
                result = {
                    "content_type": "csv",
                    "data": {
                        "columns": headers,
                        "rows": rows
                    },
                    "schema": {
                        "columns": headers,
                        "types": ["string"] * len(headers)  # Упрощенно
                    },
                    "statistics": {
                        "size_bytes": len(data_str),
                        "row_count": len(rows)
                    }
                }
                
            else:
                return self._format_error_response(
                    f"Unsupported format: {data_format}",
                    suggestions=["Supported formats: json, csv"]
                )
            
            self.logger.info(f"✅ Data parsed successfully: {result['statistics']['row_count']} rows")
            
            return {
                "status": "success",
                **result,
                "agent": self.agent_name
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error: {e}")
            return self._format_error_response(
                f"Invalid JSON: {str(e)}",
                suggestions=["Validate JSON syntax", "Check for missing quotes/brackets"]
            )
        except Exception as e:
            self.logger.error(f"Error parsing data: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    def _infer_schema(self, data: Any) -> Dict[str, Any]:
        """
        Определяет schema из данных (упрощенная версия).
        """
        if isinstance(data, list) and len(data) > 0:
            # Берем первый элемент для определения структуры
            first_item = data[0]
            if isinstance(first_item, dict):
                columns = list(first_item.keys())
                types = [self._infer_type(first_item[col]) for col in columns]
                return {
                    "columns": columns,
                    "types": types
                }
        elif isinstance(data, dict):
            columns = list(data.keys())
            types = [self._infer_type(data[col]) for col in columns]
            return {
                "columns": columns,
                "types": types
            }
        
        return {"columns": [], "types": []}
    
    def _infer_type(self, value: Any) -> str:
        """
        Определяет тип данных (упрощенно).
        """
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "unknown"
    
    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup HTTP client."""
        await self.http_client.aclose()
