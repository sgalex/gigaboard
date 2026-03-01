"""Project model."""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.board import Board
    from app.models.dashboard import Dashboard
    from app.models.project_widget import ProjectWidget
    from app.models.project_table import ProjectTable
    from app.models.dimension import Dimension
    from app.models.filter_preset import FilterPreset


class Project(Base):
    """Project model - container for boards and data sources."""
    
    __tablename__ = "projects"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Foreign keys
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    
    # Fields
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="projects")
    boards: Mapped[list["Board"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    dashboards: Mapped[list["Dashboard"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    project_widgets: Mapped[list["ProjectWidget"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    project_tables: Mapped[list["ProjectTable"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    # Cross-filter system
    dimensions: Mapped[list["Dimension"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    filter_presets: Mapped[list["FilterPreset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Project {self.name}>"
