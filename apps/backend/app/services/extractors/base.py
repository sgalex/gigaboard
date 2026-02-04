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
        columns: list[str],
        rows: list[list[Any]],
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Helper to create table structure.
        
        Args:
            name: Table name
            columns: List of column names
            rows: List of rows (each row is a list of values)
            metadata: Optional table metadata
            
        Returns:
            Table dict suitable for ContentNode
        """
        return {
            "name": name,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(columns),
            "metadata": metadata or {}
        }
