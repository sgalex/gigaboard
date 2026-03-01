"""Database Source Extractor - SQL database with table selection.

Поддержка:
- PostgreSQL
- MySQL
- SQLite

Пользователь выбирает таблицы и указывает WHERE условия.
"""
import time
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
    ConnectionTestResult,
)


class DatabaseSource(BaseSource):
    """SQL Database source handler."""
    
    source_type = "database"
    display_name = "База данных"
    icon = "🗄️"
    description = "PostgreSQL, MySQL, SQLite"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate database source config."""
        errors = []
        
        db_type = config.get("db_type")
        if not db_type:
            errors.append("Необходимо указать тип СУБД")
        elif db_type not in ["postgresql", "mysql", "sqlite"]:
            errors.append(f"Неподдерживаемый тип СУБД: {db_type}")
        
        if db_type == "sqlite":
            if not config.get("path"):
                errors.append("Для SQLite необходимо указать путь к файлу")
        else:
            if not config.get("host"):
                errors.append("Необходимо указать хост")
            if not config.get("database"):
                errors.append("Необходимо указать имя базы данных")
        
        tables = config.get("tables", [])
        if not tables:
            errors.append("Необходимо выбрать хотя бы одну таблицу")
        
        if errors:
            return ValidationResult.failure(errors)
        return ValidationResult.success()
    
    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        """Test database connection."""
        try:
            connection_string = self._build_connection_string(config)
            
            # Try to connect using sqlalchemy
            from sqlalchemy import create_engine, text
            
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            
            return ConnectionTestResult(
                success=True,
                message=f"Подключено к {config.get('db_type')}",
                details={"database": config.get("database")}
            )
            
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Ошибка подключения: {str(e)}",
            )
    
    async def extract(
        self,
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs
    ) -> ExtractionResult:
        """Extract data from database tables."""
        start_time = time.time()
        
        try:
            from sqlalchemy import create_engine, text, inspect
            
            connection_string = self._build_connection_string(config)
            engine = create_engine(connection_string)
            
            tables_config = config.get("tables", [])
            tables = []
            total_rows = 0
            
            with engine.connect() as conn:
                inspector = inspect(engine)
                
                for table_config in tables_config:
                    table_name = table_config.get("name")
                    where_clause = table_config.get("where", "")
                    limit = table_config.get("limit", 1000)
                    
                    # Build query
                    query = f"SELECT * FROM {table_name}"
                    if where_clause:
                        query += f" WHERE {where_clause}"
                    query += f" LIMIT {limit}"
                    
                    # Execute query
                    result = conn.execute(text(query))
                    rows = [dict(row._mapping) for row in result]
                    
                    # Get column info
                    columns = []
                    if rows:
                        for key, value in rows[0].items():
                            col_type = "text"
                            if isinstance(value, (int, float)):
                                col_type = "number"
                            columns.append({"name": str(key), "type": col_type})
                    else:
                        # Get columns from schema
                        for col in inspector.get_columns(table_name):
                            columns.append({"name": col["name"], "type": "text"})
                    
                    tables.append(TableData(
                        id=table_name,
                        name=table_name,
                        columns=columns,
                        rows=rows,
                    ))
                    total_rows += len(rows)
            
            extraction_time = int((time.time() - start_time) * 1000)
            
            return ExtractionResult(
                success=True,
                text=f"Загружено {len(tables)} таблиц с {total_rows} строками.",
                tables=tables,
                extraction_time_ms=extraction_time,
                metadata={
                    "db_type": config.get("db_type"),
                    "table_count": len(tables),
                    "total_rows": total_rows,
                }
            )
            
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка запроса к БД: {str(e)}")
    
    def _build_connection_string(self, config: dict[str, Any]) -> str:
        """Build SQLAlchemy connection string."""
        db_type = config.get("db_type", "")
        
        if db_type == "sqlite":
            return f"sqlite:///{config.get('path')}"
        
        driver_map = {
            "postgresql": "postgresql+psycopg2",
            "mysql": "mysql+pymysql",
        }
        driver = driver_map.get(db_type, db_type) if db_type else ""
        
        host = config.get("host", "localhost")
        port = config.get("port", 5432 if db_type == "postgresql" else 3306)
        database = config.get("database", "")
        username = config.get("username", "")
        password = config.get("password", "")
        
        if username and password:
            return f"{driver}://{username}:{password}@{host}:{port}/{database}"
        elif username:
            return f"{driver}://{username}@{host}:{port}/{database}"
        else:
            return f"{driver}://{host}:{port}/{database}"
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for database dialog."""
        return {
            "type": "object",
            "properties": {
                "db_type": {
                    "type": "string",
                    "enum": ["postgresql", "mysql", "sqlite"],
                    "title": "Тип СУБД",
                },
                "host": {"type": "string", "title": "Хост"},
                "port": {"type": "integer", "title": "Порт"},
                "database": {"type": "string", "title": "База данных"},
                "username": {"type": "string", "title": "Пользователь"},
                "password": {"type": "string", "format": "password", "title": "Пароль"},
                "tables": {
                    "type": "array",
                    "title": "Таблицы",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "where": {"type": "string"},
                            "limit": {"type": "integer", "default": 1000},
                        },
                    },
                },
            },
            "required": ["db_type", "tables"],
        }
