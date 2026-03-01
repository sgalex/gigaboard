"""
Validator Agent - Code Validation & Security Checks
Проверяет сгенерированный код на безопасность, синтаксис и логику.
"""

import logging
import json
import ast
import re
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from .base import BaseAgent
from ..message_bus import AgentMessageBus


logger = logging.getLogger(__name__)


# System Prompt для Validator Agent
VALIDATOR_SYSTEM_PROMPT = '''
Вы — Validator Agent (Агент-Валидатор) в системе GigaBoard Multi-Agent.

**ОСНОВНАЯ РОЛЬ**: Проверка сгенерированного Python кода на безопасность, корректность и производительность.

**ПРОВЕРКИ**:

1. **Синтаксис**: Код должен быть валидным Python
2. **Безопасность**: Запрещены eval, exec, file I/O, network, subprocess
3. **Логика**: df_result должен существовать и быть DataFrame
4. **Колонки**: Используемые колонки должны существовать во входных данных
5. **Типы данных**: Операции должны быть совместимы с типами
6. **Производительность**: Нет N+1 запросов, эффективные операции pandas

**ЗАПРЕЩЁННЫЕ ПАТТЕРНЫ**:
- eval(), exec(), compile()
- __import__(), importlib
- open(), file I/O
- subprocess, os.system()
- network calls (requests, urllib, socket)
- pickle, shelve (unsafe serialization)

**ФОРМАТ ВЫВОДА**:
{
  "valid": true,
  "errors": [],
  "warnings": [
    {"type": "performance", "message": "Consider using .loc instead of chained indexing"},
    {"type": "column", "message": "Column 'amount' may not exist in all datasets"}
  ],
  "suggestions": [
    "Add error handling for missing columns",
    "Use .copy() to avoid SettingWithCopyWarning"
  ],
  "dry_run_result": {
    "success": true,
    "output_shape": [450, 5],
    "execution_time_ms": 12
  }
}

**УРОВНИ СЕРЬЁЗНОСТИ**:
- ERROR: Код не может быть выполнен или небезопасен
- WARNING: Код работает, но может быть улучшен
- INFO: Рекомендации по best practices
'''


class ValidatorAgent(BaseAgent):
    """
    Validator Agent - валидация Python кода для трансформаций.
    
    Проверяет:
    - Синтаксическую корректность
    - Безопасность (запрещённые операции)
    - Логическую корректность (df_result exists)
    - Тестирование на sample данных
    """
    
    # Запрещённые паттерны (расширенный список)
    FORBIDDEN_PATTERNS = [
        (r'\beval\s*\(', 'eval() is forbidden'),
        (r'\bexec\s*\(', 'exec() is forbidden'),
        (r'\b__import__\s*\(', '__import__() is forbidden'),
        (r'\bcompile\s*\(', 'compile() is forbidden'),
        (r'\bsubprocess\.', 'subprocess module is forbidden'),
        (r'\bos\.system\(', 'os.system() is forbidden'),
        (r'\bos\.popen\(', 'os.popen() is forbidden'),
        (r'\bopen\s*\(', 'File I/O is forbidden'),
        (r'\bfile\s*\(', 'File I/O is forbidden'),
        (r'\brequests\.', 'HTTP requests are forbidden'),
        (r'\burllib\.', 'HTTP requests are forbidden'),
        (r'\bsocket\.', 'Socket operations are forbidden'),
        (r'\bpickle\.', 'pickle is forbidden (security risk)'),
        (r'\bshelve\.', 'shelve is forbidden (security risk)'),
    ]
    
    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service=None,
        system_prompt: Optional[str] = None
    ):
        super().__init__(
            agent_name="validator",
            message_bus=message_bus,
            system_prompt=system_prompt
        )
        self.gigachat = gigachat_service
        
    def _get_default_system_prompt(self) -> str:
        return VALIDATOR_SYSTEM_PROMPT
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает задачу валидации.
        
        Args:
            task: {
                "type": "validate_code",
                "code": "df_result = df[df['amount'] > 100]",
                "input_schemas": [{"columns": ["id", "amount"], "sample_data": [...]}],
                "dry_run": true
            }
        
        Returns:
            {
                "valid": bool,
                "errors": list,
                "warnings": list,
                "suggestions": list,
                "dry_run_result": {...}
            }
        """
        task_type = task.get("type")
        
        if task_type == "validate_code":
            return await self._validate_code(task, context)
        elif task_type == "validate":
            # General validation from Orchestrator — validate aggregated results
            return await self._validate_aggregated(task, context)
        else:
            # Planner may assign validator as a plan step without type.
            # Treat as generic validation/check — return success.
            self.logger.info(f"Validator called as plan step (task_type={task_type}), performing generic check")
            description = task.get("description", "")
            return self._success_payload(
                narrative_text=f"Validation check: {description or 'OK'}",
                metadata={"task_type": task_type, "generic": True},
            )

    async def _validate_aggregated(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Валидирует агрегированные результаты от оркестратора.
        
        Проверяет code_blocks на безопасность если они есть,
        иначе возвращает valid=True.
        """
        aggregated = task.get("aggregated_payload", {})
        code_blocks = aggregated.get("code_blocks", [])
        
        all_errors = []
        all_warnings = []
        
        for cb in code_blocks:
            code = cb.get("code", "")
            lang = cb.get("language", "python")
            
            if lang == "python" and code.strip():
                # Проверяем синтаксис и безопасность Python-кода
                syntax_check = self._check_syntax(code)
                if not syntax_check["valid"]:
                    all_errors.extend(syntax_check["errors"])
                
                security_check = self._check_security(code)
                if not security_check["valid"]:
                    all_errors.extend(security_check["errors"])
        
        valid = len(all_errors) == 0
        
        self.logger.info(
            f"Aggregated validation: valid={valid}, "
            f"code_blocks={len(code_blocks)}, errors={len(all_errors)}"
        )
        
        return {
            "valid": valid,
            "errors": all_errors,
            "warnings": all_warnings,
        }
    
    async def _validate_code(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Валидирует Python код трансформации."""
        
        code = task.get("code", "")
        input_schemas = task.get("input_schemas", [])
        dry_run = task.get("dry_run", True)
        
        errors = []
        warnings = []
        suggestions = []
        
        # 1. Синтаксическая проверка
        syntax_check = self._check_syntax(code)
        if not syntax_check["valid"]:
            errors.extend(syntax_check["errors"])
        
        # 2. Проверка безопасности
        security_check = self._check_security(code)
        if not security_check["valid"]:
            errors.extend(security_check["errors"])
        
        # 3. Логическая проверка
        logic_check = self._check_logic(code)
        if not logic_check["valid"]:
            errors.extend(logic_check["errors"])
        warnings.extend(logic_check.get("warnings", []))
        
        # 4. Проверка колонок
        if input_schemas:
            column_check = self._check_columns(code, input_schemas)
            warnings.extend(column_check.get("warnings", []))
            suggestions.extend(column_check.get("suggestions", []))
        
        # 5. Dry run (если запрошен и нет критических ошибок)
        dry_run_result = None
        if dry_run and not errors and input_schemas:
            dry_run_result = await self._dry_run_code(code, input_schemas)
            if not dry_run_result["success"]:
                errors.append(f"Dry run failed: {dry_run_result['error']}")
        
        valid = len(errors) == 0
        
        self.logger.info(
            f"Code validation: valid={valid}, errors={len(errors)}, "
            f"warnings={len(warnings)}, suggestions={len(suggestions)}"
        )
        
        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "dry_run_result": dry_run_result
        }
    
    def _check_syntax(self, code: str) -> Dict[str, Any]:
        """Проверяет синтаксис Python кода."""
        try:
            ast.parse(code)
            return {"valid": True, "errors": []}
        except SyntaxError as e:
            return {
                "valid": False,
                "errors": [f"Syntax error at line {e.lineno}: {e.msg}"]
            }
    
    def _check_security(self, code: str) -> Dict[str, Any]:
        """Проверяет код на запрещённые операции."""
        errors = []
        
        for pattern, message in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                errors.append(f"Security violation: {message}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _check_logic(self, code: str) -> Dict[str, Any]:
        """Проверяет логическую корректность кода."""
        errors = []
        warnings = []
        
        # Проверка наличия переменных с префиксом df_
        df_vars_match = re.findall(r'\bdf_\w+\s*=', code)
        self.logger.info(f"🔍 Found df_ variables in code: {df_vars_match}")
        
        if not df_vars_match:
            errors.append("Code must define at least one DataFrame variable starting with 'df_' (e.g., df_result, df_result1)")
            self.logger.warning(f"⚠️ Code does not define any df_ variables. Code:\n{code[:200]}...")
        
        # Проверка на чейнинг (предупреждение)
        if re.search(r'\]\[', code):
            warnings.append({
                "type": "performance",
                "message": "Chained indexing detected. Consider using .loc[] for better performance"
            })
        
        # Проверка на SettingWithCopyWarning
        if re.search(r'df\[.*\]\s*=', code) and 'copy()' not in code:
            warnings.append({
                "type": "pandas",
                "message": "Consider using .copy() to avoid SettingWithCopyWarning"
            })
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _check_columns(
        self,
        code: str,
        input_schemas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Проверяет используемые колонки в коде."""
        warnings = []
        suggestions = []
        
        # Извлечь все колонки из схем
        available_columns = set()
        for schema in input_schemas:
            columns = schema.get("columns", [])
            # Handle both old (string array) and new (dict array) formats
            if columns and isinstance(columns[0], dict):
                # New format: [{"name": "col", "type": "string"}]
                available_columns.update(col["name"] for col in columns)
            else:
                # Old format: ["col1", "col2"]
                available_columns.update(columns)
        
        # Найти все упоминания колонок в коде (простой поиск в строках)
        # Паттерн: df['column'] или df["column"]
        column_references = re.findall(r"['\"](\\w+)['\"]", code)
        
        for col in column_references:
            if col not in available_columns:
                warnings.append({
                    "type": "column",
                    "message": f"Column '{col}' may not exist in input data. Available: {list(available_columns)}"
                })
                suggestions.append(f"Add error handling for missing column '{col}'")
        
        return {
            "warnings": warnings,
            "suggestions": suggestions
        }
    
    async def _dry_run_code(
        self,
        code: str,
        input_schemas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Выполняет код на sample данных для проверки."""
        try:
            # Mock для GigaBoard helpers (gb модуль)
            class MockGBHelpers:
                """Mock для gb.ai_resolve_batch() в dry-run валидации."""
                def ai_resolve_batch(self, values, task_description, result_format="string", chunk_size=50):
                    # Возвращаем mock данные того же размера
                    return [None] * len(values)
                
                def ai_resolve_single(self, value, task_description, result_format="string"):
                    return None
            
            # Создать sample DataFrames из схем
            namespace = {
                'pd': pd,
                'np': np,
                'gb': MockGBHelpers(),  # Добавляем mock gb модуля
                '__builtins__': __builtins__  # Доступ к встроенным функциям Python (len, int, str, etc.)
            }
            
            # Если одна схема -> df, если несколько -> df1, df2, ...
            if len(input_schemas) == 1:
                sample_data = input_schemas[0].get("sample_data", [])
                columns = input_schemas[0].get("columns", [])
                
                # Handle both old (string array) and new (dict array) column formats
                if columns and isinstance(columns[0], dict):
                    column_names = [col["name"] for col in columns]
                else:
                    column_names = columns
                
                if sample_data:
                    # Handle dict rows (unified format)
                    if sample_data and isinstance(sample_data[0], dict):
                        namespace['df'] = pd.DataFrame(sample_data)
                    else:
                        namespace['df'] = pd.DataFrame(sample_data, columns=column_names)
                else:
                    # Создать пустой DataFrame с колонками
                    namespace['df'] = pd.DataFrame(columns=column_names)
            else:
                for i, schema in enumerate(input_schemas, 1):
                    sample_data = schema.get("sample_data", [])
                    columns = schema.get("columns", [])
                    
                    # Handle both old (string array) and new (dict array) column formats
                    if columns and isinstance(columns[0], dict):
                        column_names = [col["name"] for col in columns]
                    else:
                        column_names = columns
                    
                    if sample_data:
                        # Handle dict rows (unified format)
                        if sample_data and isinstance(sample_data[0], dict):
                            namespace[f'df{i}'] = pd.DataFrame(sample_data)
                        else:
                            namespace[f'df{i}'] = pd.DataFrame(sample_data, columns=column_names)
                    else:
                        namespace[f'df{i}'] = pd.DataFrame(columns=column_names)
            
            # Выполнить код
            import time
            start_time = time.time()
            
            self.logger.info(f"🔧 Executing code for dry-run:\n{code}")
            exec(code, namespace)
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Debug: log all variables in namespace
            all_vars = {k: type(v).__name__ for k, v in namespace.items() if not k.startswith('_')}
            self.logger.info(f"📦 Namespace after exec: {all_vars}")
            
            # Проверить результат - ищем ВСЕ переменные с префиксом df_
            result_dfs = {}
            for name, value in namespace.items():
                if name.startswith('df_') and isinstance(value, pd.DataFrame):
                    result_dfs[name] = value
                    self.logger.info(f"✓ Found result DataFrame: {name} shape={value.shape}")
            
            if not result_dfs:
                self.logger.error(f"❌ No df_ DataFrames found! Available: {list(all_vars.keys())}")
                return {
                    "success": False,
                    "error": "Code did not produce any DataFrame variables starting with 'df_' (e.g., df_result, df_result1)"
                }
            
            # Формируем результат валидации
            if len(result_dfs) == 1:
                # Одна выходная таблица
                df = list(result_dfs.values())[0]
                return {
                    "success": True,
                    "output_shape": list(df.shape),
                    "output_columns": list(df.columns),
                    "execution_time_ms": execution_time_ms
                }
            else:
                # Множественные выходные таблицы
                return {
                    "success": True,
                    "output_count": len(result_dfs),
                    "output_shapes": [list(df.shape) for df in result_dfs.values()],
                    "output_columns": [list(df.columns) for df in result_dfs.values()],
                    "output_names": list(result_dfs.keys()),
                    "execution_time_ms": execution_time_ms
                }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
validator_agent_instance = None

def get_validator_agent(message_bus: AgentMessageBus) -> ValidatorAgent:
    """Получить singleton instance ValidatorAgent."""
    global validator_agent_instance
    if validator_agent_instance is None:
        validator_agent_instance = ValidatorAgent(message_bus)
    return validator_agent_instance
