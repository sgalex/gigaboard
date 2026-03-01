"""Dimension model for cross-filter system.

See docs/CROSS_FILTER_SYSTEM.md
"""
from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.dimension_column_mapping import DimensionColumnMapping


class Dimension(Base):
    """Dimension model — shared filter axis across a project.

    E.g. 'region', 'date', 'category'. Multiple ContentNodes can map
    their columns to the same dimension, enabling cross-filtering.
    """

    __tablename__ = "dimensions"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )

    # Fields
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dim_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="string"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    known_values: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="dimensions")
    column_mappings: Mapped[list["DimensionColumnMapping"]] = relationship(
        back_populates="dimension", cascade="all, delete-orphan"
    )

    # Unique constraint: (project_id, name)
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_dimension_project_name"),
    )

    def __repr__(self) -> str:
        return f"<Dimension {self.name} ({self.dim_type})>"
