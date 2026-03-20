"""Automatic JSON normalization to relational-like tables."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.sources.base import TableData


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _infer_type(values: list[Any]) -> str:
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "text"
    if all(isinstance(v, bool) for v in non_null):
        return "boolean"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "number"
    return "text"


def _slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"\W+", "_", value, flags=re.UNICODE).strip("_").lower()
    return slug or fallback


def _relative_column_path(base_path: str, absolute_path: str) -> str:
    """Convert absolute JSON path to path relative to table row object."""
    if not absolute_path.startswith("$."):
        return "$"

    normalized_base = base_path
    if normalized_base.endswith("[*]"):
        normalized_base = normalized_base[:-3]
    normalized_base = normalized_base.lstrip("$.")

    abs_tail = absolute_path[2:]
    if normalized_base and abs_tail.startswith(f"{normalized_base}."):
        return f"$.{abs_tail[len(normalized_base) + 1:]}"
    return absolute_path


@dataclass
class _TableDraft:
    table_id: str
    name: str
    base_path: str
    parent_table: str | None = None
    pk_column: str = "row_id"
    fk_column: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    column_paths: dict[str, str] = field(default_factory=dict)
    column_samples: dict[str, list[Any]] = field(default_factory=dict)

    def add_value(self, row: dict[str, Any], column: str, value: Any, source_path: str) -> None:
        row[column] = value
        self.column_paths.setdefault(column, source_path)
        self.column_samples.setdefault(column, []).append(value)


@dataclass
class AutoNormalizationResult:
    tables: list[TableData]
    mapping_spec: dict[str, Any]
    generation_meta: dict[str, Any]


def auto_normalize_json(data: Any, max_rows: int | None = None) -> AutoNormalizationResult:
    """Create normalized tables and mapping spec from JSON."""
    drafts: dict[str, _TableDraft] = {}
    warnings: list[str] = []

    def ensure_table(base_path: str, parent_table: str | None) -> _TableDraft:
        existing = drafts.get(base_path)
        if existing:
            return existing
        base_name = base_path.split(".")[-1].replace("[*]", "") if base_path != "$" else "root"
        table_id = _slugify(base_name, "table")
        if table_id in {t.table_id for t in drafts.values()}:
            table_id = f"{table_id}_{len(drafts) + 1}"
        pk_column = f"{table_id}_id"
        fk_column = f"{parent_table}_id" if parent_table else None
        draft = _TableDraft(
            table_id=table_id,
            name=base_name,
            base_path=base_path,
            parent_table=parent_table,
            pk_column=pk_column,
            fk_column=fk_column,
        )
        drafts[base_path] = draft
        return draft

    def flatten_nested_object(
        nested: dict[str, Any],
        prefix: str,
        source_prefix: str,
        draft: _TableDraft,
        row: dict[str, Any],
        child_arrays: list[tuple[str, list[Any]]],
    ) -> None:
        for key, value in nested.items():
            column = f"{prefix}_{key}"
            source_path = f"{source_prefix}.{key}"
            if _is_scalar(value):
                draft.add_value(row, column, value, source_path)
            elif isinstance(value, dict):
                flatten_nested_object(value, column, source_path, draft, row, child_arrays)
            elif isinstance(value, list):
                if value and all(isinstance(item, dict) for item in value):
                    child_arrays.append((f"{prefix}.{key}", value))
                else:
                    # Keep scalar/mixed nested arrays as JSON in parent row.
                    draft.add_value(row, f"{column}_json", json.dumps(value, ensure_ascii=False), source_path)

    def process_object(
        obj: dict[str, Any],
        base_path: str,
        parent_row_id: str | None,
        parent_table: str | None,
    ) -> None:
        draft = ensure_table(base_path, parent_table)
        if max_rows and len(draft.rows) >= max_rows:
            return

        row: dict[str, Any] = {draft.pk_column: str(uuid4())}
        if draft.fk_column and parent_row_id is not None:
            row[draft.fk_column] = parent_row_id

        child_arrays: list[tuple[str, list[Any]]] = []
        for key, value in obj.items():
            if _is_scalar(value):
                draft.add_value(row, key, value, f"$.{key}" if base_path == "$" else f"{base_path}.{key}")
            elif isinstance(value, dict):
                flatten_nested_object(
                    value,
                    prefix=key,
                    source_prefix=f"{base_path}.{key}" if base_path != "$" else f"$.{key}",
                    draft=draft,
                    row=row,
                    child_arrays=child_arrays,
                )
            elif isinstance(value, list):
                if value and all(isinstance(item, dict) for item in value):
                    child_arrays.append((key, value))
                else:
                    draft.add_value(
                        row,
                        f"{key}_json",
                        json.dumps(value, ensure_ascii=False),
                        f"{base_path}.{key}" if base_path != "$" else f"$.{key}",
                    )

        draft.rows.append(row)

        for child_key, child_items in child_arrays:
            child_path_key = child_key.replace(".", ".")
            child_base = f"{base_path}.{child_path_key}[*]" if base_path != "$" else f"$.{child_path_key}[*]"
            for child in child_items:
                process_object(
                    child,
                    base_path=child_base,
                    parent_row_id=row[draft.pk_column],
                    parent_table=draft.table_id,
                )

    if isinstance(data, list):
        if data and all(isinstance(item, dict) for item in data):
            for item in data:
                process_object(item, "$[*]", None, None)
        else:
            ensure_table("$", None).rows.append(
                {
                    "root_id": str(uuid4()),
                    "value_json": json.dumps(data, ensure_ascii=False),
                }
            )
            warnings.append("Root JSON array is not array of objects; stored as single JSON column.")
    elif isinstance(data, dict):
        process_object(data, "$", None, None)
    else:
        ensure_table("$", None).rows.append(
            {
                "root_id": str(uuid4()),
                "value": data,
            }
        )
        warnings.append("Root JSON is scalar; stored in single-row table.")

    tables: list[TableData] = []
    mapping_tables: list[dict[str, Any]] = []

    for base_path, draft in sorted(drafts.items(), key=lambda kv: kv[0]):
        if not draft.rows:
            continue

        # Drop purely technical root rows with no payload.
        non_technical_columns = {
            k
            for row in draft.rows
            for k in row.keys()
            if k not in {draft.pk_column, draft.fk_column}
        }
        if base_path == "$" and not non_technical_columns:
            continue

        ordered_columns: list[str] = []
        seen = set()
        for row in draft.rows:
            for col in row.keys():
                if col not in seen:
                    seen.add(col)
                    ordered_columns.append(col)

        columns = []
        for col in ordered_columns:
            samples = draft.column_samples.get(col, [row.get(col) for row in draft.rows])
            columns.append({"name": col, "type": _infer_type(samples)})

        rows = []
        for row in draft.rows[: max_rows or len(draft.rows)]:
            normalized = {col["name"]: row.get(col["name"]) for col in columns}
            rows.append(normalized)

        tables.append(
            TableData(
                id=draft.table_id,
                name=draft.name,
                columns=columns,
                rows=rows,
            )
        )

        mapping_table: dict[str, Any] = {
            "id": draft.table_id,
            "name": draft.name,
            "base_path": draft.base_path,
            "pk": {"column": draft.pk_column, "strategy": "surrogate_uuid"},
            "columns": [
                {
                    "name": col["name"],
                    "type": col["type"],
                    "path": _relative_column_path(
                        draft.base_path,
                        draft.column_paths.get(col["name"], f"$.{col['name']}"),
                    ),
                    "nullable": True,
                }
                for col in columns
                if col["name"] not in {draft.pk_column, draft.fk_column}
            ],
        }
        if draft.fk_column and draft.parent_table:
            mapping_table["fk"] = [
                {
                    "column": draft.fk_column,
                    "ref_table": draft.parent_table,
                    "ref_column": f"{draft.parent_table}_id",
                }
            ]
        mapping_tables.append(mapping_table)

    mapping_spec = {
        "version": "1.0",
        "tables": mapping_tables,
    }
    generation_meta = {
        "generated_by": "heuristic",
        "confidence": 0.8 if mapping_tables else 0.2,
        "warnings": warnings,
    }

    return AutoNormalizationResult(
        tables=tables,
        mapping_spec=mapping_spec,
        generation_meta=generation_meta,
    )


def extract_tables_from_mapping(
    data: Any,
    mapping_spec: dict[str, Any],
    max_rows: int | None = None,
) -> list[TableData]:
    """Extract table rows based on saved mapping spec."""
    tables_cfg = mapping_spec.get("tables") if isinstance(mapping_spec, dict) else None
    if not isinstance(tables_cfg, list):
        return []

    path_index_rows: dict[tuple[str, int], str] = {}
    table_rows: dict[str, list[dict[str, Any]]] = {}

    # Parent tables first.
    def _depth(path: str) -> int:
        return path.count(".") + path.count("[*]")

    sorted_tables = sorted((t for t in tables_cfg if isinstance(t, dict)), key=lambda t: _depth(str(t.get("base_path", "$"))))

    for table_cfg in sorted_tables:
        table_id = str(table_cfg.get("id", "table"))
        base_path = str(table_cfg.get("base_path", "$"))
        pk_column = str(table_cfg.get("pk", {}).get("column", f"{table_id}_id"))
        fk_cfg = table_cfg.get("fk") or []
        fk_entry = fk_cfg[0] if isinstance(fk_cfg, list) and fk_cfg else None
        fk_column = str(fk_entry.get("column")) if isinstance(fk_entry, dict) and fk_entry.get("column") else None
        ref_table = str(fk_entry.get("ref_table")) if isinstance(fk_entry, dict) and fk_entry.get("ref_table") else None
        column_cfgs = [c for c in (table_cfg.get("columns") or []) if isinstance(c, dict)]

        matches = _iter_matches(data, base_path)
        rows: list[dict[str, Any]] = []
        for match in matches:
            if max_rows and len(rows) >= max_rows:
                break
            value = match["value"]
            if not isinstance(value, dict):
                continue

            row: dict[str, Any] = {pk_column: str(uuid4())}
            if fk_column and ref_table and match["parent_obj"] is not None:
                ref_id = path_index_rows.get((ref_table, id(match["parent_obj"])))
                if ref_id:
                    row[fk_column] = ref_id

            for column in column_cfgs:
                col_name = str(column.get("name", "col"))
                col_path = str(column.get("path", "$"))
                row[col_name] = _extract_relative_value(value, col_path)

            rows.append(row)
            path_index_rows[(table_id, id(value))] = row[pk_column]

        table_rows[table_id] = rows

    result: list[TableData] = []
    for table_cfg in sorted_tables:
        table_id = str(table_cfg.get("id", "table"))
        rows = table_rows.get(table_id, [])
        column_cfgs = [c for c in (table_cfg.get("columns") or []) if isinstance(c, dict)]
        pk_column = str(table_cfg.get("pk", {}).get("column", f"{table_id}_id"))
        fk_cfg = table_cfg.get("fk") or []
        fk_entry = fk_cfg[0] if isinstance(fk_cfg, list) and fk_cfg else None
        fk_column = str(fk_entry.get("column")) if isinstance(fk_entry, dict) and fk_entry.get("column") else None

        col_defs = [{"name": pk_column, "type": "text"}]
        if fk_column:
            col_defs.append({"name": fk_column, "type": "text"})
        col_defs.extend(
            {
                "name": str(c.get("name", "col")),
                "type": str(c.get("type", "text")),
            }
            for c in column_cfgs
        )

        normalized_rows = []
        for row in rows:
            normalized = {col["name"]: row.get(col["name"]) for col in col_defs}
            normalized_rows.append(normalized)

        if not normalized_rows:
            continue
        result.append(
            TableData(
                id=table_id,
                name=str(table_cfg.get("name", table_id)),
                columns=col_defs,
                rows=normalized_rows,
            )
        )

    return result


def _iter_matches(data: Any, base_path: str) -> list[dict[str, Any]]:
    tokens = _parse_base_path(base_path)
    matches: list[dict[str, Any]] = []

    def _walk(current: Any, idx: int, owner_obj: dict[str, Any] | None) -> None:
        if idx >= len(tokens):
            matches.append({"value": current, "parent_obj": owner_obj})
            return
        token = tokens[idx]
        if token == "[*]":
            if isinstance(current, list):
                for item in current:
                    _walk(item, idx + 1, owner_obj)
            return

        if isinstance(current, dict) and token in current:
            next_value = current[token]
            next_owner = current if isinstance(next_value, list) else owner_obj
            _walk(next_value, idx + 1, next_owner)

    _walk(data, 0, None)
    return matches


def _parse_base_path(path: str) -> list[str]:
    if not path.startswith("$"):
        return []
    tail = path[1:]
    tokens: list[str] = []
    while tail:
        if tail.startswith("."):
            tail = tail[1:]
            key = []
            while tail and not tail.startswith(".") and not tail.startswith("[*]"):
                key.append(tail[0])
                tail = tail[1:]
            if key:
                tokens.append("".join(key))
            continue
        if tail.startswith("[*]"):
            tokens.append("[*]")
            tail = tail[3:]
            continue
        break
    return tokens


def _extract_relative_value(obj: dict[str, Any], path: str) -> Any:
    if path == "$":
        return obj
    if not path.startswith("$."):
        return None
    current: Any = obj
    for token in path[2:].split("."):
        if token.endswith("[*]"):
            key = token[:-3]
            if not isinstance(current, dict) or key not in current:
                return None
            value = current[key]
            if not isinstance(value, list):
                return None
            return json.dumps(value, ensure_ascii=False)
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    if isinstance(current, (dict, list)):
        return json.dumps(current, ensure_ascii=False)
    return current

