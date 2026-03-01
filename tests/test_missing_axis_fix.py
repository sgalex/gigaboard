"""Tests for WidgetCodex._fix_echarts_missing_axis() — auto-fix for bar/line without xAxis/yAxis."""

import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


@pytest.fixture
def codex():
    """Create a WidgetCodexAgent instance without real config."""
    agent = WidgetCodexAgent.__new__(WidgetCodexAgent)
    # Provide a minimal logger stub
    import logging
    agent.logger = logging.getLogger("test_missing_axis")
    return agent


# ── No-op cases (should NOT modify) ────────────────────────────


def test_empty_input(codex):
    assert codex._fix_echarts_missing_axis("") == ""


def test_none_input(codex):
    assert codex._fix_echarts_missing_axis(None) is None


def test_no_chart_type(codex):
    """Plain HTML widget — no chart types, should not touch."""
    code = "document.getElementById('chart').innerHTML = '<h1>Hello</h1>';"
    assert codex._fix_echarts_missing_axis(code) == code


def test_pie_chart_no_axis_needed(codex):
    """Pie charts don't need xAxis/yAxis — should not inject."""
    code = """
window.chartInstance.setOption({
  series: [{ type: 'pie', data: items }]
});
"""
    assert codex._fix_echarts_missing_axis(code) == code


def test_bar_chart_with_both_axes(codex):
    """Bar chart with proper xAxis + yAxis — should not modify."""
    code = """
window.chartInstance.setOption({
  xAxis: { type: 'category', data: labels },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: values }]
});
"""
    assert codex._fix_echarts_missing_axis(code) == code


def test_line_chart_with_both_axes(codex):
    """Line chart with proper xAxis + yAxis — should not modify."""
    code = """
window.chartInstance.setOption({
  xAxis: { type: 'category', data: months },
  yAxis: { type: 'value' },
  series: [{ type: 'line', data: counts }]
});
"""
    assert codex._fix_echarts_missing_axis(code) == code


# ── Fix cases (should inject missing axes) ──────────────────────


def test_bar_chart_missing_both_axes(codex):
    """Bar chart without xAxis/yAxis — should inject both."""
    code = """
window.chartInstance.setOption({
  tooltip: { trigger: 'item' },
  series: [{ type: 'bar', data: sorted.rows.map(r => r['count']) }]
});
"""
    result = codex._fix_echarts_missing_axis(code)
    assert "xAxis:" in result
    assert "yAxis:" in result
    assert "type: 'category'" in result
    assert "type: 'value'" in result


def test_line_chart_missing_both_axes(codex):
    """Line chart without xAxis/yAxis — should inject both."""
    code = """
window.chartInstance.setOption({
  series: [{ type: 'line', data: [1, 2, 3] }]
});
"""
    result = codex._fix_echarts_missing_axis(code)
    assert "xAxis:" in result
    assert "yAxis:" in result


def test_scatter_chart_missing_both_axes(codex):
    """Scatter chart without xAxis/yAxis — should inject both."""
    code = """
window.chartInstance.setOption({
  series: [{ type: 'scatter', data: points }]
});
"""
    result = codex._fix_echarts_missing_axis(code)
    assert "xAxis:" in result
    assert "yAxis:" in result


def test_bar_chart_missing_only_yaxis(codex):
    """Bar chart with xAxis but no yAxis — should inject yAxis only."""
    code = """
window.chartInstance.setOption({
  xAxis: { type: 'category', data: labels },
  series: [{ type: 'bar', data: values }]
});
"""
    result = codex._fix_echarts_missing_axis(code)
    assert "yAxis:" in result
    # xAxis should appear only once (the original)
    assert result.count("xAxis:") == 1


def test_bar_chart_missing_only_xaxis(codex):
    """Bar chart with yAxis but no xAxis — should inject xAxis only."""
    code = """
window.chartInstance.setOption({
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: values }]
});
"""
    result = codex._fix_echarts_missing_axis(code)
    assert "xAxis:" in result
    # yAxis should appear only once (the original)
    assert result.count("yAxis:") == 1


def test_injected_code_is_valid_js(codex):
    """Injected axes should produce syntactically valid JS (comma after injected block)."""
    code = """window.chartInstance.setOption({
  tooltip: { trigger: 'axis' },
  series: [{ type: 'bar', data: vals }]
});"""
    result = codex._fix_echarts_missing_axis(code)
    # Should have proper comma after injected config
    assert "xAxis: { type: 'category' }, yAxis: { type: 'value' }," in result


# ── Real-world broken code from user report ─────────────────────


def test_real_broken_widget(codex):
    """Real code from user report: bar chart without axis config."""
    code = """if (window.chartInstance) window.chartInstance.dispose();
window.chartInstance = echarts.init(document.getElementById('chart'));

const sorted = tables['sorted'];

const option = {
  tooltip: { trigger: 'item' },
  legend: { orient: 'horizontal', right: '0' },
  visualMap: {
    pieces: [
      { lt: 1000, color: '#91cc75' },
      { gte: 1000, lte: 5000, color: '#fac858' },
      { gte: 5000, color: '#ee6666' }
    ],
    orient: 'horizontal',
    right: '5%'
  },
  series: [
    {
      type: 'bar',
      data: sorted.rows.map(row => ({ value: Number(row['Количество вакансий']), name: row['biName'] })),
      itemStyle: {
        color: function(params) {
          let value = params.value;
          return echarts.util.findColor(echarts.visual.findColorStop(value, option.visualMap.pieces));
        }
      }
    }
  ]
};

window.chartInstance.setOption(option);
window.__widgetResize = () => { if (window.chartInstance) window.chartInstance.resize(); };"""
    result = codex._fix_echarts_missing_axis(code)
    assert "xAxis:" in result
    assert "yAxis:" in result


def test_mixed_cartesian_and_pie(codex):
    """If series has both bar and pie, still inject axes (bar needs them)."""
    code = """
window.chartInstance.setOption({
  series: [
    { type: 'bar', data: barData },
    { type: 'pie', data: pieData }
  ]
});
"""
    result = codex._fix_echarts_missing_axis(code)
    assert "xAxis:" in result
    assert "yAxis:" in result


def test_no_set_option_call(codex):
    """Cartesian type present but no .setOption() call — cannot fix safely."""
    code = """
const option = {
  series: [{ type: 'bar', data: vals }]
};
"""
    # No setOption call → can't safely inject
    assert codex._fix_echarts_missing_axis(code) == code


def test_candlestick_missing_axes(codex):
    """Candlestick chart (also cartesian) without axes — should inject."""
    code = """
window.chartInstance.setOption({
  series: [{ type: 'candlestick', data: ohlc }]
});
"""
    result = codex._fix_echarts_missing_axis(code)
    assert "xAxis:" in result
    assert "yAxis:" in result
