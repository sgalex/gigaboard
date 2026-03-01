"""Filter Engine — core of the cross-filter system.

Applies FilterExpression to ContentNode tables via Pandas.
See docs/CROSS_FILTER_SYSTEM.md §4

Usage:
    from app.services.filter_engine import FilterEngine
    filtered = FilterEngine.apply_filters(tables, filter_expr, mappings)
"""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

import pandas as pd

from app.schemas.cross_filter import (
    FilterCondition,
    FilterExpression,
    FilterGroup,
    FilterOperator,
)

logger = logging.getLogger(__name__)


class FilterEngine:
    """Stateless filter engine — all methods are static / classmethods."""

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def apply_filters(
        tables: list[dict[str, Any]],
        filters: FilterExpression | dict | None,
        mappings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply *filters* to *tables* using dimension→column *mappings*.

        - Originals are NOT modified (deep-copied where necessary).
        - Tables without a matching mapping are returned **unmodified**.
        - Empty / None filters → returns tables as-is (bypass).

        Parameters
        ----------
        tables : list[dict]
            ContentNode table dicts (name, columns, rows, …).
        filters : FilterExpression | dict | None
            Parsed Pydantic model or raw dict.  ``None`` ⇒ no filtering.
        mappings : list[dict]
            DimensionColumnMapping rows, each having at least:
            ``dimension_id``, ``node_id``, ``table_name``, ``column_name``.
            Plus the related Dimension ``name`` under key ``dim_name``.

        Returns
        -------
        list[dict]
            Copies of tables with filtered rows.
        """
        if not filters or not tables:
            return tables

        # Normalise filter to Pydantic model if needed
        expr = FilterEngine._normalise_expression(filters)
        if expr is None:
            return tables

        # Determine which dim names are referenced
        dim_names = FilterEngine.extract_dimensions(expr)
        if not dim_names:
            return tables

        # Build per-table column maps:  table_name → {dim_name → column_name}
        table_col_maps: dict[str, dict[str, str]] = {}
        for m in mappings:
            tname = m.get("table_name", "")
            dname = m.get("dim_name", "")
            cname = m.get("column_name", "")
            if not tname or not dname or not cname:
                continue
            table_col_maps.setdefault(tname, {})[dname] = cname

        result: list[dict[str, Any]] = []
        for table in tables:
            tname = table.get("name", "")
            col_map = table_col_maps.get(tname)

            # If no mapping for this table — return as-is
            if not col_map or not dim_names.intersection(col_map.keys()):
                result.append(table)
                continue

            try:
                df = FilterEngine._table_to_df(table)
                if df.empty:
                    result.append(table)
                    continue

                mask = FilterEngine.evaluate_expression(df, expr, col_map)
                filtered_df = df.loc[mask].reset_index(drop=True)
                result.append(FilterEngine._df_to_table(filtered_df, tname, table))
            except Exception:
                logger.exception("FilterEngine: error filtering table %s", tname)
                result.append(table)  # fallback — keep unfiltered

        return result

    @staticmethod
    def evaluate_expression(
        df: pd.DataFrame,
        expr: FilterExpression | dict,
        column_map: dict[str, str],
    ) -> pd.Series:
        """Recursively evaluate a FilterExpression into a boolean mask Series."""
        if isinstance(expr, dict):
            expr = FilterEngine._normalise_expression(expr)  # type: ignore[assignment]
        if expr is None:
            return pd.Series(True, index=df.index)

        if isinstance(expr, FilterCondition):
            return FilterEngine._eval_condition(df, expr, column_map)

        if isinstance(expr, FilterGroup):
            if not expr.conditions:
                return pd.Series(True, index=df.index)

            masks = [
                FilterEngine.evaluate_expression(df, sub, column_map)
                for sub in expr.conditions
            ]

            if expr.type == "and":
                combined = masks[0]
                for m in masks[1:]:
                    combined = combined & m
                return combined
            else:  # "or"
                combined = masks[0]
                for m in masks[1:]:
                    combined = combined | m
                return combined

        # Unknown type — pass through
        return pd.Series(True, index=df.index)

    @staticmethod
    def extract_dimensions(expr: FilterExpression | dict | None) -> set[str]:
        """Extract all dimension names referenced in the expression."""
        if expr is None:
            return set()

        if isinstance(expr, dict):
            expr = FilterEngine._normalise_expression(expr)
            if expr is None:
                return set()

        if isinstance(expr, FilterCondition):
            return {expr.dim}

        if isinstance(expr, FilterGroup):
            dims: set[str] = set()
            for sub in expr.conditions:
                dims |= FilterEngine.extract_dimensions(sub)
            return dims

        return set()

    @staticmethod
    def get_filter_stats(
        tables: list[dict[str, Any]],
        filtered_tables: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Compare original vs filtered tables and return stats per table."""
        stats = []
        orig_by_name = {t["name"]: t for t in tables}
        for ft in filtered_tables:
            name = ft.get("name", "")
            orig = orig_by_name.get(name)
            total = orig.get("row_count", len(orig.get("rows", []))) if orig else 0
            filtered = ft.get("row_count", len(ft.get("rows", [])))
            pct = round(filtered / total * 100, 1) if total > 0 else 100.0
            stats.append({
                "table_name": name,
                "total_rows": total,
                "filtered_rows": filtered,
                "percentage": pct,
            })
        return stats

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalise_expression(raw: Any) -> FilterExpression | None:
        """Parse raw dict/model into FilterCondition or FilterGroup."""
        if raw is None:
            return None
        if isinstance(raw, (FilterCondition, FilterGroup)):
            return raw
        if isinstance(raw, dict):
            expr_type = raw.get("type", "")
            if expr_type == "condition":
                return FilterCondition(**raw)
            elif expr_type in ("and", "or"):
                return FilterGroup(**raw)
        return None

    @staticmethod
    def _eval_condition(
        df: pd.DataFrame,
        cond: FilterCondition,
        column_map: dict[str, str],
    ) -> pd.Series:
        """Evaluate a single FilterCondition against a DataFrame."""
        col = column_map.get(cond.dim)
        if not col or col not in df.columns:
            return pd.Series(True, index=df.index)

        series = df[col]
        val = cond.value
        op = cond.op

        try:
            if op == FilterOperator.EQ:
                return series == val
            elif op == FilterOperator.NE:
                return series != val
            elif op == FilterOperator.GT:
                return series > val
            elif op == FilterOperator.LT:
                return series < val
            elif op == FilterOperator.GTE:
                return series >= val
            elif op == FilterOperator.LTE:
                return series <= val
            elif op == FilterOperator.IN:
                vals = val if isinstance(val, list) else [val]
                return series.isin(vals)
            elif op == FilterOperator.NOT_IN:
                vals = val if isinstance(val, list) else [val]
                return ~series.isin(vals)
            elif op == FilterOperator.BETWEEN:
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    return (series >= val[0]) & (series <= val[1])
                return pd.Series(True, index=df.index)
            elif op == FilterOperator.CONTAINS:
                return series.astype(str).str.contains(str(val), case=False, na=False)
            elif op == FilterOperator.STARTS_WITH:
                return series.astype(str).str.startswith(str(val), na=False)
            else:
                return pd.Series(True, index=df.index)
        except Exception:
            logger.exception(
                "FilterEngine: error evaluating %s %s %s on column %s",
                cond.dim, cond.op, cond.value, col,
            )
            return pd.Series(True, index=df.index)

    @staticmethod
    def _table_to_df(table: dict[str, Any]) -> pd.DataFrame:
        """Convert ContentNode table dict → pandas DataFrame."""
        columns = table.get("columns", [])
        rows = table.get("rows", [])
        col_names = [c["name"] for c in columns]
        if not rows:
            return pd.DataFrame(columns=col_names)
        return pd.DataFrame(rows, columns=col_names)

    @staticmethod
    def _df_to_table(
        df: pd.DataFrame,
        table_name: str,
        original_table: dict[str, Any],
    ) -> dict[str, Any]:
        """Convert DataFrame back to ContentNode table dict, preserving column metadata."""
        # Preserve original column defs
        orig_columns = original_table.get("columns", [])
        col_names_set = set(df.columns)
        columns = [c for c in orig_columns if c["name"] in col_names_set]

        # Fill NaN before serializing
        df_copy = df.copy()
        for col in df_copy.columns:
            if isinstance(df_copy[col].dtype, pd.CategoricalDtype):
                df_copy[col] = df_copy[col].astype(str)
        rows = df_copy.fillna("").to_dict(orient="records")
        rows = [{str(k): v for k, v in r.items()} for r in rows]

        result = {
            "name": table_name,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(columns),
            "preview_row_count": len(rows),
            "metadata": original_table.get("metadata", {}),
        }
        if "id" in original_table:
            result["id"] = original_table["id"]
        return result
