"""Database extractor — extracts selected tables from a connected DB.

Works with the config format produced by DatabaseSourceDialog:
  {
    db_type: "postgresql" | "mysql" | "sqlite",
    host, port, database, username, password,   # for pg/mysql
    path,                                        # for sqlite
    tables: [{name, schema, limit?, where?, columns?: [{name,selected,alias}]}],
    row_limit: int   # fallback per-table limit
  }

Uses sync drivers (psycopg2, pymysql, sqlite3) via asyncio.to_thread.
"""
import asyncio
import logging
import sqlite3
from typing import Any

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


def _serialise_value(val: Any) -> Any:
    """Make a DB cell JSON-safe."""
    if val is None or isinstance(val, (int, float, str, bool)):
        return val
    return str(val)


class DatabaseExtractor(BaseExtractor):
    """Extractor for database sources (PostgreSQL, MySQL, SQLite)."""

    SUPPORTED_DATABASES = {"postgresql", "mysql", "sqlite"}
    MAX_ROWS = 10_000

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract(
        self,
        config: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        """Extract data from one or more tables specified in *config*."""
        return await asyncio.to_thread(self._extract_sync, config, params or {})

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        errors: list[str] = []
        db_type = config.get("db_type", config.get("database_type", ""))
        if db_type not in self.SUPPORTED_DATABASES:
            errors.append(f"Unsupported db_type: {db_type}")
        if db_type == "sqlite":
            if not config.get("path"):
                errors.append("path is required for SQLite")
        else:
            if not config.get("host"):
                errors.append("host is required")
            if not config.get("database"):
                errors.append("database is required")
        if not config.get("tables"):
            errors.append("At least one table must be selected")
        return len(errors) == 0, errors

    # ------------------------------------------------------------------
    # Sync extraction (runs in thread)
    # ------------------------------------------------------------------

    def _extract_sync(self, config: dict[str, Any], params: dict[str, Any]) -> ExtractionResult:
        result = ExtractionResult()
        db_type = config.get("db_type", config.get("database_type", "postgresql"))
        tables_cfg: list[dict] = config.get("tables", [])
        default_limit = config.get("row_limit", self.MAX_ROWS)

        if not tables_cfg:
            result.errors.append("No tables specified in config")
            return result

        try:
            conn = self._connect(config, db_type)
        except Exception as e:
            result.errors.append(f"Connection failed: {e}")
            return result

        try:
            for tbl in tables_cfg:
                self._extract_table(conn, db_type, tbl, default_limit, result)
        finally:
            conn.close()

        total_rows = sum(t.get("row_count", 0) for t in result.tables)
        result.text = (
            f"Extracted {len(result.tables)} table(s), {total_rows} rows total "
            f"from {db_type} database"
        )
        result.metadata.update({
            "database_type": db_type,
            "table_count": len(result.tables),
            "total_rows": total_rows,
        })
        return result

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _connect(config: dict[str, Any], db_type: str):
        if db_type == "postgresql":
            import psycopg2
            return psycopg2.connect(
                host=config.get("host", "localhost"),
                port=int(config.get("port", 5432)),
                dbname=config.get("database"),
                user=config.get("username"),
                password=config.get("password"),
                connect_timeout=10,
            )
        elif db_type == "mysql":
            import pymysql
            return pymysql.connect(
                host=config.get("host", "localhost"),
                port=int(config.get("port", 3306)),
                database=config.get("database"),
                user=config.get("username"),
                password=config.get("password"),
                connect_timeout=10,
            )
        elif db_type == "sqlite":
            return sqlite3.connect(config["path"], timeout=10)
        else:
            raise ValueError(f"Unsupported db_type: {db_type}")

    # ------------------------------------------------------------------
    # Per-table extraction
    # ------------------------------------------------------------------

    def _extract_table(
        self,
        conn,
        db_type: str,
        tbl: dict,
        default_limit: int,
        result: ExtractionResult,
    ):
        table_name = tbl["name"]
        schema_name = tbl.get("schema", "public")
        limit = min(tbl.get("limit", default_limit), self.MAX_ROWS)
        where = tbl.get("where", "").strip()

        # Build column list (respecting selected/alias)
        columns_cfg: list[dict] | None = tbl.get("columns")
        selected_cols: list[str] | None = None
        alias_map: dict[str, str] = {}
        if columns_cfg:
            selected = [c for c in columns_cfg if c.get("selected", True)]
            if selected:
                parts: list[str] = []
                for c in selected:
                    col_name = c["name"]
                    alias = c.get("alias", "").strip()
                    if alias and alias != col_name:
                        alias_map[col_name] = alias
                    parts.append(col_name)
                selected_cols = parts

        # Build qualified table name
        if db_type == "postgresql":
            q = '"'
            qualified = f'{q}{schema_name}{q}.{q}{table_name}{q}'
            col_wrap = lambda c: f'{q}{c}{q}'  # noqa: E731
        elif db_type == "mysql":
            qualified = f'`{table_name}`'
            col_wrap = lambda c: f'`{c}`'  # noqa: E731
        else:
            qualified = f'"{table_name}"'
            col_wrap = lambda c: f'"{c}"'  # noqa: E731

        # Column selector
        if selected_cols:
            col_expr = ", ".join(col_wrap(c) for c in selected_cols)
        else:
            col_expr = "*"

        sql = f"SELECT {col_expr} FROM {qualified}"
        if where:
            sql += f" WHERE {where}"
        sql += f" LIMIT {limit}"

        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            raw_rows = cursor.fetchall()
            col_names = (
                [d[0] for d in cursor.description]
                if cursor.description
                else (selected_cols or [])
            )
        except Exception as e:
            logger.warning(f"Failed to extract table {qualified}: {e}")
            result.errors.append(f"Table {schema_name}.{table_name}: {e}")
            cursor.close()
            return
        finally:
            cursor.close()

        # Apply aliases
        display_names = [alias_map.get(c, c) for c in col_names]

        # Convert to dicts
        dict_rows = []
        for row in raw_rows:
            d = {}
            for i, val in enumerate(row):
                d[display_names[i]] = _serialise_value(val)
            dict_rows.append(d)

        table = self._create_table(
            name=table_name,
            columns=display_names,
            rows=dict_rows,
            metadata={
                "database": db_type,
                "schema": schema_name,
                "row_count": len(dict_rows),
                "where": where or None,
            },
        )
        result.tables.append(table)

