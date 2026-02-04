"""Stream Source Extractor - real-time data streams (Phase 4).

Поддержка (планируется):
- WebSocket
- Server-Sent Events (SSE)
- Apache Kafka

Заглушка для Phase 4.
"""
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
)


class StreamSource(BaseSource):
    """Real-time stream source handler (Phase 4 stub)."""
    
    source_type = "stream"
    display_name = "Стрим"
    icon = "📡"
    description = "Real-time потоки данных (скоро)"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate stream source config."""
        return ValidationResult.failure(
            ["Стриминговые источники будут доступны в Phase 4"]
        )
    
    async def extract(
        self,
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs
    ) -> ExtractionResult:
        """Stream extraction - not implemented yet."""
        return ExtractionResult.failure(
            "Стриминговые источники будут доступны в Phase 4"
        )
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for stream dialog."""
        return {
            "type": "object",
            "properties": {
                "stream_type": {
                    "type": "string",
                    "enum": ["websocket", "sse", "kafka"],
                    "title": "Тип стрима",
                },
                "url": {"type": "string", "title": "URL"},
            },
            "description": "Стриминговые источники будут доступны в Phase 4",
        }
