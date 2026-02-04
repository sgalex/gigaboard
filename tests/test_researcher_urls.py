"""
Тест ResearcherAgent с явными URLs
Проверяет загрузку конкретных страниц
"""
import asyncio
import sys
from pathlib import Path

# Add backend app to path
backend_path = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_path))

from app.services.multi_agent.agents.researcher import ResearcherAgent
from app.services.multi_agent.message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService
from app.core.config import settings


async def test_researcher_with_explicit_urls():
    """Тест загрузки конкретных URLs через ResearcherAgent"""
    
    print("=" * 80)
    print("🧪 RESEARCHER AGENT TEST - Explicit URLs")
    print("=" * 80)
    print()
    
    # URLs из предыдущего теста (те, что были найдены SearchAgent)
    test_urls = [
        "https://github.com/omarabid/rust-companies",
        "https://litslink.com/blog/companies-that-use-rust-language",
        "https://andrewodendaal.com/rust-industry-adoption/",
        "https://kerkour.com/rust-in-production-2021",
        "https://serokell.io/blog/rust-companies"
    ]
    
    print(f"📋 Testing {len(test_urls)} URLs:")
    for i, url in enumerate(test_urls, 1):
        print(f"   {i}. {url}")
    print()
    
    # Initialize services
    print("🚀 Initializing services...")
    message_bus = AgentMessageBus()
    await message_bus.connect()
    
    gigachat = GigaChatService(api_key=settings.GIGACHAT_API_KEY)
    
    researcher = ResearcherAgent(
        message_bus=message_bus,
        gigachat_service=gigachat
    )
    print("✅ ResearcherAgent initialized")
    print()
    
    # Create task with explicit URLs
    task = {
        "urls": test_urls,
        "max_urls": 5,
        "description": "Fetch full content from URLs"
    }
    
    context = {
        "session_id": "test-session-123",
        "task_index": 0,
        "previous_results": {}
    }
    
    print("=" * 80)
    print("🚀 FETCHING URLS")
    print("=" * 80)
    print()
    
    # Execute task
    result = await researcher.process_task(task, context)
    
    print()
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    print()
    
    print(f"Status: {result.get('status')}")
    print(f"Pages fetched: {result.get('pages_fetched', 0)}/{len(test_urls)}")
    print(f"Pages failed: {result.get('pages_failed', 0)}")
    print(f"Total bytes: {result.get('total_content_bytes', 0)}")
    print()
    
    # Show successful pages
    if result.get('pages'):
        print("✅ SUCCESSFUL FETCHES:")
        for page in result['pages']:
            print(f"   • {page['url']}")
            print(f"     Title: {page.get('title', 'N/A')}")
            print(f"     Content length: {len(page.get('content', ''))} chars")
            print(f"     Content preview: {page.get('content', '')[:200]}...")
            print()
    
    # Show errors
    if result.get('errors'):
        print("❌ FAILED FETCHES:")
        for error in result['errors']:
            print(f"   • {error['url']}")
            print(f"     Error: {error.get('error', 'Unknown')}")
            print()
    
    # Cleanup
    await message_bus.disconnect()
    
    print("=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_researcher_with_explicit_urls())
