"""
ErrorAnalyzerAgent - Анализирует ошибки и предлагает стратегии исправления.

Этот агент:
1. Анализирует ошибки от других агентов
2. Определяет корневую причину (root cause)
3. Предлагает конкретные корректировки для следующей попытки
4. Помогает мультиагенту адаптировать стратегию
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional

from .base import BaseAgent
from ...gigachat_service import GigaChatService

logger = logging.getLogger("agent.error_analyzer")


ERROR_ANALYSIS_PROMPT = '''You are an expert error analyzer for a data transformation system.

Your task is to analyze errors from a failed transformation attempt and provide:
1. Root cause analysis - what went wrong
2. Specific corrections - how to fix it
3. Strategy recommendations - how to approach the next attempt

**COMMON ERROR PATTERNS:**

1. **Variable naming errors**:
   - "name 'X' is not defined" → Variable used before assignment or wrong variable name
   - "df_result not found" → Code didn't create df_result variable
   
2. **DataFrame operation errors**:
   - "KeyError: 'column'" → Column doesn't exist in DataFrame
   - "'DataFrame' object has no attribute" → Wrong pandas method
   - "cannot perform operation" → Type mismatch
   
3. **Syntax errors**:
   - "SyntaxError" → Invalid Python syntax
   - "IndentationError" → Wrong indentation
   
4. **Logic errors**:
   - Empty result → Filter too restrictive
   - Wrong output shape → Logic doesn't match requirements

**OUTPUT FORMAT (JSON):**
```json
{
  "root_cause": "Brief description of what went wrong",
  "error_category": "variable_naming|dataframe_operation|syntax|logic|other",
  "specific_fixes": [
    "Fix 1: Specific instruction",
    "Fix 2: Another instruction"
  ],
  "corrected_approach": "How to approach the task differently",
  "simplified_task": "If original task is too complex, simplified version",
  "code_hints": [
    "# Hint about correct code structure",
    "df_result = ..."
  ],
  "severity": "critical|high|medium|low"
}
```

Be concise and actionable. Focus on the most likely cause and provide clear fixes.
'''


class ErrorAnalyzerAgent(BaseAgent):
    """
    Error Analyzer Agent - анализирует ошибки и предлагает исправления.
    """
    
    agent_type = "error_analyzer"
    
    def __init__(
        self,
        message_bus=None,
        gigachat_service: Optional[GigaChatService] = None
    ):
        super().__init__("error_analyzer", message_bus)
        self.gigachat = gigachat_service
        self.logger = logger
    
    def _get_default_system_prompt(self) -> str:
        """Возвращает системный промпт для анализа ошибок."""
        return ERROR_ANALYSIS_PROMPT
    
    async def process_task(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Обрабатывает задачу анализа ошибок.
        
        Args:
            task: {
                "type": "analyze_error",
                "errors": ["error1", "error2", ...],
                "original_prompt": "User's original request",
                "failed_code": "The code that failed",
                "attempt_number": 1,
                "input_schemas": [...]
            }
            context: Дополнительный контекст
        
        Returns:
            {
                "root_cause": str,
                "error_category": str,
                "specific_fixes": [str, ...],
                "corrected_approach": str,
                "simplified_task": str,
                "code_hints": [str, ...],
                "severity": str
            }
        """
        task_type = task.get("type", "")
        
        if task_type == "analyze_error":
            return await self._analyze_error(task)
        else:
            self.logger.warning(f"Unknown task type: {task_type}")
            return self._fallback_analysis(task)
    
    async def _analyze_error(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализирует ошибку и предлагает решение.
        """
        errors = task.get("errors", [])
        original_prompt = task.get("original_prompt", "")
        failed_code = task.get("failed_code", "")
        attempt_number = task.get("attempt_number", 1)
        input_schemas = task.get("input_schemas", [])
        
        # Сначала попробуем быстрый паттерн-анализ
        quick_fix = self._quick_pattern_match(errors, failed_code, input_schemas)
        if quick_fix and quick_fix.get("severity") == "critical":
            self.logger.info(f"🔍 Quick pattern match found: {quick_fix['root_cause']}")
            return quick_fix
        
        # Если есть GigaChat - используем AI для глубокого анализа
        if self.gigachat:
            try:
                return await self._ai_error_analysis(
                    errors=errors,
                    original_prompt=original_prompt,
                    failed_code=failed_code,
                    attempt_number=attempt_number,
                    input_schemas=input_schemas
                )
            except Exception as e:
                self.logger.warning(f"AI error analysis failed: {e}")
        
        # Fallback: вернуть быстрый анализ или базовый
        return quick_fix or self._fallback_analysis(task)
    
    def _quick_pattern_match(
        self,
        errors: List[str],
        failed_code: str,
        input_schemas: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """
        Быстрый анализ на основе паттернов ошибок.
        """
        error_text = " ".join(errors).lower()
        
        # Pattern 1: Variable not defined (df1, df2, etc.)
        var_match = re.search(r"name '(\w+)' is not defined", " ".join(errors))
        if var_match:
            var_name = var_match.group(1)
            
            # Проверка: это встроенная функция Python?
            python_builtins = {'len', 'int', 'str', 'float', 'list', 'dict', 'tuple', 'set', 
                              'sum', 'min', 'max', 'abs', 'round', 'range', 'enumerate', 
                              'zip', 'map', 'filter', 'sorted', 'all', 'any', 'type', 'isinstance'}
            
            if var_name in python_builtins:
                return {
                    "root_cause": f"Built-in function '{var_name}' not available in sandbox",
                    "error_category": "sandbox_environment",
                    "specific_fixes": [
                        f"CRITICAL: '{var_name}' is a Python built-in function and should be available",
                        "This is a validator configuration issue, not a code issue",
                        "Validator needs __builtins__ in exec() globals"
                    ],
                    "corrected_approach": "Contact system admin - this is a validator bug",
                    "simplified_task": f"Try alternative approach without using {var_name}()",
                    "code_hints": [
                        f"# {var_name}() should work, but sandbox is broken",
                        "# Workaround: use pandas methods instead of Python builtins",
                        "# Example: df.shape[0] instead of len(df)"
                    ],
                    "severity": "critical"
                }
            
            # Если это df1, df2 - проблема с именами входных таблиц
            if re.match(r'^df\d+$', var_name):
                available_tables = [s.get("name") for s in input_schemas]
                return {
                    "root_cause": f"Variable '{var_name}' not defined. Input tables are named: {available_tables}",
                    "error_category": "variable_naming",
                    "specific_fixes": [
                        f"Use df (single source) or df1, df2, df3 (multiple sources)",
                        f"Available input table names: {', '.join(str(t) for t in available_tables if t)}",
                        "Tables are automatically available as df1, df2, df3... AND by their actual names"
                    ],
                    "corrected_approach": "Use df for single table or df1, df2, df3 for multiple tables",
                    "simplified_task": None,
                    "code_hints": [
                        "# For single table: df",
                        "# For multiple tables: df1, df2, df3",
                        "df_result = df1.merge(df2, on='common_column')",
                        "df_result = pd.concat([df1, df2, df3], ignore_index=True)"
                    ],
                    "severity": "critical"
                }
            
            return {
                "root_cause": f"Variable '{var_name}' used but not defined",
                "error_category": "variable_naming",
                "specific_fixes": [
                    f"Define '{var_name}' before using it",
                    "Use df_result for output, not intermediate variables"
                ],
                "corrected_approach": "Assign result directly to df_result",
                "simplified_task": None,
                "code_hints": [
                    f"# Don't use: {var_name} = ...",
                    "# Instead: df_result = ..."
                ],
                "severity": "critical"
            }
        
        # Pattern 2: No df_ variable created
        if "must define at least one dataframe variable starting with 'df_'" in error_text:
            return {
                "root_cause": "Code doesn't create required df_result variable",
                "error_category": "variable_naming",
                "specific_fixes": [
                    "Always assign final result to df_result",
                    "Use df_result, df_result2, df_result3 for multiple outputs"
                ],
                "corrected_approach": "Ensure code ends with df_result = <final_dataframe>",
                "simplified_task": None,
                "code_hints": [
                    "# Always end with df_result assignment:",
                    "df_result = df[df['column'] > value]",
                    "# For multiple outputs:",
                    "df_result = df[condition1]",
                    "df_result2 = df[condition2]"
                ],
                "severity": "critical"
            }
        
        # Pattern 3: Column not found
        col_match = re.search(r"keyerror:\s*['\"](\w+)['\"]", error_text)
        if col_match:
            col_name = col_match.group(1)
            available_cols = []
            for schema in input_schemas:
                available_cols.extend(schema.get("columns", []))
            
            return {
                "root_cause": f"Column '{col_name}' not found in DataFrame",
                "error_category": "dataframe_operation",
                "specific_fixes": [
                    f"Column '{col_name}' doesn't exist",
                    f"Available columns: {available_cols[:10]}...",
                    "Check column name spelling and case"
                ],
                "corrected_approach": "Use only columns that exist in the input data",
                "simplified_task": None,
                "code_hints": [
                    f"# Available columns: {available_cols[:5]}",
                    f"# Instead of df['{col_name}'], use existing column"
                ],
                "severity": "high"
            }
        
        # Pattern 4: Syntax error
        if "syntaxerror" in error_text or "indentationerror" in error_text:
            return {
                "root_cause": "Python syntax error in generated code",
                "error_category": "syntax",
                "specific_fixes": [
                    "Check for missing parentheses, brackets, or quotes",
                    "Verify correct indentation",
                    "Ensure proper line breaks"
                ],
                "corrected_approach": "Generate simpler, cleaner code",
                "simplified_task": "Simplify the transformation to basic operations",
                "code_hints": [
                    "# Keep code simple and well-formatted",
                    "df_result = df.copy()",
                    "# Add operations step by step"
                ],
                "severity": "high"
            }
        
        return None
    
    async def _ai_error_analysis(
        self,
        errors: List[str],
        original_prompt: str,
        failed_code: str,
        attempt_number: int,
        input_schemas: List[Dict]
    ) -> Dict[str, Any]:
        """
        AI-powered глубокий анализ ошибок.
        """
        # Формируем промпт для AI
        prompt = f"""Analyze this error from a Python data transformation:

**ORIGINAL TASK:**
{original_prompt}

**FAILED CODE:**
```python
{failed_code[:1000]}
```

**ERRORS (attempt #{attempt_number}):**
{chr(10).join(f"- {e}" for e in errors)}

**INPUT DATA SCHEMAS:**
{json.dumps(input_schemas[:3], indent=2, default=str)[:500]}

Provide analysis in JSON format with: root_cause, error_category, specific_fixes, corrected_approach, simplified_task, code_hints, severity.
"""

        messages = [
            {"role": "system", "content": ERROR_ANALYSIS_PROMPT},
            {"role": "user", "content": prompt}
        ]
        if not self.gigachat:
            return self._fallback_analysis({"errors": errors})
        
        response = await self.gigachat.chat_completion(
            messages=messages,
            temperature=0.3
        )
        
        return self._parse_analysis_response(response, errors)
    
    def _parse_analysis_response(self, response: str, original_errors: List[str]) -> Dict[str, Any]:
        """Парсит ответ AI."""
        try:
            # Удаляем markdown code blocks
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            elif response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            result = json.loads(response.strip())
            
            # Валидация required полей
            required_fields = ["root_cause", "error_category", "specific_fixes"]
            for field in required_fields:
                if field not in result:
                    result[field] = "Unknown"
            
            return result
            
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse AI response as JSON")
            return self._fallback_analysis({"errors": original_errors})
    
    def _fallback_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Базовый анализ ошибок без AI."""
        errors = task.get("errors", [])
        
        return {
            "root_cause": f"Transformation failed with errors: {errors[:2]}",
            "error_category": "other",
            "specific_fixes": [
                "Simplify the transformation",
                "Use basic pandas operations",
                "Assign result to df_result"
            ],
            "corrected_approach": "Try a simpler approach with basic operations",
            "simplified_task": "Filter or select data using simple conditions",
            "code_hints": [
                "df_result = df.copy()  # Start simple",
                "# Add transformations step by step"
            ],
            "severity": "medium"
        }


def get_error_analyzer_agent(
    message_bus=None,
    gigachat_service: Optional[GigaChatService] = None
) -> ErrorAnalyzerAgent:
    """Factory function для ErrorAnalyzerAgent."""
    return ErrorAnalyzerAgent(message_bus, gigachat_service)
