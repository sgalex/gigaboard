"""Tests for _fix_echarts_yaxis_index auto-fix."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend'))

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


def _make_agent():
    return WidgetCodexAgent(message_bus=None, gigachat_service=None)


def test_single_yaxis_with_yaxisindex_1():
    """yAxisIndex: 1 + single yAxis object → convert to array."""
    agent = _make_agent()
    code = """const option = {
  xAxis: { type: 'category', data: ['A','B','C'] },
  yAxis: { type: 'value' },
  series: [
    { type: 'bar', data: [10, 20, 30] },
    { type: 'line', yAxisIndex: 1, data: [100, 200, 300] }
  ]
};"""
    fixed = agent._fix_echarts_yaxis_index(code)
    assert 'yAxis: [{' in fixed, f"Expected array. Got: {fixed}"
    assert '{type: "value"}' in fixed, f"Missing extra axis entry"
    print("PASS: single yAxis + yAxisIndex:1 -> array")


def test_no_yaxisindex():
    """No yAxisIndex → no change."""
    agent = _make_agent()
    code = """const option = {
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: [1, 2, 3] }]
};"""
    fixed = agent._fix_echarts_yaxis_index(code)
    assert fixed == code, "Should not change when no yAxisIndex"
    print("PASS: no yAxisIndex unchanged")


def test_yaxisindex_0_only():
    """yAxisIndex: 0 with single yAxis → no change."""
    agent = _make_agent()
    code = """const option = {
  yAxis: { type: 'value' },
  series: [{ type: 'bar', yAxisIndex: 0, data: [1] }]
};"""
    fixed = agent._fix_echarts_yaxis_index(code)
    assert fixed == code, "yAxisIndex:0 is fine with single yAxis"
    print("PASS: yAxisIndex:0 unchanged")


def test_empty_input():
    """Empty string → unchanged."""
    agent = _make_agent()
    assert agent._fix_echarts_yaxis_index('') == ''
    assert agent._fix_echarts_yaxis_index(None) is None
    print("PASS: empty input")


def test_user_exact_pattern():
    """Exact pattern from user's broken widget."""
    agent = _make_agent()
    code = """if (window.chartInstance) window.chartInstance.dispose();
window.chartInstance = echarts.init(document.getElementById('chart'));

const sorted = tables['sorted'];

const option = {
  title: {
    text: 'BI tools',
    left: 'center'
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: sorted.rows.map(row => row['biName']),
    axisLabel: { rotate: 45 }
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      name: 'Vacancies',
      type: 'bar',
      data: sorted.rows.map(row => Number(row['count']))
    },
    {
      name: 'Salary',
      type: 'line',
      yAxisIndex: 1,
      data: sorted.rows.map(row => Number(row['salary']))
    }
  ]
};

window.chartInstance.setOption(option);
window.__widgetResize = () => { if (window.chartInstance) window.chartInstance.resize(); };"""

    fixed = agent._fix_echarts_yaxis_index(code)
    # yAxis should now be an array
    assert 'yAxis: [{' in fixed, f"Expected yAxis array"
    # Original content preserved
    assert "type: 'value'" in fixed
    # Extra axis added
    assert '{type: "value"}' in fixed
    # Rest of code intact
    assert "window.chartInstance.setOption(option)" in fixed
    assert "window.__widgetResize" in fixed
    print("PASS: user exact pattern fixed")


def test_yaxis_with_name_property():
    """yAxis with name property is preserved."""
    agent = _make_agent()
    code = """const option = {
  yAxis: {
    type: 'value',
    name: 'Count'
  },
  series: [
    { type: 'bar', data: [1] },
    { type: 'line', yAxisIndex: 1, data: [2] }
  ]
};"""
    fixed = agent._fix_echarts_yaxis_index(code)
    assert 'yAxis: [{' in fixed
    assert "name: 'Count'" in fixed, "Original yAxis properties preserved"
    print("PASS: yAxis with name property preserved")


def test_yaxisindex_2():
    """yAxisIndex: 2 → need 3 yAxis entries."""
    agent = _make_agent()
    code = """const option = {
  yAxis: { type: 'value' },
  series: [
    { type: 'bar', data: [1] },
    { type: 'line', yAxisIndex: 1, data: [2] },
    { type: 'scatter', yAxisIndex: 2, data: [3] }
  ]
};"""
    fixed = agent._fix_echarts_yaxis_index(code)
    assert 'yAxis: [{' in fixed
    # Should have 2 extra {type: "value"} entries (for index 1 and 2)
    assert fixed.count('{type: "value"}') == 2, f"Expected 2 extra axes"
    print("PASS: yAxisIndex:2 → 3 yAxis entries")


if __name__ == '__main__':
    test_single_yaxis_with_yaxisindex_1()
    test_no_yaxisindex()
    test_yaxisindex_0_only()
    test_empty_input()
    test_user_exact_pattern()
    test_yaxis_with_name_property()
    test_yaxisindex_2()
    print("\nAll 7 tests passed!")
