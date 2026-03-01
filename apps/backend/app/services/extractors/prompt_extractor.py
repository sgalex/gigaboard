"""Prompt extractor - handles AI prompt-based data generation."""
import json
import logging
from typing import Any

import pandas as pd

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class PromptExtractor(BaseExtractor):
    """Extractor for AI prompt sources."""
    
    async def extract(
        self,
        config: dict[str, Any],
        params: dict[str, Any] | None = None
    ) -> ExtractionResult:
        """Extract data using AI prompt.
        
        Config format:
            {
                "prompt": str,  # User prompt
                "model": str,  # optional, AI model to use
                "system_prompt": str  # optional system prompt
            }
        
        Params format:
            {
                "temperature": float,  # optional
                "max_tokens": int  # optional
            }
        
        Note: This is a stub for Phase 2. Actual GigaChat integration
        will be implemented later.
        """
        result = ExtractionResult()
        params = params or {}
        
        try:
            prompt = config.get("prompt")
            logger.info(f"🤖 PromptExtractor started with prompt: {prompt[:100] if prompt else 'None'}...")
            
            if not prompt:
                logger.error("❌ No prompt provided")
                result.errors.append("prompt is required")
                return result
            
            # Get orchestrator or fallback to gigachat_service
            orchestrator = params.get("orchestrator")
            gigachat_service = params.get("gigachat_service")
            source = params.get("source")
            
            if not orchestrator and not gigachat_service:
                result.errors.append("Either orchestrator (multi-agent) or gigachat_service is required")
                return result
            
            # Use Multi-Agent system if available, otherwise fallback to simple GigaChat
            if orchestrator:
                if not source:
                    result.errors.append("source node is required for multi-agent mode")
                    return result
                
                logger.info("Using Multi-Agent system for prompt extraction")
                
                # Pass prompt as-is to PlannerAgent - let it decide if it needs search, generation, or other agents
                # PlannerAgent will analyze the request and choose the appropriate workflow:
                # - Search-based: "Найди статистику..." → SearchAgent → ResearcherAgent → AnalystAgent
                # - Generation-based: "Создай таблицу..." → AnalystAgent (generate_data)
                # - API-based: "Загрузи данные с URL..." → ResearcherAgent (fetch_from_api)
                
                # Use Multi-Agent system to process the prompt
                try:
                    full_response = ""
                    
                    # Process request through orchestrator (streaming)
                    async for chunk in orchestrator.process_user_request(
                        user_id=source.created_by,
                        board_id=source.board_id,
                        user_message=prompt,  # Pass prompt as-is to PlannerAgent
                        chat_session_id=None,  # No chat session for extraction
                        selected_node_ids=None
                    ):
                        full_response += chunk
                    
                    # Получаем aggregated результаты из последней сессии
                    # Orchestrator уже агрегировал результаты всех агентов
                    aggregated_content, extracted_tables = await self._aggregate_agent_results(
                        orchestrator=orchestrator,
                        full_response=full_response
                    )
                    
                    # Сохраняем aggregated контент как текст ContentNode
                    result.text = aggregated_content
                    
                    # Добавляем извлечённые таблицы (конвертируем в формат ContentTable)
                    if extracted_tables:
                        converted_tables = self._convert_to_content_tables(extracted_tables)
                        result.tables.extend(converted_tables)
                        logger.info(f"✅ Added {len(converted_tables)} tables to extraction result")
                    
                    result.metadata.update({
                        "prompt": prompt[:200],
                        "model": "multi-agent-system",
                        "tables_extracted": len(extracted_tables),
                        "status": "success"
                    })
                    
                    logger.info("PromptExtractor: Successfully generated data via Multi-Agent system")
                    
                except Exception as ai_error:
                    logger.exception(f"Multi-Agent processing failed: {ai_error}")
                    result.errors.append(f"AI generation failed: {str(ai_error)}")
            
            else:
                # Fallback: Simple GigaChat mode
                logger.info("Using simple GigaChat mode for prompt extraction (fallback)")
                
                # Build system prompt for data generation
                system_prompt = config.get(
                    "system_prompt",
                    "You are a data generation assistant. Generate structured data based on user requests. "
                    "Return data in JSON format as either: 1) Array of objects for tables, or 2) Plain text. "
                    "Be concise and accurate."
                )
                
                # Call GigaChat
                try:
                    ai_response = await gigachat_service.generate_response(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=params.get("temperature", 0.7),
                        max_tokens=params.get("max_tokens", 2000)
                    )
                    
                    # Try to parse as JSON for table data
                    await self._parse_ai_response(ai_response, result)
                    
                    result.metadata.update({
                        "prompt": prompt[:200],
                        "model": config.get("model", "gigachat"),
                        "status": "success"
                    })
                    
                    logger.info("PromptExtractor: Successfully generated data via GigaChat (fallback mode)")
                    
                except Exception as ai_error:
                    logger.exception(f"GigaChat call failed: {ai_error}")
                    result.errors.append(f"AI generation failed: {str(ai_error)}")
            
        except Exception as e:
            logger.exception(f"Prompt extraction failed: {e}")
            result.errors.append(f"Prompt error: {str(e)}")
        
        return result
    
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate prompt source configuration."""
        errors = []
        
        if not config.get("prompt"):
            errors.append("prompt is required")
        
        return len(errors) == 0, errors
    
    async def _parse_ai_response(
        self,
        ai_response: str,
        result: ExtractionResult
    ):
        """Parse AI response - try JSON first, fallback to text."""
        # Try to extract JSON from response
        json_start = ai_response.find('[') if '[' in ai_response else ai_response.find('{')
        json_end = ai_response.rfind(']') + 1 if ']' in ai_response else ai_response.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            try:
                json_str = ai_response[json_start:json_end]
                data = json.loads(json_str)
                
                # If it's a list of dicts, create table
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    df = pd.DataFrame(data)
                    table = self._create_table(
                        name="ai_generated_data",
                        columns=[str(col) for col in df.columns],
                        rows=df.fillna("").values.tolist(),
                        metadata={"source": "ai_prompt", "rows": len(df)}
                    )
                    result.tables.append(table)
                    result.text = f"Generated {len(df)} rows with {len(df.columns)} columns\n\n{ai_response[:500]}"
                    return
                
            except json.JSONDecodeError:
                pass  # Fallback to text
        
        # Fallback: treat as text
        result.text = ai_response
    
    async def _aggregate_agent_results(
        self,
        orchestrator,
        full_response: str
    ) -> tuple[str, list[dict]]:
        """Агрегировать результаты всех агентов и извлечь структурированные данные.
        
        Извлекает:
        - Текстовый контент для ContentNode.text
        - Структурированные таблицы из AnalystAgent для ContentNode.tables
        
        Args:
            orchestrator: MultiAgentOrchestrator instance
            full_response: Streaming ответ для пользователя
            
        Returns:
            tuple[str, list[dict]]: (text_content, tables)
        """
        tables = []
        analyst_text = ""  # Текст от AnalystAgent
        
        try:
            # Получаем session_id из orchestrator
            session_id = orchestrator.current_session_id
            if not session_id:
                logger.warning("No session_id in orchestrator")
                return full_response, tables
            
            # Получаем AgentSession с результатами
            session = await orchestrator.session_manager.get_session(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found")
                return full_response, tables
            
            logger.info(f"📊 Extracting structured data from session {session_id}")
            logger.info(f"   Status: {session.status}")
            logger.info(f"   Task results: {len(session.results) if session.results else 0}")
            
            # Извлекаем структурированные данные из results
            if session.results:
                for task_idx, task_result in session.results.items():
                    agent_name = task_result.get("agent", "unknown")
                    
                    # Ищем результаты от AnalystAgent или TransformationAgent
                    if agent_name in ["analyst", "transformation"]:
                        logger.info(f"   📋 Found {agent_name} result in task {task_idx}")
                        logger.info(f"   🔍 {agent_name.capitalize()} result keys: {list(task_result.keys())}")
                        
                        # Проверяем статус результата внутри "result"
                        if isinstance(task_result.get("result"), dict):
                            result_status = task_result["result"].get("status")
                            if result_status == "error":
                                error_msg = task_result["result"].get("error", "Unknown error")
                                logger.warning(f"      ⚠️ {agent_name.capitalize()} returned error: {error_msg}")
                                logger.info(f"      ⏭️ Skipping {agent_name} result due to error status")
                                continue
                        
                        # Логируем ВСЕ содержимое для диагностики
                        for key, value in task_result.items():
                            if key not in ["agent", "status"]:
                                value_preview = str(value)[:200] if value else "None"
                                logger.info(f"      • {key}: {value_preview}...")
                        
                        # Agent может возвращать данные в разных форматах
                        # Данные могут быть:
                        # 1. На верхнем уровне task_result (новый формат после исправления промпта)
                        # 2. Во вложенном task_result["result"] (старый формат)
                        # 3. В task_result["result"]["message"] как JSON строка (legacy)
                        
                        analyst_data = {}
                        
                        # Приоритет 1: tables на верхнем уровне
                        if "tables" in task_result:
                            analyst_data = task_result
                            logger.info(f"      ✅ Found tables at top level")
                        # Приоритет 2: tables во вложенном result
                        elif isinstance(task_result.get("result"), dict):
                            result_data = task_result["result"]
                            if "tables" in result_data:
                                analyst_data = result_data
                                logger.info(f"      ✅ Found tables in result")
                            # Приоритет 3: JSON в message (legacy)
                            elif "message" in result_data:
                                message = result_data["message"]
                                # Убираем markdown блоки ```json ... ```
                                if "```json" in message:
                                    message = message.split("```json")[1].split("```")[0].strip()
                                elif "```" in message:
                                    message = message.split("```")[1].split("```")[0].strip()
                                
                                try:
                                    parsed_data = json.loads(message)
                                    logger.info(f"      ✅ Parsed JSON from message: keys={list(parsed_data.keys())}")
                                    analyst_data = parsed_data
                                except json.JSONDecodeError as e:
                                    logger.warning(f"      ⚠️ Failed to parse JSON from message: {e}")
                        
                        # Извлекаем текстовое описание от AnalystAgent
                        if "text" in analyst_data:
                            analyst_text = analyst_data["text"]
                            logger.info(f"      ✅ Extracted text: {len(analyst_text)} chars")
                        
                        # Проверяем все возможные поля со структурированными данными
                        
                        # 1. Прямые таблицы в "tables" (НОВЫЙ ФОРМАТ)
                        if "tables" in analyst_data:
                            tables_array = analyst_data["tables"]
                            logger.info(f"      📊 Found tables array: type={type(tables_array)}, length={len(tables_array) if isinstance(tables_array, list) else 'N/A'}")
                            
                            if isinstance(tables_array, list):
                                for idx, table_data in enumerate(tables_array):
                                    logger.info(f"      📋 Table {idx}: type={type(table_data)}, keys={list(table_data.keys()) if isinstance(table_data, dict) else 'N/A'}")
                                    
                                    # Проверяем что таблица имеет правильную структуру
                                    if isinstance(table_data, dict) and "columns" in table_data and "rows" in table_data:
                                        tables.append(table_data)
                                        logger.info(f"      ✅ Extracted table: {table_data.get('name', 'unnamed')}")
                                    else:
                                        logger.warning(f"      ⚠️ Invalid table structure at index {idx}: missing 'columns' or 'rows'")
                            else:
                                logger.warning(f"      ⚠️ 'tables' is not a list: {type(tables_array)}")
                        
                        # 2. cinemas (кинотеатры с просмотрами)
                        if "cinemas" in analyst_data:
                            table = self._convert_to_table(
                                name="cinemas",
                                data=analyst_data["cinemas"]
                            )
                            if table:
                                tables.append(table)
                                logger.info(f"      ✅ Extracted cinemas table")
                        
                        # 3. comparison_table (топ фреймворков, компаний и т.д.)
                        if "comparison_table" in analyst_data:
                            table = self._convert_to_table(
                                name="comparison",
                                data=analyst_data["comparison_table"],
                                columns=analyst_data.get("columns", None)
                            )
                            if table:
                                tables.append(table)
                                logger.info(f"      ✅ Extracted comparison_table")
                        
                        # 4. performance_comparison (бенчмарки)
                        if "performance_comparison" in analyst_data:
                            table = self._convert_to_table(
                                name="performance_benchmarks",
                                data=analyst_data["performance_comparison"]
                            )
                            if table:
                                tables.append(table)
                                logger.info(f"      ✅ Extracted performance_comparison")
                        
                        # 5. companies_using_rust_in_production / companies_adopting_rust
                        company_keys = ["companies_using_rust_in_production", "companies_adopting_rust", "company_usage"]
                        for key in company_keys:
                            if key in analyst_data:
                                table = self._convert_to_table(
                                    name="companies",
                                    data=analyst_data[key]
                                )
                                if table:
                                    tables.append(table)
                                    logger.info(f"      ✅ Extracted {key}")
                                break
                        
                        # 6. extracted_entities (общий формат)
                        if "extracted_entities" in analyst_data:
                            table = self._convert_to_table(
                                name="entities",
                                data=analyst_data["extracted_entities"]
                            )
                            if table:
                                tables.append(table)
                                logger.info(f"      ✅ Extracted entities")
            
            logger.info(f"✅ Extracted {len(tables)} tables from analyst results")
            
            # Формируем текстовый контент
            # Приоритет: текст от AnalystAgent > streaming response
            content_parts = []
            
            # Добавляем текст от AnalystAgent (если есть)
            if analyst_text:
                content_parts.append(analyst_text)
            else:
                # Fallback на streaming response
                content_parts.append("# Multi-Agent System Results\n")
                content_parts.append(f"\n{full_response}\n")
            
            if tables and not analyst_text:
                content_parts.append(f"\n---\n*Извлечено {len(tables)} таблиц(ы) из анализа.*\n")
            
            return "\n".join(content_parts), tables
            
        except Exception as e:
            logger.exception(f"Error extracting structured data: {e}")
            return full_response, tables
    
    def _convert_to_table(
        self,
        name: str,
        data: list | dict,
        columns: list | None = None
    ) -> dict | None:
        """Конвертировать данные analyst в формат таблицы ContentNode.
        
        Args:
            name: Имя таблицы
            data: Данные (list of dicts или dict)
            columns: Опциональный список колонок
            
        Returns:
            dict: Table в формате ContentNode или None
        """
        try:
            if not data:
                return None
            
            # Если data - это список словарей (стандартный формат)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                df = pd.DataFrame(data)
                
                # Используем columns если указаны, иначе из DataFrame
                cols = columns if columns else [str(c) for c in df.columns]
                
                return self._create_table(
                    name=name,
                    columns=cols,
                    rows=df.fillna("").values.tolist(),
                    metadata={"source": "analyst", "rows": len(df)}
                )
            
            # Если data - это словарь, преобразуем в список
            elif isinstance(data, dict):
                # Пробуем развернуть словарь в список записей
                records = [{"key": k, "value": v} for k, v in data.items()]
                df = pd.DataFrame(records)
                
                return self._create_table(
                    name=name,
                    columns=["key", "value"],
                    rows=df.values.tolist(),
                    metadata={"source": "analyst", "rows": len(df)}
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not convert data to table: {e}")
            return None
    
    def _convert_to_content_tables(self, analyst_tables: list[dict]) -> list[dict]:
        """
        Конвертирует таблицы из формата AnalystAgent в unified ContentTable format.
        
        Unified format:
            {
                "id": "uuid",
                "name": "table_name",
                "columns": [{"name": "Column1", "type": "string"}, ...],
                "rows": [{"Column1": "value1", "Column2": 123}, ...]
            }
        """
        from uuid import uuid4
        
        converted = []
        
        for table in analyst_tables:
            try:
                name = table.get("name", "таблица")
                columns = table.get("columns", [])
                rows = table.get("rows", [])
                
                # Normalize columns: ["Language", "Year"] → [{"name": "Language", "type": "string"}, ...]
                if columns and isinstance(columns[0], str):
                    converted_columns = [
                        {"name": col, "type": "string"} 
                        for col in columns
                    ]
                else:
                    converted_columns = columns
                
                col_names = [c["name"] for c in converted_columns]
                
                # Normalize rows to dict format
                converted_rows = []
                for row in rows:
                    if isinstance(row, list):
                        converted_rows.append({col_names[j]: v for j, v in enumerate(row) if j < len(col_names)})
                    elif isinstance(row, dict):
                        converted_rows.append(row)
                
                converted_table = {
                    "id": str(uuid4()),
                    "name": name,
                    "columns": converted_columns,
                    "rows": converted_rows,
                    "row_count": len(converted_rows),
                    "column_count": len(converted_columns),
                    "preview_row_count": len(converted_rows) if len(converted_rows) <= 100 else 100
                }
                logger.info(f"      🔄 Converted table '{name}': {converted_table['row_count']} rows × {converted_table['column_count']} cols")
                converted.append(converted_table)
                
            except Exception as e:
                logger.warning(f"Failed to convert table {table.get('name', 'unknown')}: {e}")
                continue
        
        return converted
