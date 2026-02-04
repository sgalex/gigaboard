"""CommentNode schemas."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base_node import BaseNodeSchema, BaseNodeResponse


class CommentNodeBase(BaseNodeSchema):
    """Base CommentNode schema."""
    content: str = Field(..., description="Comment content")
    format_type: str = Field(default="markdown", description="Content format")
    color: str | None = Field(None, max_length=20, description="Hex color")
    config: dict[str, Any] | None = Field(None, description="Additional styling")


class CommentNodeCreate(CommentNodeBase):
    """Create CommentNode schema."""
    pass


class CommentNodeUpdate(BaseModel):
    """Update CommentNode schema."""
    content: str | None = None
    format_type: str | None = None
    color: str | None = None
    config: dict[str, Any] | None = None
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None
    is_resolved: bool | None = None


class CommentNodeResponse(BaseNodeResponse, CommentNodeBase):
    """CommentNode response schema."""
    author_id: UUID
    is_resolved: bool
    resolved_at: datetime | None
    resolved_by: UUID | None
