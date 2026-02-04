"""SourceNode service - business logic for managing data sources.

См. docs/SOURCE_CONTENT_NODE_CONCEPT.md для деталей.
"""
from typing import Any
from uuid import UUID
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceNode, SourceType
from app.schemas.source_node import SourceNodeCreate, SourceNodeUpdate
from app.services.extractors import (
    FileExtractor,
    DatabaseExtractor,
    APIExtractor,
    PromptExtractor,
    StreamExtractor,
    ManualExtractor,
)
from app.services.file_storage import get_file_storage
from app.sources.csv.extractor import CSVSource
from app.sources.json.extractor import JSONSource
from app.sources.excel.extractor import ExcelSource

logger = logging.getLogger(__name__)


class SourceNodeService:
    """Service for managing SourceNodes."""
    
    @staticmethod
    async def create_source_node(
        db: AsyncSession,
        source_data: SourceNodeCreate
    ) -> SourceNode:
        """Create a new SourceNode with auto-extraction for file-based sources.
        
        Args:
            db: Database session
            source_data: SourceNode creation data
            
        Returns:
            Created SourceNode
        """
        # Prepare content - auto-extract for file-based sources
        content = None
        lineage = None
        
        source_type = source_data.source_type
        config = source_data.config
        
        # Auto-extract for CSV, JSON, EXCEL
        if source_type in [SourceType.CSV, SourceType.JSON, SourceType.EXCEL]:
            content, lineage = await SourceNodeService._extract_file_content(
                db, source_type, config
            )
        
        # Create SourceNode with content
        source_node = SourceNode(
            board_id=source_data.board_id,
            source_type=source_data.source_type,
            config=source_data.config,
            metadata=source_data.metadata or {},
            position=source_data.position,
            created_by=source_data.created_by,
            content=content or {"text": None, "tables": []},
            lineage=lineage or {"operation": "extract", "source_node_id": None}
        )
        db.add(source_node)
        await db.commit()
        await db.refresh(source_node)
        
        logger.info(f"Created SourceNode {source_node.id} (type: {source_node.source_type}, has_content: {content is not None})")
        return source_node
    
    @staticmethod
    async def _extract_file_content(
        db: AsyncSession,
        source_type: SourceType,
        config: dict[str, Any]
    ) -> tuple[dict | None, dict | None]:
        """Extract content from file-based source.
        
        Returns:
            Tuple of (content, lineage) or (None, None) on failure
        """
        file_id = config.get("file_id")
        if not file_id:
            logger.warning("No file_id in config, skipping extraction")
            return None, None
        
        try:
            # Get file from storage
            storage = get_file_storage()
            file_data = await storage.get(file_id, db=db)
            
            if file_data is None:
                logger.error(f"File {file_id} not found in storage")
                return None, None
            
            # Get appropriate extractor
            extractor = None
            if source_type == SourceType.CSV:
                extractor = CSVSource()
            elif source_type == SourceType.JSON:
                extractor = JSONSource()
            elif source_type == SourceType.EXCEL:
                extractor = ExcelSource()
            
            if not extractor:
                return None, None
            
            # Extract data (без лимита по умолчанию — читаем все строки)
            result = await extractor.extract(config, file_content=file_data)
            
            if result.success:
                content = result.to_content()
                lineage = {
                    "operation": "extract",
                    "source_node_id": None,
                    "transformation_history": []
                }
                logger.info(f"Successfully extracted content from {source_type}: {len(content.get('tables', []))} tables")
                return content, lineage
            else:
                logger.error(f"Extraction failed: {result.errors}")
                return None, None
                
        except Exception as e:
            logger.exception(f"Error extracting file content: {e}")
            return None, None
    
    @staticmethod
    async def get_source_node(db: AsyncSession, source_id: UUID) -> SourceNode | None:
        """Get SourceNode by ID.
        
        Args:
            db: Database session
            source_id: SourceNode ID
            
        Returns:
            SourceNode or None if not found
        """
        result = await db.execute(
            select(SourceNode).where(SourceNode.id == source_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_board_sources(db: AsyncSession, board_id: UUID) -> list[SourceNode]:
        """Get all SourceNodes for a board.
        
        Args:
            db: Database session
            board_id: Board ID
            
        Returns:
            List of SourceNodes
        """
        result = await db.execute(
            select(SourceNode).where(SourceNode.board_id == board_id)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def update_source_node(
        db: AsyncSession,
        source_id: UUID,
        update_data: SourceNodeUpdate
    ) -> SourceNode | None:
        """Update SourceNode.
        
        Args:
            db: Database session
            source_id: SourceNode ID
            update_data: Update data
            
        Returns:
            Updated SourceNode or None if not found
        """
        source = await SourceNodeService.get_source_node(db, source_id)
        if not source:
            return None
        
        # Update fields
        if update_data.config is not None:
            source.config = update_data.config
        if update_data.metadata is not None:
            source.node_metadata = update_data.metadata
        if update_data.position is not None:
            source.position = update_data.position
        
        await db.commit()
        await db.refresh(source)
        
        logger.info(f"Updated SourceNode {source_id}")
        return source
    
    @staticmethod
    async def delete_source_node(db: AsyncSession, source_id: UUID) -> bool:
        """Delete SourceNode.
        
        Args:
            db: Database session
            source_id: SourceNode ID
            
        Returns:
            True if deleted, False if not found
        """
        source = await SourceNodeService.get_source_node(db, source_id)
        if not source:
            return False
        
        await db.delete(source)
        await db.commit()
        
        logger.info(f"Deleted SourceNode {source_id}")
        return True
    
    @staticmethod
    async def refresh_source_data(
        db: AsyncSession,
        source_id: UUID
    ) -> SourceNode | None:
        """Re-extract data from source and update SourceNode.
        
        This method refreshes the data by re-running extraction with the same config.
        
        Args:
            db: Database session
            source_id: SourceNode ID
            
        Returns:
            Updated SourceNode with fresh data or None if not found
            
        Raises:
            ValueError: If extraction fails or source not found
        """
        logger.info(f"🔄 Refreshing data for SourceNode {source_id}")
        
        source = await SourceNodeService.get_source_node(db, source_id)
        if not source:
            logger.error(f"❌ SourceNode {source_id} not found")
            raise ValueError("SourceNode not found")
        
        logger.info(f"📋 Source type: {source.source_type}, config keys: {list(source.config.keys())}")
        
        # Re-extract data based on source type
        content = None
        lineage = None
        error_message = None
        
        try:
            # For file-based sources (CSV, JSON, Excel)
            if source.source_type in [SourceType.CSV, SourceType.JSON, SourceType.EXCEL]:
                logger.info(f"📂 Extracting file-based source: {source.source_type}")
                content, lineage = await SourceNodeService._extract_file_content(
                    db, source.source_type, source.config
                )
                if content is None:
                    error_message = "File extraction returned no content"
            # For other types, use the generic extract_data
            else:
                logger.info(f"🔧 Using generic extraction for: {source.source_type}")
                extraction_result = await SourceNodeService.extract_data(db, source_id)
                if extraction_result["success"]:
                    content = extraction_result["content"]
                    lineage = {"operation": "refresh", "source_node_id": str(source_id)}
                else:
                    error_message = ", ".join(extraction_result.get("errors", ["Unknown error"]))
        except Exception as e:
            logger.exception(f"❌ Exception during refresh: {e}")
            error_message = str(e)
        
        if content is None:
            msg = f"Refresh failed: {error_message or 'unable to extract data'}"
            logger.error(f"❌ {msg}")
            raise ValueError(msg)
        
        # Update content and lineage
        source.content = content
        if lineage:
            source.lineage = lineage
        
        # Update metadata (создаём новый dict, т.к. SQLAlchemy JSONB не поддерживает item assignment)
        updated_metadata = dict(source.node_metadata) if source.node_metadata else {}
        updated_metadata["last_extracted"] = datetime.utcnow().isoformat()
        updated_metadata["extraction_status"] = "success"
        updated_metadata["error_message"] = None
        source.node_metadata = updated_metadata
        
        await db.commit()
        await db.refresh(source)
        
        logger.info(f"✅ SourceNode {source_id} refreshed successfully")
        return source
    
    @staticmethod
    async def validate_source(db: AsyncSession, source_id: UUID) -> dict[str, Any]:
        """Validate SourceNode configuration using extractors.
        
        Args:
            db: Database session
            source_id: SourceNode ID
            
        Returns:
            Validation result {valid: bool, errors: list[str]}
        """
        source = await SourceNodeService.get_source_node(db, source_id)
        if not source:
            return {"valid": False, "errors": ["SourceNode not found"]}
        
        # Get appropriate extractor
        extractor = SourceNodeService._get_extractor(source.source_type)
        if not extractor:
            return {"valid": False, "errors": [f"No extractor for type: {source.source_type}"]}
        
        # Validate config
        is_valid, errors = extractor.validate_config(source.config)
        
        return {
            "valid": is_valid,
            "errors": errors
        }
    
    @staticmethod
    def _get_extractor(source_type: SourceType):
        """Get extractor instance for source type."""
        extractors = {
            SourceType.FILE: FileExtractor(),
            SourceType.DATABASE: DatabaseExtractor(),
            SourceType.API: APIExtractor(),
            SourceType.PROMPT: PromptExtractor(),
            SourceType.STREAM: StreamExtractor(),
            SourceType.MANUAL: ManualExtractor(),
        }
        return extractors.get(source_type)
    
    @staticmethod
    async def extract_data(
        db: AsyncSession,
        source_id: UUID,
        params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Extract data from SourceNode.
        
        Args:
            db: Database session
            source_id: SourceNode ID
            params: Optional extraction parameters
            
        Returns:
            Dict with {success: bool, content: dict | None, errors: list[str]}
        """
        logger.info(f"🔄 Starting extraction for SourceNode {source_id}")
        source = await SourceNodeService.get_source_node(db, source_id)
        if not source:
            logger.error(f"❌ SourceNode {source_id} not found")
            return {
                "success": False,
                "content": None,
                "errors": ["SourceNode not found"]
            }
        
        # Get extractor
        extractor = SourceNodeService._get_extractor(source.source_type)
        if not extractor:
            logger.error(f"❌ No extractor for type: {source.source_type}")
            return {
                "success": False,
                "content": None,
                "errors": [f"No extractor for type: {source.source_type}"]
            }
        
        logger.info(f"✅ Using {source.source_type} extractor for source {source_id}")
        
        # Prepare extraction params
        extraction_params = params or {}
        extraction_params["db"] = db  # Pass db session for file storage access
        
        # Try Multi-Agent system for PROMPT extraction (with fallback to simple mode)
        if source.source_type == SourceType.PROMPT:
            try:
                from app.services.multi_agent.orchestrator import MultiAgentOrchestrator
                from app.services.multi_agent.message_bus import AgentMessageBus
                
                # Create and connect message bus
                message_bus = AgentMessageBus()
                await message_bus.connect()
                
                orchestrator = MultiAgentOrchestrator(db, message_bus)
                
                extraction_params["orchestrator"] = orchestrator
                extraction_params["source"] = source
                logger.info("✅ Multi-Agent system initialized for PROMPT extraction")
                
            except Exception as e:
                logger.warning(f"⚠️ Multi-Agent unavailable, using simple GigaChat: {e}")
                # Fallback to simple GigaChatService
                try:
                    from app.services.gigachat_service import get_gigachat_service
                    gigachat = get_gigachat_service()
                    if not gigachat:
                        raise ValueError("GigaChatService not initialized")
                    extraction_params["gigachat_service"] = gigachat
                    logger.info("✅ GigaChatService fallback for PROMPT extraction")
                except Exception as gigachat_error:
                    logger.error(f"Failed to get GigaChatService: {gigachat_error}")
                    return {
                        "success": False,
                        "content": None,
                        "errors": [f"AI services unavailable: {str(gigachat_error)}"]
                    }
        
        # Extract data
        try:
            result = await extractor.extract(source.config, extraction_params)
            
            if result.is_success:
                return {
                    "success": True,
                    "content": result.to_content_dict(),
                    "errors": []
                }
            else:
                return {
                    "success": False,
                    "content": None,
                    "errors": result.errors or ["Unknown error"]
                }
        
        except Exception as e:
            logger.exception(f"Extraction failed for SourceNode {source_id}: {e}")
            return {
                "success": False,
                "content": None,
                "errors": [f"Extraction error: {str(e)}"]
            }
