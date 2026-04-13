"""Library routes — project widgets & tables CRUD."""
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.schemas import ErrorResponse
from app.schemas.library import (
    ProjectWidgetCreate, ProjectWidgetUpdate, ProjectWidgetResponse,
    ProjectTableCreate, ProjectTableUpdate, ProjectTableResponse,
)
from app.middleware import get_current_user
from app.services.library_service import LibraryService
from app.services.project_access_service import ProjectAccessService


async def _require_project_access_library(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await ProjectAccessService.require_project_view_access(db, project_id, current_user.id)


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/library",
    tags=["library"],
    dependencies=[Depends(_require_project_access_library)],
)


# ── Widgets ──────────────────────────────────────────

@router.post(
    "/widgets",
    response_model=ProjectWidgetResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}},
)
async def save_widget(
    project_id: UUID,
    data: ProjectWidgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a widget from a board to the project library."""
    return await LibraryService.create_widget(db, project_id, current_user.id, data)


@router.get(
    "/widgets",
    response_model=list[ProjectWidgetResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_widgets(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all widgets in the project library."""
    return await LibraryService.list_widgets(db, project_id, current_user.id)


@router.get(
    "/widgets/{widget_id}",
    response_model=ProjectWidgetResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_widget(
    project_id: UUID,
    widget_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific widget from the library."""
    return await LibraryService.get_widget(db, widget_id, current_user.id)


@router.put(
    "/widgets/{widget_id}",
    response_model=ProjectWidgetResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_widget(
    project_id: UUID,
    widget_id: UUID,
    data: ProjectWidgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a library widget (e.g. rename, update description)."""
    return await LibraryService.update_widget(db, widget_id, current_user.id, data)


@router.delete(
    "/widgets/{widget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_widget(
    project_id: UUID,
    widget_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a widget from the project library."""
    await LibraryService.delete_widget(db, widget_id, current_user.id)
    return None


# ── Tables ───────────────────────────────────────────

@router.post(
    "/tables",
    response_model=ProjectTableResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}},
)
async def save_table(
    project_id: UUID,
    data: ProjectTableCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a table from a board to the project library."""
    return await LibraryService.create_table(db, project_id, current_user.id, data)


@router.get(
    "/tables",
    response_model=list[ProjectTableResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_tables(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tables in the project library."""
    return await LibraryService.list_tables(db, project_id, current_user.id)


@router.get(
    "/tables/{table_id}",
    response_model=ProjectTableResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_table(
    project_id: UUID,
    table_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific table from the library."""
    return await LibraryService.get_table(db, table_id, current_user.id)


@router.put(
    "/tables/{table_id}",
    response_model=ProjectTableResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_table(
    project_id: UUID,
    table_id: UUID,
    data: ProjectTableUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a library table."""
    return await LibraryService.update_table(db, table_id, current_user.id, data)


@router.delete(
    "/tables/{table_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_table(
    project_id: UUID,
    table_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a table from the project library."""
    await LibraryService.delete_table(db, table_id, current_user.id)
    return None
