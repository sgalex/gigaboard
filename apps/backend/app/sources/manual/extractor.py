"""Manual Source Extractor - manual table construction.

Пользователь создаёт таблицы вручную через UI.
"""
import time
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
)


class ManualSource(BaseSource):
    """Manual data entry source handler."""
    
    source_type = "manual"
    display_name = "Ручной ввод"
    icon = "✏️"
    description = "Создание таблиц вручную"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate manual source config."""
        errors = []
        
        tables = config.get("tables", [])
        if not tables:
            errors.append("Необходимо создать хотя бы одну таблицу")
            return ValidationResult.failure(errors)
        
        for i, table in enumerate(tables):
            if not table.get("name"):
                errors.append(f"Таблица {i+1}: не указано название")
            if not table.get("columns"):
                errors.append(f"Таблица {i+1}: не определены столбцы")
        
        if errors:
            return ValidationResult.failure(errors)
        return ValidationResult.success()
    
    async def extract(
        self,
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs
    ) -> ExtractionResult:
        """Extract data from manual input config."""
        start_time = time.time()
        
        try:
            tables_config = config.get("tables", [])
            tables = []
            total_rows = 0
            
            for table_config in tables_config:
                table_name = table_config.get("name", "table")
                columns = table_config.get("columns", [])
                rows = table_config.get("rows", [])
                
                table = TableData(
                    id=table_name,
                    name=table_name,
                    columns=columns,
                    rows=rows,
                )
                tables.append(table)
                total_rows += len(rows)
            
            extraction_time = int((time.time() - start_time) * 1000)
            
            text = f"Создано {len(tables)} таблиц с {total_rows} строками."
            
            return ExtractionResult(
                success=True,
                text=text,
                tables=tables,
                extraction_time_ms=extraction_time,
                metadata={
                    "table_count": len(tables),
                    "total_rows": total_rows,
                }
            )
            
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка создания данных: {str(e)}")
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for manual input dialog."""
        return {
            "type": "object",
            "properties": {
                "tables": {
                    "type": "array",
                    "title": "Таблицы",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "title": "Название таблицы"},
                            "columns": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {"type": "string", "enum": ["text", "number", "date"]},
                                    },
                                },
                            },
                            "rows": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                        },
                    },
                },
            },
        }
