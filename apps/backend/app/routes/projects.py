"""Project routes."""
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.middleware import get_current_user
from app.models import User
from app.schemas import (
    ErrorResponse,
    ProjectCollaboratorAdd,
    ProjectCollaboratorEntry,
    ProjectCollaboratorRoleUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithBoardsResponse,
)
from app.services.project_service import ProjectService
from app.services.project_share_service import ProjectShareService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}}
)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new project."""
    project = await ProjectService.create_project(db, current_user.id, project_data)
    return project


@router.get(
    "",
    response_model=list[ProjectWithBoardsResponse],
    responses={401: {"model": ErrorResponse}}
)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all projects for current user."""
    projects = await ProjectService.list_projects_with_counts(db, current_user.id)
    return projects


@router.get(
    "/{project_id}/collaborators",
    response_model=list[ProjectCollaboratorEntry],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_project_collaborators(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Users who have access to this project (owner or collaborator may view)."""
    rows = await ProjectShareService.list_collaborators(db, project_id, current_user.id)
    return rows


@router.post(
    "/{project_id}/collaborators",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def add_project_collaborator(
    project_id: UUID,
    body: ProjectCollaboratorAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пригласить пользователя (владелец или admin-соавтор)."""
    await ProjectShareService.add_collaborator(
        db, project_id, current_user.id, body.user_id, body.role
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{project_id}/collaborators/{collaborator_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_project_collaborator_role(
    project_id: UUID,
    collaborator_user_id: UUID,
    body: ProjectCollaboratorRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Изменить роль соавтора (не владельца)."""
    await ProjectShareService.update_collaborator_role(
        db, project_id, current_user.id, collaborator_user_id, body.role
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{project_id}/collaborators/{collaborator_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def remove_project_collaborator(
    project_id: UUID,
    collaborator_user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отозвать доступ соавтора (владелец или admin-соавтор)."""
    await ProjectShareService.remove_collaborator(
        db, project_id, current_user.id, collaborator_user_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project by ID."""
    project = await ProjectService.get_project(db, project_id, current_user.id)
    return project


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={404: {"model": ErrorResponse}}
)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update project."""
    project = await ProjectService.update_project(
        db, project_id, current_user.id, project_data
    )
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}}
)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete project (cascades to boards and widgets)."""
    await ProjectService.delete_project(db, project_id, current_user.id)
    return None
