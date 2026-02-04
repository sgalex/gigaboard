"""
Database connection testing and introspection endpoints
"""
from typing import List, Dict, Any, Optional
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


# Schemas
class DatabaseConnectionRequest(BaseModel):
    """Request model for database connection testing"""
    database_type: str = Field(..., description="Type of database: postgresql, mysql, clickhouse, mongodb, sqlite")
    
    # PostgreSQL, MySQL, ClickHouse
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    
    # MongoDB
    uri: Optional[str] = None
    
    # SQLite
    path: Optional[str] = None


class DatabaseConnectionResponse(BaseModel):
    """Response model for successful database connection"""
    success: bool
    database_type: str
    tables: List[str]
    table_count: int


# Helper functions
def get_postgres_tables(host: str, port: int, database: str, user: str, password: str) -> List[str]:
    """Get list of tables from PostgreSQL database"""
    if not POSTGRES_AVAILABLE:
        raise HTTPException(status_code=500, detail="PostgreSQL driver (psycopg2) not installed")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5
        )
        cursor = conn.cursor()
        
        # Query for all tables in public schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return tables
    except Exception as e:
        logger.error(f"PostgreSQL connection error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to connect to PostgreSQL: {str(e)}")


def get_mysql_tables(host: str, port: int, database: str, user: str, password: str) -> List[str]:
    """Get list of tables from MySQL database"""
    if not MYSQL_AVAILABLE:
        raise HTTPException(status_code=500, detail="MySQL driver (pymysql) not installed")
    
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5
        )
        cursor = conn.cursor()
        
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return tables
    except Exception as e:
        logger.error(f"MySQL connection error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to connect to MySQL: {str(e)}")


def get_clickhouse_tables(host: str, port: int, database: str, user: str, password: str) -> List[str]:
    """Get list of tables from ClickHouse database"""
    if not CLICKHOUSE_AVAILABLE:
        raise HTTPException(status_code=500, detail="ClickHouse driver (clickhouse-driver) not installed")
    
    try:
        client = ClickHouseClient(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5
        )
        
        # Query for tables in the specified database
        result = client.execute(f"SHOW TABLES FROM {database}")
        tables = [row[0] for row in result]
        
        client.disconnect()
        
        return tables
    except Exception as e:
        logger.error(f"ClickHouse connection error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to connect to ClickHouse: {str(e)}")


def get_mongodb_collections(uri: str, database: str) -> List[str]:
    """Get list of collections from MongoDB database"""
    if not MONGODB_AVAILABLE:
        raise HTTPException(status_code=500, detail="MongoDB driver (pymongo) not installed")
    
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        
        # Get database and list collections
        db = client[database]
        collections = db.list_collection_names()
        
        client.close()
        
        return collections
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to connect to MongoDB: {str(e)}")


def get_sqlite_tables(path: str) -> List[str]:
    """Get list of tables from SQLite database"""
    try:
        conn = sqlite3.connect(path, timeout=5)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name 
            FROM sqlite_master 
            WHERE type='table' 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return tables
    except Exception as e:
        logger.error(f"SQLite connection error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to connect to SQLite: {str(e)}")


# Routes
@router.post("/test-connection", response_model=DatabaseConnectionResponse)
async def test_database_connection(request: DatabaseConnectionRequest):
    """
    Test database connection and return list of available tables/collections.
    
    Supports: PostgreSQL, MySQL, ClickHouse, MongoDB, SQLite
    """
    db_type = request.database_type.lower()
    tables = []
    
    try:
        if db_type == "postgresql":
            if not all([request.host, request.port, request.database, request.user]):
                raise HTTPException(status_code=400, detail="Missing required fields for PostgreSQL connection")
            tables = get_postgres_tables(
                host=request.host,  # type: ignore
                port=request.port,  # type: ignore
                database=request.database,  # type: ignore
                user=request.user,  # type: ignore
                password=request.password or ""
            )
        
        elif db_type == "mysql":
            if not all([request.host, request.port, request.database, request.user]):
                raise HTTPException(status_code=400, detail="Missing required fields for MySQL connection")
            tables = get_mysql_tables(
                host=request.host,  # type: ignore
                port=request.port,  # type: ignore
                database=request.database,  # type: ignore
                user=request.user,  # type: ignore
                password=request.password or ""
            )
        
        elif db_type == "clickhouse":
            if not all([request.host, request.port, request.database, request.user]):
                raise HTTPException(status_code=400, detail="Missing required fields for ClickHouse connection")
            tables = get_clickhouse_tables(
                host=request.host,  # type: ignore
                port=request.port,  # type: ignore
                database=request.database,  # type: ignore
                user=request.user,  # type: ignore
                password=request.password or ""
            )
        
        elif db_type == "mongodb":
            if not all([request.uri, request.database]):
                raise HTTPException(status_code=400, detail="Missing required fields for MongoDB connection")
            tables = get_mongodb_collections(
                uri=request.uri,  # type: ignore
                database=request.database  # type: ignore
            )
        
        elif db_type == "sqlite":
            if not request.path:
                raise HTTPException(status_code=400, detail="Missing path for SQLite database")
            tables = get_sqlite_tables(path=request.path)
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported database type: {db_type}. Supported types: postgresql, mysql, clickhouse, mongodb, sqlite"
            )
        
        return DatabaseConnectionResponse(
            success=True,
            database_type=db_type,
            tables=tables,
            table_count=len(tables)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error testing {db_type} connection: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
