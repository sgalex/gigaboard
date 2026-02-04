from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

# Import EdgeType from models to avoid duplication
from app.models.edge import EdgeType


class EdgeBase(BaseModel):
    """Base edge schema for DataNode architecture"""
    source_node_id: UUID = Field(..., description="Source node UUID")
    source_node_type: str = Field(..., description="Source node type (DataNode, WidgetNode, CommentNode)")
    target_node_id: UUID = Field(..., description="Target node UUID")
    target_node_type: str = Field(..., description="Target node type (DataNode, WidgetNode, CommentNode)")
    edge_type: EdgeType = Field(..., description="Type of connection")
    label: Optional[str] = Field(None, max_length=200, description="Display label for edge")
    transformation_code: Optional[str] = Field(None, description="Python pandas code for TRANSFORMATION edges")
    transformation_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parameters for transformation")
    visual_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Visual configuration (color, style, animation)")

    @field_validator('source_node_id', 'target_node_id')
    @classmethod
    def validate_node_ids(cls, v):
        if v is None:
            raise ValueError('Node ID cannot be None')
        return v
    
    @field_validator('source_node_type', 'target_node_type')
    @classmethod
    def validate_node_types(cls, v):
        allowed = ['DataNode', 'WidgetNode', 'CommentNode', 'SourceNode', 'ContentNode', 'source_node', 'content_node']
        if v not in allowed:
            raise ValueError(f'Node type must be one of {allowed}')
        return v


class EdgeCreate(EdgeBase):
    """Schema for creating an edge"""
    pass


class EdgeUpdate(BaseModel):
    """Schema for updating an edge"""
    label: Optional[str] = Field(None, max_length=200)
    transformation_code: Optional[str] = None
    transformation_params: Optional[Dict[str, Any]] = None
    visual_config: Optional[Dict[str, Any]] = None
    parameter_mapping: Optional[Dict[str, str]] = None
    visual_config: Optional[Dict[str, Any]] = None


class EdgeResponse(EdgeBase):
    """Schema for edge responses"""
    id: UUID
    board_id: UUID
    created_at: datetime
    updated_at: datetime
    is_valid: str
    validation_errors: Optional[str] = None

    class Config:
        from_attributes = True


class EdgeListResponse(BaseModel):
    """Schema for list of edges"""
    edges: list[EdgeResponse]
    total: int
