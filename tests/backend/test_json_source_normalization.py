"""Tests for JSON source schema extraction and normalization."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "backend"))
from app.sources.json.extractor import JSONSource


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


def test_json_source_max_rows_limits_each_table():
    extractor = JSONSource()
    config = {"filename": "rows.json", "max_rows": 1}
    payload = {"items": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}

    result = asyncio.run(extractor.extract(config=config, file_content=json.dumps(payload).encode("utf-8")))

    assert result.success
    assert len(result.tables) == 1
    assert len(result.tables[0].rows) == 1

