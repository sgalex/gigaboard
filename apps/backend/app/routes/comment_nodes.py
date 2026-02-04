"""CommentNode routes."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.schemas import (
    CommentNodeCreate,
    CommentNodeUpdate,
    CommentNodeResponse,
    ErrorResponse
)
from app.services.comment_node_service import CommentNodeService
from app.middleware import get_current_user

# Import Socket.IO server for broadcasting
from app.core import sio

router = APIRouter(prefix="/api/v1", tags=["comment-nodes"])


@router.post(
    "/boards/{board_id}/comment-nodes",
    response_model=CommentNodeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def create_comment_node(
    board_id: UUID,
    comment_node_data: CommentNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new CommentNode on a board."""
    try:
        comment_node = await CommentNodeService.create_comment_node(
            db, board_id, current_user.id, comment_node_data
        )
        
        # Broadcast to all clients in the board room
        await sio.emit(
            "comment_node_created",
            {
                "id": str(comment_node.id),
                "board_id": str(comment_node.board_id),
                "author_id": str(comment_node.author_id),
                "content": comment_node.content,
                "format_type": comment_node.format_type,
                "color": comment_node.color,
                "x": comment_node.x,
                "y": comment_node.y,
                "width": comment_node.width,
                "height": comment_node.height,
                "created_at": comment_node.created_at.isoformat() if comment_node.created_at else None,
                "updated_at": comment_node.updated_at.isoformat() if comment_node.updated_at else None,
            },
            room=f"board:{board_id}"
        )
        
        return comment_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/boards/{board_id}/comment-nodes",
    response_model=list[CommentNodeResponse],
    responses={404: {"model": ErrorResponse}}
)
async def list_comment_nodes(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all CommentNodes for a board."""
    comment_nodes = await CommentNodeService.list_comment_nodes(db, board_id, current_user.id)
    return comment_nodes


@router.get(
    "/boards/{board_id}/comment-nodes/{comment_node_id}",
    response_model=CommentNodeResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_comment_node(
    board_id: UUID,
    comment_node_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get CommentNode by ID."""
    try:
        comment_node = await CommentNodeService.get_comment_node(db, comment_node_id, current_user.id)
        return comment_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/boards/{board_id}/comment-nodes/{comment_node_id}",
    response_model=CommentNodeResponse,
    responses={404: {"model": ErrorResponse}}
)
async def update_comment_node(
    board_id: UUID,
    comment_node_id: UUID,
    comment_node_data: CommentNodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update CommentNode."""
    try:
        comment_node = await CommentNodeService.update_comment_node(
            db, comment_node_id, current_user.id, comment_node_data
        )
        
        # Broadcast to all clients in the board room
        await sio.emit(
            "comment_node_updated",
            {
                "id": str(comment_node.id),
                "board_id": str(comment_node.board_id),
                "author_id": str(comment_node.author_id),
                "content": comment_node.content,
                "format_type": comment_node.format_type,
                "color": comment_node.color,
                "x": comment_node.x,
                "y": comment_node.y,
                "width": comment_node.width,
                "height": comment_node.height,
                "created_at": comment_node.created_at.isoformat() if comment_node.created_at else None,
                "updated_at": comment_node.updated_at.isoformat() if comment_node.updated_at else None,
            },
            room=f"board:{board_id}"
        )
        
        return comment_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/boards/{board_id}/comment-nodes/{comment_node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}}
)
async def delete_comment_node(
    board_id: UUID,
    comment_node_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete CommentNode."""
    try:
        await CommentNodeService.delete_comment_node(db, comment_node_id, current_user.id)
        
        # Broadcast to all clients in the board room
        await sio.emit(
            "comment_node_deleted",
            {"id": str(comment_node_id)},
            room=f"board:{board_id}"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/boards/{board_id}/comment-nodes/{comment_node_id}/resolve",
    response_model=CommentNodeResponse,
    responses={404: {"model": ErrorResponse}}
)
async def resolve_comment_node(
    board_id: UUID,
    comment_node_id: UUID,
    is_resolved: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark CommentNode as resolved/unresolved."""
    try:
        comment_node = await CommentNodeService.resolve_comment_node(
            db, comment_node_id, current_user.id, is_resolved
        )
        return comment_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
