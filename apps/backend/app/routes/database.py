"""
Database connection testing, introspection and preview endpoints.

Endpoints:
  POST /test-connection  — test DB connection, return schemas/tables with row counts
  POST /preview          — preview table data (first N rows)
  POST /table-columns    — get column info for a table
"""
from typing import List, Dict, Any, Optional
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import logging

# Database drivers
try:
    import psycopg2
    from psycopg2 import pool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

try:
    from clickhouse_driver import Client as ClickHouseClient
    CLICKHOUSE_AVAILABLE = True
except ImportError:
    CLICKHOUSE_AVAILABLE = False

try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

import sqlite3

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/database", tags=["database"])


# ===================== Schemas =====================

class DatabaseConnectionRequest(BaseModel):
    """Request model for database connection testing"""
    database_type: str = Field(..., description="Type of database: postgresql, mysql, clickhouse, mongodb, sqlite")
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    uri: Optional[str] = None       # MongoDB
    path: Optional[str] = None      # SQLite


class TableInfo(BaseModel):
    name: str
    schema_name: str = "public"
    row_count: int = 0
    column_count: int = 0


class SchemaInfo(BaseModel):
    name: str
    tables: List[TableInfo]
    table_count: int = 0


class DatabaseConnectionResponse(BaseModel):
    success: bool
    database_type: str
    schemas: List[SchemaInfo]
    table_count: int
    server_version: str = ""


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool = True


class TablePreviewRequest(BaseModel):
    database_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    path: Optional[str] = None
    table_name: str
    schema_name: str = "public"
    where_clause: Optional[str] = None
    limit: int = 50


class TablePreviewResponse(BaseModel):
    success: bool
    table_name: str
    columns: List[ColumnInfo]
    rows: List[Dict[str, Any]]
    total_rows: int
    preview_rows: int


class TableColumnsRequest(BaseModel):
    database_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    path: Optional[str] = None
    table_name: str
    schema_name: str = "public"


# ===================== Connection helpers =====================

def _connect_postgres(host: str, port: int, database: str, user: str, password: str):
    if not POSTGRES_AVAILABLE:
        raise HTTPException(status_code=500, detail="PostgreSQL driver (psycopg2) not installed")
    try:
        return psycopg2.connect(host=host, port=port, database=database,
                                user=user, password=password, connect_timeout=5)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка подключения к PostgreSQL: {e}")


def _connect_mysql(host: str, port: int, database: str, user: str, password: str):
    if not MYSQL_AVAILABLE:
        raise HTTPException(status_code=500, detail="MySQL driver (pymysql) not installed")
    try:
        return pymysql.connect(host=host, port=port, database=database,
                               user=user, password=password, connect_timeout=5)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка подключения к MySQL: {e}")


def _connect_sqlite(path: str):
    try:
        return sqlite3.connect(path, timeout=5)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка подключения к SQLite: {e}")


# ===================== Table listing (returns SchemaInfo[]) =====================

def get_postgres_tables(host: str, port: int, database: str, user: str, password: str) -> tuple[List[SchemaInfo], str]:
    conn = _connect_postgres(host, port, database, user, password)
    cursor = conn.cursor()
    cursor.execute("SELECT version()")
    server_version = cursor.fetchone()[0].split(",")[0]
    # Single query: join pg_class for reltuples (fast row estimate) + column count
    cursor.execute("""
        SELECT n.nspname AS table_schema,
               c.relname AS table_name,
               GREATEST(c.reltuples, 0)::bigint AS row_count,
               (SELECT COUNT(*) FROM information_schema.columns col
                WHERE col.table_schema = n.nspname AND col.table_name = c.relname) AS col_count
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY n.nspname, c.relname
    """)
    grouped: dict[str, list[TableInfo]] = defaultdict(list)
    for schema, table, row_count, col_count in cursor.fetchall():
        grouped[schema].append(TableInfo(name=table, schema_name=schema, row_count=row_count, column_count=col_count))
    cursor.close()
    conn.close()
    schemas = [SchemaInfo(name=s, tables=tbls, table_count=len(tbls)) for s, tbls in grouped.items()]
    return schemas, server_version


def get_mysql_tables(host: str, port: int, database: str, user: str, password: str) -> tuple[List[SchemaInfo], str]:
    conn = _connect_mysql(host, port, database, user, password)
    cursor = conn.cursor()
    cursor.execute("SELECT VERSION()")
    server_version = f"MySQL {cursor.fetchone()[0]}"
    cursor.execute("""
        SELECT TABLE_NAME, TABLE_ROWS,
               (SELECT COUNT(*) FROM information_schema.COLUMNS c
                WHERE c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME)
        FROM information_schema.TABLES t
        WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """, (database,))
    tables = [TableInfo(name=r[0], schema_name=database, row_count=r[1] or 0, column_count=r[2] or 0)
              for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return [SchemaInfo(name=database, tables=tables, table_count=len(tables))], server_version


def get_clickhouse_tables(host: str, port: int, database: str, user: str, password: str) -> tuple[List[SchemaInfo], str]:
    if not CLICKHOUSE_AVAILABLE:
        raise HTTPException(status_code=500, detail="ClickHouse driver not installed")
    try:
        client = ClickHouseClient(host=host, port=port, database=database,
                                  user=user, password=password, connect_timeout=5)
        result = client.execute(f"SHOW TABLES FROM {database}")
        tables = [TableInfo(name=r[0], schema_name=database) for r in result]
        client.disconnect()
        return [SchemaInfo(name=database, tables=tables, table_count=len(tables))], "ClickHouse"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка подключения к ClickHouse: {e}")


def get_mongodb_collections(uri: str, database: str) -> tuple[List[SchemaInfo], str]:
    if not MONGODB_AVAILABLE:
        raise HTTPException(status_code=500, detail="MongoDB driver not installed")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[database]
        tables = [TableInfo(name=c, schema_name=database) for c in sorted(db.list_collection_names())]
        client.close()
        return [SchemaInfo(name=database, tables=tables, table_count=len(tables))], "MongoDB"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка подключения к MongoDB: {e}")


def get_sqlite_tables(path: str) -> tuple[List[SchemaInfo], str]:
    conn = _connect_sqlite(path)
    cursor = conn.cursor()
    cursor.execute("SELECT sqlite_version()")
    server_version = f"SQLite {cursor.fetchone()[0]}"
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name
    """)
    table_names = [r[0] for r in cursor.fetchall()]
    tables = []
    for name in table_names:
        cursor.execute(f'SELECT COUNT(*) FROM "{name}"')
        row_count = cursor.fetchone()[0]
        cursor.execute(f'PRAGMA table_info("{name}")')
        col_count = len(cursor.fetchall())
        tables.append(TableInfo(name=name, schema_name="main", row_count=row_count, column_count=col_count))
    cursor.close()
    conn.close()
    return [SchemaInfo(name="main", tables=tables, table_count=len(tables))], server_version


# ===================== Column helpers =====================

def _get_postgres_columns(conn, table_name: str, schema_name: str = "public") -> List[ColumnInfo]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position
    """, (schema_name, table_name))
    cols = [ColumnInfo(name=r[0], type=r[1], nullable=(r[2] == 'YES')) for r in cursor.fetchall()]
    cursor.close()
    return cols


def _get_mysql_columns(conn, table_name: str, database: str) -> List[ColumnInfo]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION
    """, (database, table_name))
    cols = [ColumnInfo(name=r[0], type=r[1], nullable=(r[2] == 'YES')) for r in cursor.fetchall()]
    cursor.close()
    return cols


def _get_sqlite_columns(conn, table_name: str) -> List[ColumnInfo]:
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    cols = [ColumnInfo(name=r[1], type=r[2] or 'text', nullable=(r[3] == 0)) for r in cursor.fetchall()]
    cursor.close()
    return cols


# ===================== Preview helper =====================

def _preview_table(conn, table_name: str, columns: List[ColumnInfo],
                   where_clause: str | None, limit: int,
                   db_type: str, schema_name: str | None = None) -> TablePreviewResponse:
    cursor = conn.cursor()
    if db_type == 'postgresql':
        q = '"'
        schema = schema_name or 'public'
        qualified = f'{q}{schema}{q}.{q}{table_name}{q}'
    elif db_type == 'mysql':
        qualified = f'`{table_name}`'
    else:
        qualified = f'"{table_name}"'

    query = f'SELECT * FROM {qualified}'
    if where_clause and where_clause.strip():
        query += f' WHERE {where_clause}'
    query += f' LIMIT {limit}'
    try:
        cursor.execute(query)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка SQL: {e}")

    col_names = [d[0] for d in cursor.description] if cursor.description else [c.name for c in columns]
    rows = []
    for row in cursor.fetchall():
        d = {}
        for i, val in enumerate(row):
            if val is None:
                d[col_names[i]] = None
            elif isinstance(val, (int, float, str, bool)):
                d[col_names[i]] = val
            else:
                d[col_names[i]] = str(val)
        rows.append(d)

    count_q = f'SELECT COUNT(*) FROM {qualified}'
    if where_clause and where_clause.strip():
        count_q += f' WHERE {where_clause}'
    try:
        cursor.execute(count_q)
        total_rows = cursor.fetchone()[0]
    except Exception:
        total_rows = len(rows)
    cursor.close()

    return TablePreviewResponse(
        success=True, table_name=table_name, columns=columns,
        rows=rows, total_rows=total_rows, preview_rows=len(rows))


# ===================== Routes =====================

@router.post("/test-connection", response_model=DatabaseConnectionResponse)
async def test_database_connection(request: DatabaseConnectionRequest):
    """Test database connection and return schemas with tables."""
    db_type = request.database_type.lower()
    schemas: List[SchemaInfo] = []
    server_version = ""

    try:
        if db_type == "postgresql":
            if not all([request.host, request.port, request.database, request.user]):
                raise HTTPException(status_code=400, detail="Не заполнены обязательные поля для PostgreSQL")
            schemas, server_version = get_postgres_tables(
                request.host, request.port, request.database, request.user, request.password or "")  # type: ignore

        elif db_type == "mysql":
            if not all([request.host, request.port, request.database, request.user]):
                raise HTTPException(status_code=400, detail="Не заполнены обязательные поля для MySQL")
            schemas, server_version = get_mysql_tables(
                request.host, request.port, request.database, request.user, request.password or "")  # type: ignore

        elif db_type == "clickhouse":
            if not all([request.host, request.port, request.database, request.user]):
                raise HTTPException(status_code=400, detail="Не заполнены обязательные поля для ClickHouse")
            schemas, server_version = get_clickhouse_tables(
                request.host, request.port, request.database, request.user, request.password or "")  # type: ignore

        elif db_type == "mongodb":
            if not all([request.uri, request.database]):
                raise HTTPException(status_code=400, detail="Не заполнены обязательные поля для MongoDB")
            schemas, server_version = get_mongodb_collections(request.uri, request.database)  # type: ignore

        elif db_type == "sqlite":
            if not request.path:
                raise HTTPException(status_code=400, detail="Не указан путь к файлу SQLite")
            schemas, server_version = get_sqlite_tables(request.path)

        else:
            raise HTTPException(status_code=400, detail=f"Неподдерживаемый тип БД: {db_type}")

        total = sum(s.table_count for s in schemas)
        return DatabaseConnectionResponse(
            success=True, database_type=db_type, schemas=schemas,
            table_count=total, server_version=server_version)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error testing {db_type} connection: {e}")
        raise HTTPException(status_code=500, detail=f"Неожиданная ошибка: {e}")


@router.post("/preview", response_model=TablePreviewResponse)
async def preview_table(request: TablePreviewRequest):
    """Preview table data — first N rows with column info."""
    db_type = request.database_type.lower()
    try:
        if db_type == "postgresql":
            conn = _connect_postgres(request.host or "localhost", request.port or 5432,
                                     request.database or "", request.user or "", request.password or "")
            cols = _get_postgres_columns(conn, request.table_name, request.schema_name)
            result = _preview_table(conn, request.table_name, cols,
                                    request.where_clause, request.limit, db_type, request.schema_name)
            conn.close()
            return result

        elif db_type == "mysql":
            conn = _connect_mysql(request.host or "localhost", request.port or 3306,
                                  request.database or "", request.user or "", request.password or "")
            cols = _get_mysql_columns(conn, request.table_name, request.database or "")
            result = _preview_table(conn, request.table_name, cols,
                                    request.where_clause, request.limit, db_type)
            conn.close()
            return result

        elif db_type == "sqlite":
            conn = _connect_sqlite(request.path or "")
            cols = _get_sqlite_columns(conn, request.table_name)
            result = _preview_table(conn, request.table_name, cols,
                                    request.where_clause, request.limit, db_type)
            conn.close()
            return result

        else:
            raise HTTPException(status_code=400, detail=f"Preview не поддерживается для {db_type}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing table {request.table_name}: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка предпросмотра: {e}")


@router.post("/table-columns")
async def get_table_columns(request: TableColumnsRequest):
    """Get column info for a specific table."""
    db_type = request.database_type.lower()
    try:
        if db_type == "postgresql":
            conn = _connect_postgres(request.host or "localhost", request.port or 5432,
                                     request.database or "", request.user or "", request.password or "")
            cols = _get_postgres_columns(conn, request.table_name, request.schema_name)
            conn.close()
        elif db_type == "mysql":
            conn = _connect_mysql(request.host or "localhost", request.port or 3306,
                                  request.database or "", request.user or "", request.password or "")
            cols = _get_mysql_columns(conn, request.table_name, request.database or "")
            conn.close()
        elif db_type == "sqlite":
            conn = _connect_sqlite(request.path or "")
            cols = _get_sqlite_columns(conn, request.table_name)
            conn.close()
        else:
            raise HTTPException(status_code=400, detail=f"Не поддерживается для {db_type}")
        return {"success": True, "table_name": request.table_name, "columns": [c.model_dump() for c in cols]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка: {e}")
