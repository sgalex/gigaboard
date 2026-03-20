"""Schema extraction utilities for JSON sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_MAX_NODES = 4000
_MAX_SAMPLE_VALUES = 5


@dataclass
class _NodeStats:
    node_kind: str
    value_types: set[str]
    seen_count: int = 0
    null_count: int = 0
    sample_values: list[Any] | None = None

    def __post_init__(self) -> None:
        if self.sample_values is None:
            self.sample_values = []


def extract_schema_snapshot(data: Any) -> dict[str, Any]:
    """Build a compact schema snapshot used by JSON mapping editor."""
    stats: dict[str, _NodeStats] = {}

    def _ensure(path: str, node_kind: str) -> _NodeStats:
        current = stats.get(path)
        if current is None:
            current = _NodeStats(node_kind=node_kind, value_types=set())
            stats[path] = current
        return current

    def _value_type(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return "array"
        return "unknown"

    def _visit(value: Any, path: str) -> None:
        if len(stats) >= _MAX_NODES:
            return

        if isinstance(value, dict):
            node = _ensure(path, "object")
            node.seen_count += 1
            node.value_types.add("object")
            for key, nested in value.items():
                _visit(nested, f"{path}.{key}")
            return

        if isinstance(value, list):
            node = _ensure(path, "array")
            node.seen_count += 1
            node.value_types.add("array")
            wildcard_path = f"{path}[*]"
            _ensure(wildcard_path, "item")
            for item in value:
                _visit(item, wildcard_path)
            return

        node = _ensure(path, "scalar")
        node.seen_count += 1
        value_type = _value_type(value)
        node.value_types.add(value_type)
        if value is None:
            node.null_count += 1
        elif len(node.sample_values or []) < _MAX_SAMPLE_VALUES:
            node.sample_values.append(value)

    _visit(data, "$")

    nodes: list[dict[str, Any]] = []
    for path, node in sorted(stats.items(), key=lambda kv: kv[0]):
        value_types = sorted(node.value_types)
        cardinality = "1"
        if node.node_kind == "array":
            cardinality = "0..N"
        elif "null" in node.value_types:
            cardinality = "0..1"
        nodes.append(
            {
                "path": path,
                "node_kind": node.node_kind,
                "value_types": value_types,
                "cardinality": cardinality,
                "sample_values": (node.sample_values or [])[:_MAX_SAMPLE_VALUES],
                "null_ratio": (node.null_count / node.seen_count) if node.seen_count else 0.0,
            }
        )

    return {
        "version": "1.0",
        "root_type": _value_type(data),
        "nodes": nodes,
        "truncated": len(stats) >= _MAX_NODES,
    }

