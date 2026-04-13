"""WidgetNode service - business logic for widget nodes."""
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WidgetNode
from app.models.edge import Edge
from app.schemas import WidgetNodeCreate, WidgetNodeUpdate
from app.services.board_service import BoardService


class WidgetNodeService:
    """Service for managing WidgetNodes."""
    
    @staticmethod
    async def create_widget_node(
        db: AsyncSession,
        board_id: UUID,
        user_id: UUID,
        data: WidgetNodeCreate
    ) -> WidgetNode:
        """Create a new WidgetNode."""
        await BoardService.get_board_for_edit(db, board_id, user_id)
        
        # Create WidgetNode
        widget_node = WidgetNode(
            board_id=board_id,
            **data.model_dump()
        )
        db.add(widget_node)
        await db.commit()
        await db.refresh(widget_node)
        return widget_node
    
    @staticmethod
    async def get_widget_node(
        db: AsyncSession,
        widget_node_id: UUID,
        user_id: UUID
    ) -> WidgetNode:
        """Get WidgetNode by ID."""
        result = await db.execute(select(WidgetNode).where(WidgetNode.id == widget_node_id))
        widget_node = result.scalar_one_or_none()
        if not widget_node:
            raise ValueError("WidgetNode not found or access denied")
        await BoardService.get_board(db, widget_node.board_id, user_id)
        return widget_node
    
    @staticmethod
    async def list_widget_nodes(
        db: AsyncSession,
        board_id: UUID,
        user_id: UUID
    ) -> list[WidgetNode]:
        """List all WidgetNodes for a board."""
        await BoardService.get_board(db, board_id, user_id)
        result = await db.execute(
            select(WidgetNode)
            .where(WidgetNode.board_id == board_id)
            .order_by(WidgetNode.created_at)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def update_widget_node(
        db: AsyncSession,
        widget_node_id: UUID,
        user_id: UUID,
        data: WidgetNodeUpdate
    ) -> WidgetNode:
        """Update WidgetNode."""
        widget_node = await WidgetNodeService.get_widget_node(db, widget_node_id, user_id)
        await BoardService.get_board_for_edit(db, widget_node.board_id, user_id)

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(widget_node, key, value)
        
        await db.commit()
        await db.refresh(widget_node)
        return widget_node
    
    @staticmethod
    async def delete_widget_node(
        db: AsyncSession,
        widget_node_id: UUID,
        user_id: UUID
    ) -> None:
        """Delete WidgetNode and its referencing edges."""
        widget_node = await WidgetNodeService.get_widget_node(db, widget_node_id, user_id)
        await BoardService.get_board_for_edit(db, widget_node.board_id, user_id)
        await db.execute(
            delete(Edge).where(
                or_(
                    Edge.source_node_id == widget_node_id,
                    Edge.target_node_id == widget_node_id,
                )
            )
        )
        await db.delete(widget_node)
        await db.commit()
