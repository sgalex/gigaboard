"""
Planner Agent - Orchestrator & Decision Maker
Отвечает за декомпозицию задач и координацию других агентов.
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для Planner Agent из MULTI_AGENT_SYSTEM.md
PLANNER_SYSTEM_PROMPT = '''
Вы — Planner Agent (Агент-Планировщик) в системе GigaBoard Multi-Agent.

**ОСНОВНАЯ РОЛЬ**: Оркестрировать сложные рабочие процессы, делегировать задачи специализированным агентам и адаптировать планы на основе результатов выполнения.

**ОБЯЗАННОСТИ**:
1. Анализировать запросы пользователя и понимать намерения
2. Разбивать сложные запросы на атомарные задачи
3. Делегировать задачи соответствующим специализированным агентам
4. Отслеживать прогресс выполнения и собирать результаты
5. Адаптировать планы при сбоях или неожиданных результатах
6. Сообщать о прогрессе и финальных результатах пользователю

**ДОСТУПНЫЕ АГЕНТЫ И ИХ ТИПЫ ЗАДАЧ**:

**ДОСТУПНЫЕ АГЕНТЫ**:

- **search**: Поиск информации в интернете через DuckDuckGo
  - Входные данные: поисковый запрос (query)
  - Выходные данные: список URL, snippets, краткое резюме
  - Типы поиска: web (общий), news (новости), quick (instant answers)
  - Ограничения: только находит URL и snippets, НЕ загружает полный контент
  - Используй ПЕРВЫМ, когда нужно найти источники данных в интернете
  - ВАЖНО: snippets недостаточны для анализа — нужен ResearcherAgent для загрузки контента!

- **researcher**: Получение данных из внешних источников
  - Входные данные: URL (API/веб), SQL запрос, список URL от SearchAgent
  - Выходные данные: сырые данные (JSON, HTML текст, CSV, таблицы)
  - Возможности: REST API (GET/POST), SQL SELECT, веб-скрапинг, парсинг файлов
  - Форматы: JSON, XML, CSV, HTML → структурированный вывод
  - Ограничения: только SELECT для БД, таймаут 30с для API, 60с для веб
  - Используй ПОСЛЕ search для загрузки полного контента найденных страниц
  - Используй НАПРЯМУЮ если пользователь указал конкретный URL/API

- **analyst**: Извлечение структуры из текста и анализ данных
  - Входные данные: неструктурированный текст, HTML, JSON, результаты других агентов
  - Выходные данные: СТРУКТУРИРОВАННЫЙ JSON для Python/pandas
  - Возможности:
    * Entity extraction — извлечение сущностей (имена, цены, даты, адреса)
    * Таблицы сравнения — список объектов с единой схемой
    * Агрегация — объединение данных из нескольких источников
    * Расчёты — производные метрики с формулами
    * Инсайты — паттерны, тренды, аномалии с количественными оценками
    * SQL генерация — только когда данные уже в БД
  - КЛЮЧЕВОЙ для преобразования сырого текста в данные для визуализации
  - Выход готов к: pd.DataFrame(result["entities"]), JSON для ReporterAgent

- **reporter**: Генерация интерактивных визуализаций
  - Входные данные: СТРУКТУРИРОВАННЫЕ данные (JSON/таблицы от AnalystAgent)
  - Выходные данные: HTML/CSS/JS код для iframe (WidgetNode)
  - Библиотеки: Chart.js, Plotly, D3.js, ECharts
  - Типы виджетов: графики (bar, line, pie), таблицы, метрики, custom
  - Особенности: адаптивная вёрстка, auto-refresh, CDN библиотеки
  - Используй ПОСЛЕ analyst когда данные уже структурированы в JSON
  - НЕ может работать с сырым текстом — нужен analyst для подготовки данных!

- **transformation**: Генерация Python кода для трансформаций данных
  - Входные данные: DataFrame(ы) от ContentNode (df, df1, df2...)
  - Выходные данные: Python код с pandas, результат в df_result (ВСЕГДА DataFrame!)
  - Возможности:
    * Pandas операции: фильтрация, группировка, агрегация, join
    * Numpy вычисления
    * AI-резолвинг через gb модуль (определение пола по имени, классификация текста)
  - Ограничения: запрещены file I/O, сеть, subprocess, eval()
  - Используй для сложных трансформаций, требующих программного кода
  - Используй для multi-source joins (объединение нескольких ContentNode)

**МЕХАНИЗМ ПРИНЯТИЯ РЕШЕНИЙ**:
При получении TASK_RESULT от агентов необходимо:
1. Оценить качество: Задача выполнена успешно? Результат пригоден для использования?
2. Проверить ошибки: Таймаут сети? Данные не найдены? Ошибка формата?
3. Принять решение:
   - `continue`: Перейти к следующему шагу, если всё в порядке
   - `replan`: Изменить план, если контекст изменился (например, найдены дополнительные источники данных)
   - `retry`: Повторить с другими параметрами (например, увеличить таймаут)
   - `abort`: Остановить выполнение при критической ошибке
   - `ask_user`: Запросить решение пользователя, если неоднозначно

**СТРАТЕГИЯ АДАПТИВНОГО ПЛАНИРОВАНИЯ**:

При анализе запроса определите источник данных:

1. **Пользователь указал URL/API**: 
   → используйте ResearcherAgent (fetch_from_api с указанным URL)
   Пример: "Загрузи данные с https://api.example.com/data"

2. **Пользователь указал базу данных/SQL запрос**:
   → используйте ResearcherAgent (query_database)
   Пример: "Найди продажи в базе PostgreSQL"

3. **Нужны данные с выбранных нод на доске**:
   → используйте данные из context.selected_node_ids
   Пример: "Проанализируй эти данные" (при наличии selected_nodes)

4. **Нужна информация из интернета** (нет явного источника):
   → используйте SearchAgent для поиска URL
   → затем ResearcherAgent для загрузки полного содержимого
   → затем AnalystAgent для ИЗВЛЕЧЕНИЯ СТРУКТУРЫ из текста
   → затем ReporterAgent для визуализации (если нужно)
   Пример: "Топ Rust фреймворков", "Статистика кино в Москве"

5. **Пользователь просит создать таблицу и указывает данные в запросе**:
   → используйте ТОЛЬКО AnalystAgent (данные уже есть в промпте!)
   → НЕ используйте TransformationAgent — он для трансформации СУЩЕСТВУЮЩИХ ContentNodes
   Пример: "Создай таблицу сравнения Python, Rust, JavaScript: columns [Language, Year], rows [Python 1991, Rust 2015]"
   Правильный план: analyst → reporter (если нужна визуализация)
   НЕПРАВИЛЬНО: transformation → reporter (TransformationAgent требует входной ContentNode!)

6. **Извлечение структурированных данных из текста**:
   → используйте AnalystAgent с описанием нужной структуры
   Пример: "Извлеки список кинотеатров с адресами и ценами"
   Результат: JSON массив с объектами {name, address, price}

7. **Расчёты и вычисления**:
   → используйте AnalystAgent с формулой/описанием
   Пример: "Рассчитай процент изменения цены"

ВАЖНО: Не используйте SearchAgent, если источник данных явно указан!

**КРИТИЧЕСКИ ВАЖНЫЙ ПАТТЕРН - Search → Research → Analyze → Report**:
Когда SearchAgent находит URL, ОБЯЗАТЕЛЬНО добавляйте шаги для полной обработки:
1. **SearchAgent** находит релевантные URL (snippets недостаточно!)
2. **ResearcherAgent** загружает полное содержимое страниц (HTML → текст)
3. **AnalystAgent** извлекает СТРУКТУРИРОВАННЫЕ ДАННЫЕ (JSON) из текста
4. **ReporterAgent** визуализирует данные (графики, таблицы)

AnalystAgent — КЛЮЧЕВОЙ для преобразования:
- Входит: неструктурированный текст, HTML, сырые данные
- Выходит: JSON массивы и объекты для Python/pandas

Примеры правильного планирования:
- "Топ-5 Rust фреймворков по GitHub stars" → search → researcher → analyst (извлечь таблицу) → reporter
- "Статистика кино в Москве" → search → researcher → analyst (извлечь список кинотеатров) → reporter
- "Загрузи https://api.company.com/stats" → researcher → analyst (структурировать ответ)
- "Проанализируй выбранные данные" → analyst → reporter
- "Сравни цены на iPhone" → search → researcher → analyst (таблица сравнения) → reporter
- "Создай таблицу: Python 1991, Rust 2015, JavaScript 1995" → analyst (данные в промпте!) → reporter
- "Трансформируй данные из ContentNode: отфильтруй по году > 2000" → transformation (работает с существующими данными)

**СЦЕНАРИИ АДАПТИВНОГО ПЛАНИРОВАНИЯ**:
- Данные не найдены → предложить альтернативные источники или уточнить запрос
- Таймаут API → повторить с увеличенным таймаутом или использовать кэш
- Неструктурированные данные → обязательно делегировать AnalystAgent для извлечения структуры
- Нужна сложная трансформация → делегировать TransformationAgent (Python код)

**ФОРМАТ ВЫВОДА**:
КРИТИЧЕСКИ ВАЖНО: Вы ДОЛЖНЫ отвечать ТОЛЬКО валидным JSON. Никаких пояснений, markdown, текста до или после JSON.

Always respond with structured plan in JSON format:
{
  "plan_id": "uuid_v4",
  "user_request": "original user question",
  "steps": [
    {
      "step_id": "1",
      "agent": "search",
      "task": {
        "description": "Find information about top Rust web frameworks",
        "query": "top rust web frameworks github stars 2025"
      },
      "depends_on": [],
      "estimated_time": "3s"
    },
    {
      "step_id": "2", 
      "agent": "researcher",
      "task": {
        "description": "Fetch full content from search results",
        "max_urls": 5
      },
      "depends_on": ["1"],
      "estimated_time": "10s"
    },
    {
      "step_id": "3",
      "agent": "analyst",
      "task": {
        "description": "Extract structured comparison table of Rust frameworks with columns: name, github_stars, category, description"
      },
      "depends_on": ["2"],
      "estimated_time": "5s"
    },
    {
      "step_id": "4",
      "agent": "reporter",
      "task": {
        "description": "Create horizontal bar chart showing Rust frameworks by GitHub stars",
        "chart_type": "bar"
      },
      "depends_on": ["3"],
      "estimated_time": "5s"
    }
  ],
  "estimated_total_time": "23s"
}

**ПАРАМЕТРЫ ЗАДАЧ ДЛЯ КАЖДОГО АГЕНТА**:

**search**:
- `query` (обязательно): поисковый запрос
- `search_type`: "web" | "news" | "quick" (по умолчанию "web")
- `max_results`: 5-10 (по умолчанию 5)

**researcher**:
- Для API: `url`, `method` (GET/POST), `headers`, `params`
- Для веб: `max_urls` (использует URL из предыдущего search)
- Для БД: `query` (SQL SELECT), `database`

**analyst**:
- `description` (обязательно): что нужно извлечь/проанализировать
- Опционально указывай ожидаемую структуру: "columns: name, price, rating"
- Для расчётов: описывай формулу или логику

**reporter**:
- `description` (обязательно): описание визуализации
- `chart_type`: "bar" | "line" | "pie" | "table" | "metric" | "custom"
- `data_preview`: краткое описание данных

**transformation**:
- `description` (обязательно): что нужно трансформировать
- `operation`: "filter" | "aggregate" | "join" | "custom"
- `sources`: количество входных ContentNode (по умолчанию 1)

**ВАЖНО — ЗАВИСИМОСТИ ДАННЫХ**:
- Каждый агент автоматически получает результаты предыдущих шагов через `previous_results`
- ResearcherAgent после SearchAgent автоматически получит найденные URL
- AnalystAgent получит сырые данные от ResearcherAgent
- ReporterAgent получит структурированный JSON от AnalystAgent
- НЕ нужно явно передавать данные между шагами — система делает это автоматически
- Используйте только для загрузки содержимого страниц после SearchAgent
- Пример правильной задачи:
{
  "step_id": "2",
  "agent": "researcher",
  "task": {
    "type": "fetch_urls",
    "description": "Fetch full page content from search results",
    "max_urls": 5
  },
  "depends_on": ["1"]
}

ВАЖНО: 
- Отвечайте ТОЛЬКО JSON объектом, ничего больше
- НЕ включайте никаких пояснений или текста вне JSON
- НЕ оборачивайте JSON в markdown code blocks
- Ответ должен начинаться с { и заканчиваться на }

**ПРАВИЛА DATA-CENTRIC CANVAS**:
- Данные извлекаются из SourceNode в ContentNode (EXTRACT связь)
- WidgetNode требует родительский ContentNode (VISUALIZATION связь)
- Трансформации создают новый ContentNode с TRANSFORMATION связью (ContentNode → ContentNode)
- Отслеживайте происхождение данных для всех операций (data lineage)

**ОГРАНИЧЕНИЯ**:
- Никогда не выполняйте код напрямую — всегда делегируйте Executor Agent
- Никогда не обращайтесь к внешним API — всегда делегируйте Researcher Agent
- Никогда не делайте предположений — спросите пользователя, если контекст неясен
- Всегда проверяйте ответы агентов перед переходом к следующему шагу

Будьте лаконичны, точны и всегда думайте о сценариях ошибок.
'''


class PlannerAgent(BaseAgent):
    """
    Planner Agent - главный координатор Multi-Agent системы.
    
    Основные функции:
    - Декомпозиция user requests на атомарные задачи
    - Роутинг задач к специализированным агентам
    - Адаптивное планирование на основе результатов
    - Принятие решений (continue, retry, replan, abort)
    """
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        super().__init__(
            agent_name="planner",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        
    def _get_default_system_prompt(self) -> str:
        return PLANNER_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает задачу планирования.
        
        Поддерживаемые типы задач:
        - create_plan: Создать план из user request
        - replan: Адаптировать существующий план
        - evaluate_result: Оценить результат задачи и решить, продолжать ли
        """
        task_type = task.get("type")
        
        if task_type == "create_plan":
            return await self._create_plan(task, context)
        elif task_type == "replan":
            return await self._replan(task, context)
        elif task_type == "evaluate_result":
            return await self._evaluate_result(task, context)
        else:
            return self._format_error_response(
                f"Unknown task type: {task_type}",
                suggestions=["Supported types: create_plan, replan, evaluate_result"]
            )
    
    async def _create_plan(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Создает план выполнения из user request.
        """
        try:
            # Валидация входных данных
            self._validate_task(task, ["user_request"])
            
            user_request = task["user_request"]
            board_id = context.get("board_id") if context else None
            selected_node_ids = context.get("selected_node_ids", []) if context else []
            
            self.logger.info(f"🧠 Creating plan for request: {user_request[:100]}...")
            
            # Формируем prompt для GigaChat
            planning_prompt = self._build_planning_prompt(
                user_request=user_request,
                board_id=board_id,
                selected_node_ids=selected_node_ids,
                context=context
            )
            
            # Вызываем GigaChat для генерации плана
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": planning_prompt}
            ]
            
            self.logger.info(f"🤖 Calling GigaChat with {len(messages)} messages")
            
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.3,  # Низкая температура для более детерминированных планов
                max_tokens=2000
            )
            
            self.logger.info(f"📥 GigaChat response type: {type(response)}")
            self.logger.debug(f"📦 Full response: {str(response)[:500]}...")
            
            # Парсим JSON ответ от GigaChat
            plan = self._parse_plan_from_response(response)
            
            # Валидация плана
            self._validate_plan(plan)
            
            self.logger.info(f"✅ Plan created with {len(plan['steps'])} steps")
            
            return {
                "status": "success",
                "plan": plan,
                "agent": self.agent_name
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse plan JSON: {e}")
            return self._format_error_response(
                "Failed to parse plan from LLM response",
                suggestions=["Retry with adjusted prompt", "Use simpler user request"]
            )
        except Exception as e:
            self.logger.error(f"Error creating plan: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _replan(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Адаптирует существующий план на основе новых данных.
        """
        try:
            self._validate_task(task, ["original_plan", "reason", "failed_step"])
            
            original_plan = task["original_plan"]
            reason = task["reason"]
            failed_step = task["failed_step"]
            
            self.logger.info(f"🔄 Replanning due to: {reason}")
            
            # Формируем prompt для адаптации
            replan_prompt = f"""
ORIGINAL PLAN:
{json.dumps(original_plan, indent=2, ensure_ascii=False)}

FAILED STEP: {failed_step}
REASON: {reason}

Create an updated plan that addresses the failure. You can:
1. Modify parameters of the failed step
2. Add new intermediate steps
3. Use alternative agents or approaches
4. Skip problematic steps if not critical

Return updated plan in the same JSON format.
"""
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": replan_prompt}
            ]
            response = await self.gigachat.chat_completion(
                messages=messages,
                temperature=0.5
            )
            
            updated_plan = self._parse_plan_from_response(response)
            self._validate_plan(updated_plan)
            
            self.logger.info(f"✅ Plan updated with {len(updated_plan['steps'])} steps")
            
            return {
                "status": "success",
                "plan": updated_plan,
                "changes": f"Adapted plan due to: {reason}",
                "agent": self.agent_name
            }
            
        except Exception as e:
            self.logger.error(f"Error replanning: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _evaluate_result(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Оценивает результат выполнения задачи и принимает решение о дальнейших действиях.
        Использует AI-powered анализ для интеллектуальных решений.
        """
        try:
            self._validate_task(task, ["step_result", "step_id"])
            
            step_result = task["step_result"]
            step_id = task["step_id"]
            
            # Анализируем результат
            status = step_result.get("status")
            
            if status == "success":
                decision = "continue"
                message = "Step completed successfully, proceed to next step"
            elif status == "error":
                error_msg = step_result.get("error", "Unknown error")
                agent = step_result.get("agent", "unknown")
                
                # Используем AI для интеллектуального анализа ошибки
                try:
                    ai_decision = await self._ai_evaluate_error(
                        error_msg=error_msg,
                        agent=agent,
                        step_id=step_id,
                        context=context
                    )
                    decision = ai_decision.get("decision", "abort")
                    message = ai_decision.get("message", error_msg)
                    self.logger.info(f"🤖 AI decision: {decision} - {message}")
                except Exception as ai_error:
                    # Fallback на улучшенную эвристику
                    self.logger.warning(f"AI evaluation failed, using enhanced heuristics: {ai_error}")
                    decision, message = self._heuristic_evaluate_error(error_msg, agent)
            else:
                decision = "continue"
                message = "Unknown status, proceeding cautiously"
            
            self.logger.info(f"📊 Evaluation decision for step {step_id}: {decision}")
            
            return {
                "status": "success",
                "decision": decision,
                "message": message,
                "step_id": step_id,
                "agent": self.agent_name
            }
            
        except Exception as e:
            self.logger.error(f"Error evaluating result: {e}", exc_info=True)
            return self._format_error_response(str(e))
    
    async def _ai_evaluate_error(
        self,
        error_msg: str,
        agent: str,
        step_id: int,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Использует GigaChat для интеллектуального анализа ошибки.
        """
        prompt = f"""Проанализируй ошибку в multi-agent workflow и выбери оптимальное решение.

ОШИБКА: {error_msg}
АГЕНТ: {agent}
ШАГ: {step_id}

ДОСТУПНЫЕ РЕШЕНИЯ:
1. RETRY - временная ошибка, можно повторить (timeout, connection, rate limit)
2. REPLAN - ошибка требует изменения плана (data not found, access denied, format error, resource unavailable)
3. ABORT - критическая нефиксимая ошибка (authentication failed, invalid credentials, fatal error)
4. CONTINUE - некритичная ошибка, можно продолжить без этого шага

КРИТЕРИИ ДЛЯ REPLAN:
- Источник данных недоступен → можно найти альтернативный
- Формат не поддерживается → можно добавить конвертацию
- Недостаточно данных → можно расширить поиск
- Доступ запрещён (403, 401) → можно использовать другой источник
- Ресурс не найден (404) → можно поискать альтернативы

ВАЖНО: Предпочитай REPLAN если есть возможность обойти проблему другим путём!

Верни JSON:
{{"decision": "retry|replan|abort|continue", "reason": "краткое объяснение"}}"""

        messages = [
            {"role": "system", "content": "Ты эксперт по анализу ошибок в workflow системах. Твоя задача - принимать взвешенные решения о продолжении работы."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.gigachat.chat_completion(
            messages=messages,
            temperature=0.3  # Консервативные решения
        )
        
        # Парсим ответ
        import re
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "decision": result.get("decision", "abort"),
                "message": result.get("reason", error_msg)
            }
        else:
            raise ValueError("Could not parse AI response")
    
    def _heuristic_evaluate_error(
        self,
        error_msg: str,
        agent: str
    ) -> tuple[str, str]:
        """
        Улучшенная эвристика для оценки ошибок (fallback если AI не работает).
        """
        error_lower = error_msg.lower()
        
        # RETRY - временные ошибки
        retry_keywords = ["timeout", "connection", "temporary", "rate limit", "try again"]
        if any(kw in error_lower for kw in retry_keywords):
            return "retry", f"Temporary error detected: {error_msg}"
        
        # REPLAN - ошибки, которые можно обойти
        replan_keywords = [
            "not found", "404", "missing", "unavailable", "does not exist",
            "access denied", "403", "forbidden", "401", "unauthorized",
            "invalid format", "cannot parse", "unsupported", "format error",
            "insufficient data", "no results", "empty", "no data"
        ]
        if any(kw in error_lower for kw in replan_keywords):
            return "replan", f"Error can be worked around: {error_msg}"
        
        # CONTINUE - некритичные ошибки
        continue_keywords = ["warning", "partial", "some failed"]
        if any(kw in error_lower for kw in continue_keywords):
            return "continue", f"Non-critical error: {error_msg}"
        
        # ABORT - всё остальное
        return "abort", f"Critical error: {error_msg}"
    
    def _build_planning_prompt(
        self,
        user_request: str,
        board_id: Optional[str],
        selected_node_ids: List[str],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Формирует prompt для GigaChat.
        """
        prompt_parts = [
            f"USER REQUEST: {user_request}",
            ""
        ]
        
        if board_id:
            prompt_parts.append(f"BOARD ID: {board_id}")
        
        if selected_node_ids:
            prompt_parts.append(f"SELECTED NODES: {', '.join(selected_node_ids)}")
        
        if context and context.get("board_data"):
            prompt_parts.append("\nBOARD CONTEXT:")
            prompt_parts.append(json.dumps(context["board_data"], indent=2, ensure_ascii=False))
        
        prompt_parts.extend([
            "",
            "Create a detailed execution plan with steps delegated to appropriate agents.",
            "Return the plan as a valid JSON object following the specified format.",
            "Think step-by-step about what needs to be done and which agent is best suited for each task."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_plan_from_response(self, response) -> Dict[str, Any]:
        """
        Парсит JSON план из ответа LLM.
        Поддерживает извлечение JSON из markdown code blocks.
        """
        self.logger.info(f"🔍 Parsing plan from response type: {type(response).__name__}")
        
        # Если response - это словарь (уже распарсенный JSON)
        if isinstance(response, dict):
            # GigaChat API может возвращать структуру с choices
            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0].get("message", {}).get("content", "")
                self.logger.info(f"📄 Extracted content from choices: {content[:200]}...")
            elif "content" in response:
                content = response["content"]
                self.logger.info(f"📄 Extracted content from response: {content[:200]}...")
            else:
                # Уже готовый план
                self.logger.info("✅ Response is already a plan dict")
                return response
        else:
            # Если response - строка
            content = str(response)
            self.logger.info(f"📄 Response as string: {content[:200]}...")
        
        # Очищаем от лишнего
        content = content.strip()
        
        if not content:
            self.logger.error("❌ Empty content after extraction")
            raise ValueError("Empty response from GigaChat")
        
        # Удаляем markdown code blocks если есть
        if content.startswith("```json"):
            content = content[7:]
            self.logger.info("🔧 Removed ```json prefix")
        elif content.startswith("```"):
            content = content[3:]
            self.logger.info("🔧 Removed ``` prefix")
        
        if content.endswith("```"):
            content = content[:-3]
            self.logger.info("🔧 Removed ``` suffix")
        
        content = content.strip()
        
        self.logger.info(f"📝 Content to parse: {content[:300]}...")
        
        try:
            # Парсим JSON
            plan = json.loads(content)
            self.logger.info(f"✅ Successfully parsed JSON plan with {len(plan.get('steps', []))} steps")
            return plan
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON decode error: {e}")
            self.logger.error(f"📋 Failed content: {content}")
            raise
    
    def _validate_plan(self, plan: Dict[str, Any]) -> None:
        """
        Валидирует структуру плана.
        """
        required_fields = ["steps"]
        missing = [f for f in required_fields if f not in plan]
        
        if missing:
            raise ValueError(f"Plan missing required fields: {', '.join(missing)}")
        
        if not isinstance(plan["steps"], list):
            raise ValueError("Plan 'steps' must be a list")
        
        if len(plan["steps"]) == 0:
            raise ValueError("Plan must have at least one step")
        
        # Валидация каждого step
        for i, step in enumerate(plan["steps"]):
            if "agent" not in step:
                raise ValueError(f"Step {i} missing 'agent' field")
            if "task" not in step:
                raise ValueError(f"Step {i} missing 'task' field")
