"""Tests for universal WIDGET_SCAFFOLD (no ECharts-specific code)."""
import sys
sys.path.insert(0, "apps/backend")

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent, WIDGET_SCAFFOLD


def test_scaffold_has_correct_placeholders():
    assert "%%CUSTOM_SCRIPTS%%" in WIDGET_SCAFFOLD
    assert "%%CUSTOM_STYLES%%" in WIDGET_SCAFFOLD
    assert "%%CUSTOM_HEAD_LINKS%%" in WIDGET_SCAFFOLD
    assert "%%RENDER_BODY%%" in WIDGET_SCAFFOLD
    assert "CUSTOM_SCRIPTS_START" in WIDGET_SCAFFOLD
    assert "CUSTOM_SCRIPTS_END" in WIDGET_SCAFFOLD
    print("  PASS: scaffold has correct placeholders")


def test_no_echarts_in_scaffold():
    assert "echarts.min.js" not in WIDGET_SCAFFOLD, "echarts.min.js still in scaffold!"
    assert "let chartInstance" not in WIDGET_SCAFFOLD, "chartInstance still declared!"
    assert "typeof echarts" not in WIDGET_SCAFFOLD, "echarts type check still in scaffold!"
    assert "chartInstance.resize" not in WIDGET_SCAFFOLD, "chartInstance.resize still in scaffold!"
    print("  PASS: no ECharts-specific code in scaffold")


def test_universal_resize():
    assert "window.__widgetResize" in WIDGET_SCAFFOLD
    print("  PASS: universal resize handler")


def test_direct_boot():
    assert "render();" in WIDGET_SCAFFOLD
    assert "startAutoRefresh(render)" in WIDGET_SCAFFOLD
    # waitForLib should still exist as utility, just not in boot
    assert "function waitForLib" in WIDGET_SCAFFOLD
    print("  PASS: direct boot (no waitForLib in boot sequence)")


def test_assemble_with_scripts():
    result = WidgetCodexAgent._assemble_widget(
        "const x = 1;",
        ".my-class { color: red; }",
        '<script src="/libs/echarts.min.js"></script>',
    )
    assert '<script src="/libs/echarts.min.js"></script>' in result
    assert ".my-class { color: red; }" in result
    assert "const x = 1;" in result
    print("  PASS: assemble with scripts")


def test_assemble_without_scripts():
    result = WidgetCodexAgent._assemble_widget(
        'document.getElementById("chart").innerHTML = "hello";',
        "",
        "",
        "",
    )
    assert "CUSTOM_SCRIPTS_START" in result
    assert "echarts.min.js" not in result
    assert 'document.getElementById("chart").innerHTML' in result
    print("  PASS: assemble without scripts (plain HTML)")


def test_assemble_with_head_links_leaflet():
    rb = 'window.mapInstance = L.map("chart");'
    hl = '  <link rel="stylesheet" href="/libs/leaflet.css">'
    out = WidgetCodexAgent._assemble_widget(rb, "", '<script src="/libs/leaflet.js"></script>', hl)
    assert "/libs/leaflet.css" in out
    assert "/libs/leaflet.js" in out
    assert "L.map" in out
    print("  PASS: assemble with Leaflet head link + script")


def test_roundtrip():
    rb = (
        'if (window.chartInstance) window.chartInstance.dispose();\n'
        'window.chartInstance = echarts.init(document.getElementById("chart"));\n'
        'window.chartInstance.setOption({xAxis:{type:"category"}});'
    )
    css = ".card { padding: 10px; }"
    scripts = '<script src="/libs/echarts.min.js"></script>'

    assembled = WidgetCodexAgent._assemble_widget(rb, css, scripts)
    parts = WidgetCodexAgent._extract_dynamic_parts(assembled)

    assert parts is not None, "extract returned None"
    assert parts["render_body"].strip() == rb.strip(), (
        f"render_body mismatch:\n  GOT: {repr(parts['render_body'][:120])}\n  EXP: {repr(rb[:120])}"
    )
    assert parts["styles"].strip() == css.strip(), "styles mismatch"
    assert parts["scripts"].strip() == scripts.strip(), (
        f"scripts mismatch:\n  GOT: {repr(parts['scripts'])}\n  EXP: {repr(scripts)}"
    )
    print("  PASS: roundtrip assemble -> extract")


if __name__ == "__main__":
    test_scaffold_has_correct_placeholders()
    test_no_echarts_in_scaffold()
    test_universal_resize()
    test_direct_boot()
    test_assemble_with_scripts()
    test_assemble_without_scripts()
    test_assemble_with_head_links_leaflet()
    test_roundtrip()
    print("\nALL 8 TESTS PASSED")
