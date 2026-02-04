"""Base Node model - parent class for all node types."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr

from app.core import Base

if TYPE_CHECKING:
    from app.models.board import Board


class NodeType(str, Enum):
    """Node type enum."""
    DATA_NODE = "data_node"
    SOURCE_NODE = "source_node"
    CONTENT_NODE = "content_node"
    WIDGET_NODE = "widget_node"
    COMMENT_NODE = "comment_node"


class BaseNode(Base):
    """
    Base Node class - contains common fields for all node types.
    Uses Joined Table Inheritance pattern.
    """
    
    __tablename__ = "nodes"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Foreign keys
    board_id: Mapped[UUID] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"))
    
    # Node type discriminator
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Position on canvas
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    
    # Optional size (used by WidgetNode and CommentNode)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Polymorphic configuration
    __mapper_args__ = {
        "polymorphic_identity": "base_node",
        "polymorphic_on": node_type,
        "with_polymorphic": "*",  # Eager load all subclasses
    }
    
    @declared_attr
    def board(cls) -> Mapped["Board"]:
        """Relationship to Board - defined as declared_attr to work with inheritance."""
        return relationship("Board", back_populates="nodes")
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, type={self.node_type})>"
