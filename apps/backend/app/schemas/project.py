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
    """Schema for project with boards and stats for welcome/list."""
    
    boards_count: int = 0
    dashboards_count: int = 0
    sources_count: int = 0
    content_nodes_count: int = 0  # ContentNode (incl. sources) on boards
    widgets_count: int = 0
    tables_count: int = 0  # Sum of tables in content.tables across all ContentNodes
    dimensions_count: int = 0  # Dimensions (cross-filter axes) in project
    filters_count: int = 0  # Filter presets in project
    
    class Config:
        from_attributes = True
