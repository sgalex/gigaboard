"""API extractor - handles HTTP REST APIs."""
import logging
from typing import Any
import asyncio

import httpx

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class APIExtractor(BaseExtractor):
    """Extractor for HTTP API sources."""
    
    TIMEOUT = 30.0  # seconds
    MAX_RETRIES = 3
    
    async def extract(
        self,
        config: dict[str, Any],
        params: dict[str, Any] | None = None
    ) -> ExtractionResult:
        """Extract data from API.
        
        Config format:
            {
                "url": str,
                "method": str,  # GET, POST, etc.
                "headers": dict,  # optional
                "body": dict,  # optional, for POST/PUT
                "auth": dict  # optional, {type: "bearer", token: "..."}
            }
        
        Params format:
            {
                "timeout": float,  # optional override
                "retries": int  # optional override
            }
        """
        result = ExtractionResult()
        params = params or {}
        
        try:
            url = config.get("url")
            method = config.get("method", "GET").upper()
            headers = config.get("headers", {})
            body = config.get("body")
            auth_config = config.get("auth", {})
            
            if not url:
                result.errors.append("url is required")
                return result
            
            # Add authentication header if configured
            if auth_config:
                auth_type = auth_config.get("type", "").lower()
                if auth_type == "bearer":
                    token = auth_config.get("token")
                    headers["Authorization"] = f"Bearer {token}"
                elif auth_type == "basic":
                    # httpx will handle basic auth
                    pass
                elif auth_type == "api_key":
                    key_name = auth_config.get("key_name", "X-API-Key")
                    key_value = auth_config.get("key_value")
                    headers[key_name] = key_value
            
            # Execute request with retries
            timeout = params.get("timeout", self.TIMEOUT)
            max_retries = params.get("retries", self.MAX_RETRIES)
            
            response_data = await self._execute_with_retry(
                url=url,
                method=method,
                headers=headers,
                body=body,
                timeout=timeout,
                max_retries=max_retries
            )
            
            # Parse response
            await self._parse_response(response_data, result)
            
            result.metadata.update({
                "url": url,
                "method": method,
                "status_code": response_data.get("status_code")
            })
            
            logger.info(f"API request successful: {method} {url}")
            
        except Exception as e:
            logger.exception(f"API extraction failed: {e}")
            result.errors.append(f"API error: {str(e)}")
        
        return result
    
    async def _execute_with_retry(
        self,
        url: str,
        method: str,
        headers: dict,
        body: Any,
        timeout: float,
        max_retries: int
    ) -> dict[str, Any]:
        """Execute HTTP request with retry logic."""
        last_error = None
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(max_retries):
                try:
                    if method == "GET":
                        response = await client.get(url, headers=headers)
                    elif method == "POST":
                        response = await client.post(url, headers=headers, json=body)
                    elif method == "PUT":
                        response = await client.put(url, headers=headers, json=body)
                    elif method == "DELETE":
                        response = await client.delete(url, headers=headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                    
                    response.raise_for_status()
                    
                    return {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                    }
                
                except httpx.HTTPStatusError as e:
                    last_error = e
                    # Don't retry on 4xx errors (client errors)
                    if 400 <= e.response.status_code < 500:
                        raise
                    # Retry on 5xx (server errors)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
                except (httpx.RequestError, httpx.TimeoutException) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
        
        # All retries failed
        raise last_error
    
    async def _parse_response(
        self,
        response_data: dict[str, Any],
        result: ExtractionResult
    ):
        """Parse API response into result."""
        data = response_data.get("data")
        
        if isinstance(data, dict):
            # Check if it's a table-like response
            if "data" in data and isinstance(data["data"], list):
                # Common API pattern: {data: [...], meta: {...}}
                await self._parse_table_data(data["data"], result)
                result.metadata["api_meta"] = data.get("meta", {})
            else:
                result.text = f"API response with {len(data)} fields"
                result.metadata["api_response"] = data
        
        elif isinstance(data, list):
            # Array of records
            await self._parse_table_data(data, result)
        
        else:
            # Plain text or other
            result.text = str(data)[:1000]
            result.metadata["api_response"] = data
    
    async def _parse_table_data(
        self,
        data: list,
        result: ExtractionResult
    ):
        """Parse list of records into table."""
        if not data:
            result.text = "API returned empty array"
            return
        
        # If first item is a dict, treat as table
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
            rows = [[record.get(col) for col in columns] for record in data]
            
            table = self._create_table(
                name="api_data",
                columns=columns,
                rows=rows,
                metadata={"source": "api", "record_count": len(data)}
            )
            result.tables.append(table)
            
            result.text = f"API returned {len(data)} records with {len(columns)} fields"
        else:
            result.text = f"API returned {len(data)} items"
            result.metadata["api_data"] = data[:100]  # First 100 items
    
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate API source configuration."""
        errors = []
        
        url = config.get("url")
        if not url:
            errors.append("url is required")
        elif not url.startswith(("http://", "https://")):
            errors.append("url must start with http:// or https://")
        
        method = config.get("method", "GET").upper()
        if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            errors.append(f"Unsupported HTTP method: {method}")
        
        # Validate auth config
        auth_config = config.get("auth", {})
        if auth_config:
            auth_type = auth_config.get("type", "").lower()
            if auth_type not in ("bearer", "basic", "api_key"):
                errors.append(f"Unsupported auth type: {auth_type}")
            
            if auth_type == "bearer" and not auth_config.get("token"):
                errors.append("token is required for bearer auth")
            
            if auth_type == "api_key" and not auth_config.get("key_value"):
                errors.append("key_value is required for api_key auth")
        
        return len(errors) == 0, errors
