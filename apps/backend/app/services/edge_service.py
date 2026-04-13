"""Edge service for Source-Content Node architecture."""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommentNode, ContentNode, SourceNode, WidgetNode
from app.models.edge import Edge, EdgeType
from app.schemas.edge import EdgeCreate, EdgeUpdate
from app.services.board_service import BoardService


class EdgeService:
    """Service for managing edges between nodes."""
    
    @staticmethod
    async def create_edge(
        db: AsyncSession,
        board_id: UUID,
        edge_data: EdgeCreate,
        user_id: UUID
    ) -> Edge:
        """Create a new edge between nodes."""
        await BoardService.get_board_for_edit(db, board_id, user_id)
        
        # Validate source node exists
        await EdgeService._validate_node_exists(
            db, board_id, edge_data.source_node_id, edge_data.source_node_type
        )
        
        # Validate target node exists
        await EdgeService._validate_node_exists(
            db, board_id, edge_data.target_node_id, edge_data.target_node_type
        )
        
        # Validate edge type compatibility
        EdgeService._validate_edge_type(
            edge_data.source_node_type,
            edge_data.target_node_type,
            edge_data.edge_type
        )
        
        # Create edge
        edge = Edge(
            board_id=board_id,
            source_node_id=edge_data.source_node_id,
            source_node_type=edge_data.source_node_type,
            target_node_id=edge_data.target_node_id,
            target_node_type=edge_data.target_node_type,
            edge_type=edge_data.edge_type,
            label=edge_data.label,
            transformation_code=edge_data.transformation_code,
            transformation_params=edge_data.transformation_params or {},
            visual_config=edge_data.visual_config or {},
            is_valid="true"
        )
        
        db.add(edge)
        await db.commit()
        await db.refresh(edge)
        
        return edge
    
    @staticmethod
    async def get_edge(
        db: AsyncSession,
        board_id: UUID,
        edge_id: UUID,
        user_id: UUID
    ) -> Edge:
        """Get a single edge by ID."""
        await BoardService.get_board(db, board_id, user_id)
        
        # Get edge
        result = await db.execute(
            select(Edge).where(
                and_(
                    Edge.id == edge_id,
                    Edge.board_id == board_id,
                    Edge.deleted_at.is_(None)
                )
            )
        )
        edge = result.scalar_one_or_none()
        if not edge:
            raise ValueError("Edge not found")
        
        return edge
    
    @staticmethod
    async def list_edges(
        db: AsyncSession,
        board_id: UUID,
        user_id: UUID
    ) -> List[Edge]:
        """List all edges for a board."""
        await BoardService.get_board(db, board_id, user_id)
        
        # Get all edges
        result = await db.execute(
            select(Edge).where(
                and_(
                    Edge.board_id == board_id,
                    Edge.deleted_at.is_(None)
                )
            ).order_by(Edge.created_at.desc())
        )
        edges = result.scalars().all()
        
        return list(edges)
    
    @staticmethod
    async def update_edge(
        db: AsyncSession,
        board_id: UUID,
        edge_id: UUID,
        edge_data: EdgeUpdate,
        user_id: UUID
    ) -> Edge:
        """Update an edge."""
        # Get edge with ownership verification
        edge = await EdgeService.get_edge(db, board_id, edge_id, user_id)
        await BoardService.get_board_for_edit(db, board_id, user_id)

        # Update fields
        update_data = edge_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(edge, field, value)
        
        await db.commit()
        await db.refresh(edge)
        
        return edge
    
    @staticmethod
    async def delete_edge(
        db: AsyncSession,
        board_id: UUID,
        edge_id: UUID,
        user_id: UUID
    ) -> None:
        """Delete an edge (soft delete)."""
        # Get edge with ownership verification
        edge = await EdgeService.get_edge(db, board_id, edge_id, user_id)
        await BoardService.get_board_for_edit(db, board_id, user_id)

        # Soft delete
        from datetime import datetime
        edge.deleted_at = datetime.utcnow()
        
        await db.commit()
    
    @staticmethod
    async def _validate_node_exists(
        db: AsyncSession,
        board_id: UUID,
        node_id: UUID,
        node_type: str
    ) -> None:
        """Validate that a node exists and belongs to the board."""
        model_map = {
            'SourceNode': SourceNode,
            'source_node': SourceNode,
            'ContentNode': ContentNode,
            'content_node': ContentNode,
            'WidgetNode': WidgetNode,
            'CommentNode': CommentNode
        }
        
        model = model_map.get(node_type)
        if not model:
            raise ValueError(f"Invalid node type: {node_type}")
        
        result = await db.execute(
            select(model).where(
                and_(
                    model.id == node_id,
                    model.board_id == board_id
                )
            )
        )
        node = result.scalar_one_or_none()
        if not node:
            raise ValueError(f"{node_type} not found or does not belong to this board")
    
    @staticmethod
    def _validate_edge_type(
        source_node_type: str,
        target_node_type: str,
        edge_type: EdgeType
    ) -> None:
        """Validate edge type is compatible with source and target node types.
        
        Source-Content Node Architecture v2.0:
        - SourceNode наследует ContentNode и содержит данные напрямую
        - TRANSFORMATION: SourceNode/ContentNode → ContentNode
        - VISUALIZATION: SourceNode/ContentNode → WidgetNode
        """
        # Normalize node types (support both snake_case and PascalCase)
        source_type_normalized = source_node_type.replace('_', '').lower()
        target_type_normalized = target_node_type.replace('_', '').lower()
        
        # Content-bearing nodes (can be source for transformation/visualization)
        content_bearing_types = {'sourcenode', 'contentnode'}
        
        # TRANSFORMATION: SourceNode/ContentNode -> ContentNode
        if edge_type == EdgeType.TRANSFORMATION:
            if source_type_normalized not in content_bearing_types or target_type_normalized != 'contentnode':
                raise ValueError("TRANSFORMATION edges must connect SourceNode/ContentNode to ContentNode")
        
        # VISUALIZATION: SourceNode/ContentNode -> WidgetNode
        elif edge_type == EdgeType.VISUALIZATION:
            if source_type_normalized not in content_bearing_types or target_type_normalized != 'widgetnode':
                raise ValueError("VISUALIZATION edges must connect SourceNode/ContentNode to WidgetNode")
        
        # COMMENT: CommentNode -> any node
        elif edge_type == EdgeType.COMMENT:
            if source_type_normalized != 'commentnode':
                raise ValueError("COMMENT edges must start from CommentNode")
        
        # DRILL_DOWN and REFERENCE can connect any nodes
        # No validation needed
