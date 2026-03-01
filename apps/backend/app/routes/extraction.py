"""Extraction API endpoints — извлечение данных в SourceNode.

Source-Content Node Architecture v2.0:
SourceNode наследует ContentNode и хранит данные напрямую в content.
Extraction обновляет SourceNode.content извлечёнными таблицами.
"""
import logging
from typing import Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware import get_current_user
from app.models import User, SourceNode
from app.services.source_node_service import SourceNodeService
from app.services.extractors import (
    FileExtractor,
    DatabaseExtractor,
    APIExtractor,
    ManualExtractor,
    PromptExtractor
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["extraction"])


# ============================================
# Schemas
# ============================================

class ExtractionRequest(BaseModel):
    """Request to extract data from SourceNode."""
    position: dict[str, float] | None = Field(None, description="Unused, kept for compat")
    preview_rows: int | None = Field(None, description="Limit rows for preview")


class ExtractionResponse(BaseModel):
    """Response after successful extraction."""
    source_node_id: str
    summary: dict[str, Any] = Field(description="Extraction summary")


# ============================================
# Extraction Endpoint
# ============================================

@router.post(
    "/boards/{board_id}/source-nodes/{source_node_id}/extract",
    response_model=ExtractionResponse,
)
async def extract_data_from_source(
    board_id: UUID,
    source_node_id: UUID,
    request: ExtractionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract data and store it inside SourceNode.content.

    Architecture v2.0: SourceNode inherits ContentNode,
    so extracted tables are saved directly in source_node.content.
    No separate ContentNode or Edge is created.
    """
    try:
        # 1. Get SourceNode
        source_node = await SourceNodeService.get_source_node(db, source_node_id)
        if not source_node or source_node.board_id != board_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SourceNode not found or access denied",
            )

        logger.info(
            f"Starting extraction: source={source_node_id}, "
            f"type={source_node.source_type}, user={current_user.id}"
        )

        # 2. Run extractor
        extractor = _get_extractor(source_node.source_type)
        extraction_params: dict[str, Any] = {}
        if request.preview_rows:
            extraction_params["preview_rows"] = request.preview_rows
        if source_node.source_type == "file":
            extraction_params["db"] = db

        extraction_result = await extractor.extract(
            config=source_node.config,
            params=extraction_params,
        )

        if not extraction_result.is_success:
            error_msg = "; ".join(extraction_result.errors)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extraction failed: {error_msg}",
            )

        # 3. Store extracted data directly in SourceNode.content
        content_dict = extraction_result.to_content_dict()

        # Build summary text
        tables = content_dict.get("tables", [])
        total_rows = sum(t.get("row_count", 0) for t in tables)
        if tables:
            table_names = ", ".join(t.get("name", "table") for t in tables[:5])
            content_dict["text"] = (
                f"Extracted {len(tables)} table(s), {total_rows} rows. "
                f"Tables: {table_names}"
                + ("…" if len(tables) > 5 else "")
            )

        source_node.content = content_dict
        source_node.lineage = {
            "operation": "extract",
            "extracted_at": datetime.utcnow().isoformat(),
            "extracted_by": str(current_user.id),
        }

        # Update metadata
        meta = source_node.node_metadata or {}
        meta.update({
            "table_count": len(tables),
            "total_rows": total_rows,
            **(extraction_result.metadata or {}),
        })
        source_node.node_metadata = meta

        await db.commit()
        await db.refresh(source_node)

        summary = {
            "tables_extracted": len(tables),
            "total_rows": total_rows,
            "source_type": source_node.source_type,
        }
        logger.info(
            f"Extraction complete: source_node={source_node_id}, "
            f"tables={len(tables)}, rows={total_rows}"
        )

        return ExtractionResponse(
            source_node_id=str(source_node_id),
            summary=summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Extraction failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )


# ============================================
# Helper
# ============================================

def _get_extractor(source_type: str):
    """Get appropriate extractor for source type."""
    extractors = {
        "file": FileExtractor(),
        "database": DatabaseExtractor(),
        "api": APIExtractor(),
        "manual": ManualExtractor(),
        "prompt": PromptExtractor(),
    }
    extractor = extractors.get(source_type)
    if not extractor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported source type: {source_type}",
        )
    return extractor
