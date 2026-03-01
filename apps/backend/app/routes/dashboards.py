"""Dashboard routes — CRUD for dashboards, items, sharing."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.schemas import ErrorResponse
from app.schemas.dashboard import (
    DashboardCreate, DashboardUpdate,
    DashboardResponse, DashboardWithItemsResponse,
    DashboardItemCreate, DashboardItemUpdate, DashboardItemResponse,
    BatchItemUpdateRequest,
    DashboardShareCreate, DashboardShareResponse,
)
from app.services.dashboard_service import DashboardService
from app.services.share_service import ShareService
from app.middleware import get_current_user

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


# ── Dashboard CRUD ───────────────────────────────────

@router.post(
    "",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}},
)
async def create_dashboard(
    data: DashboardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new dashboard in a project."""
    return await DashboardService.create_dashboard(
        db, data.project_id, current_user.id, data
    )


@router.get(
    "",
    response_model=list[DashboardResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_dashboards(
    project_id: UUID = Query(..., description="Filter by project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List dashboards for a project."""
    return await DashboardService.list_dashboards(db, project_id, current_user.id)


@router.get(
    "/{dashboard_id}",
    response_model=DashboardWithItemsResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_dashboard(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard with all items."""
    return await DashboardService.get_dashboard(db, dashboard_id, current_user.id)


@router.put(
    "/{dashboard_id}",
    response_model=DashboardResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_dashboard(
    dashboard_id: UUID,
    data: DashboardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update dashboard metadata / settings."""
    return await DashboardService.update_dashboard(
        db, dashboard_id, current_user.id, data
    )


@router.delete(
    "/{dashboard_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_dashboard(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete dashboard (cascades to items & share)."""
    await DashboardService.delete_dashboard(db, dashboard_id, current_user.id)
    return None


# ── Dashboard Items ──────────────────────────────────

@router.post(
    "/{dashboard_id}/items",
    response_model=DashboardItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}},
)
async def add_item(
    dashboard_id: UUID,
    data: DashboardItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an item (widget, table, text, etc.) to the dashboard."""
    return await DashboardService.add_item(db, dashboard_id, current_user.id, data)


@router.put(
    "/{dashboard_id}/items/{item_id}",
    response_model=DashboardItemResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_item(
    dashboard_id: UUID,
    item_id: UUID,
    data: DashboardItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a dashboard item (layout, content, overrides)."""
    return await DashboardService.update_item(db, item_id, current_user.id, data)


@router.delete(
    "/{dashboard_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def remove_item(
    dashboard_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an item from the dashboard."""
    await DashboardService.remove_item(db, item_id, current_user.id)
    return None


@router.put(
    "/{dashboard_id}/items",
    response_model=list[DashboardItemResponse],
    responses={404: {"model": ErrorResponse}},
)
async def batch_update_items(
    dashboard_id: UUID,
    data: BatchItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Batch update item layouts (after multi-drag/resize)."""
    return await DashboardService.batch_update_items(
        db, dashboard_id, current_user.id, data
    )


@router.post(
    "/{dashboard_id}/items/{item_id}/duplicate",
    response_model=DashboardItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}},
)
async def duplicate_item(
    dashboard_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Duplicate a dashboard item with slight offset."""
    return await DashboardService.duplicate_item(db, item_id, current_user.id)


# ── Sharing ──────────────────────────────────────────

@router.post(
    "/{dashboard_id}/share",
    response_model=DashboardShareResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}},
)
async def create_share(
    dashboard_id: UUID,
    data: DashboardShareCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a share link for the dashboard."""
    return await ShareService.create_or_update_share(
        db, dashboard_id, current_user.id, data
    )


@router.get(
    "/{dashboard_id}/share",
    response_model=DashboardShareResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_share(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current share settings for the dashboard."""
    return await ShareService.get_share(db, dashboard_id, current_user.id)


@router.delete(
    "/{dashboard_id}/share",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_share(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove share link (revoke public access)."""
    await ShareService.delete_share(db, dashboard_id, current_user.id)
    return None
