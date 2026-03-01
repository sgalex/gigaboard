"""Base extractor interface for all source types."""
from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExtractionResult:
    """Result of data extraction operation."""
    
    text: str | None = None
    """Text summary of extracted data."""
    
    tables: list[dict[str, Any]] | None = None
    """List of extracted tables with metadata."""
    
    metadata: dict[str, Any] | None = None
    """Additional extraction metadata."""
    
    errors: list[str] | None = None
    """List of errors encountered during extraction."""
    
    def __post_init__(self):
        """Initialize default values."""
        if self.tables is None:
            self.tables = []
        if self.metadata is None:
            self.metadata = {}
        if self.errors is None:
            self.errors = []
    
    @property
    def is_success(self) -> bool:
        """Check if extraction was successful."""
        # After __post_init__, these are guaranteed to be non-None
        return len(self.errors or []) == 0 and bool(self.text or self.tables)
    
    def to_content_dict(self) -> dict[str, Any]:
        """Convert to ContentNode content format.
        
        Returns:
            Dict suitable for ContentNode.content JSONB field
        """
        return {
            "text": self.text,
            "tables": self.tables or [],
            "extracted_at": datetime.utcnow().isoformat()
        }


class BaseExtractor(ABC):
    """Base class for all data extractors."""
    
    @abstractmethod
    async def extract(
        self,
        config: dict[str, Any],
        params: dict[str, Any] | None = None
    ) -> ExtractionResult:
        """Extract data from source.
        
        Args:
            config: Source configuration (from SourceNode.config)
            params: Additional parameters for extraction
            
        Returns:
            ExtractionResult with extracted data
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate source configuration.
        
        Args:
            config: Source configuration to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        pass
    
    def _create_table(
        self,
        name: str,
        columns: list[str] | list[dict[str, str]],
        rows: list[list[Any]] | list[dict[str, Any]],
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Helper to create table structure in unified format.
        
        Принимает columns как list[str] или list[{name,type}],
        rows как list[list] или list[dict].
        Всегда выдаёт:
          columns: [{name: str, type: str}, ...]
          rows: [{col_name: value, ...}, ...]
        """
        # Normalize columns to [{name, type}]
        typed_columns = []
        col_names = []
        need_type_inference = False
        for col in columns:
            if isinstance(col, dict):
                typed_columns.append({"name": col.get("name", ""), "type": col.get("type", "string")})
                col_names.append(col.get("name", ""))
            else:
                col_names.append(str(col))
                typed_columns.append({"name": str(col), "type": "string"})
                need_type_inference = True
        
        # Normalize rows to [{col: val}, ...]
        dict_rows = []
        for row in rows:
            if isinstance(row, dict):
                dict_rows.append(row)
            elif isinstance(row, (list, tuple)):
                dict_rows.append({col_names[j]: v for j, v in enumerate(row) if j < len(col_names)})
        
        # Infer types from values if columns were plain strings
        if need_type_inference and dict_rows:
            for i, col_name in enumerate(col_names):
                for row in dict_rows:
                    val = row.get(col_name)
                    if val is not None and val != "":
                        if isinstance(val, bool):
                            typed_columns[i]["type"] = "bool"
                        elif isinstance(val, int):
                            typed_columns[i]["type"] = "int"
                        elif isinstance(val, float):
                            typed_columns[i]["type"] = "float"
                        break
        
        return {
            "name": name,
            "columns": typed_columns,
            "rows": dict_rows,
            "row_count": len(dict_rows),
            "column_count": len(typed_columns),
            "metadata": metadata or {}
        }
