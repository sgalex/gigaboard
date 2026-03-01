"""Public routes — unauthenticated dashboard access via share tokens."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.schemas import ErrorResponse
from app.schemas.dashboard import PublicDashboardResponse
from app.services.share_service import ShareService

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get(
    "/dashboards/{token}",
    response_model=PublicDashboardResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        410: {"model": ErrorResponse},
    },
)
async def get_public_dashboard(
    token: str,
    password: str | None = Query(None, description="Password if required"),
    db: AsyncSession = Depends(get_db),
):
    """View a shared dashboard (no auth required)."""
    return await ShareService.get_public_dashboard(db, token, password)
