"""CommentNode service - business logic for comment nodes."""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommentNode, Board
from app.schemas import CommentNodeCreate, CommentNodeUpdate


class CommentNodeService:
    """Service for managing CommentNodes."""
    
    @staticmethod
    async def create_comment_node(
        db: AsyncSession,
        board_id: UUID,
        user_id: UUID,
        data: CommentNodeCreate
    ) -> CommentNode:
        """Create a new CommentNode."""
        # Verify board exists and user has access
        result = await db.execute(
            select(Board).where(Board.id == board_id, Board.user_id == user_id)
        )
        board = result.scalar_one_or_none()
        if not board:
            raise ValueError("Board not found or access denied")
        
        # Create CommentNode
        comment_node = CommentNode(
            board_id=board_id,
            author_id=user_id,
            **data.model_dump()
        )
        db.add(comment_node)
        await db.commit()
        await db.refresh(comment_node)
        return comment_node
    
    @staticmethod
    async def get_comment_node(
        db: AsyncSession,
        comment_node_id: UUID,
        user_id: UUID
    ) -> CommentNode:
        """Get CommentNode by ID."""
        result = await db.execute(
            select(CommentNode)
            .join(Board)
            .where(CommentNode.id == comment_node_id, Board.user_id == user_id)
        )
        comment_node = result.scalar_one_or_none()
        if not comment_node:
            raise ValueError("CommentNode not found or access denied")
        return comment_node
    
    @staticmethod
    async def list_comment_nodes(
        db: AsyncSession,
        board_id: UUID,
        user_id: UUID
    ) -> list[CommentNode]:
        """List all CommentNodes for a board."""
        result = await db.execute(
            select(CommentNode)
            .join(Board)
            .where(CommentNode.board_id == board_id, Board.user_id == user_id)
            .order_by(CommentNode.created_at)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def update_comment_node(
        db: AsyncSession,
        comment_node_id: UUID,
        user_id: UUID,
        data: CommentNodeUpdate
    ) -> CommentNode:
        """Update CommentNode."""
        comment_node = await CommentNodeService.get_comment_node(db, comment_node_id, user_id)
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(comment_node, key, value)
        
        await db.commit()
        await db.refresh(comment_node)
        return comment_node
    
    @staticmethod
    async def delete_comment_node(
        db: AsyncSession,
        comment_node_id: UUID,
        user_id: UUID
    ) -> None:
        """Delete CommentNode."""
        comment_node = await CommentNodeService.get_comment_node(db, comment_node_id, user_id)
        await db.delete(comment_node)
        await db.commit()
    
    @staticmethod
    async def resolve_comment_node(
        db: AsyncSession,
        comment_node_id: UUID,
        user_id: UUID,
        is_resolved: bool
    ) -> CommentNode:
        """Mark CommentNode as resolved/unresolved."""
        comment_node = await CommentNodeService.get_comment_node(db, comment_node_id, user_id)
        
        comment_node.is_resolved = is_resolved
        if is_resolved:
            from datetime import datetime
            comment_node.resolved_at = datetime.utcnow()
            comment_node.resolved_by = user_id
        else:
            comment_node.resolved_at = None
            comment_node.resolved_by = None
        
        await db.commit()
        await db.refresh(comment_node)
        return comment_node
