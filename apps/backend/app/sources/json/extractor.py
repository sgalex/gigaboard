"""JSON Source Extractor with schema snapshot and normalization."""
import time
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
)
from app.sources.json.normalizer import auto_normalize_json, extract_tables_from_mapping
from app.sources.json.schema_extractor import extract_schema_snapshot


class JSONSource(BaseSource):
    """JSON file source handler with auto schema extraction."""
    
    source_type = "json"
    display_name = "JSON"
    icon = "{ }"
    description = "Структурированные данные JSON с автоматической нормализацией"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate JSON source config."""
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
        """Extract and normalize JSON into one or multiple tables."""
        start_time = time.time()

        if file_content is None:
            return ExtractionResult.failure("Содержимое файла не предоставлено")

        try:
            import json as json_lib

            content_str = self._decode_file(file_content)
            data = json_lib.loads(content_str)

            max_rows = config.get("max_rows")
            if isinstance(max_rows, int) and max_rows <= 0:
                max_rows = None

            schema_snapshot = extract_schema_snapshot(data)
            config["schema_snapshot"] = schema_snapshot

            extraction_code = config.get("extraction_code")
            if extraction_code:
                # Placeholder for future safe sandbox execution. We keep this branch
                # to preserve backward compatibility of existing configs.
                result = await self._execute_extraction_code(extraction_code, data)
                if result:
                    config.setdefault("generation_meta", {})
                    config["generation_meta"]["generated_by"] = "extraction_code"
                    return result

            mapping_spec = config.get("mapping_spec")
            tables: list[TableData] = []
            generation_meta: dict[str, Any] = {"generated_by": "heuristic", "warnings": []}

            if isinstance(mapping_spec, dict) and mapping_spec.get("tables"):
                tables = extract_tables_from_mapping(data, mapping_spec, max_rows=max_rows)
                if not tables:
                    generation_meta["warnings"].append(
                        "Saved mapping_spec produced no tables; fallback to auto-normalization."
                    )

            if not tables:
                normalized = auto_normalize_json(data, max_rows=max_rows)
                tables = normalized.tables
                mapping_spec = normalized.mapping_spec
                generation_meta = normalized.generation_meta
                config["mapping_spec"] = mapping_spec
            else:
                config["mapping_spec"] = mapping_spec

            config["generation_meta"] = generation_meta

            extraction_time = int((time.time() - start_time) * 1000)

            return ExtractionResult(
                success=True,
                text=f"JSON файл '{config.get('filename', 'data.json')}' успешно обработан.",
                tables=tables,
                extraction_time_ms=extraction_time,
                metadata={
                    "schema_version": schema_snapshot.get("version"),
                    "table_count": len(tables),
                    "generation_meta": generation_meta,
                }
            )

        except Exception as e:
            return ExtractionResult.failure(f"Ошибка парсинга JSON: {str(e)}")

    def _decode_file(self, file_content: bytes) -> str:
        """Decode JSON file bytes with a small set of common encodings."""
        for encoding in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                return file_content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return file_content.decode("utf-8", errors="replace")

    async def _execute_extraction_code(self, code: str, data: Any) -> ExtractionResult | None:
        """Execute AI-generated extraction code.

        TODO: implement safe sandbox and convert output to TableData.
        """
        return None

    def get_recommendations(self, config: dict[str, Any], preview_data: Any = None) -> list[str]:
        """Get extraction recommendations for JSON source."""
        recommendations = []

        if preview_data and isinstance(preview_data, dict):
            for key, value in preview_data.items():
                if isinstance(value, list):
                    recommendations.append(f"Извлечь '{key}' как таблицу")

        recommendations.append("Автоматически извлечь схему и нормализованные таблицы")
        return recommendations

    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for JSON dialog."""
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "file",
                    "accept": ".json",
                    "title": "JSON файл",
                },
                "extraction_code": {
                    "type": "string",
                    "format": "python",
                    "title": "Python код извлечения",
                    "description": "Опциональный пользовательский код (sandbox planned)",
                },
            },
        }
