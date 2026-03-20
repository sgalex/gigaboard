# GigaBoard: Система доски (Board System)

## 🎯 Executive Summary

GigaBoard построен на парадигме **Data-Centric Canvas** — бесконечное полотно, где **данные первичны, визуализация вторична**. Пользователь строит data pipeline из узлов, соединяя их рёбрами. AI-агенты автоматизируют трансформации и создание визуализаций.

**Ключевые принципы:**
- Каждый объект на доске — это узел одного из 4 типов
- Узлы связываются рёбрами одного из 5 типов
- Направление рёбер отражает поток данных: SourceNode → ContentNode → WidgetNode
- SourceNode наследует ContentNode: хранит и конфигурацию источника, и извлечённые данные в одной ноде
- Автоматический replay — обновление source пересчитывает весь pipeline
- **Cross-Filter** — виджеты на доске могут получать отфильтрованные данные по измерениям; см. [CROSS_FILTER_SYSTEM.md](CROSS_FILTER_SYSTEM.md)

---

## 1. Иерархия наследования узлов

```mermaid
classDiagram
    BaseNode <|-- ContentNode
    ContentNode <|-- SourceNode
    BaseNode <|-- WidgetNode
    BaseNode <|-- CommentNode

    class BaseNode {
        +UUID id
        +UUID board_id
        +str node_type
        +int x
        +int y
        +int width
        +int height
        +datetime created_at
        +datetime updated_at
    }

    class ContentNode {
        +dict content
        +dict lineage
        +dict metadata
        +dict position
    }

    class SourceNode {
        +str source_type
        +dict config
        +UUID created_by
    }

    class WidgetNode {
        +str name
        +str html_code
        +str css_code
        +str js_code
        +bool auto_refresh
    }

    class CommentNode {
        +str content
        +str format_type
        +bool is_resolved
    }
```

**Таблицы БД**: `nodes` (BaseNode), `content_nodes`, `source_nodes`, `widget_nodes`, `comment_nodes` — Joined Table Inheritance.

---

## 2. Типы узлов

### 2.1 SourceNode — источник данных

**Назначение**: Точка входа данных в pipeline. Хранит конфигурацию источника и извлечённые данные одновременно.

**Правила создания**:
- Создаётся пользователем через drag & drop из витрины источников на доску
- После drop открывается диалог настройки конкретного типа источника
- Данные извлекаются в момент создания и сохраняются в `content`
- Не создаётся автоматически агентами

**Поля** (`source_nodes` + `content_nodes` + `nodes`):

| Поле          | Тип     | Описание                                                                           |
| ------------- | ------- | ---------------------------------------------------------------------------------- |
| `source_type` | `str`   | Тип источника: csv, json, excel, document, api, database, research, manual, stream |
| `config`      | `JSONB` | Конфигурация подключения/извлечения (зависит от source_type)                       |
| `created_by`  | `UUID`  | FK на users — кто создал                                                           |
| `content`     | `JSONB` | `{text: str, tables: [{name, columns, rows}]}` — извлечённые данные                |
| `lineage`     | `JSONB` | Data lineage: `{operation: "extract", ...}`                                        |
| `x`, `y`      | `int`   | Позиция на канвасе                                                                 |

**9 типов источников** (`SourceType` enum):

| Тип        | Описание                | Экстрактор                                                    | Статус                |
| ---------- | ----------------------- | ------------------------------------------------------------- | --------------------- |
| `csv`      | CSV файлы               | `CSVSource` — auto-detect encoding + separator + column types | ✅ реализован          |
| `json`     | JSON файлы              | `JSONSource`                                                  | ✅ реализован          |
| `excel`    | Excel .xlsx/.xls        | `ExcelSource` — spreadsheet grid + smart detect + regions     | ✅ реализован          |
| `document` | PDF/DOCX/TXT            | `DocumentSource` — multi-agent + fallback                     | ⚠️ частично            |
| `api`      | REST API                | `APISource` — GET/POST, auth, retry                           | ✅ реализован          |
| `database` | PostgreSQL/MySQL/SQLite | `DatabaseSource`                                              | ✅ реализован          |
| `research` | AI Research             | `ResearchSource` → `ResearchController` → Orchestrator (discovery → research → structurizer → analyst → reporter) | ✅ multi-agent |
| `manual`   | Ручной ввод             | `ManualSource` — table constructor                            | ✅ реализован          |
| `stream`   | WebSocket/SSE           | `StreamSource` — stub                                         | ❌ Phase 4             |

**Структура `content`**:
```json
{
  "text": "Sales data Q1 2024. 1500 rows, 5 columns.",
  "tables": [
    {
      "name": "Sales",
      "columns": [
        {"name": "region", "type": "string"},
        {"name": "amount", "type": "number"},
        {"name": "date",   "type": "string"}
      ],
      "rows": [
        {"region": "North", "amount": 45000, "date": "2024-01-15"}
      ],
      "row_count": 1500,
      "column_count": 5
    }
  ]
}
```

**Конфиги по типам**:

<details>
<summary>Конфиги source_type (развернуть)</summary>

```json
// csv / json / excel / document
{
  "file_id":      "uuid",
  "filename":     "sales.csv",
  "delimiter":    ",",
  "encoding":     "utf-8",
  "has_header":   true
}

// api
{
  "url":    "https://api.example.com/data",
  "method": "GET",
  "headers": {"Authorization": "Bearer xxx"},
  "auth":   {"type": "bearer", "token": "xxx"},
  "pagination": {"enabled": true, "type": "page", "page_param": "page", "page_size": 100}
}

// database
{
  "connection_string": "postgresql://user:pass@host:5432/dbname",
  "query":             "SELECT * FROM orders WHERE created_at > '2024-01-01'",
  "database_type":     "postgresql"
}

// research
{
  "initial_prompt":      "Найди статистику продаж электромобилей в России 2024",
  "sources":             ["autostat.ru", "rbc.ru"]
}

// manual
{
  "data":   {"columns": ["category", "amount"], "rows": [["A", 100], ["B", 200]]},
  "format": "table"
}

// stream (Phase 4)
{
  "stream_url":             "wss://example.com/stream",
  "stream_type":            "websocket",
  "accumulation_strategy":  "append",
  "refresh_interval":       30
}
```
</details>

---

### 2.2 ContentNode — результат обработки

**Назначение**: Результат трансформации одного или нескольких SourceNode/ContentNode.

**Правила создания**:
- Создаётся **только** как результат трансформации (вручную или через агента)
- Не создаётся пользователем напрямую из пустого состояния
- Каждая трансформация создаёт новый ContentNode (не перезаписывает источник)

**Поля** (`content_nodes` + `nodes`):

| Поле       | Тип     | Описание                                                             |
| ---------- | ------- | -------------------------------------------------------------------- |
| `content`  | `JSONB` | `{text: str, tables: [...]}` — обработанные данные                   |
| `lineage`  | `JSONB` | `{source_node_id, transformation_id, operation, parent_content_ids}` |
| `metadata` | `JSONB` | `{row_count, table_count, data_quality, computation_time}`           |
| `position` | `JSONB` | `{x, y}` — позиция для React Flow                                    |
| `x`, `y`   | `int`   | Позиция в BaseNode                                                   |

**Lineage example**:
```json
{
  "source_node_id":    "uuid",
  "transformation_id": "uuid",
  "operation":         "transform",
  "parent_content_ids": ["uuid1", "uuid2"],
  "timestamp":         "2026-02-22T10:00:00Z",
  "agent":             "transformation_agent"
}
```

---

### 2.3 WidgetNode — визуализация

**Назначение**: AI-генерированная HTML/CSS/JS визуализация данных из ContentNode или SourceNode.

**Правила создания**:
- Создаётся через **WidgetCodexAgent** из WidgetDialog (AI-генерация HTML/CSS/JS)
- Требует родительский ContentNode или SourceNode (VISUALIZATION edge обязателен)
- Не существует без привязки к данным
- Удаление родительского ContentNode/SourceNode → каскадное удаление WidgetNode

**Поля** (`widget_nodes` + `nodes`):

| Поле                | Тип          | Описание                                                   |
| ------------------- | ------------ | ---------------------------------------------------------- |
| `name`              | `str`        | Название виджета                                           |
| `description`       | `str`        | Исходный промпт пользователя                               |
| `html_code`         | `Text`       | Сгенерированный HTML                                       |
| `css_code`          | `Text\|None` | Сгенерированный CSS                                        |
| `js_code`           | `Text\|None` | Сгенерированный JS (Chart.js, ECharts, Plotly, D3)         |
| `config`            | `JSON\|None` | Дополнительные настройки                                   |
| `auto_refresh`      | `bool`       | Авто-обновление при изменении данных (по умолчанию `true`) |
| `refresh_interval`  | `int\|None`  | Интервал обновления в секундах                             |
| `generated_by`      | `str\|None`  | `"reporter_agent"` или `"user"`                            |
| `generation_prompt` | `Text\|None` | Промпт, по которому создан виджет                          |
| `width`, `height`   | `int\|None`  | Размер на канвасе (резайзится пользователем)               |

---

### 2.4 CommentNode — аннотация

**Назначение**: Комментарии, заметки, AI-инсайты, привязанные к другим узлам.

**Правила создания**:
- Создаётся пользователем через контекстное меню любого узла
- AI Assistant автоматически создаёт CommentNode с инсайтами (аномалии, паттерны)
- Не создаётся изолированно — всегда привязан к другому узлу через COMMENT edge
- Удаление родительского узла → каскадное удаление CommentNode

**Поля** (`comment_nodes` + `nodes`):

| Поле          | Тип              | Описание                                    |
| ------------- | ---------------- | ------------------------------------------- |
| `author_id`   | `UUID`           | FK на users                                 |
| `content`     | `Text`           | Текст (Markdown/plain/html)                 |
| `format_type` | `str`            | `"markdown"` (default), `"plain"`, `"html"` |
| `color`       | `str\|None`      | HEX цвет заметки                            |
| `is_resolved` | `bool`           | Статус решения (для командной работы)       |
| `resolved_at` | `DateTime\|None` | Когда решено                                |
| `resolved_by` | `UUID\|None`     | FK на users — кто решил                     |

---

## 3. Типы связей (EdgeType)

5 типов рёбер в `EdgeType` enum. Все хранятся в таблице `edges`.

**Матрица допустимых соединений**:

| EdgeType       | От                                  | К                        |
| -------------- | ----------------------------------- | ------------------------ |
| TRANSFORMATION | SourceNode / ContentNode (N входов) | ContentNode (1 выход)    |
| VISUALIZATION  | SourceNode / ContentNode            | WidgetNode               |
| COMMENT        | CommentNode                         | любой узел               |
| REFERENCE      | любой                               | любой                    |
| DRILL_DOWN     | ContentNode / WidgetNode            | ContentNode / WidgetNode |

### 3.1 TRANSFORMATION

Преобразование данных через Python-код. Самый важный тип связи.

**Характеристики**:
- Поддерживает N входных узлов → 1 выходной ContentNode
- Содержит исполняемый Python код в `transformation_code`
- Автоматический replay при изменении source данных
- Код версионируется

**Визуальный стиль**: синяя сплошная линия со стрелкой и иконкой кода `{}`

```mermaid
flowchart LR
    SN["SourceNode\norders.csv"]   -->|TRANSFORMATION| CN["ContentNode\nfiltered_orders"]
    CN2["ContentNode\ncustomers"]  -->|TRANSFORMATION| CN

    style SN  fill:#f3e5f5
    style CN2 fill:#e3f2fd
    style CN  fill:#c8e6c9
```

**Replay-режимы** (5 вариантов):
- `always` — пересчёт при каждом изменении source
- `on_demand` — только по запросу пользователя
- `scheduled` — по расписанию (cron)
- `on_threshold` — при изменении данных сверх порога
- `disabled` — без автоматического replay

### 3.2 VISUALIZATION

Привязывает WidgetNode к данным. Создаётся автоматически при генерации виджета (WidgetCodexAgent).

**Характеристики**:
- Один ContentNode/SourceNode может иметь множество WidgetNode
- WidgetNode авто-обновляется при изменении данных (если `auto_refresh=true`)
- Удаление ContentNode удаляет связанный WidgetNode каскадно

**Визуальный стиль**: фиолетовая пунктирная линия

```mermaid
flowchart TB
    CN["ContentNode\nfilterd sales"] -->|VISUALIZATION| WN1["WidgetNode\nLine Chart"]
    CN                              -->|VISUALIZATION| WN2["WidgetNode\nBar Chart"]

    style CN  fill:#e3f2fd
    style WN1 fill:#fff3e0
    style WN2 fill:#fff3e0
```

### 3.3 COMMENT

Комментарий привязывается к любому узлу.

**Визуальный стиль**: серая пунктирная линия

### 3.4 REFERENCE

Справочная связь без семантики потока данных. Используется для документирования отношений.

**Визуальный стиль**: серая линия с двойной стрелкой

### 3.5 DRILL_DOWN

Навигационная связь от агрегированного виджета/ноды к детальному.

**Характеристики**:
- Клик на элемент виджета → переход к детальному ContentNode/WidgetNode
- Определяет иерархию просмотра: "сводный → детальный → транзакционный"
- Breadcrumb навигация "назад к обзору"

**Визуальный стиль**: оранжевая линия

---

## 4. Правила работы с доской

### 4.1 Правила создания узлов

```
SourceNode    ← создаёт пользователь (drag & drop из витрины)
ContentNode   ← создаётся как результат TRANSFORMATION
WidgetNode    ← создаётся через WidgetCodexAgent из WidgetDialog (требует VISUALIZATION edge)
CommentNode   ← создаёт пользователь или AI через контекстное меню узла
```

### 4.2 Правила удаления

```
Удаление SourceNode/ContentNode → каскадное удаление:
  └── все исходящие TRANSFORMATION → целевой ContentNode (и его цепочка)
  └── все VISUALIZATION → WidgetNode
  └── все COMMENT → CommentNode

Удаление WidgetNode → только WidgetNode (без влияния на данные)
Удаление CommentNode → только CommentNode
Удаление Edge → только Edge (узлы остаются)
```

### 4.3 Правила связей (ограничения)

- **Циклы запрещены**: граф связей TRANSFORMATION — DAG (Directed Acyclic Graph)
- **WidgetNode только принимает**: нет исходящих TRANSFORMATION от WidgetNode
- **CommentNode только исходит**: нет входящих связей в CommentNode, кроме REFERENCE
- **Множественные TRANSFORMATION**: один ContentNode может быть результатом соединения нескольких источников

---

## 5. Витрина источников

Левая боковая панель. Пользователь перетаскивает тип источника на доску — открывается диалог.

```
📂 Источники данных
├── 📊 CSV          — табличные данные
├── { } JSON        — структурированные данные
├── 📗 Excel        — многолистовые таблицы
├── 📄 Документ     — PDF, DOCX, TXT
├── 🔗 API          — REST endpoint
├── 🗄️ База данных  — PostgreSQL, MySQL, SQLite
├── 🔍 AI Research  — поиск через агентов
├── ✏️ Ручной ввод  — table constructor
└── 📡 Стрим        — WebSocket/SSE (Phase 4, stub)
```

**API витрины**: `GET /api/v1/source-nodes/vitrina` — возвращает список для отображения.

---

## 6. Размещение узлов на доске

### 6.1 Автоматическое размещение при создании

При создании нового узла система (`findOptimalNodePosition`) автоматически выбирает позицию без коллизий.

**Стратегия по типу связи**:

```mermaid
flowchart LR
    subgraph TRANSFORMATION ["TRANSFORMATION (горизонтально)"]
        direction LR
        A[Source] -->|"400px →"| B[ContentNode]
    end

    subgraph VISUALIZATION ["VISUALIZATION (вертикально)"]
        direction TB
        C[ContentNode] -->|"↓ 150px"| D[WidgetNode]
    end
```

### 6.2 Алгоритм поиска свободной позиции

1. Вычислить предпочтительную позицию (400px вправо или 150px вниз)
2. Проверить коллизии через AABB с учётом padding
3. Если занято — спиральный поиск с шагом 60px, до 100 попыток
4. Fallback: вернуть предпочтительную позицию (лучше перекрытие, чем отсутствие ноды)

### 6.3 Коррекция при ручном перемещении

При drag & drop пользователем (`findNearestFreePosition`):
- Шаг поиска: 10px (минимальный визуальный сдвиг)
- 8 направлений: 4 основных + диагонали
- Максимум 50 попыток (до 500px сдвига)
- Fallback: остаётся на исходной позиции

**Параметры алгоритма**:

| Параметр         | При создании                | При перемещении       |
| ---------------- | --------------------------- | --------------------- |
| Начальный offset | 150–400px от источника      | 0 (текущая позиция)   |
| Шаг поиска       | 60px                        | 10px                  |
| Направлений      | 4 (приоритет по типу связи) | 8 (включая диагонали) |
| Макс. попыток    | 100                         | 50                    |

---

## 7. Примеры pipeline

### Простой pipeline

```mermaid
flowchart LR
    SN["📊 SourceNode\nsales.csv"]
    CN["ContentNode\nfiltered"]
    WN["WidgetNode\nLine Chart"]

    SN -->|TRANSFORMATION\nfilter amount > 10k| CN
    CN -->|VISUALIZATION| WN

    style SN fill:#f3e5f5
    style CN fill:#e3f2fd
    style WN fill:#fff3e0
```

### Многовходовая трансформация

```mermaid
flowchart LR
    SN1["📊 SourceNode\norders"]
    SN2["🗄️ SourceNode\ncustomers DB"]
    CN["ContentNode\ncustomer LTV"]
    WN["WidgetNode\nTable"]

    SN1 -->|TRANSFORMATION| CN
    SN2 -->|TRANSFORMATION| CN
    CN  -->|VISUALIZATION|  WN

    style SN1 fill:#f3e5f5
    style SN2 fill:#f3e5f5
    style CN  fill:#e3f2fd
    style WN  fill:#fff3e0
```

### Pipeline с комментарием и drill-down

```mermaid
flowchart LR
    SN["📊 SourceNode\nmetrics"]
    CN1["ContentNode\naggregated"]
    WN1["WidgetNode\nOverview Chart"]
    CM["CommentNode\n⚠️ Аномалия!"]
    CN2["ContentNode\ndetailed"]
    WN2["WidgetNode\nDetail Table"]

    SN   -->|TRANSFORMATION|  CN1
    CN1  -->|VISUALIZATION|   WN1
    CM   -->|COMMENT|         WN1
    WN1  -->|DRILL_DOWN|      WN2
    CN1  -->|TRANSFORMATION|  CN2
    CN2  -->|VISUALIZATION|   WN2

    style SN  fill:#f3e5f5
    style CN1 fill:#e3f2fd
    style CN2 fill:#e3f2fd
    style WN1 fill:#fff3e0
    style WN2 fill:#fff3e0
    style CM  fill:#f5f5f5
```

---

## 8. API endpoints (актуальные)

| Endpoint                                                | Метод  | Описание                            |
| ------------------------------------------------------- | ------ | ----------------------------------- |
| `GET /api/v1/source-nodes/vitrina`                      | GET    | Витрина источников для левой панели |
| `POST /api/v1/source-nodes/`                            | POST   | Создать SourceNode                  |
| `GET /api/v1/source-nodes/{id}`                         | GET    | Получить SourceNode                 |
| `PUT /api/v1/source-nodes/{id}`                         | PUT    | Обновить конфигурацию               |
| `POST /api/v1/source-nodes/{id}/refresh`                | POST   | Перезагрузить данные из источника   |
| `POST /api/v1/source-nodes/{id}/validate`               | POST   | Валидация конфигурации              |
| `DELETE /api/v1/source-nodes/{id}`                      | DELETE | Удалить SourceNode                  |
| `GET /api/v1/source-nodes/board/{board_id}`             | GET    | Все SourceNode доски                |
| `POST /api/v1/content-nodes/{id}/transform`             | POST   | Создать трансформацию               |
| `POST /api/v1/content-nodes/{id}/visualize`             | POST   | Создать виджет                      |
| `GET /api/v1/boards/{id}/edges`                         | GET    | Все рёбра доски                     |

---

## Связанные документы

- [DATA_NODE_SYSTEM.md](./DATA_NODE_SYSTEM.md) — детали pipeline и трансформаций
- [CONNECTION_TYPES.md](./CONNECTION_TYPES.md) — полная спецификация типов связей
- [SOURCE_NODE_CONCEPT.md](./SOURCE_NODE_CONCEPT.md) — диалоги настройки источников
- [SMART_NODE_PLACEMENT.md](./SMART_NODE_PLACEMENT.md) — детали алгоритма размещения
- [WIDGET_GENERATION_SYSTEM.md](./WIDGET_GENERATION_SYSTEM.md) — создание виджетов
- [TRANSFORM_SYSTEM.md](./TRANSFORM_SYSTEM.md) — система трансформаций
- [COLLABORATIVE_FEATURES.md](./COLLABORATIVE_FEATURES.md) — совместная работа, CommentNode
- [DRILL_DOWN_SYSTEM.md](./DRILL_DOWN_SYSTEM.md) — drill-down навигация
- [CROSS_FILTER_SYSTEM.md](./CROSS_FILTER_SYSTEM.md) — глобальные фильтры и измерения
