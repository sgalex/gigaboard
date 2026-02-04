"""Board schemas."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class BoardBase(BaseModel):
    """Base board schema."""
    
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class BoardCreate(BoardBase):
    """Schema for creating a board."""
    
    project_id: UUID


class BoardUpdate(BaseModel):
    """Schema for updating a board."""
    
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None


class BoardResponse(BoardBase):
    """Schema for board response."""
    
    id: UUID
    project_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BoardWithNodesResponse(BoardResponse):
    """Schema for board with node counts."""
    
    widget_nodes_count: int = 0
    comment_nodes_count: int = 0
    
    class Config:
        from_attributes = True
