from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.core import Base


class EdgeType(str, enum.Enum):
    """Types of connections between nodes
    
    Source-Content Node Architecture v2.0:
    - TRANSFORMATION: SourceNode/ContentNode → ContentNode (data transformation with Python code)
    - VISUALIZATION: ContentNode/SourceNode → WidgetNode (auto-refresh visualization)
    """
    TRANSFORMATION = "TRANSFORMATION"  # SourceNode/ContentNode → ContentNode (with Python code)
    VISUALIZATION = "VISUALIZATION"   # ContentNode/SourceNode → WidgetNode (auto-refresh)
    COMMENT = "COMMENT"                # CommentNode → any node (annotation)
    DRILL_DOWN = "DRILL_DOWN"          # Navigation between boards
    REFERENCE = "REFERENCE"            # Reference to another node


class Edge(Base):
    """
    Edges represent semantic connections between nodes on a board.
    They encode meaning about how nodes relate, what data flows between them,
    transformations, visualizations, and comments.
    """
    __tablename__ = "edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Relationships
    board_id = Column(UUID(as_uuid=True), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False)
    
    # Source/Target node references (polymorphic)
    # Can be DataNode, WidgetNode, or CommentNode
    source_node_id = Column(UUID(as_uuid=True), nullable=False)
    target_node_id = Column(UUID(as_uuid=True), nullable=False)
    source_node_type = Column(String(50), nullable=False)  # 'data_node', 'widget_node', 'comment_node'
    target_node_type = Column(String(50), nullable=False)
    
    # Edge properties
    edge_type = Column(SQLEnum(EdgeType), nullable=False)
    label = Column(String(200))
    
    # Data flow configuration
    # For DATA_FLOW/VISUALIZATION: {source_param: target_param} mapping
    # Example: {"total_sales": "chart_value"}
    parameter_mapping = Column(JSONB, default={})
    
    # Transformation configuration (for TRANSFORMATION edges)
    # Contains Python pandas code for DataNode → DataNode transformations
    transformation_code = Column(Text, nullable=True)
    transformation_params = Column(JSONB, default={})  # Parameters for transformation
    
    # Visual configuration
    # {color, line_style, arrow_type, animation, custom_properties}
    visual_config = Column(JSONB, default={})
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    
    # Validation state
    is_valid = Column(String(10), default="true")  # SQLite doesn't have boolean
    validation_errors = Column(Text)  # JSON string of error list
    
    # Relationships (for ORM queries)
    board = relationship("Board", back_populates="edges")
    
    def __repr__(self):
        return f"<Edge {self.edge_type.value}: {self.source_node_type}({self.source_node_id}) -> {self.target_node_type}({self.target_node_id})>"
