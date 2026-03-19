# Технический дизайн: контекстный AI Assistant для Board/Dashboard

## Executive Summary

Документ описывает реализацию дискуссионного AI Assistant, который отвечает на вопросы по данным:

- **на доске (Board)** — по таблицам `ContentNode`, доступным в рамках доски;
- **на дашборде (Dashboard)** — по таблицам `ContentNode`, связанным с виджетами дашборда.

Ключевая идея: разделить pipeline на:

1. **Навигацию по контексту** (LLM-агент решает, какие таблицы/фильтры нужны),
2. **Детерминированное исполнение** (сервис применяет фильтры и готовит данные),
3. **Финальный аналитический ответ** с прозрачным `context_used`.

Это позволяет получить обсуждение данных в естественном языке без нарушения архитектурных принципов Multi-Agent V2 и Cross-Filter.

---

## Цели и границы

### Цели

- Дать пользователю возможность обсуждать результаты исследований и данных в рамках текущего экрана (board/dashboard).
- Включать в контекст список таблиц: имя, схема колонок, метаданные, sample rows.
- Поддержать query-driven фильтрацию (в контексте Cross-Filter), если вопрос требует срез.
- Возвращать прозрачный ответ: какие таблицы и фильтры использованы.

### Не-цели (на MVP)

- Автоматическое изменение состояния фильтров в UI без подтверждения.
- Выполнение произвольного Python кода для ответа (только безопасные детерминированные операции).
- Полноценный BI-движок ad-hoc SQL на первом этапе.

---

## Архитектурные принципы

1. **Single Path через Orchestrator** — никакого bypass в прямой LLM-вызов.
2. **LLM отвечает за решение, не за исполнение**:
   - LLM формирует план контекстных действий (какие таблицы/фильтры нужны),
   - backend-сервис выполняет фильтрацию/агрегацию.
3. **Scope-aware контекст**:
   - `board` — все релевантные `ContentNode` доски,
   - `dashboard` — только `ContentNode`, чьи виджеты присутствуют на дашборде.
4. **Прозрачность** — ответ содержит `context_used` с источниками и фильтрами.

---

## Предлагаемые компоненты

### 1) Новый агент: `ContextNavigatorAgent`

Роль:

- анализирует вопрос пользователя;
- выбирает релевантные таблицы/ноды из каталога контекста;
- определяет, нужно ли применять фильтры и по каким измерениям;
- формирует структурированную инструкцию для детерминированного сервиса.

Где:

- `apps/backend/app/services/multi_agent/agents/context_navigator.py`

Выход (`AgentPayload.metadata`):

- `required_tables: string[]`
- `proposed_filter_expression: FilterExpression | null`
- `operations: ["filter", "aggregate", "compare", ...]`
- `reasoning_summary: string`

### 2) Новый сервис: `ContextExecutionService`

Роль:

- строит набор таблиц в зависимости от `scope` (`board`/`dashboard`);
- применяет Cross-Filter (существующий `FilterEngine`);
- возвращает компактный пакет данных для аналитика/репортера.

Где:

- `apps/backend/app/services/context_execution_service.py`

Вход:

- `scope_type`, `scope_id`, `required_tables`, `filter_expression`, `selected_node_ids`.

Выход:

- `prepared_tables` (ограниченные sample rows + статистика),
- `context_used` (таблицы, фильтры, row_count before/after).

### 3) Расширение `AIAssistantController`

Добавить режимы:

- `mode="board_assistant"`
- `mode="dashboard_assistant"`

И workflow:

1. Сбор каталога контекста (таблицы + схемы + sample),
2. `ContextNavigatorAgent`,
3. `ContextExecutionService`,
4. `AnalystAgent` + `ReporterAgent`,
5. Возврат ответа + `context_used` + `suggested_actions`.

---

## Контекстные источники данных

### Board scope

Источник:

- `ContentNode` и `SourceNode` с табличным контентом в рамках `board_id`.

Стратегия отбора:

- если есть `selected_node_ids` — сначала они,
- затем связанные по графу (`edges`) ноды (ограниченный радиус),
- затем остальные (до лимита).

### Dashboard scope

Источник:

- `dashboard_items` -> widget-конфиг -> `sourceContentNodeId`.

Дополнительно:

- если у элемента нет явной ссылки на `ContentNode`, он пропускается с warning в telemetry.

---

## API-контракты

### Board chat (расширение)

`POST /api/v1/boards/{board_id}/ai/chat`

Request:

```json
{
  "message": "Сравни динамику продаж по регионам после фильтра по каналу онлайн",
  "session_id": "uuid",
  "context": {
    "mode": "board",
    "selected_node_ids": ["uuid1", "uuid2"],
    "allow_auto_filter": true
  }
}
```

Response:

```json
{
  "response": "После фильтра по каналу онлайн лидируют ...",
  "session_id": "uuid",
  "suggested_actions": [
    {
      "action": "apply_filter",
      "description": "Применить фильтр: channel = online"
    }
  ],
  "context_used": {
    "scope": "board",
    "tables": [
      {
        "node_id": "uuid",
        "table_name": "sales",
        "row_count_before": 12450,
        "row_count_after": 4201
      }
    ],
    "filters": {
      "op": "and",
      "conditions": [
        { "dimension": "channel", "operator": "eq", "value": "online" }
      ]
    }
  }
}
```

### Новый endpoint для Dashboard chat

`POST /api/v1/dashboards/{dashboard_id}/ai/chat`

Контракт аналогичен board chat, но `scope = "dashboard"`.

---

## Изменения в backend (по файлам)

### Маршруты

- `apps/backend/app/routes/ai_assistant.py`
  - расширить board endpoint для `context.mode=board`;
  - возвращать `context_used` из контроллера.
- `apps/backend/app/routes/ai_assistant_dashboard.py` (новый файл) или добавить в существующий dashboard router:
  - `POST /api/v1/dashboards/{dashboard_id}/ai/chat`
  - history endpoints (опционально 2-я итерация).

### Контроллеры

- `apps/backend/app/services/controllers/ai_assistant_controller.py`
  - добавить path `board_assistant`/`dashboard_assistant`;
  - интеграцию `ContextNavigatorAgent` + `ContextExecutionService`;
  - формирование `context_used`.

### Multi-Agent

- `apps/backend/app/services/multi_agent/agents/context_navigator.py` (новый)
- `apps/backend/app/services/multi_agent/agents/__init__.py`
  - регистрация агента.
- `apps/backend/app/services/multi_agent/orchestrator.py`
  - добавить `context_navigator` в доступные агенты.
- `apps/backend/app/services/multi_agent/config.py`
  - timeout для `context_navigator`.

### Сервисы данных

- `apps/backend/app/services/context_execution_service.py` (новый)
  - `build_board_context_catalog()`
  - `build_dashboard_context_catalog()`
  - `apply_query_filters()`
  - `prepare_tables_for_llm()`

### Схемы

- `apps/backend/app/schemas/ai_chat.py`
  - добавить строго типизированные поля `context.mode`, `allow_auto_filter`;
  - расширить `context_used` schema.

---

## Изменения во frontend (по файлам)

### API слой

- `apps/web/src/services/api.ts`
  - добавить `aiAssistantAPI.chatDashboard(dashboardId, request)`.

### Types

- `apps/web/src/types/index.ts`
  - расширить `AIChatRequest.context`:
    - `mode?: "board" | "dashboard"`
    - `selected_node_ids?: string[]`
    - `allow_auto_filter?: boolean`
  - расширить `AIChatResponse.context_used`.

### UI и стор

- `apps/web/src/store/aiAssistantStore.ts`
  - поддержка `scopeType` (`board`/`dashboard`) и `scopeId`;
  - вызов нужного endpoint в зависимости от scope.
- `apps/web/src/components/board/AIAssistantPanel.tsx`
  - визуализация текущего scope и таблиц/фильтров из `context_used`.
- `apps/web/src/pages/DashboardPage.tsx`
  - подключить AI panel в dashboard-контексте (если принято продуктом).

---

## Взаимодействие с Cross-Filter

Используем существующий механизм:

- `FilterExpression`,
- `FilterEngine`,
- `compute-filtered` pipeline.

Принцип:

1. `ContextNavigatorAgent` предлагает фильтр;
2. `ContextExecutionService` применяет фильтр к данным для ответа;
3. UI получает `suggested_actions.apply_filter`;
4. только после подтверждения пользователем фильтр фиксируется в состоянии board/dashboard.

---

## Telemetry и аудит

Логировать:

- `assistant_scope` (`board`/`dashboard`);
- `tables_considered_count`, `tables_used_count`;
- `filter_applied_for_answer` (bool);
- `answer_latency_ms`;
- `context_payload_size` (для контроля токенов);
- `fallback_reason` (если контекст урезан).

---

## Этапы внедрения

### Этап 1 (MVP, board)

- `context_used` + catalog по board;
- `ContextNavigatorAgent` без auto-apply фильтров;
- аналитический ответ по selected/relevant tables.

### Этап 2 (board + query filters)

- включить `ContextExecutionService.apply_query_filters`;
- добавить `suggested_actions.apply_filter`.

### Этап 3 (dashboard scope)

- endpoint для dashboard;
- catalog только по виджетам дашборда.

### Этап 4 (продуктовые улучшения)

- подтверждаемое применение фильтров из чата;
- “показать данные, на которых основан ответ”;
- explainability panel.

---

## Тест-план

### Backend unit

- `ContextExecutionService`: выбор таблиц board/dashboard.
- `ContextNavigatorAgent`: парсинг intent + structured output.
- `AIAssistantController`: сбор `context_used`, корректный fallback.

### Backend integration

- board chat с `selected_node_ids`;
- board chat с query-driven filter;
- dashboard chat с виджетами из разных нод.

### Frontend

- корректный endpoint по scope;
- отображение `context_used`;
- UX: optimistic message, soft autoscroll, suggested actions.

---

## Риски и митигация

- **Риск**: слишком большой контекст -> деградация latency.
  - **Митигация**: жесткие лимиты таблиц/строк, двухступенчатый отбор.
- **Риск**: LLM предлагает некорректный фильтр.
  - **Митигация**: серверная валидация `FilterExpression`.
- **Риск**: несоответствие dashboard widget -> sourceContentNodeId.
  - **Митигация**: graceful skip + telemetry warning.

---

## Критерии готовности (Definition of Done)

- Пользователь может обсуждать данные и получать ответы по board/dashboard контексту.
- Ответ всегда содержит `context_used` (таблицы + фильтры + объем данных).
- В board-mode учитываются таблицы нод доски; в dashboard-mode — только ноды, представленные на дашборде.
- Предложенные фильтры валидны и могут быть применены через существующий Cross-Filter pipeline.
- Есть покрытие unit/integration тестами для новых компонентов.

