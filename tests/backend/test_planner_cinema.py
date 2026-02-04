"""
Простой тест Planner Agent - проверка создания плана для запроса о кино в Москве.
Без базы данных, только прямой вызов Planner.
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# Setup path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.redis import init_redis, close_redis
from app.core.config import settings
from app.services.multi_agent import AgentMessageBus, PlannerAgent
from app.services.gigachat_service import GigaChatService

# Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def test_planner():
    """Тест Planner для запроса о кино."""
    
    try:
        logger.info("=" * 80)
        logger.info("🧪 TEST: Planner Agent - Cinema Statistics in Moscow")
        logger.info("=" * 80)
        logger.info("")
        
        # Init
        await init_redis()
        
        gigachat = GigaChatService(
            api_key=settings.GIGACHAT_API_KEY,
            model=settings.GIGACHAT_MODEL,
            scope=settings.GIGACHAT_SCOPE,
        )
        
        message_bus = AgentMessageBus()
        await message_bus.connect()
        
        planner = PlannerAgent(
            message_bus=message_bus,
            gigachat_service=gigachat
        )
        
        logger.info("✅ Setup complete\n")
        
        # Test query
        user_request = "Найди статистику просмотра кино жителями Москвы и создай визуализацию"
        
        logger.info(f"📝 User request: {user_request}\n")
        logger.info("🤖 Planner is creating a plan...\n")
        
        # Direct task call
        task = {
            "type": "create_plan",
            "user_request": user_request
        }
        
        context = {
            "session_id": "test-session-123",
            "board_id": "test-board-456",
            "selected_node_ids": []
        }
        
        result = await planner.process_task(task, context)
        
        logger.info("=" * 80)
        logger.info("📋 PLAN CREATED")
        logger.info("=" * 80)
        logger.info("")
        
        if result.get("status") == "success":
            plan = result.get("plan", {})
            steps = plan.get("steps", [])
            
            logger.info(f"✅ Status: {result['status']}")
            logger.info(f"📊 Total steps: {len(steps)}")
            logger.info(f"⏱️  Estimated time: {plan.get('estimated_total_time', 'N/A')}\n")
            
            logger.info("🔍 PLAN DETAILS:")
            logger.info("")
            
            for i, step in enumerate(steps, 1):
                agent_name = step.get("agent", "unknown")
                task_type = step.get("task", {}).get("type", "unknown")
                description = step.get("task", {}).get("description", "N/A")
                depends_on = step.get("depends_on", [])
                
                logger.info(f"  Step {i}:")
                logger.info(f"    Agent: {agent_name}")
                logger.info(f"    Type: {task_type}")
                logger.info(f"    Description: {description}")
                if depends_on:
                    logger.info(f"    Depends on: {', '.join(depends_on)}")
                logger.info("")
            
            # Анализ плана
            logger.info("=" * 80)
            logger.info("🔬 PLAN ANALYSIS")
            logger.info("=" * 80)
            logger.info("")
            
            agent_names = [step.get("agent") for step in steps]
            
            if "search" in agent_names:
                search_step = next((i+1 for i, s in enumerate(steps) if s.get("agent") == "search"), None)
                logger.info(f"✅ SearchAgent задействован (шаг {search_step})")
            else:
                logger.info("❌ SearchAgent НЕ задействован")
            
            if "researcher" in agent_names:
                logger.info("📊 ResearcherAgent включен в план")
            
            if "analyst" in agent_names:
                analyst_step = next((i+1 for i, s in enumerate(steps) if s.get("agent") == "analyst"), None)
                logger.info(f"📈 AnalystAgent задействован (шаг {analyst_step})")
            
            if "reporter" in agent_names:
                reporter_step = next((i+1 for i, s in enumerate(steps) if s.get("agent") == "reporter"), None)
                logger.info(f"📊 ReporterAgent задействован (шаг {reporter_step})")
            
            logger.info("")
            
            # Проверка логики
            logger.info("=" * 80)
            logger.info("✅ WORKFLOW VALIDATION")
            logger.info("=" * 80)
            logger.info("")
            
            if len(steps) > 0:
                first_agent = steps[0].get("agent")
                
                if first_agent == "search":
                    logger.info("✅ CORRECT: SearchAgent идёт первым (нет явного источника данных)")
                elif first_agent == "researcher":
                    logger.info("⚠️  ResearcherAgent первый (возможно указан URL?)")
                else:
                    logger.info(f"❌ WARNING: {first_agent} идёт первым (ожидался search или researcher)")
                
                # Проверка зависимостей
                has_proper_dependencies = True
                for i, step in enumerate(steps[1:], 2):
                    deps = step.get("depends_on", [])
                    if not deps:
                        logger.info(f"⚠️  Шаг {i} не имеет зависимостей")
                        has_proper_dependencies = False
                
                if has_proper_dependencies and len(steps) > 1:
                    logger.info("✅ Зависимости между шагами корректны")
            
        else:
            logger.error(f"❌ Status: {result.get('status')}")
            logger.error(f"Error: {result.get('error', 'Unknown error')}")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("🏁 TEST COMPLETED")
        logger.info("=" * 80)
        
        # Cleanup
        await message_bus.disconnect()
        await close_redis()
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_planner())
