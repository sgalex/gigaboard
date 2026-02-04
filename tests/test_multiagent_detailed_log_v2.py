"""
Тест для создания детального MD-лога работы Multi-Agent системы.
На основе test_orchestrator_direct.py с добавлением подробного логирования.
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from datetime import datetime
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
from app.services.multi_agent.engine import MultiAgentEngine
from app.core.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.board import Board
from app.models.agent_session import AgentSession
from app.services.auth_service import AuthService
from sqlalchemy import select
from sqlalchemy.sql import desc


# Test request - Deep Research Task with Search
TEST_REQUEST = """
Проведи глубокое исследование текущего состояния языка программирования Rust:

1. Найди информацию о последней стабильной версии Rust и её ключевых особенностях
2. Определи топ-5 самых популярных Rust-фреймворков по количеству GitHub stars
3. Проанализируй тренды adoption Rust в индустрии за последний год
4. Сравни производительность Rust с Go и C++ на основе доступных бенчмарков
5. Составь список крупных компаний, использующих Rust в production

Результат должен включать:
- Сводную таблицу с версиями и датами релизов
- Рейтинг фреймворков с описанием их назначения
- Анализ трендов с конкретными метриками
- Выводы о перспективах Rust в 2026 году

Используй поиск для нахождения актуальных источников данных.
"""


async def test_with_detailed_log():
    """Тест с детальным логированием в MD файл."""
    
    print("=" * 80)
    print("🧪 MULTI-AGENT DETAILED LOGGING TEST")
    print("=" * 80)
    
    # Prepare log storage
    log_lines = []
    start_time = datetime.now()
    
    def log(msg: str):
        """Helper to log both to console and MD file."""
        print(msg)
        log_lines.append(msg)
    
    engine = None
    db = None
    
    try:
        # 1. Initialize MultiAgentEngine
        log("\n🚀 Initializing MultiAgentEngine...")
        gigachat_key = os.getenv("GIGACHAT_API_KEY")
        if not gigachat_key:
            log("❌ GIGACHAT_API_KEY not set")
            return False
        
        engine = MultiAgentEngine(
            gigachat_api_key=gigachat_key,
            enable_agents=["planner", "search", "analyst", "reporter", "researcher", "transformation"],
            adaptive_planning=True
        )
        await engine.initialize()
        log("✅ MultiAgentEngine initialized (agents listening)")
        
        # 2. Get database session
        log("\n💾 Getting database session...")
        async for session in get_db():
            db = session
            break
        log("✅ Database session ready")
        
        # 3. Get or create test user
        log("\n👤 Getting test user...")
        result = await db.execute(
            select(User).where(User.email == "test_log@example.com")
        )
        test_user = result.scalar_one_or_none()
        
        if not test_user:
            test_user = User(
                id=uuid4(),
                username="test_log",
                email="test_log@example.com",
                password_hash=AuthService.hash_password("testpass123")
            )
            db.add(test_user)
            await db.commit()
            await db.refresh(test_user)
            log(f"✅ Test user created: {test_user.id}")
        else:
            log(f"✅ Using existing test user: {test_user.id}")
        
        # 4. Create test project and board
        log("\n📋 Creating test project and board...")
        test_project = Project(
            id=uuid4(),
            name="Test Project for Detailed Log",
            user_id=test_user.id
        )
        db.add(test_project)
        await db.flush()
        
        test_board = Board(
            id=uuid4(),
            name="Test Board for Detailed Log",
            project_id=test_project.id,
            user_id=test_user.id
        )
        db.add(test_board)
        await db.commit()
        await db.refresh(test_board)
        log(f"✅ Test board created: {test_board.id}")
        
        # 5. Create orchestrator
        log("\n🎭 Creating MultiAgentOrchestrator...")
        orchestrator = MultiAgentOrchestrator(db, engine.message_bus)
        log("✅ Orchestrator created")
        
        # 6. Process request
        log("\n" + "=" * 80)
        log("🚀 EXECUTING MULTI-AGENT WORKFLOW")
        log("=" * 80)
        log(f"\n📨 User Request:\n{TEST_REQUEST}")
        log("=" * 80)
        
        # Collect streaming response
        response_chunks = []
        async for chunk in orchestrator.process_user_request(
            user_id=test_user.id,
            board_id=test_board.id,
            user_message=TEST_REQUEST
        ):
            response_chunks.append(chunk)
            # Log streaming chunks
            if len(chunk) > 100:
                log(f"📦 Stream chunk ({len(chunk)}b): {chunk[:100]}...")
            else:
                log(f"📦 Stream chunk: {chunk}")
        
        full_response = "".join(response_chunks)
        
        log("\n" + "=" * 80)
        log("✅ STREAMING COMPLETE")
        log("=" * 80)
        
        # 7. Get AgentSession from database to see detailed results
        log("\n📊 FETCHING AGENT SESSION DATA...")
        
        result_query = await db.execute(
            select(AgentSession)
            .where(AgentSession.board_id == test_board.id)
            .order_by(desc(AgentSession.created_at))
            .limit(1)
        )
        agent_session = result_query.scalar_one_or_none()
        
        if not agent_session:
            log("❌ AgentSession not found!")
            return False
        
        log(f"\n✅ AgentSession found: {agent_session.id}")
        log(f"   Status: {agent_session.status}")
        log(f"   Current task: {agent_session.current_task_index}")
        
        # Extract data for MD file
        plan_data = agent_session.plan
        results_data = agent_session.results
        final_response_data = agent_session.final_response
        
        # 8. Create detailed MD log
        log("\n📝 Creating detailed Markdown log...")
        
        md_lines = []
        md_lines.append("# 🤖 Multi-Agent System - Detailed Execution Log\n")
        md_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        md_lines.append(f"**Session ID:** `{agent_session.id}`\n")
        md_lines.append(f"**Status:** {agent_session.status}\n")
        execution_time = (datetime.now() - start_time).total_seconds()
        md_lines.append(f"**Total Execution Time:** {execution_time:.2f}s\n")
        md_lines.append("\n---\n\n")
        
        # User Request
        md_lines.append("## 📨 User Request\n\n")
        md_lines.append("```\n")
        md_lines.append(TEST_REQUEST)
        md_lines.append("\n```\n\n")
        md_lines.append("---\n\n")
        
        # Execution Plan
        if plan_data:
            md_lines.append("## 📋 Execution Plan (from PlannerAgent)\n\n")
            steps = plan_data.get('steps', [])
            md_lines.append(f"**Total Steps:** {len(steps)}\n\n")
            
            for i, step in enumerate(steps, 1):
                agent_name = step.get('agent', 'unknown').upper()
                task_info = step.get('task', {})
                task_desc = task_info.get('description', 'N/A')
                task_type = task_info.get('type', 'N/A')
                step_id = step.get('step_id', f'step_{i}')
                depends_on = step.get('depends_on', [])
                
                md_lines.append(f"### Step {i}: `{step_id}`\n\n")
                md_lines.append(f"- **Agent:** {agent_name}\n")
                md_lines.append(f"- **Task Type:** `{task_type}`\n")
                md_lines.append(f"- **Description:** {task_desc}\n")
                if depends_on:
                    md_lines.append(f"- **Depends On:** {', '.join(depends_on)}\n")
                
                # Show task parameters
                params = task_info.get('parameters', {})
                if params:
                    md_lines.append(f"\n**Parameters:**\n")
                    md_lines.append("```json\n")
                    md_lines.append(json.dumps(params, indent=2, ensure_ascii=False))
                    md_lines.append("\n```\n")
                
                md_lines.append("\n")
            
            # Full plan JSON
            md_lines.append("<details>\n<summary>📄 Full Plan JSON (expand)</summary>\n\n")
            md_lines.append("```json\n")
            md_lines.append(json.dumps(plan_data, indent=2, ensure_ascii=False))
            md_lines.append("\n```\n</details>\n\n")
            md_lines.append("---\n\n")
        
        # Task Execution Results
        if results_data and isinstance(results_data, dict):
            md_lines.append("## 🔬 Task Execution Results\n\n")
            
            for task_key in sorted(results_data.keys()):
                task_result = results_data[task_key]
                
                md_lines.append(f"### {task_key}\n\n")
                md_lines.append(f"- **Agent:** {task_result.get('agent', 'unknown')}\n")
                md_lines.append(f"- **Status:** {task_result.get('status', 'unknown')}\n")
                
                # Show execution time if available
                if 'execution_time_ms' in task_result:
                    md_lines.append(f"- **Execution Time:** {task_result['execution_time_ms']}ms\n")
                
                # Show error if any
                if task_result.get('error'):
                    md_lines.append(f"\n❌ **Error:** {task_result['error']}\n")
                
                # Show result data
                result_info = task_result.get('result', {})
                if result_info:
                    md_lines.append(f"\n**Result Data:**\n\n")
                    md_lines.append("<details>\n<summary>📊 View Result (expand)</summary>\n\n")
                    md_lines.append("```json\n")
                    md_lines.append(json.dumps(result_info, indent=2, ensure_ascii=False))
                    md_lines.append("\n```\n</details>\n\n")
                
                md_lines.append("\n")
            
            md_lines.append("---\n\n")
        
        # Critic Validation (if present)
        # Note: Critic data might be embedded in task results
        md_lines.append("## 🔍 Critic Validation\n\n")
        md_lines.append("*(Critic validation is performed by orchestrator internally)*\n\n")
        md_lines.append("The orchestrator uses CriticAgent to validate each task result:\n")
        md_lines.append("- Checks if result meets expected outcome\n")
        md_lines.append("- Validates confidence threshold (>= 70%)\n")
        md_lines.append("- Can trigger replanning if validation fails\n\n")
        md_lines.append("---\n\n")
        
        # Final Response
        md_lines.append("## ✅ Final Response to User\n\n")
        if final_response_data:
            md_lines.append("```\n")
            md_lines.append(str(final_response_data))
            md_lines.append("\n```\n\n")
        else:
            md_lines.append("```\n")
            md_lines.append(full_response)
            md_lines.append("\n```\n\n")
        
        md_lines.append("---\n\n")
        
        # Streaming Output
        md_lines.append("## 📡 Streaming Output (Raw)\n\n")
        md_lines.append("<details>\n<summary>📺 View Full Streaming Log (expand)</summary>\n\n")
        md_lines.append("```\n")
        md_lines.append("\n".join(log_lines))
        md_lines.append("\n```\n</details>\n\n")
        
        # Save MD file
        log_dir = project_root / "multiagent_logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_file = log_dir / f"detailed_log_{timestamp}.md"
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.writelines(md_lines)
        
        log(f"\n✅ Detailed Markdown log saved to: {md_file}")
        log(f"📊 Log contains {len(md_lines)} lines")
        
        return True
        
    except Exception as e:
        log(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if engine:
            await engine.shutdown()
        if db:
            await db.close()


if __name__ == "__main__":
    success = asyncio.run(test_with_detailed_log())
    sys.exit(0 if success else 1)
