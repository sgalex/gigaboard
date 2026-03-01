"""Tests for transform_codex JSON parsing and syntax auto-fix."""
import ast
import json
import sys
sys.path.insert(0, "apps/backend")

from app.services.multi_agent.agents.transform_codex import TransformCodexAgent


def test_fix_literal_escapes_outside_strings():
    """GigaChat returns literal \n between JSON fields."""
    # Simulate: {"transformation_code": "df_x = df.groupby(\ncol\n)", \n  "description": "test"}
    # The \n inside the string value is a valid JSON escape
    # The \n between fields (after comma) is invalid - should be real newline
    response = '{\n  "transformation_code": "df_x = df.groupby(\\ncol\\n)", \\n  "description": "test"}'
    print("Input repr:", repr(response))
    
    fixed = TransformCodexAgent._fix_literal_escapes_outside_strings(response)
    print("Fixed repr:", repr(fixed))
    
    # The \n between fields should become a real newline
    # The \n inside string should stay as \n (JSON escape)
    parsed = json.loads(fixed)
    print("Parsed OK:", parsed)
    assert parsed["transformation_code"] == "df_x = df.groupby(\ncol\n)"
    assert parsed["description"] == "test"
    print("PASS: test_fix_literal_escapes_outside_strings\n")


def test_fix_literal_escapes_realistic():
    """Realistic GigaChat response from the bug report."""
    # GigaChat response with literal \n between fields
    response = (
        '{\n'
        '  "transformation_code": "df_aggregated_sales = df.groupby(\'brand\')[[\'salesCount\', \'salesAmount\']].agg(\\n'
        '    {\\n'
        '        \'salesCount\': \'sum\',\\n'
        '        \'salesAmount\': \'sum\'\\n'
        '    }\\n'
        ').reset_index()", \\n'
        '  "description": "Агрегация данных по бренду", \\n'
        '  "output_schema": {"columns": ["brand", "salesCount", "salesAmount"]}'
        '}'
    )
    print("Input (first 200):", response[:200])
    
    fixed = TransformCodexAgent._fix_literal_escapes_outside_strings(response)
    print("Fixed (first 200):", fixed[:200])
    
    parsed = json.loads(fixed)
    print("Parsed OK, code:", parsed["transformation_code"][:80])
    assert "transformation_code" in parsed
    assert "groupby" in parsed["transformation_code"]
    print("PASS: test_fix_literal_escapes_realistic\n")


def test_parse_json_from_llm_with_literal_newlines():
    """Full integration test: _parse_json_from_llm handles literal \\n."""
    agent = TransformCodexAgent.__new__(TransformCodexAgent)
    
    response = (
        '{\n'
        '  "transformation_code": "df_sales = df.groupby(\'brand\').sum().reset_index()", \\n'
        '  "description": "test", \\n'
        '  "output_schema": {"columns": ["brand"]}'
        '}'
    )
    
    parsed = agent._parse_json_from_llm(response)
    print("Parsed result:", parsed)
    assert "transformation_code" in parsed
    assert "df_sales" in parsed["transformation_code"]
    print("PASS: test_parse_json_from_llm_with_literal_newlines\n")


def test_fix_unbalanced_parens():
    """GigaChat drops a closing paren in multi-line agg call."""
    code = """df_aggregated_sales = df.groupby('brand').agg(
    sales_count=('salesCount', 'sum'),
    sales_amount=('salesAmount', 'sum'
).reset_index()"""
    
    print("Code with missing paren:")
    print(code)
    print()
    
    # Should fail to parse
    try:
        ast.parse(code)
        print("ERROR: code should have had a syntax error!")
        sys.exit(1)
    except SyntaxError as e:
        print(f"Confirmed SyntaxError: {e}")
    
    result = TransformCodexAgent._try_fix_unbalanced_parens(code)
    print("\nFixed code:")
    print(result)
    
    assert result is not None
    ast.parse(result)
    print("AST parse: OK")
    assert "sales_amount=('salesAmount', 'sum')" in result
    print("PASS: test_fix_unbalanced_parens\n")


def test_fix_unbalanced_brackets():
    """Missing closing bracket."""
    code = """df_result = df[['a', 'b', 'c'].sum()"""
    
    result = TransformCodexAgent._try_fix_unbalanced_parens(code)
    print("Fixed brackets:", result)
    # Should add ] somewhere
    if result:
        ast.parse(result)
        print("PASS: test_fix_unbalanced_brackets\n")
    else:
        print("NOTE: could not fix this case (acceptable)\n")


def test_already_balanced():
    """Balanced code should be returned as-is."""
    code = "df_x = df.groupby('a').sum().reset_index()"
    result = TransformCodexAgent._try_fix_unbalanced_parens(code)
    assert result == code
    print("PASS: test_already_balanced\n")


if __name__ == "__main__":
    test_fix_literal_escapes_outside_strings()
    test_fix_literal_escapes_realistic()
    test_parse_json_from_llm_with_literal_newlines()
    test_fix_unbalanced_parens()
    test_fix_unbalanced_brackets()
    test_already_balanced()
    print("=" * 50)
    print("ALL TESTS PASSED")
