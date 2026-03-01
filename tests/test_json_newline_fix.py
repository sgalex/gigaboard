"""Tests for _fix_literal_newlines_in_json and _parse_json_from_llm."""
import sys
sys.path.insert(0, "apps/backend")

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


def test_fix_literal_newlines_basic():
    """Literal newlines inside JSON string values should become \\n."""
    raw = '{"render_body": "\n  if (x) {\n    y();\n  }\n"}'
    fixed = WidgetCodexAgent._fix_literal_newlines_in_json(raw)
    assert "\n" not in fixed.split('"render_body"')[1].split('}')[0].replace("\\n", ""), \
        f"Still has literal newlines: {repr(fixed)}"
    import json
    parsed = json.loads(fixed)
    assert "if (x)" in parsed["render_body"]
    assert "\n" in parsed["render_body"]  # After json.loads, \\n becomes \n
    print("  PASS: basic literal newlines")


def test_fix_literal_newlines_preserves_existing_escapes():
    """Already-escaped \\n should not be double-escaped."""
    raw = '{"a": "line1\\nline2"}'
    fixed = WidgetCodexAgent._fix_literal_newlines_in_json(raw)
    import json
    parsed = json.loads(fixed)
    assert parsed["a"] == "line1\nline2"
    print("  PASS: preserves existing escapes")


def test_fix_literal_newlines_outside_strings():
    """Newlines outside strings (formatting) should be preserved."""
    raw = '{\n  "a": "hello",\n  "b": "world"\n}'
    fixed = WidgetCodexAgent._fix_literal_newlines_in_json(raw)
    import json
    parsed = json.loads(fixed)
    assert parsed["a"] == "hello"
    assert parsed["b"] == "world"
    print("  PASS: newlines outside strings preserved")


def test_parse_gigachat_response_with_literal_newlines():
    """Simulate actual GigaChat response pattern from logs."""
    # This is what GigaChat actually returns (literal newlines inside render_body)
    gigachat_response = '''```json
{
  "widget_name": "LogoByteLengthBarChart",
  "widget_type": "chart",
  "description": "Bar chart showing byte lengths of logos",
  "render_body": "
  if (window.chartInstance) window.chartInstance.dispose();
  window.chartInstance = echarts.init(document.getElementById('chart'));

  const labelCol = colNames[0];
  const valueCol = colNames[1];

  const option = {
    xAxis: { type: 'category', data: rows.map(r => r[labelCol]) },
    yAxis: { type: 'value' },
    series: [{ data: rows.map(r => Number(r[valueCol])), type: 'bar' }],
    tooltip: { trigger: 'axis' }
  };

  window.chartInstance.setOption(option);
  window.__widgetResize = () => { if (window.chartInstance) window.chartInstance.resize(); };
  ",
  "styles": "",
  "scripts": "<script src=\\"/libs/echarts.min.js\\"></script>"
}
```'''

    # Create a minimal agent instance for _parse_json_from_llm
    import logging
    agent = WidgetCodexAgent.__new__(WidgetCodexAgent)
    agent.logger = logging.getLogger("test")

    parsed = agent._parse_json_from_llm(gigachat_response)
    
    assert "render_body" in parsed, f"No render_body in parsed! Keys: {list(parsed.keys())}"
    assert parsed["render_body"].strip() != "", "render_body is empty!"
    assert "chartInstance" in parsed["render_body"], "render_body doesn't contain expected code"
    assert parsed["widget_name"] == "LogoByteLengthBarChart"
    assert "echarts.min.js" in parsed.get("scripts", "")
    print(f"  PASS: GigaChat response parsed! render_body={len(parsed['render_body'])} chars")


def test_parse_valid_json_still_works():
    """Valid JSON with \\n escapes should still parse fine."""
    valid_response = '{"widget_name": "Test", "render_body": "const x = 1;\\nconst y = 2;", "styles": "", "scripts": ""}'
    
    import logging
    agent = WidgetCodexAgent.__new__(WidgetCodexAgent)
    agent.logger = logging.getLogger("test")
    
    parsed = agent._parse_json_from_llm(valid_response)
    assert parsed["widget_name"] == "Test"
    assert "const x = 1;" in parsed["render_body"]
    print("  PASS: valid JSON still works")


def test_tabs_and_carriage_returns():
    """Literal tabs and \\r inside strings should also be escaped."""
    raw = '{"code": "\tindented\r\nline"}'
    fixed = WidgetCodexAgent._fix_literal_newlines_in_json(raw)
    import json
    parsed = json.loads(fixed)
    assert "\t" in parsed["code"]
    assert "\n" in parsed["code"]
    print("  PASS: tabs and \\r handled")


if __name__ == "__main__":
    test_fix_literal_newlines_basic()
    test_fix_literal_newlines_preserves_existing_escapes()
    test_fix_literal_newlines_outside_strings()
    test_parse_gigachat_response_with_literal_newlines()
    test_parse_valid_json_still_works()
    test_tabs_and_carriage_returns()
    print("\nALL 6 TESTS PASSED")
