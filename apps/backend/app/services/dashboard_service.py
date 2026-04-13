"""Dashboard service — CRUD for Dashboard + DashboardItem."""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Dashboard, DashboardItem
from app.schemas.dashboard import (
    BatchItemUpdateRequest,
    DashboardCreate,
    DashboardItemCreate,
    DashboardItemUpdate,
    DashboardUpdate,
)
from app.services.project_access_service import ProjectAccessService


class DashboardService:
    """Service for managing dashboards and their items."""

    # ── Dashboard CRUD ──────────────────────────────────

    @staticmethod
    async def create_dashboard(
        db: AsyncSession, project_id: UUID, user_id: UUID, data: DashboardCreate
    ) -> Dashboard:
        await ProjectAccessService.require_project_edit_access(db, project_id, user_id)

        user_settings = data.settings or {}
        settings = {
            "canvas_width": user_settings.get("canvas_width", 1440),
            "canvas_height": user_settings.get("canvas_height", 900),
            "canvas_preset": user_settings.get("canvas_preset", "hd"),
            "theme": user_settings.get("theme", "light"),
            "background_color": user_settings.get("background_color", "#ffffff"),
            "grid_snap": user_settings.get("grid_snap", True),
            "grid_size": user_settings.get("grid_size", 8),
        }

        dashboard = Dashboard(
            project_id=project_id,
            created_by=user_id,
            name=data.name,
            description=data.description,
            settings=settings,
        )
        db.add(dashboard)
        await db.commit()
        await db.refresh(dashboard)
        return dashboard

    @staticmethod
    async def list_dashboards(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> list[Dashboard]:
        await ProjectAccessService.require_project_access(db, project_id, user_id)

        result = await db.execute(
            select(Dashboard)
            .where(Dashboard.project_id == project_id)
            .order_by(Dashboard.updated_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_dashboard(
        db: AsyncSession, dashboard_id: UUID, user_id: UUID
    ) -> Dashboard:
        result = await db.execute(
            select(Dashboard)
            .where(Dashboard.id == dashboard_id)
            .options(
                selectinload(Dashboard.items),
                selectinload(Dashboard.share),
            )
        )
        dashboard = result.scalar_one_or_none()
        if not dashboard:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
        await ProjectAccessService.require_project_access(db, dashboard.project_id, user_id)
        return dashboard

    @staticmethod
    async def update_dashboard(
        db: AsyncSession, dashboard_id: UUID, user_id: UUID, data: DashboardUpdate
    ) -> Dashboard:
        dashboard = await DashboardService.get_dashboard(db, dashboard_id, user_id)
        await ProjectAccessService.require_project_edit_access(
            db, dashboard.project_id, user_id
        )
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "settings" and value is not None:
                # Merge settings — don't overwrite the whole dict
                current_settings = dashboard.settings or {}
                current_settings.update(value)
                dashboard.settings = current_settings
            else:
                setattr(dashboard, field, value)
        await db.commit()
        await db.refresh(dashboard)
        return dashboard

    @staticmethod
    async def delete_dashboard(
        db: AsyncSession, dashboard_id: UUID, user_id: UUID
    ) -> None:
        dashboard = await DashboardService.get_dashboard(db, dashboard_id, user_id)
        await ProjectAccessService.require_project_edit_access(
            db, dashboard.project_id, user_id
        )
        await db.delete(dashboard)
        await db.commit()

    # ── DashboardItem CRUD ──────────────────────────────

    @staticmethod
    async def add_item(
        db: AsyncSession, dashboard_id: UUID, user_id: UUID, data: DashboardItemCreate
    ) -> DashboardItem:
        dash = await DashboardService.get_dashboard(db, dashboard_id, user_id)
        await ProjectAccessService.require_project_edit_access(
            db, dash.project_id, user_id
        )

        # Determine max z_index
        result = await db.execute(
            select(func.coalesce(func.max(DashboardItem.z_index), 0))
            .where(DashboardItem.dashboard_id == dashboard_id)
        )
        max_z = result.scalar()

        layout = data.layout or {
            "desktop": {"x": 0, "y": 0, "width": 400, "height": 300, "visible": True},
            "tablet": None,
            "mobile": None,
        }

        item = DashboardItem(
            dashboard_id=dashboard_id,
            item_type=data.item_type,
            source_id=data.source_id,
            layout=layout,
            overrides=data.overrides or {},
            content=data.content or {},
            z_index=max_z + 1,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def update_item(
        db: AsyncSession, item_id: UUID, user_id: UUID, data: DashboardItemUpdate
    ) -> DashboardItem:
        result = await db.execute(
            select(DashboardItem, Dashboard.project_id)
            .join(Dashboard, Dashboard.id == DashboardItem.dashboard_id)
            .where(DashboardItem.id == item_id)
        )
        row = result.one_or_none()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard item not found")
        item, project_id = row[0], row[1]
        await ProjectAccessService.require_project_edit_access(db, project_id, user_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "layout" and value is not None:
                # Create a new dict so SQLAlchemy detects the mutation
                current_layout = {**(item.layout or {}), **value}
                item.layout = current_layout
            elif field == "overrides" and value is not None:
                current_overrides = {**(item.overrides or {}), **value}
                item.overrides = current_overrides
            else:
                setattr(item, field, value)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def remove_item(
        db: AsyncSession, item_id: UUID, user_id: UUID
    ) -> None:
        result = await db.execute(
            select(DashboardItem, Dashboard.project_id)
            .join(Dashboard, Dashboard.id == DashboardItem.dashboard_id)
            .where(DashboardItem.id == item_id)
        )
        row = result.one_or_none()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard item not found")
        item, project_id = row[0], row[1]
        await ProjectAccessService.require_project_edit_access(db, project_id, user_id)
        await db.delete(item)
        await db.commit()

    @staticmethod
    async def batch_update_items(
        db: AsyncSession, dashboard_id: UUID, user_id: UUID, data: BatchItemUpdateRequest
    ) -> list[DashboardItem]:
        """Batch update multiple items (e.g. after drag/resize on canvas)."""
        dash = await DashboardService.get_dashboard(db, dashboard_id, user_id)
        await ProjectAccessService.require_project_edit_access(
            db, dash.project_id, user_id
        )

        updated: list[DashboardItem] = []
        for update in data.items:
            result = await db.execute(
                select(DashboardItem).where(
                    DashboardItem.id == update.id,
                    DashboardItem.dashboard_id == dashboard_id,
                )
            )
            item = result.scalar_one_or_none()
            if not item:
                continue

            if update.layout is not None:
                current_layout = item.layout or {}
                current_layout.update(update.layout)
                item.layout = current_layout
            if update.z_index is not None:
                item.z_index = update.z_index

        await db.commit()

        # Re-fetch all items
        result = await db.execute(
            select(DashboardItem)
            .where(DashboardItem.dashboard_id == dashboard_id)
            .order_by(DashboardItem.z_index)
        )
        return list(result.scalars().all())

    @staticmethod
    async def duplicate_item(
        db: AsyncSession, item_id: UUID, user_id: UUID
    ) -> DashboardItem:
        """Duplicate a dashboard item with offset."""
        result = await db.execute(
            select(DashboardItem, Dashboard.project_id)
            .join(Dashboard, Dashboard.id == DashboardItem.dashboard_id)
            .where(DashboardItem.id == item_id)
        )
        row = result.one_or_none()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard item not found")
        original, project_id = row[0], row[1]
        await ProjectAccessService.require_project_edit_access(db, project_id, user_id)

        # Get max z
        result = await db.execute(
            select(func.coalesce(func.max(DashboardItem.z_index), 0))
            .where(DashboardItem.dashboard_id == original.dashboard_id)
        )
        max_z = result.scalar()

        # Offset layout by 20px
        layout = dict(original.layout) if original.layout else {}
        if "desktop" in layout and layout["desktop"]:
            desktop = dict(layout["desktop"])
            desktop["x"] = desktop.get("x", 0) + 20
            desktop["y"] = desktop.get("y", 0) + 20
            layout["desktop"] = desktop

        new_item = DashboardItem(
            dashboard_id=original.dashboard_id,
            item_type=original.item_type,
            source_id=original.source_id,
            layout=layout,
            overrides=original.overrides,
            content=original.content,
            z_index=max_z + 1,
        )
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return new_item
