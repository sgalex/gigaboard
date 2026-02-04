# API документация

## Executive Summary

**GigaBoard REST API** — FastAPI-основанный API для управления аналитическими досками с AI-агентами и real-time событиями (Socket.IO).

**Ключевые концепции:**
- **Source-Content архитектура**: SourceNode (источники данных) → ContentNode (извлечённые данные) → WidgetNode (визуализации)
- **4 типа узлов**: SourceNode, ContentNode, WidgetNode, CommentNode
- **6 типов связей**: EXTRACT, TRANSFORMATION, VISUALIZATION, COMMENT, REFERENCE, DRILL_DOWN
- **Multi-Agent System**: Planner, SourceNode Manager, Transformation Agent, Reporter Agent, Developer Agent
- **Real-time**: Socket.IO для коллаборативных обновлений досок

**Версионирование**: Все endpoints под `/api/v1`

**Endpoints по категориям:**
- ✅ **Authentication** — реализовано
- ⏳ **Boards & Nodes** — в разработке (FR-2, FR-14, FR-23)
- ⏳ **Edges & Transformations** — в разработке (FR-11, FR-5)
- ⏳ **AI Agents & Tools** — в разработке (FR-6, FR-7, FR-8)

---

## Общее описание

REST API на FastAPI для работы с бордами и узлами с интеграцией AI. Real-time события через Socket.IO (ws). Все ответы в JSON. Валидация — Pydantic v2. Версионирование API: `/api/v1`.

**Архитектура Source-Content (FR-14, FR-23)**:
- **SourceNode**: Источники данных (file, database, api, prompt, stream, manual) без извлечённого контента
- **ContentNode**: Результаты extraction из SourceNode или transformation (text + N tables)
- **WidgetNode**: Визуализации ContentNode с HTML/CSS/JS кодом
- **CommentNode**: Комментарии к любым узлам

**Статус реализации**: 🚧 В разработке
- ✅ **Реализовано**: Authentication endpoints (`/api/v1/auth/*`), Health check (`/health`)
- ⏳ **В планах**: Boards, SourceNodes, ContentNodes, WidgetNodes, CommentNodes, Edges (EXTRACT/TRANSFORMATION/VISUALIZATION/COMMENT), AI Agents

## Аутентификация

- JWT (Bearer) для REST
- Socket.IO handshake: передача токена в query/header, верификация на сервере
- Refresh-токены — отдельный endpoint

---

## Реализованные Endpoints

### POST /api/v1/auth/register
**Статус**: ✅ Реализовано  
**Описание**: Регистрация нового пользователя.
**Request Body**:
```json
{
  "email": "user@example.com",
  "username": "john_doe",
  "password": "secure_password"
}
```
**Ответ**:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "john_doe",
  "created_at": "2026-01-24T10:30:00Z"
}
```

### POST /api/v1/auth/login
**Статус**: ✅ Реализовано  
**Описание**: Получение access/refresh токенов.
**Request Body**:
```json
{ "email": "user@example.com", "password": "string" }
```
**Ответ**:
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

### POST /api/v1/auth/logout
**Статус**: ✅ Реализовано  
**Описание**: Выход из системы (инвалидация токена).

### GET /health
**Статус**: ✅ Реализовано  
**Описание**: Проверка состояния сервера, БД и Redis.

---

## Планируемые Endpoints (будут реализованы в следующих фичах)

> **Примечание**: Все перечисленные ниже endpoints находятся в стадии проектирования и будут реализованы поэтапно согласно [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md):
> - **FR-2**: Boards & Nodes (DataNode/WidgetNode/CommentNode) CRUD
> - **FR-3**: Real-time Socket.IO events
> - **FR-11**: Edges (TRANSFORMATION/VISUALIZATION/COMMENT/DRILL_DOWN/REFERENCE)
> - **FR-5**: Transformation Agent (генерация Python кода для трансформаций)
> - **FR-6**: Reporter Agent (генерация WidgetNode из DataNode)
> - **FR-7/FR-8**: Multi-Agent System & Dynamic Tools
> - **FR-12**: Dynamic Form Generation

### Управление досками (Boards Management)

### GET /api/v1/boards
**Статус**: ⏳ FR-2  
**Описание**: Список бордов пользователя.
**Параметры**: `limit`, `offset` (optional)

### POST /api/v1/boards
**Статус**: ⏳ FR-2  
**Описание**: Создать борд.
**Параметры**: `limit`, `offset` (optional)

### POST /api/v1/boards
**Описание**: Создать борд.
**Request Body**:
```json
{ "title": "Analytics space", "description": "optional" }
```
**Ответ**: объект борда с `id`, `created_at`, `updated_at`.

### GET /api/v1/boards/{boardId}
**Описание**: Получить борд с виджетами и связями.

### PATCH /api/v1/boards/{boardId}
**Описание**: Обновить метаданные борда.

### DELETE /api/v1/boards/{boardId}
**Описание**: Удалить борд (soft delete опционально).

---

## Node Management Endpoints

### SourceNode Endpoints

### POST /api/v1/boards/{boardId}/source-nodes
**Статус**: ⏳ FR-14, FR-23
**Описание**: Создать SourceNode (источник данных).
**Request Body**:
```json
{
  "source_type": "database",
  "source_config": {
    "query": "SELECT region, SUM(sales) as total FROM sales GROUP BY region",
    "database": "analytics_db",
    "connection_id": "conn_123"
  },
  "refresh_config": {
    "auto_refresh": true,
    "schedule": "0 */6 * * *"
  },
  "position": { "x": 100, "y": 100, "width": 300, "height": 200 },
  "title": "Sales Data Source"
}
```
**Ответ**:
```json
{
  "id": "source_123",
  "type": "source_node",
  "source_type": "database",
  "source_config": {...},
  "refresh_config": {...},
  "position": { "x": 100, "y": 100, "width": 300, "height": 200 },
  "created_at": "2026-01-30T10:30:00Z"
}
```

### GET /api/v1/boards/{boardId}/source-nodes
**Описание**: Получить все SourceNode доски.

### GET /api/v1/boards/{boardId}/source-nodes/{nodeId}
**Описание**: Получить конкретный SourceNode с конфигурацией.

### PATCH /api/v1/boards/{boardId}/source-nodes/{nodeId}
**Описание**: Обновить SourceNode (позиция, конфигурация источника).

### DELETE /api/v1/boards/{boardId}/source-nodes/{nodeId}
**Описание**: Удалить SourceNode (каскадное удаление ContentNode, WidgetNode).

### POST /api/v1/boards/{boardId}/source-nodes/{nodeId}/extract
**Описание**: Извлечь данные из SourceNode → создать ContentNode с EXTRACT edge.
**Ответ**:
```json
{
  "content_node_id": "content_456",
  "edge_id": "edge_789",
  "extraction_metadata": {
    "rows_extracted": 1000,
    "tables_count": 1,
    "extraction_time_ms": 234
  }
}
```

---

### ContentNode Endpoints

### POST /api/v1/boards/{boardId}/content-nodes
**Статус**: ⏳ FR-14, FR-23
**Описание**: Создать ContentNode (результат extraction или transformation).
**Request Body**:
```json
{
  "content": {
    "text": "Extracted sales data",
    "tables": [
      {
        "name": "sales_by_region",
        "schema": [
          {"name": "region", "type": "string"},
          {"name": "total", "type": "number"}
        ],
        "data": [
          {"region": "North", "total": 450000},
          {"region": "South", "total": 380000}
        ]
      }
    ]
  },
  "content_type": "extracted",
  "source_node_id": "source_123",
  "position": { "x": 450, "y": 100, "width": 300, "height": 250 }
}
```
**Ответ**:
```json
{
  "id": "content_456",
  "type": "content_node",
  "content": {...},
  "content_type": "extracted",
  "source_node_id": "source_123",
  "statistics": {
    "size_bytes": 15420,
    "row_count": 2,
    "table_count": 1
  },
  "position": { "x": 450, "y": 100, "width": 300, "height": 250 },
  "created_at": "2026-01-30T10:30:00Z"
}
```

### GET /api/v1/boards/{boardId}/content-nodes
**Описание**: Получить все ContentNode доски.

### GET /api/v1/boards/{boardId}/content-nodes/{nodeId}
**Описание**: Получить конкретный ContentNode с данными и схемой.

### PATCH /api/v1/boards/{boardId}/content-nodes/{nodeId}
**Описание**: Обновить ContentNode (позиция, данные).

### DELETE /api/v1/boards/{boardId}/content-nodes/{nodeId}
**Описание**: Удалить ContentNode (каскадное удаление WidgetNode).

### POST /api/v1/content-nodes/{nodeId}/visualize
**Статус**: ✅ Реализовано (01.02.2026)
**Описание**: Создать WidgetNode визуализацию из ContentNode с помощью Reporter Agent.

**Workflow**:
1. Reporter Agent анализирует ContentNode (text + tables)
2. AI генерирует HTML/CSS/JS код для визуализации
3. Код валидируется (безопасность, производительность)
4. Создаётся WidgetNode с VISUALIZATION edge к ContentNode

**Request Body**:
```json
{
  "user_prompt": "create bar chart showing sales by region",
  "widget_name": "Sales Overview",
  "auto_refresh": true,
  "position": { "x": 800, "y": 100 }
}
```

**Параметры**:
- `user_prompt` (optional): Инструкция для визуализации (например, "create bar chart")
- `widget_name` (optional): Пользовательское имя виджета
- `auto_refresh` (default: true): Автообновление при изменении ContentNode
- `position` (optional): Позиция виджета, по умолчанию offset от ContentNode

**Ответ**:
```json
{
  "widget_node_id": "widget_789",
  "edge_id": "edge_abc",
  "status": "success",
  "error": null
}
```

**Примеры использования**:
- `POST /api/v1/content-nodes/{id}/visualize` + `{"user_prompt": "bar chart"}` → Bar chart
- `POST /api/v1/content-nodes/{id}/visualize` + `{}` → Auto-generated visualization
- `POST /api/v1/content-nodes/{id}/visualize` + `{"user_prompt": "table with search"}` → Searchable table

### POST /api/v1/content-nodes/{nodeId}/visualize-iterative
**Статус**: ✅ Реализовано (02.2026)
**Описание**: Итеративная генерация визуализации через чат. Используется в WidgetDialog для уточнения виджетов.

**Request Body**:
```json
{
  "user_prompt": "добавь легенду к графику",
  "existing_widget_code": "<!DOCTYPE html>...",
  "chat_history": [
    {"role": "user", "content": "создай bar chart"},
    {"role": "assistant", "content": "Создан bar chart..."}
  ]
}
```

**Параметры**:
- `user_prompt` (required): Инструкция/уточнение для AI
- `existing_widget_code` (optional): Текущий HTML код виджета для итерации
- `chat_history` (optional): История чата для контекста

**Ответ**:
```json
{
  "widget_code": "<!DOCTYPE html>...",
  "widget_name": "Sales Chart",
  "description": "Добавлена легенда к графику продаж",
  "html_code": "",
  "css_code": "",
  "js_code": "",
  "status": "success",
  "error": null
}
```

**Отличия от /visualize**:
- Не создаёт WidgetNode — только генерирует код
- Поддерживает итерацию (existing_widget_code)
- Возвращает `widget_code` (полный HTML) вместо отдельных html/css/js
- Используется Frontend'ом для preview перед сохранением

---

### DataNode Endpoints (устаревшие, будут заменены)

> **⚠️ Примечание**: DataNode endpoints устарели и будут заменены на SourceNode + ContentNode endpoints. Используйте новые endpoints выше.

### POST /api/v1/boards/{boardId}/data-nodes
**Статус**: ⏳ FR-2
**Описание**: Создать DataNode (узел с данными).
**Request Body**:
```json
{
  "data_source_type": "sql_query",
  "data_source_config": {
    "query": "SELECT region, SUM(sales) as total FROM sales GROUP BY region",
    "database": "analytics_db"
  },
  "position": { "x": 100, "y": 100, "width": 300, "height": 200 },
  "title": "Sales by Region"
}
```
**Ответ**:
```json
{
  "id": "datanode_123",
  "type": "data_node",
  "data_source_type": "sql_query",
  "schema": {
    "columns": [
      {"name": "region", "type": "string"},
      {"name": "total", "type": "number"}
    ],
    "row_count": 4
  },
  "data": [...],
  "position": { "x": 100, "y": 100, "width": 300, "height": 200 },
  "created_at": "2026-01-24T10:30:00Z"
}
```

### GET /api/v1/boards/{boardId}/data-nodes
**Описание**: Получить все DataNode доски.

### GET /api/v1/boards/{boardId}/data-nodes/{nodeId}
**Описание**: Получить конкретный DataNode с данными и схемой.

### PATCH /api/v1/boards/{boardId}/data-nodes/{nodeId}
**Описание**: Обновить DataNode (позиция, конфигурация источника данных).

### DELETE /api/v1/boards/{boardId}/data-nodes/{nodeId}
**Описание**: Удалить DataNode.

### POST /api/v1/boards/{boardId}/data-nodes/{nodeId}/refresh
**Описание**: Принудительно обновить данные DataNode из источника.

---

### WidgetNode Endpoints

### POST /api/v1/boards/{boardId}/widget-nodes
**Статус**: ⏳ FR-6
**Описание**: Создать WidgetNode (визуализация из ContentNode). Reporter Agent генерирует HTML/CSS/JS код.
**Request Body**:
```json
{
  "parent_content_node_id": "content_123",
  "user_prompt": "Create bar chart showing sales by region with color-coded bars",
  "position": { "x": 450, "y": 100, "width": 400, "height": 300 }
}
```
**Ответ**:
```json
{
  "id": "widget_456",
  "type": "widget_node",
  "parent_content_node_id": "content_123",
  "description": "Bar chart showing sales by region",
  "html_code": "<div class='chart'>...</div>",
  "css_code": ".chart { ... }",
  "js_code": "const chart = ...",
  "position": { "x": 450, "y": 100, "width": 400, "height": 300 },
  "created_at": "2026-01-30T10:31:00Z"
}
```

### GET /api/v1/boards/{boardId}/widget-nodes
**Описание**: Получить все WidgetNode доски.

### GET /api/v1/boards/{boardId}/widget-nodes/{nodeId}
**Описание**: Получить конкретный WidgetNode.

### PATCH /api/v1/boards/{boardId}/widget-nodes/{nodeId}
**Описание**: Обновить WidgetNode (позиция, размер).

### DELETE /api/v1/boards/{boardId}/widget-nodes/{nodeId}
**Описание**: Удалить WidgetNode.

---

### CommentNode Endpoints

### POST /api/v1/boards/{boardId}/comment-nodes
**Статус**: ⏳ FR-2
**Описание**: Создать CommentNode (комментарий к узлу).
**Request Body**:
```json
{
  "target_node_id": "datanode_123",
  "comment_text": "Sales spike in Q4 needs investigation",
  "author": "user",
  "position": { "x": 120, "y": 350, "width": 250, "height": 100 }
}
```

### GET /api/v1/boards/{boardId}/comment-nodes
**Описание**: Получить все комментарии доски.

### PATCH /api/v1/boards/{boardId}/comment-nodes/{nodeId}
**Описание**: Обновить комментарий.

### DELETE /api/v1/boards/{boardId}/comment-nodes/{nodeId}
**Описание**: Удалить комментарий.

---

## Edge Management Endpoints

**Статус**: ⏳ FR-11  
**Описание**: Управление связями между узлами (6 типов связей).

### POST /api/v1/boards/{boardId}/edges
**Описание**: Создать связь между узлами (EXTRACT, TRANSFORMATION, VISUALIZATION, COMMENT, DRILL_DOWN, REFERENCE).

**Пример 1: EXTRACT edge** (извлечение SourceNode → ContentNode):
```json
{
  "from_node_id": "source_123",
  "to_node_id": "content_456",
  "edge_type": "EXTRACT",
  "label": "Extract sales data",
  "extraction_metadata": {
    "rows_extracted": 1000,
    "extraction_time_ms": 234
  }
}
```
**Ответ**:
```json
{
  "id": "edge_789",
  "from_node_id": "source_123",
  "to_node_id": "content_456",
  "edge_type": "EXTRACT",
  "visual_config": {
    "color": "#4CAF50",
    "line_style": "solid",
    "arrow_type": "forward"
  },
  "created_at": "2026-01-30T10:30:00Z"
}
```

**Пример 2: TRANSFORMATION edge** (трансформация ContentNode → ContentNode):
```json
{
  "from_node_id": "content_123",
  "to_node_id": "content_456",
  "edge_type": "TRANSFORMATION",
  "transformation_code": "df_filtered = df[df['sales'] > 1000]",
  "transformation_prompt": "Filter sales data to show only values above 1000",
  "label": "Filter high-value sales"
}
```
**Ответ**:
```json
{
  "id": "edge_790",
  "from_node_id": "content_123",
  "to_node_id": "content_456",
  "edge_type": "TRANSFORMATION",
  "transformation_code": "df_filtered = df[df['sales'] > 1000]",
  "visual_config": {
    "color": "#2196F3",
    "line_style": "solid",
    "arrow_type": "forward"
  },
  "created_at": "2026-01-30T10:30:00Z"
}
```

**Пример 3: VISUALIZATION edge** (ContentNode → WidgetNode):
```json
{
  "from_node_id": "content_123",
  "to_node_id": "widget_456",
  "edge_type": "VISUALIZATION",
  "label": "Bar chart visualization",
  "auto_refresh": true
}
```

**Пример 4: COMMENT edge** (CommentNode → любой узел):
```json
{
  "from_node_id": "comment_789",
  "to_node_id": "content_123",
  "edge_type": "COMMENT",
  "label": "User annotation"
}
```

### GET /api/v1/boards/{boardId}/edges
**Описание**: Получить все связи доски.
**Query params**:
- `from_widget_id`: Фильтр по источнику
- `to_widget_id`: Фильтр по целевому виджету
- `edge_type`: Фильтр по типу связи

### PATCH /api/v1/boards/{boardId}/edges/{edgeId}
**Описание**: Обновить свойства связи (label, visual_config, parameter_mapping).
**Request Body**:
```json
{
  "label": "Updated label",
  "visual_config": {
    "color": "#FF5722"
  }
}
```

### DELETE /api/v1/boards/{boardId}/edges/{edgeId}
**Описание**: Удалить связь между узлами.

---

## Transformation Management Endpoints

**Статус**: ⏳ FR-5  
**Описание**: Управление трансформациями данных (Transformation Agent).

### POST /api/v1/boards/{boardId}/transformations
**Описание**: Создать трансформацию данных (AI генерирует Python код).
**Request Body**:
```json
{
  "source_node_ids": ["content_123"],
  "user_prompt": "Filter sales data to show only high-value transactions above $1000 and group by region",
  "output_position": { "x": 500, "y": 100 }
}
```
**Ответ**:
```json
{
  "transformation_id": "trans_789",
  "source_node_ids": ["content_123"],
  "target_node_id": "content_456",
  "transformation_code": "df_filtered = df[df['sales'] > 1000]\ndf_grouped = df_filtered.groupby('region').sum()",
  "transformation_prompt": "Filter sales data...",
  "edge_id": "edge_789",
  "execution_status": "success",
  "execution_time_ms": 145,
  "created_at": "2026-01-30T10:30:00Z"
}
```

### GET /api/v1/boards/{boardId}/transformations
**Описание**: Получить все трансформации доски.

### GET /api/v1/boards/{boardId}/transformations/{transformationId}
**Описание**: Получить детали трансформации (код, статистика выполнения).

### POST /api/v1/boards/{boardId}/transformations/{transformationId}/execute
**Описание**: Принудительно выполнить трансформацию (replay).

### PATCH /api/v1/boards/{boardId}/transformations/{transformationId}
**Описание**: Обновить код трансформации.
**Request Body**:
```json
{
  "transformation_code": "df_filtered = df[df['sales'] > 2000]  # Updated threshold"
}
```

### DELETE /api/v1/boards/{boardId}/transformations/{transformationId}
**Описание**: Удалить трансформацию (удаляет target DataNode).

---

## Board Construction Endpoints (for Agents)

**Статус**: ⏳ FR-10  
**Описание**: Agent-driven построение досок с DataNode/WidgetNode узлами.

### POST /api/v1/boards/{boardId}/build
**Описание**: Построить доску с набором узлов и связей (используется Reporter Agent и Transformation Agent).
**Request Body**:
```json
{
  "data_nodes": [
    {
      "data_source_type": "sql_query",
      "data_source_config": {
        "query": "SELECT region, SUM(sales) FROM sales GROUP BY region"
      },
      "position": { "x": 0, "y": 0, "width": 300, "height": 200 }
    }
  ],
  "transformations": [
    {
      "source_node_index": 0,
      "user_prompt": "Filter to show only top 3 regions by sales",
      "position": { "x": 350, "y": 0 }
    }
  ],
  "widget_nodes": [
    {
      "parent_data_node_index": 1,
      "user_prompt": "Create bar chart showing top regions",
      "position": { "x": 700, "y": 0, "width": 400, "height": 300 }
    }
  ],
  "layout_strategy": "flow"
}
```
**Ответ**:
```json
{
  "board_id": "board_123",
  "data_nodes_created": 2,
  "widget_nodes_created": 1,
  "edges_created": 2,
  "created_nodes": {
    "data_nodes": ["datanode_123", "datanode_456"],
    "widget_nodes": ["widget_789"]
  },
  "created_edges": [
    { "id": "edge_1", "type": "TRANSFORMATION" },
    { "id": "edge_2", "type": "VISUALIZATION" }
  ]
}
```

### GET /api/v1/boards/{boardId}/state
**Описание**: Получить полное состояние доски (все узлы и связи).
**Ответ**:
```json
{
  "board_id": "board_123",
  "title": "Sales Dashboard",
  "nodes": {
    "data_nodes": [...],
    "widget_nodes": [...],
    "comment_nodes": [...]
  },
  "edges": [...],
  "layout_info": {...},
  "last_modified": "2026-01-24T10:45:00Z",
  "modified_by": "agent_reporter"
}
```

### POST /api/v1/boards/{boardId}/layout
**Описание**: Переорганизовать лэйаут доски.
**Request Body**:
```json
{
  "strategy": "grid",  # flow, grid, hierarchy, freeform
  "options": {
    "columns": 3,
    "spacing": 20,
    "auto_arrange": true
  }
}
```

### POST /api/v1/boards/{boardId}/share
**Описание**: Поделиться доской с другими пользователями.
**Request Body**:
```json
{
  "user_emails": ["user@example.com"],
  "permission": "view"  # view, edit, admin
}
```

### GET /api/v1/boards/{boardId}/history
**Описание**: Получить историю изменений доски.
**Query params**:
- `limit`: Количество записей (default: 50)
- `offset`: Смещение

**Ответ**:
```json
{
  "changes": [
    {
      "version": 5,
      "timestamp": "2026-01-23T10:45:00Z",
      "change_type": "widget_added",
      "change_data": { "widget_id": "w5", "type": "chart" },
      "changed_by": "agent_reporter"
    }
  ],
  "total_changes": 23,
  "current_version": 23
}
```

### POST /api/v1/boards/{boardId}/revert/{version}
**Описание**: Восстановить доску в определённую версию.

---

## AI Assistant Endpoints

**Статус**: ⏳ FR-6, FR-4  
**Описание**: AI Assistant Panel для диалога с пользователем в контексте доски + AI Resolver для семантических трансформаций.

### POST /api/v1/ai/query
**Описание**: Запрос к GigaChat для генерации/рекомендации виджета.
**Request Body**:
```json
{ "board_id": "uuid", "query": "Построй сравнение продаж по регионам" }
```
**Ответ (пример)**:
```json
{
  "suggested_widget": {
    "type": "chart",
    "spec": { "kind": "bar", "x": "region", "y": "sales" },
    "data_source": "demo"
  },
  "message": "Предлагаю столбчатую диаграмму по регионам"
}
```

### POST /api/v1/ai/resolve
**Статус**: ✅ РЕАЛИЗОВАНО (31.01.2026)  
**Описание**: Batch AI resolution для семантических задач. Используется **внутри** сгенерированного кода трансформаций через модуль `gb`. Endpoint существует, но основное применение — через `gb.ai_resolve_batch()` (прямой вызов ResolverAgent без HTTP).

**Request Body**:
```json
{
  "values": ["Алексей", "Мария", "Иван"],
  "task_description": "определи пол человека по имени, верни M или F",
  "result_format": "string",
  "chunk_size": 50
}
```

**Response**:
```json
{
  "status": "success",
  "results": ["M", "F", "M"],
  "metadata": {
    "total_values": 3,
    "chunks_processed": 1,
    "processing_time_ms": 2150
  }
}
```

**Error Response**:
```json
{
  "status": "error",
  "error": "Failed to get response from GigaChat: timeout",
  "results": [null, null, null]
}
```

**Примеры задач:**
- Определение пола по имени: `"определи пол: M или F"`
- Sentiment analysis: `"классифицируй отзыв: positive/negative/neutral"`
- Категоризация: `"определи категорию продукта: electronics/clothing/food/home/other"`
- Извлечение данных: `"извлеки email адрес из текста"`
- Перевод: `"переведи с русского на английский"`

**⚠️ Основное применение — через gb module:**
```python
# В сгенерированном коде трансформации
names = df['name'].tolist()
genders = gb.ai_resolve_batch(
    names,
    "определи пол человека по имени: M или F"
)
df['gender'] = genders
```

См. полную документацию: [AI_RESOLVER_SYSTEM.md](./AI_RESOLVER_SYSTEM.md)

### POST /api/v1/boards/{boardId}/ai/chat
**Описание**: Отправить сообщение в AI Assistant Panel. Ассистент анализирует контекст доски (текущие виджеты, данные) и возвращает ответ с опциональными рекомендациями.
**Request Body**:
```json
{
  "message": "Какой регион показал максимальный рост?",
  "session_id": "uuid" (optional, для истории в рамках сессии)
}
```
**Ответ (пример)**:
```json
{
  "response": "Регион Западный показал рост на 35% квартал к кварталу. Я вижу на вашей доске график продаж...",
  "suggested_actions": [
    {
      "action": "create_widget",
      "widget_spec": {
        "type": "chart",
        "title": "Рост по регионам",
        "spec": { "kind": "line", "x": "date", "y": "growth_rate" }
      },
      "description": "Построить линейный график роста по регионам?"
    }
  ],
  "session_id": "uuid"
}
```

### GET /api/v1/boards/{boardId}/ai/chat/history
**Описание**: Получить историю диалога в текущей сессии.
**Параметры**: `session_id` (optional)
**Ответ**:
```json
{
  "messages": [
    { "role": "user", "content": "...", "timestamp": "..." },
    { "role": "assistant", "content": "...", "timestamp": "..." }
  ]
}
```

## Real-time (Socket.IO) события

### Подключение
```javascript
const socket = io('http://localhost:8000', {
  auth: { token: 'Bearer <access_token>' }
});
```

### События доски (Board Events)

#### `join_board` (Client → Server)
Подключиться к комнате доски для получения обновлений.
```json
{
  "board_id": "board_uuid"
}
```

#### `leave_board` (Client → Server)
Покинуть комнату доски.
```json
{
  "board_id": "board_uuid"
}
```

### События узлов (Node Events)

#### `source_node_created` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node": {
    "id": "source_uuid",
    "type": "source_node",
    "source_type": "database",
    "source_config": {...},
    "position": { "x": 100, "y": 200, "width": 300, "height": 200 },
    "created_by": "user_uuid",
    "created_at": "2026-01-30T10:30:00Z"
  }
}
```

#### `source_node_updated` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node_id": "source_uuid",
  "changes": {
    "position": { "x": 150, "y": 250 },
    "source_config": {...}
  },
  "updated_by": "user_uuid"
}
```

#### `source_node_deleted` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node_id": "source_uuid",
  "deleted_by": "user_uuid"
}
```

#### `content_node_created` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node": {
    "id": "content_uuid",
    "type": "content_node",
    "content_type": "extracted",
    "source_node_id": "source_uuid",
    "position": { "x": 450, "y": 200, "width": 300, "height": 250 },
    "created_by": "agent_transformation",
    "created_at": "2026-01-30T10:30:00Z"
  }
}
```

#### `content_node_updated` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node_id": "content_uuid",
  "changes": {
    "position": { "x": 500, "y": 250 },
    "content": {...}
  },
  "updated_by": "user_uuid"
}
```

#### `content_node_deleted` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node_id": "content_uuid",
  "deleted_by": "user_uuid"
}
```

#### `widget_node_created` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node": {
    "id": "widget_uuid",
    "type": "widget_node",
    "parent_content_node_id": "content_uuid",
    "description": "Bar chart showing sales",
    "position": { "x": 450, "y": 100, "width": 400, "height": 300 },
    "created_by": "agent_reporter",
    "created_at": "2026-01-30T10:31:00Z"
  }
}
```

#### `widget_node_updated` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node_id": "widget_uuid",
  "changes": {
    "position": { "x": 500, "y": 150 }
  },
  "updated_by": "user_uuid"
}
```

#### `widget_node_deleted` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node_id": "widget_uuid",
  "deleted_by": "user_uuid"
}
```

#### `comment_node_created` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "node": {
    "id": "comment_uuid",
    "type": "comment_node",
    "target_node_id": "content_uuid",
    "comment_text": "Q4 spike needs investigation",
    "author": "user",
    "created_by": "user_uuid",
    "created_at": "2026-01-30T10:32:00Z"
  }
}
```

### События связей (Edge Events)

#### `edge_created` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "edge": {
    "id": "edge_uuid",
    "from_node_id": "content_1",
    "to_node_id": "content_2",
    "edge_type": "TRANSFORMATION",
    "label": "Filter high-value sales",
    "transformation_code": "df_filtered = df[df['sales'] > 1000]",
    "created_by": "agent_transformation"
  }
}
```

#### `edge_deleted` (Server → Client | Client → Server)
```json
{
  "board_id": "board_uuid",
  "edge_id": "edge_uuid",
  "deleted_by": "user_uuid"
}
```

### События трансформаций (Transformation Events)

#### `transformation_started` (Server → Client)
```json
{
  "board_id": "board_uuid",
  "transformation_id": "trans_uuid",
  "source_node_ids": ["content_123"],
  "status": "executing",
  "started_at": "2026-01-30T10:30:00Z"
}
```

#### `transformation_completed` (Server → Client)
```json
{
  "board_id": "board_uuid",
  "transformation_id": "trans_uuid",
  "target_node_id": "content_456",
  "status": "success",
  "execution_time_ms": 145,
  "rows_processed": 1250,
  "completed_at": "2026-01-30T10:30:01Z"
}
```

#### `transformation_failed` (Server → Client)
```json
{
  "board_id": "board_uuid",
  "transformation_id": "trans_uuid",
  "status": "failed",
  "error": {
    "type": "SyntaxError",
    "message": "Invalid Python syntax",
    "line": 3
  },
  "failed_at": "2026-01-24T10:30:00Z"
}
```

### AI Agent События

#### `agent_thinking` (Server → Client)
Агент начал обработку запроса.
```json
{
  "board_id": "board_uuid",
  "agent": "planner",
  "message": "Breaking down request into subtasks...",
  "timestamp": "2026-01-24T10:30:00Z"
}
```

#### `tool_generated` (Server → Client)
Developer Agent создал новый инструмент.
```json
{
  "board_id": "board_uuid",
  "agent": "developer",
  "tool_name": "fetch_competitor_prices",
  "language": "python",
  "status": "generated"
}
```

#### `tool_executed` (Server → Client)
Инструмент был выполнен.
```json
{
  "board_id": "board_uuid",
  "agent": "executor",
  "tool_name": "fetch_competitor_prices",
  "status": "success",
  "execution_time_ms": 2340,
  "result_summary": "Retrieved 150 product prices"
}
```

### Presence Events (опционально)

#### `cursor_moved` (Client → Server)
```json
{
  "board_id": "board_uuid",
  "user_id": "user_uuid",
  "position": { "x": 450, "y": 320 },
  "username": "John Doe"
}
```

#### `user_joined` (Server → Client)
```json
{
  "board_id": "board_uuid",
  "user": {
    "id": "user_uuid",
    "username": "John Doe",
    "joined_at": "2026-01-24T10:30:00Z"
  }
}
```

#### `user_left` (Server → Client)
```json
{
  "board_id": "board_uuid",
  "user_id": "user_uuid"
}
```

**Примечание**: Все события транслируются внутри комнаты `boardId`. При горизонтальном масштабировании сервер использует Redis pub/sub для синхронизации между инстансами.

---

## Multi-Agent API Endpoints (FR-7, FR-8)

**Статус**: ⏳ FR-7, FR-8  
**Описание**: Управление мульти-агентной системой.

### POST /api/v1/agents
**Описание**: Зарегистрировать новый агент или инициализировать встроенные агенты.
**Request Body**:
```json
{
  "name": "researcher",
  "type": "built-in",
  "system_prompt": "You are a researcher agent...",
  "capabilities": ["fetch_data", "query_db", "web_scrape"]
}
```
**Response**: Идентификатор агента

### GET /api/v1/agents
**Описание**: Список всех доступных агентов.

### GET /api/v1/agents/{agentId}
**Описание**: Информация об агенте, его конфигурация и метрики.

### PATCH /api/v1/agents/{agentId}/config
**Описание**: Обновить конфигурацию агента (system prompt, capabilities).

---

## Tool Management Endpoints (FR-8)

**Статус**: ⏳ FR-8  
**Описание**: Динамическое создание и управление инструментами.

### GET /api/v1/tools
**Описание**: Список всех доступных инструментов (встроенные + пользовательские).
**Query params**: 
- `category`: "api_call", "db_query", "web_scrape", etc.
- `sort_by`: "usage_count", "quality_score", "created_at"

### GET /api/v1/tools/{toolId}
**Описание**: Информация об инструменте (код, параметры, версия, метрики).

### POST /api/v1/tools/{toolId}/test
**Описание**: Тестировать инструмент с test data в sandbox.
**Request Body**:
```json
{
  "params": { "url": "https://example.com", "selector": ".price" },
  "test_data": {...}
}
```
**Response**: Результат выполнения, логи, время выполнения.

### DELETE /api/v1/tools/{toolId}
**Описание**: Удалить инструмент (версионирование).

### GET /api/v1/tools/{toolId}/history
**Описание**: История использования инструмента (метрики, ошибки).

---

## Agent Execution Endpoints

### POST /api/v1/boards/{boardId}/agents/execute
**Описание**: Запустить multi-agent workflow для выполнения задачи.
**Request Body**:
```json
{
  "request": "Analyze sales by region and identify trends",
  "agents": ["planner", "researcher", "analyst", "reporter"],
  "board_context": true,
  "timeout": 300
}
```
**Response**:
```json
{
  "execution_id": "exec_123",
  "status": "executing",
  "agents_involved": ["planner", "researcher", "analyst", "reporter"],
  "estimated_completion": "2026-01-23T10:15:30Z",
  "websocket_url": "wss://api.gigaboard.io/ws/agents/exec_123"
}
```

### GET /api/v1/boards/{boardId}/agents/executions/{executionId}
**Описание**: Получить статус и результаты выполнения.
**Response**:
```json
{
  "execution_id": "exec_123",
  "status": "completed",
  "created_by_agent": "planner",
  "tools_created": [
    {
      "name": "fetch_competitor_prices",
      "version": "1.0",
      "language": "python",
      "execution_count": 2
    }
  ],
  "results": {
    "summary": "Analysis complete. Found 3 high-value segments.",
    "data": {...},
    "widgets_created": ["widget_123", "widget_456"]
  },
  "start_time": "2026-01-23T10:10:00Z",
  "end_time": "2026-01-23T10:15:30Z",
  "execution_time_ms": 330000
}
```

### WebSocket: /ws/agents/{boardId}/{sessionId}
**Описание**: Real-time agent communication stream.
**Messages sent**:
- `agent_thinking`: Агент начал задачу
- `tool_generation`: Код инструмента генерируется
- `tool_testing`: Инструмент тестируется в sandbox
- `tool_execution`: Инструмент выполняется
- `analysis_update`: Новые результаты анализа
- `progress_update`: Общий прогресс
- `completion`: Задача завершена с результатом

**Example message**:
```json
{
  "type": "agent_thinking",
  "agent": "planner",
  "message": "Breaking down request into 4 subtasks...",
  "timestamp": "2026-01-23T10:10:15Z"
}
```

```json
{
  "type": "tool_execution",
  "agent": "executor",
  "tool_name": "fetch_competitor_prices",
  "status": "success",
  "result_summary": "Retrieved 150 product prices from CompetitorA",
  "execution_time_ms": 2340
}
```

---

## Обработка ошибок
- JSON: `{ "error": { "code": "string", "message": "...", "details": {} } }`
- Коды: 400/401/403/404/409/429/500
- Идемпотентность: клиент может повторно слать события с `request_id`; сервер обязан не дублировать операции.

---

**Версия API**: 1.0 (обновлено для Source-Content архитектуры)  
**Последнее обновление**: 2026-01-30  
**Статус**: 🚧 Активная разработка — endpoints реализуются поэтапно  
**Архитектура**: Source-Content Data-Centric Canvas (SourceNode/ContentNode/WidgetNode/CommentNode)
