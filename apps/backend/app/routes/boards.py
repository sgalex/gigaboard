"""Board routes."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.schemas import (
    BoardCreate,
    BoardUpdate,
    BoardResponse,
    BoardWithNodesResponse,
    ErrorResponse
)
from app.services.board_service import BoardService
from app.middleware import get_current_user

router = APIRouter(prefix="/api/v1/boards", tags=["boards"])


@router.post(
    "",
    response_model=BoardResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def create_board(
    board_data: BoardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new board."""
    board = await BoardService.create_board(db, current_user.id, board_data)
    return board


@router.get(
    "",
    response_model=list[BoardWithNodesResponse],
    responses={401: {"model": ErrorResponse}}
)
async def list_boards(
    project_id: UUID | None = Query(None, description="Filter by project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all boards for current user, optionally filtered by project."""
    boards = await BoardService.list_boards_with_counts(
        db, current_user.id, project_id
    )
    return boards


@router.get(
    "/{board_id}",
    response_model=BoardResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_board(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get board by ID."""
    board = await BoardService.get_board(db, board_id, current_user.id)
    return board


@router.put(
    "/{board_id}",
    response_model=BoardResponse,
    responses={404: {"model": ErrorResponse}}
)
async def update_board(
    board_id: UUID,
    board_data: BoardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update board."""
    board = await BoardService.update_board(
        db, board_id, current_user.id, board_data
    )
    return board


@router.delete(
    "/{board_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}}
)
async def delete_board(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete board (cascades to widgets)."""
    await BoardService.delete_board(db, board_id, current_user.id)
    return None
