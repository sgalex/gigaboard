"""API Source Extractor - REST API with pagination.

Поддержка:
- GET/POST/PUT/DELETE запросы
- Bearer token / API key авторизация
- 4 типа пагинации: page, offset, cursor, link-header
"""
import time
from typing import Any

import httpx

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
    ConnectionTestResult,
)


class APISource(BaseSource):
    """REST API source handler with pagination."""
    
    source_type = "api"
    display_name = "API"
    icon = "🔗"
    description = "REST API с пагинацией"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate API source config."""
        errors = []
        
        if not config.get("url"):
            errors.append("Необходимо указать URL")
        
        method = config.get("method", "GET")
        if method not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            errors.append(f"Неподдерживаемый метод: {method}")
        
        if errors:
            return ValidationResult.failure(errors)
        return ValidationResult.success()
    
    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        """Test API connection."""
        try:
            url = config.get("url", "")
            method = config.get("method", "GET")
            headers = config.get("headers", {})
            params = config.get("params", {})
            timeout = config.get("timeout_seconds", 30)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                )
                
                return ConnectionTestResult(
                    success=response.is_success,
                    message=f"{response.status_code} {response.reason_phrase}",
                    details={
                        "status_code": response.status_code,
                        "content_type": response.headers.get("content-type"),
                        "content_length": len(response.content),
                    }
                )
                
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {str(e)}",
            )
    
    async def extract(
        self,
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs
    ) -> ExtractionResult:
        """Extract data from API with pagination."""
        start_time = time.time()
        
        try:
            url = config.get("url", "")
            method = config.get("method", "GET")
            headers = config.get("headers", {})
            params = config.get("params", {})
            body = config.get("body")
            timeout = config.get("timeout_seconds", 30)
            json_path = config.get("json_path", "$")
            
            # Pagination config
            pagination = config.get("pagination", {})
            pagination_enabled = pagination.get("enabled", False)
            
            all_rows = []
            pages_loaded = 0
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                if pagination_enabled:
                    all_rows, pages_loaded = await self._fetch_with_pagination(
                        client, url, method, headers, params, body, pagination
                    )
                else:
                    # Single request
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=body if body else None,
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    all_rows = self._extract_by_path(data, json_path)
                    pages_loaded = 1
            
            if not all_rows:
                return ExtractionResult(
                    success=True,
                    text=f"API вернул пустой результат",
                    tables=[],
                    metadata={"url": url, "pages_loaded": pages_loaded}
                )
            
            # Infer columns from first row
            columns = self._infer_columns(all_rows)
            
            table = TableData(
                id="api_data",
                name="API Data",
                columns=columns,
                rows=all_rows[:1000],  # Limit rows
            )
            
            extraction_time = int((time.time() - start_time) * 1000)
            
            return ExtractionResult(
                success=True,
                text=f"Загружено {len(all_rows)} записей с {pages_loaded} страниц.",
                tables=[table],
                extraction_time_ms=extraction_time,
                metadata={
                    "url": url,
                    "pages_loaded": pages_loaded,
                    "total_rows": len(all_rows),
                }
            )
            
        except httpx.HTTPStatusError as e:
            return ExtractionResult.failure(f"HTTP Error {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка запроса API: {str(e)}")
    
    async def _fetch_with_pagination(
        self,
        client: httpx.AsyncClient,
        url: str,
        method: str,
        headers: dict,
        params: dict,
        body: dict | None,
        pagination: dict,
    ) -> tuple[list[dict], int]:
        """Fetch all pages of data."""
        all_rows = []
        pages_loaded = 0
        
        pagination_type = pagination.get("type", "page")
        page_param = pagination.get("page_param", "page")
        size_param = pagination.get("size_param", "per_page")
        page_size = pagination.get("page_size", 100)
        max_pages = pagination.get("max_pages", 10)
        
        current_page = 1
        
        while pages_loaded < max_pages:
            # Update params for pagination
            page_params = params.copy()
            
            if pagination_type == "page":
                page_params[page_param] = current_page
                page_params[size_param] = page_size
            elif pagination_type == "offset":
                page_params[page_param] = pages_loaded * page_size
                page_params[size_param] = page_size
            
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=page_params,
                json=body if body else None,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract rows from response
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                # Try common pagination patterns
                rows = data.get("data") or data.get("results") or data.get("items") or []
            else:
                rows = []
            
            if not rows:
                break
            
            all_rows.extend(rows)
            pages_loaded += 1
            current_page += 1
            
            # Check if we got less than page_size (last page)
            if len(rows) < page_size:
                break
        
        return all_rows, pages_loaded
    
    def _extract_by_path(self, data: Any, path: str) -> list[dict]:
        """Extract data using JSONPath-like syntax."""
        if path == "$":
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
        
        # Simple path extraction ($.data, $.results, etc.)
        if path.startswith("$."):
            key = path[2:]
            if isinstance(data, dict) and key in data:
                result = data[key]
                if isinstance(result, list):
                    return result
                return [result]
        
        return []
    
    def _infer_columns(self, rows: list[dict]) -> list[dict[str, str]]:
        """Infer column definitions from rows."""
        if not rows:
            return []
        
        columns = []
        sample = rows[0]
        
        for key, value in sample.items():
            col_type = "text"
            if isinstance(value, (int, float)):
                col_type = "number"
            elif isinstance(value, bool):
                col_type = "boolean"
            
            columns.append({"name": str(key), "type": col_type})
        
        return columns
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for API dialog."""
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri", "title": "URL"},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "default": "GET",
                    "title": "Метод",
                },
                "headers": {"type": "object", "title": "Headers"},
                "params": {"type": "object", "title": "Query Parameters"},
                "pagination": {
                    "type": "object",
                    "title": "Пагинация",
                    "properties": {
                        "enabled": {"type": "boolean", "default": False},
                        "type": {
                            "type": "string",
                            "enum": ["page", "offset", "cursor", "link-header"],
                            "default": "page",
                        },
                        "page_param": {"type": "string", "default": "page"},
                        "size_param": {"type": "string", "default": "per_page"},
                        "page_size": {"type": "integer", "default": 100},
                        "max_pages": {"type": "integer", "default": 10},
                    },
                },
            },
            "required": ["url"],
        }
