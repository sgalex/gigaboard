# Source-Content Node Architecture: Quick Reference

**Дата**: 29 января 2026  
**Статус**: ✅ Концепция утверждена

---

## 🎯 TL;DR

Вводим чёткое разделение:
- **SourceNode** — точка входа данных (файл, БД, API, промпт, stream)
- **ContentNode** — результат обработки (текст + N таблиц)
- **WidgetNode** — визуализация (без изменений)
- **CommentNode** — комментарии к любым нодам

---

## 📊 Типы узлов

### 1. SourceNode

**Типы источников**:
- `prompt` — AI-промпт для генерации/анализа
- `file` — Файл (CSV, JSON, Excel, PDF)
- `database` — СУБД (PostgreSQL, MySQL, MongoDB)
- `api` — REST/GraphQL API
- `stream` — Real-time (WebSocket, SSE, Kafka)
- `manual` — Ручной ввод

**Операции**:
- `extract()` → создаёт ContentNode
- `validate()` → проверка подключения
- `refresh()` → обновление ContentNode
- `schedule_refresh(cron)` → автообновление

### 2. ContentNode

**Структура**:
```json
{
  "content": {
    "text": "Summary...",
    "tables": [
      {"id": "table_1", "name": "sales", "rows": [...], "columns": [...]},
      {"id": "table_2", "name": "stats", "rows": [...], "columns": [...]}
    ]
  },
  "lineage": {
    "source_node_id": "source_123",
    "transformation_id": null,
    "operation": "extract"
  }
}
```

**Операции**:
- `transform(prompt, sources)` → новый ContentNode
- `visualize(chart_type, table_ids)` → WidgetNode
- `export(format)` → CSV/JSON/Excel
- `get_table(table_id)` → конкретная таблица

### 3. WidgetNode

**Без изменений**. Может использовать:
- Одну таблицу из ContentNode
- Несколько таблиц из одного ContentNode
- Данные из нескольких таблиц для комплексных визуализаций

### 4. CommentNode

**Может комментировать**:
- SourceNode
- ContentNode
- WidgetNode
- Конкретную таблицу/колонку

---

## 🔗 Типы связей (Edges)

| Edge Type          | From → To                    | Описание                 |
| ------------------ | ---------------------------- | ------------------------ |
| **EXTRACT**        | SourceNode → ContentNode     | Извлечение данных        |
| **TRANSFORMATION** | ContentNode(s) → ContentNode | Преобразование через код |
| **VISUALIZATION**  | ContentNode → WidgetNode     | Визуализация             |
| **COMMENT**        | CommentNode → Any            | Комментирование          |

---

## 🌊 Streaming Sources

### Стратегия хранения
**Аккумуляция с архивированием**:
- Все данные накапливаются в ContentNode
- При достижении лимита → автоархивирование старых данных
- Пользователь может настроить: max_active_rows, archive_threshold

### Режимы обновления ContentNode
1. **Автоматический с интервалом** (по умолчанию, настраиваемый)
2. **По кнопке** (накопление в фоне, обновление вручную)

### Replay трансформаций
5 режимов:
1. **Throttled** — с ограничением частоты (рекомендуется)
2. **Batched** — по накоплению N записей
3. **Manual** — только по кнопке
4. **Intelligent** — AI-based решения
5. **Selective** — по приоритету трансформации

### Пример конфигурации
```json
{
  "source_type": "stream",
  "config": {
    "stream_type": "websocket",
    "url": "wss://...",
    "buffer_strategy": "accumulate_with_archive",
    "buffer_config": {
      "max_active_rows": 10000,
      "archive_threshold": 8000,
      "archive_storage": "s3://..."
    },
    "content_update_mode": "interval",
    "content_update_interval_ms": 5000,
    "replay_strategy": {
      "mode": "throttled",
      "interval_ms": 10000,
      "adaptive": true
    }
  }
}
```

---

## 🔄 Примеры потоков

### Простой поток
```
SourceNode (file) → EXTRACT → ContentNode → VISUALIZE → WidgetNode
```

### Join двух источников
```
SourceNode (DB: orders) → EXTRACT → ContentNode (orders)
                                            ↓
SourceNode (API: customers) → EXTRACT → ContentNode (customers)
                                            ↓
                                     TRANSFORMATION
                                            ↓
                                  ContentNode (enriched)
                                            ↓
                                        VISUALIZE
                                            ↓
                                     WidgetNode (report)
```

### Streaming pipeline
```
SourceNode (WebSocket) → EXTRACT (2sec) → ContentNode (accumulate + archive)
                                                ↓
                                         TRANSFORM (throttled 10sec)
                                                ↓
                                         ContentNode (aggregated)
                                                ↓
                                         VISUALIZE (auto-refresh 10sec)
                                                ↓
                                         WidgetNode (live chart)
```

---

## ✅ Ключевые решения

| Вопрос                               | Решение                                          |
| ------------------------------------ | ------------------------------------------------ |
| Файл — Source или Content?           | **SourceNode**                                   |
| ContentNode с несколькими таблицами? | ✅ Да, N таблиц                                   |
| WidgetNode для нескольких таблиц?    | ✅ Да, гибко                                      |
| Хранение кода трансформаций?         | В отдельной таблице `transformations`            |
| Streaming — как хранить?             | Аккумуляция + архивирование                      |
| Streaming — как обновлять?           | Настраиваемый режим (interval/manual)            |
| Replay трансформаций?                | 5 режимов (throttled рекомендуется)              |
| Версионирование ContentNode?         | Обновляет существующий + history table           |
| Cascade delete?                      | ✅ Да, удаление SourceNode удаляет все downstream |

---

## 📁 Документы

| Документ                                                                       | Содержание                          |
| ------------------------------------------------------------------------------ | ----------------------------------- |
| [SOURCE_CONTENT_NODE_CONCEPT.md](SOURCE_CONTENT_NODE_CONCEPT.md)               | Полная спецификация концепции       |
| [SOURCE_CONTENT_IMPLEMENTATION_PLAN.md](SOURCE_CONTENT_IMPLEMENTATION_PLAN.md) | План реализации (6 фаз, 10-15 дней) |
| [ROADMAP.md](ROADMAP.md)                                                       | Обновлённый roadmap с FR-14         |

---

## 🚀 Следующие шаги

1. ✅ Концепция утверждена
2. ✅ План реализации готов
3. → Создать feature branch `feature/source-content-nodes`
4. → Начать Phase 1: Database Schema & Models
5. → Code review после каждой фазы

**Оценка**: 10-15 дней разработки  
**Приоритет**: High (фундаментальная архитектура)

---

**Статус**: ✅ Готово к реализации
