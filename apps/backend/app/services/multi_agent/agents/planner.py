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
from uuid import uuid4

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import AgentPayload, Plan, PlanStep
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
- В каждом task указывать:
  • **description** — полное техническое задание для агента (контекст, критерии, ограничения)
  • **summary** — короткая строка для UI прогресса (до ~120 символов, одна строка; например «Поиск в сети», «Анализ продаж»)
- Делегировать генерацию данных специализированным агентам
- Указывать зависимости между шагами (depends_on)

ПРАВИЛЬНЫЙ ПРИМЕР (только структура плана):
{
  "steps": [
    {
      "step_id": "1",
      "agent": "analyst",
      "task": {
        "description": "Проанализируй данные и предложи 10 вариантов трансформаций",
        "summary": "Анализ данных и идеи трансформаций"
      }
    },
    {
      "step_id": "2",
      "agent": "reporter",
      "task": {
        "description": "Сформируй текстовый ответ с рекомендациями",
        "summary": "Итоговый отчёт",
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

КРИТИЧЕСКОЕ ПРАВИЛО ИМЕНОВАНИЯ АГЕНТОВ:
- В поле `steps[].agent` используй ТОЛЬКО эти точные ключи:
  `context_filter`, `discovery`, `research`, `structurizer`, `analyst`,
  `transform_codex`, `widget_codex`, `reporter`, `validator`.
- НЕЛЬЗЯ использовать синонимы или вариации имён агентов:
  `researcher`, `analyzer`, `writer`, `critic`, `validator_agent`, `planner_agent` и т.п.
- Если сомневаешься — выбирай ближайший допустимый ключ из списка выше.
- План с агентом вне списка считается невалидным.

- **context_filter**: LLM-шаг построения и применения кросс-фильтра к контексту
  - Когда использовать: перед analyst, если запрос содержит конкретную сущность/срез
    (например "у Philips", "по бренду X", "только категория Y").
  - Входные параметры шага (task): 
    * `description`: текстовая цель фильтрации
    * `allow_auto_filter`: true/false (обычно true)
    * `filter_expression`: опционально, если можно сформулировать явно
    * `required_tables`: опционально, какие таблицы приоритетно оставить
  - Правило JSON-декларации: агент формирует FilterExpression JSON
    (`condition`/`and`/`or`) и передаёт его оркестратору для установки фильтра.
  - Выход: обновлённый working set для следующих шагов и фильтрованные таблицы.
  - Важно: это НЕ внешняя сеть и НЕ генерация кода; шаг исполняется локально в backend.

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
        "description": "Analyze dataset structure and identify business analysis opportunities",
        "summary": "Анализ структуры данных"
      }
    },
    {
      "agent": "reporter",
      "task": {
        "description": "Create text report with analysis recommendations",
        "summary": "Текстовый отчёт",
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
        "summary": "Поиск источников (Rust web)",
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
        "summary": "Загрузка страниц",
        "max_urls": 5
      },
      "depends_on": ["1"],
      "estimated_time": "10s"
    },
    {
      "step_id": "3",
      "agent": "structurizer",
      "task": {
        "description": "Extract structured comparison table of Rust frameworks with columns: name, github_stars, category, description",
        "summary": "Извлечение таблицы"
      },
      "depends_on": ["2"],
      "estimated_time": "5s"
    },
    {
      "step_id": "4",
      "agent": "analyst",
      "task": {
        "description": "Analyze Rust frameworks comparison data, identify trends and top picks",
        "summary": "Анализ данных"
      },
      "depends_on": ["3"],
      "estimated_time": "5s"
    },
    {
      "step_id": "5",
      "agent": "reporter",
      "task": {
        "description": "Create final report with Rust frameworks comparison",
        "summary": "Финальный отчёт",
        "widget_type": "text"
      },
      "depends_on": ["4"],
      "estimated_time": "5s"
    }
  ],
  "estimated_total_time": "28s"
}

**ПАРАМЕТРЫ ЗАДАЧ ДЛЯ КАЖДОГО АГЕНТА**:

Общее для **каждого** шага: в `task` всегда указывай `description` (полное ТЗ) и `summary` (коротко для UI).

**discovery**:
- `query` (обязательно): поисковый запрос
- `search_type`: "web" | "news" | "quick" (по умолчанию "web")
- `max_results`: 5-10 (по умолчанию 5)
- **Два шага discovery подряд** (разный охват выдачи): для статистики по региональным рынкам (РФ, ЕС и т.д.), рейтингов продаж, когда один запрос даёт узкую выдачу — добавь **два** шага `discovery` с **разными** `query` (например: запрос на EN + запрос на RU с «Автостат» / «продажи Россия»; или общий + узкоспециализированный). Зависимости: шаг 2 discovery → `depends_on`: ["1"]. Затем **один** `research` с `max_urls`: 8–10 и `depends_on`: на id **последнего** discovery — ResearchAgent объединит URL из всех предыдущих discovery. Не повторяй одинаковый `query` в двух шагах.

**research**:
- Для API: `url`, `method` (GET/POST), `headers`, `params`
- Для веб: `max_urls` (URL из всех предыдущих discovery в `agent_results`; при двух discovery увеличь до 8–10)
- Для БД: `query` (SQL SELECT), `database`

**structurizer**:
- `description` (обязательно): что нужно извлечь
- Опционально указывай ожидаемую структуру: "columns: name, price, rating"
- Если в источниках есть **два разных рейтинга** (например «топ моделей по штукам» и «топ брендов по продажам»), в `description` **явно раздели**: две таблицы или два прохода — **не смешивай** строки «модель + продажи модели» с «бренд + продажи бренда» в одной таблице без пометки типа строки

**analyst**:
- `description` (обязательно): что нужно проанализировать
- `summary` (обязательно): короткий заголовок для прогресса UI
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
- `depends_on`: **всегда** укажи id шага **analyst** (если есть в плане), иначе **structurizer**, иначе **research**. Пустой `[]` для reporter недопустим при наличии этих шагов — оркестратор всё равно нормализует, но план должен быть корректным

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
        system_prompt: Optional[str] = None,
        llm_router: Optional[Any] = None,
    ):
        super().__init__(
            agent_name="planner",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        self.llm_router = llm_router
        
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
        elif task_type == "expand_step":
            return await self._expand_step(task, context)
        elif task_type == "revise_remaining":
            return await self._revise_remaining(task, context)
        elif task_type == "evaluate_result":
            return await self._evaluate_result(task, context)
        else:
            return self._format_error_response(
                f"Unknown task type: {task_type}",
                suggestions=["Supported types: create_plan, replan, expand_step, revise_remaining, evaluate_result"]
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
                # Нормализуем step_id и depends_on сразу в Planner,
                # чтобы оркестратор и клиенты всегда получали "чистый" план.
                plan = self._normalize_plan_steps(plan)
                return plan

            is_transform = context and (
                context.get("mode") == "transformation"
                or context.get("controller") == "transformation"
            )
            plan_max_tokens = 4500 if is_transform else 2000
            if not is_transform and len(user_request) > 4000:
                plan_max_tokens = 3800

            try:
                plan = await self._call_gigachat_with_json_retry(
                    messages=messages,
                    parse_fn=_parse_and_validate,
                    context=context,
                    temperature=0.3,
                    max_tokens=plan_max_tokens,
                )
            except Exception as plan_err:
                if is_transform:
                    self.logger.warning(
                        "Planner create_plan failed (%s), using transformation fallback plan",
                        plan_err,
                    )
                    plan = self._build_transformation_fallback_plan(user_request)
                    plan = self._normalize_plan_steps(plan)
                else:
                    raise
            plan["user_request"] = user_request[:3000] if len(user_request) > 3000 else user_request
            
            self.logger.info(f"✅ Plan created with {len(plan['steps'])} steps")

            plan = self._sanitize_suggestions_plan(plan, context, user_request)
            plan = self._ensure_widget_codex_in_plan(plan, context, user_request)
            plan = self._ensure_transform_codex_in_plan(plan, context, user_request)
            plan = self._constrain_transformation_plan_to_local_data(plan, context, user_request)
            plan = self._inject_context_filter_step(plan, context, user_request)
            if plan.get("steps"):
                self.logger.info(
                    f"✅ Plan after codex guards: {len(plan['steps'])} steps"
                )

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
            if context and isinstance(context.get("pipeline_memory"), dict):
                pm = context.get("pipeline_memory") or {}
                replan_prompt += f"""
PIPELINE MEMORY (prioritize over long raw history):
{json.dumps({
    "goal": pm.get("goal"),
    "constraints": (pm.get("constraints") or [])[:6],
    "decisions": (pm.get("decisions") or [])[:6],
    "open_questions": (pm.get("open_questions") or [])[:6],
    "evidence": (pm.get("evidence") or [])[:6],
}, ensure_ascii=False, indent=2)}
"""

            # FIX: передаём INPUT DATA SCHEMA в replan-промпт, чтобы LLM знал
            # какие таблицы уже доступны как структурированные DataFrame.
            # Без этого планировщик может создать ненужный шаг structurizer
            # для "извлечения" таблицы, которая уже есть во входных данных.
            if context and context.get("input_data_preview"):
                input_preview = context["input_data_preview"]
                replan_prompt += "\nINPUT DATA SCHEMA (already loaded DataFrames — do NOT use structurizer for these):\n"
                for table_key, info in list(input_preview.items())[:2]:
                    table_name = str(info.get("table_name") or table_key)
                    node_name = str(info.get("node_name") or "node")
                    columns = info.get("columns", [])
                    row_count = info.get("row_count", 0)
                    replan_prompt += f"  • Table '{node_name}.{table_name}': {len(columns)} columns, {row_count} rows\n"
                    col_names = self._column_names_for_prompt(columns)
                    replan_prompt += f"    Columns: {', '.join(col_names[:10])}\n"
                replan_prompt += "\n"

            if context and context.get("catalog_data_preview"):
                catalog_preview = context["catalog_data_preview"]
                replan_prompt += "CATALOG DATA SCHEMA (full board, tiny samples):\n"
                for table_key, info in list(catalog_preview.items())[:5]:
                    table_name = str(info.get("table_name") or table_key)
                    node_name = str(info.get("node_name") or "node")
                    row_count = info.get("row_count", 0)
                    replan_prompt += f"  • {node_name}.{table_name} ({row_count} rows)\n"
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
Use only valid agent keys:
["context_filter","discovery","research","structurizer","analyst","transform_codex","widget_codex","reporter","validator"].
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
                context=context,
                temperature=0.5,
            )
            
            self.logger.info(f"✅ Plan updated with {len(updated_plan['steps'])} steps")
            
            # Нормализуем step_id и depends_on и для replanned-плана,
            # чтобы не протаскивать "грязные" идентификаторы дальше по пайплайну.
            updated_plan = self._normalize_plan_steps(updated_plan)
            updated_plan = self._inject_context_filter_step(
                updated_plan,
                context,
                context.get("user_request") if context else "",
            )

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

    async def _expand_step(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentPayload:
        """
        Проверка атомарности шага. Возвращает либо {atomic: true}, либо {atomic: false, sub_steps: [...]}.
        См. docs/PLANNING_DECOMPOSITION_STRATEGY.md.
        """
        try:
            step = task.get("step")
            if not step or "agent" not in step or "task" not in step:
                return self._format_error_response(
                    "expand_step requires task.step with agent and task",
                    suggestions=["Pass step: {agent, task, step_id?, depends_on?}"],
                )
            user_request = (context or {}).get("user_request", "")
            prompt = f"""Дан один шаг плана выполнения. По правилам атомарности определи: шаг атомарен?

ПРАВИЛА АТОМАРНОСТИ:
- discovery: один шаг = один поисковый запрос (один query). Несколько запросов → разбей на несколько шагов.
- research: один шаг = загрузка из одного discovery (max_urls). Не объединяй несколько источников в один шаг.
- structurizer: один шаг = извлечение структуры из одного блока/типа контента.
- analyst: один шаг = анализ одной таблицы или одного аспекта.
- reporter: обычно один шаг в конце.
- transform_codex / widget_codex: один шаг = одна трансформация / один виджет.

ШАГ ДЛЯ ПРОВЕРКИ:
{json.dumps(step, ensure_ascii=False, indent=2)}

Исходный запрос пользователя (контекст): {user_request[:300] if user_request else "—"}

Ответь ТОЛЬКО валидным JSON, без текста до или после:
- Если шаг атомарен: {{"atomic": true}}
- Если шаг нужно разбить: {{"atomic": false, "sub_steps": [{{"step_id": "1", "agent": "...", "task": {{...}}, "depends_on": []}}, ...]}}
Подшаги в том же формате (agent, task, step_id, depends_on)."""
            messages = [
                {"role": "system", "content": "Ты планировщик. Определяешь атомарность шага и при необходимости разбиваешь на подшаги. Отвечай только JSON."},
                {"role": "user", "content": prompt},
            ]

            def _parse(response: Any) -> Dict[str, Any]:
                text = response if isinstance(response, str) else str(response)
                json_text = self._extract_json_object_text(text)
                try:
                    data = json.loads(json_text)
                except json.JSONDecodeError:
                    data = json.loads(self._repair_json(json_text))
                if "atomic" not in data:
                    raise ValueError("Response must contain 'atomic'")
                if data.get("atomic") is False and "sub_steps" in data:
                    subs = data["sub_steps"]
                    if not isinstance(subs, list) or len(subs) == 0:
                        raise ValueError("sub_steps must be non-empty list when atomic is false")
                    for i, s in enumerate(subs):
                        if not isinstance(s, dict) or "agent" not in s or "task" not in s:
                            raise ValueError(f"sub_step[{i}] must have agent and task")
                return data

            result = await self._call_gigachat_with_json_retry(
                messages=messages,
                parse_fn=_parse,
                context=context,
                temperature=0.2,
                max_tokens=1500,
            )
            atomic = result.get("atomic", True)
            sub_steps = result.get("sub_steps") if not atomic else None
            return self._success_payload(
                metadata={"expand_step_result": {"atomic": atomic, "sub_steps": sub_steps}},
            )
        except Exception as e:
            self.logger.error(f"Error in expand_step: {e}", exc_info=True)
            return self._format_error_response(str(e))

    async def _revise_remaining(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentPayload:
        """
        Пересмотр оставшейся части плана с учётом выполненных шагов и контекста (в т.ч. инсайтов).
        См. docs/PLANNING_DECOMPOSITION_STRATEGY.md.
        """
        try:
            user_request = task.get("user_request", (context or {}).get("user_request", ""))
            completed_steps = task.get("completed_steps", [])
            remaining_steps = task.get("remaining_steps", [])
            results_summary = task.get("results_summary", [])
            last_error = task.get("last_error")
            failed_agent = task.get("failed_agent")
            last_step_suboptimal = task.get("last_step_suboptimal")
            suboptimal_reason = task.get("suboptimal_reason")

            prompt = f"""Исходный запрос пользователя: {user_request}

УЖЕ ВЫПОЛНЕНЫ (кратко):
{json.dumps(completed_steps, ensure_ascii=False, indent=2)}

РЕЗУЛЬТАТЫ ВЫПОЛНЕННЫХ ШАГОВ (контекст):
{json.dumps(results_summary, ensure_ascii=False, indent=2)[:4000]}
"""
            if context and isinstance(context.get("pipeline_memory"), dict):
                pm = context.get("pipeline_memory") or {}
                prompt += f"""
PIPELINE MEMORY (high-priority context):
{json.dumps({
    "goal": pm.get("goal"),
    "constraints": (pm.get("constraints") or [])[:6],
    "decisions": (pm.get("decisions") or [])[:6],
    "open_questions": (pm.get("open_questions") or [])[:6],
    "evidence": (pm.get("evidence") or [])[:6],
}, ensure_ascii=False, indent=2)}
"""
            if last_error or failed_agent:
                prompt += f"""
ПОСЛЕДНЯЯ ОШИБКА: агент {failed_agent or '?'} — {last_error or 'N/A'}
Учти при пересмотре: можно пропустить проблемный шаг или заменить его.
"""
            if last_step_suboptimal and suboptimal_reason:
                prompt += f"""
ПОСЛЕДНИЙ ШАГ НЕ ДАЛ ПОЛЕЗНОГО РЕЗУЛЬТАТА: агент {failed_agent or '?'} — {suboptimal_reason}
Учти при пересмотре: можно добавить повторный шаг (retry) для этого агента с уточнённой задачей или заменить на альтернативу.
"""
            next_step_num = len(completed_steps) + 1
            completed_agents = {s.get("agent") for s in completed_steps if s.get("agent")}
            remaining_agents = {s.get("agent") for s in remaining_steps if s.get("agent")}
            structurizer_or_reporter_in_remaining = "structurizer" in remaining_agents or "reporter" in remaining_agents
            structurizer_reporter_not_done = structurizer_or_reporter_in_remaining and (
                "structurizer" not in completed_agents or "reporter" not in completed_agents
            )
            prompt += f"""
ТЕКУЩАЯ ОСТАВШАЯСЬ ЧАСТЬ ПЛАНА:
{json.dumps(remaining_steps, ensure_ascii=False, indent=2)}
"""
            if structurizer_reporter_not_done:
                prompt += """
ВАЖНО: В выполненных шагах ещё не было structurizer и/или reporter — структурированная таблица и итоговый отчёт не созданы. Обязательно сохрани шаги structurizer и reporter в remaining_steps (не удаляй их).

"""
            prompt += f"""
Пересмотри оставшуюся часть плана с учётом контекста и инсайтов.

Можно:
- добавить шаги (например discovery/research по инсайтам analyst),
- убрать лишнее или изменить порядок,
- при ошибке — пропустить или заменить проблемный шаг.

Если данных достаточно только для итогового отчёта — верни в remaining_steps сначала шаг reporter, при необходимости за ним validator. Не возвращай один лишь validator без reporter: отчёт должен сформировать reporter.

Важно: не удаляй шаги structurizer и reporter из остатка, если в запросе пользователя явно нужны таблица, сравнение или итоговый вывод, а эти агенты ещё не выполнялись (их нет в списке выполненных). Сохраняй их в remaining_steps до выполнения. Если в остатке есть structurizer — перед ним должен быть шаг research: structurizer извлекает таблицы из полных текстов страниц, которые загружает research; без research у structurizer не будет сырого контента.

Если из результатов discovery/research и работы structurizer/analyst видно, что:
- для части источников (Habr, Wikipedia и т.п.) **нет прямых числовых рейтингов**, а есть только текстовые описания, обзоры, перечисления;
- несколько запусков structurizer подряд извлекали только сущности/metadata без таблиц с рейтингами;
то **не добавляй новые волны discovery/research со схожими запросами** и **не плодись новый structurizer по тем же источникам**. Вместо этого:
- сократи remaining_steps до минимально достаточной цепочки для ответа (analyst → reporter или сразу reporter),
- ориентируй reporter на построение *качественной сравнительной таблицы* (например, столбцы «Популярность/распространённость», «Скорость развития», «Комьюнити», «Типичные кейсы») и текстового вывода на основе уже собранных текстовых материалов.

Не генерируй очень длинный хвост из повторяющихся discovery/research по тем же фреймворкам и площадкам. Если ты видишь в results_summary несколько однотипных поисков без новых чисел, считай, что данных мало, и переходи к сворачиванию плана и финальному отчёту.

Используй простые step_id: {next_step_num}, {next_step_num + 1}, ... (по порядку).

Ответь ТОЛЬКО валидным JSON: {{"remaining_steps": [{{"step_id": \"...\", \"agent\": \"...\", \"task\": {{...}}, \"depends_on\": []}}, ...]}}
Каждый шаг: step_id, agent, task, depends_on (массив)."""

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты планировщик. Пересматриваешь оставшуюся часть плана с учётом выполненных шагов и контекста. "
                        "Учитывай findings и narrative analyst. Верни только JSON с ключом remaining_steps. "
                        "При сокращении до минимума: сначала reporter, затем при необходимости validator — не возвращай один лишь validator без reporter. "
                        "Не удаляй structurizer и reporter из остатка, если пользователь запросил таблицу/сравнение/вывод и эти шаги ещё не выполнены. "
                        "Перед structurizer сохраняй шаг research (structurizer нуждается в полных текстах страниц от research). "
                        "Если несколько волн discovery/research и structurizer уже не дали числовых рейтингов и таблиц, "
                        "не добавляй новые похожие discovery/research; вместо этого сворачивай план к analyst/reporter и проси reporter построить "
                        "сравнительную таблицу и вывод на основе текстовых материалов."
                    ),
                },
                {"role": "user", "content": prompt},
            ]

            def _parse(response: Any) -> Dict[str, Any]:
                text = response if isinstance(response, str) else str(response)
                json_text = self._extract_json_object_text(text)
                try:
                    data = json.loads(json_text)
                except json.JSONDecodeError:
                    data = json.loads(self._repair_json(json_text))
                if "remaining_steps" not in data:
                    raise ValueError("Response must contain 'remaining_steps'")
                steps = data["remaining_steps"]
                if not isinstance(steps, list):
                    steps = []
                for i, s in enumerate(steps):
                    if not isinstance(s, dict) or "agent" not in s or "task" not in s:
                        raise ValueError(f"remaining_steps[{i}] must have agent and task")
                return {"remaining_steps": steps}

            result = await self._call_gigachat_with_json_retry(
                messages=messages,
                parse_fn=_parse,
                context=context,
                temperature=0.4,
                max_tokens=2000,
            )
            return self._success_payload(
                metadata={"remaining_steps": result["remaining_steps"]},
            )
        except Exception as e:
            self.logger.error(f"Error in revise_remaining: {e}", exc_info=True)
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
            context=context,
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
        # Длинный запрос (трансформация) в JSON-плане модель часто копирует целиком → битый JSON / обрез по токенам
        ur_prompt = user_request
        if len(ur_prompt) > 1800:
            ur_prompt = (
                user_request[:1800]
                + "\n\n[Дальше текст запроса обрезан в промпте планировщика; полная формулировка передаётся агентам из контекста оркестратора. В ответе НЕ копируй этот блок в поле user_request.]"
            )
        prompt_parts = [
            f"USER REQUEST:\n{ur_prompt}",
            "",
            "При формировании JSON-плана поле \"user_request\" — не более 160 символов, одна строка (краткое название задачи).",
            "НЕ вставляй в JSON списки таблиц, требования к коду и весь USER REQUEST — это ломает JSON.",
            "",
        ]
        from app.services.multi_agent.tabular_tool_contract import (
            planner_task_summary_hint_block,
            planner_tools_hint_block,
        )

        prompt_parts.append(planner_task_summary_hint_block())

        if context and isinstance(context.get("pipeline_memory"), dict):
            pm = context.get("pipeline_memory") or {}
            compact_pm = {
                "goal": pm.get("goal"),
                "constraints": (pm.get("constraints") or [])[:6],
                "decisions": (pm.get("decisions") or [])[:6],
                "open_questions": (pm.get("open_questions") or [])[:6],
                "evidence": (pm.get("evidence") or [])[:6],
            }
            prompt_parts.append("PIPELINE MEMORY:")
            prompt_parts.append(json.dumps(compact_pm, ensure_ascii=False, default=str))
            prompt_parts.append("")
        
        if board_id:
            prompt_parts.append(f"BOARD ID: {board_id}")
        
        if selected_node_ids:
            prompt_parts.append(f"SELECTED NODES: {', '.join(selected_node_ids)}")
        if context and isinstance(context.get("transformation_scope"), dict):
            prompt_parts.append("\nTRANSFORMATION SCOPE:")
            prompt_parts.append(
                json.dumps(context.get("transformation_scope"), ensure_ascii=False)
            )
        
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
            for table_key, info in list(input_preview.items())[:2]:  # Максимум 2 таблицы в промпт
                table_name = str(info.get("table_name") or table_key)
                node_name = str(info.get("node_name") or "node")
                columns = info.get("columns", [])
                row_count = info.get("row_count", 0)
                prompt_parts.append(f"  • Table '{node_name}.{table_name}': {len(columns)} columns, {row_count} rows")
                col_names = self._column_names_for_prompt(columns)
                prompt_parts.append(f"    Columns: {', '.join(col_names[:10])}")  # Первые 10 колонок

        if context and context.get("catalog_data_preview"):
            catalog_preview = context["catalog_data_preview"]
            prompt_parts.append("\nCATALOG DATA SCHEMA (all board tables, tiny sample):")
            for table_key, info in list(catalog_preview.items())[:5]:
                table_name = str(info.get("table_name") or table_key)
                node_name = str(info.get("node_name") or "node")
                row_count = info.get("row_count", 0)
                prompt_parts.append(f"  • {node_name}.{table_name}: {row_count} rows")
        
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

        # Специализированные подсказки для контроллеров-подсказок:
        # transform_suggestions / widget_suggestions не должны запускать
        # тяжёлый research‑pipeline — данные уже есть в INPUT DATA SCHEMA.
        controller = context.get("controller") if context else None
        mode = context.get("mode") if context else None
        is_suggestions_controller = controller in {"transform_suggestions", "widget_suggestions"}

        if is_suggestions_controller:
            prompt_parts.extend(
                [
                    "",
                    "You are building a plan for a *suggestions controller*.",
                    "IMPORTANT:",
                    "- Do NOT call discovery / research / structurizer here: all necessary data",
                    "  is already provided in INPUT DATA SCHEMA and controller context.",
                    "- The goal is to run a LIGHT pipeline that analyzes existing data and",
                    "  produces recommendations/insights, not to fetch or extract new data.",
                    "",
                    "Preferred pipeline shape:",
                    "- analyst: analyze available structured data and generate recommendations",
                    "- reporter: turn analyst findings into a compact text answer for UI",
                    "",
                    "Plan constraints:",
                    "- Do NOT add discovery, research or structurizer steps.",
                    "- Do NOT add transform_codex, widget_codex or any codex steps — suggestions",
                    "  controllers only need analyst findings + reporter text, not executable code.",
                    "- Keep the number of steps small (typically 2–3).",
                ]
            )
        elif controller == "widget" or mode == "widget":
            prompt_parts.extend(
                [
                    "",
                    "CONTROLLER: WidgetController — пользователь ждёт **готовый HTML/JS виджет**.",
                    "Обязательно:",
                    "- Один или несколько шагов **analyst** (подготовка метрик/таблиц из уже загруженных данных),",
                    "  при необходимости разные аспекты — отдельные шаги analyst.",
                    "- После всех analyst ОБЯЗАТЕЛЬНО шаг **widget_codex** — единственный агент, который",
                    "  генерирует код виджета (KPI-карточки, графики, таблицы).",
                    "- Завершающий шаг **reporter** (widget_type: text) — краткое описание для пользователя.",
                    "",
                    "ЗАПРЕЩЕНО заканчивать план только analyst без widget_codex — иначе виджет не будет создан.",
                    "НЕ используй transform_codex для виджетов.",
                ]
            )
        elif controller == "transformation" or mode == "transformation":
            prompt_parts.extend(
                [
                    "",
                    "CONTROLLER: TransformController — пользователь ждёт **готовый Python/pandas-код трансформации**.",
                    "Источник данных по умолчанию: существующие таблицы выбранных ContentNode (локальные данные доски).",
                    "Обязательно:",
                    "- При необходимости шаги **structurizer** / **analyst** (данные уже в INPUT DATA SCHEMA —",
                    "  structurizer только если нужно доформатировать; часто достаточно analyst + transform_codex).",
                    "- После подготовки данных ОБЯЗАТЕЛЬНО шаг **transform_codex** — единственный агент, который",
                    "  генерирует исполняемый код трансформации (df → df_result).",
                    "- Завершающий шаг **reporter** (widget_type: text) — краткое описание результата.",
                    "",
                    "По умолчанию НЕ добавляй discovery/research: это веб-пайплайн, он не нужен для трансформации",
                    "локальных таблиц ContentNode.",
                    "Добавляй discovery/research только если пользователь ЯВНО просит внешние/интернет-данные.",
                    "",
                    "ЗАПРЕЩЕНО заканчивать план только analyst/structurizer без transform_codex — иначе кода не будет.",
                    "НЕ используй widget_codex для трансформаций данных.",
                    "В JSON: \"user_request\" — краткая метка (≤160 символов); шаги держи компактными.",
                ]
            )
        else:
            prompt_parts.extend(
                [
                    "",
                    "Create a detailed execution plan with steps delegated to appropriate agents.",
                    "Return the plan as a valid JSON object following the specified format.",
                    "Think step-by-step about what needs to be done and which agent is best suited for each task.",
                ]
            )

        if context:
            hint = planner_tools_hint_block(context)
            if hint:
                prompt_parts.append(hint)

        return "\n".join(prompt_parts)

    @staticmethod
    def _column_names_for_prompt(columns: Any) -> List[str]:
        """Normalize columns to display names for prompt rendering."""
        if not isinstance(columns, list):
            return []
        names: List[str] = []
        for col in columns:
            if isinstance(col, dict):
                names.append(str(col.get("name", "column")))
            else:
                names.append(str(col))
        return names
    
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
        
        # Нормализуем ответ до JSON-объекта (с учётом markdown/code-fence).
        content = self._extract_json_object_text(content)
        
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

    @staticmethod
    def _extract_json_object_text(text: str) -> str:
        """
        Извлекает первую валидную JSON-область-объект из произвольного текста LLM.

        Поддерживает:
        - markdown code fences ```json ... ```
        - префиксы/суффиксы вокруг JSON
        - поиск парных фигурных скобок с учётом строк/экранирования
        """
        content = (text or "").strip()
        if not content:
            raise ValueError("Empty response from GigaChat")

        # 1) Приоритет: JSON внутри code fence (```json ...``` / ``` ... ```)
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content, flags=re.IGNORECASE)
        if fence_match:
            fenced = fence_match.group(1).strip()
            if fenced:
                content = fenced

        # 2) Найти первую область {...} с балансом скобок
        start = content.find("{")
        if start < 0:
            raise ValueError("No JSON object in response")

        depth = 0
        in_string = False
        escape_next = False
        end = -1

        for i in range(start, len(content)):
            ch = content[i]
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end < 0:
            # Возвращаем до конца строки; дальше _repair_json попробует восстановить.
            return content[start:].strip()

        return content[start : end + 1].strip()
    
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
            agent_name = str(step.get("agent") or "").strip().lower()
            if agent_name == "planner":
                raise ValueError(
                    "Planner cannot be an execution step in plan; "
                    "use Planner only for create_plan/replan/expand/revise control flow"
                )

    def _build_transformation_fallback_plan(self, user_request: str) -> Dict[str, Any]:
        """
        Если LLM вернул битый JSON (часто из‑за копирования всего промпта в user_request
        и обрезки ответа), выполняем типовой план трансформации.
        """
        short = (user_request.replace("\n", " ").strip()[:160] or "transformation")
        codex_desc = user_request.strip()[:8000]
        return {
            "plan_id": str(uuid4()),
            "user_request": short,
            "steps": [
                {
                    "agent": "analyst",
                    "task": {
                        "description": (
                            "Проверь схему входных таблиц и релевантность колонок запросу; "
                            "кратко зафиксируй findings (без генерации Python-кода)."
                        ),
                        "summary": "Проверка схемы данных",
                    },
                    "depends_on": [],
                },
                {
                    "agent": "transform_codex",
                    "task": {
                        "description": codex_desc,
                        "summary": "Генерация кода трансформации",
                        "purpose": "transformation",
                    },
                    "depends_on": ["1"],
                },
                {
                    "agent": "reporter",
                    "task": {
                        "description": "Кратко опиши результат трансформации для пользователя.",
                        "summary": "Итоговое описание",
                        "widget_type": "text",
                    },
                    "depends_on": ["2"],
                },
            ],
        }

    def _sanitize_suggestions_plan(
        self,
        plan: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        user_request: str,
    ) -> Dict[str, Any]:
        """
        transform_suggestions / widget_suggestions: не вызывать transform_codex / widget_codex.
        Удаляем такие шаги, если модель их всё же вернула.
        """
        ctrl = (context or {}).get("controller")
        if ctrl not in ("transform_suggestions", "widget_suggestions"):
            return plan
        steps_in = plan.get("steps") or []
        banned = frozenset({"transform_codex", "widget_codex"})
        filtered: List[Dict[str, Any]] = []
        removed = 0
        for s in steps_in:
            if not isinstance(s, dict):
                continue
            if s.get("agent") in banned:
                removed += 1
                continue
            filtered.append(dict(s))
        if removed:
            self.logger.info(
                "Removed %s codex step(s) from suggestions plan (controller=%s)",
                removed,
                ctrl,
            )
        if not filtered:
            desc = (user_request or "").strip()[:4000] or "Проанализируй данные и дай рекомендации."
            filtered = [
                {
                    "agent": "analyst",
                    "task": {
                        "description": desc,
                        "summary": "Анализ и рекомендации",
                    },
                    "depends_on": [],
                },
                {
                    "agent": "reporter",
                    "task": {
                        "description": "Сформулируй краткие рекомендации для UI.",
                        "summary": "Текст для UI",
                        "widget_type": "text",
                    },
                    "depends_on": [],
                },
            ]
            self.logger.warning(
                "Suggestions plan had only codex steps; fallback to analyst → reporter"
            )
        out = dict(plan)
        out["steps"] = filtered
        return self._normalize_plan_steps(out)

    def _ensure_widget_codex_in_plan(
        self,
        plan: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        user_request: str,
    ) -> Dict[str, Any]:
        """
        WidgetController требует widget_codex; LLM иногда оставляет только цепочку analyst.
        Добавляем widget_codex → reporter, если их нет (см. orchestrator revise_remaining).
        """
        if not context:
            return plan
        if context.get("controller") != "widget" and context.get("mode") != "widget":
            return plan
        steps_in = plan.get("steps") or []
        if not steps_in:
            return plan
        steps: List[Dict[str, Any]] = [
            dict(s) if isinstance(s, dict) else {} for s in steps_in
        ]
        if any(s.get("agent") == "widget_codex" for s in steps):
            self.logger.debug("_ensure_widget_codex_in_plan: widget_codex already present")
            return plan
        if any(s.get("agent") == "transform_codex" for s in steps):
            self.logger.debug("_ensure_widget_codex_in_plan: transform_codex present, skip")
            return plan

        agents_before = [s.get("agent") for s in steps]
        while steps and steps[-1].get("agent") == "reporter":
            steps.pop()

        if not steps:
            return plan

        n = len(steps)
        last_dep = str(n)
        codex_task = (user_request or "").strip()[:4000] or (
            "Сгенерируй HTML/JS виджет по данным и запросу пользователя."
        )
        steps.append(
            {
                "agent": "widget_codex",
                "task": {
                    "description": codex_task,
                    "summary": "Генерация HTML/JS виджета",
                },
                "depends_on": [last_dep],
            }
        )
        steps.append(
            {
                "agent": "reporter",
                "task": {
                    "description": "Кратко опиши итог виджета для пользователя.",
                    "summary": "Описание виджета",
                    "widget_type": "text",
                },
                "depends_on": [],
            }
        )
        out = dict(plan)
        out["steps"] = steps
        agents_after = [s.get("agent") for s in steps]
        self.logger.info(
            "🛡️ _ensure_widget_codex_in_plan: injected widget_codex+reporter "
            f"({agents_before} → {agents_after})"
        )
        return self._normalize_plan_steps(out)

    def _ensure_transform_codex_in_plan(
        self,
        plan: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        user_request: str,
    ) -> Dict[str, Any]:
        """
        TransformController требует transform_codex; иначе пайплайн не выдаёт код.
        """
        if not context:
            return plan
        if context.get("controller") != "transformation" and context.get(
            "mode"
        ) != "transformation":
            return plan
        steps_in = plan.get("steps") or []
        if not steps_in:
            return plan
        steps: List[Dict[str, Any]] = [
            dict(s) if isinstance(s, dict) else {} for s in steps_in
        ]
        if any(s.get("agent") == "transform_codex" for s in steps):
            return plan
        if any(s.get("agent") == "widget_codex" for s in steps):
            return plan

        while steps and steps[-1].get("agent") == "reporter":
            steps.pop()

        if not steps:
            return plan

        n = len(steps)
        last_dep = str(n)
        codex_task = (user_request or "").strip()[:4000] or (
            "Сгенерируй Python/pandas-код трансформации по запросу и входным таблицам."
        )
        steps.append(
            {
                "agent": "transform_codex",
                "task": {"description": codex_task},
                "depends_on": [last_dep],
            }
        )
        steps.append(
            {
                "agent": "reporter",
                "task": {
                    "description": "Кратко опиши результат трансформации для пользователя.",
                    "widget_type": "text",
                },
                "depends_on": [],
            }
        )
        out = dict(plan)
        out["steps"] = steps
        return self._normalize_plan_steps(out)

    def _normalize_plan_steps(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализует step_id и depends_on внутри плана.

        Цели:
        - step_id → последовательные строки "1", "2", ..., без суффиксов вроде "11a";
        - depends_on → ссылки только на существующие шаги, также в виде строк;
        - убираем самозависимости и дубликаты в depends_on.

        Логика:
        - В первом проходе строим маппинг "старый числовой id" → "новый последовательный id".
          Берём только начальную числовую часть из step_id / depends_on (например "11a" → "11").
        - Во втором проходе переписываем depends_on с учётом этого маппинга.
        - Дополнительно чиним research‑pipeline: если в плане есть structurizer,
          он должен зависеть от ближайшего предыдущего research, а не от discovery.
        - Шаг **reporter**: если `depends_on` пуст или неверен — привязка к ближайшему
          предшествующему analyst → иначе structurizer → research → discovery → …
        """
        steps = plan.get("steps")
        if not isinstance(steps, list) or not steps:
            return plan

        id_map: Dict[str, str] = {}
        normalized_steps: List[Dict[str, Any]] = []
        # Для некоторых агентов (discovery, research, structurizer) устраняем
        # дубликаты шагов с одинаковой задачей. Храним маппинг
        # (agent, dedupe_key) → первый нормализованный step_id.
        dedupe_seen: Dict[tuple[str, str], str] = {}
        # Жёсткий лимит на количество structurizer‑шагов в одном плане:
        # чаще всего достаточно 1–2 проходов по одному и тому же контенту.
        max_structurizer_steps = 2
        structurizer_count = 0
        last_structurizer_id: Optional[str] = None

        # Первый проход: нормализуем сами step_id и строим маппинг.
        for idx, raw_step in enumerate(steps, start=1):
            step = dict(raw_step) if isinstance(raw_step, dict) else {"agent": None, "task": {}}

            raw_step_id = str(step.get("step_id", idx))
            # Берём только ведущую числовую часть, если она есть.
            m = re.match(r"(\d+)", raw_step_id)
            base_id = m.group(1) if m else raw_step_id

            agent = step.get("agent")
            task = step.get("task") or {}

            # Уникальные ключи для отдельных агентов, чтобы не плодить
            # одинаковые шаги:
            # - discovery: по query/description;
            # - research: по description/type/max_urls;
            # - structurizer: по description.
            dedupe_key: Optional[tuple[str, str]] = None
            if agent == "discovery":
                query = task.get("query") or task.get("description") or ""
                if isinstance(query, str) and query.strip():
                    dedupe_key = ("discovery", query.strip().lower())
            elif agent == "research":
                desc = (task.get("description") or "").strip().lower()
                r_type = (task.get("type") or "").strip().lower()
                max_urls = str(task.get("max_urls") or "").strip()
                if desc:
                    dedupe_key = ("research", f"{desc}|{r_type}|{max_urls}")
            elif agent == "structurizer":
                desc = (task.get("description") or "").strip().lower()
                if desc:
                    dedupe_key = ("structurizer", desc)

            # Жёсткий лимит на structurizer: все шаги сверх лимита мапим
            # на последний структуризатор (если он уже есть).
            if agent == "structurizer" and structurizer_count >= max_structurizer_steps and last_structurizer_id:
                id_map[base_id] = last_structurizer_id
                continue

            # Если это повторный шаг с тем же ключом —
            # не добавляем его, а просто мапим старый id на уже существующий.
            if dedupe_key and dedupe_key in dedupe_seen:
                existing_id = dedupe_seen[dedupe_key]
                id_map[base_id] = existing_id
                continue

            # Новый нормализованный id для шага.
            new_id = str(len(id_map) + 1)
            id_map[base_id] = new_id

            if agent == "structurizer":
                structurizer_count += 1
                last_structurizer_id = new_id

            if dedupe_key:
                dedupe_seen[dedupe_key] = new_id

            step["step_id"] = new_id
            normalized_steps.append(step)

        # Второй проход: нормализуем depends_on и чиним связку research → structurizer.
        last_research_step_id: Optional[str] = None
        for step in normalized_steps:
            agent = step.get("agent")

            # Обновляем указатель на последний research.
            if agent == "research":
                last_research_step_id = step.get("step_id")

            deps = step.get("depends_on") or []
            if not isinstance(deps, list):
                deps = []

            norm_deps: List[str] = []
            for dep in deps:
                dep_str = str(dep)
                m = re.match(r"(\d+)", dep_str)
                base_dep = m.group(1) if m else dep_str
                new_id = id_map.get(base_dep)
                if not new_id:
                    continue
                # Убираем ссылки на самого себя и дубликаты.
                if new_id == step["step_id"]:
                    continue
                if new_id not in norm_deps:
                    norm_deps.append(new_id)

            # Исправляем зависимость structurizer: он должен опираться на research,
            # а не на discovery/пустой список, если research уже есть в плане.
            if agent == "structurizer" and last_research_step_id:
                # Если среди нормализованных зависимостей ещё нет research,
                # жёстко привязываем structurizer к последнему research.
                if last_research_step_id not in norm_deps:
                    norm_deps = [last_research_step_id]

            step["depends_on"] = norm_deps

        # Третий проход: reporter не может иметь пустой depends_on в типовом пайплайне —
        # привязываем к ближайшему предшествующему analyst / structurizer / research / …
        fallback_for_reporter = [
            "analyst",
            "structurizer",
            "research",
            "discovery",
            "widget_codex",
            "transform_codex",
        ]
        for i, step in enumerate(normalized_steps):
            if step.get("agent") != "reporter":
                continue
            chosen: Optional[str] = None
            for pref in fallback_for_reporter:
                for j in range(i - 1, -1, -1):
                    if normalized_steps[j].get("agent") == pref:
                        chosen = normalized_steps[j]["step_id"]
                        break
                if chosen:
                    break
            if not chosen and i > 0:
                chosen = normalized_steps[i - 1]["step_id"]
            if chosen and step.get("step_id") != chosen:
                step["depends_on"] = [chosen]

        for step in normalized_steps:
            t = step.get("task")
            if isinstance(t, dict):
                PlannerAgent._ensure_task_summary_field(t, step.get("agent"))

        plan["steps"] = normalized_steps
        return plan

    @staticmethod
    def _ensure_task_summary_field(task: Dict[str, Any], agent: Any) -> None:
        """Краткий summary для UI прогресса; при отсутствии — из первой строки description."""
        s = str(task.get("summary") or "").strip()
        if s:
            task["summary"] = s[:160]
            return
        desc = str(task.get("description") or "").strip()
        if desc:
            line = desc.split("\n")[0].strip()
            if len(line) > 120:
                line = line[:117] + "..."
            task["summary"] = line
        else:
            ag = str(agent or "шаг").strip() or "шаг"
            task["summary"] = ag[:80]

    def _constrain_transformation_plan_to_local_data(
        self,
        plan: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        user_request: str,
    ) -> Dict[str, Any]:
        """
        In transformation mode, keep planning local to ContentNode tables by default.
        Allow discovery/research only when user explicitly asks for external/web data.
        """
        if not context:
            return plan
        if context.get("controller") != "transformation" and context.get("mode") != "transformation":
            return plan

        raw_request = (
            (context or {}).get("controller_user_request")
            or user_request
            or ""
        )
        request_lower = str(raw_request).lower()
        explicit_external = any(
            marker in request_lower
            for marker in (
                "интернет",
                "веб",
                "web",
                "online",
                "онлайн",
                "http://",
                "https://",
                "внешн",
                "external",
                "api",
                "url",
                "research",
                "discovery",
            )
        )
        if explicit_external:
            return plan

        steps_in = plan.get("steps") or []
        if not isinstance(steps_in, list):
            return plan
        filtered: List[Dict[str, Any]] = []
        removed = 0
        for raw_step in steps_in:
            step = dict(raw_step) if isinstance(raw_step, dict) else {}
            if step.get("agent") in {"discovery", "research"}:
                removed += 1
                continue
            filtered.append(step)
        if removed:
            self.logger.info(
                "Removed %s web-step(s) from transformation plan (local ContentNode mode)",
                removed,
            )
        out = dict(plan)
        out["steps"] = filtered
        return self._normalize_plan_steps(out)

    def _inject_context_filter_step(
        self,
        plan: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        user_request: str,
    ) -> Dict[str, Any]:
        """
        Insert context_filter step before first analyst when appropriate.
        This keeps filtering explicit in the plan for multi-hop assistant requests.
        """
        if not self._needs_context_filter_step(context, user_request):
            return plan

        steps_in = plan.get("steps") or []
        if not isinstance(steps_in, list) or not steps_in:
            return plan
        if any(isinstance(s, dict) and s.get("agent") == "context_filter" for s in steps_in):
            return plan

        first_analyst_idx = next(
            (i for i, s in enumerate(steps_in) if isinstance(s, dict) and s.get("agent") == "analyst"),
            None,
        )
        if first_analyst_idx is None:
            return plan

        steps: List[Dict[str, Any]] = [dict(s) if isinstance(s, dict) else {} for s in steps_in]
        analyst_step = steps[first_analyst_idx]
        analyst_deps = analyst_step.get("depends_on", [])
        if not isinstance(analyst_deps, list):
            analyst_deps = []

        filter_step = {
            "agent": "context_filter",
            "task": {
                "description": "Apply cross-filter to focus working set for entity-specific analysis",
                "allow_auto_filter": True,
                "user_request": user_request[:1000],
            },
            "depends_on": analyst_deps,
        }
        steps.insert(first_analyst_idx, filter_step)
        # Analyst must depend on context_filter now.
        analyst_step["depends_on"] = [str(first_analyst_idx + 1)]
        steps[first_analyst_idx + 1] = analyst_step

        out = dict(plan)
        out["steps"] = steps
        out = self._normalize_plan_steps(out)
        self.logger.info("🧩 Injected context_filter step before analyst for assistant query")
        return out

    @staticmethod
    def _needs_context_filter_step(
        context: Optional[Dict[str, Any]],
        user_request: str,
    ) -> bool:
        if not context:
            return False
        if context.get("controller") != "ai_assistant":
            return False
        if context.get("mode") not in ("assistant", None, ""):
            return False
        if not context.get("input_data_preview"):
            return False

        req = (user_request or "").strip().lower()
        if not req:
            return False

        # Fast heuristics: factual/entity question likely needs filtering by dim value.
        intent_kw = (
            "самый", "топ", "ходов", "лидер", "доля", "продаж", "товар", "бренд",
            "brand", "manufacturer", "product", "sales",
        )
        if not any(k in req for k in intent_kw):
            return False
        return len(req) <= 300

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
