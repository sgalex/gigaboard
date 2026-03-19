"""setOption(...) injection after onclick fix must not cut on first semicolon inside option."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


@pytest.fixture
def codex():
    return WidgetCodexAgent(message_bus=None, gigachat_service=None)


def test_js_closing_paren_skips_semicolon_inside_function(codex):
    s = """window.chartInstance.setOption({
  tooltip: { formatter: function(p) { return p.name + ';'; } },
  series: []
});"""
    m = __import__("re").search(r"setOption\s*\(", s)
    assert m
    close = codex._js_closing_paren_after(s, m.end() - 1)
    assert close > 0
    assert s[close - 1] == ")"
    assert s[close : close + 2].strip().startswith(";")


def test_onclick_inject_after_full_setoption(codex):
    body = """if (window.chartInstance) window.chartInstance.dispose();
window.chartInstance = echarts.init(document.getElementById('chart'));
window.chartInstance.setOption({
  series: [{ type: 'pie', data: [], onclick: function(e) { window.toggleFilter('a', 'b'); } }]
});"""
    fixed = codex._fix_echarts_onclick_in_series(body)
    assert "window.chartInstance.on('click'" in fixed
    import re

    m = list(re.finditer(r"window\.chartInstance\.setOption\s*\(", fixed))[-1]
    close = codex._js_closing_paren_after(fixed, m.end() - 1)
    assert close > 0
    j = close
    while j < len(fixed) and fixed[j] in " \t\n\r":
        j += 1
    assert fixed[j] == ";"
    insert_at = j + 1
    assert fixed[insert_at:].lstrip().startswith("window.chartInstance.on")
