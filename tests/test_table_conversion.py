"""
Простой тест: PromptExtractor должен извлекать таблицы из multi-agent результатов
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

# Проверка логики без запуска multi-agent
def test_table_conversion():
    """Тест _convert_to_table метода"""
    from app.services.extractors.prompt_extractor import PromptExtractor
    
    extractor = PromptExtractor()
    
    # Test 1: List of dicts
    data1 = [
        {"name": "Dropbox", "use_case": "file sync"},
        {"name": "Discord", "use_case": "real-time messaging"}
    ]
    
    table1 = extractor._convert_to_table("companies", data1)
    
    print("="*80)
    print("🧪 TEST 1: List of dicts → Table")
    print("="*80)
    print(f"Input: {data1}")
    print(f"\nOutput:")
    if table1:
        print(f"  ✅ Table name: {table1['name']}")
        print(f"  ✅ Columns: {table1['columns']}")
        print(f"  ✅ Rows: {table1['row_count']}")
        print(f"  ✅ Sample rows: {table1['rows'][:2]}")
    else:
        print("  ❌ No table generated")
    
    # Test 2: Performance comparison
    data2 = [
        {"language": "Rust", "value": 9.8},
        {"language": "Go", "value": 8.5}
    ]
    
    table2 = extractor._convert_to_table("benchmarks", data2)
    
    print("\n" + "="*80)
    print("🧪 TEST 2: Performance data → Table")
    print("="*80)
    print(f"Input: {data2}")
    print(f"\nOutput:")
    if table2:
        print(f"  ✅ Table name: {table2['name']}")
        print(f"  ✅ Columns: {table2['columns']}")
        print(f"  ✅ Rows: {table2['row_count']}")
    else:
        print("  ❌ No table generated")
    
    print("\n" + "="*80)
    print("✅ TESTS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    test_table_conversion()
