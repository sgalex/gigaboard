# Search Agent — Поиск в интернете (DiscoveryAgent)

## Executive Summary

**SearchAgent** (часть DiscoveryAgent в V2) — агент для поиска информации в интернете через DuckDuckGo. Поддерживает веб-поиск, поиск новостей и быстрые ответы. Результаты автоматически суммаризируются GigaChat.

> **Примечание**: В Multi-Agent V2 поисковая функциональность входит в состав **DiscoveryAgent**.

---

## Возможности

| Тип задачи       | Описание                              |
| ---------------- | ------------------------------------- |
| `web_search`     | Общий поиск в интернете               |
| `news_search`    | Поиск актуальных новостей             |
| `instant_answer` | Быстрые ответы на фактические вопросы |

---

## Установка

```bash
# duckduckgo-search устанавливается с pyproject.toml
cd apps/backend
uv pip install duckduckgo-search

# Проверка
python -c "from duckduckgo_search import DDGS; print('✅ OK')"
```

---

## API

### Web Search

```json
{
  "type": "web_search",
  "query": "Python FastAPI best practices",
  "max_results": 10,
  "region": "ru-ru"
}
```

**Результат:**
```json
{
  "status": "completed",
  "query": "Python FastAPI best practices",
  "results": [
    {
      "title": "FastAPI Documentation",
      "url": "https://fastapi.tiangolo.com",
      "snippet": "FastAPI is a modern web framework..."
    }
  ],
  "summary": "FastAPI - современный веб-фреймворк...",
  "sources": ["https://fastapi.tiangolo.com"]
}
```

### News Search

```json
{
  "type": "news_search",
  "query": "искусственный интеллект",
  "max_results": 10
}
```

### Instant Answer

```json
{
  "type": "instant_answer",
  "query": "What is the capital of France?"
}
```

---

## Интеграция с Multi-Agent

Planner Agent автоматически использует SearchAgent для задач, требующих поиска:

```json
{
  "steps": [
    {
      "step_id": "1",
      "agent": "search",
      "task": {
        "type": "web_search",
        "query": "последние новости о Python 3.12",
        "max_results": 5
      }
    },
    {
      "step_id": "2",
      "agent": "analyst",
      "task": { "type": "analyze_data" },
      "depends_on": ["1"]
    }
  ]
}
```

---

## Особенности

- **Ленивая инициализация** — DuckDuckGo клиент создаётся при первом запросе
- **GigaChat суммаризация** — автоматическое резюме результатов
- **Региональный поиск** — по умолчанию `ru-ru`
- **Timeout**: 30 секунд на запрос
- **Rate limiting**: DuckDuckGo может ограничивать частоту запросов

---

## Troubleshooting

| Проблема                                           | Решение                                                                       |
| -------------------------------------------------- | ----------------------------------------------------------------------------- |
| `ImportError: No module named 'duckduckgo_search'` | `uv pip install duckduckgo-search`                                            |
| SSL Certificate Error                              | Для dev: `ssl._create_default_https_context = ssl._create_unverified_context` |
| Connection Timeout                                 | Увеличить timeout до 60 секунд                                                |
| Too many requests                                  | Добавить `asyncio.sleep(2)` между запросами                                   |
| Пустые результаты                                  | Использовать более общий запрос или другой регион                             |

---

## См. также

- [MULTI_AGENT.md](./MULTI_AGENT.md) — DiscoveryAgent в V2 архитектуре
- [API.md](./API.md) — API endpoints
