"""ContentNode service - business logic for managing processed data.

См. docs/SOURCE_CONTENT_NODE_CONCEPT.md для деталей.
"""
from typing import Any
from uuid import UUID
import logging
from datetime import datetime

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentNode
from app.schemas.content_node import ContentNodeCreate, ContentNodeUpdate, ContentData, DataLineage

logger = logging.getLogger(__name__)


class ContentNodeService:
    """Service for managing ContentNodes."""
    
    @staticmethod
    async def create_content_node(
        db: AsyncSession,
        content_data: ContentNodeCreate
    ) -> ContentNode:
        """Create a new ContentNode.
        
        Args:
            db: Database session
            content_data: ContentNode creation data
            
        Returns:
            Created ContentNode
        """
        # Normalize content and lineage to dict
        content_dict = content_data.content
        if isinstance(content_dict, ContentData):
            content_dict = content_dict.model_dump()
        
        lineage_dict = content_data.lineage
        if isinstance(lineage_dict, DataLineage):
            lineage_dict = lineage_dict.model_dump()
        
        # Create ContentNode (BaseNode fields will be auto-populated via JTI)
        content_node = ContentNode(
            board_id=content_data.board_id,
            content=content_dict,
            lineage=lineage_dict,
            node_metadata=content_data.metadata or {},
            position=content_data.position or {"x": 0, "y": 0}
        )
        db.add(content_node)
        await db.flush()  # Get the ID
        
        table_count = len(content_dict.get("tables", []))
        logger.info(f"Created ContentNode {content_node.id} (tables: {table_count})")
        
        # Log table details for debugging
        for idx, table in enumerate(content_dict.get("tables", [])):
            row_count = table.get("row_count", len(table.get("rows", [])))
            col_count = table.get("column_count", len(table.get("columns", [])))
            logger.info(f"  Table {idx}: {table.get('name')} ({row_count} rows × {col_count} cols)")
        
        return content_node
    
    @staticmethod
    async def get_content_node(db: AsyncSession, content_id: UUID) -> ContentNode | None:
        """Get ContentNode by ID.
        
        Args:
            db: Database session
            content_id: ContentNode ID
            
        Returns:
            ContentNode or None if not found
        """
        result = await db.execute(
            select(ContentNode).where(ContentNode.id == content_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_board_contents(db: AsyncSession, board_id: UUID) -> list[ContentNode]:
        """Get all ContentNodes for a board.
        
        Args:
            db: Database session
            board_id: Board ID
            
        Returns:
            List of ContentNodes
        """
        result = await db.execute(
            select(ContentNode).where(ContentNode.board_id == board_id)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def update_content_node(
        db: AsyncSession,
        content_id: UUID,
        update_data: ContentNodeUpdate
    ) -> ContentNode | None:
        """Update ContentNode.
        
        Args:
            db: Database session
            content_id: ContentNode ID
            update_data: Update data
            
        Returns:
            Updated ContentNode or None if not found
        """
        content = await ContentNodeService.get_content_node(db, content_id)
        if not content:
            return None
        
        # Update fields
        if update_data.content is not None:
            content_dict = update_data.content
            if isinstance(content_dict, ContentData):
                content_dict = content_dict.model_dump()
            content.content = content_dict
        
        if update_data.lineage is not None:
            lineage_dict = update_data.lineage
            if isinstance(lineage_dict, DataLineage):
                lineage_dict = lineage_dict.model_dump()
            content.lineage = lineage_dict
        
        if update_data.metadata is not None:
            # Merge metadata instead of replacing
            current_metadata = content.node_metadata or {}
            merged_metadata = {**current_metadata, **update_data.metadata}
            content.node_metadata = merged_metadata
            logger.info(f"Updating metadata for ContentNode {content_id}: {current_metadata} -> {merged_metadata}")
        
        if update_data.position is not None:
            content.position = update_data.position
        
        await db.commit()
        await db.refresh(content)
        
        logger.info(f"Updated ContentNode {content_id}")
        return content
    
    @staticmethod
    async def delete_content_node(db: AsyncSession, content_id: UUID) -> bool:
        """Delete ContentNode with cascade deletion of dependent nodes.
        
        Deletes:
        - All ContentNodes that have this node as source (lineage.source_node_id)
        - All WidgetNodes that visualize this ContentNode
        - All Edges connected to this node
        
        Args:
            db: Database session
            content_id: ContentNode ID
            
        Returns:
            True if deleted, False if not found
        """
        from app.models import ContentNode, WidgetNode, Edge
        from sqlalchemy import select, or_
        
        content = await ContentNodeService.get_content_node(db, content_id)
        if not content:
            return False
        
        logger.info(f"🗑️ Deleting ContentNode {content_id} with cascade")
        
        # 1. Find and delete dependent ContentNodes (those created from this node)
        dependent_contents_result = await db.execute(
            select(ContentNode)
        )
        dependent_contents = dependent_contents_result.scalars().all()
        
        # Filter by lineage in Python (JSONB queries are complex)
        to_delete = []
        for node in dependent_contents:
            if node.id == content_id:
                continue
            lineage = node.lineage or {}
            source_id = lineage.get("source_node_id")
            source_ids = lineage.get("source_node_ids", [])
            
            if source_id == str(content_id) or str(content_id) in source_ids:
                to_delete.append(node.id)
                logger.info(f"  📦 Will cascade delete dependent ContentNode {node.id}")
        
        # Recursively delete dependent ContentNodes
        for dep_id in to_delete:
            await ContentNodeService.delete_content_node(db, dep_id)
        
        # 2. Find and delete WidgetNodes that visualize this ContentNode (via VISUALIZATION edges)
        from app.models.edge import Edge
        widget_edges_result = await db.execute(
            select(Edge).where(
                and_(
                    Edge.source_node_id == content_id,
                    Edge.edge_type == "VISUALIZATION"
                )
            )
        )
        widget_edges = widget_edges_result.scalars().all()
        
        # Delete the WidgetNodes at the target of VISUALIZATION edges
        for edge in widget_edges:
            widget_result = await db.execute(
                select(WidgetNode).where(WidgetNode.id == edge.target_node_id)
            )
            widget = widget_result.scalar_one_or_none()
            if widget:
                logger.info(f"  📊 Deleting dependent WidgetNode {widget.id}")
                await db.delete(widget)
        
        # 3. Delete all edges connected to this node
        edges_result = await db.execute(
            select(Edge).where(
                or_(
                    Edge.source_node_id == content_id,
                    Edge.target_node_id == content_id
                )
            )
        )
        edges = edges_result.scalars().all()
        
        for edge in edges:
            logger.info(f"  🔗 Deleting connected Edge {edge.id}")
            await db.delete(edge)
        
        # 4. Finally delete the ContentNode itself
        await db.delete(content)
        await db.commit()
        
        logger.info(f"✅ Deleted ContentNode {content_id} with {len(to_delete)} dependent ContentNodes, {len(widget_edges)} WidgetNodes, and {len(edges)} Edges")
        return True
    
    @staticmethod
    async def get_table(
        db: AsyncSession,
        content_id: UUID,
        table_id: str
    ) -> dict[str, Any] | None:
        """Get specific table from ContentNode.
        
        Args:
            db: Database session
            content_id: ContentNode ID
            table_id: Table identifier
            
        Returns:
            Table data or None if not found
        """
        content = await ContentNodeService.get_content_node(db, content_id)
        if not content:
            return None
        
        tables = content.content.get("tables", [])
        for table in tables:
            if table.get("id") == table_id:
                return table
        
        return None
    
    @staticmethod
    async def get_lineage_chain(
        db: AsyncSession,
        content_id: UUID
    ) -> list[dict[str, Any]]:
        """Get full data lineage chain for ContentNode.
        
        Args:
            db: Database session
            content_id: ContentNode ID
            
        Returns:
            List of lineage records from source to current node
        """
        lineage_chain = []
        current_id = content_id
        visited = set()
        
        while current_id and current_id not in visited:
            visited.add(current_id)
            
            content = await ContentNodeService.get_content_node(db, current_id)
            if not content:
                break
            
            lineage_chain.append({
                "content_node_id": str(content.id),
                "lineage": content.lineage,
                "created_at": content.created_at.isoformat() if content.created_at else None
            })
            
            # Follow parent chain
            parent_ids = content.lineage.get("parent_content_ids", [])
            if parent_ids:
                current_id = UUID(parent_ids[0]) if isinstance(parent_ids[0], str) else parent_ids[0]
            else:
                break
        
        return lineage_chain
    
    @staticmethod
    async def get_downstream_contents(
        db: AsyncSession,
        content_id: UUID
    ) -> list[ContentNode]:
        """Get all ContentNodes that depend on this ContentNode.
        
        Args:
            db: Database session
            content_id: ContentNode ID
            
        Returns:
            List of downstream ContentNodes
        """
        # Query for ContentNodes where parent_content_ids contains this ID
        # Using PostgreSQL JSONB containment operator
        result = await db.execute(
            select(ContentNode).where(
                ContentNode.lineage["parent_content_ids"].astext.contains(str(content_id))
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def transform_content(
        db: AsyncSession,
        source_content_ids: list[UUID],
        transform_code: str,
        description: str | None = None
    ) -> ContentNode:
        """Transform ContentNode(s) using Python code.
        
        Args:
            db: Database session
            source_content_ids: List of source ContentNode IDs
            transform_code: Python code to execute
            description: Optional transformation description
            
        Returns:
            New ContentNode with transformed data
        
        Note: This is a simplified implementation for Phase 2.
        Full sandboxed execution will be implemented later.
        """
        # Load source ContentNodes
        source_contents = []
        for content_id in source_content_ids:
            content = await ContentNodeService.get_content_node(db, content_id)
            if not content:
                raise ValueError(f"ContentNode {content_id} not found")
            source_contents.append(content)
        
        if not source_contents:
            raise ValueError("At least one source ContentNode is required")
        
        # Prepare execution environment
        import pandas as pd
        
        # Create dataframes from source tables
        dfs = {}
        for i, content in enumerate(source_contents):
            tables = content.content.get("tables", [])
            for j, table in enumerate(tables):
                df_name = f"df{i}_{j}" if len(source_contents) > 1 else f"df{j}"
                columns = table.get("columns", [])
                rows = table.get("rows", [])
                dfs[df_name] = pd.DataFrame(rows, columns=columns)
        
        # Execute transformation code
        exec_globals = {"pd": pd, **dfs}
        exec_locals = {}
        
        try:
            exec(transform_code, exec_globals, exec_locals)
        except Exception as e:
            logger.exception(f"Transformation code execution failed: {e}")
            raise ValueError(f"Transformation failed: {str(e)}")
        
        # Extract result (expect 'result' variable or 'df' as fallback)
        result_df = exec_locals.get("result") or exec_locals.get("df")
        if result_df is None:
            raise ValueError("Transformation must produce 'result' or 'df' variable")
        
        if not isinstance(result_df, pd.DataFrame):
            raise ValueError("Result must be a pandas DataFrame")
        
        # Convert result to ContentNode format
        result_table = {
            "name": "transformed_data",
            "columns": [str(col) for col in result_df.columns],
            "rows": result_df.fillna("").values.tolist(),
            "row_count": len(result_df),
            "column_count": len(result_df.columns),
            "metadata": {"transformation": description or "Python transformation"}
        }
        
        # Build lineage
        lineage_dict = {
            "source_nodes": [],
            "parent_content_ids": [str(c.id) for c in source_contents],
            "transformation_history": [
                {
                    "operation": "transform",
                    "description": description or "Python transformation",
                    "code_snippet": transform_code[:500],  # Truncate long code
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }
        
        # Aggregate source_nodes from all parents
        for content in source_contents:
            parent_source_nodes = content.lineage.get("source_nodes", [])
            lineage_dict["source_nodes"].extend(parent_source_nodes)
        
        # Deduplicate source_nodes
        lineage_dict["source_nodes"] = list(set(lineage_dict["source_nodes"]))
        
        # Generate text summary
        text_summary = f"Transformed from {len(source_contents)} ContentNode(s)\n"
        text_summary += f"Result: {len(result_df)} rows × {len(result_df.columns)} columns\n"
        if description:
            text_summary += f"Description: {description}"
        
        # Create new ContentNode
        content_create = ContentNodeCreate(
            board_id=source_contents[0].board_id,
            content=ContentData(
                text=text_summary,
                tables=[result_table]
            ),
            lineage=DataLineage(**lineage_dict),
            metadata={"transformation": {"code": transform_code, "description": description}},
            position={"x": 0, "y": 0}
        )
        
        new_content = await ContentNodeService.create_content_node(db, content_create)
        
        # Create TRANSFORMATION edges
        from app.models import Edge, EdgeType
        for source_content in source_contents:
            edge = Edge(
                board_id=source_content.board_id,
                source_id=source_content.id,
                target_id=new_content.id,
                edge_type=EdgeType.TRANSFORMATION,
                metadata={"auto_created": True, "description": description}
            )
            db.add(edge)
        
        await db.commit()
        await db.refresh(new_content)
        
        logger.info(f"Transformed {len(source_contents)} ContentNodes -> ContentNode {new_content.id}")
        
        return new_content
