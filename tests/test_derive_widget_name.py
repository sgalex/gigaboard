"""Tests for WidgetCodex._derive_widget_name() — smart widget name fallback."""

import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


@pytest.fixture
def codex():
    """Create a WidgetCodexAgent instance without real config."""
    return WidgetCodexAgent.__new__(WidgetCodexAgent)


# ── Boilerplate stripping ──────────────────────────────────────────


def test_strips_boilerplate_description(codex):
    """Planner description like 'Создай визуализацию (HTML виджет) для данных' → meaningful name or fallback."""
    name = codex._derive_widget_name(
        "", "Создай визуализацию (HTML виджет) для данных", ""
    )
    # Should NOT contain boilerplate
    assert "визуализаци" not in name.lower() or name == "Визуализация данных"
    assert "HTML виджет" not in name


def test_strips_boilerplate_keeps_meaningful_suffix(codex):
    """'Создай визуализацию продаж по месяцам' → 'Продаж по месяцам'."""
    name = codex._derive_widget_name(
        "", "Создай визуализацию продаж по месяцам", ""
    )
    assert "продаж" in name.lower()
    assert "создай" not in name.lower()


def test_user_request_has_priority(codex):
    """user_request is preferred over description."""
    name = codex._derive_widget_name(
        "Покажи топ-10 брендов",
        "Создай визуализацию (HTML виджет) для данных",
        "",
    )
    assert "топ-10 брендов" in name.lower()


def test_user_request_boilerplate_also_stripped(codex):
    """Even user_request gets boilerplate stripped."""
    name = codex._derive_widget_name(
        "Построй график доходов по кварталам", "", ""
    )
    # 'Построй график' is boilerplate; 'доходов по кварталам' is meaningful
    assert "построй" not in name.lower()
    assert "доход" in name.lower()


def test_pure_boilerplate_fallback_to_tables(codex):
    """When both user_request and description are pure boilerplate, use table names."""
    name = codex._derive_widget_name(
        "",
        "Создай визуализацию (HTML виджет) для данных",
        "Таблица 'sales_monthly': 12 строк, 3 колонки\nТаблица 'products': 50 строк",
    )
    assert "sales_monthly" in name


def test_pure_boilerplate_no_tables_generic(codex):
    """When everything is boilerplate and no tables, return generic."""
    name = codex._derive_widget_name(
        "", "Создай визуализацию (HTML виджет) для данных", ""
    )
    assert name == "Визуализация данных"


# ── Clean user requests ────────────────────────────────────────────


def test_clean_user_request_used_directly(codex):
    """A meaningful user_request is used as-is (truncated if needed)."""
    name = codex._derive_widget_name(
        "Динамика продаж электроники за 2024 год", "", ""
    )
    assert "динамика продаж" in name.lower()


def test_long_name_truncated(codex):
    """Names over 60 chars are truncated with ellipsis."""
    long_req = "Распределение клиентов по регионам с учётом среднего чека и количества заказов за последний квартал"
    name = codex._derive_widget_name(long_req, "", "")
    assert len(name) <= 60


def test_english_user_request(codex):
    """English requests work too."""
    name = codex._derive_widget_name("Revenue by quarter", "", "")
    assert "revenue by quarter" in name.lower()


def test_english_boilerplate_stripped(codex):
    """English boilerplate like 'Create visualization widget' is stripped."""
    name = codex._derive_widget_name(
        "Create data visualization widget for sales", "", ""
    )
    assert "create" not in name.lower()
    assert "sales" in name.lower()


# ── Edge cases ─────────────────────────────────────────────────────


def test_empty_everything(codex):
    """All empty → generic name."""
    name = codex._derive_widget_name("", "", "")
    assert name == "Визуализация данных"


def test_whitespace_only(codex):
    """Whitespace-only inputs → generic name."""
    name = codex._derive_widget_name("   ", "   ", "")
    assert name == "Визуализация данных"


def test_first_letter_capitalized(codex):
    """Output always starts with uppercase."""
    name = codex._derive_widget_name("доходы по группам", "", "")
    assert name[0].isupper()


def test_table_names_en(codex):
    """English table name extraction."""
    name = codex._derive_widget_name(
        "", "", "Table 'quarterly_revenue': 20 rows"
    )
    assert "quarterly_revenue" in name


# ── English planner boilerplate stripping ───────────────────────


def test_english_planner_task_description(codex):
    """Planner generates English task like 'Generate HTML widget using ECharts v6 for @sorted'."""
    name = codex._derive_widget_name(
        "",
        "Generate HTML widget using ECharts v6 for visualization of @sorted data",
        ""
    )
    # Should NOT contain planner boilerplate
    assert "HTML widget" not in name
    assert "ECharts" not in name
    assert "Generate" not in name


def test_english_planner_task_with_echarts(codex):
    """Another planner task pattern."""
    name = codex._derive_widget_name(
        "",
        "Create HTML widget for @sales_data table visualization",
        ""
    )
    assert "HTML widget" not in name
    assert "Create" not in name
