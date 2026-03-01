"""WidgetNode routes."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.schemas import (
    WidgetNodeCreate,
    WidgetNodeUpdate,
    WidgetNodeResponse,
    ErrorResponse
)
from app.services.widget_node_service import WidgetNodeService
from app.middleware import get_current_user

# Import Socket.IO server for broadcasting
from app.core import sio

router = APIRouter(prefix="/api/v1", tags=["widget-nodes"])


@router.post(
    "/boards/{board_id}/widget-nodes",
    response_model=WidgetNodeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def create_widget_node(
    board_id: UUID,
    widget_node_data: WidgetNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new WidgetNode on a board."""
    try:
        widget_node = await WidgetNodeService.create_widget_node(
            db, board_id, current_user.id, widget_node_data
        )
        
        # Broadcast full node data to all clients in the board room
        node_response = WidgetNodeResponse.model_validate(widget_node)
        await sio.emit(
            "widget_node_created",
            node_response.model_dump(mode='json'),
            room=f"board:{board_id}"
        )
        
        return widget_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/boards/{board_id}/widget-nodes",
    response_model=list[WidgetNodeResponse],
    responses={404: {"model": ErrorResponse}}
)
async def list_widget_nodes(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all WidgetNodes for a board."""
    widget_nodes = await WidgetNodeService.list_widget_nodes(db, board_id, current_user.id)
    return widget_nodes


@router.get(
    "/boards/{board_id}/widget-nodes/{widget_node_id}",
    response_model=WidgetNodeResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_widget_node(
    board_id: UUID,
    widget_node_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get WidgetNode by ID."""
    try:
        widget_node = await WidgetNodeService.get_widget_node(db, widget_node_id, current_user.id)
        return widget_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/boards/{board_id}/widget-nodes/{widget_node_id}",
    response_model=WidgetNodeResponse,
    responses={404: {"model": ErrorResponse}}
)
async def update_widget_node(
    board_id: UUID,
    widget_node_id: UUID,
    widget_node_data: WidgetNodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update WidgetNode."""
    try:
        widget_node = await WidgetNodeService.update_widget_node(
            db, widget_node_id, current_user.id, widget_node_data
        )
        
        # Broadcast full node data to all clients in the board room
        node_response = WidgetNodeResponse.model_validate(widget_node)
        await sio.emit(
            "widget_node_updated",
            node_response.model_dump(mode='json'),
            room=f"board:{board_id}"
        )
        
        return widget_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/boards/{board_id}/widget-nodes/{widget_node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}}
)
async def delete_widget_node(
    board_id: UUID,
    widget_node_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete WidgetNode."""
    try:
        await WidgetNodeService.delete_widget_node(db, widget_node_id, current_user.id)
        
        # Broadcast to all clients in the board room
        await sio.emit(
            "widget_node_deleted",
            {"id": str(widget_node_id)},
            room=f"board:{board_id}"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
