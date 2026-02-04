"""
Тест для создания детального лога работы Multi-Agent системы.
Сохраняет все промпты, промежуточные результаты, работу Critic и финальный вывод.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path
from datetime import datetime
from uuid import uuid4, UUID
import json

# Fix Windows console encoding for emoji
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "apps" / "backend"))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.services.multi_agent.orchestrator import MultiAgentOrchestrator
from app.services.multi_agent.engine import MultiAgentEngine
from app.core.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.board import Board


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Database URL для тестов
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/gigaboard"

# Тестовый запрос
TEST_REQUEST = """
Analyze current Bitcoin (BTC) market data:
1. Get current price in USD
2. Calculate 24h price change
3. Provide brief market analysis

Return structured data with price and analysis.
"""


class DetailedLogger:
    """Логгер для детального отслеживания работы Multi-Agent системы."""
    
    def __init__(self):
        self.log_entries = []
        self.start_time = datetime.now()
        
    def log_step(self, step_type: str, agent: str, title: str, data: dict):
        """Записать шаг в лог."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": int((datetime.now() - self.start_time).total_seconds() * 1000),
            "type": step_type,
            "agent": agent,
            "title": title,
            "data": data
        }
        self.log_entries.append(entry)
        
    def save_to_markdown(self, filepath: str):
        """Сохранить лог в красиво отформатированный Markdown файл."""
        lines = []
        
        # Заголовок
        lines.append("# Multi-Agent System: Detailed Execution Log")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Total Duration**: {self.log_entries[-1]['elapsed_ms'] if self.log_entries else 0}ms")
        lines.append(f"**Steps**: {len(self.log_entries)}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Группируем по типам
        for entry in self.log_entries:
            elapsed = f"[{entry['elapsed_ms']}ms]"
            
            if entry['type'] == 'user_request':
                lines.append(f"## 📝 User Request {elapsed}")
                lines.append("")
                lines.append(f"**Agent**: {entry['agent']}")
                lines.append("")
                lines.append("**Message**:")
                lines.append("```")
                lines.append(entry['data'].get('message', 'N/A'))
                lines.append("```")
                lines.append("")
                
            elif entry['type'] == 'plan_created':
                lines.append(f"## 🧠 Execution Plan Created {elapsed}")
                lines.append("")
                lines.append(f"**Agent**: {entry['agent']}")
                lines.append(f"**Steps**: {entry['data'].get('step_count', 0)}")
                lines.append("")
                lines.append("**Plan**:")
                lines.append("```json")
                lines.append(json.dumps(entry['data'].get('plan', {}), indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("")
                
            elif entry['type'] == 'task_execution':
                lines.append(f"## ⚙️ Task Execution {elapsed}")
                lines.append("")
                lines.append(f"**Step**: {entry['data'].get('step_index', 0)}/{entry['data'].get('total_steps', 0)}")
                lines.append(f"**Agent**: {entry['agent']}")
                lines.append(f"**Description**: {entry['title']}")
                lines.append("")
                lines.append("**Task Details**:")
                lines.append("```json")
                lines.append(json.dumps(entry['data'].get('task', {}), indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("")
                
            elif entry['type'] == 'agent_prompt':
                lines.append(f"### 💬 LLM Prompt to {entry['agent'].upper()} {elapsed}")
                lines.append("")
                lines.append("<details>")
                lines.append(f"<summary>View {entry['agent']} prompt</summary>")
                lines.append("")
                lines.append("**System Prompt**:")
                lines.append("```")
                system_prompt = entry['data'].get('system_prompt', 'N/A')
                lines.append(system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt)
                lines.append("```")
                lines.append("")
                lines.append("**User Prompt**:")
                lines.append("```")
                lines.append(entry['data'].get('user_prompt', 'N/A'))
                lines.append("```")
                lines.append("")
                lines.append("</details>")
                lines.append("")
                
            elif entry['type'] == 'agent_response':
                lines.append(f"### ✅ {entry['agent'].upper()} Response {elapsed}")
                lines.append("")
                lines.append(f"**Status**: {entry['data'].get('status', 'unknown')}")
                lines.append(f"**Execution Time**: {entry['data'].get('execution_time_ms', 0)}ms")
                lines.append("")
                lines.append("**Result**:")
                lines.append("```json")
                result = entry['data'].get('result', {})
                result_str = json.dumps(result, indent=2, ensure_ascii=False)
                if len(result_str) > 1000:
                    lines.append(result_str[:1000] + "...")
                else:
                    lines.append(result_str)
                lines.append("```")
                lines.append("")
                
            elif entry['type'] == 'critic_validation':
                lines.append(f"## 🔍 Critic Agent Validation {elapsed}")
                lines.append("")
                lines.append(f"**Valid**: {entry['data'].get('valid', False)}")
                lines.append(f"**Confidence**: {entry['data'].get('confidence', 0):.0%}")
                lines.append("")
                if entry['data'].get('issues'):
                    lines.append("**Issues Found**:")
                    for issue in entry['data']['issues']:
                        lines.append(f"- {issue}")
                    lines.append("")
                lines.append("**Critic Analysis**:")
                lines.append("```json")
                lines.append(json.dumps(entry['data'].get('analysis', {}), indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("")
                
            elif entry['type'] == 'final_response':
                lines.append(f"## 🎯 Final Response {elapsed}")
                lines.append("")
                lines.append("**Aggregated Result**:")
                lines.append("```")
                lines.append(entry['data'].get('response', 'N/A'))
                lines.append("```")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        # Сохраняем
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"✅ Detailed log saved to: {filepath}")


async def test_with_detailed_logging():
    """Тест с детальным логированием всех шагов."""
    
    detailed_logger = DetailedLogger()
    
    # Setup database
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    db = async_session()
    
    try:
        print("\n" + "=" * 80)
        print("🚀 STARTING MULTI-AGENT SYSTEM WITH DETAILED LOGGING")
        print("=" * 80)
        
        # 1. Create test user
        test_user = User(
            id=uuid4(),
            username="test_user",
            email="test@example.com",
            hashed_password="test_hash"
        )
        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)
        
        # 2. Create test project
        test_project = Project(
            id=uuid4(),
            name="Test Project",
            user_id=test_user.id
        )
        db.add(test_project)
        await db.commit()
        await db.refresh(test_project)
        
        # 3. Create test board
        test_board = Board(
            id=uuid4(),
            name="Test Board",
            project_id=test_project.id,
            user_id=test_user.id
        )
        db.add(test_board)
        await db.commit()
        await db.refresh(test_board)
        
        # Log user request
        detailed_logger.log_step(
            "user_request",
            "user",
            "Initial Request",
            {"message": TEST_REQUEST}
        )
        
        # 4. Start Multi-Agent Engine
        print("\n🎭 Starting Multi-Agent Engine...")
        multi_agent_engine = MultiAgentEngine()
        await multi_agent_engine.start()
        print("✅ Multi-Agent Engine started")
        
        # 5. Create orchestrator
        orchestrator = MultiAgentOrchestrator(db, multi_agent_engine.message_bus)
        
        # Monkey-patch для логирования
        original_execute_task = orchestrator._execute_task
        
        async def logged_execute_task(session_id, task_index, task, previous_results):
            """Обёрнутый метод с логированием."""
            agent_name = task.get("agent", "unknown")
            task_desc = task.get("task", {}).get("description", "N/A")
            
            # Log task execution start
            detailed_logger.log_step(
                "task_execution",
                agent_name,
                task_desc,
                {
                    "step_index": task_index + 1,
                    "total_steps": len(orchestrator._current_plan_steps) if hasattr(orchestrator, '_current_plan_steps') else 0,
                    "task": task
                }
            )
            
            # Execute
            import time
            start_time = time.time()
            result = await original_execute_task(session_id, task_index, task, previous_results)
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log response
            detailed_logger.log_step(
                "agent_response",
                agent_name,
                f"{agent_name} completed",
                {
                    "status": result.get("status", "unknown"),
                    "execution_time_ms": execution_time,
                    "result": result
                }
            )
            
            return result
        
        orchestrator._execute_task = logged_execute_task
        
        # 6. Process request
        print("\n" + "=" * 80)
        print("🚀 EXECUTING WORKFLOW")
        print("=" * 80)
        
        response_chunks = []
        async for chunk in orchestrator.process_user_request(
            user_id=test_user.id,
            board_id=test_board.id,
            user_message=TEST_REQUEST
        ):
            response_chunks.append(chunk)
            if len(chunk) > 80:
                print(f"📦 Chunk ({len(chunk)}b): {chunk[:80]}...")
            else:
                print(f"📦 Chunk ({len(chunk)}b): {chunk}")
        
        result = "".join(response_chunks)
        
        # Log final response
        detailed_logger.log_step(
            "final_response",
            "orchestrator",
            "Workflow Completed",
            {"response": result}
        )
        
        print("\n" + "=" * 80)
        print("✅ WORKFLOW COMPLETED")
        print("=" * 80)
        
        # Save detailed log
        output_dir = Path(__file__).parent / "multiagent_logs"
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = output_dir / f"multiagent_detailed_log_{timestamp}.md"
        
        detailed_logger.save_to_markdown(str(log_file))
        
        print(f"\n📄 Detailed log saved to: {log_file}")
        
    finally:
        # Cleanup
        print("\n🧹 Cleanup...")
        if 'multi_agent_engine' in locals():
            await multi_agent_engine.stop()
            print("✅ Multi-Agent Engine stopped")
        
        await db.close()
        await engine.dispose()
        print("✅ Database closed")


if __name__ == "__main__":
    asyncio.run(test_with_detailed_logging())
