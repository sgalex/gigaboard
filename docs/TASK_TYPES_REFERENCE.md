# Multi-Agent System: Типы задач (Task Types)

## Executive Summary

Каждый агент в Multi-Agent системе GigaBoard поддерживает определённые **типы задач** (task types). Planner Agent при декомпозиции пользовательского запроса должен назначать задачи с правильными типами, иначе агент вернёт ошибку `Unknown task type`.

**Текущая проблема**: Planner генерирует типы задач `calculate_price_change` и `market_analysis`, которые **не поддерживаются** AnalystAgent.

---

## 📋 Таблица поддерживаемых типов задач

| Агент              | Типы задач                | Описание                                              | Статус           |
| ------------------ | ------------------------- | ----------------------------------------------------- | ---------------- |
| **researcher**     | `fetch_from_api`          | HTTP запрос к REST API                                | ✅ Реализовано    |
|                    | `fetch_urls`              | Массовая загрузка содержимого URL (после SearchAgent) | ✅ Реализовано    |
|                    | `query_database`          | SQL запрос к БД                                       | ⚠️ TODO           |
|                    | `parse_data`              | Парсинг данных из различных форматов                  | ✅ Реализовано    |
| **analyst**        | `generate_sql`            | Генерация SQL запроса из естественного языка          | ✅ Реализовано    |
|                    | `analyze_data`            | Анализ данных и поиск паттернов                       | ✅ Реализовано    |
|                    | `find_insights`           | Генерация insights и рекомендаций                     | ✅ Реализовано    |
|                    | `generate_data`           | Генерация синтетических данных (упомянуто в Planner)  | ❌ НЕ реализовано |
| **reporter**       | `create_visualization`    | Генерация WidgetNode с HTML/CSS/JS визуализацией      | ✅ Реализовано    |
|                    | `generate_visualization`  | Альтернативный тип для генерации                      | ✅ Реализовано    |
|                    | `update_visualization`    | Обновление существующей визуализации                  | ✅ Реализовано    |
| **transformation** | `create_transformation`   | Создание Python кода для трансформации DataNode       | ✅ Реализовано    |
|                    | `validate_transformation` | Валидация Python кода трансформации                   | ✅ Реализовано    |
|                    | `optimize_transformation` | Оптимизация кода трансформации                        | ✅ Реализовано    |
| **search**         | `web_search`              | Поиск информации в интернете (DuckDuckGo)             | ✅ Реализовано    |
|                    | `news_search`             | Поиск новостей                                        | ✅ Реализовано    |
|                    | `instant_answer`          | Быстрый ответ на вопрос                               | ✅ Реализовано    |

---

## 🔍 Детальное описание по агентам

### 1. ResearcherAgent - Получение данных

**Файл**: `apps/backend/app/services/multi_agent/agents/researcher.py`

#### `fetch_from_api`
Выполняет HTTP запрос к REST API.

**Параметры**:
```python
{
  "type": "fetch_from_api",
  "url": "https://api.example.com/data",
  "method": "GET",  # необязательно, по умолчанию GET
  "headers": {},    # необязательно
  "params": {},     # query parameters
  "json_data": {}   # для POST запросов
}
```

**Возврат**:
```python
{
  "status": "success",
  "content_type": "api_response|csv|text|html",
  "data": {...},
  "source": {
    "type": "api",
    "url": "...",
    "method": "GET",
    "status_code": 200,
    "timestamp": "2026-02-02T16:32:28.859545"
  },
  "statistics": {
    "size_bytes": 1024,
    "row_count": 10
  },
  "schema": {
    "columns": ["col1", "col2"],
    "types": ["string", "integer"]
  }
}
```

#### `fetch_urls`
Загружает содержимое из списка URL (обычно после SearchAgent).

**Параметры**:
```python
{
  "type": "fetch_urls",
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2"
  ],
  "max_urls": 5,  # необязательно, по умолчанию 3
  "extract_text": true  # извлечь текст из HTML
}
```

**Возврат**:
```python
{
  "status": "success",
  "pages_fetched": 2,
  "pages": [
    {
      "url": "https://example.com/page1",
      "title": "Page Title",
      "content": "extracted text...",
      "content_length": 5000,
      "status": "success"
    }
  ],
  "total_content_bytes": 10000
}
```

#### `query_database`
⚠️ **TODO**: SQL запрос к БД (требует DB connection).

#### `parse_data`
Парсит данные из различных форматов (CSV, JSON, XML).

---

### 2. AnalystAgent - Анализ данных

**Файл**: `apps/backend/app/services/multi_agent/agents/analyst.py`

**Поддерживаемые типы**: `generate_sql`, `analyze_data`, `find_insights`

**НЕ поддерживаемые типы** (ошибка в тесте):
- ❌ `calculate_price_change` - не реализовано
- ❌ `market_analysis` - не реализовано

#### `generate_sql`
Генерирует SQL запрос из естественного языка.

**Параметры**:
```python
{
  "type": "generate_sql",
  "description": "Получить все продажи за 2024 год с группировкой по регионам",
  "table_schema": {
    "sales": {
      "columns": ["id", "date", "region", "amount"],
      "types": ["integer", "date", "varchar", "decimal"]
    }
  },
  "database_type": "postgresql"  # postgresql|mysql|sqlite
}
```

**Возврат**:
```python
{
  "status": "success",
  "sql_query": "SELECT region, SUM(amount) FROM sales WHERE YEAR(date) = 2024 GROUP BY region",
  "query_type": "select|aggregate|join",
  "estimated_rows": 1500,
  "parameters": {"year": 2024},
  "explanation": "Получает данные о продажах за 2024 год с группировкой по регионам"
}
```

#### `analyze_data`
Анализирует данные и находит паттерны.

**Параметры**:
```python
{
  "type": "analyze_data",
  "data": {...},  # данные для анализа (или берутся из Redis)
  "analysis_type": "descriptive|diagnostic|predictive|prescriptive",
  "metrics": ["mean", "median", "std_dev"]  # необязательно
}
```

**Возврат**:
```python
{
  "status": "success",
  "insights": [
    {
      "type": "trend|anomaly|correlation|pattern",
      "severity": "high|medium|low",
      "title": "Продажи снижаются на 15%",
      "description": "...",
      "evidence": {"metric": "sales", "change": -15.3}
    }
  ],
  "statistics": {
    "mean": 1250.5,
    "median": 1100,
    "std_dev": 320.8
  }
}
```

#### `find_insights`
Генерирует insights и actionable recommendations.

**Параметры**:
```python
{
  "type": "find_insights",
  "data_summary": {...},  # или берётся из Redis (SearchAgent + ResearcherAgent)
  "business_context": "E-commerce sales analysis"
}
```

**Возврат**:
```python
{
  "status": "success",
  "insights": [
    {
      "type": "trend",
      "severity": "high",
      "title": "Regional decline in North",
      "description": "...",
      "evidence": {...},
      "suggested_actions": [
        "create_regional_breakdown_visualization",
        "investigate_competitor_activity"
      ]
    }
  ]
}
```

#### `generate_data` ❌ НЕ РЕАЛИЗОВАНО
Упоминается в Planner System Prompt, но **отсутствует в analyst.py**.

**Ожидаемые параметры** (из Planner):
```python
{
  "type": "generate_data",
  "description": "Таблица с данными о продажах онлайн-магазина",
  "format": "table|text",
  "rows": 50
}
```

**ДЕЙСТВИЕ**: Нужно либо:
1. Реализовать `generate_data` в AnalystAgent
2. Убрать из Planner System Prompt
3. Использовать существующий `AIDataGenerator` service

---

### 3. ReporterAgent - Визуализации

**Файл**: `apps/backend/app/services/multi_agent/agents/reporter.py`

**Поддерживаемые типы**: `create_visualization`, `generate_visualization`, `update_visualization`

#### `create_visualization`
Генерирует WidgetNode с HTML/CSS/JS визуализацией.

**Параметры**:
```python
{
  "type": "create_visualization",
  "data_preview": {...},  # данные для визуализации
  "chart_type": "bar|line|pie|table|scatter",
  "title": "Sales by Region",
  "description": "..."
}
```

**Возврат**:
```python
{
  "status": "success",
  "widget_type": "bar_chart",
  "description": "Interactive bar chart showing sales by region",
  "html_code": "<!DOCTYPE html>...",
  "width": 800,
  "height": 600
}
```

---

### 4. TransformationAgent - Трансформации

**Файл**: `apps/backend/app/services/multi_agent/agents/transformation.py`

**Поддерживаемые типы**: `create_transformation`, `validate_transformation`, `optimize_transformation`

#### `create_transformation`
Создаёт Python код для трансформации DataNode → DataNode.

**Параметры**:
```python
{
  "type": "create_transformation",
  "description": "Filter rows where amount > 1000",
  "source_schema": {
    "columns": ["id", "amount", "date"],
    "types": ["int", "float", "date"]
  },
  "target_schema": {...}  # необязательно
}
```

**Возврат**:
```python
{
  "status": "success",
  "python_code": "def transform(df):\n    return df[df['amount'] > 1000]",
  "explanation": "Filters DataFrame to keep only rows where amount exceeds 1000",
  "dependencies": ["pandas"]
}
```

---

### 5. SearchAgent - Поиск информации

**Файл**: `apps/backend/app/services/multi_agent/agents/search.py`

**Поддерживаемые типы**: `web_search`, `news_search`, `instant_answer`

#### `web_search`
Поиск информации в интернете через DuckDuckGo.

**Параметры**:
```python
{
  "type": "web_search",
  "query": "Bitcoin price analysis 2026",
  "max_results": 5,
  "region": "ru-ru"  # необязательно
}
```

**Возврат**:
```python
{
  "status": "success",
  "query": "Bitcoin price analysis 2026",
  "results": [
    {
      "title": "Bitcoin Market Analysis",
      "url": "https://example.com/btc-analysis",
      "snippet": "Bitcoin price reached $77,000...",
      "published": "2026-02-01"
    }
  ],
  "result_count": 5,
  "summary": "Found 5 articles about Bitcoin price analysis...",
  "sources": ["example.com", "crypto.org"]
}
```

**ВАЖНО**: После SearchAgent используйте ResearcherAgent с `fetch_urls` для загрузки полного содержимого страниц!

---

## 🔧 Решение проблемы с тестом

### Проблема
Planner генерирует задачи с типами:
- `calculate_price_change` - не поддерживается AnalystAgent
- `market_analysis` - не поддерживается AnalystAgent

### Решения

#### Вариант 1: Расширить AnalystAgent
Добавить поддержку этих типов в `analyst.py`:

```python
async def process_task(self, task, context):
    task_type = task.get("type")
    
    if task_type == "generate_sql":
        return await self._generate_sql(task, context)
    elif task_type == "analyze_data":
        return await self._analyze_data(task, context)
    elif task_type == "find_insights":
        return await self._find_insights(task, context)
    elif task_type == "calculate_price_change":
        return await self._calculate_price_change(task, context)
    elif task_type == "market_analysis":
        return await self._market_analysis(task, context)
    # ...
```

#### Вариант 2: Обновить Planner System Prompt
Указать Planner, что AnalystAgent поддерживает только:
- `generate_sql`
- `analyze_data`
- `find_insights`

И использовать эти типы вместо custom типов.

#### Вариант 3: Маппинг в AnalystAgent
Добавить маппинг custom типов на существующие:

```python
# Маппинг custom типов на стандартные
TYPE_MAPPING = {
    "calculate_price_change": "analyze_data",
    "market_analysis": "find_insights",
    "generate_data": "analyze_data"  # когда реализуем
}

task_type = TYPE_MAPPING.get(task.get("type"), task.get("type"))
```

**Рекомендация**: Вариант 2 - обновить Planner System Prompt, чтобы он генерировал стандартные типы задач.

---

## 📊 Статистика реализации

- **Реализовано**: 15 типов задач
- **TODO**: 2 типа (`query_database`, `generate_data`)
- **Проблемных**: 2 типа (генерируются Planner, но не поддерживаются Analyst)

**Coverage**: 88% (15/17)

---

## 🔗 Ссылки на код

- Planner System Prompt: [planner.py](../apps/backend/app/services/multi_agent/agents/planner.py#L39-L97)
- AnalystAgent: [analyst.py](../apps/backend/app/services/multi_agent/agents/analyst.py#L136-L158)
- ResearcherAgent: [researcher.py](../apps/backend/app/services/multi_agent/agents/researcher.py#L120-L149)
- ReporterAgent: [reporter.py](../apps/backend/app/services/multi_agent/agents/reporter.py#L237-L247)
- TransformationAgent: [transformation.py](../apps/backend/app/services/multi_agent/agents/transformation.py#L247-L261)
- SearchAgent: [search.py](../apps/backend/app/services/multi_agent/agents/search.py#L144-L152)

---

**Последнее обновление**: 2026-02-02
