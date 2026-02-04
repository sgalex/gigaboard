"""JSON Source Extractor - AI generates Python extraction code.

AI анализирует структуру JSON и генерирует Python код для извлечения данных.
Код сохраняется в config для повторного использования при refresh.
"""
import time
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
)


class JSONSource(BaseSource):
    """JSON file source handler with AI-powered extraction."""
    
    source_type = "json"
    display_name = "JSON"
    icon = "{ }"
    description = "Структурированные данные JSON с AI-извлечением"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate JSON source config."""
        errors = []
        
        if not config.get("file_id") and not config.get("filename"):
            errors.append("Необходимо указать file_id или filename")
        
        if errors:
            return ValidationResult.failure(errors)
        return ValidationResult.success()
    
    async def extract(
        self,
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs
    ) -> ExtractionResult:
        """Extract data from JSON file using AI-generated code."""
        start_time = time.time()
        
        if file_content is None:
            return ExtractionResult.failure("Содержимое файла не предоставлено")
        
        try:
            import json as json_lib
            
            # Parse JSON
            content_str = file_content.decode("utf-8")
            data = json_lib.loads(content_str)
            
            # Check if we have extraction code
            extraction_code = config.get("extraction_code")
            
            if extraction_code:
                # Execute AI-generated extraction code
                result = await self._execute_extraction_code(extraction_code, data)
                if result:
                    return result
            
            # Fallback: auto-extract if no code provided
            max_rows = config.get("max_rows", 100)
            tables = self._auto_extract(data, config.get("filename", "data"), max_rows=max_rows)
            
            extraction_time = int((time.time() - start_time) * 1000)
            
            return ExtractionResult(
                success=True,
                text=f"JSON файл '{config.get('filename', 'data.json')}' успешно обработан.",
                tables=tables,
                extraction_time_ms=extraction_time,
                metadata={
                    "has_extraction_code": bool(extraction_code),
                    "table_count": len(tables),
                }
            )
            
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка парсинга JSON: {str(e)}")
    
    async def _execute_extraction_code(self, code: str, data: Any) -> ExtractionResult | None:
        """Execute AI-generated extraction code.
        
        TODO: Implement secure sandbox execution.
        """
        # Placeholder - будет реализовано с sandbox execution
        return None
    
    def _auto_extract(self, data: Any, filename: str, max_rows: int | None = None) -> list[TableData]:
        """Auto-extract tables from JSON structure."""
        tables = []
        
        if isinstance(data, list) and data and isinstance(data[0], dict):
            # Root is array of objects - convert to table
            columns = self._infer_columns(data)
            tables.append(TableData(
                id=filename.replace(".json", ""),
                name=filename.replace(".json", ""),
                columns=columns,
                rows=data[:max_rows] if max_rows else data,
            ))
        
        elif isinstance(data, dict):
            # Look for arrays in top-level keys
            for key, value in data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    columns = self._infer_columns(value)
                    tables.append(TableData(
                        id=key,
                        name=key,
                        columns=columns,
                        rows=value[:max_rows] if max_rows else value,
                    ))
        
        return tables
    
    def _infer_columns(self, rows: list[dict]) -> list[dict[str, str]]:
        """Infer column definitions from rows."""
        if not rows:
            return []
        
        columns = []
        sample = rows[0]
        
        for key, value in sample.items():
            col_type = "text"
            if isinstance(value, (int, float)):
                col_type = "number"
            elif isinstance(value, bool):
                col_type = "boolean"
            
            columns.append({"name": key, "type": col_type})
        
        return columns
    
    def get_recommendations(self, config: dict[str, Any], preview_data: Any = None) -> list[str]:
        """Get AI recommendations for JSON extraction."""
        recommendations = []
        
        if preview_data and isinstance(preview_data, dict):
            for key, value in preview_data.items():
                if isinstance(value, list):
                    recommendations.append(f"Извлечь '{key}' как таблицу")
        
        recommendations.append("Автоматически извлечь все массивы")
        
        return recommendations
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for JSON dialog."""
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "file",
                    "accept": ".json",
                    "title": "JSON файл",
                },
                "extraction_code": {
                    "type": "string",
                    "format": "python",
                    "title": "Python код извлечения",
                    "description": "Генерируется AI-ассистентом",
                },
            },
        }
