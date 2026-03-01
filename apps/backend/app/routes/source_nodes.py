"""SourceNode API routes.

v2: SourceNode наследует ContentNode, хранит и конфигурацию и данные.
См. docs/SOURCE_NODE_CONCEPT_V2.md для архитектуры.
"""
from typing import Any
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.middleware import get_current_user
from app.services.source_node_service import SourceNodeService
from app.schemas.source_node import (
    SourceNodeCreate,
    SourceNodeUpdate,
    SourceNodeResponse,
    SourceVitrinaResponse,
)
from app.sources import SourceRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/source-nodes", tags=["source-nodes"])


# ============================================
# Витрина источников (Source Showcase)
# ============================================

@router.get("/vitrina", response_model=SourceVitrinaResponse)
async def get_source_vitrina():
    """Get available source types for vitrina (left panel showcase).
    
    Returns list of all source types that can be dragged onto the canvas.
    Public endpoint - no authentication required.
    """
    items = SourceRegistry.get_vitrina_items()
    return SourceVitrinaResponse(items=items)


@router.post("/", response_model=SourceNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_source_node(
    source_data: SourceNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new SourceNode.
    
    Creates a data source point (file, database, API, prompt, stream, or manual).
    """
    try:
        logger.info(f"📥 create_source_node route - source_data.metadata: {source_data.metadata}")
        logger.info(f"📥 create_source_node route - source_data.metadata.name: '{source_data.metadata.get('name', '<NOT SET>>') if source_data.metadata else '<NONE>>'}'")
        source_node = await SourceNodeService.create_source_node(db, source_data)
        logger.info(f"📤 create_source_node route - response node_metadata: {source_node.node_metadata}")
        logger.info(f"📤 create_source_node route - response node_metadata.name: '{source_node.node_metadata.get('name', '<NOT SET>>') if source_node.node_metadata else '<NONE>>'}'")
        return source_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create SourceNode: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{source_id}", response_model=SourceNodeResponse)
async def get_source_node(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get SourceNode by ID."""
    source_node = await SourceNodeService.get_source_node(db, source_id)
    if not source_node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SourceNode not found")
    return source_node


@router.get("/board/{board_id}", response_model=list[SourceNodeResponse])
async def get_board_sources(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all SourceNodes for a board."""
    sources = await SourceNodeService.get_board_sources(db, board_id)
    return sources


@router.put("/{source_id}", response_model=SourceNodeResponse)
async def update_source_node(
    source_id: UUID,
    update_data: SourceNodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update SourceNode configuration or metadata."""
    source_node = await SourceNodeService.update_source_node(db, source_id, update_data)
    if not source_node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SourceNode not found")
    return source_node


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source_node(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete SourceNode."""
    deleted = await SourceNodeService.delete_source_node(db, source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SourceNode not found")


# =============================================================================
# DEPRECATED: POST /extract endpoint удалён в Source-Content Node Architecture v2.0
# SourceNode теперь наследует ContentNode и содержит данные напрямую.
# Данные извлекаются автоматически при создании SourceNode.
# См. docs/SOURCE_CONTENT_NODE_CONCEPT.md
# =============================================================================


@router.post("/{source_id}/refresh", response_model=SourceNodeResponse)
async def refresh_source_node(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-extract data from source.
    
    Extracts fresh data from the original source (file, API, database, etc.)
    and updates the SourceNode's content field.
    """
    try:
        source_node = await SourceNodeService.refresh_source_data(db, source_id)
        if not source_node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SourceNode not found")
        return source_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to refresh SourceNode: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{source_id}/validate", response_model=dict[str, Any])
async def validate_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Validate SourceNode configuration.
    
    Returns validation result with any configuration errors.
    """
    validation_result = await SourceNodeService.validate_source(db, source_id)
    return validation_result
