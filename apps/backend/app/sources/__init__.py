"""Sources module - pluggable data source extractors.

Каждый тип источника имеет свою логику извлечения данных.
См. docs/SOURCE_NODE_CONCEPT.md для деталей архитектуры.
"""
from app.sources.base import BaseSource, ExtractionResult, ValidationResult, TableData
from app.sources.registry import SourceRegistry, get_source_handler

# Import all source handlers
from app.sources.csv import CSVSource
from app.sources.json import JSONSource
from app.sources.excel import ExcelSource
from app.sources.document import DocumentSource
from app.sources.api import APISource
from app.sources.database import DatabaseSource
from app.sources.research import ResearchSource
from app.sources.manual import ManualSource
from app.sources.stream import StreamSource

# Register all handlers
SourceRegistry.register(CSVSource)
SourceRegistry.register(JSONSource)
SourceRegistry.register(ExcelSource)
SourceRegistry.register(DocumentSource)
SourceRegistry.register(APISource)
SourceRegistry.register(DatabaseSource)
SourceRegistry.register(ResearchSource)
SourceRegistry.register(ManualSource)
SourceRegistry.register(StreamSource)

__all__ = [
    # Base classes
    "BaseSource",
    "ExtractionResult",
    "ValidationResult",
    "TableData",
    # Registry
    "SourceRegistry",
    "get_source_handler",
    # Source handlers
    "CSVSource",
    "JSONSource",
    "ExcelSource",
    "DocumentSource",
    "APISource",
    "DatabaseSource",
    "ResearchSource",
    "ManualSource",
    "StreamSource",
]
