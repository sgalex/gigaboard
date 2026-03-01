"""Tests for ContentNode/SourceNode naming pipeline.

Verifies:
1. SourceNode creation uses correct attribute name (node_metadata, not metadata)
2. _generate_content_metadata() response parsing for ContentNode names
3. V2 transform metadata generation fallback logic
"""
import sys
import os
import re
import json
import inspect

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend'))


# ══════════════════════════════════════════════════════════════════
#  SourceNode creation — correct attribute name (regression guard)
# ══════════════════════════════════════════════════════════════════

def test_source_node_service_uses_node_metadata():
    """Verify SourceNodeService.create_source_node uses node_metadata= (not metadata=).
    
    Bug history: metadata= silently sets SQLAlchemy MetaData instead of the JSONB column.
    The Python attribute is 'node_metadata', mapped to DB column 'metadata'.
    """
    from app.services.source_node_service import SourceNodeService
    
    source_code = inspect.getsource(SourceNodeService.create_source_node)
    
    # Must use node_metadata= in SourceNode constructor
    assert 'node_metadata=' in source_code, \
        "SourceNodeService.create_source_node must use node_metadata= (not metadata=) in SourceNode constructor"
    
    # Must NOT use bare metadata= in constructor (except in comments)
    # Find SourceNode( constructor call and check it doesn't use bare metadata=
    constructor_match = re.search(r'SourceNode\((.*?)\)', source_code, re.DOTALL)
    assert constructor_match, "SourceNode constructor call not found"
    constructor_args = constructor_match.group(1)
    
    # Check that there's no bare 'metadata=' (without 'node_' prefix) in constructor args
    bare_metadata_matches = re.findall(r'(?<!\w)metadata\s*=', constructor_args)
    node_metadata_matches = re.findall(r'node_metadata\s*=', constructor_args)
    
    # All metadata references should be node_metadata
    assert len(node_metadata_matches) >= 1, "Must have at least one node_metadata= in constructor"
    assert len(bare_metadata_matches) == 0, \
        f"Found bare 'metadata=' in SourceNode constructor — should be 'node_metadata='. Matches: {bare_metadata_matches}"


def test_content_node_service_uses_node_metadata():
    """Verify ContentNodeService.create_content_node uses node_metadata=."""
    from app.services.content_node_service import ContentNodeService
    
    source_code = inspect.getsource(ContentNodeService.create_content_node)
    
    assert 'node_metadata=' in source_code, \
        "ContentNodeService.create_content_node must use node_metadata= in ContentNode constructor"


def test_source_node_model_has_node_metadata():
    """SourceNode inherits node_metadata from ContentNode."""
    from app.models.source_node import SourceNode
    from app.models.content_node import ContentNode
    
    # ContentNode defines node_metadata
    assert hasattr(ContentNode, 'node_metadata'), \
        "ContentNode must have node_metadata attribute"
    
    # SourceNode inherits it
    assert hasattr(SourceNode, 'node_metadata'), \
        "SourceNode must inherit node_metadata from ContentNode"


def test_content_node_model_node_metadata_column():
    """Verify node_metadata maps to 'metadata' DB column."""
    from app.models.content_node import ContentNode
    
    # Check that the mapped column name is 'metadata' in the DB
    col = ContentNode.__table__.columns.get('metadata')
    assert col is not None, "ContentNode must have a 'metadata' column in the DB"


# ══════════════════════════════════════════════════════════════════
#  _generate_content_metadata() response parsing
# ══════════════════════════════════════════════════════════════════

def _parse_ai_metadata_response(response: str) -> dict:
    """Simulate the parsing logic from _generate_content_metadata."""
    import json
    import re
    
    # Try to extract JSON from response — support any key order
    brace_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
    if brace_match:
        try:
            metadata = json.loads(brace_match.group())
            if metadata.get("name") or metadata.get("description"):
                return {
                    "name": metadata.get("name", "")[:100],
                    "description": metadata.get("description", "")[:500],
                }
        except json.JSONDecodeError:
            pass
    
    # Second attempt: regex for JSON with "name" and "description"
    json_match = re.search(
        r'\{[^{}]*(?:"name"|"description")[^{}]*(?:"name"|"description")[^{}]*\}',
        response, re.DOTALL,
    )
    if json_match:
        try:
            metadata = json.loads(json_match.group())
            return {
                "name": metadata.get("name", "")[:100],
                "description": metadata.get("description", "")[:500],
            }
        except json.JSONDecodeError:
            pass
    
    # Try alternative: look for lines starting with name/description
    name_match = re.search(r'[*_`"\']*name[*_`"\']*\s*[:=]\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
    desc_match = re.search(r'[*_`"\']*description[*_`"\']*\s*[:=]\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
    
    if name_match or desc_match:
        return {
            "name": name_match.group(1)[:100] if name_match else "",
            "description": desc_match.group(1)[:500] if desc_match else "",
        }
    
    return {"name": "", "description": ""}


def test_parse_standard_json():
    """Standard JSON response from AI."""
    response = '{"name": "Продажи по месяцам", "description": "Группировка данных по месяцу"}'
    result = _parse_ai_metadata_response(response)
    assert result["name"] == "Продажи по месяцам"
    assert result["description"] == "Группировка данных по месяцу"


def test_parse_json_with_markdown():
    """JSON wrapped in markdown code block."""
    response = """```json
{"name": "Фильтрация данных", "description": "Отфильтрованы строки по условию"}
```"""
    result = _parse_ai_metadata_response(response)
    assert result["name"] == "Фильтрация данных"


def test_parse_reversed_key_order():
    """AI sometimes returns description before name."""
    response = '{"description": "Агрегация по регионам", "name": "Итоги по регионам"}'
    result = _parse_ai_metadata_response(response)
    assert result["name"] == "Итоги по регионам"
    assert result["description"] == "Агрегация по регионам"


def test_parse_json_with_preamble():
    """AI sometimes adds text before JSON."""
    response = """Вот результат анализа:

{"name": "Топ-10 продуктов", "description": "Выборка 10 продуктов с наибольшей выручкой"}

Надеюсь, это полезно!"""
    result = _parse_ai_metadata_response(response)
    assert result["name"] == "Топ-10 продуктов"


def test_parse_name_value_format():
    """AI returns key: "value" format instead of JSON."""
    response = 'name: "Сводная таблица"\ndescription: "Объединение двух таблиц по ключу"'
    result = _parse_ai_metadata_response(response)
    assert result["name"] == "Сводная таблица"
    assert result["description"] == "Объединение двух таблиц по ключу"


def test_parse_markdown_bold_keys():
    """AI wraps keys in markdown bold."""
    response = '**name**: "Анализ продаж"\n**description**: "Детальный анализ по категориям"'
    result = _parse_ai_metadata_response(response)
    assert result["name"] == "Анализ продаж"


def test_parse_long_name_truncated():
    """Names longer than 100 chars should be truncated."""
    long_name = "А" * 150
    response = f'{{"name": "{long_name}", "description": "test"}}'
    result = _parse_ai_metadata_response(response)
    assert len(result["name"]) == 100


def test_parse_empty_response():
    """Empty or garbage response returns empty strings."""
    result = _parse_ai_metadata_response("")
    assert result["name"] == ""
    assert result["description"] == ""
    
    result = _parse_ai_metadata_response("Я не могу выполнить этот запрос.")
    assert result["name"] == ""


def test_parse_json_with_extra_fields():
    """AI may return extra fields — we only need name and description."""
    response = '{"name": "Данные Q1", "description": "Квартальные данные", "confidence": 0.95}'
    result = _parse_ai_metadata_response(response)
    assert result["name"] == "Данные Q1"
    assert result["description"] == "Квартальные данные"


# ══════════════════════════════════════════════════════════════════
#  V2 transform route — must call _generate_content_metadata
# ══════════════════════════════════════════════════════════════════

def test_v2_transform_uses_ai_metadata():
    """V2 transform route (/{content_id}/transform) must call _generate_content_metadata.
    
    Previously it hardcoded 'Трансформация: {source_name}' without AI generation.
    """
    # Read the route source code
    import app.routes.content_nodes as content_nodes_module
    source_code = inspect.getsource(content_nodes_module.transform_content_node)
    
    assert '_generate_content_metadata' in source_code, \
        "V2 transform route must call _generate_content_metadata for AI-powered naming"
    
    # Should NOT hardcode "Трансформация:" as the only name source
    # It's OK as a fallback, but _generate_content_metadata should be primary
    assert 'ai_metadata' in source_code, \
        "V2 transform route must use ai_metadata result"


def test_v1_transform_uses_ai_metadata():
    """V1 transform route (/{content_id}/transform/execute) must call _generate_content_metadata."""
    import app.routes.content_nodes as content_nodes_module
    source_code = inspect.getsource(content_nodes_module.execute_transformation)
    
    assert '_generate_content_metadata' in source_code, \
        "V1 transform route must call _generate_content_metadata for AI-powered naming"


def test_transform_routes_use_serialize_helper():
    """Both V1 and V2 transform routes must use _serialize_content_node to ensure correct JSON keys.
    
    Bug history: Without serialization, node_metadata was returned as 'node_metadata' 
    instead of 'metadata' — frontend couldn't read contentNode.metadata.name.
    """
    import app.routes.content_nodes as content_nodes_module
    
    v1_source = inspect.getsource(content_nodes_module.execute_transformation)
    v2_source = inspect.getsource(content_nodes_module.transform_content_node)
    
    assert '_serialize_content_node' in v1_source, \
        "V1 execute_transformation must use _serialize_content_node for proper JSON serialization"
    assert '_serialize_content_node' in v2_source, \
        "V2 transform_content_node must use _serialize_content_node for proper JSON serialization"


def test_serialize_content_node_outputs_metadata_key():
    """_serialize_content_node must output 'metadata' key (not 'node_metadata')."""
    from app.routes.content_nodes import _serialize_content_node
    from app.schemas.content_node import ContentNodeResponse
    
    # Verify the helper function exists and uses ContentNodeResponse  
    source_code = inspect.getsource(_serialize_content_node)
    assert 'ContentNodeResponse' in source_code, \
        "_serialize_content_node must use ContentNodeResponse for proper alias mapping"
    assert 'by_alias' in source_code, \
        "_serialize_content_node must use by_alias=True to apply serialization_alias"


# ══════════════════════════════════════════════════════════════════
#  Frontend title fallback logic (documentation tests)
# ══════════════════════════════════════════════════════════════════

def test_source_node_title_fallback_chain():
    """Document the SourceNodeCard getTitle() fallback chain.
    
    1. sourceNode.metadata?.name → primary (set by frontend dialog)
    2. sourceNode.config?.filename → fallback for file-based sources
    3. `${typeLabel} источник` → generic fallback
    """
    # This is really a documentation test — verifies our understanding
    source_node_card_path = os.path.join(
        os.path.dirname(__file__), '..', 'apps', 'web', 'src', 'components', 'board', 'SourceNodeCard.tsx'
    )
    
    with open(source_node_card_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verify getTitle function exists and reads metadata.name
    assert 'sourceNode.metadata?.name' in content, \
        "SourceNodeCard.getTitle must check metadata.name"
    assert 'config?.filename' in content, \
        "SourceNodeCard.getTitle must fall back to config.filename"


def test_content_node_title_fallback_chain():
    """Document the ContentNodeCard getTitle() fallback chain.
    
    1. contentNode.metadata?.name → primary (set by AI or user)
    2. tables[0].name → fallback to first table name
    3. 'Узел данных' → generic fallback
    """
    content_node_card_path = os.path.join(
        os.path.dirname(__file__), '..', 'apps', 'web', 'src', 'components', 'board', 'ContentNodeCard.tsx'
    )
    
    with open(content_node_card_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert 'metadata?.name' in content, \
        "ContentNodeCard.getTitle must check metadata.name"
    assert 'Узел данных' in content, \
        "ContentNodeCard.getTitle must have 'Узел данных' as final fallback"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
