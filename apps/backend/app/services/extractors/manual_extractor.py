"""Manual extractor - handles manually entered data."""
import io
import logging
from typing import Any

import pandas as pd

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class ManualExtractor(BaseExtractor):
    """Extractor for manually entered data sources."""
    
    async def extract(
        self,
        config: dict[str, Any],
        params: dict[str, Any] | None = None
    ) -> ExtractionResult:
        """Extract manually entered data.
        
        Config format:
            {
                "data": dict | list | str,  # Manually entered data
                "format": str  # "text", "json", "table"
            }
        """
        result = ExtractionResult()
        params = params or {}
        
        try:
            data = config.get("data")
            data_format = config.get("format", "text")
            
            if data is None:
                result.errors.append("data is required")
                return result
            
            # Process based on format
            if data_format == "text":
                result.text = str(data)
            
            elif data_format == "json":
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    # List of records -> table
                    columns = list(data[0].keys())
                    rows = [[record.get(col) for col in columns] for record in data]
                    
                    table = self._create_table(
                        name="manual_data",
                        columns=columns,
                        rows=rows,
                        metadata={"source": "manual", "format": "json"}
                    )
                    result.tables.append(table)
                    result.text = f"Manual data: {len(data)} records"
                else:
                    result.text = f"Manual JSON data: {str(data)[:500]}"
                    result.metadata["json_data"] = data
            
            elif data_format == "table":
                # Expect dict with {columns: [...], rows: [[...]]}
                if isinstance(data, dict):
                    columns = data.get("columns", [])
                    rows = data.get("rows", [])
                    
                    if columns and rows:
                        table = self._create_table(
                            name="manual_table",
                            columns=columns,
                            rows=rows,
                            metadata={"source": "manual", "format": "table"}
                        )
                        result.tables.append(table)
                        result.text = f"Manual table: {len(rows)} rows × {len(columns)} columns"
                    else:
                        result.errors.append("table format requires 'columns' and 'rows' fields")
                else:
                    result.errors.append("table format expects dict with columns and rows")
            
            elif data_format == "csv":
                # Parse CSV string
                if isinstance(data, str):
                    try:
                        df = pd.read_csv(io.StringIO(data))
                        table = self._create_table(
                            name="manual_csv",
                            columns=[str(col) for col in df.columns],
                            rows=df.fillna("").values.tolist(),
                            metadata={"source": "manual", "format": "csv"}
                        )
                        result.tables.append(table)
                        result.text = f"Manual CSV: {len(df)} rows × {len(df.columns)} columns"
                    except Exception as e:
                        result.errors.append(f"Failed to parse CSV: {str(e)}")
                else:
                    result.errors.append("csv format expects string data")
            
            else:
                result.errors.append(f"Unsupported format: {data_format}")
            
            result.metadata.update({
                "format": data_format,
                "source": "manual"
            })
            
            logger.info(f"Processed manual data ({data_format} format)")
            
        except Exception as e:
            logger.exception(f"Manual extraction failed: {e}")
            result.errors.append(f"Manual data error: {str(e)}")
        
        return result
    
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate manual source configuration."""
        errors = []
        
        if "data" not in config:
            errors.append("data is required")
        
        data_format = config.get("format", "text")
        if data_format not in ("text", "json", "table"):
            errors.append(f"Unsupported format: {data_format}")
        
        # Validate table format structure
        if data_format == "table":
            data = config.get("data")
            if not isinstance(data, dict):
                errors.append("table format requires data to be a dict")
            elif not data.get("columns") or not data.get("rows"):
                errors.append("table format requires 'columns' and 'rows' fields")
        
        return len(errors) == 0, errors
