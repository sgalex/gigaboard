# Source-Content Node Architecture: План реализации

**Дата**: 29 января 2026  
**Статус**: 📋 Roadmap  
**Цель**: Миграция с DataNode на SourceNode + ContentNode архитектуру

---

## 🎯 Краткое резюме

Переход от универсальной **DataNode** к специализированным:
- **SourceNode** — точка входа данных (файл, БД, API, промпт, stream)
- **ContentNode** — результаты обработки (текст + N таблиц)
- **WidgetNode** — визуализация (без изменений)
- **CommentNode** — комментарии к любым нодам (без изменений)

---

## 📅 Фазы реализации

### Phase 1: Database Schema & Models (1-2 дня)

#### 1.1 Создать новые таблицы

```sql
-- apps/backend/migrations/versions/xxx_add_source_content_nodes.py

-- Source nodes
CREATE TABLE source_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,  -- prompt, file, database, api, stream, manual
    config JSONB NOT NULL,
    metadata JSONB NOT NULL,
    position JSONB NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Content nodes
CREATE TABLE content_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    content JSONB NOT NULL,  -- {text, tables: [...]}
    lineage JSONB NOT NULL,  -- {source_node_id, transformation_id, operation}
    metadata JSONB NOT NULL,
    position JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_source_nodes_board ON source_nodes(board_id);
CREATE INDEX idx_source_nodes_type ON source_nodes(source_type);
CREATE INDEX idx_content_nodes_board ON content_nodes(board_id);
CREATE INDEX idx_content_nodes_lineage ON content_nodes USING GIN(lineage);
```

#### 1.2 Создать SQLAlchemy модели

```python
# apps/backend/app/models/source_node.py
from sqlalchemy import Column, String, JSON, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base

class SourceNode(Base):
    __tablename__ = "source_nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    board_id = Column(UUID(as_uuid=True), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(50), nullable=False)
    config = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=False)
    position = Column(JSON, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime, nullable=False, server_default=text("NOW()"))

# apps/backend/app/models/content_node.py
class ContentNode(Base):
    __tablename__ = "content_nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    board_id = Column(UUID(as_uuid=True), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False)
    content = Column(JSON, nullable=False)
    lineage = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=False)
    position = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
```

#### 1.3 Создать Pydantic schemas

```python
# apps/backend/app/schemas/source_node.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Literal
from datetime import datetime

class SourceNodeConfig(BaseModel):
    """Base config for all source types"""
    pass

class PromptSourceConfig(SourceNodeConfig):
    prompt: str
    agent_type: str = "data_generation"
    parameters: Dict[str, Any] = {}

class FileSourceConfig(SourceNodeConfig):
    file_id: str
    filename: str
    mime_type: str
    size_bytes: int

class DatabaseSourceConfig(SourceNodeConfig):
    connection_string: str
    query: str
    timeout_seconds: int = 30

class StreamSourceConfig(SourceNodeConfig):
    stream_type: Literal["websocket", "sse", "kafka", "mqtt"]
    url: str
    buffer_strategy: str = "accumulate_with_archive"
    content_update_mode: str = "interval"
    content_update_interval_ms: int = 5000

class SourceNodeCreate(BaseModel):
    board_id: str
    source_type: Literal["prompt", "file", "database", "api", "stream", "manual"]
    config: Dict[str, Any]
    metadata: Dict[str, Any]
    position: Dict[str, float]

class SourceNodeResponse(BaseModel):
    id: str
    board_id: str
    source_type: str
    config: Dict[str, Any]
    metadata: Dict[str, Any]
    position: Dict[str, float]
    created_at: datetime
    updated_at: datetime

# apps/backend/app/schemas/content_node.py
class ContentTable(BaseModel):
    id: str
    name: str
    description: str = ""
    columns: List[Dict[str, Any]]
    row_count: int
    size_bytes: int = 0
    sample_rows: List[Dict[str, Any]] = []

class ContentData(BaseModel):
    text: str = ""
    tables: List[ContentTable] = []

class ContentNodeLineage(BaseModel):
    source_node_id: Optional[str] = None
    transformation_id: Optional[str] = None
    operation: Literal["extract", "transform"]
    created_by: str

class ContentNodeCreate(BaseModel):
    board_id: str
    content: ContentData
    lineage: ContentNodeLineage
    metadata: Dict[str, Any]
    position: Dict[str, float]

class ContentNodeResponse(BaseModel):
    id: str
    board_id: str
    content: ContentData
    lineage: ContentNodeLineage
    metadata: Dict[str, Any]
    position: Dict[str, float]
    created_at: datetime
    updated_at: datetime
```

---

### Phase 2: Backend Services & API (2-3 дня)

#### 2.1 Создать сервисы

```python
# apps/backend/app/services/source_node_service.py
class SourceNodeService:
    async def create_source_node(
        self, 
        board_id: str, 
        source_type: str, 
        config: Dict,
        user_id: str
    ) -> SourceNode:
        """Создать SourceNode"""
        
    async def extract_data(self, source_node_id: str) -> ContentNode:
        """Извлечь данные из источника → создать ContentNode"""
        
    async def validate_connection(self, source_node_id: str) -> ValidationResult:
        """Проверить доступность источника"""
        
    async def refresh_data(self, source_node_id: str) -> ContentNode:
        """Обновить ContentNode из источника"""
        
    async def schedule_refresh(self, source_node_id: str, cron: str):
        """Настроить автообновление"""

# apps/backend/app/services/content_node_service.py
class ContentNodeService:
    async def get_content_node(self, node_id: str) -> ContentNode:
        """Получить ContentNode"""
        
    async def get_table(self, node_id: str, table_id: str) -> Dict:
        """Получить конкретную таблицу"""
        
    async def preview_data(self, node_id: str, limit: int = 100) -> Dict:
        """Preview данных"""
        
    async def transform(
        self,
        source_node_ids: List[str],
        prompt: str
    ) -> ContentNode:
        """Создать новый ContentNode через трансформацию"""
        
    async def visualize(
        self,
        content_node_id: str,
        chart_type: str = None,
        table_ids: List[str] = None
    ) -> WidgetNode:
        """Создать WidgetNode"""
        
    async def export_data(
        self,
        node_id: str,
        format: Literal["csv", "json", "excel"]
    ) -> bytes:
        """Экспорт данных"""

# apps/backend/app/services/extractors/base.py
class BaseExtractor(ABC):
    @abstractmethod
    async def extract(self, config: Dict) -> ContentData:
        """Extract data from source"""

# apps/backend/app/services/extractors/file_extractor.py
class FileExtractor(BaseExtractor):
    async def extract(self, config: FileSourceConfig) -> ContentData:
        # Парсинг файла (CSV, JSON, Excel, PDF)
        pass

# apps/backend/app/services/extractors/database_extractor.py
class DatabaseExtractor(BaseExtractor):
    async def extract(self, config: DatabaseSourceConfig) -> ContentData:
        # SQL запрос к БД
        pass

# apps/backend/app/services/extractors/stream_extractor.py
class StreamExtractor(BaseExtractor):
    async def extract(self, config: StreamSourceConfig) -> ContentData:
        # Подключение к stream
        pass
```

#### 2.2 Создать API endpoints

```python
# apps/backend/app/routes/source_nodes.py
from fastapi import APIRouter, Depends
from app.schemas.source_node import SourceNodeCreate, SourceNodeResponse

router = APIRouter(prefix="/api/v1", tags=["source-nodes"])

@router.post("/boards/{board_id}/source-nodes", response_model=SourceNodeResponse)
async def create_source_node(
    board_id: str,
    data: SourceNodeCreate,
    current_user = Depends(get_current_user)
):
    """Создать SourceNode"""
    
@router.get("/boards/{board_id}/source-nodes", response_model=List[SourceNodeResponse])
async def list_source_nodes(board_id: str):
    """Список SourceNode на доске"""
    
@router.get("/source-nodes/{node_id}", response_model=SourceNodeResponse)
async def get_source_node(node_id: str):
    """Получить SourceNode"""
    
@router.put("/source-nodes/{node_id}", response_model=SourceNodeResponse)
async def update_source_node(node_id: str, data: SourceNodeUpdate):
    """Обновить SourceNode"""
    
@router.delete("/source-nodes/{node_id}")
async def delete_source_node(node_id: str):
    """Удалить SourceNode (cascade delete downstream)"""
    
@router.post("/source-nodes/{node_id}/extract", response_model=ContentNodeResponse)
async def extract_data(node_id: str):
    """Извлечь данные → создать ContentNode"""
    
@router.post("/source-nodes/{node_id}/validate")
async def validate_connection(node_id: str):
    """Проверить подключение"""
    
@router.post("/source-nodes/{node_id}/refresh", response_model=ContentNodeResponse)
async def refresh_data(node_id: str):
    """Обновить ContentNode"""

# apps/backend/app/routes/content_nodes.py
router = APIRouter(prefix="/api/v1", tags=["content-nodes"])

@router.get("/boards/{board_id}/content-nodes", response_model=List[ContentNodeResponse])
async def list_content_nodes(board_id: str):
    """Список ContentNode на доске"""
    
@router.get("/content-nodes/{node_id}", response_model=ContentNodeResponse)
async def get_content_node(node_id: str):
    """Получить ContentNode"""
    
@router.get("/content-nodes/{node_id}/preview")
async def preview_data(node_id: str, limit: int = 100):
    """Preview данных"""
    
@router.get("/content-nodes/{node_id}/tables/{table_id}")
async def get_table(node_id: str, table_id: str):
    """Получить конкретную таблицу"""
    
@router.post("/content-nodes/{node_id}/transform", response_model=ContentNodeResponse)
async def transform_data(node_id: str, data: TransformRequest):
    """Трансформация → новый ContentNode"""
    
@router.post("/content-nodes/{node_id}/visualize", response_model=WidgetNodeResponse)
async def create_visualization(node_id: str, data: VisualizeRequest):
    """Создать WidgetNode"""
    
@router.get("/content-nodes/{node_id}/export")
async def export_data(node_id: str, format: str):
    """Экспорт (CSV/JSON/Excel)"""
    
@router.delete("/content-nodes/{node_id}")
async def delete_content_node(node_id: str):
    """Удалить ContentNode"""
```

#### 2.3 Обновить edges API

```python
# apps/backend/app/routes/edges.py

# Добавить новый тип edge: EXTRACT
@router.post("/boards/{board_id}/edges")
async def create_edge(board_id: str, data: EdgeCreate):
    """
    Создать связь
    
    Поддерживаемые типы:
    - EXTRACT: SourceNode → ContentNode
    - TRANSFORMATION: ContentNode(s) → ContentNode
    - VISUALIZATION: ContentNode → WidgetNode
    - COMMENT: CommentNode → Any Node
    """
```

---

### Phase 3: Frontend Components (3-4 дня)

#### 3.1 Создать типы TypeScript

```typescript
// apps/web/src/types/source-node.ts
export type SourceType = 
  | "prompt" 
  | "file" 
  | "database" 
  | "api" 
  | "stream" 
  | "manual";

export interface SourceNodeConfig {
  [key: string]: any;
}

export interface SourceNode {
  id: string;
  boardId: string;
  sourceType: SourceType;
  config: SourceNodeConfig;
  metadata: {
    title: string;
    description?: string;
    status?: string;
    lastExtracted?: string;
  };
  position: { x: number; y: number };
  createdAt: string;
  updatedAt: string;
}

// apps/web/src/types/content-node.ts
export interface ContentTable {
  id: string;
  name: string;
  description?: string;
  columns: Array<{
    name: string;
    type: string;
    nullable: boolean;
  }>;
  rowCount: number;
  sampleRows: Array<Record<string, any>>;
}

export interface ContentData {
  text: string;
  tables: ContentTable[];
}

export interface ContentNode {
  id: string;
  boardId: string;
  content: ContentData;
  lineage: {
    sourceNodeId?: string;
    transformationId?: string;
    operation: "extract" | "transform";
  };
  metadata: {
    title: string;
    description?: string;
    sizeBytes?: number;
    rowCount?: number;
  };
  position: { x: number; y: number };
  createdAt: string;
  updatedAt: string;
}
```

#### 3.2 Создать React компоненты

```typescript
// apps/web/src/components/nodes/SourceNode.tsx
export function SourceNode({ data }: { data: SourceNode }) {
  return (
    <div className="source-node">
      <div className="node-header">
        <SourceIcon type={data.sourceType} />
        <span>{data.metadata.title}</span>
      </div>
      
      <div className="node-body">
        <SourceTypeInfo config={data.config} />
        <StatusIndicator status={data.metadata.status} />
      </div>
      
      <div className="node-actions">
        <Button onClick={handleExtract}>🔄 Extract Data</Button>
        <Button onClick={handleConfig}>⚙️ Config</Button>
      </div>
    </div>
  );
}

// apps/web/src/components/nodes/ContentNode.tsx
export function ContentNode({ data }: { data: ContentNode }) {
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  
  return (
    <div className="content-node">
      <div className="node-header">
        <FileTextIcon />
        <span>{data.metadata.title}</span>
        {data.streamingMetadata?.isStreaming && (
          <LiveBadge />
        )}
      </div>
      
      <div className="node-body">
        {data.content.text && (
          <p className="content-text">{data.content.text}</p>
        )}
        
        <div className="tables-list">
          <h4>📊 Tables ({data.content.tables.length})</h4>
          {data.content.tables.map(table => (
            <TableItem 
              key={table.id} 
              table={table}
              onSelect={() => setSelectedTable(table.id)}
            />
          ))}
        </div>
      </div>
      
      <div className="node-actions">
        <Button onClick={handlePreview}>👁️ Preview</Button>
        <Button onClick={handleVisualize}>📈 Visualize</Button>
        <Button onClick={handleExport}>💾 Export</Button>
      </div>
    </div>
  );
}

// apps/web/src/components/modals/CreateSourceNodeModal.tsx
export function CreateSourceNodeModal({ boardId, onClose }) {
  const [sourceType, setSourceType] = useState<SourceType>("file");
  
  return (
    <Modal onClose={onClose}>
      <h2>Add Data Source</h2>
      
      <SourceTypeSelector 
        value={sourceType} 
        onChange={setSourceType}
      />
      
      {sourceType === "file" && <FileUploader />}
      {sourceType === "database" && <DatabaseConfigForm />}
      {sourceType === "api" && <APIConfigForm />}
      {sourceType === "prompt" && <PromptInput />}
      {sourceType === "stream" && <StreamConfigForm />}
      
      <Button onClick={handleCreate}>Create Source</Button>
    </Modal>
  );
}
```

#### 3.3 Обновить React Flow конфигурацию

```typescript
// apps/web/src/components/board/Board.tsx
const nodeTypes = {
  source_node: SourceNode,
  content_node: ContentNode,
  widget_node: WidgetNode,
  comment_node: CommentNode,
};

const edgeTypes = {
  extract: ExtractEdge,
  transformation: TransformationEdge,
  visualization: VisualizationEdge,
  comment: CommentEdge,
};
```

---

### Phase 4: Streaming Support (2-3 дня)

#### 4.1 WebSocket/SSE support

```python
# apps/backend/app/services/streaming/stream_manager.py
class StreamManager:
    def __init__(self):
        self.active_streams: Dict[str, StreamHandler] = {}
    
    async def start_stream(self, source_node_id: str):
        """Запустить stream"""
        
    async def stop_stream(self, source_node_id: str):
        """Остановить stream"""
        
    async def pause_stream(self, source_node_id: str):
        """Приостановить"""
        
    async def resume_stream(self, source_node_id: str):
        """Возобновить"""

# apps/backend/app/services/streaming/handlers/websocket_handler.py
class WebSocketStreamHandler:
    async def connect(self, config: StreamSourceConfig):
        """Подключиться к WebSocket"""
        
    async def handle_message(self, message: Any):
        """Обработать входящее сообщение"""
        
    async def update_content_node(self, data: List[Dict]):
        """Обновить ContentNode новыми данными"""
```

#### 4.2 Архивирование данных

```python
# apps/backend/app/services/streaming/archiver.py
class StreamArchiver:
    async def archive_old_records(
        self,
        content_node_id: str,
        threshold: int
    ):
        """Переместить старые записи в архив"""
        
    async def get_archived_data(
        self,
        content_node_id: str,
        date_range: Tuple[datetime, datetime]
    ) -> List[Dict]:
        """Получить архивные данные"""
```

---

### Phase 5: Migration (1 день)

#### 5.1 Создать migration script

```python
# apps/backend/scripts/migrate_datanodes_to_source_content.py

async def migrate_data_nodes():
    """
    Миграция DataNode → SourceNode + ContentNode
    """
    data_nodes = await db.data_nodes.find_all()
    
    for data_node in data_nodes:
        if data_node.source:
            # Создать SourceNode
            source_node = await create_source_node_from_datanode(data_node)
            
            # Создать ContentNode
            content_node = await create_content_node_from_datanode(data_node)
            
            # Создать EXTRACT edge
            await create_edge(
                edge_type="EXTRACT",
                from_node_id=source_node.id,
                to_node_id=content_node.id
            )
            
            # Обновить edges (TRANSFORMATION, VISUALIZATION)
            await update_edges_references(
                old_node_id=data_node.id,
                new_node_id=content_node.id
            )
        else:
            # Создать только ContentNode (результат трансформации)
            content_node = await create_content_node_from_datanode(data_node)
            
            await update_edges_references(
                old_node_id=data_node.id,
                new_node_id=content_node.id
            )
    
    print(f"Migrated {len(data_nodes)} DataNodes")
```

---

### Phase 6: Testing & Documentation (1-2 дня)

#### 6.1 Unit tests

```python
# tests/backend/test_source_node_service.py
async def test_create_source_node():
    """Тест создания SourceNode"""

async def test_extract_data_from_file():
    """Тест извлечения данных из файла"""

async def test_extract_data_from_database():
    """Тест SQL запроса"""

async def test_streaming_accumulation():
    """Тест аккумуляции streaming данных"""

# tests/backend/test_content_node_service.py
async def test_transform_content_nodes():
    """Тест трансформации"""

async def test_visualize_content_node():
    """Тест создания WidgetNode"""
```

#### 6.2 Integration tests

```python
# tests/integration/test_source_to_widget_flow.py
async def test_full_pipeline():
    """
    Тест полного pipeline:
    SourceNode → Extract → ContentNode → Transform → ContentNode → Visualize → WidgetNode
    """
```

#### 6.3 Обновить документацию

- ✅ `SOURCE_CONTENT_NODE_CONCEPT.md` (готово)
- Обновить `ARCHITECTURE.md`
- Обновить `API.md`
- Обновить `DATA_NODE_SYSTEM.md` → переименовать в `NODE_SYSTEM.md`
- Создать `STREAMING_GUIDE.md`

---

## 📊 Оценка времени

| Фаза      | Задачи                 | Время          |
| --------- | ---------------------- | -------------- |
| Phase 1   | Database & Models      | 1-2 дня        |
| Phase 2   | Backend Services & API | 2-3 дня        |
| Phase 3   | Frontend Components    | 3-4 дня        |
| Phase 4   | Streaming Support      | 2-3 дня        |
| Phase 5   | Migration              | 1 день         |
| Phase 6   | Testing & Docs         | 1-2 дня        |
| **ИТОГО** |                        | **10-15 дней** |

---

## 🚀 Приоритизация

### Must Have (MVP)
- ✅ SourceNode: file, database, api, prompt
- ✅ ContentNode с множественными таблицами
- ✅ EXTRACT edge
- ✅ Basic UI components
- ✅ Migration script

### Should Have
- ✅ Streaming sources (websocket, sse)
- ✅ Архивирование данных
- ✅ Throttled replay
- ✅ Live indicators в UI

### Nice to Have
- Intelligent replay (ML-based)
- Advanced stream analytics
- Real-time collaboration для streaming
- TimescaleDB для исторических данных

---

## ✅ Готовность к старту

- [x] Концепция финализирована
- [x] Архитектура спроектирована
- [x] API endpoints определены
- [x] Database schema готова
- [ ] Команда готова к реализации
- [ ] Приоритеты согласованы

**Статус**: 🎯 Готово к началу реализации

---

**Next Steps**:
1. Создать feature branch: `feature/source-content-nodes`
2. Начать с Phase 1: Database Schema & Models
3. Провести code review после каждой фазы
4. Параллельно обновлять документацию
