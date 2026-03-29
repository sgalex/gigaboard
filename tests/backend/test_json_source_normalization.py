"""Tests for JSON source schema extraction and normalization."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "backend"))
from app.sources.json.extractor import JSONSource
from app.sources.json.normalizer import extract_tables_from_mapping


def test_json_source_generates_schema_and_mapping_spec():
    extractor = JSONSource()
    config = {"filename": "commerce.json"}
    payload = {
        "КоммерческаяИнформация": {
            "Документ": [
                {
                    "Ид": "doc-1",
                    "Дата": "2026-03-20",
                    "Контрагенты": {
                        "Контрагент": [
                            {"ИНН": "7701000001", "КПП": "770101001"},
                            {"ИНН": "7701000002", "КПП": "770101002"},
                        ]
                    },
                }
            ]
        }
    }

    result = asyncio.run(extractor.extract(config=config, file_content=json.dumps(payload, ensure_ascii=False).encode("utf-8")))

    assert result.success
    assert len(result.tables) >= 2
    assert "schema_snapshot" in config
    assert "mapping_spec" in config
    assert isinstance(config["mapping_spec"].get("tables"), list)


def test_json_source_uses_saved_mapping_spec():
    extractor = JSONSource()
    config = {
        "filename": "orders.json",
        "mapping_spec": {
            "version": "1.0",
            "tables": [
                {
                    "id": "orders",
                    "name": "orders",
                    "base_path": "$.orders[*]",
                    "pk": {"column": "order_id", "strategy": "surrogate_uuid"},
                    "columns": [
                        {"name": "external_id", "type": "text", "path": "$.id", "nullable": False},
                        {"name": "amount", "type": "number", "path": "$.amount", "nullable": True},
                    ],
                }
            ],
        },
    }
    payload = {"orders": [{"id": "A-1", "amount": 100}, {"id": "A-2", "amount": 200}]}

    result = asyncio.run(extractor.extract(config=config, file_content=json.dumps(payload).encode("utf-8")))

    assert result.success
    assert len(result.tables) == 1
    table = result.tables[0]
    row = table.rows[0]
    assert "external_id" in row
    assert row["external_id"] == "A-1"
    assert "order_id" in row
    assert len(row["order_id"]) == 36  # uuid string


def test_extract_tables_from_mapping_sets_fk_to_parent_surrogate():
    """Child rows must reference parent PK via same JSON object identity as parent table."""
    payload = {
        "data": [
            {"id": 1, "route": [{"x": 10}, {"x": 20}]},
            {"id": 2, "route": [{"x": 30}]},
        ]
    }
    mapping_spec = {
        "version": "1.0",
        "tables": [
            {
                "id": "trip",
                "name": "trip",
                "base_path": "$.data[*]",
                "pk": {"column": "trip_id", "strategy": "surrogate_uuid"},
                "columns": [{"name": "id", "type": "number", "path": "$.id", "nullable": True}],
            },
            {
                "id": "route_point",
                "name": "route_point",
                "base_path": "$.data[*].route[*]",
                "pk": {"column": "route_point_id", "strategy": "surrogate_uuid"},
                "fk": [
                    {
                        "column": "trip_id",
                        "ref_table": "trip",
                        "ref_column": "trip_id",
                    }
                ],
                "columns": [{"name": "x", "type": "number", "path": "$.x", "nullable": True}],
            },
        ],
    }
    tables = extract_tables_from_mapping(payload, mapping_spec)
    trip = next(t for t in tables if t.id == "trip")
    routes = next(t for t in tables if t.id == "route_point")
    trip_ids = {r["trip_id"] for r in trip.rows}
    for r in routes.rows:
        assert r["trip_id"] in trip_ids
        assert "route_point_id" in r
        assert len(r["route_point_id"]) == 36

    by_name = {c["name"]: c for c in routes.columns}
    assert "description" in by_name["route_point_id"]
    assert "PK" in by_name["route_point_id"]["description"]
    assert "description" in by_name["trip_id"]
    assert "FK" in by_name["trip_id"]["description"]
    assert "trip" in by_name["trip_id"]["description"]
    assert "description" in by_name["x"]
    assert "Не ключ" in by_name["x"]["description"]


def test_json_source_max_rows_limits_each_table():
    extractor = JSONSource()
    config = {"filename": "rows.json", "max_rows": 1}
    payload = {"items": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}

    result = asyncio.run(extractor.extract(config=config, file_content=json.dumps(payload).encode("utf-8")))

    assert result.success
    assert len(result.tables) == 1
    assert len(result.tables[0].rows) == 1

