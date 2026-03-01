"""Dashboard model — presentation layer for widgets and tables."""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.dashboard_item import DashboardItem
    from app.models.dashboard_share import DashboardShare


class Dashboard(Base):
    """Dashboard — collection of widgets and tables with free-form layout."""

    __tablename__ = "dashboards"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, published, archived
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # splash/preview image URL

    # Dashboard settings: canvas_width, canvas_height, grid settings, theme, etc.
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=lambda: {
        "canvas_width": 1440,
        "canvas_height": 900,
        "canvas_preset": "hd",
        "theme": "light",
        "background_color": "#ffffff",
        "grid_snap": True,
        "grid_size": 8,
    })

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="dashboards")
    creator: Mapped["User"] = relationship()
    items: Mapped[list["DashboardItem"]] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan",
        order_by="DashboardItem.z_index"
    )
    share: Mapped["DashboardShare | None"] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Dashboard {self.name}>"
