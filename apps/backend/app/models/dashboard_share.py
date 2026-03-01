"""DashboardShare model — sharing configuration for a dashboard."""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.dashboard import Dashboard


class DashboardShare(Base):
    """Sharing configuration for a dashboard (public URL, password, etc.)."""

    __tablename__ = "dashboard_shares"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dashboard_id: Mapped[UUID] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"), unique=True
    )

    # Access type: public, password, private
    share_type: Mapped[str] = mapped_column(String(20), default="public")
    share_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Limits
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_views: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Branding
    branding: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Analytics
    view_count: Mapped[int] = mapped_column(Integer, default=0)

    # Flags
    allow_download: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dashboard: Mapped["Dashboard"] = relationship(back_populates="share")

    def __repr__(self) -> str:
        return f"<DashboardShare {self.share_type} token={self.share_token[:8]}...>"
