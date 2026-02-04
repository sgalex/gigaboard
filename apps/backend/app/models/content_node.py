"""ContentNode model - results of data processing (text + N tables).

См. docs/SOURCE_CONTENT_NODE_CONCEPT.md для деталей архитектуры.
"""
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.models.base_node import BaseNode

if TYPE_CHECKING:
    pass


class ContentNode(BaseNode):
    """ContentNode - result of data processing.
    
    Contains processed data from SourceNode or transformation results.
    Supports multiple tables in a single node + textual summary.
    
    Attributes:
        content: Data content {text: str, tables: [{id, name, columns, rows}]}
        lineage: Data lineage tracking {source_node_id, transformation_id, operation, parent_content_ids}
        metadata: Additional metadata (row_count, table_count, data_quality, etc.)
        position: UI position on canvas {x, y}
    """
    
    __tablename__ = "content_nodes"
    
    # Primary key (inherited from BaseNode via nodes table)
    id: Mapped[UUID] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True)
    
    # Content: text summary + multiple tables
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB, 
        nullable=False, 
        server_default=text("'{\"text\": \"\", \"tables\": []}'::jsonb")
    )
    
    # Data lineage tracking
    lineage: Mapped[dict[str, Any]] = mapped_column(
        JSONB, 
        nullable=False, 
        server_default=text("'{}'::jsonb")
    )
    
    # Node metadata (row counts, data quality, computation time, etc.)
    # Note: Using node_metadata instead of metadata to avoid SQLAlchemy reserved word
    node_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    # Position on canvas
    position: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{\"x\": 0, \"y\": 0}'::jsonb"))
    
    # Polymorphic configuration
    __mapper_args__ = {
        "polymorphic_identity": "content_node",  # Sets node_type='content_node' in nodes table
    }
    
    def __repr__(self) -> str:
        table_count = len(self.content.get("tables", [])) if self.content else 0
        return f"<ContentNode(id={self.id}, tables={table_count})>"


# Example content structure:
# {
#     "text": "Sales data for Q1 2024. Total revenue: $1.2M",
#     "tables": [
#         {
#             "id": "sales_by_month",
#             "name": "Monthly Sales",
#             "columns": [
#                 {"name": "month", "type": "string"},
#                 {"name": "revenue", "type": "number"},
#                 {"name": "units", "type": "integer"}
#             ],
#             "rows": [
#                 {"month": "January", "revenue": 400000, "units": 1200},
#                 {"month": "February", "revenue": 450000, "units": 1350},
#                 {"month": "March", "revenue": 350000, "units": 1050}
#             ]
#         }
#     ]
# }
#
# Example lineage structure:
# {
#     "source_node_id": "uuid",              # SourceNode that provided raw data
#     "transformation_id": "uuid",           # Transformation that created this (optional)
#     "operation": "extract",                # "extract", "transform", "aggregate", "join"
#     "parent_content_ids": ["uuid1", "uuid2"],  # Parent ContentNodes (for transformations)
#     "timestamp": "2026-01-30T12:00:00Z",
#     "agent": "researcher_agent"            # Agent that created this
# }
