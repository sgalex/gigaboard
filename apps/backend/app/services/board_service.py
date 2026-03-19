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
        # Скалярные подзапросы вместо нескольких outerjoin к подклассам nodes
        # (иначе SAWarning: overlapping tables / joined inheritance).
        query = (
            select(
                Board,
                select(func.count(SourceNode.id))
                .where(SourceNode.board_id == Board.id)
                .scalar_subquery()
                .label("source_nodes_count"),
                select(func.count(ContentNode.id))
                .where(ContentNode.board_id == Board.id)
                .scalar_subquery()
                .label("content_nodes_count"),
                select(func.count(WidgetNode.id))
                .where(WidgetNode.board_id == Board.id)
                .scalar_subquery()
                .label("widget_nodes_count"),
                select(func.count(CommentNode.id))
                .where(CommentNode.board_id == Board.id)
                .scalar_subquery()
                .label("comment_nodes_count"),
            )
            .where(Board.user_id == user_id)
            .order_by(Board.updated_at.desc())
        )
        
        if project_id:
            query = query.where(Board.project_id == project_id)
        
        result = await db.execute(query)
        
        boards_with_counts = []
        board_ids = []
        for board, source_nodes_count, content_nodes_count, widget_nodes_count, comment_nodes_count in result:
            # Build dict explicitly so thumbnail_url and all Board fields are included
            # (board.__dict__ can contain SQLAlchemy internals and may omit some attributes)
            board_dict = {
                "id": board.id,
                "project_id": board.project_id,
                "user_id": board.user_id,
                "name": board.name,
                "description": board.description,
                "settings": board.settings,
                "thumbnail_url": getattr(board, "thumbnail_url", None),
                "created_at": board.created_at,
                "updated_at": board.updated_at,
                "source_nodes_count": source_nodes_count,
                "content_nodes_count": content_nodes_count,
                "widget_nodes_count": widget_nodes_count,
                "comment_nodes_count": comment_nodes_count,
                "tables_count": 0,
                "columns_count": 0,
            }
            boards_with_counts.append(board_dict)
            board_ids.append(board.id)
        
        if board_ids:
            from sqlalchemy import text
            t_result = await db.execute(
                text("""
                    SELECT n.board_id, COALESCE(SUM(
                        COALESCE(jsonb_array_length(cn.content->'tables'), 0)
                    ), 0)::bigint AS c
                    FROM content_nodes cn
                    JOIN nodes n ON n.id = cn.id
                    WHERE n.board_id = ANY(:board_ids)
                    GROUP BY n.board_id
                """),
                {"board_ids": list(board_ids)},
            )
            t_map = {row[0]: int(row[1]) for row in t_result}
            col_result = await db.execute(
                text("""
                    WITH expanded AS (
                        SELECT n.board_id,
                            CASE
                                WHEN jsonb_typeof(tbl->'columns') = 'array' THEN
                                    COALESCE(jsonb_array_length(tbl->'columns'), 0)
                                WHEN tbl ? 'column_count' AND jsonb_typeof(tbl->'column_count') = 'number' THEN
                                    GREATEST(0, (tbl->>'column_count')::int)
                                ELSE 0
                            END AS col_count
                        FROM content_nodes cn
                        JOIN nodes n ON n.id = cn.id,
                        LATERAL jsonb_array_elements(
                            CASE WHEN jsonb_typeof(cn.content->'tables') = 'array'
                                THEN cn.content->'tables'
                                ELSE '[]'::jsonb
                            END
                        ) AS tbl
                        WHERE n.board_id = ANY(:board_ids)
                    )
                    SELECT board_id, COALESCE(SUM(col_count), 0)::bigint AS c
                    FROM expanded
                    GROUP BY board_id
                """),
                {"board_ids": list(board_ids)},
            )
            col_map = {row[0]: int(row[1]) for row in col_result}
            for b in boards_with_counts:
                b['tables_count'] = t_map.get(b['id'], 0)
                b['columns_count'] = col_map.get(b['id'], 0)
        
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
        if board_data.settings is not None:
            board.settings = board_data.settings
        if board_data.thumbnail_url is not None:
            board.thumbnail_url = board_data.thumbnail_url
        
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
