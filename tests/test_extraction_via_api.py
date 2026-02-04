"""
Тест извлечения таблиц через real API
"""

import requests
import json
import time

# Backend URL
BASE_URL = "http://localhost:8000/api/v1"

# Prompt с гарантированными табличными данными
TEST_PROMPT = """Проанализируй топ-3 языка программирования (Python, Rust, JavaScript) по следующим параметрам:
1. Год создания
2. Основная область применения
3. Рейтинг популярности (1-10)
4. Производительность (low/medium/high)

Создай таблицу comparison_table со структурой:
- language (название языка)
- year (год создания)
- domain (область применения)
- rating (рейтинг 1-10)
- performance (производительность)

Верни ОБЯЗАТЕЛЬНО в формате JSON с полями:
- text: описание анализа
- tables: массив с одной таблицей comparison_table
"""

def main():
    print("\n" + "="*80)
    print("🧪 API EXTRACTION TEST")
    print("="*80)
    
    # 1. Get or create SourceNode
    print("\n1️⃣ Creating SourceNode...")
    
    # Get boards
    response = requests.get(f"{BASE_URL}/boards")
    if response.status_code != 200:
        print(f"❌ Failed to get boards: {response.status_code}")
        return
    
    boards = response.json()
    if not boards:
        print("❌ No boards found")
        return
    
    board_id = boards[0]["id"]
    print(f"   ✅ Using board: {board_id}")
    
    # Get existing SourceNodes
    response = requests.get(f"{BASE_URL}/source-nodes/board/{board_id}")
    source_nodes = response.json()
    
    # Find or create test SourceNode
    test_source = None
    for sn in source_nodes:
        if sn.get("source_type") == "prompt":
            test_source = sn
            print(f"   ✅ Using existing SourceNode: {sn['id']}")
            break
    
    if not test_source:
        print("   ⚠️ No prompt SourceNode found, create one manually via UI")
        return
    
    source_id = test_source["id"]
    
    # 2. Trigger extraction
    print(f"\n2️⃣ Triggering extraction...")
    print(f"   📝 Prompt: {TEST_PROMPT[:100]}...\n")
    
    response = requests.post(
        f"{BASE_URL}/source-nodes/extract",
        json={
            "source_id": source_id,
            "params": {}
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Extraction failed: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    content_node_id = result.get("content_node_id")
    
    print(f"   ✅ Extraction triggered, ContentNode ID: {content_node_id}\n")
    
    # 3. Wait a bit for multi-agent processing
    print("3️⃣ Waiting for multi-agent processing (15s)...")
    time.sleep(15)
    
    # 4. Check ContentNode
    print("\n4️⃣ Fetching ContentNode...")
    response = requests.get(f"{BASE_URL}/content-nodes/{content_node_id}")
    
    if response.status_code != 200:
        print(f"❌ Failed to get ContentNode: {response.status_code}")
        return
    
    content_node = response.json()
    
    # 5. Analyze result
    print("\n" + "="*80)
    print("📊 EXTRACTION RESULT")
    print("="*80)
    
    content = content_node.get("content", {})
    
    text = content.get("text", "")
    tables = content.get("tables", [])
    
    print(f"\n📝 Text content length: {len(text)} chars")
    print(f"📋 Tables extracted: {len(tables)}")
    
    if text:
        print(f"\n📄 Text preview (first 500 chars):")
        print("-" * 80)
        print(text[:500])
        print("..." if len(text) > 500 else "")
    
    if tables:
        print(f"\n📊 Tables:")
        for i, table in enumerate(tables, 1):
            print(f"\n   Table {i}: {table.get('name', 'unnamed')}")
            print(f"      Columns: {table.get('columns', [])}")
            print(f"      Row count: {len(table.get('rows', []))}")
            print(f"      Sample (first 3 rows):")
            for row in table.get('rows', [])[:3]:
                print(f"         {row}")
    else:
        print("\n⚠️ NO TABLES EXTRACTED!")
        print("   Expected: comparison_table with Python, Rust, JavaScript")
    
    # 6. Summary
    print("\n" + "="*80)
    if tables:
        print("✅ TEST PASSED - Tables extracted successfully!")
    else:
        print("❌ TEST FAILED - No tables found")
        print("\n   Check backend logs for:")
        print("   - '📊 Found tables array: type=..., length=...'")
        print("   - '✅ Extracted table: ...'")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
