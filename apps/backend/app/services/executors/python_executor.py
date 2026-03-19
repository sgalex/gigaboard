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


class _GBUnavailable:
    """Stub object that fails with clear guidance when gb helpers are unavailable."""

    def __init__(self, reason: str):
        self._reason = reason

    def __getattr__(self, name: str):
        raise RuntimeError(
            "GigaBoard helpers (gb) are unavailable: "
            f"{self._reason}. "
            "Initialize GigaChat service via initialize_gigachat_service() "
            "or avoid using gb.* in this transformation."
        )


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
    ) -> ExecutionResult:
        """Выполняет Python код трансформации.
        
        Args:
            code: Python код для выполнения
            input_data: Входные данные {table_name: dataframe}
            timeout: Таймаут в секундах (optional)
            user_id: ID пользователя для логирования
            
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

            # Инициализируем gb helper только если код реально его использует.
            # Это убирает шум в логах на обычных pandas-трансформациях.
            if re.search(r"\bgb\.", code):
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
                    # Сохраняем совместимость исполнения, но даём явную причину при обращении к gb.*
                    logger.info(f"ℹ️ gb helpers unavailable for this run: {e}")
                    namespace['gb'] = _GBUnavailable(str(e))
            
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
            
            # Debug: log code before execution
            logger.info(f"🔍 Executor received code ({len(code)} chars): {code[:300]}...")
            logger.info(f"🔍 Checking for df_ pattern: {bool(re.search(r'df_[a-z_]', code))}")
            
            # Выполнить код
            exec(code, namespace)
            
            # Извлечь ВСЕ DataFrames начинающиеся с 'df_'
            raw_dfs: dict[str, tuple[int, "pd.DataFrame"]] = {}  # name -> (id, df)
            for name, value in namespace.items():
                if name.startswith('df_') and isinstance(value, pd.DataFrame):
                    table_name = name[3:]  # "df_sales_by_brand" -> "sales_by_brand"
                    raw_dfs[table_name] = (id(value), value)
                    logger.info(f"📊 Extracted result table: {name} -> {table_name} (shape: {value.shape})")
                elif name.startswith('df_') and not isinstance(value, pd.DataFrame):
                    # Auto-wrap скаляров/Series в DataFrame
                    # GigaChat часто генерирует: df_avg = df['col'].mean() → float
                    scalar_types = (int, float, np.integer, np.floating)
                    if isinstance(value, scalar_types):
                        col_name = name[3:]  # df_average_salary → average_salary
                        wrapped = pd.DataFrame({col_name: [value]})
                        raw_dfs[col_name] = (id(wrapped), wrapped)
                        logger.warning(f"⚠️ Auto-wrapped scalar {name}={value} into DataFrame (shape: {wrapped.shape})")
                    elif isinstance(value, pd.Series):
                        wrapped = value.to_frame()
                        col_name = name[3:]
                        raw_dfs[col_name] = (id(wrapped), wrapped)
                        logger.warning(f"⚠️ Auto-wrapped Series {name} into DataFrame (shape: {wrapped.shape})")
                    else:
                        logger.warning(f"⚠️ Skipping {name}: type={type(value).__name__}, not a DataFrame")
            
            if not raw_dfs:
                logger.error(f"❌ No df_ variables found in namespace. Available variables: {[k for k in namespace.keys() if not k.startswith('_')]}")
                raise ValueError("Code must define at least one DataFrame variable starting with 'df_' (e.g., df_sales_by_brand, df_monthly_stats)")
            
            # Дедупликация: если два df_ указывают на один и тот же объект (id),
            # оставляем ПОСЛЕДНИЙ (по порядку обхода namespace, т.е. по порядку создания).
            # Пример: df_average_salary = ...; df_city_stats = df_average_salary
            #   → оба имеют одинаковый id() → оставляем df_city_stats
            seen_ids: dict[int, str] = {}  # object_id -> table_name
            for table_name, (obj_id, df_obj) in raw_dfs.items():
                if obj_id in seen_ids:
                    prev_name = seen_ids[obj_id]
                    logger.warning(
                        f"⚠️ Duplicate DataFrame detected: df_{table_name} is same object as df_{prev_name}. "
                        f"Keeping df_{table_name}, dropping df_{prev_name}."
                    )
                seen_ids[obj_id] = table_name
            
            # Собираем финальный результат — только уникальные объекты
            unique_names = set(seen_ids.values())
            result_dfs = {
                name: df_obj
                for name, (_, df_obj) in raw_dfs.items()
                if name in unique_names
            }
            
            if len(result_dfs) < len(raw_dfs):
                dropped = len(raw_dfs) - len(result_dfs)
                logger.info(f"🧹 Deduplicated: {dropped} duplicate(s) removed, {len(result_dfs)} unique table(s) remain")
            
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
            # FIX: Включаем тип ошибки в сообщение.
            # Без этого KeyError('biName') → str(e) = "'biName'" — тип теряется,
            # и codex hint r'KeyError:.*' не срабатывает.
            error_type = type(e).__name__
            error_msg = f"{error_type}: {e}"

            # FIX: Для KeyError / InvalidIndexError добавляем доступные колонки
            # каждого DataFrame, чтобы GigaChat мог сопоставить и исправить ошибку.
            _needs_col_hints = isinstance(e, KeyError) or type(e).__name__ == 'InvalidIndexError'
            if _needs_col_hints:
                col_hints: list[str] = []
                for var_name, var_val in namespace.items():
                    if isinstance(var_val, pd.DataFrame) and not var_name.startswith('_'):
                        cols_preview = list(var_val.columns[:30])
                        col_hints.append(f"  {var_name}: {cols_preview}")
                if col_hints:
                    error_msg += "\nДоступные колонки DataFrame:\n" + "\n".join(col_hints)

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
        """Конвертирует pandas DataFrame в unified формат ContentNode table.
        
        Returns:
            {
                "name": str,
                "columns": [{"name": str, "type": str}, ...],
                "rows": [{col_name: value, ...}, ...],
                "row_count": int,
                "column_count": int,
            }
        """
        # Создаем копию, чтобы не изменять оригинал
        df_copy = df.copy()

        # Flatten MultiIndex columns (e.g. from .agg(['sum'])) to avoid
        # tuple keys that jsonable_encoder converts to unhashable lists.
        if isinstance(df_copy.columns, pd.MultiIndex):
            df_copy.columns = ['_'.join(str(c) for c in col).strip('_') for col in df_copy.columns]
            df = df.copy()
            df.columns = df_copy.columns
        
        # Конвертируем Categorical колонки в строки (чтобы избежать ошибок с fillna)
        for col in df_copy.columns:
            if isinstance(df_copy[col].dtype, pd.CategoricalDtype):
                df_copy[col] = df_copy[col].astype(str)
        
        # Typed columns from DataFrame dtypes
        columns = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            if 'int' in dtype:
                col_type = "int"
            elif 'float' in dtype:
                col_type = "float"
            elif 'bool' in dtype:
                col_type = "bool"
            elif 'datetime' in dtype:
                col_type = "date"
            else:
                col_type = "string"
            columns.append({"name": str(col), "type": col_type})
        
        # Dict rows via to_dict(orient='records')
        rows = df_copy.fillna("").to_dict(orient='records')
        rows = [{str(k): v for k, v in row.items()} for row in rows]
        
        return {
            "name": table_name,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(columns),
            "metadata": {
                "dtypes": {str(col): str(df[col].dtype) for col in df.columns},
                "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
            }
        }
    
    def table_dict_to_dataframe(self, table: Dict[str, Any]) -> pd.DataFrame:
        """Конвертирует ContentNode table в pandas DataFrame.
        
        Формат:
          columns: [{name: str, type: str}, ...]
          rows: [{col_name: value, ...}, ...]
        """
        columns = table["columns"]
        rows = table.get("data") or table.get("rows", [])
        
        # Extract column names
        column_names = [col["name"] for col in columns]
        
        if not rows:
            return pd.DataFrame(columns=column_names)
        
        return pd.DataFrame(rows, columns=column_names)


# Singleton instance
python_executor = PythonExecutor()
