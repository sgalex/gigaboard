"""Library service — CRUD for ProjectWidget and ProjectTable."""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectTable, ProjectWidget
from app.services.project_access_service import ProjectAccessService
from app.schemas.library import (
    ProjectWidgetCreate, ProjectWidgetUpdate,
    ProjectTableCreate, ProjectTableUpdate,
)


class LibraryService:
    """Service for managing project library (widgets & tables)."""

    # === ProjectWidget ===

    @staticmethod
    async def create_widget(
        db: AsyncSession, project_id: UUID, user_id: UUID, data: ProjectWidgetCreate
    ) -> ProjectWidget:
        await ProjectAccessService.require_project_edit_access(db, project_id, user_id)

        widget = ProjectWidget(
            project_id=project_id,
            created_by=user_id,
            name=data.name,
            description=data.description,
            html_code=data.html_code,
            css_code=data.css_code,
            js_code=data.js_code,
            source_widget_node_id=data.source_widget_node_id,
            source_content_node_id=data.source_content_node_id,
            source_board_id=data.source_board_id,
            config=data.config,
        )
        db.add(widget)
        await db.commit()
        await db.refresh(widget)
        return widget

    @staticmethod
    async def list_widgets(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> list[ProjectWidget]:
        await ProjectAccessService.require_project_view_access(db, project_id, user_id)

        result = await db.execute(
            select(ProjectWidget)
            .where(ProjectWidget.project_id == project_id)
            .order_by(ProjectWidget.updated_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_widget(
        db: AsyncSession, widget_id: UUID, user_id: UUID
    ) -> ProjectWidget:
        result = await db.execute(select(ProjectWidget).where(ProjectWidget.id == widget_id))
        widget = result.scalar_one_or_none()
        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
        await ProjectAccessService.require_project_view_access(db, widget.project_id, user_id)
        return widget

    @staticmethod
    async def update_widget(
        db: AsyncSession, widget_id: UUID, user_id: UUID, data: ProjectWidgetUpdate
    ) -> ProjectWidget:
        widget = await LibraryService.get_widget(db, widget_id, user_id)
        await ProjectAccessService.require_project_edit_access(db, widget.project_id, user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(widget, field, value)
        await db.commit()
        await db.refresh(widget)
        return widget

    @staticmethod
    async def delete_widget(
        db: AsyncSession, widget_id: UUID, user_id: UUID
    ) -> None:
        widget = await LibraryService.get_widget(db, widget_id, user_id)
        await ProjectAccessService.require_project_edit_access(db, widget.project_id, user_id)
        await db.delete(widget)
        await db.commit()

    # === ProjectTable ===

    @staticmethod
    async def create_table(
        db: AsyncSession, project_id: UUID, user_id: UUID, data: ProjectTableCreate
    ) -> ProjectTable:
        await ProjectAccessService.require_project_edit_access(db, project_id, user_id)

        table = ProjectTable(
            project_id=project_id,
            created_by=user_id,
            name=data.name,
            description=data.description,
            source_content_node_id=data.source_content_node_id,
            source_board_id=data.source_board_id,
            table_name_in_node=data.table_name_in_node,
            columns=data.columns,
            sample_data=data.sample_data,
            row_count=data.row_count,
            config=data.config,
        )
        db.add(table)
        await db.commit()
        await db.refresh(table)
        return table

    @staticmethod
    async def list_tables(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> list[ProjectTable]:
        await ProjectAccessService.require_project_view_access(db, project_id, user_id)

        result = await db.execute(
            select(ProjectTable)
            .where(ProjectTable.project_id == project_id)
            .order_by(ProjectTable.updated_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_table(
        db: AsyncSession, table_id: UUID, user_id: UUID
    ) -> ProjectTable:
        result = await db.execute(select(ProjectTable).where(ProjectTable.id == table_id))
        table = result.scalar_one_or_none()
        if not table:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
        await ProjectAccessService.require_project_view_access(db, table.project_id, user_id)
        return table

    @staticmethod
    async def update_table(
        db: AsyncSession, table_id: UUID, user_id: UUID, data: ProjectTableUpdate
    ) -> ProjectTable:
        table = await LibraryService.get_table(db, table_id, user_id)
        await ProjectAccessService.require_project_edit_access(db, table.project_id, user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(table, field, value)
        await db.commit()
        await db.refresh(table)
        return table

    @staticmethod
    async def delete_table(
        db: AsyncSession, table_id: UUID, user_id: UUID
    ) -> None:
        table = await LibraryService.get_table(db, table_id, user_id)
        await ProjectAccessService.require_project_edit_access(db, table.project_id, user_id)
        await db.delete(table)
        await db.commit()
