"""Data extractors for different source types.

См. docs/SOURCE_CONTENT_NODE_CONCEPT.md для деталей.
"""
from .base import BaseExtractor, ExtractionResult
from .file_extractor import FileExtractor
from .database_extractor import DatabaseExtractor
from .api_extractor import APIExtractor
from .prompt_extractor import PromptExtractor
from .stream_extractor import StreamExtractor
from .manual_extractor import ManualExtractor

__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "FileExtractor",
    "DatabaseExtractor",
    "APIExtractor",
    "PromptExtractor",
    "StreamExtractor",
    "ManualExtractor",
]
