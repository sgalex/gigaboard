"""ContentNode API routes.

См. docs/API.md для полной документации endpoints.
"""
from typing import Any
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.middleware import get_current_user, get_current_user_with_token
from app.services.content_node_service import ContentNodeService
from app.services.board_service import BoardService
from app.services.agents.transformation_agent import transformation_agent
from app.services.agents.transformation_multi_agent import get_transformation_multi_agent
from app.services.executors.python_executor import python_executor
from app.services.edge_service import EdgeService
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


@router.post("/", response_model=ContentNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_content_node(
    content_data: ContentNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new ContentNode.
    
    Contains processed data (text + tables) with full data lineage tracking.
    """
    try:
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get ContentNode by ID."""
    content_node = await ContentNodeService.get_content_node(db, content_id)
    if not content_node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ContentNode not found")
    return content_node


@router.get("/board/{board_id}", response_model=list[ContentNodeResponse])
async def get_board_contents(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all ContentNodes for a board."""
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
    """
    Generate transformation code using Multi-Agent system (no execution).
    
    Returns code for preview/edit before execution.
    
    Request body:
    {
        "prompt": str,
        "selected_node_ids": [UUID, UUID, ...]  # Optional, defaults to [content_id]
    }
    
    Workflow:
    1. Collect data from all selected ContentNodes
    2. AnalystAgent analyzes data
    3. TransformationAgent generates code
    4. ValidatorAgent validates code
    5. Returns code + validation + agent plan
    """
    prompt = params.get("prompt")
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prompt is required")
    
    # Get selected node IDs (default to single content_id)
    selected_node_ids = params.get("selected_node_ids", [str(content_id)])
    if isinstance(selected_node_ids, str):
        selected_node_ids = [selected_node_ids]
    
    try:
        # Collect data from all selected ContentNodes
        all_nodes_data = []
        for node_id_str in selected_node_ids:
            try:
                node_id = UUID(node_id_str) if isinstance(node_id_str, str) else node_id_str
            except ValueError:
                logger.warning(f"Invalid UUID format: {node_id_str}")
                continue
                
            node = await ContentNodeService.get_content_node(db, node_id)
            if node and node.content:
                # Collect node text and tables
                node_data = {
                    "node_id": str(node.id),
                    "node_name": node.node_metadata.get("name", f"Node {node.id}") if node.node_metadata else f"Node {node.id}",
                    "text": node.content.get("text", ""),
                    "tables": []
                }
                
                # Process tables: limit rows to 10
                if "tables" in node.content:
                    for table in node.content["tables"]:
                        table_data = {
                            "name": table.get("name", "table"),
                            "columns": table.get("columns", []),
                            "column_types": table.get("column_types", {}),
                            "rows": table.get("rows", [])[:10],  # First 10 rows only
                            "row_count": table.get("row_count", len(table.get("rows", [])))
                        }
                        node_data["tables"].append(table_data)
                
                all_nodes_data.append(node_data)
        
        if not all_nodes_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No valid ContentNodes found")
        
        # Initialize Multi-Agent system with message bus (or fallback if Redis unavailable)
        from app.services.multi_agent import AgentMessageBus
        from app.services.gigachat_service import get_gigachat_service
        
        message_bus = None
        gigachat_service = get_gigachat_service()
        
        # Try to connect to message bus, fallback to direct mode if Redis unavailable
        try:
            message_bus = AgentMessageBus()
            await message_bus.connect()
            logger.info("Using Multi-Agent system with message bus")
        except Exception as e:
            logger.warning(f"Message bus unavailable, using direct mode: {e}")
            message_bus = None
        
        # Use Multi-Agent system for code generation
        multi_agent = get_transformation_multi_agent(
            message_bus=message_bus,
            gigachat_service=gigachat_service
        )
        
        result = await multi_agent.generate_transformation_code(
            nodes_data=all_nodes_data,
            user_prompt=prompt
        )
        
        # Disconnect message bus if connected
        if message_bus:
            await message_bus.disconnect()
        
        return {
            "transformation_id": result["transformation_id"],
            "code": result["code"],
            "description": result["description"],
            "validation": result["validation"],
            "agent_plan": result["agent_plan"],
            "analysis": result["analysis"],
            "source_node_ids": selected_node_ids
        }
        
    except ValueError as e:
        logger.error(f"Multi-agent code generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
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
    
    try:
        # Collect input data from all selected nodes
        input_data = {}
        text_content = ""  # For text-only ContentNodes
        
        for node_id_str in selected_node_ids:
            try:
                node_id = UUID(node_id_str) if isinstance(node_id_str, str) else node_id_str
            except ValueError:
                continue
            
            node = await ContentNodeService.get_content_node(db, node_id)
            if node and node.content:
                # Collect text content
                if "text" in node.content and node.content["text"]:
                    text_content += node.content["text"] + "\n\n"
                
                # Collect tables
                if "tables" in node.content:
                    for table in node.content["tables"]:
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
            auth_token=auth_token
        )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        if not execution_result.success:
            return {
                "success": False,
                "error": execution_result.error,
                "execution_time_ms": execution_time_ms
            }
        
        # Convert result DataFrames to table format (limit rows for preview)
        result_tables = []
        row_counts = {}
        
        for var_name, df in execution_result.result_dfs.items():
            if hasattr(df, 'to_dict'):  # Is DataFrame
                row_count = len(df)
                row_counts[var_name] = row_count
                
                # Limit to first 100 rows for preview
                preview_df = df.head(100)
                
                table_dict = python_executor.dataframe_to_table_dict(
                    df=preview_df,
                    table_name=var_name
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
    """
    Iterative transformation generation with AI chat.
    
    Generates new transformation or improves existing one based on chat history.
    Automatically executes and returns preview data.
    
    Request body:
    {
        "user_prompt": str,
        "existing_code": str | null,  // For improvements
        "transformation_id": str | null,
        "chat_history": [{"role": str, "content": str}, ...],
        "selected_node_ids": [UUID, ...],
        "preview_only": bool = True
    }
    
    Returns:
    {
        "transformation_id": str,
        "code": str,
        "description": str,
        "preview_data": {...},  // Executed results
        "validation": {...},
        "agent_plan": {...}
    }
    """
    current_user, auth_token = user_and_token
    
    user_prompt = params.get("user_prompt")
    if not user_prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_prompt is required")
    
    existing_code = params.get("existing_code")
    transformation_id = params.get("transformation_id")
    chat_history = params.get("chat_history", [])
    selected_node_ids = params.get("selected_node_ids", [str(content_id)])
    
    if isinstance(selected_node_ids, str):
        selected_node_ids = [selected_node_ids]
    
    try:
        # Collect data from all selected ContentNodes
        all_nodes_data = []
        input_data = {}  # For execution
        text_content = ""  # For text-only ContentNodes

        for node_id_str in selected_node_ids:
            try:
                node_id = UUID(node_id_str) if isinstance(node_id_str, str) else node_id_str
            except ValueError:
                logger.warning(f"Invalid UUID format: {node_id_str}")
                continue
                
            node = await ContentNodeService.get_content_node(db, node_id)
            if node and node.content:
                # Collect text content for text-only mode
                if "text" in node.content and node.content["text"]:
                    text_content += node.content["text"] + "\n\n"
                
                # For AI prompt context (limited)
                node_data = {
                    "node_id": str(node.id),
                    "node_name": node.node_metadata.get("name", f"Node {node.id}") if node.node_metadata else f"Node {node.id}",
                    "text": node.content.get("text", ""),
                    "tables": []
                }
                
                # Process tables
                if "tables" in node.content:
                    for table in node.content["tables"]:
                        # Limited for AI context
                        table_data = {
                            "name": table.get("name", "table"),
                            "columns": table.get("columns", []),
                            "column_types": table.get("column_types", {}),
                            "rows": table.get("rows", [])[:10],
                            "row_count": table.get("row_count", len(table.get("rows", [])))
                        }
                        node_data["tables"].append(table_data)
                        
                        # Full data for execution
                        df = python_executor.table_dict_to_dataframe(table)
                        input_data[table["name"]] = df
                
                all_nodes_data.append(node_data)
        
        # If no tables but we have text, add it as 'text' variable
        if not input_data and text_content.strip():
            input_data["text"] = text_content.strip()
            logger.info(f"📝 Using text-only mode for AI transformation: {len(text_content)} characters")
        
        if not all_nodes_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No valid ContentNodes found")
        
        # Initialize Multi-Agent system
        from app.services.multi_agent import AgentMessageBus
        from app.services.gigachat_service import get_gigachat_service
        
        message_bus = None
        gigachat_service = get_gigachat_service()
        
        try:
            message_bus = AgentMessageBus()
            await message_bus.connect()
            logger.info("Using Multi-Agent system with message bus")
        except Exception as e:
            logger.warning(f"Message bus unavailable, using direct mode: {e}")
            message_bus = None
        
        # Use Multi-Agent system for iterative generation
        multi_agent = get_transformation_multi_agent(
            message_bus=message_bus,
            gigachat_service=gigachat_service
        )
        
        # Build context for AI
        context = {
            "nodes_data": all_nodes_data,
            "existing_code": existing_code,
            "chat_history": chat_history,
            "mode": "improve" if existing_code else "create"
        }
        
        # Generate/improve code
        result = await multi_agent.generate_transformation_code(
            nodes_data=all_nodes_data,
            user_prompt=user_prompt,
            existing_code=existing_code,
            chat_history=chat_history
        )
        
        # Auto-execute for preview
        import time
        start_time = time.time()
        
        execution_result = await python_executor.execute_transformation(
            code=result["code"],
            input_data=input_data,
            user_id=str(current_user.id),
            auth_token=auth_token
        )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Convert results to preview format
        preview_tables = []
        if execution_result.success:
            for var_name, df in execution_result.result_dfs.items():
                if hasattr(df, 'to_dict'):
                    row_count = len(df)
                    preview_df = df.head(50)  # First 50 rows for quick preview
                    
                    table_dict = python_executor.dataframe_to_table_dict(
                        df=preview_df,
                        table_name=var_name
                    )
                    table_dict["row_count"] = row_count
                    table_dict["preview_row_count"] = len(preview_df)
                    preview_tables.append(table_dict)
        
        # Disconnect message bus
        if message_bus:
            await message_bus.disconnect()
        
        return {
            "transformation_id": result["transformation_id"],
            "code": result["code"],
            "description": result["description"],
            "preview_data": {
                "tables": preview_tables,
                "execution_time_ms": execution_time_ms
            } if execution_result.success else None,
            "validation": result["validation"],
            "agent_plan": result["agent_plan"]
        }
        
    except ValueError as e:
        logger.error(f"Iterative transformation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
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
            cols = ", ".join(table.get('columns', [])[:5])  # Max 5 columns
            result_summary.append(f"  - {table['name']}: {table.get('row_count', 0)} rows ({cols}...)")
        
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

Важно: название должно быть информативным и отражать суть трансформации, без слова "Transformed"."""
        
        logger.info(f"🤖 Sending prompt to GigaChat ({len(prompt)} chars)")
        
        response = await gigachat.chat_completion([{"role": "user", "content": prompt}])
        
        logger.info(f"📝 AI metadata generation response ({len(response) if response else 0} chars): {response[:500] if response else 'EMPTY'}")
        
        # Parse JSON from response
        import json
        import re
        
        # Try to extract JSON from response (improved regex)
        json_match = re.search(r'\{[^{}]*"name"[^{}]*"description"[^{}]*\}', response, re.DOTALL)
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
        name_match = re.search(r'["\']?name["\']?\s*[:=]\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
        desc_match = re.search(r'["\']?description["\']?\s*[:=]\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
        
        if name_match or desc_match:
            name = name_match.group(1)[:100] if name_match else f"Result: {result_tables[0]['name'] if result_tables else 'Data'}"
            description = desc_match.group(1)[:500] if desc_match else user_prompt[:200] if user_prompt else "Transformation result"
            
            logger.info(f"✅ Extracted AI metadata - name: '{name}', description: '{description[:100]}...'")
            
            return {
                "name": name,
                "description": description
            }
        
        # Fallback if parsing failed
        logger.warning(f"⚠️ Failed to parse AI metadata response, using fallback. Response: {response[:200]}")
        return {
            "name": f"Result: {result_tables[0]['name'] if result_tables else 'Data'}",
            "description": user_prompt[:200] if user_prompt else "Transformation result"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to generate AI metadata: {e}", exc_info=True)
        # Fallback to simple generation
        return {
            "name": f"Result: {result_tables[0]['name'] if result_tables else 'Data'}",
            "description": user_prompt[:200] if user_prompt else "Transformation result"
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
        
        # Execute transformation code with auth token for gb helpers
        execution_result = await python_executor.execute_transformation(
            code=code,
            input_data=input_data,
            user_id=str(current_user.id),
            auth_token=auth_token
        )
        
        if not execution_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transformation execution failed: {execution_result.error}"
            )
        
        # Convert result DataFrames to ContentNode format (multiple tables)
        result_tables = []
        for table_name, df in execution_result.result_dfs.items():
            result_table = python_executor.dataframe_to_table_dict(df, table_name)
            # Keep 'rows' as is - frontend expects it
            # (dataframe_to_table_dict already returns 'rows')
            result_tables.append(result_table)
            logger.info(f"📋 Result table '{table_name}': {result_table.get('row_count', 0)} rows, columns: {result_table.get('columns', [])}")
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
                
                logger.info(f"🔄 UPDATE mode: updating existing node {target_node_id}")
                
                # Update content and lineage
                final_name = ai_metadata.get("name") or existing_node.node_metadata.get('name', f"Transformed: {source_node.node_metadata.get('name', 'Data')}")
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
                            "code_snippet": code,
                            "transformation_id": transformation_id or str(uuid.uuid4()),
                            "timestamp": datetime.utcnow().isoformat()
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
                    "content_node": updated_node,
                    "transform_edge": existing_edges[0] if existing_edges else None,
                    "transform_edges": existing_edges,
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
        final_name = ai_metadata.get("name") or f"Transformed: {source_node.node_metadata.get('name', 'Data')}"
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
                            "code_snippet": code,  # Full code, not truncated
                            "transformation_id": transformation_id or str(uuid.uuid4()),
                            "timestamp": datetime.utcnow().isoformat()
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
            "content_node": new_content_node,
            "transform_edge": created_edges[0] if created_edges else None,  # Return first edge for backward compatibility
            "transform_edges": created_edges,  # Return all edges
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
    """Transform a ContentNode using AI-generated Python code.
    
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
        
        # 2. Generate transformation code via AI agent
        transformation = await transformation_agent.generate_transformation(
            source_content=source_node.content,
            prompt=prompt,
            metadata={
                "board_id": str(source_node.board_id),
                "user_id": str(current_user.id),
            }
        )
        
        # Validate generated code
        validation = await transformation_agent.validate_code(transformation["code"])
        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Generated code validation failed: {validation['errors']}"
            )
        
        # 3. Prepare input data for execution
        input_data = {}
        for table in source_node.content.get("tables", []):
            df = python_executor.table_dict_to_dataframe(table)
            input_data[table["name"]] = df
        
        # 4. Execute transformation code with auth token for gb helpers
        execution_result = await python_executor.execute_transformation(
            code=transformation["code"],
            input_data=input_data,
            user_id=str(current_user.id),
            auth_token=auth_token
        )
        
        if not execution_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transformation execution failed: {execution_result.error}"
            )
        
        # 5. Convert result DataFrames to ContentNode format (multiple tables)
        result_tables = []
        for table_name, df in execution_result.result_dfs.items():
            result_table = python_executor.dataframe_to_table_dict(df, table_name)
            result_tables.append(result_table)
        
        # 6. Create new ContentNode with multiple result tables
        from app.schemas.content_node import ContentNodeCreate, DataLineage
        
        new_content_node = await ContentNodeService.create_content_node(
            db,
            ContentNodeCreate(
                board_id=source_node.board_id,
                content={
                    "text": prompt[:100] if prompt else "",
                    "tables": result_tables
                },
                lineage={
                    "source_node_id": str(content_id),
                    "transformation_id": transformation["transformation_id"],
                    "operation": "transform",
                    "timestamp": transformation["metadata"]["generated_at"],
                    "agent": "transformation_agent",
                    "created_by": str(current_user.id),
                },
                metadata={
                    "name": f"Transformed: {source_node.node_metadata.get('name', 'Data')}",
                    "description": transformation["description"],
                    "transformation_prompt": prompt,
                    "execution_time_ms": execution_result.execution_time_ms,
                    "source_rows": sum(t.get("row_count", 0) for t in source_node.content.get("tables", [])),
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
                    "transformation_id": transformation["transformation_id"],
                    "prompt": prompt,
                    "code": transformation["code"],
                    "execution_time_ms": execution_result.execution_time_ms,
                }
            ),
            current_user.id
        )
        
        await db.commit()
        
        logger.info(f"Transformation completed: {content_id} -> {new_content_node.id}")
        
        return {
            "content_node": new_content_node,
            "transform_edge": transform_edge,
            "transformation": {
                "id": transformation["transformation_id"],
                "code": transformation["code"],
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
    downstream = await ContentNodeService.get_downstream_contents(db, content_id)
    return downstream


@router.post("/{content_id}/visualize", response_model=VisualizeResponse, status_code=status.HTTP_201_CREATED)
async def create_visualization(
    content_id: UUID,
    request: VisualizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create WidgetNode visualization from ContentNode using Reporter Agent.
    
    Workflow:
    1. Reporter Agent analyzes ContentNode (text + tables)
    2. AI generates HTML/CSS/JS code for visualization
    3. Code is validated (security, performance)
    4. WidgetNode is created with VISUALIZATION edge to ContentNode
    
    Args:
        content_id: Source ContentNode to visualize
        request: Visualization options (user_prompt, widget_name, auto_refresh, position)
    
    Returns:
        VisualizeResponse with created WidgetNode and edge IDs
    """
    try:
        # Get ContentNode
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ContentNode {content_id} not found"
            )
        
        # Initialize Reporter Agent
        from app.services.multi_agent.agents.reporter import get_reporter_agent
        from app.services.gigachat_service import get_gigachat_service
        from app.services.multi_agent import AgentMessageBus
        
        message_bus = None
        gigachat_service = get_gigachat_service()
        
        # Try to connect to message bus (optional)
        try:
            message_bus = AgentMessageBus()
            await message_bus.connect()
            logger.info("Using Reporter Agent with message bus")
        except Exception as e:
            logger.warning(f"Message bus unavailable, using direct mode: {e}")
        
        reporter_agent = get_reporter_agent(
            message_bus=message_bus,
            gigachat_service=gigachat_service
        )
        
        # Prepare task for Reporter Agent
        task = {
            "type": "generate_visualization",
            "content_node_id": str(content_id),
            "content_node": {
                "id": str(content_node.id),
                "board_id": str(content_node.board_id),
                "content": content_node.content,
                "metadata": content_node.node_metadata or {},
                "position": content_node.position
            },
            "user_prompt": request.user_prompt
        }
        
        # Generate visualization
        logger.info(f"🎨 Generating visualization for ContentNode {content_id}")
        result = await reporter_agent.process_task(task)
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Visualization generation failed: {result['error']}"
            )
        
        # Create WidgetNode
        from app.services.widget_node_service import WidgetNodeService
        from app.schemas.widget_node import WidgetNodeCreate
        
        widget_name = request.widget_name or result.get("description", "Visualization")
        
        # Determine position (user override or offset from ContentNode)
        if request.position:
            widget_position = request.position
        else:
            node_position = content_node.position or {"x": 0, "y": 0}
            widget_position = {
                "x": node_position.get("x", 0) + 350,  # Offset to the right
                "y": node_position.get("y", 0)
            }
        
        widget_data = WidgetNodeCreate(
            board_id=content_node.board_id,
            name=widget_name,
            description=result.get("description", "AI-generated visualization"),
            html_code=result.get("widget_code", ""),  # Reporter returns full HTML or separate parts
            css_code=result.get("css_code"),
            js_code=result.get("js_code"),
            config=result.get("visualization_config", {}),
            auto_refresh=request.auto_refresh,
            generated_by="reporter_agent",
            generation_prompt=request.user_prompt,
            x=widget_position["x"],
            y=widget_position["y"],
            width=result.get("width", 400),
            height=result.get("height", 300)
        )
        
        widget_node = await WidgetNodeService.create_widget_node(
            db, content_node.board_id, current_user.id, widget_data
        )
        
        # Create VISUALIZATION edge
        from app.schemas.edge import EdgeCreate
        
        edge_data = EdgeCreate(
            source_node_id=content_id,
            source_node_type="ContentNode",
            target_node_id=widget_node.id,
            target_node_type="WidgetNode",
            edge_type="VISUALIZATION",
            label=f"Visualizes: {widget_node.name}",
            transformation_params={
                "description": result.get("description", ""),
                "widget_type": result.get("widget_type", "custom"),
                "auto_refresh": request.auto_refresh,
                "created_by": "reporter_agent"
            }
        )
        
        edge = await EdgeService.create_edge(db, content_node.board_id, edge_data, current_user.id)
        
        # Commit transaction
        await db.commit()
        await db.refresh(widget_node)
        await db.refresh(edge)
        
        # Clean up message bus
        if message_bus:
            await message_bus.disconnect()
        
        logger.info(
            f"✅ Created WidgetNode {widget_node.id} with VISUALIZATION edge from ContentNode {content_id}"
        )
        
        return VisualizeResponse(
            widget_node_id=widget_node.id,
            edge_id=edge.id,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Visualization creation failed: {e}", exc_info=True)
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
    """Generate visualization code iteratively (for interactive editor).
    
    This endpoint is used by the interactive WidgetDialog to:
    1. Generate initial visualization from user prompt
    2. Refine existing visualization based on user feedback
    3. Return HTML/CSS/JS code without creating WidgetNode
    
    The actual WidgetNode is created later via /visualize endpoint
    when user clicks "Save to board".
    
    Args:
        content_id: Source ContentNode to visualize
        request: Iterative generation request (prompt + optional existing code)
    
    Returns:
        VisualizeIterativeResponse with generated HTML/CSS/JS code
    """
    try:
        # Fetch ContentNode
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ContentNode {content_id} not found"
            )
        
        # Verify board access
        board = await BoardService.get_board(db, content_node.board_id, current_user.id)
        if not board:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this board"
            )
        
        # Initialize Reporter Agent
        from app.services.multi_agent.agents.reporter import get_reporter_agent
        from app.services.gigachat_service import get_gigachat_service
        from app.services.multi_agent import AgentMessageBus
        
        message_bus = None
        gigachat_service = get_gigachat_service()
        
        # Try to connect to message bus (optional)
        try:
            message_bus = AgentMessageBus()
            await message_bus.connect()
            logger.info("Using Reporter Agent with message bus")
        except Exception as e:
            logger.warning(f"Message bus unavailable, using direct mode: {e}")
        
        reporter_agent = get_reporter_agent(
            message_bus=message_bus,
            gigachat_service=gigachat_service
        )
        
        # Prepare task for Reporter Agent
        content_data = content_node.content or {}
        tables = content_data.get("tables", [])
        text = content_data.get("text", "")
        
        task = {
            "type": "generate_visualization" if not (request.existing_html or request.existing_css or request.existing_js) else "refine_visualization",
            "content_node_id": str(content_id),
            "content_node": {
                "id": str(content_id),
                "board_id": str(content_node.board_id),
                "content": content_data,
                "metadata": content_node.node_metadata or {},
                "position": content_node.position
            },
            # Explicit data fields for easier access
            "data": {
                "tables": tables,
                "text": text
            },
            "user_prompt": request.user_prompt
        }
        
        # Log data structure for debugging
        if tables:
            logger.info(f"📊 Data tables: {len(tables)} table(s)")
            for idx, table in enumerate(tables):
                logger.info(f"  Table {idx}: {table.get('name', 'Unnamed')} - {table.get('row_count', 0)} rows, {table.get('column_count', 0)} cols")
        if text:
            logger.info(f"📝 Text data: {len(text)} characters")
        
        # Add data access instructions for agent (DYNAMIC API)
        task["data_access_info"] = {
            "description": "Widget can fetch live data from ContentNode via async API",
            "api_method": "window.fetchContentData()",
            "examples": [
                "// Fetch all data (async)",
                "const data = await window.fetchContentData();",
                "const tables = data.tables; // Array of tables",
                "const text = data.text; // Text content",
                "",
                "// Get specific table",
                "const salesTable = await window.getTable('Sales Data');",
                "const firstTable = await window.getTable(0);",
                "",
                "// Auto-refresh example",
                "async function render() {",
                "  const data = await window.fetchContentData();",
                "  // Update chart with data.tables[0].data",
                "}",
                "render(); // Initial render",
                "const refreshId = window.startAutoRefresh(render, 5000); // Auto-refresh every 5s",
                "",
                "// IMPORTANT: All data access must use await/async pattern"
            ]
        }
        
        # Add existing code if iterating
        if request.existing_widget_code:
            task["existing_widget_code"] = request.existing_widget_code
            logger.info(f"📝 Including existing widget_code: {len(request.existing_widget_code)} chars")
        elif request.existing_html or request.existing_css or request.existing_js:
            task["existing_code"] = {
                "html": request.existing_html or "",
                "css": request.existing_css or "",
                "js": request.existing_js or ""
            }
        
        # Add chat history for context
        if request.chat_history:
            task["chat_history"] = request.chat_history
            logger.info(f"💬 Including chat history: {len(request.chat_history)} messages")
        
        # Generate visualization
        logger.info(f"🎨 Generating iterative visualization for ContentNode {content_id}")
        logger.info(f"📋 Task type: {task['type']}, User prompt: '{request.user_prompt}'")
        logger.info(f"🤖 Using Reporter Agent via Multi-Agent System")
        result = await reporter_agent.process_task(task)
        
        # Clean up message bus
        if message_bus:
            try:
                await message_bus.disconnect()
            except:
                pass
        
        # Check result
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Visualization generation failed: {result.get('error', 'Unknown error')}"
            )
        
        # Extract code parts (support both new widget_code and legacy format)
        widget_code = result.get("widget_code")
        html_code = result.get("html_code", "")
        css_code = result.get("css_code", "")
        js_code = result.get("js_code", "")
        widget_name = result.get("widget_name", "")
        description = result.get("description", "AI-generated visualization")
        
        logger.info(
            f"✅ Generated iterative visualization for ContentNode {content_id}"
        )
        logger.info(f"  widget_name: {widget_name}, widget_code: {len(widget_code) if widget_code else 0} chars")
        
        return VisualizeIterativeResponse(
            html_code=html_code,
            css_code=css_code,
            js_code=js_code,
            widget_code=widget_code,
            widget_name=widget_name,
            description=description,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Iterative visualization generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Visualization generation failed: {str(e)}"
        )


@router.post("/{content_id}/analyze-suggestions", response_model=SuggestionAnalysisResponse)
async def analyze_widget_suggestions(
    content_id: UUID,
    request: SuggestionAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyze widget and generate improvement suggestions.
    
    This endpoint uses WidgetSuggestionAgent to provide AI-powered recommendations
    for improving visualizations based on:
    - Data structure analysis (columns, types, cardinality)
    - Widget code analysis (libraries, interactivity, chart type)
    - Chat history context
    
    Args:
        content_id: Source ContentNode to analyze
        request: Analysis request (chat history + current widget code)
    
    Returns:
        SuggestionAnalysisResponse with prioritized suggestions
    """
    try:
        # Verify ContentNode exists and user has access
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ContentNode {content_id} not found"
            )
        
        board = await BoardService.get_board(db, content_node.board_id, current_user.id)
        if not board:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this board"
            )
        
        # Get global MultiAgentEngine instance
        from app.main import get_multi_agent_engine
        
        engine = get_multi_agent_engine()
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MultiAgentEngine not initialized. Check backend logs for Redis/GigaChat connection issues."
            )
        
        if not engine.is_initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MultiAgentEngine initialization failed. Widget Suggestions requires Redis and GigaChat."
            )
        
        suggestions_agent = engine.agents.get("suggestions")
        if not suggestions_agent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WidgetSuggestionAgent not initialized. Check that 'suggestions' is in enable_agents list."
            )
        
        # Execute analysis
        logger.info(f"🔍 Analyzing widget suggestions for ContentNode {content_id}")
        try:
            result = await suggestions_agent.execute_sync(
                db=db,
                content_node_id=str(content_id),
                chat_history=request.chat_history or [],
                current_widget_code=request.current_widget_code,
                max_suggestions=request.max_suggestions or 8
            )
        except Exception as agent_error:
            logger.error(f"❌ WidgetSuggestionAgent execution failed: {agent_error}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis failed: {str(agent_error)}"
            )
        
        # Format response
        return SuggestionAnalysisResponse(
            suggestions=result["suggestions"],
            analysis_summary=result["analysis_summary"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Widget suggestions analysis failed: {e}", exc_info=True)
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
    """Analyze data and generate transformation suggestions using AI agent.
    
    Uses TransformSuggestionsAgent to generate contextual recommendations based on:
    - Current code (if exists) - for iterative improvements
    - Chat history - for understanding user intent
    - Data schema - for column-specific suggestions
    
    Args:
        content_id: Source ContentNode to analyze
        request: {"chat_history": [...], "current_code": str | null}
    
    Returns:
        {"suggestions": [{"id", "label", "prompt", "category", "confidence"}, ...]}
    """
    try:
        # Get ContentNode
        content_node = await ContentNodeService.get_content_node(db, content_id)
        if not content_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ContentNode not found"
            )
        
        chat_history = request.get("chat_history", [])
        current_code = request.get("current_code")
        
        # Prepare input schemas for agent
        tables = content_node.content.get("tables", []) if content_node.content else []
        content_text = content_node.content.get("text", "") if content_node.content else ""
        
        input_schemas = []
        
        # Если есть таблицы — формируем схемы из них
        for table in tables[:2]:  # Limit to first 2 tables for performance
            columns = table.get("columns", [])
            # Handle both list of dicts {"name": "col"} and list of strings ["col"]
            if columns and isinstance(columns[0], dict):
                column_names = [col["name"] for col in columns][:15]
            else:
                column_names = columns[:15]
            
            schema = {
                "name": table.get("name", "df"),
                "columns": column_names,
                "content_text": content_text  # Добавляем текст из ContentNode
            }
            input_schemas.append(schema)
        
        # Если таблиц нет, но есть текст — создаём специальную схему
        if not input_schemas and content_text and len(content_text.strip()) > 50:
            input_schemas.append({
                "name": "text_content",
                "columns": [],
                "content_text": content_text,
                "is_text_only": True
            })
            logger.info(f"📝 No tables, using text content ({len(content_text)} chars)")
        
        logger.info(f"📊 Prepared {len(input_schemas)} input schemas:")
        for schema in input_schemas:
            if schema.get("is_text_only"):
                logger.info(f"   Text content: {len(schema.get('content_text', ''))} chars")
            else:
                logger.info(f"   Table '{schema['name']}': {len(schema['columns'])} columns")
        
        # Initialize TransformSuggestionsAgent
        from app.services.multi_agent.agents.transform_suggestions import TransformSuggestionsAgent
        from app.services.gigachat_service import get_gigachat_service
        
        try:
            gigachat = get_gigachat_service()
        except RuntimeError as e:
            logger.error(f"❌ GigaChat service not initialized: {e}")
            # Fallback: базовые рекомендации
            fallback_suggestions = [
                {
                    "id": "fallback-1",
                    "label": "Фильтрация данных",
                    "prompt": "Отфильтровать строки по условию",
                    "category": "filter",
                    "confidence": 0.7,
                    "description": "Базовая рекомендация (AI недоступен)"
                },
                {
                    "id": "fallback-2",
                    "label": "Группировка",
                    "prompt": "Сгруппировать данные и посчитать агрегаты",
                    "category": "aggregate",
                    "confidence": 0.65,
                    "description": "Базовая рекомендация (AI недоступен)"
                }
            ]
            return {"suggestions": fallback_suggestions, "fallback": True}
        
        suggestions_agent = TransformSuggestionsAgent(gigachat_service=gigachat)
        
        # Generate suggestions via agent
        logger.info(f"🎯 Requesting suggestions for ContentNode {content_id}")
        logger.info(f"   Existing code: {'YES' if current_code else 'NO'}")
        logger.info(f"   Chat history: {len(chat_history)} messages")
        logger.info(f"   Input schemas: {len(input_schemas)} tables")
        
        task = {
            "type": "generate_suggestions",
            "existing_code": current_code,
            "chat_history": chat_history,
            "input_schemas": input_schemas
        }
        
        result = await suggestions_agent.process_task(task)
        
        logger.info(f"📦 Agent result status: {result.get('status')}")
        if result.get("status") != "success":
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ Agent returned error: {error_msg}")
            raise ValueError(f"Agent failed: {error_msg}")
        
        suggestions = result.get("suggestions", [])
        is_fallback = result.get("fallback", False)
        logger.info(f"✅ Generated {len(suggestions)} suggestions (fallback: {is_fallback})")
        
        if is_fallback:
            logger.warning("⚠️ Using fallback suggestions - AI generation failed")
        
        return {"suggestions": suggestions, "fallback": is_fallback}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Transform suggestions analysis failed: {e}", exc_info=True)
        
        # Fallback: базовые рекомендации
        fallback_suggestions = [
            {
                "id": "fallback-1",
                "label": "Фильтрация данных",
                "prompt": "Отфильтровать строки по условию",
                "category": "filter",
                "confidence": 0.7,
                "description": "Базовая рекомендация (AI недоступен)"
            },
            {
                "id": "fallback-2",
                "label": "Группировка",
                "prompt": "Сгруппировать данные и посчитать агрегаты",
                "category": "aggregate",
                "confidence": 0.65,
                "description": "Базовая рекомендация (AI недоступен)"
            }
        ]
        
        return {"suggestions": fallback_suggestions, "fallback": True}

