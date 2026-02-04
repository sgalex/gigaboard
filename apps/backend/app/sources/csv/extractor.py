"""CSV Source Extractor - auto-parse CSV files with AI schema detection.

Автоматически определяет:
- Разделитель (запятая, точка с запятой, табуляция)
- Кодировку (UTF-8, CP1251, etc.)
- Наличие заголовков
- Типы столбцов
"""
import csv
import io
import time
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
    ConnectionTestResult,
)


class CSVSource(BaseSource):
    """CSV file source handler."""
    
    source_type = "csv"
    display_name = "CSV"
    icon = "📊"
    description = "Табличные данные CSV с автоопределением схемы"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate CSV source config."""
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
        """Extract data from CSV file."""
        start_time = time.time()
        
        if file_content is None:
            return ExtractionResult.failure("Содержимое файла не предоставлено")
        
        try:
            # Determine encoding
            encoding = config.get("encoding", "utf-8")
            try:
                content_str = file_content.decode(encoding)
            except UnicodeDecodeError:
                # Fallback to cp1251 for Russian files
                content_str = file_content.decode("cp1251")
                encoding = "cp1251"
            
            # Determine delimiter
            delimiter = config.get("delimiter")
            if not delimiter:
                # Auto-detect delimiter
                sniffer = csv.Sniffer()
                try:
                    sample = content_str[:4096]
                    dialect = sniffer.sniff(sample, delimiters=",;\t|")
                    delimiter = dialect.delimiter
                except csv.Error:
                    delimiter = ","
            
            # Parse CSV
            reader = csv.reader(io.StringIO(content_str), delimiter=delimiter)
            rows_list = list(reader)
            
            if not rows_list:
                return ExtractionResult.failure("CSV файл пуст")
            
            # Check for header
            has_header = config.get("has_header", True)
            if has_header:
                header = rows_list[0]
                data_rows = rows_list[1:]
            else:
                # Generate column names
                header = [f"column_{i+1}" for i in range(len(rows_list[0]))]
                data_rows = rows_list
            
            # Filter columns if specified
            selected_columns = config.get("selected_columns")
            if selected_columns:
                col_indices = [header.index(col) for col in selected_columns if col in header]
                header = [header[i] for i in col_indices]
                data_rows = [[row[i] for i in col_indices] for row in data_rows]
            
            # Limit rows if max_rows specified (по умолчанию читаем все)
            max_rows = config.get("max_rows")
            if max_rows and max_rows > 0:
                data_rows = data_rows[:max_rows]
            
            # Infer column types
            columns = []
            for i, col_name in enumerate(header):
                col_type = self._infer_column_type([row[i] if i < len(row) else "" for row in data_rows[:100]])
                columns.append({"name": col_name, "type": col_type})
            
            # Convert to row dicts
            rows = []
            for row in data_rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i] if i < len(row) else ""
                    row_dict[col["name"]] = self._convert_value(value, col["type"])
                rows.append(row_dict)
            
            # Create table
            table_name = config.get("filename", "data").replace(".csv", "")
            table = TableData(
                id=table_name,
                name=table_name,
                columns=columns,
                rows=rows,
            )
            
            extraction_time = int((time.time() - start_time) * 1000)
            
            return ExtractionResult(
                success=True,
                text=f"CSV файл '{config.get('filename', 'data.csv')}' содержит {len(rows)} строк и {len(columns)} столбцов.",
                tables=[table],
                extraction_time_ms=extraction_time,
                metadata={
                    "encoding": encoding,
                    "delimiter": delimiter,
                    "has_header": has_header,
                    "row_count": len(rows),
                    "column_count": len(columns),
                }
            )
            
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка парсинга CSV: {str(e)}")
    
    def _infer_column_type(self, values: list[str]) -> str:
        """Infer column type from sample values."""
        # Check if all values are numbers
        numeric_count = 0
        date_count = 0
        
        for val in values:
            if not val:
                continue
            
            # Check numeric
            try:
                float(val.replace(",", ".").replace(" ", ""))
                numeric_count += 1
                continue
            except ValueError:
                pass
            
            # Check date patterns
            if any(sep in val for sep in ["-", "/", "."]) and len(val) <= 20:
                date_count += 1
        
        non_empty = sum(1 for v in values if v)
        if non_empty == 0:
            return "text"
        
        if numeric_count / non_empty > 0.8:
            return "number"
        if date_count / non_empty > 0.8:
            return "date"
        return "text"
    
    def _convert_value(self, value: str, col_type: str) -> Any:
        """Convert string value to appropriate type."""
        if not value:
            return None
        
        if col_type == "number":
            try:
                return float(value.replace(",", ".").replace(" ", ""))
            except ValueError:
                return value
        
        return value
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for CSV dialog."""
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "file",
                    "accept": ".csv",
                    "title": "CSV файл",
                },
                "delimiter": {
                    "type": "string",
                    "enum": ["auto", ",", ";", "\t", "|"],
                    "default": "auto",
                    "title": "Разделитель",
                },
                "encoding": {
                    "type": "string",
                    "enum": ["auto", "utf-8", "cp1251", "cp1252"],
                    "default": "auto",
                    "title": "Кодировка",
                },
                "has_header": {
                    "type": "boolean",
                    "default": True,
                    "title": "Первая строка — заголовки",
                },
            },
        }
