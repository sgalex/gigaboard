"""Project schemas."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    """Base project schema."""
    
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""
    
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None


class ProjectResponse(ProjectBase):
    """Schema for project response."""
    
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProjectWithBoardsResponse(ProjectResponse):
    """Schema for project with boards list."""
    
    boards_count: int = 0
    
    class Config:
        from_attributes = True
