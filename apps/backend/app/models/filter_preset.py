"""FilterPreset model for cross-filter system.

See docs/CROSS_FILTER_SYSTEM.md
"""
from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class FilterPreset(Base):
    """Saved set of filter conditions that can be applied to boards/dashboards.

    Scope:
    - 'project' — global within the project
    - 'board' — scoped to a specific board (target_id = board_id)
    - 'dashboard' — scoped to a specific dashboard (target_id = dashboard_id)
    """

    __tablename__ = "filter_presets"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )

    # Fields
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    scope: Mapped[str] = mapped_column(
        String(50), nullable=False, default="project"
    )
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="filter_presets")
    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<FilterPreset {self.name} (scope={self.scope})>"
