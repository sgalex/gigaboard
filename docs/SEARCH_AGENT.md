# Search Agent - Документация

## Обзор

**SearchAgent** - специализированный агент для поиска информации в интернете через DuckDuckGo в системе GigaBoard Multi-Agent.

## Основные возможности

1. **Веб-поиск** - поиск текстовых результатов через DuckDuckGo
2. **Поиск новостей** - поиск актуальных новостей по запросу
3. **Быстрые ответы** - получение мгновенных ответов на вопросы (instant answers)
4. **Суммаризация результатов** - автоматическая суммаризация найденной информации с помощью GigaChat
5. **Указание источников** - все результаты содержат ссылки на источники

## Поддерживаемые типы задач

### 1. `web_search` - Веб-поиск

Выполняет общий поиск информации в интернете.

**Параметры:**
```json
{
  "type": "web_search",
  "query": "поисковый запрос",
  "max_results": 10,  // опционально, по умолчанию 10
  "region": "ru-ru"   // опционально, по умолчанию "ru-ru"
}
```

**Результат:**
```json
{
  "status": "completed",
  "query": "Python programming",
  "results": [
    {
      "title": "Python.org",
      "url": "https://python.org",
      "snippet": "Python is a programming language..."
    }
  ],
  "summary": "Python - высокоуровневый язык программирования...",
  "sources": ["https://python.org", "..."],
  "timestamp": "2024-01-20T10:00:00Z"
}
```

### 2. `news_search` - Поиск новостей

Ищет актуальные новости по заданному запросу.

**Параметры:**
```json
{
  "type": "news_search",
  "query": "искусственный интеллект",
  "max_results": 10  // опционально
}
```

**Результат:**
```json
{
  "status": "completed",
  "query": "искусственный интеллект",
  "results": [
    {
      "title": "Заголовок новости",
      "url": "https://news.example.com/ai",
      "date": "2024-01-20",
      "source": "News Portal",
      "snippet": "Краткое описание..."
    }
  ],
  "summary": "Последние новости об ИИ...",
  "sources": ["https://news.example.com/ai"],
  "timestamp": "2024-01-20T10:00:00Z"
}
```

### 3. `instant_answer` - Быстрый ответ

Получает мгновенный ответ на простой вопрос.

**Параметры:**
```json
{
  "type": "instant_answer",
  "query": "What is the capital of France?"
}
```

**Результат:**
```json
{
  "status": "completed",
  "query": "What is the capital of France?",
  "answer": "Paris",
  "results": [],  // Дополнительные результаты при необходимости
  "timestamp": "2024-01-20T10:00:00Z"
}
```

## Интеграция с Multi-Agent системой

### Регистрация в Planner Agent

SearchAgent автоматически доступен в Planner Agent со следующими типами задач:

```python
# В системном промпте Planner Agent:
- **search**: Поиск информации в интернете через DuckDuckGo
  Поддерживаемые типы: `web_search`, `news_search`, `instant_answer`
```

### Пример использования в плане

```json
{
  "step_id": "1",
  "agent": "search",
  "task": {
    "type": "web_search",
    "query": "последние новости о Python 3.12",
    "max_results": 5
  },
  "depends_on": [],
  "estimated_time": "5s"
}
```

## Технические детали

### Зависимости

- `duckduckgo-search>=5.0.0` - библиотека для работы с DuckDuckGo API
- GigaChat - для суммаризации результатов

### Установка зависимости

```bash
# Автоматически устанавливается с pyproject.toml
pip install -e .

# Или вручную
pip install duckduckgo-search
```

### Инициализация

```python
from app.services.multi_agent import SearchAgent

search_agent = SearchAgent(
    message_bus=message_bus,
    gigachat_service=gigachat_service
)

# Запуск агента
await search_agent.start_listening()
```

## Особенности реализации

### 1. Ленивая инициализация DuckDuckGo

Клиент DuckDuckGo инициализируется только при первом использовании для экономии ресурсов:

```python
def _ensure_ddgs_client(self):
    """Lazy initialization of DuckDuckGo client."""
    if self._ddgs_client is None:
        self._ddgs_client = DDGS()
```

### 2. GigaChat суммаризация

Все результаты поиска автоматически суммаризируются GigaChat для удобства пользователя:

- **Веб-поиск**: Генерирует краткое резюме (2-3 предложения) из найденных результатов
- **Новости**: Создает обзор основных тем и трендов в новостях

### 3. Обработка ошибок

- Timeout поиска: 30 секунд
- Fallback при отсутствии результатов
- Логирование всех ошибок с контекстом

### 4. Региональный поиск

По умолчанию используется регион `ru-ru`, но можно указать другой:

```json
{
  "type": "web_search",
  "query": "weather",
  "region": "en-us"
}
```

## Тестирование

### Запуск тестов

```bash
cd apps/backend
python tests/test_search_agent.py
```

### Тесты включают:

1. **Web Search Test** - поиск "Python programming language"
2. **News Search Test** - поиск новостей об "искусственный интеллект"
3. **Instant Answer Test** - вопрос "What is the capital of France?"

## Примеры сценариев использования

### Сценарий 1: Исследование технологии

```json
{
  "steps": [
    {
      "step_id": "1",
      "agent": "search",
      "task": {
        "type": "web_search",
        "query": "FastAPI best practices 2024",
        "max_results": 10
      }
    },
    {
      "step_id": "2",
      "agent": "analyst",
      "task": {
        "type": "analyze_data",
        "data": "<результаты_поиска>",
        "analysis_type": "summarize_practices"
      },
      "depends_on": ["1"]
    }
  ]
}
```

### Сценарий 2: Мониторинг новостей

```json
{
  "steps": [
    {
      "step_id": "1",
      "agent": "search",
      "task": {
        "type": "news_search",
        "query": "artificial intelligence breakthroughs",
        "max_results": 20
      }
    },
    {
      "step_id": "2",
      "agent": "reporter",
      "task": {
        "type": "create_visualization",
        "description": "Создать timeline последних новостей об ИИ",
        "data_preview": "<новости_из_шага_1>"
      },
      "depends_on": ["1"]
    }
  ]
}
```

### Сценарий 3: Быстрая справка

```json
{
  "steps": [
    {
      "step_id": "1",
      "agent": "search",
      "task": {
        "type": "instant_answer",
        "query": "Какая текущая версия Python?"
      }
    }
  ]
}
```

## Ограничения

1. **Rate Limiting**: DuckDuckGo может ограничивать частоту запросов
2. **Качество результатов**: Зависит от качества данных DuckDuckGo
3. **Региональные ограничения**: Некоторые результаты могут быть недоступны в определенных регионах
4. **Instant Answers**: Работает только для простых фактических вопросов

## Best Practices

1. **Используйте конкретные запросы**: "Python 3.12 новые возможности" вместо "Python"
2. **Ограничивайте max_results**: Не запрашивайте более 20 результатов за раз
3. **Указывайте регион**: Для лучшей локализации результатов
4. **Комбинируйте с другими агентами**: Используйте результаты поиска для дальнейшего анализа

## Логирование

SearchAgent логирует:
- Входящие задачи
- Параметры поиска
- Количество найденных результатов
- Ошибки и предупреждения
- Время выполнения

Пример логов:

```
INFO - 🔍 SearchAgent received task: web_search
INFO - 🔎 Performing web search: query='Python', max_results=10, region='ru-ru'
INFO - ✅ Found 10 search results
INFO - 🤖 Summarizing search results with GigaChat...
INFO - ✅ SearchAgent completed task in 4.2s
```

## Дальнейшее развитие

Планируемые улучшения:

1. **Кэширование результатов** - Redis кэш для популярных запросов
2. **Расширенная фильтрация** - По дате, типу контента, языку
3. **Поиск изображений** - Интеграция DuckDuckGo image search
4. **Поиск видео** - Интеграция видео поиска
5. **Semantic search** - Использование embeddings для ранжирования результатов

## См. также

- [MULTI_AGENT_SYSTEM.md](MULTI_AGENT_SYSTEM.md) - Общая архитектура Multi-Agent системы
- [API.md](API.md) - API endpoints для Multi-Agent системы
- [test_search_agent.py](../apps/backend/tests/test_search_agent.py) - Примеры тестов
