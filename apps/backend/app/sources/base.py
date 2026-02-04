"""Base Source - abstract class for all source type handlers.

Каждый тип источника (CSV, JSON, API, etc.) реализует этот интерфейс.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class ValidationResult:
    """Result of config validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    @classmethod
    def success(cls) -> "ValidationResult":
        return cls(is_valid=True)
    
    @classmethod
    def failure(cls, errors: list[str]) -> "ValidationResult":
        return cls(is_valid=False, errors=errors)


@dataclass
class TableData:
    """Structured table data."""
    id: str
    name: str
    columns: list[dict[str, str]]  # [{"name": "col1", "type": "string"}, ...]
    rows: list[dict[str, Any]]


@dataclass
class ExtractionResult:
    """Result of data extraction."""
    success: bool
    text: str = ""
    tables: list[TableData] = field(default_factory=list)
    error: str | None = None
    extraction_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def failure(cls, error: str) -> "ExtractionResult":
        return cls(success=False, error=error)
    
    def to_content(self) -> dict[str, Any]:
        """Convert to ContentNode content format.
        
        Frontend expects:
        - columns: string[] (array of column names)
        - rows: Array<Array<any>> (2D array of values)
        - row_count, column_count
        """
        tables = []
        for t in self.tables:
            # Extract column names
            column_names = [col["name"] if isinstance(col, dict) else col for col in t.columns]
            
            # Convert rows from dict to array format
            rows_array = []
            for row in t.rows:
                if isinstance(row, dict):
                    # Row is a dict - convert to array in column order
                    row_values = [row.get(col_name, "") for col_name in column_names]
                else:
                    # Row is already an array
                    row_values = row
                rows_array.append(row_values)
            
            tables.append({
                "name": t.name,
                "columns": column_names,
                "rows": rows_array,
                "row_count": len(rows_array),
                "column_count": len(column_names),
            })
        
        return {
            "text": self.text,
            "tables": tables
        }


@dataclass
class ConnectionTestResult:
    """Result of connection test."""
    success: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class BaseSource(ABC):
    """Abstract base class for all source type handlers.
    
    Каждый тип источника (CSV, JSON, Excel, API, Database, etc.)
    должен реализовать этот интерфейс.
    """
    
    # Source type identifier (csv, json, excel, document, api, database, research, manual, stream)
    source_type: str
    
    # Human-readable name for UI
    display_name: str
    
    # Icon for vitrina (emoji or icon name)
    icon: str
    
    # Description for tooltip
    description: str
    
    @abstractmethod
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate source configuration.
        
        Args:
            config: Source-specific configuration dict
            
        Returns:
            ValidationResult with is_valid flag and any errors/warnings
        """
        pass
    
    @abstractmethod
    async def extract(
        self, 
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs
    ) -> ExtractionResult:
        """Extract data from source.
        
        Args:
            config: Source-specific configuration
            file_content: Optional file content for file-based sources
            **kwargs: Additional context (db session, gigachat client, etc.)
            
        Returns:
            ExtractionResult with text and tables
        """
        pass
    
    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        """Test connection to source (for API, Database, Stream).
        
        Default implementation returns success.
        Override for sources that support connection testing.
        
        Args:
            config: Source-specific configuration
            
        Returns:
            ConnectionTestResult
        """
        return ConnectionTestResult(success=True, message="Connection test not implemented")
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for dialog form.
        
        Used by frontend to generate dynamic forms.
        Default implementation returns empty schema.
        
        Returns:
            JSON Schema dict for the configuration form
        """
        return {}
    
    def get_recommendations(self, config: dict[str, Any], preview_data: Any = None) -> list[str]:
        """Get AI recommendations for extraction.
        
        Args:
            config: Current configuration
            preview_data: Optional preview of source data
            
        Returns:
            List of recommendation strings for UI
        """
        return []
