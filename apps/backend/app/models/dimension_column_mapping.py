"""DimensionColumnMapping model for cross-filter system.

See docs/CROSS_FILTER_SYSTEM.md
"""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.dimension import Dimension


class DimensionColumnMapping(Base):
    """Maps a Dimension to a specific column in a specific table of a node.

    Example: Dimension 'region' → ContentNode(id=X).tables['Sales'].columns['region_name']
    """

    __tablename__ = "dimension_column_mappings"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    dimension_id: Mapped[UUID] = mapped_column(
        ForeignKey("dimensions.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"), index=True
    )

    # Target column identification
    table_name: Mapped[str] = mapped_column(String(200), nullable=False)
    column_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Mapping provenance
    mapping_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    dimension: Mapped["Dimension"] = relationship(back_populates="column_mappings")

    # Unique constraint: one column per dimension per node+table
    __table_args__ = (
        UniqueConstraint(
            "dimension_id", "node_id", "table_name", "column_name",
            name="uq_dim_mapping_unique"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DimensionColumnMapping dim={self.dimension_id} "
            f"node={self.node_id} {self.table_name}.{self.column_name}>"
        )
