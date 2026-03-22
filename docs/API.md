# API документация

## Executive Summary

**GigaBoard REST API** — FastAPI-основанный API для управления аналитическими досками с AI-агентами и real-time событиями (Socket.IO).

**Ключевые концепции:**
- **Source-Content архитектура**: SourceNode (источники + данные) → ContentNode (трансформированные данные) → WidgetNode (визуализации)
- **SourceNode наследует ContentNode** — хранит и конфигурацию источника, и извлечённые данные
- **4 типа узлов**: SourceNode, ContentNode, WidgetNode, CommentNode
- **5 типов связей**: TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN
- **Multi-Agent System**: Orchestrator (Single Path) → 9 ролей в плане (planner, discovery, research, structurizer, analyst, transform_codex, widget_codex, reporter, validator) + шаги `context_filter` и др.; ключ плана `validator` исполняет **QualityGateAgent**; 6 satellite-контроллеров (Transform, TransformSuggestions, Widget, WidgetSuggestions, AI Assistant, Research). См. [`MULTI_AGENT.md`](./MULTI_AGENT.md)
- **Real-time**: Socket.IO для коллаборативных обновлений

**Версионирование**: Все endpoints под `/api/v1` (кроме `/health` и `/ai/resolve`)

---

## Общее описание

REST API на FastAPI для работы с проектами, бордами и узлами с AI-интеграцией. Real-time события через Socket.IO. Все ответы в JSON. Валидация — Pydantic v2.

**Статусы:**
- ✅ — реализовано и работает
- ⚠️ — реализовано, но prefix/формат могут отличаться от идеала

---

## Аутентификация

- JWT (Bearer) для REST
- Socket.IO handshake: передача токена в query/header
- Refresh-токены через отдельный endpoint

---

## 1. Health Check

| Method | Path             | Описание                                 | Статус |
| ------ | ---------------- | ---------------------------------------- | ------ |
| GET    | `/health`        | Базовая проверка                         | ✅      |
| GET    | `/api/v1/health` | Детальная проверка (DB, Redis, GigaChat) | ✅      |

---

## 2. Authentication (`/api/v1/auth`)

| Method | Path                    | Request Body | Response        | Status Code | Описание             |
| ------ | ----------------------- | ------------ | --------------- | ----------- | -------------------- |
| POST   | `/api/v1/auth/register` | `UserCreate` | `TokenResponse` | 201         | Регистрация          |
| POST   | `/api/v1/auth/login`    | `UserLogin`  | `TokenResponse` | 200         | Логин                |
| POST   | `/api/v1/auth/logout`   | —            | `{message}`     | 200         | Выход                |
| GET    | `/api/v1/auth/me`       | —            | `UserResponse`  | 200         | Текущий пользователь |

<details>
<summary>📄 Schemas (развернуть)</summary>

```
UserCreate { email: EmailStr, username: str (3-255), password: str (8-255) }
UserLogin { email: EmailStr, password: str }
UserResponse { id: UUID, email: str, username: str, created_at, updated_at }
TokenResponse { access_token: str, token_type: "bearer", user: UserResponse, expires_in: int }
```

</details>

---

## 3. Projects (`/api/v1/projects`)

| Method | Path                            | Request Body    | Response                          | Status Code | Описание         |
| ------ | ------------------------------- | --------------- | --------------------------------- | ----------- | ---------------- |
| POST   | `/api/v1/projects`              | `ProjectCreate` | `ProjectResponse`                 | 201         | Создать проект   |
| GET    | `/api/v1/projects`              | —               | `list[ProjectWithBoardsResponse]` | 200         | Список проектов  |
| GET    | `/api/v1/projects/{project_id}` | —               | `ProjectResponse`                 | 200         | Получить проект  |
| PUT    | `/api/v1/projects/{project_id}` | `ProjectUpdate` | `ProjectResponse`                 | 200         | Обновить         |
| DELETE | `/api/v1/projects/{project_id}` | —               | —                                 | 204         | Удалить (каскад) |

<details>
<summary>📄 Schemas</summary>

```
ProjectCreate { name: str (1-200), description: str? }
ProjectUpdate { name: str? (1-200), description: str? }
ProjectResponse { id, user_id, name, description?, created_at, updated_at }
ProjectWithBoardsResponse extends ProjectResponse { boards_count: int }
```

</details>

---

## 4. Boards (`/api/v1/boards`)

| Method | Path                        | Request Body         | Response                       | Status Code | Описание         |
| ------ | --------------------------- | -------------------- | ------------------------------ | ----------- | ---------------- |
| POST   | `/api/v1/boards`            | `BoardCreate`        | `BoardResponse`                | 201         | Создать борд     |
| GET    | `/api/v1/boards`            | query: `project_id?` | `list[BoardWithNodesResponse]` | 200         | Список бордов    |
| GET    | `/api/v1/boards/{board_id}` | —                    | `BoardResponse`                | 200         | Получить борд    |
| PUT    | `/api/v1/boards/{board_id}` | `BoardUpdate`        | `BoardResponse`                | 200         | Обновить         |
| DELETE | `/api/v1/boards/{board_id}` | —                    | —                              | 204         | Удалить (каскад) |

<details>
<summary>📄 Schemas</summary>

```
BoardCreate { name: str (1-200), description: str?, project_id: UUID }
BoardUpdate { name: str?, description: str? }
BoardResponse { id, project_id, user_id, name, description?, created_at, updated_at }
BoardWithNodesResponse extends BoardResponse { widget_nodes_count, comment_nodes_count }
```

</details>

---

## 5. Source Nodes (`/api/v1/source-nodes`)

> **⚠️ URL-структура**: Flat URLs без `{boardId}` в пути. `board_id` передаётся в теле запроса при создании.

| Method | Path                                        | Request Body       | Response                   | Status Code | Описание                          |
| ------ | ------------------------------------------- | ------------------ | -------------------------- | ----------- | --------------------------------- |
| GET    | `/api/v1/source-nodes/vitrina`              | —                  | `SourceVitrinaResponse`    | 200         | Каталог типов источников (public) |
| POST   | `/api/v1/source-nodes/`                     | `SourceNodeCreate` | `SourceNodeResponse`       | 201         | Создать SourceNode                |
| GET    | `/api/v1/source-nodes/{source_id}`          | —                  | `SourceNodeResponse`       | 200         | Получить SourceNode               |
| GET    | `/api/v1/source-nodes/board/{board_id}`     | —                  | `list[SourceNodeResponse]` | 200         | Все SourceNode доски              |
| PUT    | `/api/v1/source-nodes/{source_id}`          | `SourceNodeUpdate` | `SourceNodeResponse`       | 200         | Обновить                          |
| DELETE | `/api/v1/source-nodes/{source_id}`          | —                  | —                          | 204         | Удалить                           |
| POST   | `/api/v1/source-nodes/{source_id}/refresh`  | —                  | `SourceNodeResponse`       | 200         | Перезагрузить данные              |
| POST   | `/api/v1/source-nodes/{source_id}/validate` | —                  | `dict`                     | 200         | Валидировать конфигурацию         |

<details>
<summary>📄 Schemas</summary>

```
SourceTypeEnum = "csv" | "json" | "excel" | "document" | "api" | "database" | "research" | "manual" | "stream"

SourceNodeCreate {
    source_type: SourceTypeEnum
    config: dict              // Source-specific config
    metadata: dict = {}
    position: dict = {"x": 0, "y": 0}
    board_id: UUID
    created_by: UUID
    data: dict?               // Initial data
}

SourceNodeUpdate { config?, metadata?, position?, data? }

SourceNodeResponse {
    id, board_id, created_by, created_at, updated_at,
    node_type: "source_node",
    source_type: SourceTypeEnum,
    config: dict,
    content: dict?,           // {text, tables} — inherited from ContentNode
    lineage: dict?,
    metadata: dict,
    position: dict
}

SourceVitrinaResponse { items: list[SourceVitrinaItem] }
SourceVitrinaItem { source_type, display_name, icon, description }
```

</details>

### Конфигурации по типам источников

<details>
<summary>📄 Source Config Schemas (развернуть)</summary>

```
CSVSourceConfig      { file_id, delimiter?, encoding?, has_header=true, skip_rows=0, max_rows? }
JSONSourceConfig     {
    file_id,
    filename?,
    mime_type?,
    size_bytes?,
    json_path="$",
    schema_snapshot?: {
        version: "1.0",
        root_type?: "object"|"array"|"scalar",
        nodes: [{ path, node_kind, value_types, cardinality? }]
    },
    mapping_spec?: {
        version: "1.0",
        tables: [{
            id, name, base_path,
            pk?: { column, strategy? },
            fk?: [{ column, ref_table, ref_column }],
            columns: [{ name, type, path, nullable? }]
        }]
    },
    generation_meta?: { generated_by?, confidence?, warnings? }
}
ExcelSourceConfig    { file_id, filename, has_header, analysis_mode="smart", max_rows?, detected_regions: [{sheet_name, start_row, start_col, end_row, end_col, header_row, table_name, column_overrides, selected_columns}] }
DocumentSourceConfig { file_id, extraction_prompt?, extraction_code? }
APISourceConfig      { url, method="GET", headers={}, params={}, body?, timeout_seconds=30, pagination? }
DatabaseSourceConfig { db_type, host?, port?, database?, username?, password?, path?, tables }
ResearchSourceConfig { initial_prompt, context={} }
ManualSourceConfig   { columns: [{name, type}], data=[] }
StreamSourceConfig   { stream_type: "websocket"|"sse"|"kafka", url, buffer_strategy="accumulate" }
```

</details>

#### JSON Source: контракт и поведение

- При создании/обновлении JSON-источника backend извлекает `schema_snapshot` и использует `mapping_spec` для построения таблиц.
- Если `mapping_spec` отсутствует, backend выполняет авто-нормализацию и сохраняет результат в `config.mapping_spec`.
- `PUT /api/v1/source-nodes/{source_id}` для `source_type=json` с изменённым `config.mapping_spec` инициирует повторное извлечение данных.
- `POST /api/v1/source-nodes/{source_id}/refresh` повторно использует сохранённый `mapping_spec` (воспроизводимый refresh).
- Результат извлечения возвращается в `SourceNodeResponse.content.tables` в unified формате (см. `docs/DATA_FORMATS.md`).

### Research Chat (`/api/v1/research`)

Чат исследования для диалога **AI Research** (без обязательной привязки к доске). Тот же Orchestrator, что и в админском Playground; отличие — формирование `user_request` в `ResearchController` (см. [AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md](./AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md) §2.0.1).

| Method | Path                       | Request Body          | Response               | Статус | Описание                                      |
| ------ | -------------------------- | --------------------- | ---------------------- | ------ | --------------------------------------------- |
| POST   | `/api/v1/research/chat`    | `ResearchChatRequest` | `ResearchChatResponse` | ✅      | Сообщение → narrative, tables, sources, session_id |

**Аутентификация**: JWT, любой авторизованный пользователь (не только admin).

<details>
<summary>📄 Schemas (Research Chat)</summary>

```
ResearchChatMessage { role: str, content: str }
ResearchChatRequest {
  message: str (1..15000)
  session_id?: str
  chat_history?: list[ResearchChatMessage]
}
ResearchSourceRef { url: str, title: str }
ResearchChatResponse {
  narrative: str
  tables: list[dict]   // name, columns, rows (ContentTable-like)
  sources: list[ResearchSourceRef]
  session_id: str
  execution_time_ms?: int
  plan?: dict
}
```

</details>

---

## 6. Content Nodes (`/api/v1/content-nodes`)

> **⚠️ URL-структура**: Flat URLs без `{boardId}` в пути. `board_id` передаётся в теле запроса при создании.

### CRUD

| Method | Path                                     | Request Body        | Response                    | Status Code | Описание              |
| ------ | ---------------------------------------- | ------------------- | --------------------------- | ----------- | --------------------- |
| POST   | `/api/v1/content-nodes/`                 | `ContentNodeCreate` | `ContentNodeResponse`       | 201         | Создать ContentNode   |
| GET    | `/api/v1/content-nodes/{content_id}`     | —                   | `ContentNodeResponse`       | 200         | Получить ContentNode  |
| GET    | `/api/v1/content-nodes/board/{board_id}` | —                   | `list[ContentNodeResponse]` | 200         | Все ContentNode доски |
| PUT    | `/api/v1/content-nodes/{content_id}`     | `ContentNodeUpdate` | `ContentNodeResponse`       | 200         | Обновить              |
| DELETE | `/api/v1/content-nodes/{content_id}`     | —                   | —                           | 204         | Удалить               |

### Трансформации

| Method | Path                                 | Request Body                                                                            | Response                     | Описание                                                  |
| ------ | ------------------------------------ | --------------------------------------------------------------------------------------- | ---------------------------- | --------------------------------------------------------- |
| POST   | `/{content_id}/transform/preview`    | `{prompt, selected_node_ids?}`                                                          | `dict`                       | Генерация кода трансформации (без выполнения)             |
| POST   | `/{content_id}/transform/test`       | `{code, transformation_id, selected_node_ids?}`                                         | `dict`                       | Тестирование кода, возврат результатов без создания ноды  |
| POST   | `/{content_id}/transform/iterative`  | `TransformIterativeRequest`                                                             | `TransformIterativeResponse` | Итеративная трансформация через AI-чат                    |
| POST   | `/{content_id}/transform/execute`    | `{code, transformation_id?, description?, prompt?, selected_node_ids, target_node_id?}` | `dict`                       | Выполнение кода и создание/обновление ContentNode + edge  |
| POST   | `/{content_id}/transform`            | `{prompt}`                                                                              | `dict`                       | Трансформация через TransformationController               |
| POST   | `/content-nodes/transform`           | `TransformRequest`                                                                      | `TransformResponse`          | Трансформация через прямой Python код                     |
| POST   | `/{content_id}/transform-multiagent` | `{user_prompt, existing_code?, ...}`                                                    | `dict`                       | Трансформация через Orchestrator (TransformCodexAgent) |

### Визуализации

| Method | Path                                 | Request Body                | Response                     | Описание                                                |
| ------ | ------------------------------------ | --------------------------- | ---------------------------- | ------------------------------------------------------- |
| POST   | `/{content_id}/visualize`            | `VisualizeRequest`          | `VisualizeResponse`          | Создать WidgetNode из ContentNode (WidgetController) |
| POST   | `/{content_id}/visualize-iterative`  | `VisualizeIterativeRequest` | `VisualizeIterativeResponse` | Итеративная генерация виджета (чат)                     |
| POST   | `/{content_id}/visualize-multiagent` | `VisualizeIterativeRequest` | `VisualizeIterativeResponse` | Визуализация через Orchestrator (WidgetCodexAgent)   |

### Data Lineage и утилиты

| Method | Path                       | Response                    | Описание                        |
| ------ | -------------------------- | --------------------------- | ------------------------------- |
| GET    | `/{content_id}/lineage`    | `list[dict]`                | Полная цепочка data lineage     |
| GET    | `/{content_id}/downstream` | `list[ContentNodeResponse]` | Downstream ContentNodes         |
| POST   | `/content-nodes/get-table` | `GetTableResponse`          | Получить таблицу из ContentNode |

### AI-рекомендации

| Method | Path                                          | Request Body                     | Response                     | Описание                         |
| ------ | --------------------------------------------- | -------------------------------- | ---------------------------- | -------------------------------- |
| POST   | `/{content_id}/analyze-suggestions`           | `SuggestionAnalysisRequest`      | `SuggestionAnalysisResponse` | AI-рекомендации по виджету       |
| POST   | `/{content_id}/analyze-transform-suggestions` | `{chat_history?, current_code?}` | `dict`                       | AI-рекомендации по трансформации |

<details>
<summary>📄 Schemas</summary>

```
ContentTable { id, name, columns: [{name, type}], rows: [dict], row_count, column_count, preview_row_count }
ContentData { text: str = "", tables: list[ContentTable] = [] }
DataLineage { source_node_id?, transformation_id?, operation, parent_content_ids, timestamp, agent? }

ContentNodeCreate { content, lineage, metadata={}, position={"x":0,"y":0}, board_id: UUID }
ContentNodeUpdate { content?, lineage?, metadata?, position? }
ContentNodeResponse { id, board_id, created_at, updated_at, node_type, content, lineage, metadata, position }

VisualizeRequest { user_prompt?, widget_name? (max 200), auto_refresh=true, position? }
VisualizeResponse { widget_node_id: UUID, edge_id: UUID, status, error? }

VisualizeIterativeRequest { user_prompt, existing_widget_code?, chat_history? }
VisualizeIterativeResponse { widget_code?, widget_name?, description, status, error?, html_code, css_code, js_code }

TransformRequest { source_content_ids: [UUID], transformation_code, output_description? }
TransformResponse { content_node_id: UUID, status, execution_time_ms?, error? }

SuggestionAnalysisRequest { chat_history=[], current_widget_code?, max_suggestions=5 }
SuggestionAnalysisResponse { suggestions: [Suggestion], analysis_summary }
Suggestion { id, type, priority, title, description, prompt, reasoning }
```

</details>

---

## 7. Extraction (`/api/v1/boards/{board_id}`)

| Method | Path                                                              | Request Body        | Response             | Описание                     |
| ------ | ----------------------------------------------------------------- | ------------------- | -------------------- | ---------------------------- |
| POST   | `/api/v1/boards/{board_id}/source-nodes/{source_node_id}/extract` | `ExtractionRequest` | `ExtractionResponse` | Извлечь данные из SourceNode |

<details>
<summary>📄 Schemas</summary>

```
ExtractionRequest { position: dict = {"x": 0, "y": 0}, preview_rows: int? }
ExtractionResponse { content_node: dict, extract_edge: dict, summary: {tables_created, total_rows, source_type} }
```

</details>

---

## 8. Widget Nodes (`/api/v1/boards/{board_id}/widget-nodes`)

| Method | Path                                          | Request Body       | Response                   | Status Code | Описание                |
| ------ | --------------------------------------------- | ------------------ | -------------------------- | ----------- | ----------------------- |
| POST   | `/api/v1/boards/{board_id}/widget-nodes`      | `WidgetNodeCreate` | `WidgetNodeResponse`       | 201         | Создать WidgetNode      |
| GET    | `/api/v1/boards/{board_id}/widget-nodes`      | —                  | `list[WidgetNodeResponse]` | 200         | Список WidgetNode доски |
| GET    | `/api/v1/boards/{board_id}/widget-nodes/{id}` | —                  | `WidgetNodeResponse`       | 200         | Получить WidgetNode     |
| PATCH  | `/api/v1/boards/{board_id}/widget-nodes/{id}` | `WidgetNodeUpdate` | `WidgetNodeResponse`       | 200         | Обновить                |
| DELETE | `/api/v1/boards/{board_id}/widget-nodes/{id}` | —                  | —                          | 204         | Удалить                 |

<details>
<summary>📄 Schemas</summary>

```
WidgetNodeCreate { name (max 200), description, html_code, css_code?, js_code?, config?, auto_refresh=true,
                   refresh_interval?, generated_by?, generation_prompt?, x=0, y=0, width?, height? }
WidgetNodeUpdate { name?, description?, html_code?, css_code?, js_code?, config?, x?, y?, width?, height?,
                   auto_refresh?, refresh_interval? }
WidgetNodeResponse { id, board_id, node_type, name, description, html_code, css_code, js_code, config,
                     auto_refresh, refresh_interval, generated_by, generation_prompt,
                     x, y, width, height, created_at, updated_at }
```

</details>

---

## 9. Comment Nodes (`/api/v1/boards/{board_id}/comment-nodes`)

| Method | Path                             | Request Body               | Response                    | Status Code | Описание          |
| ------ | -------------------------------- | -------------------------- | --------------------------- | ----------- | ----------------- |
| POST   | `.../comment-nodes`              | `CommentNodeCreate`        | `CommentNodeResponse`       | 201         | Создать           |
| GET    | `.../comment-nodes`              | —                          | `list[CommentNodeResponse]` | 200         | Список            |
| GET    | `.../comment-nodes/{id}`         | —                          | `CommentNodeResponse`       | 200         | Получить          |
| PATCH  | `.../comment-nodes/{id}`         | `CommentNodeUpdate`        | `CommentNodeResponse`       | 200         | Обновить          |
| DELETE | `.../comment-nodes/{id}`         | —                          | —                           | 204         | Удалить           |
| POST   | `.../comment-nodes/{id}/resolve` | query: `is_resolved?=true` | `CommentNodeResponse`       | 200         | Resolve/unresolve |

<details>
<summary>📄 Schemas</summary>

```
CommentNodeCreate { content, format_type="markdown", color? (hex), config?, x=0, y=0, width?, height? }
CommentNodeUpdate { content?, format_type?, color?, config?, x?, y?, width?, height?, is_resolved? }
CommentNodeResponse { id, board_id, node_type, content, format_type, color, config,
                      author_id, is_resolved, resolved_at?, resolved_by?,
                      x, y, width, height, created_at, updated_at }
```

</details>

---

## 10. Edges (`/api/v1/boards/{board_id}/edges`)

| Method | Path                  | Request Body | Response           | Status Code | Описание              |
| ------ | --------------------- | ------------ | ------------------ | ----------- | --------------------- |
| POST   | `.../edges`           | `EdgeCreate` | `EdgeResponse`     | 201         | Создать связь         |
| GET    | `.../edges`           | —            | `EdgeListResponse` | 200         | Список связей доски   |
| GET    | `.../edges/{edge_id}` | —            | `EdgeResponse`     | 200         | Получить связь        |
| PATCH  | `.../edges/{edge_id}` | `EdgeUpdate` | `EdgeResponse`     | 200         | Обновить              |
| DELETE | `.../edges/{edge_id}` | —            | —                  | 204         | Удалить (soft delete) |

**Типы связей (EdgeType)**: `TRANSFORMATION`, `VISUALIZATION`, `COMMENT`, `DRILL_DOWN`, `REFERENCE`

<details>
<summary>📄 Schemas</summary>

```
EdgeCreate {
    source_node_id: UUID,      // Примечание: в коде используется source_node_id/target_node_id (не from_node_id/to_node_id)
    source_node_type: str,     // source_node, content_node, widget_node, comment_node
    target_node_id: UUID,
    target_node_type: str,
    edge_type: EdgeType,
    label?: str (max 200),
    transformation_code?: str,
    transformation_params?: dict,
    visual_config?: dict
}

EdgeUpdate { label?, transformation_code?, transformation_params?, visual_config?, parameter_mapping? }

EdgeResponse extends EdgeCreate { id, board_id, created_at, updated_at, is_valid, validation_errors? }
EdgeListResponse { edges: [EdgeResponse], total: int }
```

</details>

---

## 11. AI Assistant

### 11.1 Доска (`/api/v1/boards/{board_id}/ai`)

История чата хранится в PostgreSQL (`chat_messages`).

| Method | Path                               | Request Body                     | Response              | Описание                    |
| ------ | ---------------------------------- | -------------------------------- | --------------------- | --------------------------- |
| POST   | `.../ai/chat`                      | `AIChatRequest`                  | `AIChatResponse`      | Отправить сообщение AI      |
| GET    | `.../ai/chat/history/me`           | query: `limit?=50`               | `ChatHistoryResponse` | История чата текущего юзера |
| GET    | `.../ai/chat/history`              | query: `session_id`, `limit?=50` | `ChatHistoryResponse` | История по сессии           |
| DELETE | `.../ai/chat/session/{session_id}` | —                                | `{message}`           | Удалить сессию чата         |

### 11.2 Дашборд (`/api/v1/dashboards/{dashboard_id}/ai`)

Тот же контракт запроса/ответа (`AIChatRequest` / `AIChatResponse`), но контекст `mode: dashboard` и история сессий — в **Redis** (не в `chat_messages`). См. `apps/backend/app/routes/ai_assistant.py`.

| Method | Path                               | Request Body                     | Response              | Описание                    |
| ------ | ---------------------------------- | -------------------------------- | --------------------- | --------------------------- |
| POST   | `.../ai/chat`                      | `AIChatRequest`                  | `AIChatResponse`      | Отправить сообщение AI      |
| GET    | `.../ai/chat/history/me`           | query: `limit?=50`               | `ChatHistoryResponse` | Последняя сессия из Redis   |
| GET    | `.../ai/chat/history`              | query: `session_id`, `limit?=50` | `ChatHistoryResponse` | История сессии из Redis     |
| DELETE | `.../ai/chat/session/{session_id}` | —                                | `{message}`           | Удалить сессию в Redis      |

**Стриминг с прогрессом** для дашборда — через Socket.IO (см. ниже), не через отдельный REST NDJSON.

<details>
<summary>📄 Schemas</summary>

```
AIChatRequest { message: str (1-10000), session_id?: UUID, context?: dict }
AIChatResponse { response: str, session_id: UUID, suggested_actions?: [SuggestedAction], context_used?: dict }
SuggestedAction { action, description, params? }
ChatHistoryResponse { messages: [ChatMessageSchema], session_id?, total_messages: int }
```

</details>

---

## 12. AI Resolver (`/ai`)

> **⚠️ Prefix**: `/ai` без `/api/v1` — endpoint вне версионированного API.

| Method | Path          | Request Body | Response | Описание                                    |
| ------ | ------------- | ------------ | -------- | ------------------------------------------- |
| POST   | `/ai/resolve` | `dict`       | `dict`   | Batch AI resolution для семантических задач |

**Request**: `{ values: [str], task_description: str, result_format?: str, chunk_size?: int }`

**Response**: `{ results: [...], count: int, task_description: str }`

**Основное применение** — через `gb.ai_resolve_batch()` в коде трансформаций:
```python
names = df['name'].tolist()
genders = gb.ai_resolve_batch(names, "определи пол: M или F")
df['gender'] = genders
```

См. [AI_RESOLVER_SYSTEM.md](./AI_RESOLVER_SYSTEM.md)

---

## 13. User Profile & LLM Settings (`/api/v1/users/me/*`)

Настройки профиля пользователя и предпочитаемого LLM-провайдера.

### AI / LLM настройки (`/api/v1/users/me/ai-settings`)

| Method | Path                                   | Request Body             | Response                   | Описание                                      |
| ------ | -------------------------------------- | ------------------------ | -------------------------- | --------------------------------------------- |
| GET    | `/api/v1/users/me/ai-settings`         | —                        | `UserAISettingsResponse`   | Получить AI/LLM-настройки текущего пользователя |
| PUT    | `/api/v1/users/me/ai-settings`         | `UserAISettingsUpdate`   | `UserAISettingsResponse`   | Обновить настройки и при необходимости API-ключ |
| POST   | `/api/v1/users/me/ai-settings/test`    | `UserAISettingsUpdate?`  | `UserAISettingsTestResponse` | Тест подключения к выбранному провайдеру   |

#### Schemas

```
LLMProvider = "gigachat" | "external_openai_compat"

UserAISettingsResponse {
    user_id: UUID
    provider: LLMProvider
    gigachat_model?: str
    gigachat_scope?: str
    external_base_url?: str
    external_default_model?: str
    external_timeout_seconds?: int
    temperature?: float
    max_tokens?: int
    has_external_api_key: bool
    preferred_style?: dict
    multi_agent_settings?: dict  // только admin; для остальных в ответе не возвращается
}

UserAISettingsUpdate {
    provider: LLMProvider

    // GigaChat (опционально)
    gigachat_model?: str
    gigachat_scope?: str

    // Внешний OpenAI-совместимый провайдер
    external_base_url?: str
    external_default_model?: str
    external_timeout_seconds?: int

    // Новый/обновлённый API-ключ (write-only)
    external_api_key?: str

    // Общие параметры генерации
    temperature?: float
    max_tokens?: int

    preferred_style?: dict
    multi_agent_settings?: dict  // optional; если передано — сохранить (null — очистить)
}

UserAISettingsTestResponse {
    ok: bool
    provider: LLMProvider
    message: str
    details?: dict
}
```

**Поведение:**

- `provider = "gigachat"` — используется системный GigaChat (см. конфиг backend), поля `gigachat_model`/`gigachat_scope` задают только пользовательские предпочтения.
- `provider = "external_openai_compat"`:
  - `external_base_url` по умолчанию `https://api.openai.com/v1`;
  - `external_default_model` и `temperature`/`max_tokens` задают дефолты для Multi-Agent системы;
  - `external_api_key` сохраняется в зашифрованном виде в отдельной сущности `UserSecret`, в ответе ключ никогда не возвращается — только флаг `has_external_api_key`.
- `multi_agent_settings`: словарь с теми же ключами, что переменные окружения `MULTI_AGENT_*`; применяется при запуске оркестратора для данного пользователя (приоритет над env). Чтение и запись в API — только для роли **admin**; в ответе для не-админов поле не возвращается.
- `POST /ai-settings/test`:
  - использует текущие сохранённые настройки + значения из тела запроса (они имеют приоритет);
  - на MVP-этапе выполняет только валидацию параметров (формат URL, наличие ключа) и возвращает диагностическое сообщение; в следующих итерациях будет вызывать реальный OpenAI-совместимый endpoint.

### Admin LLM settings (`/api/v1/admin/*`)

Управление системными LLM-пресетами и привязками агентов (только `admin`).

| Method | Path                                   | Request Body              | Response                          | Описание |
| ------ | -------------------------------------- | ------------------------- | --------------------------------- | -------- |
| GET    | `/api/v1/admin/llm-configs`            | —                         | `list[LLMConfigResponse]`         | Список LLM-пресетов |
| POST   | `/api/v1/admin/llm-configs`            | `LLMConfigCreate`         | `LLMConfigResponse`               | Создать пресет |
| GET    | `/api/v1/admin/llm-configs/{id}`       | —                         | `LLMConfigResponse`               | Получить пресет |
| PATCH  | `/api/v1/admin/llm-configs/{id}`       | `LLMConfigUpdate`         | `LLMConfigResponse`               | Обновить пресет |
| DELETE | `/api/v1/admin/llm-configs/{id}`       | —                         | —                                 | Удалить пресет |
| GET    | `/api/v1/admin/llm-settings`           | —                         | `SystemLLMSettingsResponse`       | Получить default + overrides |
| PATCH  | `/api/v1/admin/llm-settings`           | `SystemLLMSettingsUpdate` | `SystemLLMSettingsResponse`       | Обновить модель по умолчанию |
| GET    | `/api/v1/admin/agent-llm-overrides`    | —                         | `list[AgentLLMOverrideItem]`      | Список привязок агента |
| PUT    | `/api/v1/admin/agent-llm-overrides`    | `AgentLLMOverridesSet`    | `list[AgentLLMOverrideItem]`      | Полная замена привязок |

`AgentLLMOverrideItem.runtime_options` поддерживает:

```json
{
  "timeout_sec": 45,
  "max_retries": 1,
  "context_ladder": ["full", "compact", "minimal"],
  "max_items": 30,
  "max_total_chars": 100000,
  "task_overrides": {
    "replan": {
      "timeout_sec": 60,
      "context_ladder": ["compact", "minimal"],
      "max_items": 35,
      "max_total_chars": 120000
    }
  }
}
```

Валидация `runtime_options`:
- `context_ladder`: только `full`, `compact`, `minimal`;
- `timeout_sec`: `1..1800`;
- `max_retries`: `0..10`;
- `max_items`: `1..200`;
- `max_total_chars`: `1000..500000`.

---

## 14. Files (`/api/v1/files`)

| Method | Path                                       | Request Body        | Response                                      | Описание                  |
| ------ | ------------------------------------------ | ------------------- | --------------------------------------------- | ------------------------- |
| POST   | `/api/v1/files/upload`                      | multipart/form-data | `{file_id, filename, mime_type, size_bytes}`  | Загрузить файл            |
| GET    | `/api/v1/files/download/{file_id}`         | —                   | File/Redirect                                 | Скачать файл              |
| GET    | `/api/v1/files/image/{file_id}`             | —                   | Image (public)                                | Публичное изображение     |
| POST   | `/api/v1/files/{file_id}/analyze-csv`      | —                   | `CSVAnalysisResult`                           | Анализ структуры CSV      |
| POST   | `/api/v1/files/{file_id}/analyze-excel`    | —                   | `ExcelAnalysisResult`                         | Анализ Excel              |
| POST   | `/api/v1/files/{file_id}/excel-preview`    | —                   | `ExcelPreviewResponse`                        | Превью листов Excel       |
| POST   | `/api/v1/files/{file_id}/analyze-excel-smart` | —                 | `SmartExcelAnalysisResult`                    | Умный анализ областей     |
| POST   | `/api/v1/files/{file_id}/analyze-document` | —                   | `DocumentAnalysisResult`                      | Анализ документа          |
| POST   | `/api/v1/files/{file_id}/extract-document-chat` | body             | `DocumentExtractionChatResponse`              | Итеративное извлечение    |

<details>
<summary>📄 CSVAnalysisResult</summary>

```
CSVAnalysisResult { delimiter, encoding, has_header, rows_count, columns: [{name, type, sample_values}], preview_rows }
```

</details>

---

## 15. Database (`/api/v1/database`)

| Method | Path                               | Request Body                | Response                     | Описание              |
| ------ | ---------------------------------- | --------------------------- | ---------------------------- | --------------------- |
| POST   | `/api/v1/database/test-connection` | `DatabaseConnectionRequest` | `DatabaseConnectionResponse` | Тест подключения к БД |
| POST   | `/api/v1/database/preview`          | —                           | `TablePreviewResponse`       | Превью таблицы БД     |
| POST   | `/api/v1/database/table-columns`   | —                           | —                            | Список колонок таблицы|

<details>
<summary>📄 Schemas</summary>

```
DatabaseConnectionRequest { database_type: str, host?, port?, database?, user?, password?, uri?, path? }
DatabaseConnectionResponse { success: bool, database_type, tables: [str], table_count: int }
```

</details>

---

## 16. Dimensions (`/api/v1/projects/{project_id}/dimensions`)

Измерения для Cross-Filter. См. [CROSS_FILTER_SYSTEM.md](./CROSS_FILTER_SYSTEM.md).

| Method | Path                                                                 | Request Body   | Response                           | Описание                |
| ------ | -------------------------------------------------------------------- | -------------- | ---------------------------------- | ----------------------- |
| GET    | `/api/v1/projects/{project_id}/dimensions`                           | —              | `list[DimensionResponse]`          | Список измерений        |
| POST   | `/api/v1/projects/{project_id}/dimensions`                           | `DimensionCreate` | `DimensionResponse`             | Создать измерение       |
| GET    | `/api/v1/projects/{project_id}/dimensions/{dim_id}`                  | —              | `DimensionResponse`                | Получить измерение      |
| PUT    | `/api/v1/projects/{project_id}/dimensions/{dim_id}`                  | `DimensionUpdate` | `DimensionResponse`             | Обновить                |
| DELETE | `/api/v1/projects/{project_id}/dimensions/{dim_id}`                  | —              | 204                                | Удалить                 |
| POST   | `/api/v1/projects/{project_id}/dimensions/merge`                     | body           | `MergeDimensionsResponse`          | Объединить измерения    |
| GET    | `/api/v1/projects/{project_id}/dimensions/{dim_id}/mappings`         | —              | `list[DimensionColumnMappingResponse]` | Маппинги столбцов  |
| POST   | `/api/v1/projects/{project_id}/dimensions/{dim_id}/mappings`         | body           | `DimensionColumnMappingResponse`   | Добавить маппинг        |
| DELETE | `/api/v1/projects/{project_id}/dimensions/mappings/{mapping_id}`     | —              | 204                                | Удалить маппинг         |
| GET    | `/api/v1/projects/{project_id}/dimensions/{dim_id}/values`            | —              | —                                  | Уникальные значения     |

---

## 17. Board Filters (`/api/v1/boards/{board_id}/filters`)

Активные фильтры доски (Cross-Filter). Хранение in-memory по умолчанию (для production — Redis).

Тот же бэкендный пересчёт **`_compute_filtered_pipeline`** используется мультиагентным оркестратором для тулов `readTableData` / `readTableListFromContentNodes` (при `MULTI_AGENT_TOOLS_USE_FILTERED_PIPELINE`), см. **`docs/CROSS_FILTER_SYSTEM.md`** §3.5 и **`docs/MULTI_AGENT.md`**.

| Method | Path                                                           | Request Body        | Response                 | Описание              |
| ------ | -------------------------------------------------------------- | ------------------- | ------------------------ | --------------------- |
| GET    | `/api/v1/boards/{board_id}/filters`                            | —                   | `ActiveFiltersResponse`  | Текущие активные      |
| PUT    | `/api/v1/boards/{board_id}/filters`                            | `ActiveFiltersUpdate` | `ActiveFiltersResponse` | Установить фильтры    |
| POST   | `/api/v1/boards/{board_id}/filters/clear`                      | —                   | `ActiveFiltersResponse`  | Сбросить              |
| POST   | `/api/v1/boards/{board_id}/filters/apply-preset/{preset_id}`   | —                   | `ActiveFiltersResponse`  | Применить пресет      |
| POST   | `/api/v1/boards/{board_id}/filters/compute-filtered`            | body (node_ids, filters) | `{nodes: [...]}`   | Пересчёт pipeline с фильтром |

---

## 18. Dashboard Filters (`/api/v1/dashboards/{dashboard_id}/filters`)

Активные фильтры дашборда. Контракт аналогичен Board Filters.

| Method | Path                                                                 | Request Body        | Response                 | Описание              |
| ------ | -------------------------------------------------------------------- | ------------------- | ------------------------ | --------------------- |
| GET    | `/api/v1/dashboards/{dashboard_id}/filters`                         | —                   | `ActiveFiltersResponse`  | Текущие активные      |
| PUT    | `/api/v1/dashboards/{dashboard_id}/filters`                         | `ActiveFiltersUpdate` | `ActiveFiltersResponse` | Установить фильтры    |
| POST   | `/api/v1/dashboards/{dashboard_id}/filters/clear`                   | —                   | `ActiveFiltersResponse`  | Сбросить              |
| POST   | `/api/v1/dashboards/{dashboard_id}/filters/apply-preset/{preset_id}` | —                   | `ActiveFiltersResponse`  | Применить пресет      |
| POST   | `/api/v1/dashboards/{dashboard_id}/filters/compute-filtered`         | body                | `{nodes: [...]}`         | Пересчёт с фильтром   |

---

## 19. Filter Presets (`/api/v1/projects/{project_id}/filter-presets`)

Сохранённые наборы фильтров (проектный скоуп).

| Method | Path                                                                   | Request Body          | Response                | Описание        |
| ------ | ---------------------------------------------------------------------- | --------------------- | ----------------------- | --------------- |
| GET    | `/api/v1/projects/{project_id}/filter-presets`                         | query: scope?, target_id? | `list[FilterPresetResponse]` | Список пресетов |
| POST   | `/api/v1/projects/{project_id}/filter-presets`                         | `FilterPresetCreate`  | `FilterPresetResponse`  | Создать         |
| GET    | `/api/v1/projects/{project_id}/filter-presets/{preset_id}`             | —                     | `FilterPresetResponse`  | Получить        |
| PUT    | `/api/v1/projects/{project_id}/filter-presets/{preset_id}`             | `FilterPresetUpdate`  | `FilterPresetResponse`  | Обновить        |
| DELETE | `/api/v1/projects/{project_id}/filter-presets/{preset_id}`             | —                     | 204                      | Удалить         |

---

## 20. Dashboards (`/api/v1/dashboards`)

Дашборды — презентационный слой. См. [DASHBOARD_SYSTEM.md](./DASHBOARD_SYSTEM.md).

| Method | Path                                           | Request Body           | Response                    | Описание           |
| ------ | ---------------------------------------------- | ---------------------- | --------------------------- | ------------------ |
| POST   | `/api/v1/dashboards`                           | `DashboardCreate`      | `DashboardResponse`         | Создать дашборд    |
| GET    | `/api/v1/dashboards`                           | query: project_id?     | `list[DashboardResponse]`   | Список дашбордов   |
| GET    | `/api/v1/dashboards/{dashboard_id}`             | —                      | `DashboardResponse`         | Получить           |
| PUT    | `/api/v1/dashboards/{dashboard_id}`            | `DashboardUpdate`      | `DashboardResponse`         | Обновить           |
| DELETE | `/api/v1/dashboards/{dashboard_id}`            | —                      | 204                         | Удалить            |
| POST   | `/api/v1/dashboards/{dashboard_id}/items`      | `DashboardItemCreate`  | `DashboardItemResponse`    | Добавить элемент   |
| PUT    | `/api/v1/dashboards/{dashboard_id}/items/{item_id}` | `DashboardItemUpdate` | `DashboardItemResponse`    | Обновить элемент   |
| DELETE | `/api/v1/dashboards/{dashboard_id}/items/{item_id}` | —                  | 204                         | Удалить элемент   |
| PUT    | `/api/v1/dashboards/{dashboard_id}/items/reorder` | body                | —                           | Z-order элементов  |
| POST   | `/api/v1/dashboards/{dashboard_id}/clone`      | —                      | `DashboardResponse`         | Клонировать        |
| GET    | `/api/v1/dashboards/{dashboard_id}/thumbnail`  | —                      | —                           | Thumbnail URL      |
| DELETE | `/api/v1/dashboards/{dashboard_id}/thumbnail`  | —                      | —                           | Удалить thumbnail  |

---

## 21. Library (`/api/v1/projects/{project_id}/library`)

Библиотека виджетов и таблиц проекта (для размещения на дашбордах).

| Method | Path                                                                         | Request Body    | Response                      | Описание            |
| ------ | ---------------------------------------------------------------------------- | --------------- | ----------------------------- | ------------------- |
| POST   | `/api/v1/projects/{project_id}/library/widgets`                              | body            | `ProjectWidgetResponse`       | Сохранить виджет    |
| GET    | `/api/v1/projects/{project_id}/library/widgets`                              | —               | `list[ProjectWidgetResponse]` | Список виджетов     |
| GET    | `/api/v1/projects/{project_id}/library/widgets/{widget_id}`                   | —               | `ProjectWidgetResponse`       | Получить виджет     |
| PUT    | `/api/v1/projects/{project_id}/library/widgets/{widget_id}`                   | body            | `ProjectWidgetResponse`       | Обновить            |
| DELETE | `/api/v1/projects/{project_id}/library/widgets/{widget_id}`                  | —               | 204                           | Удалить             |
| POST   | `/api/v1/projects/{project_id}/library/tables`                               | body            | `ProjectTableResponse`        | Сохранить таблицу   |
| GET    | `/api/v1/projects/{project_id}/library/tables`                               | —               | `list[ProjectTableResponse]`  | Список таблиц       |
| GET    | `/api/v1/projects/{project_id}/library/tables/{table_id}`                     | —               | `ProjectTableResponse`        | Получить таблицу    |
| PUT    | `/api/v1/projects/{project_id}/library/tables/{table_id}`                    | body            | `ProjectTableResponse`        | Обновить            |
| DELETE | `/api/v1/projects/{project_id}/library/tables/{table_id}`                    | —               | 204                           | Удалить             |

---

## 22. Public (`/api/v1/public`)

Публичный доступ без авторизации (шаринг дашбордов).

| Method | Path                               | Query/Request   | Response                    | Описание              |
| ------ | ---------------------------------- | --------------- | --------------------------- | --------------------- |
| GET    | `/api/v1/public/dashboards/{token}` | password?       | `PublicDashboardResponse`   | Просмотр дашборда по токену |

---

## 23. Content Nodes — Dimension mappings

Эндпоинты для Cross-Filter (маппинг столбцов к измерениям):

| Method | Path                                                       | Описание                        |
| ------ | ---------------------------------------------------------- | ------------------------------- |
| GET    | `/api/v1/content-nodes/{content_id}/dimension-mappings`    | Маппинги столбцов ноды на измерения |
| POST   | `/api/v1/content-nodes/{content_id}/detect-dimensions`     | Авто-определение и создание маппингов |

---

## Real-time (Socket.IO) события

### Подключение
```javascript
const socket = io('http://localhost:8000', {
  path: '/socket.io',
  auth: { token: 'Bearer <access_token>' } // опционально; третий аргумент auth передаётся в обработчик connect на сервере
});
```

### AI Assistant — стрим чата (`ai_chat_stream`)

Клиент → сервер: событие **`ai_chat_stream`**, тело (JSON):

| Поле | Тип | Описание |
| ---- | --- | -------- |
| `board_id` | string (UUID) | Для **доски** — `board_id`; для **дашборда** — `dashboard_id` (то же поле, см. `scope`) |
| `session_id` | string (UUID), опционально | Сессия чата |
| `message` | string | Текст пользователя |
| `selected_node_ids` | string[] | Только доска: выделенные ноды |
| `allow_auto_filter` | bool | |
| `required_tables` | list | |
| `filter_expression` | object | |
| `scope` | `"board"` \| `"dashboard"` | По умолчанию `board`. Для дашборда обязательно `dashboard` |
| `access_token` | string | Для **`scope=dashboard`** — JWT доступа (как в REST) |

Сервер → клиент (после успешного старта):

| Событие | Назначение |
| ------- | ---------- |
| `ai:stream:start` | `{ session_id, board_id }` — начало (в поле `board_id` для дашборда передаётся id дашборда) |
| `ai:stream:progress` | Прогресс мультиагента: `event`, `task`, `steps`, `step_index`, `total_steps`, `completed_count`, … |
| `ai:stream:chunk` | Фрагменты итогового текста |
| `ai:stream:end` | `{ session_id, full_response, suggested_actions? }` |
| `ai:stream:error` | `{ error, session_id? }` |

Реализация: `apps/backend/app/core/socketio.py` (`ai_chat_stream`). Для дашборда контекст и Redis-история совпадают с REST `POST .../dashboards/{id}/ai/chat`.

### События доски

| Event         | Направление     | Описание                     |
| ------------- | --------------- | ---------------------------- |
| `join_board`  | Client → Server | Подключиться к комнате доски |
| `leave_board` | Client → Server | Покинуть комнату             |

### События узлов

| Event                                  | Направление    | Описание             |
| -------------------------------------- | -------------- | -------------------- |
| `source_node_created/updated/deleted`  | Bi-directional | CRUD для SourceNode  |
| `content_node_created/updated/deleted` | Bi-directional | CRUD для ContentNode |
| `widget_node_created/updated/deleted`  | Bi-directional | CRUD для WidgetNode  |
| `comment_node_created`                 | Bi-directional | Создание комментария |

### События связей

| Event          | Направление    | Описание       |
| -------------- | -------------- | -------------- |
| `edge_created` | Bi-directional | Создание связи |
| `edge_deleted` | Bi-directional | Удаление связи |

### События трансформаций

| Event                      | Направление     | Описание            |
| -------------------------- | --------------- | ------------------- |
| `transformation_started`   | Server → Client | Начало выполнения   |
| `transformation_completed` | Server → Client | Успешное завершение |
| `transformation_failed`    | Server → Client | Ошибка выполнения   |

### AI Agent события

| Event            | Направление     | Описание                          |
| ---------------- | --------------- | --------------------------------- |
| `agent_thinking` | Server → Client | Агент начал обработку             |
| `tool_generated` | Server → Client | Событие генерации инструмента (legacy / отладка) |
| `tool_executed`  | Server → Client | Инструмент выполнен               |

---

## Обработка ошибок

- JSON: `{ "detail": "error message" }` или `{ "error": { "code": "string", "message": "..." } }`
- Коды: 400 / 401 / 403 / 404 / 409 / 429 / 500
- Идемпотентность: клиент может повторно слать события с `request_id`

---

> **Предыдущая версия**: Устаревшая API документация с DataNode endpoints и nested URLs доступна в [history/API_V1_LEGACY.md](history/API_V1_LEGACY.md)

**Версия API**: 1.0  
**Последнее обновление**: 2026-03-22  
**Статус**: ✅ Актуален — описывает реально существующие endpoints  
**Итого**: REST-модули: Health, Auth, Projects, Boards, Source Nodes, Content Nodes, Extraction, Widget Nodes, Comment Nodes, Edges, AI Assistant, AI Resolver, User Profile & LLM, Admin LLM, Files, Database, Dimensions, Board Filters, Dashboard Filters, Filter Presets, Dashboards, Library, Public, Content Nodes dimension mappings; + Socket.IO события
