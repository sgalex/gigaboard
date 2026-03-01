"""Tests for WidgetCodexAgent._fix_smart_quotes — sanitize typographic chars in JS/CSS."""

import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


@pytest.fixture
def codex():
    return WidgetCodexAgent(message_bus=None, gigachat_service=None)


# ── Smart / curly quotes ───────────────────────────────────────────


def test_single_curly_quotes_replaced(codex):
    """Typographic ' ' → ASCII '."""
    code = "const x = \u2018hello\u2019;"
    assert codex._fix_smart_quotes(code) == "const x = 'hello';"


def test_double_curly_quotes_replaced(codex):
    """Typographic " " → ASCII \"."""
    code = 'const x = \u201chello\u201d;'
    assert codex._fix_smart_quotes(code) == 'const x = "hello";'


def test_guillemets_replaced(codex):
    """« » → ASCII \"."""
    code = "const x = \u00abvalue\u00bb;"
    assert codex._fix_smart_quotes(code) == 'const x = "value";'


def test_low9_quotes_replaced(codex):
    """\u201e \u201a → ASCII equivalents."""
    code = "const x = \u201ehello\u201d;"
    assert codex._fix_smart_quotes(code) == 'const x = "hello";'


def test_prime_replaced(codex):
    """Prime symbols ′ ″ → ' \"."""
    code = "const a = \u2032test\u2032; const b = \u2033test\u2033;"
    result = codex._fix_smart_quotes(code)
    assert result == """const a = 'test'; const b = "test";"""


# ── Dashes ─────────────────────────────────────────────────────────


def test_em_dash_replaced(codex):
    """Em dash — → -- in JS code."""
    code = "// comment \u2014 hello"
    assert codex._fix_smart_quotes(code) == "// comment -- hello"


def test_en_dash_replaced(codex):
    """En dash – → - in JS code."""
    code = "const range = 1\u20132;"
    assert codex._fix_smart_quotes(code) == "const range = 1-2;"


# ── Invisible characters ──────────────────────────────────────────


def test_nbsp_replaced(codex):
    """Non-breaking space → regular space."""
    code = "const\u00a0x = 1;"
    assert codex._fix_smart_quotes(code) == "const x = 1;"


def test_zero_width_space_removed(codex):
    """Zero-width space removed."""
    code = "const\u200bx = 1;"
    assert codex._fix_smart_quotes(code) == "constx = 1;"


def test_bom_removed(codex):
    """BOM (U+FEFF) removed."""
    code = "\ufeffconst x = 1;"
    assert codex._fix_smart_quotes(code) == "const x = 1;"


def test_zwj_zwnj_removed(codex):
    """ZWNJ (U+200C) and ZWJ (U+200D) removed."""
    code = "const\u200cx\u200d = 1;"
    assert codex._fix_smart_quotes(code) == "constx = 1;"


# ── No-op for clean code ──────────────────────────────────────────


def test_clean_code_unchanged(codex):
    """Normal ASCII code passes through unchanged."""
    code = "const x = 'hello'; const y = \"world\";"
    assert codex._fix_smart_quotes(code) == code


def test_empty_string(codex):
    assert codex._fix_smart_quotes("") == ""


def test_none_returns_none(codex):
    assert codex._fix_smart_quotes(None) is None


# ── Real-world GigaChat patterns ──────────────────────────────────


def test_echarts_formatter_with_smart_quotes(codex):
    """Real case: ECharts formatter with curly quotes from GigaChat."""
    code = "formatter: \u2018{b}\\n{c} ({d}%)\u2019"
    assert codex._fix_smart_quotes(code) == "formatter: '{b}\\n{c} ({d}%)'"


def test_row_access_with_smart_quotes(codex):
    """Real case: row access like row['column'] with smart quotes."""
    code = "const val = row[\u2018brand\u2019];"
    assert codex._fix_smart_quotes(code) == "const val = row['brand'];"


def test_mixed_quotes_in_template_literal(codex):
    """Template literal with smart quotes inside."""
    code = "const html = `<div class=\u201ccard\u201d>${row[\u2018name\u2019]}</div>`;"
    assert codex._fix_smart_quotes(code) == 'const html = `<div class="card">${row[\'name\']}</div>`;'


def test_css_with_smart_quotes(codex):
    """CSS with smart quotes in font-family."""
    code = ".card { font-family: \u2018Inter\u2019, sans-serif; }"
    assert codex._fix_smart_quotes(code) == ".card { font-family: 'Inter', sans-serif; }"
