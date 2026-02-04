"""SourceNode model - points of data entry with embedded content.

SourceNode наследует ContentNode и добавляет конфигурацию источника.
Это позволяет хранить и конфиг источника, и извлечённые данные в одной ноде.

См. docs/SOURCE_NODE_CONCEPT_V2.md для деталей архитектуры.
"""
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.models.content_node import ContentNode

if TYPE_CHECKING:
    pass


class SourceType(str, Enum):
    """Source type enum.
    
    Каждый тип файла — отдельный тип источника для специфичной логики извлечения.
    """
    
    # File types (each has specific extraction logic)
    CSV = "csv"                 # CSV files — auto-parse with AI schema detection
    JSON = "json"               # JSON files — AI generates extraction Python code
    EXCEL = "excel"             # Excel files — multi-sheet with AI extraction code
    DOCUMENT = "document"       # PDF/DOCX/TXT — multi-agent extraction with OCR
    
    # Other sources
    API = "api"                 # REST API endpoint with pagination
    DATABASE = "database"       # Database connection (PostgreSQL, MySQL, SQLite)
    RESEARCH = "research"       # AI Research — deep research via multi-agent (search → research → analyze)
    MANUAL = "manual"           # Manual data entry — table constructor
    STREAM = "stream"           # Streaming source (Phase 4: WebSocket, SSE, Kafka)


class SourceNode(ContentNode):
    """SourceNode - point of data entry with embedded content.
    
    Наследует ContentNode, добавляя конфигурацию источника данных.
    При создании источника данные извлекаются и сохраняются в content.
    
    Иерархия наследования: BaseNode → ContentNode → SourceNode
    
    Attributes:
        # От ContentNode:
        content: Data content {text: str, tables: [{id, name, columns, rows}]}
        lineage: Data lineage tracking
        node_metadata: Metadata (row_count, table_count, etc.)
        position: UI position on canvas {x, y}
        
        # Специфичные для SourceNode:
        source_type: Type of data source (csv, json, excel, document, api, database, research, manual, stream)
        config: Source-specific configuration (connection settings, extraction code, etc.)
        created_by: User who created this source
    """
    
    __tablename__ = "source_nodes"
    
    # Primary key (inherited from ContentNode via content_nodes table)
    id: Mapped[UUID] = mapped_column(ForeignKey("content_nodes.id", ondelete="CASCADE"), primary_key=True)
    
    # Source configuration
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    # Creator
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Polymorphic configuration
    __mapper_args__ = {
        "polymorphic_identity": "source_node",  # Sets node_type='source_node' in nodes table
    }
    
    def __repr__(self) -> str:
        table_count = len(self.content.get("tables", [])) if self.content else 0
        return f"<SourceNode(id={self.id}, source_type={self.source_type}, tables={table_count})>"


# ============================================
# Example config structures for documentation
# ============================================

# CSV:
# {
#     "file_id": "uuid",
#     "filename": "sales.csv",
#     "delimiter": ",",
#     "encoding": "utf-8",
#     "has_header": true,
#     "selected_columns": ["date", "product", "amount"]
# }
#
# JSON:
# {
#     "file_id": "uuid",
#     "filename": "data.json",
#     "extraction_code": "import json\ndata = json.loads(content)\n..."
# }
#
# EXCEL:
# {
#     "file_id": "uuid",
#     "filename": "report.xlsx",
#     "extraction_code": "import pandas as pd\ndf = pd.read_excel(file, sheet_name='Sheet1')\n..."
# }
#
# DOCUMENT (PDF/DOCX/TXT):
# {
#     "file_id": "uuid",
#     "filename": "report.pdf",
#     "document_type": "pdf",
#     "is_scanned": false,
#     "extraction_prompt": "Найди все финансовые таблицы..."
# }
#
# API:
# {
#     "url": "https://api.example.com/data",
#     "method": "GET",
#     "headers": {"Authorization": "Bearer xxx"},
#     "params": {"per_page": 100},
#     "pagination": {
#         "enabled": true,
#         "type": "page",
#         "page_param": "page",
#         "size_param": "per_page",
#         "page_size": 100,
#         "max_pages": 10
#     },
#     "json_path": "$"
# }
#
# DATABASE:
# {
#     "db_type": "postgresql",
#     "host": "localhost",
#     "port": 5432,
#     "database": "mydb",
#     "username": "user",
#     "password": "encrypted:xxx",
#     "tables": [
#         {"name": "orders", "where": "created_at > '2024-01-01'", "limit": 1000},
#         {"name": "products", "where": null, "limit": 1000}
#     ]
# }
#
# RESEARCH (AI deep research):
# {
#     "initial_prompt": "Найди статистику продаж электромобилей...",
#     "conversation_history": [...],
#     "sources": ["autostat.ru", "rbc.ru"]
# }
#
# MANUAL:
# {
#     "tables": [
#         {
#             "name": "budget",
#             "columns": [
#                 {"name": "category", "type": "text"},
#                 {"name": "plan", "type": "number"},
#                 {"name": "fact", "type": "number"}
#             ]
#         }
#     ]
# }
#
# STREAM (Phase 4):
# {
#     "stream_type": "websocket",
#     "url": "wss://example.com/stream",
#     "accumulation_strategy": "append",
#     "max_records": 10000,
#     "ttl_hours": 24
# }
