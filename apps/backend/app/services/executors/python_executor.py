"""PythonExecutor - безопасное выполнение Python/pandas кода.

Сейчас локальное выполнение, позже Docker sandbox.
"""
from typing import Any, Dict, List
import io
import sys
import re
import logging
from datetime import datetime
import pandas as pd
import numpy as np

from .gigaboard_helpers import init_helpers

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Результат выполнения кода."""
    
    def __init__(
        self,
        success: bool,
        result_dfs: dict[str, pd.DataFrame] | None = None,  # Multiple DataFrames
        output: str = "",
        error: str | None = None,
        execution_time_ms: int = 0
    ):
        self.success = success
        self.result_dfs = result_dfs if result_dfs is not None else {}
        self.output = output
        self.error = error
        self.execution_time_ms = execution_time_ms


class PythonExecutor:
    """Executor для выполнения Python/pandas трансформаций."""
    
    def __init__(self):
        self.timeout_seconds = 30  # Максимальное время выполнения
        self.max_memory_mb = 512   # Лимит памяти (для Docker)
    
    async def execute_transformation(
        self,
        code: str,
        input_data: Dict[str, Any],
        timeout: int | None = None,
        user_id: str | None = None,
        auth_token: str | None = None
    ) -> ExecutionResult:
        """Выполняет Python код трансформации.
        
        Args:
            code: Python код для выполнения
            input_data: Словарь с входными DataFrame
            timeout: Таймаут выполнения
            user_id: ID пользователя для логирования
            auth_token: Bearer token для вызовов API
            input_data: Входные данные {table_name: dataframe}
            timeout: Таймаут в секундах (optional)
            
        Returns:
            ExecutionResult с результатом или ошибкой
        """
        start_time = datetime.utcnow()
        
        # Захват stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # Подготовка namespace для выполнения
            namespace = {
                'pd': pd,
                'np': np,
                're': re,  # Regex module for text processing
                '__builtins__': __builtins__,
            }
            
            # Инициализация GigaBoard helpers (gb module)
            # Context-aware: автоматически выбирает direct/MessageBus
            try:
                execution_context = {
                    "orchestrated": False,  # TODO: передавать из вызывающего кода
                    "source": "user_ui",
                    "session_id": None  # TODO: если есть session
                }
                gb_helpers = init_helpers(execution_context)
                namespace['gb'] = gb_helpers
                logger.info("✅ GigaBoard helpers (gb) initialized")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize gb helpers: {e}")
            
            # Добавить входные данные
            # Предполагаем, что основная таблица называется 'df'
            if input_data:
                # Проверяем, есть ли текстовый контент (text variable)
                if 'text' in input_data and isinstance(input_data['text'], str):
                    # Text-only mode
                    namespace['text'] = input_data['text']
                    logger.info(f"📝 Input: Text content ({len(input_data['text'])} chars)")
                    
                    # Также добавляем empty df на случай если код ожидает его
                    namespace['df'] = pd.DataFrame()
                else:
                    # Table mode
                    main_table_name = list(input_data.keys())[0]
                    namespace['df'] = input_data[main_table_name]
                    logger.info(f"📥 Input: Main table '{main_table_name}' as 'df' (shape: {input_data[main_table_name].shape})")
                    
                    # Добавить все таблицы по именам И как df1, df2, df3
                    for idx, (table_name, df) in enumerate(input_data.items()):
                        namespace[table_name] = df
                        # Добавить алиасы df1, df2, df3 для multiple source трансформаций
                        dfN_name = f"df{idx + 1}"
                        namespace[dfN_name] = df
                        logger.info(f"📥 Input: Table '{table_name}' as '{dfN_name}' (shape: {df.shape})")
            
            # Выполнить код
            exec(code, namespace)
            
            # Извлечь ВСЕ DataFrames начинающиеся с 'df_'
            result_dfs = {}
            for name, value in namespace.items():
                if name.startswith('df_') and isinstance(value, pd.DataFrame):
                    # Убрать префикс 'df_' для читаемых имён таблиц
                    table_name = name[3:]  # "df_result" -> "result"
                    result_dfs[table_name] = value
                    logger.info(f"📊 Extracted result table: {name} -> {table_name} (shape: {value.shape})")
            
            if not result_dfs:
                logger.error(f"❌ No df_ variables found in namespace. Available variables: {[k for k in namespace.keys() if not k.startswith('_')]}")
                raise ValueError("Code must define at least one DataFrame variable starting with 'df_' (e.g., df_result, df_summary)")
            
            logger.info(f"✅ Total result tables extracted: {len(result_dfs)} - {list(result_dfs.keys())}")
            
            # Вычислить время выполнения
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            output = stdout_capture.getvalue()
            
            logger.info(f"Transformation executed successfully in {execution_time:.0f}ms, {len(result_dfs)} tables created")
            
            return ExecutionResult(
                success=True,
                result_dfs=result_dfs,
                output=output,
                execution_time_ms=int(execution_time)
            )
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_msg = str(e)
            stderr_output = stderr_capture.getvalue()
            
            if stderr_output:
                error_msg += f"\n\nStderr:\n{stderr_output}"
            
            logger.error(f"Transformation execution failed: {error_msg}")
            
            return ExecutionResult(
                success=False,
                error=error_msg,
                output=stdout_capture.getvalue(),
                execution_time_ms=int(execution_time)
            )
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def dataframe_to_table_dict(self, df: pd.DataFrame, table_name: str = "result") -> Dict[str, Any]:
        """Конвертирует pandas DataFrame в формат ContentNode table.
        
        Returns:
            {
                "name": str,
                "columns": [str, ...],
                "rows": [[val, ...], ...],
                "row_count": int,
                "column_count": int,
            }
        """
        # Создаем копию, чтобы не изменять оригинал
        df_copy = df.copy()
        
        # Конвертируем Categorical колонки в строки (чтобы избежать ошибок с fillna)
        for col in df_copy.columns:
            if isinstance(df_copy[col].dtype, pd.CategoricalDtype):
                df_copy[col] = df_copy[col].astype(str)
        
        # Конвертировать в list of lists, заполняя NaN пустыми строками
        rows = df_copy.fillna("").values.tolist()
        
        # Имена колонок
        columns = [str(col) for col in df.columns]
        
        return {
            "name": table_name,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(columns),
            "metadata": {
                "dtypes": {col: str(df[col].dtype) for col in df.columns},
                "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
            }
        }
    
    def table_dict_to_dataframe(self, table: Dict[str, Any]) -> pd.DataFrame:
        """Конвертирует ContentNode table в pandas DataFrame.
        
        Args:
            table: {name, columns, data/rows, ...}
            
        Returns:
            pandas DataFrame
        """
        columns = table["columns"]
        # Support both 'data' (ContentNode format) and 'rows' (legacy)
        rows = table.get("data") or table.get("rows", [])
        
        # Handle new Pydantic format:
        # columns: [{"name": "col1", "type": "string"}, ...] → ["col1", ...]
        # rows: [{"id": "uuid", "values": [...]}, ...] → [[...], ...]
        
        if columns and isinstance(columns[0], dict):
            # New format: extract column names
            column_names = [col["name"] for col in columns]
        else:
            # Old format: columns are already strings
            column_names = columns
        
        if rows and isinstance(rows[0], dict) and "values" in rows[0]:
            # New format: extract values from each row
            row_values = [row["values"] for row in rows]
        else:
            # Old format: rows are already arrays
            row_values = rows
        
        return pd.DataFrame(row_values, columns=column_names)


# Singleton instance
python_executor = PythonExecutor()
