"""Project collaboration — users granted access to another user's project."""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class ProjectCollaborator(Base):
    """Many-to-many: project ↔ user (collaborator, not owner)."""

    __tablename__ = "project_collaborators"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_collaborator"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # viewer | editor | admin (admin = полный доступ к управлению участниками, не владелец)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="editor", server_default="editor")

    project: Mapped["Project"] = relationship(back_populates="collaborators")
    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<ProjectCollaborator project={self.project_id} user={self.user_id}>"
