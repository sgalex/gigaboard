"""User directory — search for sharing, etc."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.middleware import get_current_user
from app.models import User
from app.schemas import ErrorResponse, UserSearchResult
from app.services.project_access_service import ProjectAccessService
from app.services.project_share_service import ProjectShareService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get(
    "/search",
    response_model=list[UserSearchResult],
    responses={401: {"model": ErrorResponse}},
)
async def search_users(
    project_id: UUID = Query(..., description="Проект, в который идёт приглашение"),
    q: str = Query("", max_length=200, description="Поиск по имени или email"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Подбор пользователей для приглашения (только у кого есть право шаринга в этом проекте)."""
    await ProjectAccessService.require_project_share_access(db, project_id, current_user.id)
    rows = await ProjectShareService.search_users(db, q, current_user.id)
    return rows
