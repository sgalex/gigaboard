"""Excel Source Extractor - multi-sheet with AI extraction code.

Поддержка .xlsx файлов с несколькими листами.
AI генерирует Python код для сложного извлечения и объединения данных.
"""
import time
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
)


class ExcelSource(BaseSource):
    """Excel file source handler."""
    
    source_type = "excel"
    display_name = "Excel"
    icon = "📗"
    description = "Excel файлы с несколькими листами"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate Excel source config."""
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
        """Extract data from Excel file."""
        start_time = time.time()
        
        if file_content is None:
            return ExtractionResult.failure("Содержимое файла не предоставлено")
        
        try:
            import io
            import pandas as pd
            
            # Read Excel file
            excel_file = io.BytesIO(file_content)
            xlsx = pd.ExcelFile(excel_file)
            
            sheet_names = xlsx.sheet_names
            tables = []
            
            # Check for extraction code
            extraction_code = config.get("extraction_code")
            
            if extraction_code:
                # TODO: Execute AI-generated code
                pass
            
            # Default: extract each sheet as table
            max_rows = config.get("max_rows")  # None = все строки
            for sheet_name in sheet_names:
                df = pd.read_excel(xlsx, sheet_name=sheet_name)
                
                # Limit rows if specified
                if max_rows and max_rows > 0:
                    df = df.head(max_rows)
                
                # Convert to table format
                columns = [
                    {"name": str(col), "type": self._infer_pandas_type(df[col])}
                    for col in df.columns
                ]
                
                rows = [{str(k): v for k, v in row.items()} for row in df.to_dict(orient="records")]
                
                tables.append(TableData(
                    id=str(sheet_name),
                    name=str(sheet_name),
                    columns=columns,
                    rows=rows,
                ))
            
            extraction_time = int((time.time() - start_time) * 1000)
            
            return ExtractionResult(
                success=True,
                text=f"Excel файл '{config.get('filename', 'data.xlsx')}' содержит {len(sheet_names)} листов.",
                tables=tables,
                extraction_time_ms=extraction_time,
                metadata={
                    "sheet_names": sheet_names,
                    "table_count": len(tables),
                }
            )
            
        except ImportError:
            return ExtractionResult.failure("Необходимо установить pandas и openpyxl")
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка чтения Excel: {str(e)}")
    
    def _infer_pandas_type(self, series) -> str:
        """Infer column type from pandas series."""
        import pandas as pd
        
        if pd.api.types.is_numeric_dtype(series):
            return "number"
        elif pd.api.types.is_datetime64_any_dtype(series):
            return "date"
        return "text"
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for Excel dialog."""
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "file",
                    "accept": ".xlsx,.xls",
                    "title": "Excel файл",
                },
                "extraction_code": {
                    "type": "string",
                    "format": "python",
                    "title": "Python код извлечения",
                },
            },
        }
