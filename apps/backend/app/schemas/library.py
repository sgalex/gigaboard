"""Library schemas — ProjectWidget and ProjectTable."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# === ProjectWidget ===

class ProjectWidgetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class ProjectWidgetCreate(ProjectWidgetBase):
    """Create a widget in the project library from a WidgetNode."""
    source_widget_node_id: UUID | None = None
    source_content_node_id: UUID | None = None
    source_board_id: UUID | None = None
    html_code: str | None = None
    css_code: str | None = None
    js_code: str | None = None
    config: dict | None = None


class ProjectWidgetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    html_code: str | None = None
    css_code: str | None = None
    js_code: str | None = None
    config: dict | None = None


class ProjectWidgetResponse(ProjectWidgetBase):
    id: UUID
    project_id: UUID
    created_by: UUID
    html_code: str | None = None
    css_code: str | None = None
    js_code: str | None = None
    thumbnail_url: str | None = None
    source_widget_node_id: UUID | None = None
    source_content_node_id: UUID | None = None
    source_board_id: UUID | None = None
    config: dict | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# === ProjectTable ===

class ProjectTableBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class ProjectTableCreate(ProjectTableBase):
    """Create a table in the project library from a ContentNode."""
    source_content_node_id: UUID | None = None
    source_board_id: UUID | None = None
    table_name_in_node: str | None = None
    columns: list | None = None
    sample_data: list | None = None
    row_count: int = 0
    config: dict | None = None


class ProjectTableUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    config: dict | None = None


class ProjectTableResponse(ProjectTableBase):
    id: UUID
    project_id: UUID
    created_by: UUID
    columns: list | None = None
    sample_data: list | None = None
    row_count: int = 0
    source_content_node_id: UUID | None = None
    source_board_id: UUID | None = None
    table_name_in_node: str | None = None
    config: dict | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
