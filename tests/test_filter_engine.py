"""Tests for FilterEngine — see docs/CROSS_FILTER_SYSTEM.md §Phase 2."""
import pytest
from app.services.filter_engine import FilterEngine
from app.schemas.cross_filter import FilterCondition, FilterGroup, FilterOperator


# ── test data helpers ────────────────────────────────────────────────────

def _sales_table(n: int | None = None) -> dict:
    """Small sales-like table."""
    rows = [
        {"region": "North", "category": "Electronics", "amount": 100, "active": True},
        {"region": "South", "category": "Clothing", "amount": 200, "active": False},
        {"region": "North", "category": "Clothing", "amount": 50, "active": True},
        {"region": "East", "category": "Electronics", "amount": 300, "active": True},
        {"region": "South", "category": "Food", "amount": 150, "active": False},
    ]
    if n:
        rows = rows[:n]
    return {
        "name": "Sales",
        "columns": [
            {"name": "region", "type": "string"},
            {"name": "category", "type": "string"},
            {"name": "amount", "type": "int"},
            {"name": "active", "type": "bool"},
        ],
        "rows": rows,
        "row_count": len(rows),
        "column_count": 4,
    }


def _mappings(table_name: str = "Sales") -> list[dict]:
    """Dimension→column mappings for _sales_table."""
    return [
        {"dim_name": "region", "table_name": table_name, "column_name": "region"},
        {"dim_name": "category", "table_name": table_name, "column_name": "category"},
        {"dim_name": "amount", "table_name": table_name, "column_name": "amount"},
        {"dim_name": "active", "table_name": table_name, "column_name": "active"},
    ]


# ── Unit tests ───────────────────────────────────────────────────────────

class TestFilterEngineOperators:
    """Test every operator."""

    def test_eq(self):
        cond = FilterCondition(dim="region", op=FilterOperator.EQ, value="North")
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 2
        for row in result[0]["rows"]:
            assert row["region"] == "North"

    def test_ne(self):
        cond = FilterCondition(dim="region", op=FilterOperator.NE, value="North")
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 3

    def test_gt(self):
        cond = FilterCondition(dim="amount", op=FilterOperator.GT, value=100)
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 3

    def test_lt(self):
        cond = FilterCondition(dim="amount", op=FilterOperator.LT, value=150)
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 2

    def test_gte(self):
        cond = FilterCondition(dim="amount", op=FilterOperator.GTE, value=150)
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 3

    def test_lte(self):
        cond = FilterCondition(dim="amount", op=FilterOperator.LTE, value=150)
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 3

    def test_in(self):
        cond = FilterCondition(dim="region", op=FilterOperator.IN, value=["North", "East"])
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 3

    def test_not_in(self):
        cond = FilterCondition(dim="region", op=FilterOperator.NOT_IN, value=["North", "East"])
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 2

    def test_between(self):
        cond = FilterCondition(dim="amount", op=FilterOperator.BETWEEN, value=[100, 200])
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 3  # 100, 200, 150

    def test_contains(self):
        cond = FilterCondition(dim="category", op=FilterOperator.CONTAINS, value="elec")
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 2

    def test_starts_with(self):
        cond = FilterCondition(dim="category", op=FilterOperator.STARTS_WITH, value="Cloth")
        result = FilterEngine.apply_filters([_sales_table()], cond, _mappings())
        assert result[0]["row_count"] == 2


class TestFilterEngineGroups:
    """Test AND / OR / nested groups."""

    def test_and_group(self):
        group = FilterGroup(
            type="and",
            conditions=[
                FilterCondition(dim="region", op=FilterOperator.EQ, value="North"),
                FilterCondition(dim="category", op=FilterOperator.EQ, value="Clothing"),
            ],
        )
        result = FilterEngine.apply_filters([_sales_table()], group, _mappings())
        assert result[0]["row_count"] == 1

    def test_or_group(self):
        group = FilterGroup(
            type="or",
            conditions=[
                FilterCondition(dim="region", op=FilterOperator.EQ, value="North"),
                FilterCondition(dim="region", op=FilterOperator.EQ, value="East"),
            ],
        )
        result = FilterEngine.apply_filters([_sales_table()], group, _mappings())
        assert result[0]["row_count"] == 3

    def test_nested_groups(self):
        """(region == North AND category == Electronics) OR (amount > 150)"""
        group = FilterGroup(
            type="or",
            conditions=[
                FilterGroup(
                    type="and",
                    conditions=[
                        FilterCondition(dim="region", op=FilterOperator.EQ, value="North"),
                        FilterCondition(dim="category", op=FilterOperator.EQ, value="Electronics"),
                    ],
                ),
                FilterCondition(dim="amount", op=FilterOperator.GT, value=150),
            ],
        )
        result = FilterEngine.apply_filters([_sales_table()], group, _mappings())
        # North+Electronics = 1 row (amount=100), amount>150 = 2 rows (200, 300)
        # Union = 3 rows
        assert result[0]["row_count"] == 3


class TestFilterEngineEdgeCases:
    """Edge cases."""

    def test_none_filter_passthrough(self):
        tables = [_sales_table()]
        result = FilterEngine.apply_filters(tables, None, _mappings())
        assert result[0]["row_count"] == 5

    def test_empty_tables(self):
        result = FilterEngine.apply_filters(
            [], FilterCondition(dim="region", op=FilterOperator.EQ, value="North"), _mappings()
        )
        assert result == []

    def test_no_mapping_for_table(self):
        """Table without matching mappings should be returned as-is."""
        cond = FilterCondition(dim="region", op=FilterOperator.EQ, value="North")
        result = FilterEngine.apply_filters(
            [_sales_table()], cond, _mappings(table_name="Other")
        )
        assert result[0]["row_count"] == 5  # unfiltered

    def test_nonexistent_column(self):
        """Dimension mapped to non-existent column → data unchanged."""
        cond = FilterCondition(dim="region", op=FilterOperator.EQ, value="North")
        bad_mapping = [{"dim_name": "region", "table_name": "Sales", "column_name": "xxx"}]
        result = FilterEngine.apply_filters([_sales_table()], cond, bad_mapping)
        assert result[0]["row_count"] == 5

    def test_empty_group(self):
        """Empty AND-group → all rows pass."""
        group = FilterGroup(type="and", conditions=[])
        result = FilterEngine.apply_filters([_sales_table()], group, _mappings())
        assert result[0]["row_count"] == 5

    def test_dict_filter_input(self):
        """Filter passed as raw dict instead of Pydantic model."""
        raw = {"type": "condition", "dim": "region", "op": "==", "value": "North"}
        result = FilterEngine.apply_filters([_sales_table()], raw, _mappings())
        assert result[0]["row_count"] == 2


class TestExtractDimensions:
    def test_single_condition(self):
        cond = FilterCondition(dim="region", op=FilterOperator.EQ, value="x")
        assert FilterEngine.extract_dimensions(cond) == {"region"}

    def test_group(self):
        group = FilterGroup(
            type="and",
            conditions=[
                FilterCondition(dim="region", op=FilterOperator.EQ, value="x"),
                FilterCondition(dim="amount", op=FilterOperator.GT, value=0),
            ],
        )
        assert FilterEngine.extract_dimensions(group) == {"region", "amount"}


class TestFilterStats:
    def test_stats(self):
        original = [_sales_table()]
        cond = FilterCondition(dim="region", op=FilterOperator.EQ, value="North")
        filtered = FilterEngine.apply_filters(original, cond, _mappings())
        stats = FilterEngine.get_filter_stats(original, filtered)
        assert stats[0]["total_rows"] == 5
        assert stats[0]["filtered_rows"] == 2
        assert stats[0]["percentage"] == 40.0
