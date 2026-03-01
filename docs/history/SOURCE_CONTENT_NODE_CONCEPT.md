# Source-Content Node Architecture Concept

**Статус**: 🎯 Концепция для обсуждения  
**Дата**: 29 января 2026  
**Цель**: Явное разделение источников данных и результатов обработки

---

## 🎯 Ключевая идея

Вместо универсальной **DataNode**, которая смешивает источники и результаты, вводим чёткую семантику:

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ SourceNode   │──────>│ ContentNode  │──────>│ WidgetNode   │
│ (Источник)   │Extract│ (Результат)  │Visual │ (Визуализ.)  │
└──────────────┘      └──────────────┘      └──────────────┘
       ↑                     ↑                     ↑
       │                     │                     │
  CommentNode           CommentNode           CommentNode
  (к любым нодам)
```

**Принципы**:
1. **SourceNode** — явная точка входа данных (файл, СУБД, API, промпт)
2. **ContentNode** — результат обработки (текст + таблицы)
3. **WidgetNode** — визуализация ContentNode (HTML/CSS/JS)
4. **CommentNode** — комментарии к любым нодам

---

## 📊 Типы узлов

### 1. SourceNode (Источник данных)

**Назначение**: Точка входа данных в систему. Описывает, **откуда** брать данные.

#### Типы источников

```typescript
type SourceType = 
  | "prompt"       // AI-промпт для генерации/анализа данных
  | "file"         // Загруженный файл (CSV, JSON, Excel, PDF)
  | "database"     // Подключение к СУБД (PostgreSQL, MySQL, MongoDB)
  | "api"          // REST/GraphQL API endpoint
  | "stream"       // Real-time stream (WebSocket, SSE, Kafka)
  | "manual"       // Ручной ввод данных через форму
```

#### Структура данных

```json
{
  "id": "source_123",
  "type": "source_node",
  "source_type": "database",
  
  "config": {
    "connection_string": "postgresql://user:pass@localhost:5432/sales",
    "query": "SELECT * FROM orders WHERE date >= '2026-01-01'",
    "credentials": {
      "username": "analyst",
      "password_ref": "vault://secrets/db_password"
    },
    "refresh_schedule": "0 */6 * * *"  // Каждые 6 часов
  },
  
  "metadata": {
    "title": "Sales Database",
    "description": "Production sales database",
    "last_extracted": "2026-01-29T10:00:00Z",
    "extraction_status": "success",
    "error_message": null,
    "created_by": "user_123",
    "created_at": "2026-01-29T09:00:00Z"
  },
  
  "position": {"x": 100, "y": 100},
  "board_id": "board_456"
}
```

#### Примеры конфигураций

**1. Промпт для AI**
```json
{
  "source_type": "prompt",
  "config": {
    "prompt": "Generate synthetic sales data for Q1 2026 with seasonal patterns",
    "agent_type": "data_generation",
    "parameters": {
      "rows": 10000,
      "columns": ["date", "product", "region", "amount", "quantity"]
    }
  }
}
```

**2. Файл**
```json
{
  "source_type": "file",
  "config": {
    "file_id": "file_789",
    "filename": "sales_q1_2026.csv",
    "mime_type": "text/csv",
    "size_bytes": 524288,
    "uploaded_at": "2026-01-29T09:30:00Z"
  }
}
```

**3. API**
```json
{
  "source_type": "api",
  "config": {
    "url": "https://api.stripe.com/v1/charges",
    "method": "GET",
    "headers": {
      "Authorization": "Bearer sk_test_xxx"
    },
    "params": {
      "created[gte]": "2026-01-01",
      "limit": 100
    },
    "pagination": {
      "type": "cursor",
      "param": "starting_after"
    }
  }
}
```

**4. База данных**
```json
{
  "source_type": "database",
  "config": {
    "connection_string": "postgresql://localhost:5432/analytics",
    "query": "SELECT * FROM sales WHERE created_at > NOW() - INTERVAL '7 days'",
    "query_params": {},
    "timeout_seconds": 30
  }
}
```

#### Операции с SourceNode

```python
class SourceNode:
    """Source node operations"""
    
    async def extract(self) -> ContentNode:
        """
        Извлекает данные из источника и создаёт ContentNode
        
        Returns:
            ContentNode с извлечёнными данными
        """
        if self.source_type == "prompt":
            # Отправить промпт Multi-Agent системе
            result = await multi_agent_engine.process_prompt(
                prompt=self.config["prompt"],
                context={"board_id": self.board_id}
            )
            return ContentNode.from_ai_result(result)
        
        elif self.source_type == "file":
            # Прочитать и распарсить файл
            file_data = await storage.read_file(self.config["file_id"])
            parsed = await parsers.parse(file_data, self.config["mime_type"])
            return ContentNode.from_parsed_data(parsed)
        
        elif self.source_type == "database":
            # Выполнить SQL запрос
            result = await db_connector.execute_query(
                connection_string=self.config["connection_string"],
                query=self.config["query"]
            )
            return ContentNode.from_db_result(result)
        
        elif self.source_type == "api":
            # Запросить API
            result = await api_client.fetch(
                url=self.config["url"],
                method=self.config["method"],
                headers=self.config["headers"]
            )
            return ContentNode.from_api_response(result)
    
    async def validate(self) -> ValidationResult:
        """Проверяет доступность источника без извлечения данных"""
        pass
    
    async def refresh(self) -> ContentNode:
        """
        Повторное извлечение данных (для обновления)
        Создаёт новый ContentNode или обновляет существующий
        """
        pass
    
    async def schedule_refresh(self, cron: str):
        """Настраивает автоматическое обновление по расписанию"""
        pass
```

#### UI представление

```
┌────────────────────────────────┐
│  📊 Source: Sales Database     │
│  ────────────────────────────  │
│  Type: PostgreSQL              │
│  Query: SELECT * FROM sales... │
│                                │
│  Last extracted: 2 hours ago   │
│  Status: ✅ Connected          │
│                                │
│  [🔄 Extract Data]  [⚙️ Config] │
└────────────────────────────────┘
```

---

### 2. ContentNode (Результат обработки)

**Назначение**: Хранение результатов извлечения или обработки данных. Содержит **текст + таблицы**.

#### Структура данных

```json
{
  "id": "content_123",
  "type": "content_node",
  
  "content": {
    "text": "Extracted 15,234 sales records from Q1 2026. Average order value: $127.45. Top region: North America (42% of revenue).",
    
    "tables": [
      {
        "id": "table_1",
        "name": "sales_data",
        "description": "Raw sales records",
        "columns": [
          {"name": "date", "type": "date", "nullable": false},
          {"name": "product", "type": "string", "nullable": false},
          {"name": "region", "type": "string", "nullable": false},
          {"name": "amount", "type": "float", "nullable": false},
          {"name": "quantity", "type": "integer", "nullable": false}
        ],
        "row_count": 15234,
        "size_bytes": 1024000,
        "sample_rows": [
          {"date": "2026-01-01", "product": "Widget A", "region": "North", "amount": 125.00, "quantity": 5},
          {"date": "2026-01-01", "product": "Widget B", "region": "South", "amount": 87.50, "quantity": 2}
        ]
      },
      {
        "id": "table_2",
        "name": "aggregated_stats",
        "description": "Statistical summary",
        "columns": [
          {"name": "metric", "type": "string", "nullable": false},
          {"name": "value", "type": "float", "nullable": false}
        ],
        "row_count": 5,
        "sample_rows": [
          {"metric": "total_revenue", "value": 1945678.00},
          {"metric": "avg_order_value", "value": 127.45},
          {"metric": "total_orders", "value": 15234}
        ]
      }
    ]
  },
  
  "lineage": {
    "source_node_id": "source_123",
    "transformation_id": null,  // Если прямое извлечение
    "operation": "extract",
    "created_by": "researcher_agent"
  },
  
  "metadata": {
    "title": "Q1 2026 Sales Data",
    "description": "Extracted sales records with aggregations",
    "created_at": "2026-01-29T10:15:00Z",
    "updated_at": "2026-01-29T10:15:00Z",
    "size_bytes": 1024000,
    "row_count": 15234
  },
  
  "position": {"x": 450, "y": 100},
  "board_id": "board_456"
}
```

#### Множественные таблицы

ContentNode может содержать **несколько таблиц** одновременно:

```
ContentNode: "Sales Analysis Result"
├── text: "Analysis summary..."
├── table_1: "raw_sales" (15,234 rows)
├── table_2: "aggregated_by_region" (4 rows)
├── table_3: "aggregated_by_product" (25 rows)
└── table_4: "trend_data" (90 rows)
```

Это полезно когда AI-агент выполняет комплексный анализ:
- Основные данные
- Агрегации по разным измерениям
- Временные ряды
- Статистические метрики

#### Операции с ContentNode

```python
class ContentNode:
    """Content node operations"""
    
    async def transform(
        self, 
        prompt: str,
        additional_sources: List[ContentNode] = None
    ) -> ContentNode:
        """
        Создаёт новый ContentNode через трансформацию
        
        Args:
            prompt: Описание требуемой трансформации
            additional_sources: Дополнительные ContentNode для join/merge
        
        Returns:
            Новый ContentNode с результатом трансформации
        """
        transformation = await transformation_agent.generate_code(
            source_nodes=[self] + (additional_sources or []),
            prompt=prompt
        )
        
        result = await executor_agent.execute(transformation)
        
        new_content = ContentNode(
            content=result.content,
            lineage={
                "source_node_ids": [self.id] + [s.id for s in additional_sources or []],
                "transformation_id": transformation.id,
                "operation": "transform"
            }
        )
        
        # Создать TRANSFORMATION edge
        await create_edge(
            edge_type="TRANSFORMATION",
            from_node_ids=[self.id] + [s.id for s in additional_sources or []],
            to_node_id=new_content.id,
            transformation_id=transformation.id
        )
        
        return new_content
    
    async def visualize(
        self, 
        chart_type: str = None,
        table_ids: List[str] = None
    ) -> WidgetNode:
        """
        Создаёт WidgetNode для визуализации
        
        Args:
            chart_type: Тип визуализации (bar, line, pie, table)
            table_ids: Какие таблицы визуализировать (если None - все)
        
        Returns:
            WidgetNode с HTML/CSS/JS кодом
        """
        # Определить, какие таблицы визуализировать
        tables_to_visualize = self.content["tables"]
        if table_ids:
            tables_to_visualize = [
                t for t in tables_to_visualize 
                if t["id"] in table_ids
            ]
        
        # Reporter Agent генерирует код визуализации
        widget = await reporter_agent.generate_widget(
            content_node=self,
            tables=tables_to_visualize,
            chart_type=chart_type
        )
        
        # Создать VISUALIZATION edge
        await create_edge(
            edge_type="VISUALIZATION",
            from_node_id=self.id,
            to_node_id=widget.id,
            metadata={
                "visualized_tables": [t["id"] for t in tables_to_visualize]
            }
        )
        
        return widget
    
    async def export(self, format: str) -> bytes:
        """Экспорт данных (CSV, JSON, Excel)"""
        pass
    
    async def add_comment(self, text: str, author: str) -> CommentNode:
        """Добавить комментарий к ContentNode"""
        pass
    
    def get_table(self, table_id: str) -> Dict:
        """Получить конкретную таблицу по ID"""
        for table in self.content["tables"]:
            if table["id"] == table_id:
                return table
        return None
```

#### UI представление

```
┌────────────────────────────────────────┐
│  📄 Content: Q1 2026 Sales Data        │
│  ──────────────────────────────────────│
│  Extracted 15,234 sales records...     │
│                                        │
│  📊 Tables (3):                        │
│  ┌─ sales_data (15,234 rows)          │
│  ┌─ aggregated_by_region (4 rows)     │
│  └─ trend_data (90 rows)               │
│                                        │
│  [👁️ Preview] [📈 Visualize] [💾 Export]│
└────────────────────────────────────────┘
```

---

### 3. WidgetNode (Визуализация)

**Назначение**: Визуализация данных из ContentNode с помощью HTML/CSS/JS кода.

#### Структура данных

```json
{
  "id": "widget_123",
  "type": "widget_node",
  
  "widget_config": {
    "title": "Sales by Region",
    "description": "Bar chart showing revenue distribution",
    "chart_type": "bar",
    "html_code": "<div id=\"chart\">...</div>",
    "css_code": ".chart { ... }",
    "js_code": "const data = ...; Chart.js config..."
  },
  
  "data_binding": {
    "content_node_id": "content_123",
    "table_ids": ["table_2"],  // Какие таблицы используются
    "columns_used": ["region", "revenue"]
  },
  
  "layout": {
    "position": {"x": 800, "y": 100},
    "size": {"width": 600, "height": 400}
  },
  
  "metadata": {
    "generated_by": "reporter_agent",
    "created_at": "2026-01-29T10:20:00Z"
  },
  
  "board_id": "board_456"
}
```

#### Множественные таблицы в одном виджете

WidgetNode может использовать **несколько таблиц** из одного ContentNode:

```javascript
// Пример: Dashboard widget использующий 3 таблицы
const widgetCode = `
  <div class="dashboard">
    <!-- Таблица 1: KPI метрики -->
    <div class="metrics">
      ${renderMetrics(table_1_data)}
    </div>
    
    <!-- Таблица 2: Региональное распределение -->
    <div class="regional-chart">
      ${renderBarChart(table_2_data)}
    </div>
    
    <!-- Таблица 3: Временной тренд -->
    <div class="trend-chart">
      ${renderLineChart(table_3_data)}
    </div>
  </div>
`;
```

#### Множественные виджеты для одного ContentNode

Один ContentNode может иметь **несколько WidgetNode**:

```
ContentNode "Sales Data"
├── WidgetNode "Sales by Region" (bar chart, table_2)
├── WidgetNode "Product Performance" (pie chart, table_3)
├── WidgetNode "Trend Analysis" (line chart, table_4)
└── WidgetNode "Raw Data Table" (table, table_1)
```

---

### 4. CommentNode (Комментарии)

**Назначение**: Аннотации и комментарии к любым нодам (Source, Content, Widget).

#### Структура данных

```json
{
  "id": "comment_123",
  "type": "comment_node",
  
  "text": "This data shows unusual spike on Jan 15 - needs investigation",
  
  "target": {
    "node_id": "content_123",
    "node_type": "content_node",
    "table_id": "table_1",  // Опционально: комментарий к конкретной таблице
    "column": "amount"      // Опционально: комментарий к колонке
  },
  
  "metadata": {
    "author": "user_123",
    "author_type": "user",  // или "ai_agent"
    "created_at": "2026-01-29T11:00:00Z"
  },
  
  "position": {"x": 650, "y": 200},
  "board_id": "board_456"
}
```

#### CommentNode может быть привязан к:

1. **SourceNode**: "This database connection is slow, consider caching"
2. **ContentNode**: "Data quality issue: 234 null values in 'amount' column"
3. **WidgetNode**: "Add interactive filters to this chart"
4. **Конкретной таблице**: "Table 'sales_data' needs deduplication"
5. **Конкретной колонке**: "Column 'region' has inconsistent naming"

---

## 🔗 Типы связей (Edges)

### 1. EXTRACT (SourceNode → ContentNode)

**Назначение**: Извлечение данных из источника

```json
{
  "edge_type": "EXTRACT",
  "from_node_id": "source_123",
  "to_node_id": "content_123",
  "metadata": {
    "extracted_at": "2026-01-29T10:15:00Z",
    "status": "success",
    "duration_ms": 3450,
    "rows_extracted": 15234
  }
}
```

**Визуализация**: Зелёная стрелка с иконкой загрузки

### 2. TRANSFORMATION (ContentNode(s) → ContentNode)

**Назначение**: Преобразование данных через произвольный Python код

```json
{
  "edge_type": "TRANSFORMATION",
  "from_node_ids": ["content_123", "content_456"],
  "to_node_id": "content_789",
  "transformation_id": "transform_999",
  "metadata": {
    "prompt": "Join sales with customer data by customer_id",
    "executed_at": "2026-01-29T10:20:00Z"
  }
}
```

**Визуализация**: Синяя стрелка с иконкой кода

### 3. VISUALIZATION (ContentNode → WidgetNode)

**Назначение**: Визуализация данных

```json
{
  "edge_type": "VISUALIZATION",
  "from_node_id": "content_123",
  "to_node_id": "widget_123",
  "metadata": {
    "visualized_tables": ["table_2", "table_4"],
    "chart_type": "bar"
  }
}
```

**Визуализация**: Фиолетовая стрелка с иконкой графика

### 4. COMMENT (CommentNode → Any Node)

**Назначение**: Комментирование

```json
{
  "edge_type": "COMMENT",
  "from_node_id": "comment_123",
  "to_node_id": "content_123",
  "metadata": {
    "author": "user_123",
    "created_at": "2026-01-29T11:00:00Z"
  }
}
```

**Визуализация**: Пунктирная линия с иконкой комментария

---

## 🔄 Примеры потоков данных

### Пример 1: Простой поток (Файл → Визуализация)

```
┌──────────────┐   EXTRACT   ┌──────────────┐   VISUAL   ┌──────────────┐
│ SourceNode   │────────────>│ ContentNode  │─────────-->│ WidgetNode   │
│ Type: file   │             │ sales.csv    │            │ Bar Chart    │
│ sales.csv    │             │ 1000 rows    │            │              │
└──────────────┘             └──────────────┘            └──────────────┘
```

### Пример 2: AI-генерация данных

```
┌──────────────┐   EXTRACT   ┌──────────────┐   VISUAL   ┌──────────────┐
│ SourceNode   │────────────>│ ContentNode  │─────────-->│ WidgetNode   │
│ Type: prompt │             │ Generated    │            │ Dashboard    │
│ "Generate    │             │ synthetic    │            │              │
│ sales data"  │             │ data + stats │            │              │
└──────────────┘             └──────────────┘            └──────────────┘
```

### Пример 3: Join двух источников

```
┌──────────────┐   EXTRACT   ┌──────────────┐
│ SourceNode   │────────────>│ ContentNode  │
│ Type: db     │             │ Orders       │──┐
│ orders table │             └──────────────┘  │
└──────────────┘                               │ TRANSFORM
                                               │ (join)
┌──────────────┐   EXTRACT   ┌──────────────┐  │
│ SourceNode   │────────────>│ ContentNode  │──┘
│ Type: api    │             │ Customers    │    
│ CRM API      │             └──────────────┘    
└──────────────┘                   │
                                   ↓
                            ┌──────────────┐   VISUAL   ┌──────────────┐
                            │ ContentNode  │─────────-->│ WidgetNode   │
                            │ Enriched     │            │ Report       │
                            │ Orders       │            │              │
                            └──────────────┘            └──────────────┘
```

### Пример 4: Комплексный pipeline с комментариями

```
┌──────────────┐   EXTRACT   ┌──────────────┐   TRANSFORM   ┌──────────────┐
│ SourceNode   │────────────>│ ContentNode  │──────────────>│ ContentNode  │
│ Type: db     │             │ Raw Sales    │   (filter)    │ Filtered     │
│ PostgreSQL   │             └──────────────┘               └──────────────┘
└──────────────┘                    ↑                              ↓
                                    │                         VISUALIZE
                              ┌─────┴──────┐                      ↓
                              │CommentNode │               ┌──────────────┐
                              │"Check nulls"│               │ WidgetNode   │
                              └────────────┘               │ Charts       │
                                                           └──────────────┘
                                                                  ↑
                                                            ┌─────┴──────┐
                                                            │CommentNode │
                                                            │"Add filters"│
                                                            └────────────┘
```

---

## 🎨 UI/UX концепция

### Канвас с разными типами нод

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GIGABOARD CANVAS                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────┐       ┌────────────────┐       ┌────────────┐ │
│  │ 📊 Source      │──────>│ 📄 Content     │──────>│ 📈 Widget  │ │
│  │ Sales DB       │Extract│ Sales Data     │Visual │ Bar Chart  │ │
│  │                │       │ 15K rows       │       │            │ │
│  │ [🔄 Extract]   │       │ [👁️ Preview]   │       │ [Revenue]  │ │
│  └────────────────┘       └────────────────┘       └────────────┘ │
│         ↓                        ↓                                 │
│    [💬 Comment]              [💬 Comment]                          │
│    "Connection               "Check nulls"                         │
│     is slow"                                                       │
│                                                                     │
│  ┌────────────────┐       ┌────────────────┐                      │
│  │ 🤖 Source      │──────>│ 📄 Content     │                      │
│  │ AI Prompt      │Extract│ AI Analysis    │                      │
│  │                │       │ text + 3 tables│                      │
│  │ "Analyze sales"│       │                │                      │
│  └────────────────┘       └────────────────┘                      │
│                                  │                                 │
│                                  └──────────┬─────────┐            │
│                                             ↓         ↓            │
│                                    ┌─────────────┐ ┌─────────────┐│
│                                    │📈 Widget    │ │📈 Widget    ││
│                                    │ Metrics     │ │ Trend Chart ││
│                                    └─────────────┘ └─────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Контекстное меню для разных типов нод

**SourceNode**:
- 🔄 Extract Data
- ⚙️ Configure
- 🔍 Validate Connection
- 🕐 Schedule Refresh
- 💬 Add Comment
- 🗑️ Delete

**ContentNode**:
- 👁️ Preview Data
- 📊 Transform Data
- 📈 Create Visualization
- 💾 Export (CSV/JSON/Excel)
- 🔗 Merge with Another
- 💬 Add Comment
- 🗑️ Delete

**WidgetNode**:
- 🎨 Edit Visualization
- 🔄 Refresh Data
- 📥 Download Image
- 💬 Add Comment
- 🗑️ Delete

---

## 🔧 Схема базы данных

```sql
-- Source nodes (источники данных)
CREATE TABLE source_nodes (
    id UUID PRIMARY KEY,
    board_id UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,  -- prompt, file, database, api, stream, manual
    config JSONB NOT NULL,             -- Конфигурация источника
    metadata JSONB NOT NULL,           -- Метаданные (title, description, status)
    position JSONB NOT NULL,           -- {x, y}
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Content nodes (результаты обработки)
CREATE TABLE content_nodes (
    id UUID PRIMARY KEY,
    board_id UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    content JSONB NOT NULL,            -- {text, tables: [...]}
    lineage JSONB NOT NULL,            -- {source_node_id, transformation_id, operation}
    metadata JSONB NOT NULL,           -- Метаданные (title, description, size)
    position JSONB NOT NULL,           -- {x, y}
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Widget nodes (визуализации)
CREATE TABLE widget_nodes (
    id UUID PRIMARY KEY,
    board_id UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    widget_config JSONB NOT NULL,      -- {title, chart_type, html_code, css_code, js_code}
    data_binding JSONB NOT NULL,       -- {content_node_id, table_ids, columns_used}
    layout JSONB NOT NULL,             -- {position: {x, y}, size: {width, height}}
    metadata JSONB NOT NULL,           -- {generated_by, created_at}
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Comment nodes (комментарии)
CREATE TABLE comment_nodes (
    id UUID PRIMARY KEY,
    board_id UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    target JSONB NOT NULL,             -- {node_id, node_type, table_id?, column?}
    metadata JSONB NOT NULL,           -- {author, author_type, created_at}
    position JSONB NOT NULL,           -- {x, y}
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Edges (связи между нодами)
CREATE TABLE edges (
    id UUID PRIMARY KEY,
    board_id UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    edge_type VARCHAR(50) NOT NULL,    -- EXTRACT, TRANSFORMATION, VISUALIZATION, COMMENT
    from_node_ids UUID[],              -- Массив для TRANSFORMATION (может быть несколько источников)
    to_node_id UUID NOT NULL,
    transformation_id UUID,            -- Ссылка на transformations, если edge_type = TRANSFORMATION
    metadata JSONB,                    -- Дополнительные метаданные
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Transformations (код трансформаций)
CREATE TABLE transformations (
    id UUID PRIMARY KEY,
    prompt TEXT NOT NULL,
    generated_code TEXT NOT NULL,
    source_node_ids UUID[] NOT NULL,
    target_node_id UUID NOT NULL,
    input_mapping JSONB NOT NULL,
    execution_metadata JSONB,
    replay_enabled BOOLEAN DEFAULT TRUE,
    schedule VARCHAR(100),
    version INTEGER DEFAULT 1,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_source_nodes_board ON source_nodes(board_id);
CREATE INDEX idx_content_nodes_board ON content_nodes(board_id);
CREATE INDEX idx_widget_nodes_board ON widget_nodes(board_id);
CREATE INDEX idx_comment_nodes_board ON comment_nodes(board_id);
CREATE INDEX idx_edges_board ON edges(board_id);
CREATE INDEX idx_edges_from ON edges USING GIN(from_node_ids);
CREATE INDEX idx_edges_to ON edges(to_node_id);
```

---

## 📋 API Endpoints

### SourceNode

```
POST   /api/v1/boards/{board_id}/source-nodes          - Создать SourceNode
GET    /api/v1/boards/{board_id}/source-nodes          - Список SourceNode
GET    /api/v1/source-nodes/{node_id}                  - Получить SourceNode
PUT    /api/v1/source-nodes/{node_id}                  - Обновить SourceNode
DELETE /api/v1/source-nodes/{node_id}                  - Удалить SourceNode

POST   /api/v1/source-nodes/{node_id}/extract          - Извлечь данные → ContentNode
POST   /api/v1/source-nodes/{node_id}/validate         - Проверить подключение
POST   /api/v1/source-nodes/{node_id}/schedule-refresh - Настроить auto-refresh
```

### ContentNode

```
GET    /api/v1/boards/{board_id}/content-nodes         - Список ContentNode
GET    /api/v1/content-nodes/{node_id}                 - Получить ContentNode
GET    /api/v1/content-nodes/{node_id}/preview         - Preview данных
DELETE /api/v1/content-nodes/{node_id}                 - Удалить ContentNode

POST   /api/v1/content-nodes/{node_id}/transform       - Трансформация → новый ContentNode
POST   /api/v1/content-nodes/{node_id}/visualize       - Создать WidgetNode
POST   /api/v1/content-nodes/{node_id}/export          - Экспорт (CSV/JSON/Excel)
GET    /api/v1/content-nodes/{node_id}/tables/{table_id} - Получить конкретную таблицу
```

### WidgetNode

```
GET    /api/v1/boards/{board_id}/widget-nodes          - Список WidgetNode
GET    /api/v1/widget-nodes/{node_id}                  - Получить WidgetNode
PUT    /api/v1/widget-nodes/{node_id}                  - Обновить WidgetNode
DELETE /api/v1/widget-nodes/{node_id}                  - Удалить WidgetNode

POST   /api/v1/widget-nodes/{node_id}/refresh          - Обновить данные виджета
```

### CommentNode

```
POST   /api/v1/boards/{board_id}/comment-nodes         - Создать CommentNode
GET    /api/v1/boards/{board_id}/comment-nodes         - Список CommentNode
GET    /api/v1/comment-nodes/{node_id}                 - Получить CommentNode
PUT    /api/v1/comment-nodes/{node_id}                 - Обновить CommentNode
DELETE /api/v1/comment-nodes/{node_id}                 - Удалить CommentNode
```

### Edges

```
POST   /api/v1/boards/{board_id}/edges                 - Создать связь
GET    /api/v1/boards/{board_id}/edges                 - Список связей
DELETE /api/v1/edges/{edge_id}                         - Удалить связь
```

---

## 🚀 Миграция с текущей модели

### Стратегия миграции

**Текущая модель**: DataNode (универсальная)  
**Новая модель**: SourceNode + ContentNode

#### Вариант 1: Автоматическое разделение

Все существующие `DataNode` анализируются и разделяются:

```python
def migrate_data_node(data_node):
    """
    Логика миграции:
    - Если DataNode.source существует → создаём SourceNode + ContentNode
    - Если DataNode.source == None → создаём только ContentNode
    """
    if data_node.source:
        # Создать SourceNode
        source_node = SourceNode(
            board_id=data_node.board_id,
            source_type=data_node.source["type"],
            config=data_node.source["details"],
            position=data_node.position
        )
        
        # Создать ContentNode
        content_node = ContentNode(
            board_id=data_node.board_id,
            content={
                "text": "",
                "tables": [{
                    "id": "table_1",
                    "name": "data",
                    "columns": data_node.schema["columns"],
                    "row_count": data_node.statistics["row_count"]
                }]
            },
            lineage={
                "source_node_id": source_node.id,
                "transformation_id": None,
                "operation": "extract"
            },
            position={"x": data_node.position["x"] + 350, "y": data_node.position["y"]}
        )
        
        # Создать EXTRACT edge
        create_edge(
            edge_type="EXTRACT",
            from_node_id=source_node.id,
            to_node_id=content_node.id
        )
        
        return source_node, content_node
    else:
        # Создать только ContentNode (результат трансформации)
        return ContentNode(
            board_id=data_node.board_id,
            content={
                "text": "",
                "tables": [{
                    "id": "table_1",
                    "name": "data",
                    "columns": data_node.schema["columns"],
                    "row_count": data_node.statistics["row_count"]
                }]
            },
            lineage={
                "source_node_id": None,
                "transformation_id": data_node.transformation_id,
                "operation": "transform"
            },
            position=data_node.position
        )
```

#### Вариант 2: Постепенная миграция

- Новые ноды создаются по новой модели
- Старые DataNode остаются до ручного обновления
- UI показывает legacy badge на старых нодах

---

## ✅ Преимущества новой модели

1. **Чёткая семантика**:
   - SourceNode = "откуда"
   - ContentNode = "что"
   - WidgetNode = "как показать"

2. **Улучшенный Data Lineage**:
   - Явное отслеживание источников
   - Прозрачная цепочка трансформаций

3. **Упрощение refresh/replay**:
   - SourceNode.refresh() → обновляет ContentNode
   - Автоматический пересчёт downstream нод

4. **Гибкость**:
   - ContentNode может содержать N таблиц
   - WidgetNode может визуализировать любую комбинацию таблиц

5. **Точка входа для пользователя**:
   - SourceNode — явный UI-элемент для добавления данных
   - Промпт, файл, БД, API — всё в одной концепции

---

## ✅ Решения по ключевым вопросам

### 1. **Файлы-промежуточные результаты**
**Решение**: Это отдельный **SourceNode**

Если ContentNode экспортируется в файл, а затем загружается обратно — создаётся новый SourceNode с type: file.

```
ContentNode_A → Export CSV → File on disk
File on disk → Upload → SourceNode_B → ContentNode_B
```

### 2. **Streaming sources** ✨

**Решение**: Аккумуляция данных с архивированием и гибкими режимами обновления

#### Стратегия хранения данных

```typescript
type StreamBufferStrategy = "accumulate_with_archive";

// Все данные аккумулируются в ContentNode
// При достижении лимита, старые данные автоматически вытесняются в архив
const streamConfig = {
  buffer_strategy: "accumulate_with_archive",
  buffer_config: {
    max_active_rows: 10000,      // Последние 10K в ContentNode
    archive_threshold: 8000,      // При 8K начинать архивирование
    archive_batch_size: 2000,     // Архивировать по 2K записей
    archive_storage: "s3://bucket/archive/"
  }
}
```

#### Режимы обновления ContentNode

**Режим 1: Автоматический с интервалом** (по умолчанию)
```json
{
  "content_update_mode": "interval",
  "content_update_interval_ms": 5000,
  "adaptive_interval": true  // Увеличивает интервал при высокой нагрузке
}
```

**Режим 2: Обновление по кнопке**
```json
{
  "content_update_mode": "manual",
  "accumulate_in_background": true,  // Накапливать данные, но не обновлять UI
  "show_pending_count": true         // Показать "234 new records pending"
}
```

#### Replay трансформаций для streaming

**Smart Throttled Auto-Replay** с несколькими режимами:

```python
class StreamReplayStrategy:
    """
    Гибкая система replay для streaming источников
    """
    
    # Режим 1: Throttled (ограничение частоты)
    THROTTLED = {
        "auto_replay": True,
        "min_interval_ms": 10000,     # Минимум 10 сек между replay
        "adaptive": True,              # Адаптивный интервал
        "priority": "high"
    }
    
    # Режим 2: Batched (пакетная обработка)
    BATCHED = {
        "auto_replay": True,
        "batch_size": 500,             # Накопить 500 новых записей
        "max_wait_ms": 60000,          # Или максимум 1 минута
        "on_trigger": "replay_all"
    }
    
    # Режим 3: Manual (только по кнопке)
    MANUAL = {
        "auto_replay": False,
        "notify_user": True,           # Показать бадж "Data Updated"
        "show_replay_button": True,
        "show_stale_indicator": True   # "⚠️ Analysis outdated"
    }
    
    # Режим 4: Intelligent (AI-based решения)
    INTELLIGENT = {
        "auto_replay": True,
        "analyze_changes": True,
        "threshold_percent": 5,        # Replay если изменилось >5%
        "significant_fields": ["price", "volume"],
        "ml_based": True
    }
    
    # Режим 5: Selective (выборочный по приоритету)
    SELECTIVE = {
        "high_priority": {"auto_replay": True, "interval_ms": 5000},
        "medium_priority": {"auto_replay": True, "interval_ms": 30000},
        "low_priority": {"auto_replay": False, "manual_only": True}
    }
```

**Пример конфигурации**:

```json
{
  "id": "source_123",
  "type": "source_node",
  "source_type": "stream",
  
  "config": {
    "stream_type": "websocket",
    "url": "wss://stream.binance.com/btcusdt",
    
    "connection": {
      "auth": {...},
      "reconnect": true,
      "reconnect_delay_ms": 5000
    },
    
    "buffer_strategy": "accumulate_with_archive",
    "buffer_config": {
      "max_active_rows": 10000,
      "archive_threshold": 8000,
      "archive_storage": "s3://gigaboard/archives/"
    },
    
    "content_update_mode": "interval",
    "content_update_interval_ms": 2000,
    
    "replay_strategy": {
      "mode": "throttled",
      "interval_ms": 10000,
      "adaptive": true,
      "priority": "high"
    }
  },
  
  "state": {
    "status": "ACTIVE",
    "records_received": 45678,
    "records_archived": 35000,
    "active_records": 10678,
    "last_update": "2026-01-29T12:30:00Z",
    "connection_uptime_seconds": 7200
  }
}
```

**UI для streaming источников**:

```
┌─────────────────────────────────────────────────┐
│ 🌊 Source: Stock Price Stream                   │
│ ───────────────────────────────────────────────  │
│ Type: WebSocket (BTC/USDT)                      │
│                                                 │
│ Status: 🔴 LIVE                                 │
│ Records: 45,678 total | 10,678 active          │
│ Archived: 35,000 records                        │
│ Rate: 3,245 records/min                         │
│ Uptime: 2h 15m                                  │
│                                                 │
│ Updates: ⚡ Auto (every 2 sec)                  │
│ Replay: 🔄 Throttled (every 10 sec)             │
│                                                 │
│ [⏸️ Pause] [⏹️ Stop] [⚙️ Config] [📦 Archive]   │
└─────────────────────────────────────────────────┘
        ↓ EXTRACT (streaming)
┌─────────────────────────────────────────────────┐
│ 📄 Content: BTC/USDT Live Data                  │
│ ───────────────────────────────────────────────  │
│ 🔴 LIVE | Updated 2 sec ago                     │
│                                                 │
│ 📊 Active Data (10,678 rows)                    │
│ 📦 Archived (35,000 rows)                       │
│                                                 │
│ 💾 Pending updates: 234 records                 │
│                                                 │
│ [👁️ Preview] [⏸️ Freeze] [🔄 Manual Update]     │
│ [📈 Visualize] [📦 View Archive]                │
└─────────────────────────────────────────────────┘
        ↓ TRANSFORM (throttled, 10 sec)
┌─────────────────────────────────────────────────┐
│ 📄 Content: Price Analysis                      │
│ ───────────────────────────────────────────────  │
│ ⚠️ Last updated 8 sec ago                       │
│ 💡 234 new records pending analysis             │
│                                                 │
│ [🔄 Refresh Analysis Now]                       │
└─────────────────────────────────────────────────┘
```

**Layered Updates (многослойное обновление)**:

```
Stream ─→ ContentNode (Raw)        [2 sec updates]
            ↓
         ContentNode (Aggregated)   [10 sec updates, auto-replay]
            ↓
         ContentNode (Analytics)    [60 sec updates, auto-replay]
            ↓
         WidgetNode (Dashboard)     [60 sec refresh]
```

### 3. **Версионирование ContentNode**

**Решение**: SourceNode.refresh() **обновляет существующий** ContentNode

```python
class SourceNode:
    async def refresh(self) -> ContentNode:
        """
        Повторное извлечение данных
        Обновляет существующий ContentNode, а не создаёт новый
        """
        # Найти существующий ContentNode, созданный из этого SourceNode
        existing_content = await db.content_nodes.find_one({
            "lineage.source_node_id": self.id
        })
        
        # Извлечь новые данные
        new_data = await self.extract_data()
        
        if existing_content:
            # Обновить существующий
            await db.content_nodes.update_one(
                {"id": existing_content.id},
                {"$set": {
                    "content": new_data.content,
                    "updated_at": datetime.now()
                }}
            )
            
            # Сохранить версию в истории (опционально)
            await db.content_node_history.insert_one({
                "content_node_id": existing_content.id,
                "version": existing_content.version + 1,
                "content": existing_content.content,
                "timestamp": datetime.now()
            })
            
            return existing_content
        else:
            # Создать новый, если не существует
            return await self.extract()
```

**История версий** (опционально):
```sql
CREATE TABLE content_node_history (
    id UUID PRIMARY KEY,
    content_node_id UUID NOT NULL,
    version INTEGER NOT NULL,
    content JSONB NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    
    FOREIGN KEY (content_node_id) REFERENCES content_nodes(id) ON DELETE CASCADE
);
```

### 4. **Cascade delete**

**Решение**: Удаление SourceNode **удаляет все downstream** ContentNode/WidgetNode

```sql
-- При удалении SourceNode каскадно удаляются все связанные ноды
DELETE FROM source_nodes WHERE id = 'source_123';
-- ↓
-- Удаляет edges (EXTRACT)
-- ↓
-- Удаляет ContentNode, созданные из этого источника
-- ↓
-- Удаляет edges (TRANSFORMATION, VISUALIZATION)
-- ↓
-- Удаляет downstream ContentNode и WidgetNode
```

**UI предупреждение**:

```
┌────────────────────────────────────────────────┐
│ ⚠️ Delete Source Node                          │
├────────────────────────────────────────────────┤
│                                                │
│ This will delete:                              │
│ • Source: Sales Database                       │
│ • 3 Content nodes                              │
│ • 7 Widget nodes                               │
│ • 12 edges                                     │
│                                                │
│ This action cannot be undone.                  │
│                                                │
│ [Cancel]  [Delete Everything]                  │
└────────────────────────────────────────────────┘
```

**Опция: Soft Delete** (сохранить данные):

```python
class SourceNode:
    async def soft_delete(self):
        """
        Мягкое удаление: отключить источник, но сохранить данные
        """
        # Отключить SourceNode
        await db.source_nodes.update_one(
            {"id": self.id},
            {"$set": {
                "status": "disconnected",
                "deleted_at": datetime.now()
            }}
        )
        
        # ContentNode остаются, но помечаются как "orphaned"
        await db.content_nodes.update_many(
            {"lineage.source_node_id": self.id},
            {"$set": {"lineage.source_disconnected": True}}
        )
```

---

## 🎯 Итоговая архитектура Streaming

### Полный пример: Real-time Financial Dashboard

```
┌──────────────────────┐
│  SourceNode          │
│  Type: WebSocket     │  ← Пользователь настраивает:
│  BTC/USDT Stream     │    • Auto update: 2 sec
│                      │    • Replay: Throttled 10 sec
│  🔴 LIVE             │    • Archive: 10K rows
│  45,678 records      │
└──────────────────────┘
        ↓ EXTRACT (streaming, 2 sec)
┌──────────────────────┐
│  ContentNode         │
│  Raw Price Data      │  ← Аккумуляция + архивирование
│                      │    • Active: 10,678 rows
│  Tables:             │    • Archived: 35,000 rows
│  • raw_prices        │
│  • live_stats        │
└──────────────────────┘
        ↓ TRANSFORM (throttled, 10 sec)
┌──────────────────────┐
│  ContentNode         │
│  Moving Averages     │  ← Auto-replay каждые 10 сек
│                      │
│  Tables:             │
│  • ma_5min           │
│  • ma_15min          │
└──────────────────────┘
        ↓ VISUALIZE (auto-refresh 10 sec)
┌──────────────────────┐
│  WidgetNode          │
│  Live Price Chart    │  ← Автообновление
│  🔴 LIVE             │    • [⏸️ Freeze] для анализа
│  [Line Chart]        │
└──────────────────────┘
```

---

**Статус**: ✅ Концепция финализирована и готова к реализации
