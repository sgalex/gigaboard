"""Board service."""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text
from fastapi import HTTPException, status

from app.models import Board, Project, SourceNode, ContentNode, WidgetNode, CommentNode
from app.schemas import BoardCreate, BoardUpdate


class BoardService:
    """Service for managing boards."""
    
    @staticmethod
    async def create_board(
        db: AsyncSession,
        user_id: UUID,
        board_data: BoardCreate
    ) -> Board:
        """Create a new board."""
        # Verify project exists and user owns it
        result = await db.execute(
            select(Project).where(
                Project.id == board_data.project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
            )
        
        board = Board(
            project_id=board_data.project_id,
            user_id=user_id,
            name=board_data.name,
            description=board_data.description
        )
        
        db.add(board)
        await db.commit()
        await db.refresh(board)
        
        return board
    
    @staticmethod
    async def get_board(
        db: AsyncSession,
        board_id: UUID,
        user_id: UUID
    ) -> Board:
        """Get board by ID (user must be owner)."""
        result = await db.execute(
            select(Board).where(
                Board.id == board_id,
                Board.user_id == user_id
            )
        )
        board = result.scalar_one_or_none()
        
        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found"
            )
        
        return board
    
    @staticmethod
    async def list_boards(
        db: AsyncSession,
        user_id: UUID,
        project_id: UUID | None = None
    ) -> list[Board]:
        """List all boards for user, optionally filtered by project."""
        query = select(Board).where(Board.user_id == user_id)
        
        if project_id:
            query = query.where(Board.project_id == project_id)
        
        query = query.order_by(Board.updated_at.desc())
        
        result = await db.execute(query)
        boards = result.scalars().all()
        
        return list(boards)
    
    @staticmethod
    async def list_boards_with_counts(
        db: AsyncSession,
        user_id: UUID,
        project_id: UUID | None = None
    ) -> list[dict]:
        """List all boards with node counts."""
        # Query boards with counts for all node types (SourceNode + ContentNode replaced DataNode)
        query = (
            select(
                Board,
                func.count(SourceNode.id.distinct()).label('source_nodes_count'),
                func.count(ContentNode.id.distinct()).label('content_nodes_count'),
                func.count(WidgetNode.id.distinct()).label('widget_nodes_count'),
                func.count(CommentNode.id.distinct()).label('comment_nodes_count')
            )
            .outerjoin(SourceNode, SourceNode.board_id == Board.id)
            .outerjoin(ContentNode, ContentNode.board_id == Board.id)
            .outerjoin(WidgetNode, WidgetNode.board_id == Board.id)
            .outerjoin(CommentNode, CommentNode.board_id == Board.id)
            .where(Board.user_id == user_id)
            .group_by(Board.id)
            .order_by(Board.updated_at.desc())
        )
        
        if project_id:
            query = query.where(Board.project_id == project_id)
        
        result = await db.execute(query)
        
        boards_with_counts = []
        for board, source_nodes_count, content_nodes_count, widget_nodes_count, comment_nodes_count in result:
            board_dict = board.__dict__.copy()
            board_dict['source_nodes_count'] = source_nodes_count
            board_dict['content_nodes_count'] = content_nodes_count
            board_dict['widget_nodes_count'] = widget_nodes_count
            board_dict['comment_nodes_count'] = comment_nodes_count
            boards_with_counts.append(board_dict)
        
        return boards_with_counts
    
    @staticmethod
    async def update_board(
        db: AsyncSession,
        board_id: UUID,
        user_id: UUID,
        board_data: BoardUpdate
    ) -> Board:
        """Update board."""
        board = await BoardService.get_board(db, board_id, user_id)
        
        # Update only provided fields
        if board_data.name is not None:
            board.name = board_data.name
        if board_data.description is not None:
            board.description = board_data.description
        
        await db.commit()
        await db.refresh(board)
        
        return board
    
    @staticmethod
    async def delete_board(
        db: AsyncSession,
        board_id: UUID,
        user_id: UUID
    ) -> None:
        """Delete board (cascades to nodes).
        
        Due to polymorphic inheritance (SourceNode->ContentNode->BaseNode),
        we use raw SQL to avoid SQLAlchemy ORM issues with joined table inheritance.
        board_id exists only in nodes table, child tables use id as FK to nodes.id
        """
        board = await BoardService.get_board(db, board_id, user_id)
        
        # Use raw SQL to delete in correct order
        # Step 1: Delete edges (has board_id)
        await db.execute(
            text("DELETE FROM edges WHERE board_id = :board_id"),
            {"board_id": board_id}
        )
        
        # Step 2: Delete child node tables using subquery to nodes
        # SourceNode references ContentNode, so delete it first
        await db.execute(
            text("DELETE FROM source_nodes WHERE id IN (SELECT id FROM nodes WHERE board_id = :board_id)"),
            {"board_id": board_id}
        )
        await db.execute(
            text("DELETE FROM content_nodes WHERE id IN (SELECT id FROM nodes WHERE board_id = :board_id)"),
            {"board_id": board_id}
        )
        await db.execute(
            text("DELETE FROM widget_nodes WHERE id IN (SELECT id FROM nodes WHERE board_id = :board_id)"),
            {"board_id": board_id}
        )
        await db.execute(
            text("DELETE FROM comment_nodes WHERE id IN (SELECT id FROM nodes WHERE board_id = :board_id)"),
            {"board_id": board_id}
        )
        
        # Step 3: Delete from base nodes table (has board_id)
        await db.execute(
            text("DELETE FROM nodes WHERE board_id = :board_id"),
            {"board_id": board_id}
        )
        
        # Step 4: Delete the board
        await db.execute(
            text("DELETE FROM boards WHERE id = :board_id"),
            {"board_id": board_id}
        )
        
        await db.commit()
