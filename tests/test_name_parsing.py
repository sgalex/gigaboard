"""Tests for name generation/parsing in WidgetCodex and ContentNode metadata.

Verifies that widget_name is correctly extracted from various LLM response formats,
including markdown-formatted headers, different key names, and edge cases.
"""
import sys
import os
import re
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend'))

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


def _make_agent():
    """Create WidgetCodexAgent without message_bus for testing."""
    return WidgetCodexAgent(message_bus=None, gigachat_service=None)


# ══════════════════════════════════════════════════════════════════
#  WidgetCodex structured response parser — widget_name extraction
# ══════════════════════════════════════════════════════════════════

def test_standard_header_format():
    """Standard header with widget_name, widget_type, description."""
    agent = _make_agent()
    response = """widget_name: Продажи по категориям
widget_type: chart
description: Столбчатая диаграмма продаж

===RENDER_BODY===
console.log('test');

===STYLES===
.chart { color: red; }
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'Продажи по категориям'
    assert result['widget_type'] == 'chart'
    assert result['description'] == 'Столбчатая диаграмма продаж'
    print("✅ test_standard_header_format passed")


def test_markdown_bold_keys():
    """LLM wraps keys in **bold** markdown."""
    agent = _make_agent()
    response = """**widget_name**: Топ-10 товаров
**widget_type**: cards
**description**: Карточки популярных товаров

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'Топ-10 товаров'
    assert result['widget_type'] == 'cards'
    print("✅ test_markdown_bold_keys passed")


def test_markdown_italic_keys():
    """LLM wraps keys in *italic* markdown."""
    agent = _make_agent()
    response = """*widget_name*: KPI Метрики
*widget_type*: kpi
*description*: Ключевые метрики производства

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'KPI Метрики'
    print("✅ test_markdown_italic_keys passed")


def test_backtick_keys():
    """LLM wraps keys in `backticks`."""
    agent = _make_agent()
    response = """`widget_name`: Распределение по регионам
`widget_type`: chart
`description`: Pie chart регионов

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'Распределение по регионам'
    print("✅ test_backtick_keys passed")


def test_list_marker_keys():
    """LLM uses list markers (-, •) before keys."""
    agent = _make_agent()
    response = """- widget_name: Таблица сотрудников
- widget_type: table
- description: Список всех сотрудников

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'Таблица сотрудников'
    assert result['widget_type'] == 'table'
    print("✅ test_list_marker_keys passed")


def test_russian_key_names():
    """LLM uses Russian key names instead of English."""
    agent = _make_agent()
    response = """название: Динамика продаж
тип: chart
описание: График динамики продаж за год

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result.get('widget_name') == 'Динамика продаж'
    assert result.get('widget_type') == 'chart'
    assert result.get('description') == 'График динамики продаж за год'
    print("✅ test_russian_key_names passed")


def test_short_key_aliases():
    """LLM uses 'name' and 'type' instead of 'widget_name' and 'widget_type'."""
    agent = _make_agent()
    response = """name: Обзор заказов
type: table
description: Таблица последних заказов

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result.get('widget_name') == 'Обзор заказов'
    assert result.get('widget_type') == 'table'
    print("✅ test_short_key_aliases passed")


def test_preamble_text_before_headers():
    """LLM adds preamble text before the headers."""
    agent = _make_agent()
    response = """Вот результат визуализации:

widget_name: Воронка продаж
widget_type: chart
description: Воронка конверсии на каждом этапе

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'Воронка продаж'
    print("✅ test_preamble_text_before_headers passed")


def test_quoted_values():
    """LLM wraps values in quotes."""
    agent = _make_agent()
    response = """widget_name: "Аналитика по кварталам"
widget_type: "chart"
description: "Сравнение показателей по кварталам"

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'Аналитика по кварталам'
    print("✅ test_quoted_values passed")


def test_markdown_code_block_wrapper():
    """LLM wraps the whole response in a markdown code block."""
    agent = _make_agent()
    response = """```
widget_name: График температуры
widget_type: chart
description: Температурный график

===RENDER_BODY===
console.log('test');

===STYLES===
.temp { color: blue; }
```"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'График температуры'
    print("✅ test_markdown_code_block_wrapper passed")


def test_numbered_list_keys():
    """LLM uses numbered list for keys."""
    agent = _make_agent()
    response = """1. widget_name: Статистика посещений
2. widget_type: kpi
3. description: Основные метрики

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'Статистика посещений'
    print("✅ test_numbered_list_keys passed")


def test_mixed_bold_and_list():
    """Combined markdown bold + list markers."""
    agent = _make_agent()
    response = """- **widget_name**: Карта клиентов
- **widget_type**: chart
- **description**: Географическое распределение клиентов

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result['widget_name'] == 'Карта клиентов'
    print("✅ test_mixed_bold_and_list passed")


def test_empty_widget_name_fallback():
    """If widget_name is absent, default to 'Widget'."""
    agent = _make_agent()
    response = """widget_type: chart
description: Какой-то график

===RENDER_BODY===
console.log('test');
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    # widget_name not in result, so parsed.get("widget_name", "Widget") should give "Widget"
    assert result.get('widget_name') is None or result.get('widget_name') == ''
    print("✅ test_empty_widget_name_fallback passed")


# ══════════════════════════════════════════════════════════════════
#  ContentNode _generate_content_metadata JSON parsing
# ══════════════════════════════════════════════════════════════════

def _parse_content_metadata(response: str) -> dict:
    """Simulate the JSON parsing logic from content_nodes.py _generate_content_metadata."""
    # First attempt: standard json.loads on first {...} block
    brace_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
    if brace_match:
        try:
            metadata = json.loads(brace_match.group())
            if metadata.get("name") or metadata.get("description"):
                return {
                    "name": metadata.get("name", "")[:100],
                    "description": metadata.get("description", "")[:500]
                }
        except json.JSONDecodeError:
            pass

    # Second attempt: regex for JSON with "name" and "description" (any order)
    json_match = re.search(
        r'\{[^{}]*(?:"name"|"description")[^{}]*(?:"name"|"description")[^{}]*\}',
        response, re.DOTALL,
    )
    if json_match:
        try:
            metadata = json.loads(json_match.group())
            return {
                "name": metadata.get("name", "")[:100],
                "description": metadata.get("description", "")[:500]
            }
        except json.JSONDecodeError:
            pass

    # Fallback: key=value parsing with markdown support
    name_match = re.search(r'[*_`"\']*name[*_`"\']*\s*[:=]\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
    desc_match = re.search(r'[*_`"\']*description[*_`"\']*\s*[:=]\s*["\']([^"\']+)["\']', response, re.IGNORECASE)

    if name_match or desc_match:
        return {
            "name": name_match.group(1)[:100] if name_match else "Fallback",
            "description": desc_match.group(1)[:500] if desc_match else "Fallback"
        }

    return {"name": "", "description": ""}


def test_content_metadata_standard_json():
    """Standard JSON response."""
    response = '{"name": "Группировка по брендам", "description": "Данные сгруппированы по брендам"}'
    result = _parse_content_metadata(response)
    assert result['name'] == 'Группировка по брендам'
    print("✅ test_content_metadata_standard_json passed")


def test_content_metadata_reversed_keys():
    """JSON with description before name."""
    response = '{"description": "Фильтрация по дате", "name": "Данные за 2025"}'
    result = _parse_content_metadata(response)
    assert result['name'] == 'Данные за 2025'
    print("✅ test_content_metadata_reversed_keys passed")


def test_content_metadata_markdown_wrapped():
    """JSON wrapped in markdown code block."""
    response = """```json
{"name": "Топ категории", "description": "Топ-10 категорий по продажам"}
```"""
    result = _parse_content_metadata(response)
    assert result['name'] == 'Топ категории'
    print("✅ test_content_metadata_markdown_wrapped passed")


def test_content_metadata_with_preamble():
    """JSON with preamble text."""
    response = """Вот результат:

{"name": "Анализ клиентов", "description": "Сегментация клиентов по возрасту"}"""
    result = _parse_content_metadata(response)
    assert result['name'] == 'Анализ клиентов'
    print("✅ test_content_metadata_with_preamble passed")


def test_content_metadata_extra_fields():
    """JSON with extra fields beyond name/description."""
    response = '{"name": "Отчёт о продажах", "description": "Сводный отчёт", "type": "report"}'
    result = _parse_content_metadata(response)
    assert result['name'] == 'Отчёт о продажах'
    print("✅ test_content_metadata_extra_fields passed")


def test_content_metadata_key_value_format():
    """Non-JSON key=value format with quotes."""
    response = """name: "Агрегация данных"
description: "Агрегация по категориям и месяцам"
"""
    result = _parse_content_metadata(response)
    assert result['name'] == 'Агрегация данных'
    print("✅ test_content_metadata_key_value_format passed")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing WidgetCodex structured response parser")
    print("=" * 60)
    test_standard_header_format()
    test_markdown_bold_keys()
    test_markdown_italic_keys()
    test_backtick_keys()
    test_list_marker_keys()
    test_russian_key_names()
    test_short_key_aliases()
    test_preamble_text_before_headers()
    test_quoted_values()
    test_markdown_code_block_wrapper()
    test_numbered_list_keys()
    test_mixed_bold_and_list()
    test_empty_widget_name_fallback()

    print()
    print("=" * 60)
    print("Testing ContentNode metadata JSON parsing")
    print("=" * 60)
    test_content_metadata_standard_json()
    test_content_metadata_reversed_keys()
    test_content_metadata_markdown_wrapped()
    test_content_metadata_with_preamble()
    test_content_metadata_extra_fields()
    test_content_metadata_key_value_format()

    print()

    print("=" * 60)
    print("Testing ===KEY=== section markers and multi-line values")
    print("=" * 60)
    test_section_marker_widget_name()
    test_section_marker_all_fields()
    test_description_value_on_next_line()
    test_mixed_section_markers_and_key_value()

    print()
    print("🎉 All tests passed!")


# ══════════════════════════════════════════════════════════════════
#  ===KEY=== section markers and multi-line header values
# ══════════════════════════════════════════════════════════════════


def test_section_marker_widget_name():
    """LLM uses ===widget_name=== section marker instead of 'widget_name: value'."""
    agent = _make_agent()
    response = """===widget_name===
Платформы и аналитические инструменты
===widget_type===
chart
description: Диаграмма сравнения популярности

===RENDER_BODY===
console.log('test');

===STYLES===

===SCRIPTS===
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result.get('widget_name') == 'Платформы и аналитические инструменты'
    assert result.get('widget_type') == 'chart'
    assert result.get('description') == 'Диаграмма сравнения популярности'
    print("✅ test_section_marker_widget_name passed")


def test_section_marker_all_fields():
    """All header fields as ===KEY=== markers."""
    agent = _make_agent()
    response = """===widget_name===
Топ-10 вакансий
===widget_type===
table
===description===
Таблица самых популярных вакансий

===RENDER_BODY===
document.getElementById('chart').innerHTML = '<table></table>';

===STYLES===
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result.get('widget_name') == 'Топ-10 вакансий'
    assert result.get('widget_type') == 'table'
    print("✅ test_section_marker_all_fields passed")


def test_description_value_on_next_line():
    """description: on one line, value on the next line."""
    agent = _make_agent()
    response = """widget_name: Продажи по регионам
widget_type: chart
description:
Столбчатая диаграмма продаж по регионам за 2024 год

===RENDER_BODY===
console.log('hello');

===STYLES===
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result.get('widget_name') == 'Продажи по регионам'
    assert result.get('description') == 'Столбчатая диаграмма продаж по регионам за 2024 год'
    print("✅ test_description_value_on_next_line passed")


def test_mixed_section_markers_and_key_value():
    """Mix of ===KEY=== markers and regular key: value."""
    agent = _make_agent()
    response = """===widget_name===
Динамика зарплат
widget_type: chart
description:
Линейный график изменения зарплат по месяцам

===RENDER_BODY===
window.chartInstance.setOption({});

===STYLES===
.chart { }
"""
    result = agent._parse_structured_response(response)
    assert result is not None
    assert result.get('widget_name') == 'Динамика зарплат'
    assert result.get('widget_type') == 'chart'
    assert result.get('description') == 'Линейный график изменения зарплат по месяцам'
    print("✅ test_mixed_section_markers_and_key_value passed")
