"""SourceNode service - business logic for managing data sources.

См. docs/SOURCE_CONTENT_NODE_CONCEPT.md для деталей.
"""
from typing import Any
from uuid import UUID
import logging
from datetime import datetime
import json

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
from app.sources import get_source_handler
from app.sources.csv.extractor import CSVSource
from app.sources.json.extractor import JSONSource
from app.sources.excel.extractor import ExcelSource
from app.sources.document.extractor import DocumentSource

logger = logging.getLogger(__name__)


class SourceNodeService:
    """Service for managing SourceNodes."""

    @staticmethod
    def _to_json_safe(value: Any) -> Any:
        """Convert arbitrary nested values to JSON-serializable representation."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, UUID):
            return str(value)

        if isinstance(value, dict):
            return {str(k): SourceNodeService._to_json_safe(v) for k, v in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [SourceNodeService._to_json_safe(v) for v in value]

        # numpy scalar support (e.g. np.int64/np.float64 from pandas)
        if hasattr(value, "item") and callable(getattr(value, "item", None)):
            try:
                return SourceNodeService._to_json_safe(value.item())
            except Exception:
                pass

        # pandas.Timestamp / date-like values usually support isoformat()
        if hasattr(value, "isoformat") and callable(getattr(value, "isoformat", None)):
            try:
                return value.isoformat()
            except Exception:
                pass

        try:
            json.dumps(value)
            return value
        except TypeError:
            return str(value)

    @staticmethod
    def _normalize_prefilled_content(data: dict[str, Any] | None) -> dict[str, Any]:
        """Normalize externally provided content payload to SourceNode content format."""
        if not isinstance(data, dict):
            return {"text": None, "tables": []}

        tables_in = data.get("tables") or []
        normalized_tables: list[dict[str, Any]] = []
        for idx, table in enumerate(tables_in):
            if not isinstance(table, dict):
                continue
            columns = table.get("columns") or []
            rows = table.get("rows") or []
            normalized_tables.append(
                {
                    "name": table.get("name") or f"table_{idx + 1}",
                    "columns": columns,
                    "rows": rows,
                    "row_count": table.get("row_count", len(rows)),
                    "column_count": table.get("column_count", len(columns)),
                }
            )

        # list[list] → list[dict] по именам колонок (LLM / document extraction)
        from app.services.controllers.document_extraction_controller import (
            DocumentExtractionController,
        )
        normalized_tables = DocumentExtractionController._normalize_table_rows_to_dicts(
            normalized_tables
        )
        normalized_tables = DocumentExtractionController._align_dict_rows_to_schema_columns(
            normalized_tables
        )

        return {
            "text": data.get("text"),
            "tables": normalized_tables,
        }

    @staticmethod
    async def _auto_detect_dimensions(
        db: AsyncSession,
        board_id: UUID,
        node_id: UUID,
        tables: list[dict[str, Any]],
    ) -> None:
        """Auto-detect dimensions from tables and upsert into project."""
        logger.info(
            f"📊 _auto_detect_dimensions called for SourceNode {node_id}, "
            f"board={board_id}, tables_count={len(tables)}"
        )
        if not tables:
            logger.info("📊 No tables provided, skipping dimension detection")
            return
        try:
            from app.services.dimension_service import DimensionService
            project_id = await DimensionService.get_project_id_for_node(db, board_id)
            logger.info(f"📊 Resolved project_id={project_id} for board {board_id}")
            if project_id:
                results = await DimensionService.auto_detect_and_upsert(
                    db, project_id, node_id, tables,
                )
                if results:
                    await db.commit()
                    logger.info(
                        f"📊 Auto-detected {len(results)} dimension(s) for SourceNode {node_id}: "
                        f"{[r['dimension'] for r in results]}"
                    )
                else:
                    logger.info(f"📊 No dimensions detected for SourceNode {node_id} (no suitable columns)")
            else:
                logger.warning(f"⚠️ Could not resolve project_id for board {board_id}")
        except Exception as e:
            logger.warning(f"⚠️ Dimension auto-detect failed for SourceNode {node_id}: {e}", exc_info=True)
    
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

        # If frontend already provided extracted content (e.g. AI document extraction),
        # persist this content as-is instead of re-running file heuristics.
        if source_data.data and (
            source_data.data.get("text") is not None
            or (source_data.data.get("tables") and len(source_data.data.get("tables", [])) > 0)
        ):
            content = SourceNodeService._normalize_prefilled_content(source_data.data)
            lineage = {
                "operation": "extract",
                "source_node_id": None,
                "transformation_history": [],
                "source": "prefilled_dialog_data",
            }
            logger.info(
                f"Using prefilled content for SourceNode create: "
                f"type={source_type}, tables={len(content.get('tables', []))}"
            )
        
        # Auto-extract for CSV, JSON, EXCEL, DOCUMENT
        elif source_type in [SourceType.CSV, SourceType.JSON, SourceType.EXCEL, SourceType.DOCUMENT]:
            content, lineage = await SourceNodeService._extract_file_content(
                db, source_type, config
            )
        
        # Auto-extract for MANUAL source — config already contains table data
        elif source_type == SourceType.MANUAL:
            content, lineage = await SourceNodeService._extract_manual_content(config)

        # RESEARCH: используем переданный data (результат из диалога) или запускаем извлечение
        elif source_type == SourceType.RESEARCH:
            if source_data.data and (
                source_data.data.get("text") is not None
                or (source_data.data.get("tables") and len(source_data.data.get("tables", [])) > 0)
            ):
                content = source_data.data
                lineage = {
                    "operation": "extract",
                    "source_node_id": None,
                    "transformation_history": [],
                }
                logger.info(
                    f"Research source created with pre-filled content: "
                    f"{len(content.get('tables', []))} tables"
                )
            else:
                content, lineage, research_err = await SourceNodeService._extract_research_content(config)
                if research_err:
                    logger.warning(
                        "Research extraction at create returned no content: %s", research_err
                    )
        
        # Create SourceNode with content
        # Note: используем node_metadata (Python attr), а не metadata (зарезервировано SQLAlchemy)
        incoming_metadata = source_data.metadata or {}
        logger.info(f"📝 SourceNode creation - incoming metadata: {incoming_metadata}")
        logger.info(f"📝 SourceNode creation - incoming metadata.name: '{incoming_metadata.get('name', '<NOT SET>>')}'")
        
        safe_content = SourceNodeService._to_json_safe(content or {"text": None, "tables": []})
        safe_lineage = SourceNodeService._to_json_safe(
            lineage or {"operation": "extract", "source_node_id": None}
        )

        source_node = SourceNode(
            board_id=source_data.board_id,
            source_type=source_data.source_type,
            config=source_data.config,
            node_metadata=incoming_metadata,
            position=source_data.position,
            created_by=source_data.created_by,
            content=safe_content,
            lineage=safe_lineage,
        )
        db.add(source_node)
        await db.commit()
        await db.refresh(source_node)
        
        logger.info(f"✅ Created SourceNode {source_node.id} (type: {source_node.source_type}, has_content: {content is not None})")
        logger.info(f"✅ SourceNode {source_node.id} node_metadata after save: {source_node.node_metadata}")
        logger.info(f"✅ SourceNode {source_node.id} node_metadata.name: '{source_node.node_metadata.get('name', '<NOT SET>>') if source_node.node_metadata else '<NONE>>'}'")

        # Auto-detect dimensions from tables
        tables_for_detect = (content or {}).get("tables", [])
        logger.info(
            f"🔍 [DIM] SourceNode {source_node.id}: about to call _auto_detect_dimensions, "
            f"content is None={content is None}, "
            f"tables_count={len(tables_for_detect)}, "
            f"table_names={[t.get('name','?') for t in tables_for_detect]}, "
            f"table_col_counts={[len(t.get('columns',[])) for t in tables_for_detect]}, "
            f"table_row_counts={[len(t.get('rows',[])) for t in tables_for_detect]}"
        )
        for tidx, tbl in enumerate(tables_for_detect):
            cols = tbl.get('columns', [])
            rows = tbl.get('rows', [])
            logger.info(
                f"🔍 [DIM] SourceNode table[{tidx}]='{tbl.get('name','')}': "
                f"columns={[c.get('name','?')+':'+c.get('type','?') for c in cols]}, "
                f"rows_sample_keys={list(rows[0].keys()) if rows else '[]'}"
            )
        await SourceNodeService._auto_detect_dimensions(
            db, source_node.board_id, source_node.id, tables_for_detect,
        )

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
            elif source_type == SourceType.DOCUMENT:
                extractor = DocumentSource()
            
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
    async def _extract_manual_content(
        config: dict[str, Any]
    ) -> tuple[dict | None, dict | None]:
        """Extract content from manual source config.
        
        Supports two config formats:
        1. New format: config.tables = [{name, columns, rows}, ...]
        2. Legacy format: config.columns = [...], config.data = [...]
        
        Returns:
            Tuple of (content, lineage) or (None, None) on failure
        """
        try:
            from app.sources.manual.extractor import ManualSource
            
            extractor = ManualSource()
            
            # Normalize config: legacy format → new format
            normalized_config = config
            if "tables" not in config and "columns" in config:
                # Legacy format: {columns: [...], data: [...]}
                columns = config.get("columns", [])
                data = config.get("data", [])
                table_name = config.get("table_name", "table_1")
                
                # Convert row dicts to list format if needed
                rows = []
                for row in data:
                    if isinstance(row, dict):
                        rows.append(row)
                    else:
                        rows.append(row)
                
                normalized_config = {
                    "tables": [{
                        "name": table_name,
                        "columns": columns,
                        "rows": rows,
                    }]
                }
            
            result = await extractor.extract(normalized_config)
            
            if result.success:
                content = result.to_content()
                lineage = {
                    "operation": "manual_input",
                    "source_node_id": None,
                    "transformation_history": []
                }
                logger.info(f"Successfully extracted manual content: {len(content.get('tables', []))} tables")
                return content, lineage
            else:
                logger.error(f"Manual extraction failed: {result.error}")
                return None, None
                
        except Exception as e:
            logger.exception(f"Error extracting manual content: {e}")
            return None, None

    @staticmethod
    async def _extract_research_content(
        config: dict[str, Any],
    ) -> tuple[dict | None, dict | None, str | None]:
        """Extract content for RESEARCH source via ResearchSource + Orchestrator.

        Returns `(content, lineage, error_message)`; `error_message` is set on failure.
        """
        try:
            from app.main import get_orchestrator

            orchestrator = get_orchestrator()
            if not orchestrator:
                msg = "Мультиагент оркестратор недоступен (проверьте запуск backend)"
                logger.warning(msg)
                return None, None, msg

            handler = get_source_handler("research")
            result = await handler.extract(config, orchestrator=orchestrator)

            if not result.success:
                err = result.error or "Ошибка извлечения research"
                logger.error(f"Research extraction failed: {err}")
                return None, None, err

            content = result.to_content()
            lineage = {
                "operation": "extract",
                "source_node_id": None,
                "transformation_history": [],
            }
            logger.info(
                f"Successfully extracted research content: "
                f"{len(content.get('tables', []))} tables"
            )
            return content, lineage, None
        except Exception as e:
            logger.exception(f"Error extracting research content: {e}")
            return None, None, str(e)

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
            
            # For manual sources, re-extract content from updated config
            if source.source_type == SourceType.MANUAL:
                content, lineage = await SourceNodeService._extract_manual_content(update_data.config)
                if content:
                    source.content = SourceNodeService._to_json_safe(content)
                    if lineage:
                        source.lineage = SourceNodeService._to_json_safe(lineage)
            # For JSON sources, re-extract content so edited mapping_spec is applied immediately
            elif source.source_type == SourceType.JSON:
                content, lineage = await SourceNodeService._extract_file_content(
                    db,
                    SourceType.JSON,
                    source.config,
                )
                # JSON extractor may enrich config (schema_snapshot, mapping_spec, generation_meta)
                source.config = dict(source.config or {})
                if content:
                    source.content = SourceNodeService._to_json_safe(content)
                    if lineage:
                        source.lineage = SourceNodeService._to_json_safe(lineage)
        
        if update_data.metadata is not None:
            source.node_metadata = update_data.metadata
        if update_data.position is not None:
            source.position = update_data.position

        # Документ: сохранение текста/таблиц из диалога (как при create с prefilled data)
        if (
            update_data.data is not None
            and source.source_type == SourceType.DOCUMENT
        ):
            content = SourceNodeService._normalize_prefilled_content(update_data.data)
            source.content = SourceNodeService._to_json_safe(content)
            lineage = {
                "operation": "extract",
                "source_node_id": str(source.id),
                "transformation_history": [],
                "source": "prefilled_dialog_data_update",
            }
            source.lineage = SourceNodeService._to_json_safe(lineage)
            logger.info(
                f"Updated DOCUMENT SourceNode {source_id} content from dialog: "
                f"{len(content.get('tables', []))} tables"
            )
        
        await db.commit()
        await db.refresh(source)
        
        logger.info(f"Updated SourceNode {source_id}")

        # Auto-detect dimensions if content was re-extracted (manual/json sources)
        if update_data.config is not None and source.source_type in (SourceType.MANUAL, SourceType.JSON):
            tables = (source.content or {}).get("tables", [])
            logger.info(
                f"🔍 [DIM] SourceNode {source_id} update ({source.source_type}): "
                f"tables_count={len(tables)}"
            )
            if tables:
                await SourceNodeService._auto_detect_dimensions(
                    db, source.board_id, source.id, tables,
                )

        if update_data.data is not None and source.source_type == SourceType.DOCUMENT:
            tables = (source.content or {}).get("tables", [])
            if tables:
                await SourceNodeService._auto_detect_dimensions(
                    db, source.board_id, source.id, tables,
                )

        return source
    
    @staticmethod
    async def delete_source_node(db: AsyncSession, source_id: UUID) -> bool:
        """Delete SourceNode and clean up linked dimensions.

        After deletion:
        - DimensionColumnMapping rows cascade-delete via FK (ondelete=CASCADE on node_id).
        - Dimensions that have no remaining mappings are removed as orphans.
        """
        source = await SourceNodeService.get_source_node(db, source_id)
        if not source:
            return False

        # Capture board_id before deletion (needed to resolve project_id afterwards)
        board_id = source.board_id

        await db.delete(source)
        await db.commit()

        logger.info(f"Deleted SourceNode {source_id}")

        # Clean up orphaned Dimensions (mappings already cascade-deleted by PG)
        try:
            from app.services.dimension_service import DimensionService
            project_id = await DimensionService.get_project_id_for_node(db, board_id)
            if project_id:
                deleted_count = await DimensionService.cleanup_orphaned_dimensions(db, project_id)
                if deleted_count:
                    await db.commit()
        except Exception as exc:
            logger.warning(f"cleanup_orphaned_dimensions failed for SourceNode {source_id}: {exc}")

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
            # For file-based sources (CSV, JSON, Excel, Document)
            if source.source_type in [SourceType.CSV, SourceType.JSON, SourceType.EXCEL, SourceType.DOCUMENT]:
                logger.info(f"📂 Extracting file-based source: {source.source_type}")
                content, lineage = await SourceNodeService._extract_file_content(
                    db, source.source_type, source.config
                )
                # JSON extractor may enrich config (schema_snapshot, mapping_spec).
                # Reassign to mark JSONB field as dirty for SQLAlchemy.
                source.config = dict(source.config or {})
                if content is None:
                    error_message = "File extraction returned no content"
            # For manual sources, re-extract from config
            elif source.source_type == SourceType.MANUAL:
                logger.info(f"✏️ Re-extracting manual source from config")
                content, lineage = await SourceNodeService._extract_manual_content(source.config)
                if content is None:
                    error_message = "Manual extraction returned no content"
            elif source.source_type == SourceType.RESEARCH:
                logger.info("🔬 Re-extracting research source (Поиск с ИИ)")
                content, lineage, research_err = await SourceNodeService._extract_research_content(
                    source.config
                )
                if content is None:
                    error_message = research_err or "Не удалось выполнить поиск с ИИ"
                else:
                    lineage = {"operation": "refresh", "source_node_id": str(source_id)}
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
        source.content = SourceNodeService._to_json_safe(content)
        if lineage:
            source.lineage = SourceNodeService._to_json_safe(lineage)
        
        # Update metadata (создаём новый dict, т.к. SQLAlchemy JSONB не поддерживает item assignment)
        updated_metadata = dict(source.node_metadata) if source.node_metadata else {}
        updated_metadata["last_extracted"] = datetime.utcnow().isoformat()
        updated_metadata["extraction_status"] = "success"
        updated_metadata["error_message"] = None
        source.node_metadata = updated_metadata
        
        await db.commit()
        await db.refresh(source)
        
        logger.info(f"✅ SourceNode {source_id} refreshed successfully")

        # Auto-detect dimensions from refreshed tables
        refresh_tables = (content or {}).get("tables", [])
        logger.info(
            f"🔍 [DIM] SourceNode {source_id} refresh: "
            f"tables_count={len(refresh_tables)}, "
            f"table_names={[t.get('name','?') for t in refresh_tables]}"
        )
        await SourceNodeService._auto_detect_dimensions(
            db, source.board_id, source.id, refresh_tables,
        )

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
        if source_type == SourceType.RESEARCH:
            return get_source_handler("research")
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
        
        # Orchestrator for RESEARCH extraction
        if source.source_type == SourceType.RESEARCH:
            try:
                from app.main import get_orchestrator
                orchestrator = get_orchestrator()
                if orchestrator:
                    extraction_params["orchestrator"] = orchestrator
                    logger.info("Orchestrator available for RESEARCH extraction")
                else:
                    raise RuntimeError("Orchestrator not initialized")
            except Exception as e:
                logger.warning(f"Orchestrator unavailable for RESEARCH: {e}")
                return {
                    "success": False,
                    "content": None,
                    "errors": [f"AI services unavailable: {str(e)}"],
                }

        # Try Orchestrator V2 for PROMPT extraction (with fallback to simple mode)
        if source.source_type == SourceType.PROMPT:
            try:
                from app.main import get_orchestrator

                orchestrator = get_orchestrator()
                if orchestrator:
                    extraction_params["orchestrator"] = orchestrator
                    extraction_params["source"] = source
                    logger.info("Orchestrator V2 available for PROMPT extraction")
                else:
                    raise RuntimeError("Orchestrator not initialized")

            except Exception as e:
                logger.warning(f"Orchestrator unavailable, using simple GigaChat: {e}")
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
            if source.source_type == SourceType.RESEARCH:
                result = await extractor.extract(source.config, **extraction_params)
            else:
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
