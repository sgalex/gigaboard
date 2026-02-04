"""
Transformation Multi-Agent Coordinator
Координирует цепочку агентов для генерации кода трансформаций.

Workflow: Analyst → Transformation → Validator → ErrorAnalyzer (if failed) → (retry)
"""

import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from ..multi_agent.agents.analyst import AnalystAgent
from ..multi_agent.agents.transformation import TransformationAgent
from ..multi_agent.agents.validator import ValidatorAgent
from ..multi_agent.agents.error_analyzer import ErrorAnalyzerAgent, get_error_analyzer_agent
from ..multi_agent.message_bus import AgentMessageBus
from ..gigachat_service import GigaChatService


logger = logging.getLogger(__name__)


class TransformationMultiAgent:
    """
    Multi-Agent координатор для генерации кода трансформаций.
    
    Цепочка:
    1. AnalystAgent — анализирует входные данные (типы, статистика)
    2. TransformationAgent — генерирует Python/pandas код
    3. ValidatorAgent — проверяет код (синтаксис, безопасность, dry-run)
    4. Retry — если валидация упала, повторить с ошибками
    """
    
    def __init__(
        self,
        message_bus: Optional[AgentMessageBus] = None,
        gigachat_service: Optional[GigaChatService] = None
    ):
        """
        Args:
            message_bus: Экземпляр AgentMessageBus (опционально, для полной интеграции)
            gigachat_service: GigaChat сервис для AI генерации
        """
        self.message_bus = message_bus
        self.gigachat = gigachat_service
        
        # Создать агенты (если нет message bus, используем direct mode)
        if message_bus and gigachat_service:
            self.analyst = AnalystAgent(message_bus, gigachat_service)
            self.coder = TransformationAgent(message_bus, gigachat_service)
            self.validator = ValidatorAgent(message_bus)
            self.error_analyzer = get_error_analyzer_agent(message_bus, gigachat_service)
        else:
            # Direct mode (без message bus, вызовы напрямую)
            self.analyst = None
            self.coder = None
            self.validator = None
            self.error_analyzer = get_error_analyzer_agent(None, gigachat_service) if gigachat_service else None
        
        self.logger = logging.getLogger("TransformationMultiAgent")
    
    async def generate_transformation_code(
        self,
        nodes_data: list[Dict[str, Any]],
        user_prompt: str,
        max_retries: int = 2,
        existing_code: Optional[str] = None,
        chat_history: Optional[list[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Генерирует код трансформации через цепочку агентов.
        Поддерживает iterative mode: улучшение существующего кода.
        
        Args:
            nodes_data: Список данных от ContentNodes
            user_prompt: Описание трансформации от пользователя
            max_retries: Максимальное количество попыток при ошибках валидации
            existing_code: Существующий код (для режима улучшения)
            chat_history: История диалога (для контекста)
        
        Returns:
            {
                "transformation_id": str,
                "code": str,
                "description": str,
                "validation": {...},
                "agent_plan": {...},
                "analysis": {...}
            }
        """
        start_time = datetime.utcnow()
        transformation_id = str(uuid.uuid4())
        
        self.logger.info(
            f"🚀 Starting transformation code generation: id={transformation_id}, "
            f"prompt='{user_prompt[:50]}...', nodes={len(nodes_data)}"
        )
        
        try:
            # Шаг 1: Анализ данных через AnalystAgent
            self.logger.info("📊 Step 1: Analyzing data with AnalystAgent...")
            analysis = await self._analyze_data(nodes_data, user_prompt)
            
            # Шаг 2: Генерация кода через TransformationAgent (с retry)
            attempt = 0
            validation_errors: list = []
            code_result: Optional[Dict[str, Any]] = None
            validation_result: Optional[Dict[str, Any]] = None
            
            # Адаптивные стратегии
            strategies = [
                {"name": "original", "simplify": False},
                {"name": "simplified", "simplify": True},
                {"name": "basic", "simplify": True, "basic_mode": True},
            ]
            current_strategy_idx = 0
            last_error_analysis: Optional[Dict[str, Any]] = None
            
            while attempt < max_retries * len(strategies):
                strategy = strategies[min(current_strategy_idx, len(strategies) - 1)]
                
                self.logger.info(
                    f"🔨 Step 2: Generating code with TransformationAgent "
                    f"(attempt {attempt + 1}, strategy: {strategy['name']})..."
                )
                
                # Адаптируем промпт в зависимости от стратегии и анализа ошибок
                adapted_prompt = user_prompt
                if strategy.get("simplify") and attempt >= max_retries:
                    self.logger.info("🔄 Simplifying task due to repeated failures...")
                    adapted_prompt = self._simplify_prompt(user_prompt, validation_errors, last_error_analysis)
                elif last_error_analysis and last_error_analysis.get("corrected_approach"):
                    # Даже без simplify, добавляем подсказки от ErrorAnalyzer
                    adapted_prompt = f"{user_prompt}\n\nIMPORTANT: {last_error_analysis['corrected_approach']}"
                
                code_result = await self._generate_code(
                    nodes_data=nodes_data,
                    user_prompt=adapted_prompt,
                    analysis=analysis,
                    previous_errors=validation_errors,
                    existing_code=existing_code,
                    chat_history=chat_history
                )
                
                if not code_result or "code" not in code_result:
                    self.logger.error("❌ Code generation returned empty result")
                    validation_errors.append("Code generation returned empty result")
                    attempt += 1
                    continue
                
                # Шаг 3: Валидация кода через ValidatorAgent
                self.logger.info("✅ Step 3: Validating code with ValidatorAgent...")
                validation_result = await self._validate_code(
                    code=code_result["code"],
                    input_schemas=self._extract_input_schemas_from_nodes(nodes_data),
                    dry_run=True
                )
                
                if validation_result["valid"]:
                    self.logger.info(f"✅ Code validation passed with strategy '{strategy['name']}'!")
                    break
                
                # Если валидация не прошла — анализируем ошибки через ErrorAnalyzerAgent
                validation_errors = validation_result["errors"]
                self.logger.warning(
                    f"❌ Code validation failed (attempt {attempt + 1}, strategy '{strategy['name']}'): {validation_errors}"
                )
                
                # Шаг 3.5: Анализ ошибок через ErrorAnalyzerAgent
                error_analysis = None
                if self.error_analyzer:
                    self.logger.info("🔍 Step 3.5: Analyzing errors with ErrorAnalyzerAgent...")
                    try:
                        error_analysis = await self.error_analyzer.process_task({
                            "type": "analyze_error",
                            "errors": validation_errors,
                            "original_prompt": user_prompt,
                            "failed_code": code_result.get("code", ""),
                            "attempt_number": attempt + 1,
                            "input_schemas": self._extract_input_schemas_from_nodes(nodes_data)
                        })
                        
                        # Сохраняем для использования в следующей итерации
                        last_error_analysis = error_analysis
                        
                        self.logger.info(f"🔍 Error analysis: root_cause='{error_analysis.get('root_cause', 'unknown')}'")
                        self.logger.info(f"🔍 Specific fixes: {error_analysis.get('specific_fixes', [])[:2]}")
                        
                        # Обогащаем validation_errors контекстом от ErrorAnalyzer
                        if error_analysis.get("specific_fixes"):
                            fixes = [f"[FIX] {fix}" for fix in error_analysis["specific_fixes"][:3]]
                            validation_errors = validation_errors + fixes
                        
                        # Используем corrected_approach для следующей попытки
                        if error_analysis.get("corrected_approach"):
                            adapted_prompt = f"{user_prompt}\n\nIMPORTANT: {error_analysis['corrected_approach']}"
                            self.logger.info(f"📝 Adapted prompt with correction: {error_analysis['corrected_approach'][:50]}...")
                        
                    except Exception as e:
                        self.logger.warning(f"Error analysis failed: {e}")
                
                self.logger.info(
                    f"🔄 Will retry with error context and fixes..."
                )
                
                attempt += 1
                
                # Переключаем стратегию после max_retries попыток
                if attempt % max_retries == 0 and attempt > 0:
                    current_strategy_idx += 1
                    if current_strategy_idx < len(strategies):
                        self.logger.info(
                            f"🔀 Switching to strategy: {strategies[current_strategy_idx]['name']}"
                        )
            
            # Если все попытки исчерпаны - пытаемся вернуть хоть что-то полезное
            if not validation_result or not validation_result["valid"]:
                self.logger.warning(
                    f"⚠️ Code generation failed after {attempt} attempts across all strategies"
                )
                
                # Последняя попытка: вернуть простейший код-заглушку
                fallback_code = self._generate_fallback_code(nodes_data, user_prompt, validation_errors)
                
                return {
                    "transformation_id": transformation_id,
                    "code": fallback_code["code"],
                    "description": fallback_code["description"],
                    "validation": {
                        "valid": False,
                        "errors": validation_errors,
                        "warnings": ["This is a fallback code - manual review required"],
                        "is_fallback": True
                    },
                    "agent_plan": {
                        "strategy": "fallback",
                        "attempts": attempt,
                        "status": "partial_success"
                    },
                    "analysis": analysis,
                    "execution_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
                }
            
            # Успех!
            total_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            if not code_result:
                raise ValueError("Code generation failed: no result returned")
            
            result = {
                "transformation_id": transformation_id,
                "code": code_result["code"],
                "description": code_result.get("description", user_prompt),
                "validation": validation_result,
                "agent_plan": {
                    "steps": ["analyze_data", "generate_code", "validate_code"],
                    "attempts": attempt + 1,
                    "total_time_ms": total_time_ms,
                    "agents_used": ["analyst", "transformation", "validator"]
                },
                "analysis": analysis,
                "metadata": {
                    "created_at": datetime.utcnow().isoformat(),
                    "user_prompt": user_prompt,
                    "method": code_result.get("method", "unknown")
                }
            }
            
            self.logger.info(
                f"🎉 Transformation code generated successfully! "
                f"id={transformation_id}, time={total_time_ms}ms, attempts={attempt + 1}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"💥 Transformation code generation failed: {e}", exc_info=True)
            raise
    
    async def _analyze_data(
        self,
        nodes_data: list[Dict[str, Any]],
        user_prompt: str
    ) -> Dict[str, Any]:
        """Анализирует входные данные через AnalystAgent."""
        
        # Если есть message bus, используем агент
        if self.analyst:
            task = {
                "type": "analyze_datanode_content",
                "nodes_data": nodes_data,
                "prompt": user_prompt
            }
            return await self.analyst.process_task(task)
        
        # Fallback: простой анализ без AI
        return self._simple_data_analysis(nodes_data)
    
    def _simple_data_analysis(self, nodes_data: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Простой анализ данных без AI (fallback)."""
        # Собрать все таблицы со всех нод
        all_tables = []
        for node in nodes_data:
            all_tables.extend(node.get("tables", []))
        
        if not all_tables:
            return {
                "column_types": {},
                "suitable_operations": ["filter", "transform"],
                "recommendations": "No tables found in nodes"
            }
        
        # Взять самую большую таблицу
        main_table = max(all_tables, key=lambda t: t.get("row_count", 0))
        
        columns = main_table.get("columns", [])
        rows = main_table.get("rows", [])
        
        # Определить типы колонок (упрощённо)
        column_types = {}
        if rows and columns:
            first_row = rows[0]
            for i, col in enumerate(columns):
                if i < len(first_row):
                    value = first_row[i]
                    if isinstance(value, (int, float)):
                        column_types[col] = "numeric"
                    elif isinstance(value, str):
                        column_types[col] = "categorical"
                    else:
                        column_types[col] = "unknown"
        
        return {
            "table_name": main_table.get("name", "data"),
            "column_types": column_types,
            "row_count": main_table.get("row_count", 0),
            "column_count": len(columns),
            "suitable_operations": ["filter", "group", "aggregate", "sort"],
            "recommendations": f"Table has {len(columns)} columns and {main_table.get('row_count', 0)} rows"
        }
    
    async def _generate_code(
        self,
        nodes_data: list[Dict[str, Any]],
        user_prompt: str,
        analysis: Dict[str, Any],
        previous_errors: Optional[list] = None,
        existing_code: Optional[str] = None,
        chat_history: Optional[list[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Генерирует код через TransformationAgent.
        
        Если existing_code указан — улучшает его, иначе создаёт новый.
        """
        
        # Если есть message bus, используем агент
        if self.coder:
            # Prepare input schemas for TransformationAgent
            input_schemas = self._extract_input_schemas_from_nodes(nodes_data)
            
            self.logger.info(f"Input schemas for TransformationAgent: {len(input_schemas)} tables")
            for schema in input_schemas:
                self.logger.info(f"  Table '{schema['name']}': columns={schema['columns'][:5]}")  # First 5 columns
            
            task = {
                "type": "generate_transformation",
                "description": user_prompt,  # TransformationAgent expects "description"
                "input_schemas": input_schemas,
                "analysis": analysis,
                "previous_errors": previous_errors or [],
                "existing_code": existing_code,  # For iterative improvements
                "chat_history": chat_history or []  # For context
            }
            result = await self.coder.process_task(task)
            
            # Normalize response format (TransformationAgent returns different keys)
            code = result.get("transformation_code", result.get("code", ""))
            
            self.logger.info(f"📤 Code from TransformationAgent (type={type(code).__name__}):")
            if isinstance(code, str):
                self.logger.info(f"   {code[:200]}")
            else:
                self.logger.info(f"   ⚠️ NOT A STRING: {code}")
            
            return {
                "code": code,
                "description": result.get("description", user_prompt),
                "method": "gigachat"
            }
        
        # Fallback: использовать существующий TransformationAgent (mock)
        # Преобразовать nodes_data в старый формат source_content для совместимости
        from ..agents.transformation_agent import transformation_agent
        
        # Собрать все таблицы в один source_content
        all_tables = []
        for node in nodes_data:
            all_tables.extend(node.get("tables", []))
        
        source_content = {"tables": all_tables}
        
        transformation = await transformation_agent.generate_transformation(
            source_content=source_content,
            prompt=user_prompt,
            metadata={
                "analysis": analysis,
                "previous_errors": previous_errors or [],
                "nodes_data": nodes_data
            }
        )
        
        return {
            "code": transformation["code"],
            "description": transformation["description"],
            "method": "mock"
        }
    
    async def _validate_code(
        self,
        code: str,
        input_schemas: list,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Валидирует код через ValidatorAgent."""
        
        # Если есть message bus, используем агент
        if self.validator:
            task = {
                "type": "validate_code",
                "code": code,
                "input_schemas": input_schemas,
                "dry_run": dry_run
            }
            return await self.validator.process_task(task)
        
        # Fallback: простая валидация
        from ..agents.transformation_agent import transformation_agent
        
        validation = await transformation_agent.validate_code(code)
        
        # Добавить dry-run если данные есть
        dry_run_result = None
        if dry_run and input_schemas:
            dry_run_result = {"success": True, "note": "Dry-run skipped in fallback mode"}
        
        return {
            "valid": validation["valid"],
            "errors": validation.get("errors", []),
            "warnings": [],
            "suggestions": [],
            "dry_run_result": dry_run_result
        }
    
    def _extract_input_schemas(self, source_content: Dict[str, Any]) -> list:
        """Извлекает схемы таблиц для валидации (старый метод для совместимости)."""
        tables = source_content.get("tables", [])
        
        schemas = []
        for table in tables:
            schemas.append({
                "name": table.get("name", "table"),
                "columns": table.get("columns", []),
                "sample_data": table.get("rows", [])[:5]  # Первые 5 строк для dry-run
            })
        
        return schemas
    
    def _extract_input_schemas_from_nodes(self, nodes_data: list[Dict[str, Any]]) -> list:
        """Извлекает схемы таблиц из nodes_data для валидации."""
        schemas = []
        for node in nodes_data:
            # Добавляем информацию о тексте ноды, если есть
            node_text = node.get("text", "")
            tables = node.get("tables", [])
            
            # Если таблиц нет, но есть текст — создаём text-only схему
            if not tables and node_text and len(node_text.strip()) > 50:
                schemas.append({
                    "name": "text_content",
                    "columns": [],
                    "is_text_only": True,
                    "content_text": node_text,
                    "node_id": node.get("node_id"),
                    "node_name": node.get("node_name"),
                })
                continue
            
            for table in tables:
                schemas.append({
                    "name": table.get("name", "table"),
                    "columns": table.get("columns", []),
                    "column_types": table.get("column_types", {}),
                    "sample_data": table.get("rows", [])[:5],  # Первые 5 строк для dry-run
                    "node_id": node.get("node_id"),
                    "node_name": node.get("node_name"),
                    "node_text": node_text  # Текст из ContentNode
                })
        
        return schemas
    
    def _simplify_prompt(
        self, 
        original_prompt: str, 
        errors: list,
        error_analysis: Optional[Dict[str, Any]] = None
    ) -> str:
        """Упрощает промпт на основе ошибок валидации и анализа ошибок."""
        
        # Если есть анализ от ErrorAnalyzerAgent — используем его
        if error_analysis:
            hints = []
            
            if error_analysis.get("corrected_approach"):
                hints.append(error_analysis["corrected_approach"])
            
            if error_analysis.get("simplified_task"):
                hints.append(f"Simplified task: {error_analysis['simplified_task']}")
            
            if error_analysis.get("code_hints"):
                hints.append(f"Code pattern: {error_analysis['code_hints'][0]}")
            
            if hints:
                return f"{original_prompt}\n\nCRITICAL INSTRUCTIONS:\n" + "\n".join(f"- {h}" for h in hints)
        
        # Fallback: анализируем типичные ошибки
        common_issues = {
            "DataFrame variables": "Create simple transformation with df_result variable",
            "syntax": "Use basic pandas operations only",
            "import": "Use only pandas and numpy",
            "multiple outputs": "Create single output dataframe df_result",
            "not defined": "Use df for single input or df1, df2, df3 for multiple inputs"
        }
        
        simplified_hints = []
        for error in errors:
            for issue_key, hint in common_issues.items():
                if issue_key.lower() in error.lower():
                    simplified_hints.append(hint)
                    break
        
        if simplified_hints:
            return f"{original_prompt}\n\nIMPORTANT: {' '.join(set(simplified_hints))}"
        
        # Общее упрощение
        return f"{original_prompt}\n\nIMPORTANT: Use simplest possible pandas code, single output df_result"
    
    def _generate_fallback_code(
        self, 
        nodes_data: list[Dict[str, Any]], 
        user_prompt: str, 
        errors: list
    ) -> Dict[str, Any]:
        """Генерирует безопасный fallback код когда все попытки провалились."""
        self.logger.info("🛟 Generating fallback code as last resort...")
        
        # Извлекаем первую таблицу
        first_table = None
        for node in nodes_data:
            tables = node.get("tables", [])
            if tables:
                first_table = tables[0]
                break
        
        if not first_table:
            return {
                "code": "# No input data available\ndf_result = pd.DataFrame()",
                "description": "Fallback: Empty DataFrame (no input data)"
            }
        
        table_name = first_table.get("name", "data")
        
        # Простейший код - просто копируем данные
        fallback_code = f"""# Fallback transformation: pass-through
# Original request: {user_prompt[:100]}
# Generation failed with errors: {', '.join(errors[:2])}
df_result = df.copy()"""
        
        return {
            "code": fallback_code,
            "description": f"Fallback: Data pass-through (generation failed after multiple attempts)"
        }


# Singleton instance
_transformation_multi_agent_instance = None

def get_transformation_multi_agent(
    message_bus: Optional[AgentMessageBus] = None,
    gigachat_service: Optional[GigaChatService] = None
) -> TransformationMultiAgent:
    """Получить singleton instance TransformationMultiAgent."""
    global _transformation_multi_agent_instance
    if _transformation_multi_agent_instance is None:
        _transformation_multi_agent_instance = TransformationMultiAgent(
            message_bus, gigachat_service
        )
    return _transformation_multi_agent_instance
