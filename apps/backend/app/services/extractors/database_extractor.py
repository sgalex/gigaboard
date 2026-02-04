"""Database extractor - handles SQL queries."""
import logging
from typing import Any
from urllib.parse import urlparse

import asyncpg
import aiomysql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class DatabaseExtractor(BaseExtractor):
    """Extractor for database sources."""
    
    SUPPORTED_DATABASES = {"postgresql", "mysql", "sqlite"}
    MAX_ROWS = 10000
    
    async def extract(
        self,
        config: dict[str, Any],
        params: dict[str, Any] | None = None
    ) -> ExtractionResult:
        """Extract data from database.
        
        Config format:
            {
                "connection_string": str,  # Database URL
                "query": str,  # SQL query to execute
                "database_type": str  # postgresql, mysql, sqlite
            }
        
        Params format:
            {
                "limit": int  # optional, limit rows
            }
        """
        result = ExtractionResult()
        params = params or {}
        
        try:
            connection_string = config.get("connection_string")
            query = config.get("query")
            db_type = config.get("database_type", "postgresql")
            
            if not connection_string:
                result.errors.append("connection_string is required")
                return result
            
            if not query:
                result.errors.append("query is required")
                return result
            
            # Add limit if specified
            limit = params.get("limit", self.MAX_ROWS)
            if limit and "limit" not in query.lower():
                query = f"{query.rstrip(';')} LIMIT {limit}"
            
            # Execute query based on database type
            if db_type == "postgresql":
                await self._extract_postgresql(connection_string, query, result)
            elif db_type == "mysql":
                await self._extract_mysql(connection_string, query, result)
            elif db_type == "sqlite":
                await self._extract_sqlite(connection_string, query, result)
            else:
                result.errors.append(f"Unsupported database type: {db_type}")
                return result
            
            result.metadata.update({
                "database_type": db_type,
                "query": query[:500]  # Truncate long queries
            })
            
            logger.info(f"Executed database query: {db_type} ({len(result.tables)} tables)")
            
        except Exception as e:
            logger.exception(f"Database extraction failed: {e}")
            result.errors.append(f"Database error: {str(e)}")
        
        return result
    
    async def _extract_postgresql(
        self,
        connection_string: str,
        query: str,
        result: ExtractionResult
    ):
        """Extract from PostgreSQL."""
        conn = await asyncpg.connect(connection_string)
        try:
            rows = await conn.fetch(query)
            
            if rows:
                # Get column names from first row
                columns = list(rows[0].keys())
                
                # Convert rows to list of lists
                data_rows = [list(row.values()) for row in rows]
                
                table = self._create_table(
                    name="query_result",
                    columns=columns,
                    rows=data_rows,
                    metadata={"database": "postgresql", "row_count": len(rows)}
                )
                result.tables.append(table)
                
                result.text = f"PostgreSQL query returned {len(rows)} rows with {len(columns)} columns"
            else:
                result.text = "Query returned no rows"
        
        finally:
            await conn.close()
    
    async def _extract_mysql(
        self,
        connection_string: str,
        query: str,
        result: ExtractionResult
    ):
        """Extract from MySQL."""
        # Parse connection string
        parsed = urlparse(connection_string)
        
        conn = await aiomysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            db=parsed.path.lstrip('/'),
            autocommit=True
        )
        
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(query)
                rows = await cursor.fetchall()
                
                if rows:
                    # Get column names from cursor description
                    columns = [desc[0] for desc in cursor.description]
                    
                    # Convert rows to list of lists
                    data_rows = [list(row) for row in rows]
                    
                    table = self._create_table(
                        name="query_result",
                        columns=columns,
                        rows=data_rows,
                        metadata={"database": "mysql", "row_count": len(rows)}
                    )
                    result.tables.append(table)
                    
                    result.text = f"MySQL query returned {len(rows)} rows with {len(columns)} columns"
                else:
                    result.text = "Query returned no rows"
        
        finally:
            conn.close()
    
    async def _extract_sqlite(
        self,
        connection_string: str,
        query: str,
        result: ExtractionResult
    ):
        """Extract from SQLite using SQLAlchemy."""
        engine = create_async_engine(connection_string)
        
        try:
            async with engine.connect() as conn:
                cursor_result = await conn.execute(text(query))
                rows = cursor_result.fetchall()
                
                if rows:
                    # Get column names
                    columns = list(cursor_result.keys())
                    
                    # Convert rows to list of lists
                    data_rows = [list(row) for row in rows]
                    
                    table = self._create_table(
                        name="query_result",
                        columns=columns,
                        rows=data_rows,
                        metadata={"database": "sqlite", "row_count": len(rows)}
                    )
                    result.tables.append(table)
                    
                    result.text = f"SQLite query returned {len(rows)} rows with {len(columns)} columns"
                else:
                    result.text = "Query returned no rows"
        
        finally:
            await engine.dispose()
    
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate database source configuration."""
        errors = []
        
        if not config.get("connection_string"):
            errors.append("connection_string is required")
        
        if not config.get("query"):
            errors.append("query is required")
        
        db_type = config.get("database_type", "postgresql")
        if db_type not in self.SUPPORTED_DATABASES:
            errors.append(f"Unsupported database: {db_type}. Supported: {self.SUPPORTED_DATABASES}")
        
        # Basic SQL injection check
        query = config.get("query", "").lower()
        dangerous_keywords = ["drop", "delete", "truncate", "alter", "create"]
        if any(keyword in query for keyword in dangerous_keywords):
            errors.append("Query contains potentially dangerous keywords (DROP, DELETE, etc.)")
        
        return len(errors) == 0, errors
