"""TransformationAgent - генерирует Python код для трансформации данных.

Пока mock-версия, позже будет интеграция с GigaChat.
"""
from typing import Any, Dict, List
import logging
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


class TransformationAgent:
    """Agent для генерации Python/pandas кода трансформации данных."""
    
    def __init__(self):
        self.model = "mock"  # В будущем: "gigachat"
    
    async def generate_transformation(
        self,
        source_content: Dict[str, Any],
        prompt: str,
        metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Генерирует Python код для трансформации данных.
        
        Args:
            source_content: ContentNode.content dict {text, tables}
            prompt: Описание требуемой трансформации от пользователя
            metadata: Дополнительные метаданные (board_id, user_id, etc.)
            
        Returns:
            {
                "transformation_id": UUID,
                "code": str,  # Python/pandas код
                "description": str,  # Описание трансформации
                "input_mapping": dict,  # Какие таблицы используются
                "estimated_output": dict,  # Ожидаемая структура выхода
            }
        """
        logger.info(f"Generating transformation code for prompt: {prompt[:100]}")
        
        # Анализ входных данных
        tables = source_content.get("tables", [])
        table_count = len(tables)
        
        if table_count == 0:
            raise ValueError("Source content has no tables to transform")
        
        # Определить основную таблицу (самую большую)
        main_table = max(tables, key=lambda t: t.get("row_count", 0))
        table_name = main_table["name"]
        columns = main_table.get("columns", [])
        
        # Mock генерация кода на основе ключевых слов в промпте
        code = self._generate_mock_code(prompt, table_name, columns)
        
        transformation_id = str(uuid4())
        
        return {
            "transformation_id": transformation_id,
            "code": code,
            "description": f"Transform based on: {prompt}",
            "input_mapping": {
                "main_table": table_name,
                "columns_used": [col for col in columns[:5]],  # First 5 columns
            },
            "estimated_output": {
                "tables": 1,
                "rows": "dynamic",
                "description": "Transformed data based on user prompt"
            },
            "metadata": {
                "agent": "transformation_agent",
                "model": self.model,
                "prompt": prompt,
                "generated_at": datetime.utcnow().isoformat(),
            }
        }
    
    def _generate_mock_code(self, prompt: str, table_name: str, columns: List[str]) -> str:
        """Mock генерация кода, создающего ДВЕ таблицы: df_result + df_summary."""
        prompt_lower = prompt.lower()
        
        # Генерация с двумя таблицами
        if "filter" in prompt_lower or "where" in prompt_lower:
            code = f"""import pandas as pd
import numpy as np

df = {table_name}
numeric_cols = df.select_dtypes(include=[np.number]).columns

# Основная таблица: фильтрация
if len(numeric_cols) > 0:
    df_result = df[df[numeric_cols[0]] > 100]
else:
    df_result = df.copy()

# Сводная таблица: статистика фильтрации
df_summary = pd.DataFrame({{
    'Метрика': ['Всего строк', 'После фильтра', 'Удалено'],
    'Значение': [len(df), len(df_result), len(df) - len(df_result)]
}})
"""
        
        elif "group" in prompt_lower or "aggregate" in prompt_lower or "sum" in prompt_lower:
            code = f"""import pandas as pd
import numpy as np

df = {table_name}
categorical_cols = df.select_dtypes(include=['object']).columns
numeric_cols = df.select_dtypes(include=[np.number]).columns

# Основная таблица: группировка
if len(categorical_cols) > 0 and len(numeric_cols) > 0:
    df_result = df.groupby(categorical_cols[0])[numeric_cols[0]].sum().reset_index()
    # Сводная: топ-5 групп
    df_summary = df_result.nlargest(5, numeric_cols[0]).copy()
else:
    df_result = df.copy()
    df_summary = pd.DataFrame({{'info': ['No grouping']}})
"""
        
        elif "sort" in prompt_lower or "order" in prompt_lower:
            code = f"""import pandas as pd
import numpy as np

df = {table_name}

# Основная: сортировка
if len(df.columns) > 0:
    df_result = df.sort_values(by=df.columns[0])
    # Сводная: топ/низ значения
    df_summary = pd.DataFrame({{
        'position': ['Top-1', 'Top-2', 'Top-3', 'Bottom-1', 'Bottom-2', 'Bottom-3'],
        'value': list(df_result[df.columns[0]].head(3)) + list(df_result[df.columns[0]].tail(3))
    }})
else:
    df_result = df.copy()
    df_summary = pd.DataFrame({{'info': ['No sorting']}})
"""
        
        elif "add" in prompt_lower and "column" in prompt_lower or "calculate" in prompt_lower:
            code = f"""import pandas as pd
import numpy as np

df = {table_name}
numeric_cols = df.select_dtypes(include=[np.number]).columns

# Основная: добавить вычисляемый столбец
if len(numeric_cols) >= 2:
    df_result = df.copy()
    df_result['calculated'] = df[numeric_cols[0]] + df[numeric_cols[1]]
    # Сводная: статистика нового столбца
    df_summary = pd.DataFrame({{
        'stat': ['mean', 'median', 'min', 'max', 'std'],
        'value': [
            df_result['calculated'].mean(),
            df_result['calculated'].median(),
            df_result['calculated'].min(),
            df_result['calculated'].max(),
            df_result['calculated'].std()
        ]
    }})
else:
    df_result = df.copy()
    df_summary = pd.DataFrame({{'info': ['No calculation']}})
"""
        
        else:
            # По умолчанию: очистка + метрики
            code = f"""import pandas as pd
import numpy as np

df = {table_name}
original_count = len(df)

# Основная: очистка данных
df_result = df.copy()
df_result = df_result.drop_duplicates()
df_result = df_result.dropna()

# Сводная: метрики качества
df_summary = pd.DataFrame({{
    'metric': ['Original', 'Dedup', 'Removed', 'Final'],
    'count': [original_count, len(df.drop_duplicates()), original_count - len(df.drop_duplicates()), len(df_result)]
}})
"""
        
        return code.strip()
    
    
    async def validate_code(self, code: str) -> Dict[str, Any]:
        """Проверяет сгенерированный код на синтаксические ошибки.
        
        Returns:
            {"valid": bool, "errors": List[str]}
        """
        try:
            compile(code, '<transformation>', 'exec')
            return {"valid": True, "errors": []}
        except SyntaxError as e:
            return {
                "valid": False,
                "errors": [f"Syntax error at line {e.lineno}: {e.msg}"]
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"]
            }


# Singleton instance
transformation_agent = TransformationAgent()
