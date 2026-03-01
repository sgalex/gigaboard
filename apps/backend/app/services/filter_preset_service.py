"""FilterPreset service — CRUD for saved filter presets.

See docs/CROSS_FILTER_SYSTEM.md
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.filter_preset import FilterPreset
from app.schemas.cross_filter import FilterPresetCreate, FilterPresetUpdate

logger = logging.getLogger(__name__)


class FilterPresetService:
    """CRUD operations for FilterPreset."""

    @staticmethod
    async def create_preset(
        db: AsyncSession,
        project_id: UUID,
        user_id: UUID,
        data: FilterPresetCreate,
    ) -> FilterPreset:
        # If this preset is_default — reset other defaults with same scope
        if data.is_default:
            await FilterPresetService._reset_defaults(
                db, project_id, data.scope.value, data.target_id
            )

        filters_dict = data.filters.model_dump() if hasattr(data.filters, "model_dump") else data.filters
        preset = FilterPreset(
            project_id=project_id,
            created_by=user_id,
            name=data.name,
            description=data.description,
            filters=filters_dict,
            scope=data.scope.value,
            target_id=data.target_id,
            is_default=data.is_default,
            tags=data.tags or [],
        )
        db.add(preset)
        await db.flush()
        logger.info("Created FilterPreset %s (%s) in project %s", preset.name, preset.id, project_id)
        return preset

    @staticmethod
    async def list_presets(
        db: AsyncSession,
        project_id: UUID,
        scope: str | None = None,
        target_id: UUID | None = None,
    ) -> list[FilterPreset]:
        stmt = select(FilterPreset).where(FilterPreset.project_id == project_id)
        if scope:
            stmt = stmt.where(FilterPreset.scope == scope)
        if target_id:
            stmt = stmt.where(FilterPreset.target_id == target_id)
        stmt = stmt.order_by(FilterPreset.name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_preset(
        db: AsyncSession,
        preset_id: UUID,
    ) -> FilterPreset | None:
        stmt = select(FilterPreset).where(FilterPreset.id == preset_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_preset(
        db: AsyncSession,
        preset_id: UUID,
        data: FilterPresetUpdate,
    ) -> FilterPreset | None:
        preset = await FilterPresetService.get_preset(db, preset_id)
        if not preset:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Handle is_default toggling
        if update_data.get("is_default"):
            await FilterPresetService._reset_defaults(
                db, preset.project_id, preset.scope, preset.target_id
            )

        # Serialize filters if present
        if "filters" in update_data and update_data["filters"] is not None:
            f = update_data["filters"]
            if hasattr(f, "model_dump"):
                update_data["filters"] = f.model_dump()

        for key, value in update_data.items():
            setattr(preset, key, value)
        await db.flush()
        return preset

    @staticmethod
    async def delete_preset(
        db: AsyncSession,
        preset_id: UUID,
    ) -> bool:
        preset = await FilterPresetService.get_preset(db, preset_id)
        if not preset:
            return False
        await db.delete(preset)
        await db.flush()
        return True

    @staticmethod
    async def get_default_preset(
        db: AsyncSession,
        project_id: UUID,
        scope: str | None = None,
        target_id: UUID | None = None,
    ) -> FilterPreset | None:
        """Get the default preset for a given scope."""
        stmt = (
            select(FilterPreset)
            .where(
                FilterPreset.project_id == project_id,
                FilterPreset.is_default == True,
            )
        )
        if scope:
            stmt = stmt.where(FilterPreset.scope == scope)
        if target_id:
            stmt = stmt.where(FilterPreset.target_id == target_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def _reset_defaults(
        db: AsyncSession,
        project_id: UUID,
        scope: str,
        target_id: UUID | None,
    ) -> None:
        """Set is_default=False for all presets matching scope+target."""
        stmt = select(FilterPreset).where(
            FilterPreset.project_id == project_id,
            FilterPreset.scope == scope,
            FilterPreset.is_default == True,
        )
        if target_id:
            stmt = stmt.where(FilterPreset.target_id == target_id)
        result = await db.execute(stmt)
        for p in result.scalars().all():
            p.is_default = False
