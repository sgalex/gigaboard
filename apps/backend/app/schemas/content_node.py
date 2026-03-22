"""ContentNode Pydantic schemas.

См. docs/SOURCE_CONTENT_NODE_CONCEPT.md для деталей.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# Content Structure
# ============================================

class ContentTable(BaseModel):
    """Table structure within ContentNode."""
    id: str = Field(..., description="Unique table identifier")
    name: str = Field(..., description="Human-readable table name")
    columns: list[dict[str, str]] = Field(..., description="Column definitions [{'name': str, 'type': str}]")
    rows: list[dict[str, Any]] = Field(..., description="Table rows")
    row_count: int = Field(..., description="Total number of rows")
    column_count: int = Field(..., description="Total number of columns")
    preview_row_count: int = Field(..., description="Number of rows in preview")


class ContentData(BaseModel):
    """Content data structure."""
    text: str = Field(default="", description="Textual summary or description")
    tables: list[ContentTable] = Field(default_factory=list, description="Data tables")


# ============================================
# Data Lineage
# ============================================

class DataLineage(BaseModel):
    """Data lineage information."""
    source_node_id: str | None = Field(None, description="Original SourceNode UUID as string")
    transformation_id: str | None = Field(None, description="Transformation UUID as string")
    operation: str = Field(..., description="Operation type: extract, transform, aggregate, join")
    parent_content_ids: list[str] = Field(default_factory=list, description="Parent ContentNode UUIDs as strings")
    timestamp: str = Field(..., description="Creation timestamp in ISO format")
    agent: str | None = Field(None, description="Agent that created this content")


# ============================================
# ContentNode Schemas
# ============================================

class ContentNodeBase(BaseModel):
    """Base ContentNode schema."""
    content: ContentData | dict[str, Any] = Field(..., description="Content data")
    lineage: dict[str, Any] = Field(..., description="Data lineage (dict to preserve all fields)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0}, description="Position on canvas")


class ContentNodeCreate(ContentNodeBase):
    """Create ContentNode schema."""
    board_id: UUID = Field(..., description="Board ID")


class ContentNodeUpdate(BaseModel):
    """Update ContentNode schema."""
    content: ContentData | dict[str, Any] | None = None
    lineage: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    position: dict[str, float] | None = None


class ContentNodeResponse(ContentNodeBase):
    """ContentNode response schema."""
    id: UUID
    board_id: UUID
    created_at: datetime
    updated_at: datetime
    node_type: str = Field(default="content_node", description="Node type discriminator")
    
    # Override metadata field to use node_metadata from model
    # Use serialization_alias to output as "metadata" in JSON
    metadata: dict[str, Any] = Field(
        default_factory=dict, 
        validation_alias="node_metadata",
        serialization_alias="metadata",
        description="Additional metadata"
    )
    
    class Config:
        from_attributes = True
        populate_by_name = True


# ============================================
# Content Operations
# ============================================

class TransformRequest(BaseModel):
    """Request to transform ContentNode(s)."""
    source_content_ids: list[UUID] = Field(..., description="Source ContentNode IDs")
    transformation_code: str = Field(..., description="Python code for transformation")
    output_description: str | None = Field(None, description="Description of expected output")


class TransformResponse(BaseModel):
    """Response from transformation operation."""
    content_node_id: UUID = Field(..., description="Created ContentNode ID")
    status: str = Field(..., description="Transformation status")
    execution_time_ms: int | None = Field(None, description="Execution time in milliseconds")
    error: str | None = Field(None, description="Error message if failed")


class GetTableRequest(BaseModel):
    """Request to get specific table from ContentNode."""
    content_node_id: UUID = Field(..., description="ContentNode ID")
    table_id: str = Field(..., description="Table identifier")


class GetTableResponse(BaseModel):
    """Response with table data."""
    table: ContentTable = Field(..., description="Table data")
    row_count: int = Field(..., description="Number of rows")


class VisualizeRequest(BaseModel):
    """Request to create visualization (WidgetNode) from ContentNode."""
    user_prompt: str | None = Field(None, description="Optional user instruction for visualization (e.g., 'create bar chart')")
    widget_name: str | None = Field(None, max_length=200, description="Custom name for the widget")
    auto_refresh: bool = Field(default=True, description="Auto-refresh on data change")
    position: dict[str, int] | None = Field(None, description="Custom position {x, y}")
    selected_node_ids: list[str] | None = Field(
        None,
        description="Optional list of ContentNode/SourceNode ids for multi-node visualization context",
    )


class VisualizeResponse(BaseModel):
    """Response from visualization creation."""
    widget_node_id: UUID = Field(..., description="Created WidgetNode ID")
    edge_id: UUID = Field(..., description="Created VISUALIZATION edge ID")
    status: str = Field(..., description="Creation status")
    error: str | None = Field(None, description="Error message if failed")


class VisualizeIterativeRequest(BaseModel):
    """Request for iterative visualization generation (chat-based)."""
    user_prompt: str = Field(..., description="User instruction for visualization")
    existing_html: str | None = Field(None, description="Existing HTML code to iterate on (legacy)")
    existing_css: str | None = Field(None, description="Existing CSS code (legacy)")
    existing_js: str | None = Field(None, description="Existing JS code (legacy)")
    existing_widget_code: str | None = Field(None, description="Existing full HTML widget code")
    chat_history: list[dict[str, str]] | None = Field(None, description="Chat history for context (list of {role, content} messages)")
    selected_node_ids: list[str] | None = Field(
        None,
        description="Optional list of ContentNode/SourceNode ids for multi-node visualization context",
    )


class VisualizeIterativeResponse(BaseModel):
    """Response from iterative visualization generation."""
    html_code: str = Field("", description="Generated HTML code (legacy format)")
    css_code: str = Field("", description="Generated CSS code (legacy format)")
    js_code: str = Field("", description="Generated JavaScript code (legacy format)")
    widget_code: str | None = Field(None, description="Full HTML widget code (new format)")
    widget_name: str | None = Field(None, description="Short widget name (2-4 words)")
    widget_type: str = Field("custom", description="Widget type: chart, table, metric, text, custom")
    description: str = Field(..., description="Description of the visualization")
    status: str = Field(..., description="Generation status")
    error: str | None = Field(None, description="Error message if failed")
