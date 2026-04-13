"""ContentNode API routes.

См. docs/API.md для полной документации endpoints.
"""
from datetime import date, datetime
from typing import Any
from uuid import UUID
import uuid
import logging
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.middleware import get_current_user, get_current_user_with_token
from app.services.content_node_service import ContentNodeService
from app.services.board_service import BoardService
from app.services.executors.python_executor import python_executor
from app.services.edge_service import EdgeService
from app.services.filter_engine import FilterEngine
from app.services.dimension_service import DimensionService
from app.services.controllers import (
    TransformationController,
    TransformSuggestionsController,
    WidgetController,
    WidgetSuggestionsController,
)
from app.utils.node_positioning import find_optimal_node_position, NodeBounds
from app.schemas.content_node import (
    ContentNodeCreate,
    ContentNodeUpdate,
    ContentNodeResponse,
    TransformRequest,
    TransformResponse,
    GetTableRequest,
    GetTableResponse,
    VisualizeRequest,
    VisualizeResponse,
    VisualizeIterativeRequest,
    VisualizeIterativeResponse
)
from app.schemas.widget_suggestions import (
    SuggestionAnalysisRequest,
    SuggestionAnalysisResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/content-nodes", tags=["content-nodes"])


# ══════════════════════════════════════════════════════════════════════
#  Serialization helpers
# ══════════════════════════════════════════════════════════════════════


def _serialize_content_node(node) -> dict:
    """Serialize ContentNode/SourceNode SQLAlchemy model to dict with correct field names.
    
    Without this, node_metadata is serialized as 'node_metadata' instead of 'metadata',
    because transform routes return raw dicts without response_model.
    ContentNodeResponse applies validation_alias='node_metadata' → serialization_alias='metadata'.
    """
    return ContentNodeResponse.model_validate(node).model_dump(by_alias=True)


def _serialize_edge(edge) -> dict | None:
    """Serialize Edge SQLAlchemy model to dict."""
    if edge is None:
        return None
    from app.schemas.edge import EdgeResponse
    return EdgeResponse.model_validate(edge).model_dump(by_alias=True)


def _ndjson_default(obj: Any) -> Any:
    """Fallback for NDJSON streams: pandas Period/Timestamp, numpy scalars, etc."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    try:
        import numpy as np

        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except Exception:
        pass
    try:
        import pandas as pd

        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.Period):
            return str(obj)
        if isinstance(obj, pd.Timedelta):
            return str(obj)
    except Exception:
        pass
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            pass
    return str(obj)


# ══════════════════════════════════════════════════════════════════════
#  Helper functions for V2 controller integration
# ══════════════════════════════════════════════════════════════════════


def _get_orchestrator_or_503():
    """Get Orchestrator V2 or raise 503."""
    from app.main import get_orchestrator
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized. Check backend logs for Redis/GigaChat connection issues."
        )
    return orch


async def _require_content_view(
    db: AsyncSession, content_id: UUID, user_id: UUID
):
    """Доступ к узлу только при праве просмотра проекта/доски."""
    node = await ContentNodeService.get_content_node(db, content_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ContentNode not found",
        )
    await BoardService.get_board(db, node.board_id, user_id)
    return node


async def _require_content_edit(
    db: AsyncSession, content_id: UUID, user_id: UUID
):
    """Изменение узла и тяжёлые операции — только не viewer."""
    node = await ContentNodeService.get_content_node(db, content_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ContentNode not found",
        )
    await BoardService.get_board_for_edit(db, node.board_id, user_id)
    return node


async def _collect_content_nodes_data(
    db: AsyncSession,
    primary_content_id: UUID,
    selected_node_ids: list[str] | None,
    user_id: UUID,
) -> tuple[list[dict], dict, str, str]:
    """
    Collect data from ContentNodes for controller processing.

    Consolidates duplicated node-loading logic from multiple route handlers.

    Returns:
        (nodes_data, input_data, text_content, board_id)
        - nodes_data: list of node dicts {node_id, node_name, text, tables}
        - input_data: dict name→DataFrame for PythonExecutor
        - text_content: concatenated text from all nodes
        - board_id: UUID string of the board
    """
    if selected_node_ids is None:
        selected_node_ids = [str(primary_content_id)]

    # Get board_id from primary node
    primary_node = await ContentNodeService.get_content_node(db, primary_content_id)
    if not primary_node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ContentNode {primary_content_id} not found"
        )
    await BoardService.get_board_for_edit(db, primary_node.board_id, user_id)
    board_id = str(primary_node.board_id)

    nodes_data: list[dict] = []
    input_data: dict = {}
    text_content = ""

    for nid_str in selected_node_ids:
        try:
            nid = UUID(nid_str) if isinstance(nid_str, str) else nid_str
        except ValueError:
            logger.warning(f"Invalid UUID format: {nid_str}")
            continue

        # Reuse primary_node if same ID
        if nid == primary_content_id:
            node = primary_node
        else:
            node = await ContentNodeService.get_content_node(db, nid)

        if not node:
            continue
        if node.board_id != primary_node.board_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Все выбранные узлы должны принадлежать одной доске",
            )
        if not node.content:
            continue

        if "text" in node.content and node.content["text"]:
            text_content += node.content["text"] + "\n\n"

        nd: dict = {
            "node_id": str(node.id),
            "node_name": (
                node.node_metadata.get("name", f"Node {node.id}")
                if node.node_metadata else f"Node {node.id}"
            ),
            "text": node.content.get("text", ""),
            "tables": [],
        }

        for table in node.content.get("tables", []):
            nd["tables"].append({
                "name": table.get("name", "table"),
                "columns": table.get("columns", []),
                "column_types": table.get("column_types", {}),
                "rows": table.get("rows", [])[:10],
                "row_count": table.get("row_count", len(table.get("rows", []))),
            })
            try:
                df = python_executor.table_dict_to_dataframe(table)
                input_data[table["name"]] = df
            except Exception as e:
                logger.warning(f"Failed to convert table to DataFrame: {e}")

        nodes_data.append(nd)

    # Text-only fallback
    if not input_data and text_content.strip():
        input_data["text"] = text_content.strip()
        logger.info(f"📝 Text-only mode: {len(text_content)} characters")

    if not nodes_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid ContentNodes found"
        )

    return nodes_data, input_data, text_content, board_id


# ══════════════════════════════════════════════════════════════════════
#  CRUD Routes
# ══════════════════════════════════════════════════════════════════════


# Пустой path — маршрут без завершающего «/», совпадает с axios `/api/v1/content-nodes`.
# `@router.post("/")` даёт только `/api/v1/content-nodes/`; при redirect_slashes=False POST без слэша → 404.
@router.post("", response_model=ContentNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_content_node(
    content_data: ContentNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new ContentNode.
    
    Contains processed data (text + tables) with full data lineage tracking.
    """
    try:
        await BoardService.get_board_for_edit(db, content_data.board_id, current_user.id)
        content_node = await ContentNodeService.create_content_node(db, content_data)
        await db.commit()
        await db.refresh(content_node)
        return content_node
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create ContentNode: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{content_id}", response_model=ContentNodeResponse)
async def get_content_node(
    content_id: UUID,
    filters: str | None = Query(None, description="URL-encoded FilterExpression JSON for cross-filtering"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get ContentNode by ID.

    Supports optional cross-filtering via `?filters=<encoded JSON>`.
    See docs/CROSS_FILTER_SYSTEM.md
    """
    content_node = await _require_content_view(db, content_id, current_user.id)

    # Apply cross-filters if provided
    if filters and content_node.content and content_node.content.get("tables"):
        import json as _json
        from urllib.parse import unquote
        try:
            decoded = unquote(filters)
            filter_expr = _json.loads(decoded)
            mappings = await DimensionService.get_mappings_for_node(db, content_id)
            logger.info(
                "get_content_node %s: filters applied, mappings=%d",
                content_id, len(mappings),
            )
            if not mappings:
                logger.info(
                    "get_content_node %s: no mappings, running auto-detect",
                    content_id,
                )
                project_id = await DimensionService.get_project_id_for_node(
                    db, content_node.board_id,
                )
                if project_id:
                    await DimensionService.auto_detect_and_upsert(
                        db, project_id, content_id,
                        content_node.content["tables"],
                    )
                    await db.flush()
                    mappings = await DimensionService.get_mappings_for_node(db, content_id)
            if mappings:
                orig_tables = content_node.content["tables"]
                filtered_tables = FilterEngine.apply_filters(
                    orig_tables,
                    filter_expr,
                    mappings,
                )
                for i, (ot, ft) in enumerate(zip(orig_tables, filtered_tables)):
                    logger.info(
                        "get_content_node %s: table[%d] '%s' rows %d→%d",
                        content_id, i, ot.get("name", "?"),
                        ot.get("row_count", len(ot.get("rows", []))),
                        ft.get("row_count", len(ft.get("rows", []))),
                    )
                from copy import deepcopy
                node_dict = _serialize_content_node(content_node)
                node_dict["content"]["tables"] = filtered_tables
                return node_dict
            else:
                logger.warning(
                    "get_content_node %s: no dimension mappings even after auto-detect — filter skipped",
                    content_id,
                )
        except Exception as e:
            logger.warning("Failed to apply cross-filters: %s", e)
            # Fall through to return unfiltered data

    return content_node


@router.get("/board/{board_id}", response_model=list[ContentNodeResponse])
async def get_board_contents(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all ContentNodes for a board."""
    await BoardService.get_board(db, board_id, current_user.id)
    contents = await ContentNodeService.get_board_contents(db, board_id)
    return contents


@router.put("/{content_id}", response_model=ContentNodeResponse)
async def update_content_node(
    content_id: UUID,
    update_data: ContentNodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update ContentNode data or metadata."""
    await _require_content_edit(db, content_id, current_user.id)
    content_node = await ContentNodeService.update_content_node(db, content_id, update_data)
    if not content_node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ContentNode not found")
    return content_node


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content_node(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete ContentNode."""
    await _require_content_edit(db, content_id, current_user.id)
    deleted = await ContentNodeService.delete_content_node(db, content_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ContentNode not found")


@router.post("/{content_id}/transform/preview")
async def preview_transformation(
    content_id: UUID,
    params: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate transformation code using Orchestrator V2 (no execution).

    Returns code for preview/edit before execution.

    Request body:
    {
        "prompt": str,
        "selected_node_ids": [UUID, ...]  # Optional, defaults to [content_id]
    }
    """
    prompt = params.get("prompt")
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prompt is required")

    selected_node_ids = params.get("selected_node_ids", [str(content_id)])
    if isinstance(selected_node_ids, str):
        selected_node_ids = [selected_node_ids]
    
    existing_code = params.get("existing_code")
    chat_history = params.get("chat_history", [])

    try:
        nodes_data, _input_data, text_content, board_id = await _collect_content_nodes_data(
            db, content_id, selected_node_ids, current_user.id
        )

        # V2 controller — preview only (no execution)
        orchestrator = _get_orchestrator_or_503()
        controller = TransformationController(orchestrator)

        result = await controller.process_request(
            user_message=prompt,
            context={
                "board_id": board_id,
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "input_tables": [t for nd in nodes_data for t in nd.get("tables", [])],
                "text_content": text_content,
                "existing_code": existing_code,
                "chat_history": chat_history,
                "selected_node_ids": selected_node_ids,
                "skip_execution": True,
            },
        )

        if result.status != "success":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Code generation failed"
            )

        return {
            "transformation_id": str(uuid.uuid4()),
            "code": result.code,
            "description": result.code_description,
            "validation": result.validation,
            "agent_plan": result.plan,
            "analysis": None,
            "source_node_ids": selected_node_ids,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview transformation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation failed: {str(e)}"
        )


@router.post("/{content_id}/transform/test")
async def test_transformation(
    content_id: UUID,
    params: dict,
    db: AsyncSession = Depends(get_db),
    user_and_token: tuple[User, str] = Depends(get_current_user_with_token)
):
    """
    Test transformation code execution and return results WITHOUT creating ContentNode.
    
    This allows users to preview transformation results before committing.
    
    Request body:
    {
        "code": str,
        "transformation_id": str,
        "selected_node_ids": [UUID, ...]  // Optional
    }
    
    Returns:
    {
        "success": bool,
        "tables": [...],  // Result tables with data
        "execution_time_ms": int,
        "row_counts": {"table1": 100, ...}
    }
    """
    current_user, auth_token = user_and_token

    code = params.get("code")
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="code is required")
    
    selected_node_ids = params.get("selected_node_ids", [str(content_id)])
    if isinstance(selected_node_ids, str):
        selected_node_ids = [selected_node_ids]

    primary_cn = await ContentNodeService.get_content_node(db, content_id)
    if not primary_cn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ContentNode not found",
        )
    await BoardService.get_board_for_edit(db, primary_cn.board_id, current_user.id)

    try:
        # Collect input data from all selected nodes
        input_data = {}
        text_content = ""  # For text-only ContentNodes

        from app.services.source_node_service import SourceNodeService

        for node_id_str in selected_node_ids:
            try:
                node_id = UUID(node_id_str) if isinstance(node_id_str, str) else node_id_str
            except ValueError:
                continue

            node = await ContentNodeService.get_content_node(db, node_id)
            node_content = None
            if node:
                if node.board_id != primary_cn.board_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Все выбранные узлы должны принадлежать одной доске",
                    )
                node_content = node.content
            else:
                source_node = await SourceNodeService.get_source_node(db, node_id)
                if source_node:
                    if source_node.board_id != primary_cn.board_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Все выбранные узлы должны принадлежать одной доске",
                        )
                    node_content = source_node.content
                    if node_content:
                        logger.info(f"📦 Using SourceNode fallback for {node_id} in test")

            if node_content:
                # Collect text content
                if "text" in node_content and node_content["text"]:
                    text_content += node_content["text"] + "\n\n"
                
                # Collect tables
                if "tables" in node_content:
                    for table in node_content["tables"]:
                        df = python_executor.table_dict_to_dataframe(table)
                        input_data[table["name"]] = df
        
        # If no tables but we have text, add it as 'text' variable
        if not input_data and text_content.strip():
            input_data["text"] = text_content.strip()
            logger.info(f"📝 Using text-only mode: {len(text_content)} characters")
        elif not input_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No input tables found")
        
        # Execute transformation code with auth token for gb helpers
        import time
        start_time = time.time()
        
        execution_result = await python_executor.execute_transformation(
            code=code,
            input_data=input_data,
            user_id=str(current_user.id),
        )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        if not execution_result.success:
            return {
                "success": False,
                "error": execution_result.error,
                "execution_time_ms": execution_time_ms
            }
        
        # Convert result DataFrames to table format with AI-generated names (limit rows for preview)
        result_tables = []
        row_counts = {}
        
        for var_name, df in execution_result.result_dfs.items():
            if hasattr(df, 'to_dict'):  # Is DataFrame
                row_count = len(df)
                row_counts[var_name] = row_count
                
                # Limit to first 100 rows for preview
                preview_df = df.head(100)
                
                # var_name now contains meaningful name from generated code (e.g., sales_by_brand)
                logger.info(f"📝 Using table name from code: '{var_name}'")
                
                table_dict = python_executor.dataframe_to_table_dict(
                    df=preview_df,
                    table_name=var_name  # Use name from generated code
                )
                table_dict["row_count"] = row_count  # Total count
                table_dict["preview_row_count"] = len(preview_df)  # Preview count
                
                result_tables.append(table_dict)
        
        return {
            "success": True,
            "tables": result_tables,
            "execution_time_ms": execution_time_ms,
            "row_counts": row_counts
        }
        
    except Exception as e:
        logger.error(f"Test transformation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/{content_id}/transform/iterative")
async def iterative_transformation(
    content_id: UUID,
    params: dict,
    db: AsyncSession = Depends(get_db),
    user_and_token: tuple[User, str] = Depends(get_current_user_with_token)
):
    """Iterative transformation generation with AI chat via V2 controller.

    Generates new transformation or improves existing one based on chat history.
    Automatically executes and returns preview data.

    Request body:
    {
        "user_prompt": str,
        "existing_code": str | null,
        "transformation_id": str | null,
        "chat_history": [{"role": str, "content": str}, ...],
        "selected_node_ids": [UUID, ...],
        "preview_only": bool = True
    }
    """
    current_user, auth_token = user_and_token

    user_prompt = params.get("user_prompt")
    if not user_prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_prompt is required")

    existing_code = params.get("existing_code")
    chat_history = params.get("chat_history", [])
    selected_node_ids = params.get("selected_node_ids", [str(content_id)])
    if isinstance(selected_node_ids, str):
        selected_node_ids = [selected_node_ids]

    try:
        nodes_data, input_data, text_content, board_id = await _collect_content_nodes_data(
            db, content_id, selected_node_ids, current_user.id
        )

        # V2 controller — generates + executes
        orchestrator = _get_orchestrator_or_503()
        controller = TransformationController(orchestrator)

        result = await controller.process_request(
            user_message=user_prompt,
            context={
                "board_id": board_id,
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "auth_token": auth_token,
                "input_tables": [t for nd in nodes_data for t in nd.get("tables", [])],
                "input_data": input_data,  # Full DataFrames for execution
                "text_content": text_content,
                "existing_code": existing_code,
                "chat_history": chat_history,
                "selected_node_ids": selected_node_ids,
            },
        )

        if result.status != "success":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Transformation failed"
            )

        return {
            "transformation_id": str(uuid.uuid4()),
            "code": result.code,
            "description": result.code_description,
            "preview_data": result.preview_data,
            "validation": result.validation,
            "agent_plan": result.plan,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Iterative transformation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transformation failed: {str(e)}"
        )


async def _generate_content_metadata(
    source_nodes: list,
    user_prompt: str,
    transformation_code: str,
    result_tables: list[dict],
    execution_time_ms: float
) -> dict:
    """
    Generate AI-powered name and description for ContentNode.
    
    Args:
        source_nodes: List of source ContentNodes/SourceNodes
        user_prompt: User's transformation request
        transformation_code: Python code that was executed
        result_tables: List of result tables with data
        execution_time_ms: Execution time in milliseconds
        
    Returns:
        dict with 'name' and 'description' keys
    """
    logger.info(f"🤖 Starting AI metadata generation for transformation")
    logger.info(f"🤖 _generate_content_metadata called with: user_prompt='{user_prompt[:100] if user_prompt else None}', result_tables={[t.get('name') for t in (result_tables or [])]}")
    
    try:
        from app.services.gigachat_service import get_gigachat_service
        
        gigachat = get_gigachat_service()
        
        logger.info(f"🤖 GigaChat service obtained: {gigachat is not None}")
        
        # Build summary of source data
        source_summary = []
        for idx, node in enumerate(source_nodes):
            if hasattr(node, 'content') and node.content:
                tables = node.content.get("tables", [])
                source_summary.append(f"Source {idx + 1}: {len(tables)} tables")
                for table in tables[:2]:  # Max 2 tables per source
                    source_summary.append(f"  - {table['name']}: {table.get('row_count', 0)} rows")
        
        # Build summary of result data
        result_summary = []
        for table in result_tables[:3]:  # Max 3 result tables
            raw_cols = table.get('columns', [])[:5]
            # columns can be list of dicts [{name, type}] or list of strings
            if raw_cols and isinstance(raw_cols[0], dict):
                cols = ", ".join(c.get("name", str(c)) for c in raw_cols)
            else:
                cols = ", ".join(str(c) for c in raw_cols)
            result_summary.append(f"  - {table['name']}: {table.get('row_count', 0)} rows ({cols}...)")
        
        logger.info(f"🤖 source_summary: {source_summary}")
        logger.info(f"🤖 result_summary: {result_summary}")
        
        # Create prompt for AI
        prompt = f"""На основе следующей информации о data transformation сгенерируй краткое название (3-5 слов) и описание (1-2 предложения).

Запрос пользователя: {user_prompt}

Исходные данные:
{chr(10).join(source_summary)}

Результат:
{chr(10).join(result_summary)}

Время выполнения: {execution_time_ms:.0f}ms

Верни JSON в формате:
{{
  "name": "Краткое название результата",
  "description": "Краткое описание: что было сделано и какой получен результат"
}}

ВАЖНО: 
- Название и описание должны быть СТРОГО на русском языке, даже если исходные данные содержат английские термины или данные на других языках
- Название должно быть информативным и отражать суть трансформации, без слова "Transformed"
- Используй русские термины для технических понятий (например: "фильтрация", "группировка", "агрегация", "объединение")"""
        
        logger.info(f"🤖 Sending prompt to GigaChat ({len(prompt)} chars)")
        
        response = await gigachat.chat_completion([{"role": "user", "content": prompt}])
        
        logger.info(f"📝 AI metadata generation response ({len(response) if response else 0} chars): {response[:500] if response else 'EMPTY'}")
        
        # Parse JSON from response
        import json
        import re
        
        # Try to extract JSON from response — support any key order
        # First attempt: standard json.loads on first {...} block
        brace_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if brace_match:
            try:
                metadata = json.loads(brace_match.group())
                if metadata.get("name") or metadata.get("description"):
                    name = metadata.get("name", "")[:100]
                    description = metadata.get("description", "")[:500]
                    
                    logger.info(f"✅ Parsed AI metadata (json.loads) - name: '{name}', description: '{description[:100]}...'")
                    
                    return {
                        "name": name,
                        "description": description
                    }
            except json.JSONDecodeError:
                pass

        # Second attempt: regex for JSON with "name" and "description" (any order)
        json_match = re.search(
            r'\{[^{}]*(?:"name"|"description")[^{}]*(?:"name"|"description")[^{}]*\}',
            response, re.DOTALL,
        )
        if json_match:
            try:
                metadata = json.loads(json_match.group())
                name = metadata.get("name", "")[:100]
                description = metadata.get("description", "")[:500]
                
                logger.info(f"✅ Parsed AI metadata - name: '{name}', description: '{description[:100]}...'")
                
                return {
                    "name": name,
                    "description": description
                }
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON: {e}, matched text: {json_match.group()}")
        
        # Try alternative: look for lines starting with name/description
        # Handle markdown formatting: **name**, *name*, __name__, `name`
        name_match = re.search(r'[*_`"\']*name[*_`"\']*\s*[:=]\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
        desc_match = re.search(r'[*_`"\']*description[*_`"\']*\s*[:=]\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
        
        if name_match or desc_match:
            name = name_match.group(1)[:100] if name_match else f"Result: {result_tables[0]['name'] if result_tables else 'Data'}"
            description = desc_match.group(1)[:500] if desc_match else user_prompt[:200] if user_prompt else "Transformation result"
            
            logger.info(f"✅ Extracted AI metadata - name: '{name}', description: '{description[:100]}...'")
            
            return {
                "name": name,
                "description": description
            }
        
        # Fallback if parsing failed
        fallback_name = f"Результат: {result_tables[0]['name'] if result_tables else 'Данные'}"
        logger.warning(f"⚠️ Failed to parse AI metadata response, using fallback name='{fallback_name}'. Full response: {response[:500]}")
        return {
            "name": fallback_name,
            "description": user_prompt[:200] if user_prompt else "Результат трансформации"
        }
        
    except Exception as e:
        fallback_name = f"Результат: {result_tables[0]['name'] if result_tables else 'Данные'}"
        logger.error(f"❌ Failed to generate AI metadata: {e}, using fallback name='{fallback_name}'", exc_info=True)
        # Fallback to simple generation
        return {
            "name": fallback_name,
            "description": user_prompt[:200] if user_prompt else "Результат трансформации"
        }


@router.post("/{content_id}/transform/execute")
async def execute_transformation(
    content_id: UUID,
    params: dict,
    db: AsyncSession = Depends(get_db),
    user_and_token: tuple[User, str] = Depends(get_current_user_with_token)
):
    """
    Execute transformation code (potentially edited by user).
    
    Takes code from /preview endpoint (or user-edited version) and executes it.
    """
    from datetime import datetime
    import uuid
    from app.schemas.content_node import ContentNodeCreate
    from app.schemas.edge import EdgeCreate
    
    current_user, auth_token = user_and_token
    
    code = params.get("code")
    transformation_id = params.get("transformation_id")
    description = params.get("description", "Custom transformation")
    prompt = params.get("prompt", "")  # Original user prompt for transformation
    chat_history = params.get("chat_history", [])  # Chat history for editing later
    selected_node_ids = params.get("selected_node_ids", [str(content_id)])  # Support multiple source nodes
    target_node_id = params.get("target_node_id")  # If provided, UPDATE existing node instead of CREATE
    
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="code is required")
    
    if isinstance(selected_node_ids, str):
        selected_node_ids = [selected_node_ids]
    
    try:
        # Get source ContentNode(s)
        source_node = await ContentNodeService.get_content_node(db, content_id)
        if not source_node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ContentNode not found")
        await BoardService.get_board_for_edit(db, source_node.board_id, current_user.id)

        # Collect all source nodes for input data
        all_source_nodes = []
        for node_id_str in selected_node_ids:
            try:
                node_id = UUID(node_id_str) if isinstance(node_id_str, str) else node_id_str
            except ValueError:
                logger.warning(f"Invalid UUID format: {node_id_str}")
                continue

            node = await ContentNodeService.get_content_node(db, node_id)
            if node and node.content:
                if node.board_id != source_node.board_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Все исходные узлы должны принадлежать одной доске",
                    )
                all_source_nodes.append(node)
        
        if not all_source_nodes:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No valid source ContentNodes found")
        
        # Validate code before execution (security check)
        from app.services.multi_agent.agents.validator import get_validator_agent
        validator = get_validator_agent(None)  # No message bus needed for validation
        
        # Prepare input schemas for validation (from all nodes)
        input_schemas = []
        for node in all_source_nodes:
            for table in node.content.get("tables", []):
                schema = {
                    "name": table["name"],
                    "columns": table["columns"],
                    "sample_data": table.get("data", [])[:5]
                }
                input_schemas.append(schema)
        
        validation_result = await validator.process_task(
            task={
                "type": "validate_code",
                "code": code,
                "input_schemas": input_schemas,
                "dry_run": False  # Skip dry-run for execute (already validated in preview)
            },
            context={}
        )
        
        if not validation_result.get("valid", False):
            errors = validation_result.get("errors", [])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Code validation failed: {'; '.join(errors)}"
            )
        
        # Prepare input data for execution (from all nodes)
        input_data = {}
        for node in all_source_nodes:
            for table in node.content.get("tables", []):
                df = python_executor.table_dict_to_dataframe(table)
                input_data[table["name"]] = df
                logger.info(f"📥 Prepared input table '{table['name']}': {df.shape[0]} rows, {df.shape[1]} columns")
        
        logger.info(f"🚀 Executing transformation code ({len(code)} chars)...")
        
        # Execute transformation code
        execution_result = await python_executor.execute_transformation(
            code=code,
            input_data=input_data,
            user_id=str(current_user.id),
        )
        
        if not execution_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transformation execution failed: {execution_result.error}"
            )
        
        # Convert result DataFrames to ContentNode format with AI-generated table names
        result_tables = []
        for var_name, df in execution_result.result_dfs.items():
            # var_name now contains meaningful name from generated code (e.g., sales_by_brand)
            logger.info(f"📝 Using table name from code: '{var_name}'")
            
            result_table = python_executor.dataframe_to_table_dict(df, var_name)
            result_tables.append(result_table)
            logger.info(f"📋 Result table '{var_name}': {result_table.get('row_count', 0)} rows, columns: {result_table.get('columns', [])}")
            # Log first 2 rows of data
            if result_table.get('data') and len(result_table['data']) > 0:
                logger.info(f"   First row: {result_table['data'][0]}")
        
        logger.info(f"✅ Creating ContentNode with {len(result_tables)} tables: {[t['name'] for t in result_tables]}")
        
        # Generate AI-powered name and description for the transformation result
        ai_metadata = await _generate_content_metadata(
            source_nodes=all_source_nodes,
            user_prompt=prompt,
            transformation_code=code,
            result_tables=result_tables,
            execution_time_ms=execution_result.execution_time_ms
        )
        
        logger.info(f"🤖 AI metadata generated - name: '{ai_metadata.get('name')}', description: '{ai_metadata.get('description', '')[:100]}...'")
        
        # Check if we should UPDATE existing node or CREATE new one
        if target_node_id:
            # UPDATE mode: update existing ContentNode
            try:
                target_uuid = UUID(target_node_id) if isinstance(target_node_id, str) else target_node_id
                existing_node = await ContentNodeService.get_content_node(db, target_uuid)
                
                if not existing_node:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target node {target_node_id} not found")
                if existing_node.board_id != source_node.board_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Целевой узел должен принадлежать той же доске",
                    )

                logger.info(f"🔄 UPDATE mode: updating existing node {target_node_id}")
                
                # Update content and lineage
                final_name = ai_metadata.get("name") or existing_node.node_metadata.get('name', f"Трансформация: {source_node.node_metadata.get('name', 'Данные')}")
                final_description = ai_metadata.get("description", description[:100] if description else "")
                
                # Preserve existing lineage and append new transformation
                existing_lineage = existing_node.lineage or {}
                existing_history = existing_lineage.get("transformation_history", [])
                
                updated_lineage = {
                    "source_node_id": existing_lineage.get("source_node_id") or str(content_id),
                    "source_node_ids": existing_lineage.get("source_node_ids") or [str(n.id) for n in all_source_nodes],
                    "transformation_id": transformation_id or existing_lineage.get("transformation_id") or str(uuid.uuid4()),
                    "operation": "transform",
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "multi_agent_system",
                    "created_by": str(current_user.id),
                    "transformation_history": existing_history + [
                        {
                            "operation": "transform",
                            "description": description,
                            "prompt": prompt,
                            "code_snippet": code,
                            "transformation_id": transformation_id or str(uuid.uuid4()),
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_history": chat_history
                        }
                    ]
                }
                
                from app.schemas.content_node import ContentNodeUpdate
                updated_node = await ContentNodeService.update_content_node(
                    db,
                    target_uuid,
                    ContentNodeUpdate(
                        content={
                            "text": final_description,
                            "tables": result_tables
                        },
                        lineage=updated_lineage,
                        metadata={
                            "name": final_name,
                            "description": description,
                            "ai_generated_summary": final_description,
                            "execution_time_ms": execution_result.execution_time_ms,
                            "source_nodes_count": len(all_source_nodes),
                            "source_rows": sum(
                                sum(t.get("row_count", 0) for t in n.content.get("tables", []))
                                for n in all_source_nodes
                                if hasattr(n, 'content') and n.content
                            ),
                            "result_tables_count": len(result_tables),
                            "result_rows": sum(t.get("row_count", 0) for t in result_tables),
                        }
                    )
                )
                
                await db.commit()
                await db.refresh(updated_node)
                
                # Update transformation edge params (keep existing edges, just update params)
                from sqlalchemy import select, update
                from app.models.edge import Edge
                
                edge_stmt = select(Edge).where(
                    Edge.target_node_id == target_uuid,
                    Edge.edge_type == "TRANSFORMATION"
                )
                result = await db.execute(edge_stmt)
                existing_edges = result.scalars().all()
                
                for edge in existing_edges:
                    edge.transformation_params = {
                        "transformation_id": transformation_id,
                        "code": code,
                        "prompt": prompt,
                        "execution_time_ms": execution_result.execution_time_ms,
                    }
                    edge.label = description[:50]
                
                await db.commit()
                
                logger.info(f"✅ Updated existing node {target_node_id} with {len(result_tables)} tables")
                
                return {
                    "content_node": _serialize_content_node(updated_node),
                    "transform_edge": _serialize_edge(existing_edges[0]) if existing_edges else None,
                    "transform_edges": [_serialize_edge(e) for e in existing_edges],
                    "transformation": {
                        "id": transformation_id,
                        "code": code,
                        "execution_time_ms": execution_result.execution_time_ms,
                    },
                    "updated": True  # Flag to indicate UPDATE operation
                }
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid target_node_id format: {target_node_id}")
        
        # CREATE mode: create new ContentNode
        logger.info(f"➕ CREATE mode: creating new ContentNode")
        
        # Smart positioning: get all existing nodes on board for collision detection
        all_content_nodes = await ContentNodeService.get_board_contents(db, source_node.board_id)
        from app.services.source_node_service import SourceNodeService
        board_source_nodes = await SourceNodeService.get_board_sources(db, source_node.board_id)
        
        # Convert nodes to bounds for collision detection
        existing_nodes = []
        for node in all_content_nodes:
            pos = node.position or {"x": 0, "y": 0}
            existing_nodes.append(NodeBounds(
                id=str(node.id),
                x=pos.get("x", 0),
                y=pos.get("y", 0),
                width=node.width or 320,
                height=node.height or 200
            ))
        for node in board_source_nodes:
            pos = node.position or {"x": 0, "y": 0}
            existing_nodes.append(NodeBounds(
                id=str(node.id),
                x=pos.get("x", 0),
                y=pos.get("y", 0),
                width=node.width or 280,
                height=node.height or 150
            ))
        
        # Find optimal position for new node
        source_pos = source_node.position or {"x": 0, "y": 0}
        optimal_position = find_optimal_node_position(
            source_node={
                "x": source_pos.get("x", 0),
                "y": source_pos.get("y", 0),
                "width": source_node.width or 320,
                "height": source_node.height or 200
            },
            target_width=320,
            target_height=200,
            existing_nodes=existing_nodes,
            connection_type="transformation"
        )
        
        # Create new ContentNode with multiple result tables
        final_name = ai_metadata.get("name") or f"Трансформация: {source_node.node_metadata.get('name', 'Данные')}"
        final_description = ai_metadata.get("description", description[:100] if description else "")
        
        logger.info(f"📦 Creating ContentNode with name='{final_name}', description='{final_description[:50]}...'")
        
        new_content_node = await ContentNodeService.create_content_node(
            db,
            ContentNodeCreate(
                board_id=source_node.board_id,
                content={
                    "text": final_description,
                    "tables": result_tables
                },
                lineage={
                    "source_node_id": str(content_id),  # Primary source for backward compatibility
                    "source_node_ids": [str(n.id) for n in all_source_nodes],  # All sources
                    "transformation_id": transformation_id or str(uuid.uuid4()),
                    "operation": "transform",
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "multi_agent_system",
                    "created_by": str(current_user.id),
                    "transformation_history": [
                        {
                            "operation": "transform",
                            "description": description,
                            "prompt": prompt,
                            "code_snippet": code,  # Full code, not truncated
                            "transformation_id": transformation_id or str(uuid.uuid4()),
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_history": chat_history
                        }
                    ]
                },
                metadata={
                    "name": final_name,
                    "description": description,
                    "ai_generated_summary": final_description,
                    "execution_time_ms": execution_result.execution_time_ms,
                    "source_nodes_count": len(all_source_nodes),
                    "source_rows": sum(
                        sum(t.get("row_count", 0) for t in n.content.get("tables", []))
                        for n in all_source_nodes
                        if hasattr(n, 'content') and n.content  # Only ContentNodes have content
                    ),
                    "result_tables_count": len(result_tables),
                    "result_rows": sum(t.get("row_count", 0) for t in result_tables),
                },
                position=optimal_position
            )
        )
        
        await db.commit()
        await db.refresh(new_content_node)
        
        # Create TRANSFORMATION edges from ALL source nodes
        created_edges = []
        for idx, source_n in enumerate(all_source_nodes):
            transform_edge = await EdgeService.create_edge(
                db,
                source_node.board_id,
                EdgeCreate(
                    source_node_id=source_n.id,
                    source_node_type="content_node",
                    target_node_id=new_content_node.id,
                    target_node_type="content_node",
                    edge_type="TRANSFORMATION",
                    label=description[:50] if idx == 0 else "",  # Label only on first edge
                    transformation_params={
                        "transformation_id": transformation_id,
                        "code": code,
                        "prompt": prompt,  # Save original prompt for editing
                        "execution_time_ms": execution_result.execution_time_ms,
                    }
                ),
                current_user.id
            )
            created_edges.append(transform_edge)
            logger.info(f"Created TRANSFORMATION edge: {source_n.id} -> {new_content_node.id}")
        
        await db.commit()
        
        logger.info(f"Transformation executed: {len(all_source_nodes)} source nodes -> {new_content_node.id}")
        
        return {
            "content_node": _serialize_content_node(new_content_node),
            "transform_edge": _serialize_edge(created_edges[0]) if created_edges else None,
            "transform_edges": [_serialize_edge(e) for e in created_edges],
            "transformation": {
                "id": transformation_id,
                "code": code,
                "execution_time_ms": execution_result.execution_time_ms,
            },
            "updated": False  # Flag to indicate CREATE operation
        }
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Execute transformation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{content_id}/transform")
async def transform_content_node(
    content_id: UUID,
    params: dict,
    db: AsyncSession = Depends(get_db),
    user_and_token: tuple[User, str] = Depends(get_current_user_with_token)
):
    """Transform a ContentNode using AI-generated Python code (V2 controller).

    Creates a new ContentNode with transformed data and TRANSFORMATION edge.
    """
    current_user, auth_token = user_and_token

    prompt = params.get("prompt")
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prompt is required")

    try:
        # 1. Get source ContentNode
        source_node = await ContentNodeService.get_content_node(db, content_id)
        if not source_node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ContentNode not found")
        await BoardService.get_board_for_edit(db, source_node.board_id, current_user.id)

        # 2. Generate code via V2 controller (skip_execution — route handles execution + DB save)
        orchestrator = _get_orchestrator_or_503()
        controller = TransformationController(orchestrator)

        input_tables = source_node.content.get("tables", []) if source_node.content else []
        gen_result = await controller.process_request(
            user_message=prompt,
            context={
                "board_id": str(source_node.board_id),
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "input_tables": input_tables,
                "skip_execution": True,
            },
        )

        if gen_result.status != "success" or not gen_result.code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=gen_result.error or "Code generation failed"
            )

        # 3. Prepare input data for execution
        input_data = {}
        for table in input_tables:
            df = python_executor.table_dict_to_dataframe(table)
            input_data[table["name"]] = df

        # 4. Execute transformation code
        execution_result = await python_executor.execute_transformation(
            code=gen_result.code,
            input_data=input_data,
            user_id=str(current_user.id),
        )

        if not execution_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transformation execution failed: {execution_result.error}"
            )

        # 5. Convert result DataFrames to ContentNode format
        result_tables = []
        for var_name, df in execution_result.result_dfs.items():
            result_table = python_executor.dataframe_to_table_dict(df, var_name)
            result_tables.append(result_table)

        # 6. Generate AI-powered name and description (как в V1 execute-transformation)
        from app.schemas.content_node import ContentNodeCreate

        ai_metadata = await _generate_content_metadata(
            source_nodes=[source_node],
            user_prompt=prompt,
            transformation_code=gen_result.code,
            result_tables=result_tables,
            execution_time_ms=execution_result.execution_time_ms or 0,
        )

        source_name = source_node.node_metadata.get("name", "Данные") if source_node.node_metadata else "Данные"
        final_name = ai_metadata.get("name") or f"Трансформация: {source_name}"
        final_description = ai_metadata.get("description") or gen_result.code_description or ""

        logger.info(f"🤖 V2 transform AI metadata - name: '{final_name}', description: '{final_description[:100]}...'")

        # 7. Create new ContentNode
        new_content_node = await ContentNodeService.create_content_node(
            db,
            ContentNodeCreate(
                board_id=source_node.board_id,
                content={"text": prompt[:100] if prompt else "", "tables": result_tables},
                lineage={
                    "source_node_id": str(content_id),
                    "operation": "transform",
                    "agent": "orchestrator_v2",
                    "created_by": str(current_user.id),
                },
                metadata={
                    "name": final_name,
                    "description": final_description,
                    "transformation_prompt": prompt,
                    "execution_time_ms": execution_result.execution_time_ms,
                    "result_tables_count": len(result_tables),
                    "result_rows": sum(t.get("row_count", 0) for t in result_tables),
                },
                position={
                    "x": source_node.position.get("x", 0) + 400,
                    "y": source_node.position.get("y", 0)
                }
            )
        )

        await db.commit()
        await db.refresh(new_content_node)

        # 7. Create TRANSFORMATION edge
        from app.schemas.edge import EdgeCreate

        transform_edge = await EdgeService.create_edge(
            db,
            source_node.board_id,
            EdgeCreate(
                source_node_id=content_id,
                source_node_type="content_node",
                target_node_id=new_content_node.id,
                target_node_type="content_node",
                edge_type="TRANSFORMATION",
                label=prompt[:50],
                transformation_params={
                    "prompt": prompt,
                    "code": gen_result.code,
                    "execution_time_ms": execution_result.execution_time_ms,
                }
            ),
            current_user.id
        )

        await db.commit()

        logger.info(f"Transformation completed: {content_id} -> {new_content_node.id}")

        return {
            "content_node": _serialize_content_node(new_content_node),
            "transform_edge": _serialize_edge(transform_edge),
            "transformation": {
                "code": gen_result.code,
                "execution_time_ms": execution_result.execution_time_ms,
            }
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Transformation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/transform", response_model=TransformResponse)
async def transform_content(
    request: TransformRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Transform one or more ContentNodes using Python code.
    
    Executes arbitrary Python code to transform source ContentNodes into new ContentNode.
    Maintains data lineage and creates TRANSFORMATION edges automatically.
    
    Example code:
        # Simple transformation
        result = df0.groupby('category')['value'].sum().reset_index()
        
        # Combine multiple sources
        result = pd.merge(df0, df1, on='id')
    """
    try:
        if not request.source_content_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_content_ids is required",
            )
        first = await ContentNodeService.get_content_node(db, request.source_content_ids[0])
        if not first:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source ContentNode not found",
            )
        board_id = first.board_id
        for cid in request.source_content_ids[1:]:
            cn = await ContentNodeService.get_content_node(db, cid)
            if not cn:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ContentNode {cid} not found",
                )
            if cn.board_id != board_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Все исходные узлы должны быть на одной доске",
                )
        await BoardService.get_board_for_edit(db, board_id, current_user.id)

        new_content = await ContentNodeService.transform_content(
            db,
            request.source_content_ids,
            request.code,
            request.description
        )
        
        return TransformResponse(
            content_node_id=new_content.id,
            status="success",
            message=f"Transformation complete ({len(request.source_content_ids)} sources)"
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Transform operation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transformation error: {str(e)}"
        )


@router.post("/get-table", response_model=GetTableResponse)
async def get_table(
    request: GetTableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific table from ContentNode.
    
    ContentNode can contain multiple tables. This endpoint retrieves a specific one by ID.
    """
    await _require_content_view(db, request.content_node_id, current_user.id)
    table = await ContentNodeService.get_table(db, request.content_node_id, request.table_id)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table {request.table_id} not found in ContentNode"
        )
    
    row_count = len(table.get("rows", []))
    return GetTableResponse(table=table, row_count=row_count)


@router.get("/{content_id}/lineage", response_model=list[dict[str, Any]])
async def get_lineage_chain(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full data lineage chain for ContentNode.
    
    Returns the complete chain from original SourceNode to current ContentNode,
    including all intermediate transformations.
    """
    await _require_content_view(db, content_id, current_user.id)
    lineage_chain = await ContentNodeService.get_lineage_chain(db, content_id)
    return lineage_chain


@router.get("/{content_id}/downstream", response_model=list[ContentNodeResponse])
async def get_downstream_contents(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all ContentNodes that depend on this ContentNode.
    
    Useful for understanding impact of changes and for replay operations.
    """
    await _require_content_view(db, content_id, current_user.id)
    downstream = await ContentNodeService.get_downstream_contents(db, content_id)
    return downstream


@router.post("/{content_id}/visualize", response_model=VisualizeResponse, status_code=status.HTTP_201_CREATED)
async def create_visualization(
    content_id: UUID,
    request: VisualizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create WidgetNode visualization from ContentNode via V2 controller.

    Workflow:
    1. WidgetController generates HTML/CSS/JS code via Orchestrator V2
    2. WidgetNode is created in DB
    3. VISUALIZATION edge is created to ContentNode

    Args:
        content_id: Source ContentNode to visualize
        request: Visualization options (user_prompt, widget_name, auto_refresh, position)

    Returns:
        VisualizeResponse with created WidgetNode and edge IDs
    """
    try:
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ContentNode {content_id} not found"
            )
        await BoardService.get_board_for_edit(db, content_node.board_id, current_user.id)

        content_data = content_node.content or {}
        selected_node_ids = [str(content_id)]
        if isinstance(request.selected_node_ids, list) and request.selected_node_ids:
            selected_node_ids = [str(item).strip() for item in request.selected_node_ids if str(item).strip()]
            if str(content_id) not in selected_node_ids:
                selected_node_ids.insert(0, str(content_id))

        # 1. Generate widget code via V2 controller
        orchestrator = _get_orchestrator_or_503()
        controller = WidgetController(orchestrator)

        result = await controller.process_request(
            user_message=request.user_prompt,
            context={
                "board_id": str(content_node.board_id),
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "content_data": content_data,
                "content_node_metadata": content_node.node_metadata or {},
                "selected_node_ids": selected_node_ids,
            },
        )

        if result.status != "success":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Visualization generation failed: {result.error}"
            )

        # 2. Create WidgetNode
        from app.services.widget_node_service import WidgetNodeService
        from app.schemas.widget_node import WidgetNodeCreate

        widget_name = request.widget_name or result.widget_name or "Visualization"

        if request.position:
            widget_position = request.position
        else:
            node_position = content_node.position or {"x": 0, "y": 0}
            widget_position = {
                "x": node_position.get("x", 0) + 350,
                "y": node_position.get("y", 0)
            }

        widget_data = WidgetNodeCreate(
            board_id=content_node.board_id,
            name=widget_name,
            description=result.code_description or "AI-generated visualization",
            html_code=result.widget_code or "",
            css_code=None,
            js_code=None,
            config={"widget_type": result.widget_type or "custom"},
            auto_refresh=request.auto_refresh,
            generated_by="orchestrator_v2",
            generation_prompt=request.user_prompt,
            x=widget_position["x"],
            y=widget_position["y"],
            width=400,
            height=300
        )

        widget_node = await WidgetNodeService.create_widget_node(
            db, content_node.board_id, current_user.id, widget_data
        )

        # 3. Create VISUALIZATION edge
        from app.schemas.edge import EdgeCreate

        edge_data = EdgeCreate(
            source_node_id=content_id,
            source_node_type="ContentNode",
            target_node_id=widget_node.id,
            target_node_type="WidgetNode",
            edge_type="VISUALIZATION",
            label=f"Visualizes: {widget_node.name}",
            transformation_params={
                "description": result.code_description or "",
                "widget_type": result.widget_type or "custom",
                "auto_refresh": request.auto_refresh,
                "created_by": "orchestrator_v2"
            }
        )

        edge = await EdgeService.create_edge(db, content_node.board_id, edge_data, current_user.id)

        await db.commit()
        await db.refresh(widget_node)
        await db.refresh(edge)

        logger.info(f"Created WidgetNode {widget_node.id} with VISUALIZATION edge from ContentNode {content_id}")

        return VisualizeResponse(
            widget_node_id=widget_node.id,
            edge_id=edge.id,
            status="success"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Visualization creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Visualization creation failed: {str(e)}"
        )


@router.post("/{content_id}/visualize-iterative", response_model=VisualizeIterativeResponse)
async def visualize_content_iterative(
    content_id: UUID,
    request: VisualizeIterativeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate visualization code iteratively via V2 controller.

    Used by the interactive WidgetDialog:
    1. Generate initial visualization from user prompt
    2. Refine existing visualization based on user feedback
    3. Return HTML/CSS/JS code without creating WidgetNode

    Args:
        content_id: Source ContentNode to visualize
        request: Iterative generation request (prompt + optional existing code)

    Returns:
        VisualizeIterativeResponse with generated HTML/CSS/JS code
    """
    try:
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ContentNode {content_id} not found"
            )
        await BoardService.get_board_for_edit(db, content_node.board_id, current_user.id)

        content_data = content_node.content or {}
        selected_node_ids = [str(content_id)]
        if isinstance(request.selected_node_ids, list) and request.selected_node_ids:
            selected_node_ids = [str(item).strip() for item in request.selected_node_ids if str(item).strip()]
            if str(content_id) not in selected_node_ids:
                selected_node_ids.insert(0, str(content_id))

        # V2 controller
        orchestrator = _get_orchestrator_or_503()
        controller = WidgetController(orchestrator)

        result = await controller.process_request(
            user_message=request.user_prompt,
            context={
                "board_id": str(content_node.board_id),
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "content_data": content_data,
                "content_node_metadata": content_node.node_metadata or {},
                "existing_widget_code": request.existing_widget_code,
                "chat_history": request.chat_history or [],
                "selected_node_ids": selected_node_ids,
                "is_refinement": bool(request.existing_widget_code),
            },
        )

        if result.status != "success":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Visualization generation failed"
            )

        return VisualizeIterativeResponse(
            html_code=result.code if result.code_language == "html" else "",
            css_code="",
            js_code="",
            widget_code=result.widget_code,
            widget_name=result.widget_name or "",
            widget_type=result.widget_type or "custom",
            description=result.code_description or "AI-generated visualization",
            status="success"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Iterative visualization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Visualization generation failed: {str(e)}"
        )


@router.post("/{content_id}/visualize-multiagent", response_model=VisualizeIterativeResponse)
async def visualize_content_multiagent(
    content_id: UUID,
    request: VisualizeIterativeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate visualization code via Orchestrator V2 (full pipeline).

    Uses WidgetController → Orchestrator V2.

    Args:
        content_id: Source ContentNode to visualize
        request: Iterative generation request (prompt + optional existing code)

    Returns:
        VisualizeIterativeResponse with generated HTML/CSS/JS code
    """
    try:
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ContentNode {content_id} not found"
            )
        await BoardService.get_board_for_edit(db, content_node.board_id, current_user.id)

        content_data = content_node.content or {}
        selected_node_ids = [str(content_id)]
        if isinstance(request.selected_node_ids, list) and request.selected_node_ids:
            selected_node_ids = [str(item).strip() for item in request.selected_node_ids if str(item).strip()]
            if str(content_id) not in selected_node_ids:
                selected_node_ids.insert(0, str(content_id))

        # V2 controller
        orchestrator = _get_orchestrator_or_503()
        controller = WidgetController(orchestrator)

        result = await controller.process_request(
            user_message=request.user_prompt,
            context={
                "board_id": str(content_node.board_id),
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "content_data": content_data,
                "content_node_metadata": content_node.node_metadata or {},
                "existing_widget_code": request.existing_widget_code,
                "chat_history": request.chat_history or [],
                "selected_node_ids": selected_node_ids,
                "is_refinement": bool(request.existing_widget_code),
            },
        )

        if result.status != "success":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Visualization generation failed"
            )

        logger.info(
            f"🏷️ visualize-multiagent response: "
            f"widget_name={result.widget_name!r}, "
            f"description={str(result.code_description or '')[:80]!r}"
        )
        return VisualizeIterativeResponse(
            html_code=result.code if result.code_language == "html" else "",
            css_code="",
            js_code="",
            widget_code=result.widget_code,
            widget_name=result.widget_name or "",
            widget_type=result.widget_type or "custom",
            description=result.code_description or "AI-generated visualization",
            status="success"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MultiAgent visualization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Visualization generation failed: {str(e)}"
        )


@router.post("/{content_id}/visualize-multiagent-stream")
async def visualize_content_multiagent_stream(
    content_id: UUID,
    request: VisualizeIterativeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streaming-версия /visualize-multiagent (NDJSON прогресс + финальный результат)."""
    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def _progress_callback(progress_payload: dict) -> None:
        payload = progress_payload or {}
        if payload.get("event") == "plan_update":
            await queue.put(
                {
                    "type": "plan",
                    "steps": payload.get("steps") or [],
                    "completed_count": payload.get("completed_count") or 0,
                    "source": payload.get("source"),
                }
            )
            return
        await queue.put({"type": "progress", **payload})

    async def _run_pipeline() -> None:
        try:
            await queue.put({"type": "start"})
            content_node = await ContentNodeService.get_content_node(db, content_id)
            if not content_node:
                await queue.put({"type": "error", "error": f"ContentNode {content_id} not found"})
                return

            try:
                await BoardService.get_board_for_edit(db, content_node.board_id, current_user.id)
            except HTTPException as e:
                await queue.put({"type": "error", "error": str(e.detail)})
                return

            content_data = content_node.content or {}
            selected_node_ids = [str(content_id)]
            if isinstance(request.selected_node_ids, list) and request.selected_node_ids:
                selected_node_ids = [str(item).strip() for item in request.selected_node_ids if str(item).strip()]
                if str(content_id) not in selected_node_ids:
                    selected_node_ids.insert(0, str(content_id))
            orchestrator = _get_orchestrator_or_503()
            controller = WidgetController(orchestrator)

            result = await controller.process_request(
                user_message=request.user_prompt,
                context={
                    "board_id": str(content_node.board_id),
                    "user_id": str(current_user.id),
                    "content_node_id": str(content_id),
                    "content_data": content_data,
                    "content_node_metadata": content_node.node_metadata or {},
                    "existing_widget_code": request.existing_widget_code,
                    "chat_history": request.chat_history or [],
                    "selected_node_ids": selected_node_ids,
                    "is_refinement": bool(request.existing_widget_code),
                    "_progress_callback": _progress_callback,
                    "_enable_plan_progress": True,
                },
            )

            if result.status != "success":
                await queue.put({"type": "error", "error": result.error or "Visualization generation failed"})
                return

            response_payload = {
                "html_code": result.code if result.code_language == "html" else "",
                "css_code": "",
                "js_code": "",
                "widget_code": result.widget_code,
                "widget_name": result.widget_name or "",
                "widget_type": result.widget_type or "custom",
                "description": result.code_description or "AI-generated visualization",
                "status": "success",
            }
            await queue.put({"type": "result", "result": response_payload})
        except HTTPException as e:
            await queue.put({"type": "error", "error": str(e.detail)})
        except Exception as e:
            logger.error(f"MultiAgent visualization stream failed: {e}", exc_info=True)
            await queue.put(
                {
                    "type": "error",
                    "error": f"Visualization generation failed: {str(e)}",
                }
            )
        finally:
            await queue.put({"type": "done"})

    async def _event_stream():
        task = asyncio.create_task(_run_pipeline())
        try:
            while True:
                item = await queue.get()
                yield json.dumps(item, ensure_ascii=False, default=_ndjson_default) + "\n"
                if item.get("type") == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(_event_stream(), media_type="application/x-ndjson")


@router.post("/{content_id}/transform-multiagent")
async def transform_content_multiagent(
    content_id: UUID,
    params: dict,
    db: AsyncSession = Depends(get_db),
    user_and_token: tuple[User, str] = Depends(get_current_user_with_token)
):
    """Transform data via Orchestrator V2 (full validation pipeline).

    Uses TransformationController → Orchestrator V2.
    Supports both TRANSFORMATION mode (code gen + execution) and
    DISCUSSION mode (narrative response).

    Request body:
    {
        "user_prompt": str,
        "existing_code": str | null,
        "transformation_id": str | null,
        "chat_history": [{"role": str, "content": str}, ...],
        "selected_node_ids": [UUID, ...],
        "preview_only": bool = True
    }
    """
    current_user, auth_token = user_and_token

    user_prompt = params.get("user_prompt")
    if not user_prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_prompt is required")

    existing_code = params.get("existing_code")
    chat_history = params.get("chat_history", [])
    selected_node_ids = params.get("selected_node_ids", [str(content_id)])
    if isinstance(selected_node_ids, str):
        selected_node_ids = [selected_node_ids]

    try:
        # Collect data using helper
        nodes_data, input_data, text_content, board_id = await _collect_content_nodes_data(
            db, content_id, selected_node_ids, current_user.id
        )

        # V2 controller
        orchestrator = _get_orchestrator_or_503()
        controller = TransformationController(orchestrator)

        result = await controller.process_request(
            user_message=user_prompt,
            context={
                "board_id": board_id,
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "auth_token": auth_token,
                "input_tables": [t for nd in nodes_data for t in nd.get("tables", [])],
                "input_data": input_data,  # Full DataFrames for execution
                "text_content": text_content,
                "existing_code": existing_code,
                "chat_history": chat_history,
                "selected_node_ids": selected_node_ids,
            },
        )

        if result.status != "success":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Transformation failed"
            )

        # Discussion mode
        if result.mode == "discussion":
            return {
                "transformation_id": None,
                "code": None,
                "description": result.narrative,
                "content_type": result.narrative_format,
                "preview_data": None,
                "validation": {"is_valid": True, "errors": []},
                "agent_plan": result.plan,
                "mode": "discussion",
            }

        # Transformation mode
        logger.info(f"📤 Sending transformation response: code={len(result.code or '')} chars, preview_tables={len(result.preview_data.get('tables', []) if result.preview_data else [])}")
        logger.info(f"📄 First 100 chars of code: {(result.code or '')[:100]}...")
        return {
            "transformation_id": str(uuid.uuid4()),
            "code": result.code,
            "description": result.code_description,
            "preview_data": result.preview_data,
            "validation": result.validation or {"is_valid": True, "errors": []},
            "agent_plan": result.plan,
        }

    except HTTPException:
        raise
    except RuntimeError as e:
        error_msg = str(e)
        if "Failed to get response from GigaChat" in error_msg or "getaddrinfo failed" in error_msg:
            logger.error(f"GigaChat API connection error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось подключиться к GigaChat API. Проверьте GIGACHAT_CREDENTIALS в .env"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transformation generation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"MultiAgent transformation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transformation generation failed: {str(e)}"
        )


@router.post("/{content_id}/transform-multiagent-stream")
async def transform_content_multiagent_stream(
    content_id: UUID,
    params: dict,
    db: AsyncSession = Depends(get_db),
    user_and_token: tuple[User, str] = Depends(get_current_user_with_token),
):
    """Streaming-версия /transform-multiagent (NDJSON прогресс + финальный результат)."""
    current_user, auth_token = user_and_token

    user_prompt = params.get("user_prompt")
    if not user_prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_prompt is required")

    existing_code = params.get("existing_code")
    chat_history = params.get("chat_history", [])
    selected_node_ids = params.get("selected_node_ids", [str(content_id)])
    if isinstance(selected_node_ids, str):
        selected_node_ids = [selected_node_ids]

    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def _progress_callback(progress_payload: dict) -> None:
        payload = progress_payload or {}
        if payload.get("event") == "plan_update":
            await queue.put(
                {
                    "type": "plan",
                    "steps": payload.get("steps") or [],
                    "completed_count": payload.get("completed_count") or 0,
                    "source": payload.get("source"),
                }
            )
            return
        await queue.put({"type": "progress", **payload})

    async def _run_pipeline() -> None:
        try:
            await queue.put({"type": "start"})
            nodes_data, input_data, text_content, board_id = await _collect_content_nodes_data(
                db, content_id, selected_node_ids, current_user.id
            )

            orchestrator = _get_orchestrator_or_503()
            controller = TransformationController(orchestrator)

            result = await controller.process_request(
                user_message=user_prompt,
                context={
                    "board_id": board_id,
                    "user_id": str(current_user.id),
                    "content_node_id": str(content_id),
                    "auth_token": auth_token,
                    "input_tables": [t for nd in nodes_data for t in nd.get("tables", [])],
                    "input_data": input_data,
                    "text_content": text_content,
                    "existing_code": existing_code,
                    "chat_history": chat_history,
                    "selected_node_ids": selected_node_ids,
                    "_progress_callback": _progress_callback,
                    "_enable_plan_progress": True,
                },
            )

            if result.status != "success":
                await queue.put(
                    {
                        "type": "error",
                        "error": result.error or "Transformation failed",
                    }
                )
                return

            if result.mode == "discussion":
                response_payload = {
                    "transformation_id": None,
                    "code": None,
                    "description": result.narrative,
                    "content_type": result.narrative_format,
                    "preview_data": None,
                    "validation": {"is_valid": True, "errors": []},
                    "agent_plan": result.plan,
                    "mode": "discussion",
                }
            else:
                response_payload = {
                    "transformation_id": str(uuid.uuid4()),
                    "code": result.code,
                    "description": result.code_description,
                    "preview_data": result.preview_data,
                    "validation": result.validation or {"is_valid": True, "errors": []},
                    "agent_plan": result.plan,
                }
            await queue.put({"type": "result", "result": response_payload})
        except HTTPException as e:
            await queue.put({"type": "error", "error": str(e.detail)})
        except Exception as e:
            logger.error(f"MultiAgent transformation stream failed: {e}", exc_info=True)
            await queue.put(
                {
                    "type": "error",
                    "error": f"Transformation generation failed: {str(e)}",
                }
            )
        finally:
            await queue.put({"type": "done"})

    async def _event_stream():
        task = asyncio.create_task(_run_pipeline())
        try:
            while True:
                item = await queue.get()
                yield json.dumps(item, ensure_ascii=False, default=_ndjson_default) + "\n"
                if item.get("type") == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(_event_stream(), media_type="application/x-ndjson")


@router.post("/{content_id}/analyze-suggestions")
async def analyze_widget_suggestions(
    content_id: UUID,
    request: SuggestionAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyze widget and generate improvement suggestions via V2 controller.

    Uses WidgetSuggestionsController → Orchestrator V2 pipeline.

    Args:
        content_id: Source ContentNode to analyze
        request: Analysis request (chat history + current widget code)

    Returns:
        {"suggestions": [...], "analysis_summary": str}
    """
    try:
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ContentNode {content_id} not found"
            )
        await BoardService.get_board_for_edit(db, content_node.board_id, current_user.id)

        content_data = content_node.content or {}
        _cn_meta = content_node.node_metadata or {}

        # V2 controller
        orchestrator = _get_orchestrator_or_503()
        controller = WidgetSuggestionsController(orchestrator)

        result = await controller.process_request(
            user_message=f"Предложи улучшения виджета для ContentNode {content_id}",
            context={
                "board_id": str(content_node.board_id),
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "selected_node_ids": [str(content_id)],
                "content_data": content_data,
                "content_node_metadata": _cn_meta,
                "current_widget_code": request.current_widget_code,
                "chat_history": request.chat_history or [],
            },
        )

        return {
            "suggestions": result.suggestions,
            "analysis_summary": result.narrative or "Analysis complete",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Widget suggestions analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Widget suggestions analysis failed: {str(e)}"
        )


@router.post("/{content_id}/analyze-transform-suggestions")
async def analyze_transform_suggestions(
    content_id: UUID,
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyze data and generate transformation suggestions via V2 controller.

    Uses TransformSuggestionsController → Orchestrator V2 pipeline.

    Args:
        content_id: Source ContentNode to analyze
        request: {"chat_history": [...], "current_code": str | null}

    Returns:
        {"suggestions": [...], "fallback": bool}
    """
    try:
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ContentNode not found")
        await BoardService.get_board_for_edit(db, content_node.board_id, current_user.id)

        chat_history = request.get("chat_history", [])
        current_code = request.get("current_code")

        # Build input schemas from ContentNode tables
        tables = content_node.content.get("tables", []) if content_node.content else []
        content_text = content_node.content.get("text", "") if content_node.content else ""

        # 🔗 CHAIN TRANSFORMATIONS: Если есть current_code, выполнить его
        # и использовать результат как базу для suggestions (а не исходные данные)
        if current_code and tables:
            logger.info(f"🔗 Executing current_code to get transformed data for suggestions")
            try:
                # Конвертируем tables в DataFrames
                from app.services.executors.python_executor import python_executor
                input_data_for_exec = {}
                for table in tables[:2]:
                    df = python_executor.table_dict_to_dataframe(table)
                    input_data_for_exec[table.get("name", "df")] = df
                
                # Выполняем current_code
                exec_result = await python_executor.execute_transformation(
                    code=current_code,
                    input_data=input_data_for_exec,
                    user_id=str(current_user.id),
                )
                
                if exec_result.success and exec_result.result_dfs:
                    logger.info(f"✅ Using {len(exec_result.result_dfs)} result table(s) from current_code as base for suggestions")
                    # Заменяем tables результатами трансформации
                    tables = []
                    for table_name, df in exec_result.result_dfs.items():
                        table_dict = python_executor.dataframe_to_table_dict(df, table_name)
                        tables.append(table_dict)
                else:
                    logger.warning(f"⚠️ current_code execution failed, using original data: {exec_result.error}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to execute current_code for suggestions: {e}")

        input_schemas: list[dict] = []
        for table in tables[:2]:  # Берём первые 2 таблицы
            columns = table.get("columns", [])
            # Extract column names (handle both [{name,type}] and [str])
            if columns and isinstance(columns[0], dict):
                column_names = [col["name"] for col in columns][:15]
            else:
                column_names = columns[:15]
            
            # Добавляем sample_rows для лучшего понимания агентами (до 10 строк)
            rows = table.get("rows", []) or table.get("data", [])
            sample_rows = rows[:10] if rows else []
            
            input_schemas.append({
                "name": table.get("name", "df"),
                "columns": column_names,
                "content_text": content_text,
                "sample_rows": sample_rows,  # Данные для агентов
                "row_count": len(rows),
            })

        if not input_schemas and content_text and len(content_text.strip()) > 50:
            input_schemas.append({
                "name": "text_content", "columns": [],
                "content_text": content_text, "is_text_only": True,
            })

        _cn_meta = content_node.node_metadata or {}

        # V2 controller
        orchestrator = _get_orchestrator_or_503()
        controller = TransformSuggestionsController(orchestrator)

        result = await controller.process_request(
            user_message=f"Предложи трансформации для данных ContentNode {content_id}",
            context={
                "board_id": str(content_node.board_id),
                "user_id": str(current_user.id),
                "content_node_id": str(content_id),
                "selected_node_ids": [str(content_id)],
                "content_node_name": _cn_meta.get("name", "content_node"),
                "input_schemas": input_schemas,
                "existing_code": current_code,
                "chat_history": chat_history,
            },
        )

        return {"suggestions": result.suggestions, "fallback": result.status != "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transform suggestions analysis failed: {e}", exc_info=True)
        return {
            "suggestions": [
                {"id": "fallback-1", "label": "Фильтрация данных", "prompt": "Отфильтровать строки по условию", "category": "filter", "confidence": 0.7, "description": "Базовая рекомендация (AI недоступен)"},
                {"id": "fallback-2", "label": "Группировка", "prompt": "Сгруппировать данные и посчитать агрегаты", "category": "aggregate", "confidence": 0.65, "description": "Базовая рекомендация (AI недоступен)"},
            ],
            "fallback": True,
        }


# ══════════════════════════════════════════════════════════════════════
#  Cross-filter: dimension mappings for a content node
# ══════════════════════════════════════════════════════════════════════


@router.get("/{content_id}/dimension-mappings")
async def get_node_dimension_mappings(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dimension→column mappings for a ContentNode.

    See docs/CROSS_FILTER_SYSTEM.md
    """
    await _require_content_view(db, content_id, current_user.id)
    mappings = await DimensionService.get_mappings_for_node(db, content_id)
    return {"mappings": mappings}


@router.post("/{content_id}/detect-dimensions")
async def detect_dimensions(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-detect potential dimensions from ContentNode tables.

    Scans columns of all tables in the node and suggests dimensions based on:
    - Column data type
    - Number of unique values (<50 unique → likely categorical → dimension candidate)
    - Fuzzy match against existing Dimension names in the project

    See docs/CROSS_FILTER_SYSTEM.md §Phase 8.3
    """
    from difflib import SequenceMatcher

    node = await ContentNodeService.get_content_node(db, content_id)
    if not node:
        raise HTTPException(status_code=404, detail="ContentNode not found")
    await BoardService.get_board_for_edit(db, node.board_id, current_user.id)

    tables = (node.content or {}).get("tables", [])
    if not tables:
        return {"suggestions": [], "message": "No tables found in node"}

    # Load existing project dimensions
    from app.models.dimension import Dimension as DimModel
    from sqlalchemy import select as sa_select
    existing_dims_q = await db.execute(
        sa_select(DimModel).where(DimModel.project_id == node.project_id)
    )
    existing_dims = list(existing_dims_q.scalars().all())
    dim_name_map = {d.name.lower(): d for d in existing_dims}

    suggestions = []

    for table in tables:
        table_name = table.get("name", "")
        columns = table.get("columns", [])
        rows = table.get("rows", [])

        for col in columns:
            col_name = col.get("name", "")
            col_type = col.get("type", "string")

            # Compute unique values
            values = [row.get(col_name) for row in rows if row.get(col_name) is not None]
            unique_values = list(set(str(v) for v in values))
            unique_count = len(unique_values)

            # Heuristic: columns with <= 50 unique values are dimension candidates
            # For number type, lower threshold (10)
            max_unique = 50 if col_type in ("string", "date") else 10
            if col_type == "boolean":
                max_unique = 3

            is_candidate = unique_count <= max_unique and unique_count > 0

            if not is_candidate:
                continue

            # Map column type to dimension type
            dim_type_map = {
                "string": "string",
                "text": "string",
                "number": "number",
                "integer": "number",
                "float": "number",
                "date": "date",
                "datetime": "date",
                "boolean": "boolean",
                "bool": "boolean",
            }
            suggested_type = dim_type_map.get(col_type, "string")

            # Fuzzy match against existing dimensions
            best_match_id = None
            best_confidence = 0.0
            col_lower = col_name.lower().replace("_", " ")

            for dim_name_lower, dim in dim_name_map.items():
                ratio = SequenceMatcher(None, col_lower, dim_name_lower.replace("_", " ")).ratio()
                if ratio > best_confidence and ratio >= 0.6:
                    best_confidence = ratio
                    best_match_id = str(dim.id)

            # Confidence based on heuristics
            confidence = 0.5
            if best_match_id:
                confidence = max(confidence, best_confidence)
            if unique_count <= 20:
                confidence += 0.1
            if col_type in ("string", "boolean"):
                confidence += 0.1
            confidence = min(confidence, 1.0)

            # Take sample values (up to 10)
            sample = unique_values[:10]

            suggestions.append({
                "column_name": col_name,
                "table_name": table_name,
                "suggested_name": col_name.lower().replace(" ", "_"),
                "suggested_display_name": col_name.replace("_", " ").title(),
                "suggested_type": suggested_type,
                "unique_count": unique_count,
                "sample_values": sample,
                "confidence": round(confidence, 2),
                "existing_dimension_id": best_match_id,
            })

    # Sort by confidence descending
    suggestions.sort(key=lambda s: s["confidence"], reverse=True)

    return {
        "suggestions": suggestions,
        "total_columns_scanned": sum(len(t.get("columns", [])) for t in tables),
    }

