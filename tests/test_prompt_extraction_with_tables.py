"""
Тест извлечения данных из SourceNode (prompt) с получением структурированных таблиц
"""

import asyncio
import sys
import os
import json
from uuid import uuid4

# Добавляем путь к backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.extractors.prompt_extractor import PromptExtractor
from app.models import SourceNode, SourceType


async def test_prompt_extraction():
    """Тест извлечения через prompt с получением таблиц"""
    print("\n" + "="*80)
    print("🧪 PROMPT EXTRACTION TEST (с таблицами)")
    print("="*80 + "\n")
    
    # Mock SourceNode
    source_node = type('obj', (object,), {
        'id': uuid4(),
        'board_id': uuid4(),
        'created_by': uuid4(),
        'source_type': SourceType.PROMPT,
        'config': {
            "prompt": """Проанализируй популярность языка Rust:
1. Найди топ-5 компаний использующих Rust
2. Найди бенчмарки сравнения Rust vs Go
3. Создай 2 таблицы:
   - companies: name, use_case, year_adopted
   - benchmarks: test_name, rust_ms, go_ms, speedup

Верни structured JSON с таблицами."""
        }
    })()
    
    print(f"📝 Prompt: {source_node.config['prompt'][:100]}...\n")
    
    # Получаем зависимости
    from dotenv import load_dotenv
    load_dotenv()
    
    # Initialize services
    print("🔧 Initializing services...")
    
    # GigaChat Service
    from app.services.gigachat_service import GigaChatService
    api_key = os.getenv("GIGACHAT_API_KEY")
    if not api_key:
        print("❌ GIGACHAT_API_KEY not found")
        return
    gigachat_service = GigaChatService(api_key=api_key)
    
    # Multi-Agent System
    from app.services.multi_agent.engine import MultiAgentEngine
    import redis.asyncio as redis_async
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis = await redis_async.from_url(redis_url, decode_responses=True)
    
    engine = MultiAgentEngine(
        gigachat_api_key=api_key
    )
    await engine.initialize()
    
    # Orchestrator
    from app.services.multi_agent.orchestrator import MultiAgentOrchestrator
    
    orchestrator = MultiAgentOrchestrator(
        gigachat_service=gigachat_service,
        multi_agent_engine=engine
    )
    
    print("✅ Services initialized\n")
    
    # Extract data
    extractor = PromptExtractor()
    
    print("🚀 Starting extraction...\n")
    
    result = await extractor.extract(
        config=source_node.config,
        params={
            "orchestrator": orchestrator,
            "source": source_node
        }
    )
    
    # Анализ результата
    print("\n" + "="*80)
    print("📊 EXTRACTION RESULT")
    print("="*80)
    
    if result.errors:
        print(f"\n❌ Errors: {result.errors}")
    else:
        print("\n✅ Extraction successful!")
    
    print(f"\n📝 Text content length: {len(result.text)} chars")
    print(f"📋 Tables extracted: {len(result.tables)}")
    
    if result.text:
        print(f"\n📄 Text preview (first 500 chars):")
        print("-" * 80)
        print(result.text[:500])
        print("..." if len(result.text) > 500 else "")
    
    if result.tables:
        print(f"\n📊 Tables:")
        for i, table in enumerate(result.tables, 1):
            print(f"\n   Table {i}: {table['name']}")
            print(f"      Columns: {table['columns']}")
            print(f"      Rows: {table['row_count']}")
            print(f"      Sample (first 3 rows):")
            for row in table['rows'][:3]:
                print(f"         {row}")
    else:
        print("\n⚠️ NO TABLES EXTRACTED!")
        print("   Expected: companies table, benchmarks table")
        print("   This is the issue we need to fix!")
    
    # Проверяем metadata
    print(f"\n📋 Metadata:")
    for key, value in result.metadata.items():
        print(f"   {key}: {value}")
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80 + "\n")
    
    # Cleanup
    await redis.close()


if __name__ == "__main__":
    asyncio.run(test_prompt_extraction())
