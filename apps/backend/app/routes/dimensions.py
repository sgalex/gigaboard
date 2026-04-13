"""Dimensions API routes — CRUD for project dimensions and column mappings.

See docs/CROSS_FILTER_SYSTEM.md §3.1, §5
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import ContentNode, User
from app.middleware import get_current_user
from app.services.project_access_service import ProjectAccessService
from app.schemas.cross_filter import (
    DimensionCreate,
    DimensionUpdate,
    DimensionResponse,
    DimensionColumnMappingCreate,
    DimensionColumnMappingResponse,
    MergeDimensionsRequest,
    MergeDimensionsResponse,
)
from app.services.content_node_service import ContentNodeService
from app.services.dimension_service import DimensionService


async def _require_project_view(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await ProjectAccessService.require_project_view_access(db, project_id, current_user.id)


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/dimensions",
    tags=["dimensions"],
    dependencies=[Depends(_require_project_view)],
)


# ═══════════════════════════════════════════════════════════════════════
#  Dimension CRUD
# ═══════════════════════════════════════════════════════════════════════


@router.get("", response_model=list[DimensionResponse])
async def list_dimensions(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all dimensions in a project."""
    return await DimensionService.list_dimensions(db, project_id)


@router.post("", response_model=DimensionResponse, status_code=status.HTTP_201_CREATED)
async def create_dimension(
    project_id: UUID,
    data: DimensionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new dimension in a project."""
    await ProjectAccessService.require_project_edit_access(db, project_id, current_user.id)
    dim = await DimensionService.create_dimension(db, project_id, data)
    await db.commit()
    await db.refresh(dim)
    return dim


@router.get("/{dim_id}", response_model=DimensionResponse)
async def get_dimension(
    project_id: UUID,
    dim_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a dimension by ID."""
    dim = await DimensionService.get_dimension(db, dim_id)
    if not dim or dim.project_id != project_id:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return dim


@router.put("/{dim_id}", response_model=DimensionResponse)
async def update_dimension(
    project_id: UUID,
    dim_id: UUID,
    data: DimensionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a dimension."""
    await ProjectAccessService.require_project_edit_access(db, project_id, current_user.id)
    dim = await DimensionService.update_dimension(db, dim_id, data)
    if not dim or dim.project_id != project_id:
        raise HTTPException(status_code=404, detail="Dimension not found")
    await db.commit()
    await db.refresh(dim)
    return dim


@router.delete("/{dim_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dimension(
    project_id: UUID,
    dim_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a dimension and all its mappings."""
    await ProjectAccessService.require_project_edit_access(db, project_id, current_user.id)
    deleted = await DimensionService.delete_dimension(db, dim_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dimension not found")
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════
#  Merge dimensions
# ═══════════════════════════════════════════════════════════════════════


@router.post("/merge", response_model=MergeDimensionsResponse)
async def merge_dimensions(
    project_id: UUID,
    data: MergeDimensionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merge one or more source dimensions into a target dimension.

    All column mappings from source dimensions are transferred to the target.
    Duplicate mappings are silently dropped. Source dimensions are deleted.
    """
    await ProjectAccessService.require_project_edit_access(db, project_id, current_user.id)
    try:
        result = await DimensionService.merge_dimensions(
            db, project_id, list(data.source_ids), data.target_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return MergeDimensionsResponse(
        target_id=data.target_id,
        deleted_count=result["deleted"],
        transferred_count=result["transferred"],
    )


# ═══════════════════════════════════════════════════════════════════════
#  Column Mappings
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{dim_id}/mappings", response_model=list[DimensionColumnMappingResponse])
async def list_mappings(
    project_id: UUID,
    dim_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List column mappings for a dimension."""
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as sa_select
    from app.models.dimension_column_mapping import DimensionColumnMapping as DCM

    stmt = (
        sa_select(DCM)
        .where(DCM.dimension_id == dim_id)
        .options(selectinload(DCM.dimension))
        .order_by(DCM.table_name, DCM.column_name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{dim_id}/mappings", response_model=DimensionColumnMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    project_id: UUID,
    dim_id: UUID,
    data: DimensionColumnMappingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a column mapping for a dimension."""
    await ProjectAccessService.require_project_edit_access(db, project_id, current_user.id)
    # Ensure the dimension_id matches the path
    data.dimension_id = dim_id
    mapping = await DimensionService.create_mapping(db, data)
    await db.commit()
    await db.refresh(mapping)
    return mapping


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(
    project_id: UUID,
    mapping_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a column mapping."""
    await ProjectAccessService.require_project_edit_access(db, project_id, current_user.id)
    deleted = await DimensionService.delete_mapping(db, mapping_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════
#  Dimension Values (aggregate unique values from mapped columns)
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{dim_id}/values")
async def get_dimension_values(
    project_id: UUID,
    dim_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get unique values for a dimension from all mapped content nodes."""
    from sqlalchemy import select
    from app.models.dimension_column_mapping import DimensionColumnMapping
    from app.models.content_node import ContentNode as CN

    # Get all mappings
    mappings = await DimensionService.get_mappings_for_dimension(db, dim_id)
    if not mappings:
        return {"values": [], "total": 0}

    unique_values: set = set()
    for m in mappings:
        # Load the ContentNode
        stmt = select(CN).where(CN.id == m.node_id)
        result = await db.execute(stmt)
        node = result.scalar_one_or_none()
        if not node or not node.content:
            continue

        tables = node.content.get("tables", [])
        for table in tables:
            if table.get("name") != m.table_name:
                continue
            for row in table.get("rows", []):
                val = row.get(m.column_name)
                if val is not None and val != "":
                    unique_values.add(val)

    sorted_values = sorted(unique_values, key=lambda x: str(x))
    return {"values": sorted_values, "total": len(sorted_values)}
