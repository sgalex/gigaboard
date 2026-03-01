"""Tests for DimensionService.auto_detect_and_upsert — dimension auto-detection."""
import asyncio
import sys
sys.path.insert(0, "apps/backend")

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


# ------------------------------------------------------------------
# Lightweight in-memory simulation of the auto-detect logic
# (does NOT require a real database)
# ------------------------------------------------------------------

def test_heuristics_string_column():
    """String column with <=100 unique values should be detected as a dimension."""
    from app.services.dimension_service import DimensionService

    max_u = DimensionService._MAX_UNIQUE.get("string", DimensionService._MAX_UNIQUE_DEFAULT)
    assert max_u == 100


def test_heuristics_number_column():
    """Numeric columns have tighter threshold (30)."""
    from app.services.dimension_service import DimensionService

    max_u = DimensionService._MAX_UNIQUE.get("number", DimensionService._MAX_UNIQUE_DEFAULT)
    assert max_u == DimensionService._MAX_UNIQUE_DEFAULT == 30


def test_col_type_mapping():
    """Column types map to correct dimension types."""
    from app.services.dimension_service import DimensionService

    assert DimensionService._COL_TYPE_TO_DIM_TYPE["string"] == "string"
    assert DimensionService._COL_TYPE_TO_DIM_TYPE["integer"] == "number"
    assert DimensionService._COL_TYPE_TO_DIM_TYPE["date"] == "date"
    assert DimensionService._COL_TYPE_TO_DIM_TYPE["boolean"] == "boolean"


def test_auto_detect_creates_dimensions():
    """Full integration: auto_detect_and_upsert creates Dimensions + Mappings.
    
    Uses a mock AsyncSession to simulate DB calls.
    """
    from app.services.dimension_service import DimensionService

    project_id = uuid4()
    node_id = uuid4()
    tables = [
        {
            "name": "sales",
            "columns": [
                {"name": "brand", "type": "string"},
                {"name": "region", "type": "string"},
                {"name": "revenue", "type": "number"},  # likely >10 unique → skipped
                {"name": "id", "type": "number"},        # many unique → skipped
            ],
            "rows": [
                {"brand": "Apple", "region": "US", "revenue": 100, "id": i}
                for i in range(200)
            ] + [
                {"brand": "Samsung", "region": "EU", "revenue": 200, "id": i}
                for i in range(200, 400)
            ] + [
                {"brand": "Sony", "region": "Asia", "revenue": 50, "id": i}
                for i in range(400, 500)
            ],
        }
    ]

    # Mock DB session
    db = AsyncMock()

    # First execute: load existing dimensions → empty
    mock_dims_result = MagicMock()
    mock_dims_result.scalars.return_value.all.return_value = []

    # Subsequent executes: mapping lookups → no existing mapping
    mock_mapping_result = MagicMock()
    mock_mapping_result.scalar_one_or_none.return_value = None

    # First call returns dims, all subsequent return mapping-not-found
    db.execute.side_effect = [mock_dims_result] + [mock_mapping_result] * 20

    # Track db.add calls
    added_objects = []
    def track_add(obj):
        added_objects.append(obj)
        if hasattr(obj, 'id') and obj.id is None:
            obj.id = uuid4()  # simulate flush generating id
    db.add.side_effect = track_add

    # Run
    results = asyncio.run(
        DimensionService.auto_detect_and_upsert(db, project_id, node_id, tables)
    )

    # brand (3 unique) and region (3 unique) should be detected
    # revenue: 3 unique values → within 10 limit → also detected
    # id: 500 unique → exceeds 10 → skipped
    dim_names = [r["dimension"] for r in results]
    assert "brand" in dim_names, f"Expected 'brand' in {dim_names}"
    assert "region" in dim_names, f"Expected 'region' in {dim_names}"

    # All results should have valid actions
    for r in results:
        assert r["action"] in ("created", "updated")
        assert r["confidence"] > 0

    print(f"PASS: {len(results)} dimensions detected: {dim_names}")


def test_auto_detect_fuzzy_match():
    """Existing dimension 'brand_name' should fuzzy-match column 'brand'."""
    from app.services.dimension_service import DimensionService
    from app.models.dimension import Dimension

    project_id = uuid4()
    node_id = uuid4()

    # Create a fake existing dimension
    existing_dim = MagicMock(spec=Dimension)
    existing_dim.id = uuid4()
    existing_dim.name = "brand_name"
    existing_dim.known_values = {"values": ["OldBrand"]}

    tables = [
        {
            "name": "products",
            "columns": [{"name": "brand", "type": "string"}],
            "rows": [
                {"brand": "Apple"},
                {"brand": "Samsung"},
                {"brand": "Sony"},
            ],
        }
    ]

    db = AsyncMock()

    # First call returns existing dims, subsequent calls return empty (for mapping check)
    mock_dims_result = MagicMock()
    mock_dims_result.scalars.return_value.all.return_value = [existing_dim]

    mock_mapping_result = MagicMock()
    mock_mapping_result.scalar_one_or_none.return_value = None

    db.execute.side_effect = [mock_dims_result, mock_mapping_result]

    added_objects = []
    db.add.side_effect = lambda obj: added_objects.append(obj)

    results = asyncio.run(
        DimensionService.auto_detect_and_upsert(db, project_id, node_id, tables)
    )

    assert len(results) == 1
    assert results[0]["action"] == "updated"
    # known_values should be merged
    assert "Apple" in existing_dim.known_values["values"]
    assert "OldBrand" in existing_dim.known_values["values"]

    print(f"PASS: fuzzy match reused existing dim, merged values: {existing_dim.known_values['values']}")


def test_auto_detect_empty_tables():
    """Empty tables should return empty results."""
    from app.services.dimension_service import DimensionService

    db = AsyncMock()
    results = asyncio.run(
        DimensionService.auto_detect_and_upsert(db, uuid4(), uuid4(), [])
    )
    assert results == []
    print("PASS: empty tables → empty results")


def test_auto_detect_skips_high_cardinality():
    """Columns with too many unique values should be skipped."""
    from app.services.dimension_service import DimensionService

    tables = [
        {
            "name": "data",
            "columns": [{"name": "user_id", "type": "string"}],
            "rows": [{"user_id": f"user_{i}"} for i in range(200)],
        }
    ]

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    results = asyncio.run(
        DimensionService.auto_detect_and_upsert(db, uuid4(), uuid4(), tables)
    )
    assert results == [], f"Expected no dimensions for 200 unique strings out of 200 rows (100% cardinality), got {results}"
    print("PASS: high cardinality (200 unique / 200 rows = 100%) → skipped")


def test_auto_detect_brand_high_unique_low_ratio():
    """'brand' column with 4000 uniques out of 50000 rows (8%) must be detected.

    This is the real-world case where brand has many unique values in absolute
    terms but a low cardinality ratio — it's a valid categorical dimension.
    """
    from app.services.dimension_service import DimensionService

    total_rows = 50_000
    brands = [f"Brand_{i}" for i in range(4_018)]
    rows = [{"brand": brands[i % len(brands)]} for i in range(total_rows)]

    tables = [
        {
            "name": "sales",
            "columns": [{"name": "brand", "type": "string"}],
            "rows": rows,
        }
    ]

    db = AsyncMock()

    mock_dims_result = MagicMock()
    mock_dims_result.scalars.return_value.all.return_value = []

    mock_mapping_result = MagicMock()
    mock_mapping_result.scalar_one_or_none.return_value = None

    db.execute.side_effect = [mock_dims_result, mock_mapping_result]

    added_objects = []
    def track_add(obj):
        added_objects.append(obj)
        if hasattr(obj, 'id') and obj.id is None:
            obj.id = uuid4()
    db.add.side_effect = track_add

    results = asyncio.run(
        DimensionService.auto_detect_and_upsert(db, uuid4(), uuid4(), tables)
    )

    # 4018/50000 ≈ 8% < 30% → should be detected
    dim_names = [r["dimension"] for r in results]
    assert "brand" in dim_names, (
        f"Expected 'brand' to be detected (4018 uniques / 50000 rows = 8% cardinality), "
        f"got: {dim_names}"
    )
    print(f"PASS: brand with 4018 uniques / 50000 rows (8%) → detected as dimension")


if __name__ == "__main__":
    test_heuristics_string_column()
    test_heuristics_number_column()
    test_col_type_mapping()
    test_auto_detect_creates_dimensions()
    test_auto_detect_fuzzy_match()
    test_auto_detect_empty_tables()
    test_auto_detect_skips_high_cardinality()
    test_auto_detect_brand_high_unique_low_ratio()
    print("\n" + "=" * 50)
    print("ALL TESTS PASSED")
