"""
Тест для создания детального лога работы Multi-Agent системы.
Перехватывает все промпты, промежуточные результаты, работу Critic и сохраняет в MD файл.
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from uuid import uuid4, UUID

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
from app.services.auth_service import AuthService
from sqlalchemy import select


class DetailedLogger:
    """Собирает детальный лог работы Multi-Agent системы."""
    
    def __init__(self):
        self.logs = []
        self.start_time = datetime.now()
        
    def log_step(self, step_type: str, agent: str, title: str, data: dict):
        """Добавить шаг в лог."""
        self.logs.append({
            "type": step_type,
            "agent": agent,
            "title": title,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": int((datetime.now() - self.start_time).total_seconds() * 1000)
        })
        
    def save_to_markdown(self, filepath: str):
        """Сохранить лог в Markdown файл."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# 🤖 Multi-Agent System - Detailed Execution Log\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Total Execution Time:** {self.logs[-1]['elapsed_ms']}ms\n\n")
            f.write("---\n\n")
            
            for log in self.logs:
                f.write(f"## [{log['elapsed_ms']}ms] {log['type'].upper()}: {log['title']}\n\n")
                f.write(f"**Agent:** `{log['agent']}`  \n")
                f.write(f"**Timestamp:** {log['timestamp']}\n\n")
                
                # Вывод данных
                if log['type'] == 'user_request':
                    f.write("### User Request\n\n")
                    f.write(f"```\n{log['data']['request']}\n```\n\n")
                    
                elif log['type'] == 'plan_created':
                    f.write("### Execution Plan\n\n")
                    f.write("<details>\n<summary>📋 Plan JSON (expand)</summary>\n\n")
                    f.write(f"```json\n{json.dumps(log['data']['plan'], indent=2, ensure_ascii=False)}\n```\n\n")
                    f.write("</details>\n\n")
                    f.write(f"**Steps:** {log['data']['steps_count']}\n\n")
                    
                elif log['type'] == 'task_execution':
                    f.write("### Task Details\n\n")
                    f.write(f"- **Task Index:** {log['data']['task_index']}\n")
                    f.write(f"- **Description:** {log['data']['description']}\n")
                    if 'parameters' in log['data'] and log['data']['parameters']:
                        f.write(f"- **Parameters:** `{log['data']['parameters']}`\n")
                    f.write("\n")
                    
                elif log['type'] == 'agent_prompt':
                    f.write("### Prompt Sent to Agent\n\n")
                    f.write("<details>\n<summary>💬 Full Prompt (expand)</summary>\n\n")
                    f.write(f"```json\n{json.dumps(log['data']['prompt'], indent=2, ensure_ascii=False)}\n```\n\n")
                    f.write("</details>\n\n")
                    
                elif log['type'] == 'agent_response':
                    f.write("### Agent Response\n\n")
                    f.write(f"**Execution Time:** {log['data'].get('execution_time_ms', 0)}ms\n\n")
                    f.write("<details>\n<summary>📤 Response Data (expand)</summary>\n\n")
                    f.write(f"```json\n{json.dumps(log['data']['response'], indent=2, ensure_ascii=False)}\n```\n\n")
                    f.write("</details>\n\n")
                    
                elif log['type'] == 'critic_validation':
                    f.write("### Critic Validation\n\n")
                    f.write(f"- **Valid:** {'✅ YES' if log['data']['valid'] else '❌ NO'}\n")
                    f.write(f"- **Confidence:** {log['data']['confidence']:.1%}\n")
                    if log['data'].get('issues'):
                        f.write(f"- **Issues:** {', '.join(log['data']['issues'])}\n")
                    f.write("\n")
                    
                elif log['type'] == 'final_response':
                    f.write("### Final Response to User\n\n")
                    f.write("```\n")
                    f.write(log['data']['response'])
                    f.write("\n```\n\n")
                    
                f.write("---\n\n")


# Test request
TEST_REQUEST = """
Analyze current Bitcoin (BTC) market data:
1. Get current price in USD
2. Calculate 24h price change
3. Provide brief market analysis

Return structured data with price and analysis.
"""


async def test_with_detailed_logging():
    """Запуск теста с детальным логированием."""
    
    print("=" * 80)
    print("🧪 MULTI-AGENT DETAILED LOGGING TEST")
    print("=" * 80)
    
    engine = None
    db = None
    detailed_logger = DetailedLogger()
    
    try:
        # 1. Initialize MultiAgentEngine
        print("\n🚀 Initializing MultiAgentEngine...")
        gigachat_key = os.getenv("GIGACHAT_API_KEY")
        if not gigachat_key:
            print("❌ GIGACHAT_API_KEY not set")
            return False
        
        engine = MultiAgentEngine(
            gigachat_api_key=gigachat_key,
            enable_agents=["planner", "search", "analyst", "reporter", "researcher", "transformation"],
            adaptive_planning=True
        )
        await engine.initialize()
        print("✅ MultiAgentEngine initialized")
        
        # 2. Get database session
        print("\n💾 Getting database session...")
        async for session in get_db():
            db = session
            break
        print("✅ Database session ready")
        
        # 3. Get or create test user
        print("\n👤 Getting test user...")
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
        print(f"✅ Test user: {test_user.id}")
        
        # 4. Create orchestrator
        print("\n🎭 Creating orchestrator...")
        orchestrator = MultiAgentOrchestrator(db, engine.message_bus)
        print("✅ Orchestrator ready")
        
        # 5. Log initial request
        detailed_logger.log_step(
            "user_request",
            "system",
            "User Request Received",
            {"request": TEST_REQUEST}
        )
        
        # 6. Monkey-patch orchestrator methods to log everything
        print("\n🔌 Installing logging hooks...")
        
        # Wrap _request_plan
        original_request_plan = orchestrator._request_plan
        async def logged_request_plan(session_id, user_message, board_id=None, selected_node_ids=None):
            result = await original_request_plan(session_id, user_message, board_id, selected_node_ids)
            detailed_logger.log_step(
                "plan_created",
                "PlannerAgent",
                "Execution Plan Created",
                {
                    "plan": result,
                    "steps_count": len(result.get("steps", []))
                }
            )
            return result
        orchestrator._request_plan = logged_request_plan
        
        # Wrap _execute_task
        original_execute_task = orchestrator._execute_task
        async def logged_execute_task(session_id, task_index, task, previous_results=None):
            # Log task start
            detailed_logger.log_step(
                "task_execution",
                task.get("assigned_to", "unknown"),
                f"Task {task_index}: {task.get('description', 'No description')[:50]}...",
                {
                    "task_index": task_index,
                    "description": task.get("description", ""),
                    "parameters": task.get("parameters", {}),
                    "assigned_to": task.get("assigned_to", "unknown")
                }
            )
            
            # Log prompt (reconstruct from task)
            detailed_logger.log_step(
                "agent_prompt",
                task.get("assigned_to", "unknown"),
                f"Prompt for Task {task_index}",
                {
                    "prompt": {
                        "task": task,
                        "previous_results": previous_results
                    }
                }
            )
            
            # Execute
            start_time = datetime.now()
            result = await original_execute_task(session_id, task_index, task, previous_results)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log response
            detailed_logger.log_step(
                "agent_response",
                task.get("assigned_to", "unknown"),
                f"Response from Task {task_index}",
                {
                    "response": result,
                    "execution_time_ms": int(execution_time)
                }
            )
            
            # Log critic validation (if present in result)
            if "validation" in result:
                detailed_logger.log_step(
                    "critic_validation",
                    "CriticAgent",
                    f"Validation for Task {task_index}",
                    result["validation"]
                )
            
            return result
        orchestrator._execute_task = logged_execute_task
        
        print("✅ Logging hooks installed")
        
        # 7. Process request
        print("\n" + "=" * 80)
        print("📨 PROCESSING REQUEST")
        print("=" * 80)
        
        final_response = []
        async for chunk in orchestrator.process_user_request(
            user_id=test_user.id,
            board_id=uuid4(),  # Create dummy board ID
            user_message=TEST_REQUEST
        ):
            print(chunk, end="")
            if isinstance(chunk, dict) and chunk.get("type") == "final_response":
                final_response.append(chunk.get("data", ""))
            elif isinstance(chunk, str):
                final_response.append(chunk)
        
        # 8. Log final response
        detailed_logger.log_step(
            "final_response",
            "system",
            "Final Response to User",
            {"response": "\n".join(final_response)}
        )
        
        # 9. Save log to file
        log_dir = project_root / "multiagent_logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"detailed_log_{timestamp}.md"
        
        detailed_logger.save_to_markdown(str(log_file))
        
        print(f"\n📝 Detailed log saved to: {log_file}")
        print(f"📊 Total steps logged: {len(detailed_logger.logs)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if engine:
            await engine.shutdown()
        if db:
            await db.close()


if __name__ == "__main__":
    success = asyncio.run(test_with_detailed_logging())
    sys.exit(0 if success else 1)
