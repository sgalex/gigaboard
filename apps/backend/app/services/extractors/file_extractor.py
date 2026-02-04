"""File extractor - handles CSV, JSON, Excel files."""
import io
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class FileExtractor(BaseExtractor):
    """Extractor for file-based data sources."""
    
    SUPPORTED_FORMATS = {"csv", "json", "xlsx", "xls", "parquet", "txt"}
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    
    async def extract(
        self,
        config: dict[str, Any],
        params: dict[str, Any] | None = None
    ) -> ExtractionResult:
        """Extract data from file.
        
        Config format:
            {
                "file_id": str,  # UUID of uploaded file
                "filename": str,  # Original filename
                "mime_type": str,  # MIME type
                "size_bytes": int  # File size
            }
        
        Params format:
            {
                "preview_rows": int,  # optional, limit rows
                "sheets": list[str],  # optional for Excel, which sheets to read
                "db": AsyncSession  # Database session for file storage access
            }
        """
        result = ExtractionResult()
        params = params or {}
        
        try:
            file_id = config.get("file_id")
            filename = config.get("filename", "unknown")
            mime_type = config.get("mime_type", "")
            
            if not file_id:
                result.errors.append("file_id is required")
                return result
            
            # Get database session
            db = params.get("db")
            if not db:
                result.errors.append("Database session required for file extraction")
                return result
            
            # Determine format from mime_type or filename
            file_format = self._detect_format(mime_type, filename)
            if not file_format:
                result.errors.append(f"Cannot determine file format from: {filename}")
                return result
            
            if file_format not in self.SUPPORTED_FORMATS:
                result.errors.append(f"Unsupported format: {file_format}")
                return result
            
            # Get file content from storage
            from app.services.file_storage import get_storage
            storage = get_storage()
            file_content = await storage.get(file_id, db=db)
            
            if not file_content:
                result.errors.append(f"File not found: {file_id}")
                return result
            
            # Extract based on format
            if file_format == "csv":
                await self._extract_csv_from_bytes(file_content, params, result, filename)
            elif file_format == "json":
                await self._extract_json_from_bytes(file_content, params, result, filename)
            elif file_format in ("xlsx", "xls"):
                await self._extract_excel_from_bytes(file_content, params, result, filename)
            elif file_format == "parquet":
                await self._extract_parquet_from_bytes(file_content, params, result, filename)
            elif file_format == "txt":
                await self._extract_text_from_bytes(file_content, params, result, filename)
            
            # Add extraction metadata
            result.metadata.update({
                "file_id": file_id,
                "filename": filename,
                "format": file_format,
                "mime_type": mime_type,
                "size_bytes": config.get("size_bytes", len(file_content))
            })
            
            logger.info(f"Extracted file: {filename} ({len(result.tables)} tables)")
            
        except Exception as e:
            logger.exception(f"File extraction failed: {e}")
            result.errors.append(f"Extraction error: {str(e)}")
        
        return result
    
    def _detect_format(self, mime_type: str, filename: str) -> str | None:
        """Detect file format from MIME type or filename."""
        # MIME type mapping
        mime_formats = {
            "text/csv": "csv",
            "application/json": "json",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/vnd.ms-excel": "xls",
            "text/plain": "txt",
            "application/octet-stream": None  # Check extension
        }
        
        if mime_type in mime_formats:
            fmt = mime_formats[mime_type]
            if fmt:
                return fmt
        
        # Fallback to filename extension
        ext = Path(filename).suffix.lstrip(".").lower()
        if ext in self.SUPPORTED_FORMATS:
            return ext
        
        return None
    
    async def _extract_csv_from_bytes(
        self,
        file_content: bytes,
        params: dict,
        result: ExtractionResult,
        filename: str
    ):
        """Extract CSV from bytes."""
        csv_options = {
            "sep": ",",
            "header": 0,
        }
        
        # Preview rows limit
        if preview_rows := params.get("preview_rows"):
            csv_options["nrows"] = preview_rows
        
        df = pd.read_csv(io.BytesIO(file_content), **csv_options)
        
        # Convert to table structure
        table = self._dataframe_to_table(
            df,
            name=Path(filename).stem,
            metadata={"source": "csv", "rows_loaded": len(df)}
        )
        result.tables.append(table)
        
        # Generate text summary
        result.text = self._generate_dataframe_summary(df, Path(filename).stem)
    
    async def _extract_json_from_bytes(
        self,
        file_content: bytes,
        params: dict,
        result: ExtractionResult,
        filename: str
    ):
        """Extract JSON from bytes."""
        data = json.loads(file_content.decode('utf-8'))
        
        # Handle different JSON structures
        if isinstance(data, list):
            # List of records -> single table
            if data and isinstance(data[0], dict):
                df = pd.DataFrame(data)
                table = self._dataframe_to_table(
                    df,
                    name=Path(filename).stem,
                    metadata={"source": "json", "structure": "array"}
                )
                result.tables.append(table)
                result.text = self._generate_dataframe_summary(df, Path(filename).stem)
            else:
                result.text = f"JSON array with {len(data)} items"
                result.metadata["json_data"] = data[:100]  # First 100 items
        
        elif isinstance(data, dict):
            # Check if it's a table-like dict
            if all(isinstance(v, list) for v in data.values()):
                df = pd.DataFrame(data)
                table = self._dataframe_to_table(
                    df,
                    name=Path(filename).stem,
                    metadata={"source": "json", "structure": "dict"}
                )
                result.tables.append(table)
                result.text = self._generate_dataframe_summary(df, Path(filename).stem)
            else:
                result.text = f"JSON object with {len(data)} keys"
                result.metadata["json_data"] = data
        
        else:
            result.text = f"JSON value: {str(data)[:500]}"
            result.metadata["json_data"] = data
    
    async def _extract_excel_from_bytes(
        self,
        file_content: bytes,
        params: dict,
        result: ExtractionResult,
        filename: str
    ):
        """Extract Excel from bytes."""
        sheets_to_read = params.get("sheets")
        preview_rows = params.get("preview_rows")
        
        # Read all sheets or specified sheets
        excel_file = pd.ExcelFile(io.BytesIO(file_content))
        
        if sheets_to_read:
            sheet_names = [s for s in sheets_to_read if s in excel_file.sheet_names]
        else:
            sheet_names = excel_file.sheet_names
        
        summaries = []
        for sheet_name in sheet_names:
            df = pd.read_excel(
                io.BytesIO(file_content),
                sheet_name=sheet_name,
                nrows=preview_rows
            )
            
            table = self._dataframe_to_table(
                df,
                name=f"{Path(filename).stem}_{sheet_name}",
                metadata={"source": "excel", "sheet": sheet_name}
            )
            result.tables.append(table)
            summaries.append(self._generate_dataframe_summary(df, sheet_name))
        
        result.text = "\n\n".join(summaries)
    
    async def _extract_parquet_from_bytes(
        self,
        file_content: bytes,
        params: dict,
        result: ExtractionResult,
        filename: str
    ):
        """Extract Parquet from bytes."""
        import pyarrow.parquet as pq
        
        preview_rows = params.get("preview_rows")
        
        # Read Parquet file
        table = pq.read_table(io.BytesIO(file_content))
        df = table.to_pandas()
        
        # Apply row limit if specified
        if preview_rows:
            df = df.head(preview_rows)
        
        table_result = self._dataframe_to_table(
            df,
            name=Path(filename).stem,
            metadata={"source": "parquet", "rows_loaded": len(df)}
        )
        result.tables.append(table_result)
        
        # Generate text summary
        result.text = self._generate_dataframe_summary(df, Path(filename).stem)
    
    async def _extract_text_from_bytes(
        self,
        file_content: bytes,
        params: dict,
        result: ExtractionResult,
        filename: str
    ):
        """Extract plain text from bytes."""
        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Try with different encodings
            for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    text = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                result.errors.append("Cannot decode text file")
                return
        
        # Limit preview if requested
        if preview_lines := params.get("preview_rows"):
            lines = text.split('\n')[:preview_lines]
            text = '\n'.join(lines)
        
        result.text = text[:10000]  # Limit to 10k chars
        result.metadata["text_length"] = len(text)
        result.metadata["lines"] = len(text.split('\n'))
    
    def _dataframe_to_table(
        self,
        df: pd.DataFrame,
        name: str,
        metadata: dict | None = None
    ) -> dict[str, Any]:
        """Convert pandas DataFrame to table structure."""
        # Convert DataFrame to list of lists (handle NaN values)
        rows = df.fillna("").values.tolist()
        
        # Convert column names to strings
        columns = [str(col) for col in df.columns]
        
        return self._create_table(
            name=name,
            columns=columns,
            rows=rows,
            metadata=metadata
        )
    
    def _generate_dataframe_summary(self, df: pd.DataFrame, name: str) -> str:
        """Generate text summary of DataFrame."""
        lines = [
            f"Table: {name}",
            f"Rows: {len(df)}",
            f"Columns: {len(df.columns)}",
            "",
            "Columns:",
        ]
        
        for col in df.columns:
            dtype = str(df[col].dtype)
            non_null = df[col].count()
            lines.append(f"  - {col} ({dtype}): {non_null} non-null")
        
        return "\n".join(lines)
    
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate file source configuration."""
        errors = []
        
        file_id = config.get("file_id")
        if not file_id:
            errors.append("file_id is required")
        
        filename = config.get("filename", "")
        if not filename:
            errors.append("filename is required")
        
        mime_type = config.get("mime_type", "")
        file_format = self._detect_format(mime_type, filename) if mime_type or filename else None
        
        if not file_format:
            errors.append("Cannot determine file format from MIME type or filename")
        elif file_format not in self.SUPPORTED_FORMATS:
            errors.append(f"Unsupported format: {file_format}. Supported: {self.SUPPORTED_FORMATS}")
        
        return len(errors) == 0, errors
