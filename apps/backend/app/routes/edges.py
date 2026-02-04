"""Edge routes for node connections."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.edge import EdgeCreate, EdgeUpdate, EdgeResponse, EdgeListResponse
from app.services.edge_service import EdgeService
from app.core import sio

router = APIRouter(prefix="/api/v1/boards", tags=["edges"])


@router.post(
    "/{board_id}/edges",
    response_model=EdgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create edge between nodes"
)
async def create_edge(
    board_id: UUID,
    edge_data: EdgeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a connection between two nodes.
    
    Edge types:
    - TRANSFORMATION: DataNode -> DataNode (with Python pandas code)
    - VISUALIZATION: DataNode -> WidgetNode (auto-refresh)
    - COMMENT: CommentNode -> any node
    - DRILL_DOWN: any node -> any node (navigation)
    - REFERENCE: any node -> any node (logical link)
    """
    try:
        edge = await EdgeService.create_edge(
            db, board_id, edge_data, current_user.id
        )
        
        # Broadcast to all clients in the board room
        await sio.emit(
            "edge_created",
            {
                "id": str(edge.id),
                "board_id": str(edge.board_id),
                "source_node_id": str(edge.source_node_id),
                "target_node_id": str(edge.target_node_id),
                "source_node_type": edge.source_node_type,
                "target_node_type": edge.target_node_type,
                "edge_type": edge.edge_type.value if hasattr(edge.edge_type, 'value') else str(edge.edge_type),
                "label": edge.label,
                "created_at": edge.created_at.isoformat() if edge.created_at else None,
                "updated_at": edge.updated_at.isoformat() if edge.updated_at else None,
            },
            room=f"board:{board_id}"
        )
        
        return edge
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/{board_id}/edges",
    response_model=EdgeListResponse,
    summary="Get all edges for a board"
)
async def list_edges(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all edges (connections) for a board."""
    try:
        edges = await EdgeService.list_edges(db, board_id, current_user.id)
        return EdgeListResponse(edges=edges, total=len(edges))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/{board_id}/edges/{edge_id}",
    response_model=EdgeResponse,
    summary="Get edge by ID"
)
async def get_edge(
    board_id: UUID,
    edge_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific edge by ID."""
    try:
        edge = await EdgeService.get_edge(db, board_id, edge_id, current_user.id)
        return edge
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.patch(
    "/{board_id}/edges/{edge_id}",
    response_model=EdgeResponse,
    summary="Update edge"
)
async def update_edge(
    board_id: UUID,
    edge_id: UUID,
    edge_data: EdgeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update edge properties.
    
    Can update:
    - label
    - transformation_code (for TRANSFORMATION edges)
    - transformation_params
    - visual_config
    """
    try:
        edge = await EdgeService.update_edge(
            db, board_id, edge_id, edge_data, current_user.id
        )
        
        # Broadcast to all clients in the board room
        await sio.emit(
            "edge_updated",
            {
                "id": str(edge.id),
                "board_id": str(edge.board_id),
                "source_node_id": str(edge.source_node_id),
                "target_node_id": str(edge.target_node_id),
                "source_node_type": edge.source_node_type,
                "target_node_type": edge.target_node_type,
                "edge_type": edge.edge_type.value if hasattr(edge.edge_type, 'value') else str(edge.edge_type),
                "label": edge.label,
                "created_at": edge.created_at.isoformat() if edge.created_at else None,
                "updated_at": edge.updated_at.isoformat() if edge.updated_at else None,
            },
            room=f"board:{board_id}"
        )
        
        return edge
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete(
    "/{board_id}/edges/{edge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete edge"
)
async def delete_edge(
    board_id: UUID,
    edge_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete (soft delete) an edge."""
    try:
        await EdgeService.delete_edge(db, board_id, edge_id, current_user.id)
        
        # Broadcast to all clients in the board room
        await sio.emit(
            "edge_deleted",
            {
                "id": str(edge_id),
                "board_id": str(board_id)
            },
            room=f"board:{board_id}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
