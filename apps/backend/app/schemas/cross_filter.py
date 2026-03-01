"""Cross-filter system schemas.

See docs/CROSS_FILTER_SYSTEM.md
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================
# FILTER OPERATORS & CONDITIONS
# ============================================

class FilterOperator(str, Enum):
    """Supported filter operators."""
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"


FilterValue = Union[str, int, float, bool, list[str], list[int], list[float], tuple[float, float], None]


class FilterCondition(BaseModel):
    """Single filter condition — e.g. region == 'North'."""
    type: Literal["condition"] = "condition"
    dim: str = Field(..., description="Dimension name (e.g. 'region')")
    op: FilterOperator
    value: Any = Field(..., description="Filter value (type depends on dim_type)")
    initiator_widget_id: str | None = Field(None, alias="initiatorWidgetId", description="Widget node ID that added this condition (UI only, ignored by FilterEngine)")


class FilterGroup(BaseModel):
    """AND/OR group of conditions or nested groups."""
    type: Literal["and", "or"]
    conditions: list[FilterExpression] = Field(default_factory=list)


# Recursive union type
FilterExpression = Union[FilterCondition, FilterGroup]

# Rebuild models for recursive reference
FilterGroup.model_rebuild()


# ============================================
# DIMENSION SCHEMAS
# ============================================

class DimensionType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"


class DimensionCreate(BaseModel):
    """Create a new dimension in a project."""
    name: str = Field(..., min_length=1, max_length=100, description="Technical name")
    display_name: str = Field(..., min_length=1, max_length=200, description="Human-readable name")
    dim_type: DimensionType = DimensionType.STRING
    description: str | None = None
    known_values: dict[str, Any] | None = Field(
        None,
        description="Known values metadata, e.g. {'values': ['North', 'South']}"
    )


class DimensionUpdate(BaseModel):
    """Update dimension."""
    display_name: str | None = Field(None, min_length=1, max_length=200)
    dim_type: DimensionType | None = None
    description: str | None = None
    known_values: dict[str, Any] | None = None


class DimensionResponse(BaseModel):
    """Dimension response."""
    id: UUID
    project_id: UUID
    name: str
    display_name: str
    dim_type: DimensionType
    description: str | None
    known_values: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================
# DIMENSION COLUMN MAPPING SCHEMAS
# ============================================

class MappingSource(str, Enum):
    MANUAL = "manual"
    AUTO_DETECTED = "auto_detected"
    AI_SUGGESTED = "ai_suggested"


class DimensionColumnMappingCreate(BaseModel):
    """Create a mapping between dimension and a table column."""
    dimension_id: UUID
    node_id: UUID
    table_name: str = Field(..., min_length=1, max_length=200)
    column_name: str = Field(..., min_length=1, max_length=200)
    mapping_source: MappingSource = MappingSource.MANUAL
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class DimensionColumnMappingResponse(BaseModel):
    """Mapping response."""
    id: UUID
    dimension_id: UUID
    node_id: UUID
    table_name: str
    column_name: str
    mapping_source: str   # stored as plain str to tolerate legacy values
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================
# DIMENSION MANAGEMENT SCHEMAS
# ============================================

class MergeDimensionsRequest(BaseModel):
    """Merge two or more dimensions into a target dimension."""
    source_ids: list[UUID] = Field(..., min_length=1, description="Dimensions to merge FROM (will be deleted)")
    target_id: UUID = Field(..., description="Dimension to merge INTO (survives)")

class MergeDimensionsResponse(BaseModel):
    """Result of a dimension merge operation."""
    target_id: UUID
    deleted_count: int       # number of source dimensions deleted
    transferred_count: int   # number of mappings transferred to target


# ============================================
# FILTER PRESET SCHEMAS
# ============================================

class FilterPresetScope(str, Enum):
    PROJECT = "project"
    BOARD = "board"
    DASHBOARD = "dashboard"


class FilterPresetCreate(BaseModel):
    """Create a filter preset."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    filters: FilterExpression
    scope: FilterPresetScope = FilterPresetScope.PROJECT
    target_id: UUID | None = Field(None, description="Board or Dashboard ID when scope != project")
    is_default: bool = False
    tags: list[str] = Field(default_factory=list)


class FilterPresetUpdate(BaseModel):
    """Update a filter preset."""
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    filters: FilterExpression | None = None
    is_default: bool | None = None
    tags: list[str] | None = None


class FilterPresetResponse(BaseModel):
    """Preset response."""
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    filters: dict[str, Any]  # serialized FilterExpression
    scope: FilterPresetScope
    target_id: UUID | None
    is_default: bool
    tags: list[str]
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================
# ACTIVE FILTERS (for PUT /boards/{id}/filters)
# ============================================

class ActiveFiltersUpdate(BaseModel):
    """Update active filters on a board/dashboard."""
    filters: FilterExpression | None = None


class ActiveFiltersResponse(BaseModel):
    """Response with current active filters."""
    filters: dict[str, Any] | None = None
    preset_id: UUID | None = None
    updated_at: datetime | None = None


# ============================================
# FILTER STATS
# ============================================

class TableFilterStats(BaseModel):
    """Filter statistics for a single table."""
    table_name: str
    total_rows: int
    filtered_rows: int
    percentage: float


class FilterStatsResponse(BaseModel):
    """Statistics about filtering effect."""
    tables: list[TableFilterStats]


# ============================================
# DIMENSION DETECTION
# ============================================

class DimensionSuggestion(BaseModel):
    """Auto-detected dimension suggestion."""
    column_name: str
    table_name: str
    suggested_name: str
    suggested_display_name: str
    suggested_type: DimensionType
    unique_count: int
    sample_values: list[Any]
    confidence: float
    existing_dimension_id: UUID | None = None  # if matches existing dim


class DetectDimensionsResponse(BaseModel):
    """Response from detect-dimensions endpoint."""
    suggestions: list[DimensionSuggestion]
    auto_mapped: int = Field(0, description="Number of auto-created mappings")
