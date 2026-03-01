"""SourceNode Pydantic schemas.

SourceNode v2: Наследует от ContentNode, хранит и конфигурацию и данные.
См. docs/SOURCE_NODE_CONCEPT_V2.md для деталей архитектуры.
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# Source Type - новый перечень из 9 типов
# ============================================

SourceTypeEnum = Literal[
    "csv",      # CSV файлы
    "json",     # JSON файлы  
    "excel",    # Excel файлы (xlsx, xls)
    "document", # Документы (PDF, DOCX, TXT)
    "api",      # REST API
    "database", # SQL базы данных
    "research", # AI Deep Research
    "manual",   # Ручной ввод
    "stream",   # Real-time стримы (Phase 4)
]


# ============================================
# Source Type Specific Configs (обновлённые)
# ============================================

class CSVSourceConfig(BaseModel):
    """Configuration for CSV file source."""
    file_id: str = Field(..., description="Uploaded file ID")
    delimiter: str | None = Field(None, description="CSV delimiter (auto-detect if None)")
    encoding: str | None = Field(None, description="File encoding (auto-detect if None)")
    has_header: bool = Field(default=True, description="First row is header")
    skip_rows: int = Field(default=0, description="Rows to skip at start")
    max_rows: int | None = Field(default=None, description="Maximum rows to load (None = all rows)")


class JSONSourceConfig(BaseModel):
    """Configuration for JSON file source."""
    file_id: str = Field(..., description="Uploaded file ID")
    max_rows: int | None = Field(default=None, description="Maximum rows to load per table (None = all rows)")
    json_path: str = Field(default="$", description="JSONPath to data array")
    extraction_code: str | None = Field(None, description="AI-generated extraction code")


class DetectedRegionConfig(BaseModel):
    """A single detected table region in an Excel sheet."""
    sheet_name: str = Field(..., description="Sheet name")
    start_row: int = Field(..., description="Start row (1-based)")
    start_col: int = Field(..., description="Start column (1-based)")
    end_row: int = Field(..., description="End row (1-based)")
    end_col: int = Field(..., description="End column (1-based)")
    header_row: int | None = Field(None, description="Header row (1-based or None)")
    table_name: str = Field(default="", description="Display name for the table")
    selected_columns: list[str] = Field(default_factory=list, description="Columns to extract")


class ExcelSourceConfig(BaseModel):
    """Configuration for Excel file source.
    
    Два режима:
    - simple: извлечение по листам (sheets, selected_columns)
    - smart: извлечение по регионам (detected_regions)
    
    See docs/SOURCE_NODE_CONCEPT_V2.md - section "Excel Dialog".
    """
    file_id: str = Field(..., description="Uploaded file ID")
    filename: str | None = Field(None, description="Original filename")
    mime_type: str | None = Field(None, description="File MIME type")
    size_bytes: int | None = Field(None, description="File size in bytes")
    analysis_mode: str = Field(default="simple", description="Analysis mode: 'simple' or 'smart'")
    # Simple mode
    sheets: list[str] = Field(default_factory=list, description="Sheets to extract (all if empty)")
    has_header: bool = Field(default=True, description="First row is header")
    max_rows: int | None = Field(default=None, description="Maximum rows to load per sheet (None = all rows)")
    selected_columns: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Selected columns per sheet: {sheet_name: [col1, col2, ...]}. Empty = all columns."
    )
    # Smart mode
    detected_regions: list[DetectedRegionConfig] = Field(
        default_factory=list,
        description="Detected table regions for smart extraction"
    )
    extraction_code: str | None = Field(None, description="AI-generated Python extraction code")


class DocumentSourceConfig(BaseModel):
    """Configuration for document source (PDF, DOCX, TXT).
    
    См. docs/SOURCE_NODE_CONCEPT_V2.md — раздел "📄 4. Document Dialog".
    """
    file_id: str = Field(..., description="Uploaded file ID")
    filename: str | None = Field(None, description="Original filename")
    document_type: str | None = Field(None, description="Document type: pdf, docx, txt")
    mime_type: str | None = Field(None, description="File MIME type")
    size_bytes: int | None = Field(None, description="File size in bytes")
    is_scanned: bool = Field(default=False, description="Whether PDF is scanned (needs OCR)")
    extraction_prompt: str | None = Field(None, description="AI prompt for data extraction")
    extraction_code: str | None = Field(None, description="AI-generated extraction code")
    page_range: str | None = Field(None, description="Page range to extract, e.g. '1-5'")


class APISourceConfig(BaseModel):
    """Configuration for API source."""
    url: str = Field(..., description="API endpoint URL")
    method: str = Field(default="GET", description="HTTP method")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    params: dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    body: dict[str, Any] | None = Field(None, description="Request body for POST/PUT")
    timeout_seconds: int = Field(default=30, description="Request timeout in seconds")
    pagination: dict[str, Any] | None = Field(None, description="Pagination config")


class DatabaseSourceConfig(BaseModel):
    """Configuration for database source."""
    db_type: Literal["postgresql", "mysql", "sqlite"] = Field(..., description="Database type")
    host: str | None = Field(None, description="Database host")
    port: int | None = Field(None, description="Database port")
    database: str | None = Field(None, description="Database name")
    username: str | None = Field(None, description="Database user")
    password: str | None = Field(None, description="Database password")
    path: str | None = Field(None, description="SQLite file path")
    tables: list[dict[str, Any]] = Field(..., description="Tables to extract with WHERE conditions")


class ResearchSourceConfig(BaseModel):
    """Configuration for AI Research source."""
    initial_prompt: str = Field(..., description="Research query/prompt")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context for research")


class ManualSourceConfig(BaseModel):
    """Configuration for manual data entry."""
    columns: list[dict[str, str]] = Field(..., description="Column definitions [{name, type}]")
    data: list[dict[str, Any]] = Field(default_factory=list, description="Initial data rows")


class StreamSourceConfig(BaseModel):
    """Configuration for streaming source (Phase 4)."""
    stream_type: Literal["websocket", "sse", "kafka"] = Field(..., description="Type of stream")
    url: str = Field(..., description="Stream URL")
    buffer_strategy: str = Field(default="accumulate", description="Buffer strategy")


# ============================================
# SourceNode Schemas (v2 - inherits ContentNode)
# ============================================

class SourceNodeBase(BaseModel):
    """Base SourceNode schema.
    
    v2: SourceNode теперь наследует ContentNode, хранит и конфигурацию и данные.
    """
    source_type: SourceTypeEnum = Field(..., description="Type of data source")
    config: dict[str, Any] = Field(..., description="Source-specific configuration")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0}, description="Position on canvas")


class SourceNodeCreate(SourceNodeBase):
    """Create SourceNode schema."""
    board_id: UUID = Field(..., description="Board ID")
    created_by: UUID = Field(..., description="User ID who creates this source")
    
    # Initial data (optional, can be populated during extraction)
    data: dict[str, Any] | None = Field(None, description="Initial table data")


class SourceNodeUpdate(BaseModel):
    """Update SourceNode schema."""
    config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    position: dict[str, float] | None = None
    data: dict[str, Any] | None = None  # Update extracted data


class SourceNodeResponse(SourceNodeBase):
    """SourceNode response schema.
    
    v2: Includes content and lineage from ContentNode inheritance.
    """
    id: UUID
    board_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    node_type: str = Field(default="source_node", description="Node type discriminator")
    
    # ContentNode fields (inherited) - content with tables
    content: dict[str, Any] | None = Field(None, description="Content with text and tables")
    lineage: dict[str, Any] | None = Field(None, description="Data lineage tracking")
    
    # Map node_metadata from model to metadata in API
    metadata: dict[str, Any] = Field(alias="node_metadata", serialization_alias="metadata")
    
    class Config:
        from_attributes = True
        populate_by_name = True


# ============================================
# Source Operations (v2 - упрощённые)
# ============================================

class ExtractRequest(BaseModel):
    """Request to extract/refresh data in SourceNode.
    
    v2: Данные сохраняются в самом SourceNode (не создаётся отдельный ContentNode).
    """
    source_node_id: UUID = Field(..., description="SourceNode to extract from")
    extraction_params: dict[str, Any] = Field(default_factory=dict, description="Extraction parameters")
    force: bool = Field(default=False, description="Force re-extraction even if recent")


class ExtractResponse(BaseModel):
    """Response from extraction operation."""
    source_node_id: UUID = Field(..., description="Updated SourceNode ID")
    status: str = Field(..., description="Extraction status: success/failed/pending")
    row_count: int | None = Field(None, description="Number of rows extracted")
    tables_count: int | None = Field(None, description="Number of tables extracted")
    extraction_time_ms: int | None = Field(None, description="Extraction time in milliseconds")
    error: str | None = Field(None, description="Error message if failed")


class RefreshRequest(BaseModel):
    """Request to refresh SourceNode data."""
    source_node_id: UUID = Field(..., description="SourceNode to refresh")
    force: bool = Field(default=False, description="Force refresh even if recent")


class RefreshResponse(BaseModel):
    """Response from refresh operation."""
    status: str = Field(..., description="Refresh status")
    source_node_id: UUID = Field(..., description="Refreshed SourceNode ID")
    row_count: int | None = Field(None, description="New row count")
    refresh_time_ms: int | None = Field(None, description="Refresh time in milliseconds")
    error: str | None = Field(None, description="Error message if failed")


# ============================================
# Vitrina (Source Showcase) Schemas
# ============================================

class SourceVitrinaItem(BaseModel):
    """Item in source vitrina (left panel showcase)."""
    source_type: SourceTypeEnum
    display_name: str = Field(..., description="Human-readable name")
    icon: str = Field(..., description="Emoji icon")
    description: str = Field(..., description="Short description")


class SourceVitrinaResponse(BaseModel):
    """Response with all available source types for vitrina."""
    items: list[SourceVitrinaItem] = Field(..., description="Available source types")
