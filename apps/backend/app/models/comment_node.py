"""CommentNode model - nodes containing comments and annotations."""
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_node import BaseNode

if TYPE_CHECKING:
    from app.models.user import User


class CommentNode(BaseNode):
    """CommentNode - contains comments, annotations, and insights."""
    
    __tablename__ = "comment_nodes"
    
    # Primary key (inherited from BaseNode)
    id: Mapped[UUID] = mapped_column(ForeignKey("nodes.id"), primary_key=True)
    
    # Foreign keys
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    
    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Formatting
    format_type: Mapped[str] = mapped_column(String(20), default="markdown")  # markdown, plain, html
    
    # Visual configuration
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)  # hex color
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # Additional styling
    
    # Resolved status (for collaborative workflows)
    is_resolved: Mapped[bool] = mapped_column(default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Relationships
    author: Mapped["User"] = relationship(foreign_keys=[author_id])
    
    # Polymorphic configuration
    __mapper_args__ = {
        "polymorphic_identity": "comment_node",
    }
    
    def __repr__(self):
        return f"<CommentNode(id={self.id}, author_id={self.author_id})>"
