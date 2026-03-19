"""Tests for WidgetCodexAgent._fix_formatter_multiline_strings — JS SyntaxError from newline inside '...'."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


@pytest.fixture
def codex():
    return WidgetCodexAgent(message_bus=None, gigachat_service=None)


def test_pie_label_formatter_newline_becomes_escape(codex):
    """ECharts label formatter split across lines breaks JS; fix to \\n in string."""
    broken = """series: [{
  label: {
    formatter: '{b}
        {c}%'
  }
}]"""
    fixed = codex._fix_formatter_multiline_strings(broken)
    assert "\n" not in fixed.split("formatter:")[1].split("'")[1]  # content between first pair of '
    assert "{b}\\n{c}%" in fixed or "{b}\\n" in fixed


def test_single_line_formatter_unchanged(codex):
    code = "formatter: '{b}: {c}%'"
    assert codex._fix_formatter_multiline_strings(code) == code


def test_double_quoted_formatter_multiline(codex):
    broken = 'tooltip: { formatter: "{a}\n{b}" }'
    fixed = codex._fix_formatter_multiline_strings(broken)
    assert '"{a}\\n{b}"' in fixed


def test_u2028_line_separator_in_js_string(codex):
    """U+2028 inside '...' causes Invalid or unexpected token in browsers."""
    broken = "tooltip: { formatter: '{b}:\u2028{c}%' }"
    fixed = codex._fix_illegal_js_string_line_terminators(broken)
    assert "\u2028" not in fixed
    assert "{b}:\\n{c}" in fixed
