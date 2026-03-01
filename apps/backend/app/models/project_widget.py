"""ProjectWidget model — saved widget from board to project library."""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class ProjectWidget(Base):
    """Widget saved to project library from a WidgetNode on a board."""

    __tablename__ = "project_widgets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Widget content (snapshot from WidgetNode)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    css_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    js_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Source references
    source_widget_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("widget_nodes.id", ondelete="SET NULL"), nullable=True
    )
    source_content_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("content_nodes.id", ondelete="SET NULL"), nullable=True
    )
    source_board_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("boards.id", ondelete="SET NULL"), nullable=True
    )

    # Config
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="project_widgets")
    creator: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<ProjectWidget {self.name}>"
