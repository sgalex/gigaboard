"""Tests for _fix_undefined_col_vars auto-fix."""
import sys
import logging

sys.path.insert(0, "apps/backend")

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


def _make_agent():
    agent = WidgetCodexAgent.__new__(WidgetCodexAgent)
    agent.logger = logging.getLogger("test")
    return agent


def test_fixes_undefined_biNameCol():
    """Exact scenario from the bug: biNameCol used but never defined."""
    agent = _make_agent()
    code = """if (window.chartInstance) window.chartInstance.dispose();
window.chartInstance = echarts.init(document.getElementById('chart'));

const logoCol = 'logo';
const vacIdCol = 'vacId';

const option = {
  xAxis: { type: 'category', data: rows.map(r => r[biNameCol]) },
  yAxis: { type: 'value' },
  series: [{ data: rows.map(r => r[vacIdCol]), type: 'bar' }]
};"""

    fixed = agent._fix_undefined_col_vars(code)
    assert "const biNameCol = colNames[0];" in fixed, f"Missing biNameCol definition. Got:\n{fixed[:200]}"
    # logoCol and vacIdCol should NOT be re-declared (they're already defined)
    assert fixed.count("const logoCol") == 1
    assert fixed.count("const vacIdCol") == 1
    print("  PASS: fixes undefined biNameCol")


def test_no_fix_when_all_defined():
    """No changes when all variables are properly defined."""
    agent = _make_agent()
    code = """const labelCol = colNames[0];
const valueCol = colNames[1];
rows.map(r => r[labelCol]);
rows.map(r => Number(r[valueCol]));"""

    fixed = agent._fix_undefined_col_vars(code)
    assert fixed == code, "Should not modify code when all vars are defined"
    print("  PASS: no fix when all defined")


def test_ignores_string_literals():
    """r["columnName"] with string literal should not trigger fix."""
    agent = _make_agent()
    code = """rows.map(r => r["name"]);
rows.map(r => r['value']);"""

    fixed = agent._fix_undefined_col_vars(code)
    assert fixed == code, "Should not modify string-literal access"
    print("  PASS: ignores string literals")


def test_ignores_scaffold_vars():
    """colNames, rows, data, table should not trigger fix."""
    agent = _make_agent()
    code = """rows.map(r => r[col]);"""

    fixed = agent._fix_undefined_col_vars(code)
    assert fixed == code, f"'col' is a scaffold var, should not be fixed. Got:\n{fixed}"
    print("  PASS: ignores scaffold variables")


def test_multiple_undefined():
    """Multiple undefined vars get sequential colNames assignments."""
    agent = _make_agent()
    code = """const option = {
  xAxis: { data: rows.map(r => r[nameCol]) },
  series: [{ data: rows.map(r => r[scoreCol]) }]
};"""

    fixed = agent._fix_undefined_col_vars(code)
    assert "const nameCol = colNames[" in fixed
    assert "const scoreCol = colNames[" in fixed
    print("  PASS: multiple undefined vars")


def test_empty_code():
    """Empty code should return unchanged."""
    agent = _make_agent()
    assert agent._fix_undefined_col_vars("") == ""
    assert agent._fix_undefined_col_vars("   ") == "   "
    print("  PASS: empty code unchanged")


if __name__ == "__main__":
    test_fixes_undefined_biNameCol()
    test_no_fix_when_all_defined()
    test_ignores_string_literals()
    test_ignores_scaffold_vars()
    test_multiple_undefined()
    test_empty_code()
    print("\nALL 6 TESTS PASSED")
