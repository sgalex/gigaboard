"""Extraction API endpoints - SourceNode → ContentNode data extraction.

Handles EXTRACT edge creation between SourceNode and ContentNode.
См. docs/CONNECTION_TYPES.md для деталей о EXTRACT edges.
"""
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware import get_current_user
from app.models import User, SourceNode, ContentNode, Edge
from app.services.source_node_service import SourceNodeService
from app.services.content_node_service import ContentNodeService
from app.services.edge_service import EdgeService
from app.services.extractors import (
    FileExtractor,
    DatabaseExtractor,
    APIExtractor,
    ManualExtractor,
    PromptExtractor
)
from app.services.file_storage import get_storage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["extraction"])


# ============================================
# Schemas
# ============================================

class ExtractionRequest(BaseModel):
    """Request to extract data from SourceNode."""
    position: dict[str, float] = Field(
        default_factory=lambda: {"x": 0, "y": 0},
        description="Position for ContentNode on canvas"
    )
    preview_rows: int | None = Field(None, description="Limit rows for preview")


class ExtractionResponse(BaseModel):
    """Response after successful extraction."""
    content_node: dict[str, Any]
    extract_edge: dict[str, Any]
    summary: dict[str, Any] = Field(
        description="Extraction summary (tables, rows, etc.)"
    )


# ============================================
# Extraction Endpoints
# ============================================

@router.post(
    "/boards/{board_id}/source-nodes/{source_node_id}/extract",
    response_model=ExtractionResponse
)
async def extract_data_from_source(
    board_id: UUID,
    source_node_id: UUID,
    request: ExtractionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Extract data from SourceNode and create ContentNode with EXTRACT edge.
    
    Workflow:
    1. Get SourceNode and validate permissions
    2. Use appropriate extractor based on source_type
    3. Create ContentNode with extracted data
    4. Create EXTRACT edge
    5. Broadcast to board via Socket.IO
    
    Args:
        board_id: Board UUID
        source_node_id: SourceNode UUID
        request: Extraction parameters
        db: Database session
        current_user: Authenticated user
        
    Returns:
        ExtractionResponse with ContentNode and edge data
        
    Raises:
        404: SourceNode not found or user has no access
        400: Extraction failed (invalid config, parsing error, etc.)
        500: Internal error
    """
    try:
        # 1. Get SourceNode
        source_node = await SourceNodeService.get_source_node(db, source_node_id)
        
        if not source_node or source_node.board_id != board_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SourceNode not found or access denied"
            )
        
        logger.info(
            f"Starting extraction: source={source_node_id}, "
            f"type={source_node.source_type}, user={current_user.id}"
        )
        
        # 2. Select and execute extractor
        extractor = _get_extractor(source_node.source_type)
        extraction_params = {}
        if request.preview_rows:
            extraction_params["preview_rows"] = request.preview_rows
        
        # Special handling for file source - need to pass db session for storage
        if source_node.source_type == "file":
            extraction_params["db"] = db
        
        extraction_result = await extractor.extract(
            config=source_node.config,
            params=extraction_params
        )
        
        if not extraction_result.is_success:
            error_msg = "; ".join(extraction_result.errors)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extraction failed: {error_msg}"
            )
        
        # 3. Create ContentNode
        content_dict = extraction_result.to_content_dict()
        
        # Add extraction summary to text if empty
        if not content_dict.get("text"):
            tables = content_dict.get("tables", [])
            if tables:
                total_rows = sum(t.get("row_count", 0) for t in tables)
                table_names = ", ".join(t.get("name", "table") for t in tables[:3])
                content_dict["text"] = (
                    f"Extracted {len(tables)} table(s) with {total_rows} total rows. "
                    f"Tables: {table_names}"
                    + ("..." if len(tables) > 3 else "")
                )
        
        from app.schemas.content_node import ContentNodeCreate
        content_create = ContentNodeCreate(
            board_id=board_id,
            content=content_dict,
            lineage={
                "source_node_id": str(source_node_id),
                "operation": "extract",
                "created_by": str(current_user.id)
            },
            metadata=extraction_result.metadata,
            position=request.position
        )
        
        content_node = await ContentNodeService.create_content_node(db, content_create)
        
        # 4. Create EXTRACT edge
        from app.schemas.edge import EdgeCreate
        edge_create = EdgeCreate(
            board_id=board_id,
            edge_type="EXTRACT",
            source_node_id=source_node_id,
            source_node_type="source_node",
            target_node_id=content_node.id,
            target_node_type="content_node",
            transformation_params={
                "extraction_method": source_node.source_type,
                "rows_extracted": sum(
                    t.get("row_count", 0) for t in content_dict.get("tables", [])
                ),
                "tables_created": len(content_dict.get("tables", []))
            }
        )
        
        extract_edge = await EdgeService.create_edge(db, board_id, edge_create, current_user.id)
        
        await db.commit()
        await db.refresh(content_node)
        await db.refresh(extract_edge)
        
        logger.info(
            f"Extraction complete: content_node={content_node.id}, "
            f"tables={len(content_dict.get('tables', []))}"
        )
        
        # 5. Prepare response
        summary = {
            "tables_created": len(content_dict.get("tables", [])),
            "total_rows": sum(
                t.get("row_count", 0) for t in content_dict.get("tables", [])
            ),
            "source_type": source_node.source_type
        }
        
        # TODO: Broadcast to board via Socket.IO
        # await broadcast_to_board(board_id, {
        #     "type": "content_node_created",
        #     "content_node": content_node_dict,
        #     "edge": edge_dict
        # })
        
        return ExtractionResponse(
            content_node=_serialize_content_node(content_node),
            extract_edge=_serialize_edge(extract_edge),
            summary=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Extraction failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )


# ============================================
# Helper Functions
# ============================================

def _get_extractor(source_type: str):
    """Get appropriate extractor for source type."""
    extractors = {
        "file": FileExtractor(),
        "database": DatabaseExtractor(),
        "api": APIExtractor(),
        "manual": ManualExtractor(),
        "prompt": PromptExtractor()
    }
    
    extractor = extractors.get(source_type)
    if not extractor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported source type: {source_type}"
        )
    
    return extractor


def _serialize_content_node(content_node: ContentNode) -> dict[str, Any]:
    """Serialize ContentNode for API response."""
    return {
        "id": str(content_node.id),
        "board_id": str(content_node.board_id),
        "node_type": content_node.node_type,
        "content": content_node.content,
        "lineage": content_node.lineage,
        "metadata": content_node.node_metadata,
        "position": content_node.position,
        "created_at": content_node.created_at.isoformat(),
        "updated_at": content_node.updated_at.isoformat()
    }


def _serialize_edge(edge: Edge) -> dict[str, Any]:
    """Serialize Edge for API response."""
    return {
        "id": str(edge.id),
        "board_id": str(edge.board_id),
        "edge_type": edge.edge_type.value if hasattr(edge.edge_type, 'value') else edge.edge_type,
        "source_node_id": str(edge.source_node_id),
        "target_node_id": str(edge.target_node_id),
        "source_node_type": edge.source_node_type,
        "target_node_type": edge.target_node_type,
        "transformation_params": edge.transformation_params or {},
        "visual_config": edge.visual_config or {},
        "created_at": edge.created_at.isoformat()
    }
