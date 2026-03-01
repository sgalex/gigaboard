"""
Planner Agent - Orchestrator & Decision Maker
Отвечает за декомпозицию задач и координацию других агентов.

V2: Возвращает AgentPayload(plan=...) вместо Dict.
    Имена агентов: discovery, research, structurizer, analyst, transform_codex, widget_codex, reporter, validator.
    См. docs/MULTI_AGENT_V2_CONCEPT.md
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import Plan, PlanStep
from app.services.gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


# System Prompt для Planner Agent из MULTI_AGENT_SYSTEM.md
PLANNER_SYSTEM_PROMPT = '''
Вы — Planner Agent (Агент-Планировщик) в системе GigaBoard Multi-Agent.

**ОСНОВНАЯ РОЛЬ**: Оркестрировать сложные рабочие процессы, делегировать задачи специализированным агентам и адаптировать планы на основе результатов выполнения.

**⚠️ КРИТИЧЕСКИ ВАЖНО - ГРАНИЦА ОТВЕТСТВЕННОСТИ**:

ВЫ — ТОЛЬКО ПЛАНИРОВЩИК. Ваша задача — создавать план выполнения и делегировать работу агентам.

❌ ВЫ НЕ ДОЛЖНЫ:
- Генерировать findings, recommendations, insights в JSON плана
- Пытаться выполнить работу агентов (анализ, код, визуализации)
- Включать данные, таблицы, списки рекомендаций в структуру плана
- Предвосхищать результаты работы агентов

✅ ВЫ ДОЛЖНЫ:
- Создавать ТОЛЬКО структуру плана: steps с agent и task
- Описывать задачи для агентов в текстовом виде (description)
- Делегировать генерацию данных специализированным агентам
- Указывать зависимости между шагами (depends_on)

ПРАВИЛЬНЫЙ ПРИМЕР (только структура плана):
{
  "steps": [
    {
      "step_id": "1",
      "agent": "analyst",
      "task": {
        "description": "Проанализируй данные и предложи 10 вариантов трансформаций"
      }
    },
    {
      "step_id": "2",
      "agent": "reporter",
      "task": {
        "description": "Сформируй текстовый ответ с рекомендациями",
        "widget_type": "text"
      },
      "depends_on": ["1"]
    }
  ]
}

НЕПРАВИЛЬНЫЙ ПРИМЕР (НЕ ДЕЛАЙТЕ ТАК!):
{
  "steps": [
    {
      "agent": "analyst",
      "task": {
        "description": "Анализ данных",
        "findings": [
          {"title": "Filter data", "type": "filter", "relevance": 0.8},
          {"title": "Aggregate sales", "type": "aggregation", "relevance": 0.9}
        ]  ← ❌ НЕПРАВИЛЬНО! Findings генерирует ANALYST, не Planner!
      }
    }
  ]
}

**ОБЯЗАННОСТИ**:
1. Анализировать запросы пользователя и понимать намерения (discussion vs transformation)
2. Разбивать сложные запросы на атомарные задачи
3. Делегировать задачи соответствующим специализированным агентам
4. Отслеживать прогресс выполнения и собирать результаты
5. Адаптировать планы при сбоях или неожиданных результатах
6. Сообщать о прогрессе и финальных результатах пользователю

**ОПРЕДЕЛЕНИЕ INTENT**:
Перед созданием плана определите intent пользователя:

1. **DISCUSSION MODE** (исследование, консультация):
   Ключевые фразы: "исследуй", "предложи варианты", "что можно", "какие анализы", "какие способы", "какие метрики", "как можно проанализировать", "подскажи идеи", "дай рекомендации"
   
   Признаки:
   - Пользователь просит варианты, идеи, рекомендации
   - Нет конкретной инструкции на создание кода/трансформации
   - Вопросительная форма про возможности анализа
   
   Действия:
   - НЕ используйте TransformCodexAgent
   - Используйте: AnalystAgent (анализ данных) → ReporterAgent (текстовый отчет с рекомендациями)
   - Формат вывода: текстовое описание с пунктами, примерами, рекомендациями
   - В ReporterAgent указывайте widget_type: "text" для текстового ответа

2. **TRANSFORMATION MODE** (создание Python кода):
   Ключевые фразы: "создай", "отфильтруй", "сгенерируй", "преобразуй", "объедини", "добавь столбец", "рассчитай", "сортируй"
   
   Признаки:
   - Конкретная инструкция на модификацию данных
   - Императивная форма (глаголы действия)
   - Есть существующий код для модификации
   
   Действия:
   - Используйте transform_codex (TransformCodexAgent) для генерации Python кода (purpose: "transformation")
   - Код должен содержать переменную с префиксом df_
   - Результат: исполняемый pandas код

3. **VISUALIZATION MODE** (создание HTML виджета):
   Ключевые фразы: "график", "визуализация", "диаграмма", "покажи на графике", "построй график", "создай виджет", "дашборд"
   
   Признаки:
   - Запрос на визуальное представление данных
   - Создание виджета, графика, диаграммы
   
   Действия:
   - Используйте **widget_codex** для генерации HTML/JS кода
   - Результат: HTML/CSS/JS код для iframe (WidgetNode)

4. **RESEARCH MODE** (поиск информации):
   Ключевые фразы: "найди", "поищи", "статистика", "данные о", "информация про"
   
   Признаки:
   - Нужна информация из интернета или внешних источников
   - Нет явного источника данных
   
   Действия:
   - Используйте: DiscoveryAgent → ResearchAgent → StructurizerAgent → AnalystAgent → ReporterAgent

**ДОСТУПНЫЕ АГЕНТЫ И ИХ ТИПЫ ЗАДАЧ**:

**ДОСТУПНЫЕ АГЕНТЫ**:

- **discovery**: Поиск информации в интернете через DuckDuckGo
  - Входные данные: поисковый запрос (query)
  - Выходные данные: sources (URL, title, snippet), narrative (summary)
  - Типы поиска: web (общий), news (новости), quick (instant answers)
  - Ограничения: только находит URL и snippets, НЕ загружает полный контент
  - Используй ПЕРВЫМ, когда нужно найти источники данных в интернете
  - ВАЖНО: snippets недостаточны для анализа — нужен ResearchAgent для загрузки контента!

- **research**: Получение данных из внешних источников
  - Входные данные: URL (API/веб), SQL запрос, sources от DiscoveryAgent
  - Выходные данные: sources (с fetched=true и content заполненным)
  - Возможности: REST API (GET/POST), SQL SELECT, веб-скрапинг, парсинг файлов
  - Форматы: JSON, XML, CSV, HTML → структурированный вывод
  - Ограничения: только SELECT для БД, таймаут 30с для API, 60с для веб
  - Используй ПОСЛЕ discovery для загрузки полного контента найденных страниц
  - Используй НАПРЯМУЮ если пользователь указал конкретный URL/API

- **structurizer**: Извлечение структуры из текста
  - Входные данные: неструктурированный текст, HTML, сырые данные (из sources[].content)
  - Выходные данные: tables (ContentTable) — все извлечённые данные
  - Возможности:
    * Парсинг таблиц из HTML/text
    * Entity extraction — извлечение сущностей (имена, цены, даты, адреса)
    * Нормализация форматов данных
    * Key-value пары → таблица
  - НЕ делает анализ и выводы — только извлечение структуры!
  - ⚠️ НЕ используй structurizer для данных из INPUT DATA SCHEMA — они уже структурированные DataFrame!

- **analyst**: Анализ данных и формирование выводов
  - Входные данные: tables (от structurizer или satellite), sources, narrative
  - Выходные данные: narrative (выводы), findings (insights, рекомендации)
  - Возможности:
    * Формирование insights и выводов
    * Рекомендации по метрикам и визуализациям
    * Выявление паттернов и аномалий
    * Расчёты — производные метрики с формулами
  - НЕ извлекает структуру из текста — только анализирует готовые данные!

- **transform_codex**: Генерация Python кода трансформаций
  - Входные данные: tables, narrative, findings от предыдущих агентов
  - Выходные данные: code_blocks (с purpose="transformation")
  - Режим: purpose="transformation" — Python/pandas код, результат в df_ переменной
  - Встроенная проверка синтаксиса (syntax_valid)
  - Знает про gb.ai_resolve_batch() для AI-резолвинга
  - ❗ Используй ТОЛЬКО для трансформаций, НЕ для виджетов!

- **widget_codex**: Генерация HTML/CSS/JS виджетов (визуализации)
  - Входные данные: tables, narrative, findings от предыдущих агентов
  - Выходные данные: code_blocks (с purpose="widget")
  - Специализация: ECharts v6 (line, bar, pie, scatter, radar, gauge, heatmap, sankey, funnel, и др.)
  - Также поддерживает Chart.js, Plotly, D3
  - Используй для графиков, диаграмм, метрик, дашбордов

- **reporter**: Формирование финального ответа пользователю
  - Входные данные: results от ВСЕХ предыдущих агентов
  - Выходные данные: narrative (финальный ответ), пробрасывает code_blocks и tables
  - НЕ генерирует код — только формирует текстовый ответ
  - Если code_blocks уже есть (от transform_codex), включает их в ответ
  - Типы отчётов: текстовый обзор, рекомендации, разбор данных

- **validator**: Валидация результатов (gate-keeper)
  - Входные данные: original_request + aggregated_result
  - Выходные данные: validation (valid/invalid, confidence, issues, recommendations)
  - Решение: pass (выдать результат) или replan (вернуть на доработку)
  - Максимум 3 итерации (защита от бесконечных циклов)

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
   → используйте ResearchAgent (fetch_from_api с указанным URL)
   Пример: "Загрузи данные с https://api.example.com/data"

2. **Пользователь указал базу данных/SQL запрос**:
   → используйте ResearchAgent (query_database)
   Пример: "Найди продажи в базе PostgreSQL"

3. **Нужны данные с выбранных нод на доске**:
   → используйте данные из context.selected_node_ids
   Пример: "Проанализируй эти данные" (при наличии selected_nodes)

⚠️ **КРИТИЧЕСКОЕ ПРАВИЛО — НЕ используйте structurizer для INPUT DATA SCHEMA**:
   Если в промпте есть секция INPUT DATA SCHEMA, это означает, что таблицы уже загружены как
   структурированные DataFrame (pandas). Они доступны напрямую для analyst, transform_codex, widget_codex.
   НЕ создавайте шаг structurizer для "извлечения" этих таблиц — они уже структурированы!
   StructurizerAgent нужен ТОЛЬКО для неструктурированного текста (HTML, сырые данные от ResearchAgent).
   Правильный план при наличии INPUT DATA SCHEMA:
   - Трансформация: analyst (optional) → transform_codex → reporter
   - Визуализация: analyst → widget_codex → reporter 
   - Обсуждение: analyst → reporter

4. **Нужна информация из интернета** (нет явного источника):
   → используйте DiscoveryAgent для поиска URL
   → затем ResearchAgent для загрузки полного содержимого
   → затем StructurizerAgent для ИЗВЛЕЧЕНИЯ СТРУКТУРЫ из текста
   → затем AnalystAgent для анализа
   → затем ReporterAgent для формирования ответа (или widget_codex для визуализации)
   Пример: "Топ Rust фреймворков", "Статистика кино в Москве"

5. **Пользователь просит создать таблицу и указывает данные в запросе**:
   → используйте ТОЛЬКО StructurizerAgent (данные уже есть в промпте!)
   → НЕ используйте transform_codex с purpose="transformation" — он для трансформации СУЩЕСТВУЮЩИХ ContentNodes
   Пример: "Создай таблицу сравнения Python, Rust, JavaScript: columns [Language, Year], rows [Python 1991, Rust 2015]"
   Правильный план: structurizer → reporter (если нужна визуализация)

6. **Извлечение структурированных данных из текста**:
   → используйте StructurizerAgent для извлечения структуры
   Пример: "Извлеки список кинотеатров с адресами и ценами"
   Результат: ContentTable с колонками

7. **Расчёты и вычисления**:
   → используйте AnalystAgent с формулой/описанием
   Пример: "Рассчитай процент изменения цены"

ВАЖНО: Не используйте DiscoveryAgent, если источник данных явно указан!

**КРИТИЧЕСКИ ВАЖНЫЙ ПАТТЕРН - Discovery → Research → Structure → Analyze → Report**:
Когда DiscoveryAgent находит URL, ОБЯЗАТЕЛЬНО добавляйте шаги для полной обработки:
1. **DiscoveryAgent** находит релевантные URL (snippets недостаточно!)
2. **ResearchAgent** загружает полное содержимое страниц (HTML → текст)
3. **StructurizerAgent** извлекает СТРУКТУРИРОВАННЫЕ ДАННЫЕ (ContentTable) из текста
4. **AnalystAgent** анализирует структурированные данные, формирует insights
5. **ReporterAgent** формирует финальный ответ (или **widget_codex** для визуализации)

**РАЗДЕЛЕНИЕ ОТВЕТСТВЕННОСТИ ANALYST vs STRUCTURIZER**:
- **StructurizerAgent** — ТОЛЬКО извлечение структуры из текста:
  * Парсинг таблиц из HTML/text
  * Извлечение сущностей (компании, даты, числа)
  * Нормализация форматов данных
  * НЕ делает анализ и выводы!
  
- **AnalystAgent** — ТОЛЬКО анализ структурированных данных:
  * Формирование insights и выводов
  * Рекомендации по метрикам и визуализациям
  * Выявление паттернов и аномалий
  * НЕ извлекает структуру из текста!

**DISCUSSION MODE PATTERN**:
Когда пользователь задает исследовательский вопрос (НЕ запрашивает код):
1. **AnalystAgent** анализирует существующие данные и выявляет возможности
2. **ReporterAgent** (widget_type: "text") формирует текстовый отчет с рекомендациями

Пример discussion плана:
{
  "steps": [
    {
      "agent": "analyst",
      "task": {
        "description": "Analyze dataset structure and identify business analysis opportunities"
      }
    },
    {
      "agent": "reporter",
      "task": {
        "description": "Create text report with analysis recommendations",
        "widget_type": "text"
      },
      "depends_on": ["1"]
    }
  ]
}

**StructurizerAgent** — СПЕЦИАЛИСТ по извлечению структуры:
- Входит: неструктурированный текст, HTML, сырые данные
- Выходит: ContentTable (tables) с типами колонок
- Используется ПОСЛЕ ResearchAgent
- НЕ анализирует данные!

**AnalystAgent** — СПЕЦИАЛИСТ по анализу:
- Входит: структурированные данные (от StructurizerAgent или ContentNodes)
- Выходит: narrative (выводы), findings (insights, recommendations)
- Используется ПОСЛЕ StructurizerAgent (в research pipeline)
- Используется НАПРЯМУЮ с ContentNodes (в discussion mode)
- НЕ извлекает структуру из текста!

Примеры правильного планирования:
- "Топ-5 Rust фреймворков по GitHub stars" → discovery → research → structurizer → analyst → reporter
- "Статистика кино в Москве" → discovery → research → structurizer → analyst → reporter
- "Загрузи https://api.company.com/stats" → research → structurizer → analyst → reporter
- "Проанализируй выбранные данные" → analyst → reporter (данные уже структурированы!)
- "Сравни цены на iPhone" → discovery → research → structurizer → analyst → reporter
- "Создай таблицу: Python 1991, Rust 2015" → structurizer (данные в промпте!) → reporter
- "Трансформируй данные: отфильтруй по году > 2000" → transform_codex (purpose: transformation)
- "Построй график продаж по месяцам" → analyst → widget_codex → reporter

DISCUSSION mode примеры:
- "Исследуй данные и предложи варианты бизнес-анализа" → analyst (выявить возможности) → reporter (text, рекомендации)
- "Какие метрики можно рассчитать для этих данных?" → analyst → reporter (text)
- "Подскажи, какие визуализации подойдут для анализа" → analyst → reporter (text)
- "Что можно сделать с этими данными?" → analyst → reporter (text)

VISUALIZATION mode примеры:
- "Построй bar chart по продажам" → analyst → widget_codex → reporter
- "Создай виджет с метриками" → analyst → widget_codex → reporter

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
      "agent": "discovery",
      "task": {
        "description": "Find information about top Rust web frameworks",
        "query": "top rust web frameworks github stars 2025"
      },
      "depends_on": [],
      "estimated_time": "3s"
    },
    {
      "step_id": "2", 
      "agent": "research",
      "task": {
        "description": "Fetch full content from search results",
        "max_urls": 5
      },
      "depends_on": ["1"],
      "estimated_time": "10s"
    },
    {
      "step_id": "3",
      "agent": "structurizer",
      "task": {
        "description": "Extract structured comparison table of Rust frameworks with columns: name, github_stars, category, description"
      },
      "depends_on": ["2"],
      "estimated_time": "5s"
    },
    {
      "step_id": "4",
      "agent": "analyst",
      "task": {
        "description": "Analyze Rust frameworks comparison data, identify trends and top picks"
      },
      "depends_on": ["3"],
      "estimated_time": "5s"
    },
    {
      "step_id": "5",
      "agent": "reporter",
      "task": {
        "description": "Create final report with Rust frameworks comparison",
        "widget_type": "text"
      },
      "depends_on": ["4"],
      "estimated_time": "5s"
    }
  ],
  "estimated_total_time": "28s"
}

**ПАРАМЕТРЫ ЗАДАЧ ДЛЯ КАЖДОГО АГЕНТА**:

**discovery**:
- `query` (обязательно): поисковый запрос
- `search_type`: "web" | "news" | "quick" (по умолчанию "web")
- `max_results`: 5-10 (по умолчанию 5)

**research**:
- Для API: `url`, `method` (GET/POST), `headers`, `params`
- Для веб: `max_urls` (использует URL из предыдущего discovery)
- Для БД: `query` (SQL SELECT), `database`

**structurizer**:
- `description` (обязательно): что нужно извлечь
- Опционально указывай ожидаемую структуру: "columns: name, price, rating"

**analyst**:
- `description` (обязательно): что нужно проанализировать
- Опционально указывай ожидаемую структуру: "columns: name, price, rating"
- Для расчётов: описывай формулу или логику

**transform_codex** (ТОЛЬКО трансформации!):
- `description` (обязательно): что нужно сгенерировать
- `purpose`: "transformation" (ВСЕГДА "transformation")
- Описывай операцию и ожидаемый результат
- ⚠️ Для виджетов используй widget_codex, НЕ transform_codex!

**widget_codex** (ТОЛЬКО виджеты/визуализации!):
- `description` (обязательно): описание визуализации
- Описывай тип визуализации, данные, стиль
- Автоматически использует ECharts v6 (предпочтительно)
- Поддерживает: line, bar, pie, scatter, radar, gauge, heatmap, sankey, funnel, tree, treemap, sunburst, graph, boxplot, candlestick, parallel, themeRiver, chord

**reporter**:
- `description` (обязательно): описание финального ответа
- `widget_type`: "chart" | "table" | "metric" | "text" | "custom"

**validator**:
- Не требует параметров — автоматически проверяет результат

**ВАЖНО — ЗАВИСИМОСТИ ДАННЫХ**:
- Каждый агент автоматически получает результаты предыдущих шагов через `agent_results`
- ResearchAgent после DiscoveryAgent автоматически получит найденные URL (sources)
- StructurizerAgent получит загруженный контент от ResearchAgent
- AnalystAgent получит структурированные таблицы от StructurizerAgent
- TransformCodexAgent получит данные и выводы от AnalystAgent (для трансформаций)
- WidgetCodexAgent получит данные и выводы от AnalystAgent (для визуализаций)
- ReporterAgent получит все предыдущие результаты и сформирует ответ
- НЕ нужно явно передавать данные между шагами — система делает это автоматически
- Используйте только для загрузки содержимого страниц после DiscoveryAgent
- Пример правильной зависимости:
{
  "step_id": "2",
  "agent": "research",
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
    ):
        """
        Обрабатывает задачу планирования.
        Возвращает AgentPayload (V2).
        
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

            def _parse_and_validate(response):
                self.logger.info(f"📥 GigaChat response type: {type(response)}")
                self.logger.debug(f"📦 Full response: {str(response)[:500]}...")
                plan = self._parse_plan_from_response(response)
                self._validate_plan(plan)
                return plan

            plan = await self._call_gigachat_with_json_retry(
                messages=messages,
                parse_fn=_parse_and_validate,
                temperature=0.3,
                max_tokens=2000,
            )
            
            self.logger.info(f"✅ Plan created with {len(plan['steps'])} steps")
            
            # V2: Конвертируем dict-план в Plan модель
            plan_model = self._dict_to_plan(plan, user_request)
            
            return self._success_payload(plan=plan_model)
            
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Failed to parse plan JSON after retries: {e}")
            return self._format_error_response(
                f"Failed to parse plan from LLM response: {e}",
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
        
        Использует расширенный контекст (current_results из agent_results)
        для информированного перепланирования.
        См. docs/ADAPTIVE_PLANNING.md — "Передаёт ВСЕ накопленные результаты как контекст"
        """
        try:
            self._validate_task(task, ["original_plan", "reason"])
            
            original_plan = task["original_plan"]
            reason = task["reason"]
            failed_step = task.get("failed_step", "N/A (adaptive replanning)")
            suggested_steps = task.get("suggested_steps", [])
            validation_issues = task.get("validation_issues", [])
            # Изменение: используем current_results (сериализованные agent_results)
            # Передаются из Orchestrator._replan() — расширенный контекст после выполнения агентов
            current_results = task.get("current_results", [])
            
            self.logger.info(
                f"🔄 Replanning due to: {reason} "
                f"(accumulated results: {len(current_results)}, "
                f"suggested_steps: {len(suggested_steps)})"
            )
            
            # Формируем prompt для адаптации
            replan_prompt = f"""
ORIGINAL PLAN:
{json.dumps(original_plan, indent=2, ensure_ascii=False)}

FAILED STEP: {failed_step}
REASON: {reason}
"""

            # FIX: передаём INPUT DATA SCHEMA в replan-промпт, чтобы LLM знал
            # какие таблицы уже доступны как структурированные DataFrame.
            # Без этого планировщик может создать ненужный шаг structurizer
            # для "извлечения" таблицы, которая уже есть во входных данных.
            if context and context.get("input_data_preview"):
                input_preview = context["input_data_preview"]
                replan_prompt += "\nINPUT DATA SCHEMA (already loaded DataFrames — do NOT use structurizer for these):\n"
                for table_name, info in list(input_preview.items())[:2]:
                    columns = info.get("columns", [])
                    row_count = info.get("row_count", 0)
                    replan_prompt += f"  • Table '{table_name}': {len(columns)} columns, {row_count} rows\n"
                    replan_prompt += f"    Columns: {', '.join(columns[:10])}\n"
                replan_prompt += "\n"

            # Изменение: добавляем накопленные результаты агентов (расширенный контекст)
            # Это позволяет PlannerAgent учитывать что уже было сделано и найдено
            if current_results:
                replan_prompt += f"""

ACCUMULATED AGENT RESULTS (context from completed steps):
{json.dumps(current_results, indent=2, ensure_ascii=False)}

IMPORTANT: Use these results to understand what has already been accomplished.
Agents have expanded the context — consider their findings when creating the updated plan.
"""
            
            # Добавляем suggested_steps если есть (от ValidatorAgent)
            if suggested_steps:
                replan_prompt += f"""

RECOMMENDED STEPS (from ValidatorAgent):
{json.dumps(suggested_steps, indent=2, ensure_ascii=False)}

IMPORTANT: Use these EXACT steps in your plan. They are designed to fix the validation failure.
"""
            
            # Добавляем validation issues если есть
            if validation_issues:
                replan_prompt += f"""

VALIDATION ISSUES:
{json.dumps(validation_issues, indent=2, ensure_ascii=False)}
"""
            
            replan_prompt += """

Create an updated plan that addresses the failure. You can:
1. Use the recommended steps if provided (PREFERRED)
2. Modify parameters of the failed step
3. Add new intermediate steps
4. Use alternative agents or approaches
5. Skip problematic steps if not critical

Consider the ACCUMULATED AGENT RESULTS when deciding — agents may have already 
gathered data, extracted tables, or produced code that should be preserved or built upon.

Return updated plan in the same JSON format.
"""
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": replan_prompt}
            ]

            def _parse_and_validate_replan(response):
                plan = self._parse_plan_from_response(response)
                self._validate_plan(plan)
                return plan

            updated_plan = await self._call_gigachat_with_json_retry(
                messages=messages,
                parse_fn=_parse_and_validate_replan,
                temperature=0.5,
            )
            
            self.logger.info(f"✅ Plan updated with {len(updated_plan['steps'])} steps")
            
            # V2: Конвертируем dict-план в Plan модель
            plan_model = self._dict_to_plan(
                updated_plan,
                original_plan.get("user_request", "")
            )
            
            return self._success_payload(
                plan=plan_model,
                narrative_text=f"Adapted plan due to: {reason}"
            )
            
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
            
            return self._success_payload(
                narrative_text=message,
                metadata={"decision": decision, "step_id": step_id}
            )
            
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

        def _parse_decision(response):
            text = response if isinstance(response, str) else str(response)
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "decision": result.get("decision", "abort"),
                    "message": result.get("reason", error_msg)
                }
            raise ValueError("Could not extract JSON decision from AI response")

        return await self._call_gigachat_with_json_retry(
            messages=messages,
            parse_fn=_parse_decision,
            temperature=0.3,
        )
    
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
        
        # Существующий код трансформации (если редактируются существующие данные)
        if context and context.get("existing_code"):
            prompt_parts.append("\nEXISTING CODE:")
            prompt_parts.append("```python")
            prompt_parts.append(context["existing_code"])
            prompt_parts.append("```")
            prompt_parts.append("⚠️ User wants to modify or improve this existing transformation.")
        
        # История диалога (контекст предыдущих действий)
        if context and context.get("chat_history"):
            chat_history = context["chat_history"]
            if chat_history and len(chat_history) > 0:
                prompt_parts.append("\nCHAT HISTORY (full conversation):")
                # Показываем ВСЕ сообщения для полного контекста
                for msg in chat_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    # Длинные сообщения (>500 chars) обрезаем, чтобы не переполнить промпт
                    if len(content) > 500:
                        content = content[:500] + "..."
                    prompt_parts.append(f"  - {role}: {content}")
        
        # Входные данные (схема таблиц)
        if context and context.get("input_data_preview"):
            input_preview = context["input_data_preview"]
            prompt_parts.append("\nINPUT DATA SCHEMA:")
            for table_name, info in list(input_preview.items())[:2]:  # Максимум 2 таблицы в промпт
                columns = info.get("columns", [])
                row_count = info.get("row_count", 0)
                prompt_parts.append(f"  • Table '{table_name}': {len(columns)} columns, {row_count} rows")
                prompt_parts.append(f"    Columns: {', '.join(columns[:10])}")  # Первые 10 колонок
        
        # Изменение #1: board_data → board_context (см. docs/CONTEXT_ARCHITECTURE_PROPOSAL.md)
        if context and context.get("board_context"):
            prompt_parts.append("\nBOARD CONTEXT:")
            board_ctx = context["board_context"]
            # Передаём компактную версию — полный board_context слишком большой
            compact = {
                "nodes_count": len(board_ctx.get("content_nodes", [])),
                "content_nodes": [
                    {"id": n.get("id"), "name": n.get("name"), "type": n.get("type")}
                    for n in board_ctx.get("content_nodes", [])[:10]
                ],
            }
            prompt_parts.append(json.dumps(compact, indent=2, ensure_ascii=False))
        
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
        
        # Remove Python-style comments from JSON (GigaChat sometimes adds them)
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove # comments (but preserve # inside strings)
            # Simple approach: remove # and everything after if not inside quotes
            if '#' in line:
                # Check if # is inside a string
                in_string = False
                quote_char = None
                comment_pos = -1
                for i, char in enumerate(line):
                    if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                        if not in_string:
                            in_string = True
                            quote_char = char
                        elif char == quote_char:
                            in_string = False
                            quote_char = None
                    elif char == '#' and not in_string:
                        comment_pos = i
                        break
                if comment_pos >= 0:
                    line = line[:comment_pos].rstrip()
            cleaned_lines.append(line)
        content = '\n'.join(cleaned_lines)
        
        self.logger.info(f"📝 Content to parse: {content[:300]}...")
        
        try:
            # Парсим JSON
            plan = json.loads(content)
            self.logger.info(f"✅ Successfully parsed JSON plan with {len(plan.get('steps', []))} steps")
            return plan
        except json.JSONDecodeError as e:
            self.logger.warning(f"⚠️ JSON decode error (attempting repair): {e}")
            self.logger.debug(f"📋 Content before repair: {content}")
            
            # Пытаемся починить JSON
            repaired = self._repair_json(content)
            try:
                plan = json.loads(repaired)
                self.logger.info(f"✅ Successfully parsed REPAIRED JSON plan with {len(plan.get('steps', []))} steps")
                return plan
            except json.JSONDecodeError as e2:
                self.logger.error(f"❌ JSON decode error after repair: {e2}")
                self.logger.error(f"📋 Repaired content: {repaired}")
                raise
    
    def _repair_json(self, content: str) -> str:
        """
        Пытается починить типичные ошибки JSON от GigaChat:
        1. Пропущенная закрывающая } у последнего объекта в массиве перед ]
        2. Висячие запятые перед ] или }
        3. Лишний текст после основной JSON структуры
        4. Несбалансированные скобки
        """
        self.logger.info("🔧 Attempting JSON repair...")
        
        # Шаг 1: Найти основную JSON структуру (первый { до последнего })
        # GigaChat иногда добавляет текст после JSON
        first_brace = content.find('{')
        if first_brace < 0:
            return content
        
        # Пробуем найти правильный конец JSON: считаем скобки
        depth_curly = 0
        depth_square = 0
        in_string = False
        escape_next = False
        last_valid_pos = -1
        
        for i in range(first_brace, len(content)):
            char = content[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\' and in_string:
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char == '{':
                depth_curly += 1
            elif char == '}':
                depth_curly -= 1
            elif char == '[':
                depth_square += 1
            elif char == ']':
                depth_square -= 1
            
            if depth_curly == 0 and depth_square == 0:
                last_valid_pos = i
                break
        
        if last_valid_pos > 0:
            repaired = content[first_brace:last_valid_pos + 1]
        else:
            repaired = content[first_brace:]
        
        # Шаг 2: Починить пропущенные } перед ]
        # Паттерн: "value"\n  ] — нужна } перед ]
        # GigaChat часто пропускает } у последнего элемента массива
        repaired = re.sub(
            r'("estimated_time"\s*:\s*"[^"]*")\s*\n(\s*)\]',
            r'\1\n\2}\n\2]',
            repaired
        )
        
        # Более общий паттерн: строковое значение после двоеточия, потом ]
        # Ищем pattern: "key": "value" (без закрывающей }) перед ]
        repaired = re.sub(
            r'("[^"]+"\s*:\s*"[^"]*")\s*\n(\s*)\]',
            r'\1\n\2}\n\2]',
            repaired
        )
        
        # Паттерн: числовое значение перед ]
        repaired = re.sub(
            r'("[^"]+"\s*:\s*\d+)\s*\n(\s*)\]',
            r'\1\n\2}\n\2]',
            repaired
        )
        
        # Паттерн: массив-значение перед ] (например "depends_on": ["1", "2"])
        # GigaChat пропускает } у последнего объекта когда его последнее свойство — массив
        repaired = re.sub(
            r'("[^"]+"\s*:\s*\[[^\]]*\])\s*\n(\s*)\]',
            r'\1\n\2}\n\2]',
            repaired
        )
        
        # Паттерн: boolean/null значение перед ]
        repaired = re.sub(
            r'("[^"]+"\s*:\s*(?:true|false|null))\s*\n(\s*)\]',
            r'\1\n\2}\n\2]',
            repaired
        )
        
        # Шаг 3: Починить значения без кавычек (например: "key": 5_to_8)
        # GigaChat иногда возвращает идентификаторы без кавычек
        # Находим паттерн: "key": identifier (где identifier содержит буквы/подчеркивания)
        # НЕ трогаем: true, false, null (ключевые слова JSON)
        # НЕ трогаем: чистые числа (123, 45.6)
        # Исправляем: 5_to_8, my_value, some_id и т.п.
        repaired = re.sub(
            r'("[^"]+"\s*:\s*)(?!true\b|false\b|null\b|\d+\.?\d*\b)([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\1"\2"',
            repaired
        )
        
        # Шаг 4: Убрать висячие запятые
        # ,] → ]
        repaired = re.sub(r',\s*\]', ']', repaired)
        # ,} → }
        repaired = re.sub(r',\s*\}', '}', repaired)
        
        # Шаг 5: Проверить баланс скобок и добить недостающие
        open_curly = repaired.count('{') - repaired.count('}')
        open_square = repaired.count('[') - repaired.count(']')
        
        if open_curly > 0 or open_square > 0:
            self.logger.info(f"🔧 Balancing brackets: adding {open_curly} curly, {open_square} square")
            repaired = repaired.rstrip()
            # Убираем висячую запятую перед добавлением скобок
            repaired = repaired.rstrip(',')
            repaired += '}' * open_curly
            repaired += ']' * open_square
        
        # Шаг 6: Удалить лишние закрывающие скобки с конца
        # Может возникнуть когда Шаг 2 добавил недостающую },
        # но Шаг 1 уже включил компенсирующую лишнюю } от GigaChat
        open_curly = repaired.count('{') - repaired.count('}')
        open_square = repaired.count('[') - repaired.count(']')
        
        if open_curly < 0 or open_square < 0:
            self.logger.info(f"🔧 Stripping extra brackets: {-open_curly} curly, {-open_square} square")
            while open_curly < 0:
                pos = repaired.rfind('}')
                if pos >= 0:
                    repaired = repaired[:pos] + repaired[pos + 1:]
                    open_curly += 1
                else:
                    break
            while open_square < 0:
                pos = repaired.rfind(']')
                if pos >= 0:
                    repaired = repaired[:pos] + repaired[pos + 1:]
                    open_square += 1
                else:
                    break
        
        self.logger.info(f"🔧 Repaired JSON: {repaired[:300]}...")
        return repaired
    
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

    def _dict_to_plan(self, plan_dict: Dict[str, Any], user_request: str) -> Plan:
        """
        Конвертирует dict-план от LLM в Plan модель (V2).
        
        Обрабатывает различные форматы step_id и зависимостей.
        """
        steps = []
        for i, step in enumerate(plan_dict.get("steps", [])):
            steps.append(PlanStep(
                step_id=str(step.get("step_id", i + 1)),
                agent=step["agent"],
                task=step.get("task", {}),
                depends_on=[str(d) for d in step.get("depends_on", [])],
                estimated_time=step.get("estimated_time"),
            ))
        
        return Plan(
            plan_id=plan_dict.get("plan_id", ""),
            user_request=plan_dict.get("user_request", user_request),
            steps=steps,
            estimated_total_time=plan_dict.get("estimated_total_time"),
        )
