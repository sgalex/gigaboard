# Search Agent - Быстрый старт

## Установка

### 1. Установите зависимость

```bash
cd apps/backend
pip install duckduckgo-search
```

Или установите все зависимости из pyproject.toml:

```bash
pip install -e .
```

### 2. Проверьте, что SearchAgent экспортирован

```python
from app.services.multi_agent import SearchAgent
print("✅ SearchAgent imported successfully")
```

## Быстрый тест

### Запустите тестовый скрипт

```bash
cd apps/backend
python tests/test_search_agent.py
```

Этот скрипт проверит:
- ✅ Веб-поиск через DuckDuckGo
- ✅ Поиск новостей
- ✅ Быстрые ответы (instant answers)
- ✅ Суммаризацию результатов с GigaChat

### Пример вывода

```
🔧 Setting up Search Agent test...
✅ Redis connected
✅ GigaChat initialized
✅ Message Bus connected
✅ Search Agent initialized
🚀 Starting Search Agent...
✅ Search Agent is listening

================================================================================
🔍 TEST 1: Web Search - 'Python programming language'
================================================================================

📊 RESULT:
Status: completed
Query: Python programming language
Results count: 10

📝 Summary:
Python - высокоуровневый язык программирования общего назначения...

🔗 Top results:
  1. Python.org - Official Website
     URL: https://python.org
     Snippet: Python is a programming language that lets you work quickly...
```

## Использование в Multi-Agent системе

### Обновите test_moscow_cinema.py

SearchAgent уже добавлен в `test_moscow_cinema.py`:

```python
from app.services.multi_agent import SearchAgent

# В setup():
self.agents["search"] = SearchAgent(
    message_bus=self.message_bus,
    gigachat_service=gigachat
)
```

### Planner Agent автоматически знает о SearchAgent

System prompt уже обновлен:

```
- **search**: Поиск информации в интернете через DuckDuckGo
  Поддерживаемые типы: `web_search`, `news_search`, `instant_answer`
```

## Примеры запросов

### Пример 1: Простой веб-поиск

```python
task = {
    "type": "web_search",
    "query": "FastAPI best practices",
    "max_results": 5
}

result = await message_bus.send_task_to_agent(
    agent_name="search",
    session_id=session_id,
    step_index=0,
    task=task,
    timeout=30.0
)

print(result["summary"])  # GigaChat summary
print(len(result["results"]))  # 5 results
```

### Пример 2: Поиск новостей

```python
task = {
    "type": "news_search",
    "query": "искусственный интеллект",
    "max_results": 10
}

result = await message_bus.send_task_to_agent(
    agent_name="search",
    session_id=session_id,
    step_index=0,
    task=task,
    timeout=30.0
)

for news in result["results"]:
    print(f"{news['date']}: {news['title']}")
```

### Пример 3: Быстрый ответ

```python
task = {
    "type": "instant_answer",
    "query": "What is Python?"
}

result = await message_bus.send_task_to_agent(
    agent_name="search",
    session_id=session_id,
    step_index=0,
    task=task,
    timeout=30.0
)

if result.get("answer"):
    print(f"Ответ: {result['answer']}")
```

## Пример полного workflow

Создайте запрос пользователя, который требует поиск в интернете:

```python
user_message = "Найди последние новости о Python 3.12 и создай визуализацию timeline"

async for chunk in orchestrator.process_user_request(
    user_id=user_id,
    board_id=board_id,
    user_message=user_message
):
    print(chunk, end="", flush=True)
```

Planner Agent автоматически создаст план:

```json
{
  "steps": [
    {
      "step_id": "1",
      "agent": "search",
      "task": {
        "type": "news_search",
        "query": "Python 3.12 release",
        "max_results": 20
      }
    },
    {
      "step_id": "2",
      "agent": "analyst",
      "task": {
        "type": "analyze_data",
        "data": "<results_from_step_1>"
      }
    },
    {
      "step_id": "3",
      "agent": "reporter",
      "task": {
        "type": "create_visualization",
        "description": "Timeline визуализация новостей о Python 3.12"
      }
    }
  ]
}
```

## Troubleshooting

### Проблема: DuckDuckGo rate limiting

**Симптомы**: Ошибка "Too many requests"

**Решение**: Добавьте задержки между запросами:

```python
await asyncio.sleep(2)  # 2 секунды между поисками
```

### Проблема: Нет результатов

**Симптомы**: `results: []`

**Возможные причины**:
1. Слишком специфичный запрос
2. Региональные ограничения
3. DuckDuckGo временно недоступен

**Решение**: Используйте более общие запросы или измените регион:

```python
task = {
    "type": "web_search",
    "query": "Python",  # Более общий запрос
    "region": "en-us"   # Другой регион
}
```

### Проблема: Timeout

**Симптомы**: `TimeoutError after 30s`

**Решение**: Увеличьте timeout:

```python
result = await message_bus.send_task_to_agent(
    agent_name="search",
    session_id=session_id,
    step_index=0,
    task=task,
    timeout=60.0  # Увеличен до 60 секунд
)
```

## Следующие шаги

1. ✅ SearchAgent создан и протестирован
2. ✅ Интегрирован с Multi-Agent системой
3. ✅ Planner Agent знает о SearchAgent
4. ⏭️ Используйте в реальных сценариях
5. ⏭️ Добавьте кэширование результатов (опционально)

## Полезные ссылки

- [SEARCH_AGENT.md](SEARCH_AGENT.md) - Полная документация
- [MULTI_AGENT_SYSTEM.md](MULTI_AGENT_SYSTEM.md) - Архитектура системы
- [test_search_agent.py](../apps/backend/tests/test_search_agent.py) - Примеры кода
- [DuckDuckGo Search Python](https://github.com/deedy5/duckduckgo_search) - Документация библиотеки

---

**Готово!** 🎉 SearchAgent полностью интегрирован и готов к использованию.
