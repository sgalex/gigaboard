"""
Тест Planner - запрос с явным URL (должен использовать ResearcherAgent вместо SearchAgent).
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


async def test_planner_with_url():
    """Тест Planner с явным URL."""
    
    try:
        logger.info("=" * 80)
        logger.info("🧪 TEST: Planner Agent - Request with Explicit URL")
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
        
        # Test query with explicit URL
        user_request = "Загрузи данные с https://api.cinema-stats.ru/moscow/data.json и создай визуализацию"
        
        logger.info(f"📝 User request: {user_request}\n")
        logger.info("🤖 Planner is creating a plan...\n")
        
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
            logger.info(f"📊 Total steps: {len(steps)}\n")
            
            logger.info("🔍 PLAN DETAILS:")
            logger.info("")
            
            for i, step in enumerate(steps, 1):
                agent_name = step.get("agent", "unknown")
                task_type = step.get("task", {}).get("type", "unknown")
                description = step.get("task", {}).get("description", "N/A")
                url = step.get("task", {}).get("url", None)
                
                logger.info(f"  Step {i}:")
                logger.info(f"    Agent: {agent_name}")
                logger.info(f"    Type: {task_type}")
                logger.info(f"    Description: {description}")
                if url:
                    logger.info(f"    URL: {url}")
                logger.info("")
            
            # Валидация
            logger.info("=" * 80)
            logger.info("✅ VALIDATION")
            logger.info("=" * 80)
            logger.info("")
            
            if len(steps) > 0:
                first_agent = steps[0].get("agent")
                first_type = steps[0].get("task", {}).get("type")
                
                if first_agent == "researcher" and first_type == "fetch_from_api":
                    logger.info("✅ CORRECT: ResearcherAgent используется для fetch_from_api")
                    logger.info("✅ SearchAgent НЕ используется (есть явный URL)")
                elif first_agent == "search":
                    logger.error("❌ WRONG: SearchAgent используется, хотя указан URL!")
                    logger.error("   Ожидалось: ResearcherAgent с fetch_from_api")
                else:
                    logger.warning(f"⚠️  Неожиданный агент: {first_agent}")
        
        else:
            logger.error(f"❌ Status: {result.get('status')}")
        
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
    asyncio.run(test_planner_with_url())
