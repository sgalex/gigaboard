"""
Простой тест мультиагентной цепочки: Search → Research → Analyst → Reporter
"""
import asyncio
import sys
from pathlib import Path

# Add backend app to path
backend_path = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker
from app.models.user import User
from app.models.project import Project
from app.models.board import Board
from app.services.multi_agent.engine import MultiAgentEngine
from app.services.multi_agent.orchestrator import MultiAgentOrchestrator


async def test_simple_chain():
    """Тест простой цепочки: Search → Research → Analyst → Reporter"""
    
    print("=" * 80)
    print("🧪 SIMPLE CHAIN TEST: Search → Research → Analyst → Reporter")
    print("=" * 80)
    print()
    
    # Initialize MultiAgentEngine
    print("🚀 Initializing MultiAgentEngine...")
    engine = MultiAgentEngine()
    await engine.initialize()
    print("✅ MultiAgentEngine initialized")
    print()
    
    # Get DB session
    print("💾 Getting database session...")
    async with async_session_maker() as db:
        # Get test user
        print("👤 Getting test user...")
        user = await db.execute(
            "SELECT * FROM users WHERE email = 'test@example.com'"
        )
        user = user.first()
        if not user:
            print("❌ Test user not found")
            return
        user_id = user[0]
        print(f"✅ Using test user: {user_id}")
        print()
        
        # Create test board
        print("📋 Creating test board...")
        project = Project(
            name="Simple Chain Test",
            description="Test Search→Research→Analyst→Reporter",
            owner_id=user_id
        )
        db.add(project)
        await db.flush()
        
        board = Board(
            name="Test Board",
            description="Simple chain test",
            project_id=project.id,
            owner_id=user_id
        )
        db.add(board)
        await db.commit()
        print(f"✅ Test board created: {board.id}")
        print()
        
        # Create orchestrator
        print("🎭 Creating MultiAgentOrchestrator...")
        orchestrator = MultiAgentOrchestrator(
            engine=engine,
            db=db,
            user_id=user_id,
            board_id=board.id
        )
        print("✅ Orchestrator created")
        print()
        
        # Simple user request
        user_request = """
Найди информацию о Python последней версии:
1. Поищи в интернете последнюю стабильную версию Python
2. Извлеки данные из найденных страниц
3. Создай таблицу с версией и датой релиза
4. Визуализируй результат
"""
        
        print("=" * 80)
        print("🚀 EXECUTING SIMPLE CHAIN")
        print("=" * 80)
        print()
        print("📨 User Request:")
        print(user_request)
        print()
        print("=" * 80)
        print()
        
        # Execute workflow
        result_stream = orchestrator.execute_workflow(user_request)
        
        print("📦 Streaming results:")
        async for chunk in result_stream:
            if chunk:
                print(f"   {chunk[:100]}...")
        
        print()
        print("=" * 80)
        print("✅ TEST COMPLETE")
        print("=" * 80)
        
        # Get session results
        session = orchestrator.current_session
        if session:
            print(f"\n📊 Session ID: {session.id}")
            print(f"   Status: {session.status}")
            print(f"   Tasks completed: {session.current_task_index}")
        
        await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(test_simple_chain())
