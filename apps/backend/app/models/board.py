"""Board model."""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.edge import Edge
    from app.models.base_node import BaseNode
    from app.models.widget_node import WidgetNode
    from app.models.comment_node import CommentNode


class Board(Base):
    """Board model - infinite canvas with widgets."""
    
    __tablename__ = "boards"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    
    # Fields
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # preview image URL for card
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="boards")
    user: Mapped["User"] = relationship(back_populates="boards")
    
    # Base nodes relationship (polymorphic)
    nodes: Mapped[list["BaseNode"]] = relationship(
        back_populates="board", cascade="all, delete-orphan"
    )
    
    # Agent sessions
    agent_sessions: Mapped[list["AgentSession"]] = relationship(
        back_populates="board", cascade="all, delete-orphan"
    )
    
    # Convenience relationships for specific node types
    # Note: These are views over the nodes relationship, filtered by node_type
    @property
    def widget_nodes(self) -> list["WidgetNode"]:
        """Get all WidgetNodes on this board."""
        from app.models.widget_node import WidgetNode
        return [node for node in self.nodes if isinstance(node, WidgetNode)]
    
    @property
    def comment_nodes(self) -> list["CommentNode"]:
        """Get all CommentNodes on this board."""
        from app.models.comment_node import CommentNode
        return [node for node in self.nodes if isinstance(node, CommentNode)]
    
    # Edges (connections between nodes)
    edges: Mapped[list["Edge"]] = relationship(
        back_populates="board", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Board {self.name}>"
