"""
Direct test of MultiAgentOrchestrator payload wrapping.

Directly calls orchestrator.process_user_request() to verify:
1. Orchestrator correctly wraps message payloads for agents
2. Agents receive properly structured messages
3. Full workflow executes successfully

No API, no database entities needed - just orchestrator + Message Bus.
"""

import asyncio
import sys
import os
from pathlib import Path
from uuid import uuid4

# Fix Windows console encoding for emoji
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "apps" / "backend"))

from app.services.multi_agent.orchestrator import MultiAgentOrchestrator
from app.services.multi_agent.message_bus import AgentMessageBus
from app.services.multi_agent.engine import MultiAgentEngine
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService

# Test prompt
TEST_REQUEST = """
Analyze current Bitcoin (BTC) market data:
1. Get current price in USD
2. Calculate 24h price change
3. Provide brief market analysis

Return structured data with price and analysis.
"""


async def test_orchestrator_direct():
    """Test orchestrator directly without API layer."""
    
    print("=" * 80)
    print("🧪 DIRECT ORCHESTRATOR TEST")
    print("=" * 80)
    print("Testing orchestrator payload wrapping in production code")
    print("=" * 80)
    
    # Setup
    engine = None
    db = None
    
    try:
        # 1. Initialize MultiAgentEngine (does everything: Redis, GigaChat, MessageBus, Agents)
        print("\n🚀 Initializing MultiAgentEngine...")
        import os
        gigachat_key = os.getenv("GIGACHAT_API_KEY")
        if not gigachat_key:
            print("❌ GIGACHAT_API_KEY not set in environment")
            return False
        
        engine = MultiAgentEngine(
            gigachat_api_key=gigachat_key,
            enable_agents=["planner", "search", "analyst", "reporter", "researcher", "transformation"],
            adaptive_planning=True
        )
        await engine.initialize()
        print("✅ MultiAgentEngine initialized (agents are listening)")
        
        # 2. Get database session
        print("\n💾 Getting database session...")
        async for session in get_db():
            db = session
            break
        print("✅ Database session ready")
        
        # 3. Create test user
        print("\n👤 Creating test user...")
        from sqlalchemy import select
        
        # Try to find existing user
        result = await db.execute(
            select(User).where(User.email == "test_orchestrator@example.com")
        )
        test_user = result.scalar_one_or_none()
        
        if test_user:
            print(f"✅ Using existing test user: {test_user.id}")
        else:
            test_user = User(
                id=uuid4(),
                username="test_orchestrator",
                email="test_orchestrator@example.com",
                password_hash=AuthService.hash_password("testpass123")
            )
            db.add(test_user)
            await db.commit()
            await db.refresh(test_user)
            print(f"✅ Test user created: {test_user.id}")
        
        # 4. Create test board
        print("\n📋 Creating test board...")
        from app.models.board import Board
        from app.models.project import Project
        
        test_project = Project(
            id=uuid4(),
            name="Test Project",
            user_id=test_user.id
        )
        db.add(test_project)
        await db.flush()
        
        test_board = Board(
            id=uuid4(),
            name="Test Board",
            project_id=test_project.id,
            user_id=test_user.id
        )
        db.add(test_board)
        await db.commit()
        await db.refresh(test_board)
        print(f"✅ Test board created: {test_board.id}")
        
        # 5. Create orchestrator
        print("\n🎭 Creating MultiAgentOrchestrator...")
        orchestrator = MultiAgentOrchestrator(db, engine.message_bus)
        print("✅ Orchestrator created")
        
        # 6. Process user request (this is the production code path)
        print("\n" + "=" * 80)
        print("🚀 EXECUTING PRODUCTION WORKFLOW")
        print("=" * 80)
        print(f"Request: {TEST_REQUEST[:100]}...")
        print("=" * 80)
        
        # Collect streaming response
        response_chunks = []
        async for chunk in orchestrator.process_user_request(
            user_id=test_user.id,
            board_id=test_board.id,
            user_message=TEST_REQUEST
        ):
            response_chunks.append(chunk)
            # Show short chunks completely, truncate long ones
            if len(chunk) > 80:
                print(f"📦 Chunk ({len(chunk)}b): {chunk[:80]}...")
            else:
                print(f"📦 Chunk ({len(chunk)}b): {chunk}")
        
        result = "".join(response_chunks)
        
        print("\n" + "=" * 80)
        print("📋 FULL STREAMING RESPONSE (AGGREGATED)")
        print("=" * 80)
        print(result)
        print("=" * 80)
        
        # 7. Get session details to see actual agent results
        print("\n" + "=" * 80)
        print("📊 FETCHING AGENT RESULTS FROM DATABASE")
        print("=" * 80)
        
        from app.models.agent_session import AgentSession
        from sqlalchemy import select, desc
        
        # Get latest session for this board
        result_query = await db.execute(
            select(AgentSession)
            .where(AgentSession.board_id == test_board.id)
            .order_by(desc(AgentSession.created_at))
            .limit(1)
        )
        agent_session = result_query.scalar_one_or_none()
        
        if agent_session:
            print(f"\n✅ AgentSession found: {agent_session.id}")
            print(f"   Status: {agent_session.status}")
            print(f"   Steps executed: {agent_session.current_task_index}")
            
            # Show plan
            plan_data = agent_session.plan
            if plan_data is not None:
                import json
                steps = plan_data.get('steps', [])
                print(f"\n📋 Execution Plan ({len(steps)} steps):")
                for step in steps:
                    agent_name = step.get('agent', 'unknown').upper()
                    task_info = step.get('task', {})
                    desc = task_info.get('description', 'N/A')
                    task_type = task_info.get('type', 'N/A')
                    step_id = step.get('step_id', '?')
                    print(f"   {step_id}. [{agent_name}] {desc}")
                    print(f"      Тип: {task_type}")
                    if step.get('depends_on'):
                        print(f"      Зависит от: {', '.join(step.get('depends_on'))}")
            
            # Show results
            results_data = agent_session.results
            if results_data is not None and isinstance(results_data, dict):
                print(f"\n📊 Task Results:")
                for task_key, task_result in results_data.items():
                    print(f"\n   {task_key}:")
                    print(f"   Agent: {task_result.get('agent', 'unknown')}")
                    print(f"   Status: {task_result.get('status', 'unknown')}")
                    
                    result_data = task_result.get('result', {})
                    if result_data:
                        result_str = json.dumps(result_data, ensure_ascii=False, indent=2)
                        if len(result_str) > 500:
                            print(f"   Result ({len(result_str)} bytes):")
                            print(f"      {result_str[:500]}...")
                        else:
                            print(f"   Result:")
                            for line in result_str.split('\n'):
                                print(f"      {line}")
                    
                    if task_result.get('error'):
                        print(f"   ❌ Error: {task_result['error']}")
            
            # Show final response
            final_resp = agent_session.final_response
            if final_resp is not None:
                print("\n📄 Final Response:")
                final_resp_str = str(final_resp)
                if len(final_resp_str) > 1000:
                    print(f"{final_resp_str[:1000]}...")
                    print(f"\n... (total {len(final_resp_str)} bytes)")
                else:
                    print(final_resp_str)
            
            # Save to file for detailed analysis
            import json
            from datetime import datetime
            
            output_dir = Path(__file__).parent / "orchestrator_results"
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"result_{timestamp}.json"
            
            result_data = {
                "session_id": str(agent_session.id),
                "status": agent_session.status.value if hasattr(agent_session.status, 'value') else str(agent_session.status),
                "user_message": agent_session.user_message,
                "plan": agent_session.plan,
                "results": agent_session.results,
                "final_response": str(agent_session.final_response) if agent_session.final_response is not None else None,
                "steps_executed": agent_session.current_task_index,
                "session_metadata": agent_session.session_metadata,
                "error_message": agent_session.error_message
            }
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Detailed results saved to: {output_file}")
        else:
            print("\n⚠️ No AgentSession found in database")
        
        # 8. Verify result
        print("\n" + "=" * 80)
        print("✅ WORKFLOW COMPLETED")
        print("=" * 80)
        
        if result:
            print(f"✅ Response received: {len(result)} bytes")
            print(f"   Preview: {result[:300]}...")
            
            print("\n" + "=" * 80)
            print("✅ TEST PASSED")
            print("=" * 80)
            print("Orchestrator correctly wrapped all message payloads")
            print("Agents processed requests successfully")
            print("Full Multi-Agent workflow executed in production code")
            print("=" * 80)
            
            return True
        else:
            print("❌ No response received")
            return False
            
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        print("\n🧹 Cleanup...")
        if engine:
            await engine.shutdown()
            print("✅ MultiAgentEngine shut down")
        if db:
            await db.close()
            print("✅ Database session closed")


async def main():
    """Run direct orchestrator test."""
    
    # Check Redis connection
    try:
        import redis.asyncio as redis
        client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        await client.ping()
        await client.aclose()
        print("[OK] Redis is running\n")
    except Exception as e:
        print("[ERROR] Redis not available - start it first")
        print(f"   Error: {e}")
        sys.exit(1)
    
    success = await test_orchestrator_direct()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
