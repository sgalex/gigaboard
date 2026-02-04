"""Base Node schema - parent schema for all node types."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BaseNodeSchema(BaseModel):
    """Base schema for node creation (without board_id - it comes from URL)."""
    
    # Position on canvas
    x: int = Field(default=0, description="X position on canvas")
    y: int = Field(default=0, description="Y position on canvas")
    
    # Optional size (used by WidgetNode and CommentNode)
    width: int | None = Field(None, description="Width on canvas")
    height: int | None = Field(None, description="Height on canvas")


class BaseNodeResponse(BaseModel):
    """Base response schema for all node types."""
    
    id: UUID
    board_id: UUID
    node_type: str
    x: int
    y: int
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


