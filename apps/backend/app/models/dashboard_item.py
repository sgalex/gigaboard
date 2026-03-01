"""DashboardItem model — element placed on a dashboard."""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.dashboard import Dashboard


class DashboardItem(Base):
    """An item placed on a dashboard (widget, table, text block, image, line)."""

    __tablename__ = "dashboard_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dashboard_id: Mapped[UUID] = mapped_column(ForeignKey("dashboards.id", ondelete="CASCADE"))

    # Item type: widget, table, text, image, line
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Reference to library source (ProjectWidget or ProjectTable)
    source_id: Mapped[UUID | None] = mapped_column(nullable=True)

    # Layout per breakpoint: { desktop: {x,y,width,height,visible}, tablet: null|{...}, mobile: null|{...} }
    layout: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {
        "desktop": {"x": 0, "y": 0, "width": 400, "height": 300, "visible": True},
        "tablet": None,
        "mobile": None,
    })

    # Override styles for this placement
    overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    # Content for text/image items (not from library)
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Z-order
    z_index: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dashboard: Mapped["Dashboard"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<DashboardItem {self.item_type} z={self.z_index}>"
