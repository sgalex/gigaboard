"""
Тестовый скрипт для проверки PlannerAgent и AnalystAgent.
Запускает агенты, подключает к Message Bus и отправляет тестовые задачи.
"""

import asyncio
import logging
from uuid import uuid4

from app.core.redis import init_redis
from app.core.config import settings
from app.services.gigachat_service import get_gigachat_service
from app.services.multi_agent.message_bus import AgentMessageBus
from app.services.multi_agent.message_types import MessageType, AgentMessage
from app.services.multi_agent.agents import PlannerAgent, AnalystAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_planner_agent():
    """Тест PlannerAgent."""
    logger.info("=" * 80)
    logger.info("🧪 Testing PlannerAgent")
    logger.info("=" * 80)
    
    # Инициализация
    redis_client = await init_redis()
    message_bus = AgentMessageBus()
    gigachat_service = get_gigachat_service()
    
    # Создаем Planner Agent
    planner = PlannerAgent(
        message_bus=message_bus,
        gigachat_service=gigachat_service
    )
    
    # Запускаем агент в фоне
    agent_task = asyncio.create_task(planner.start_listening())
    
    # Даем время на подписку
    await asyncio.sleep(1)
    
    # Отправляем тестовую задачу
    session_id = str(uuid4())
    board_id = str(uuid4())
    
    test_message = AgentMessage(
        message_id=str(uuid4()),
        message_type=MessageType.TASK_REQUEST,
        sender="test_script",
        receiver="planner",
        session_id=session_id,
        board_id=board_id,
        payload={
            "task": {
                "type": "create_plan",
                "user_request": "Создай визуализацию продаж по регионам за последний квартал",
            },
            "context": {
                "session_id": session_id,
                "board_id": board_id,
                "selected_node_ids": [],
            }
        }
    )
    
    logger.info("📤 Sending task request to Planner Agent...")
    
    try:
        # Отправляем запрос и ждем ответ (timeout 30s)
        response = await message_bus.request_response(
            message=test_message,
            timeout=30
        )
        
        if response:
            logger.info("✅ Received response from Planner Agent:")
            logger.info(f"Status: {response.payload.get('status')}")
            
            if response.payload.get('status') == 'success':
                plan = response.payload.get('plan', {})
                logger.info(f"Plan ID: {plan.get('plan_id', 'N/A')}")
                logger.info(f"Steps count: {len(plan.get('steps', []))}")
                
                for i, step in enumerate(plan.get('steps', [])):
                    logger.info(f"\nStep {i+1}:")
                    logger.info(f"  Agent: {step.get('agent')}")
                    logger.info(f"  Task: {step.get('task', {}).get('description', 'N/A')}")
            else:
                error = response.payload.get('error', 'Unknown error')
                logger.error(f"❌ Planner Agent failed: {error}")
        else:
            logger.error("❌ No response from Planner Agent (timeout)")
    
    except asyncio.TimeoutError:
        logger.error("⏱️ Request timeout")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        # Останавливаем агент
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


async def test_analyst_agent():
    """Тест AnalystAgent."""
    logger.info("\n" + "=" * 80)
    logger.info("🧪 Testing AnalystAgent")
    logger.info("=" * 80)
    
    # Инициализация
    redis_client = await init_redis()
    message_bus = AgentMessageBus()
    gigachat_service = get_gigachat_service()
    
    # Создаем Analyst Agent
    analyst = AnalystAgent(
        message_bus=message_bus,
        gigachat_service=gigachat_service
    )
    
    # Запускаем агент в фоне
    agent_task = asyncio.create_task(analyst.start_listening())
    
    # Даем время на подписку
    await asyncio.sleep(1)
    
    # Отправляем тестовую задачу на генерацию SQL
    session_id = str(uuid4())
    board_id = str(uuid4())
    
    test_message = AgentMessage(
        message_id=str(uuid4()),
        message_type=MessageType.TASK_REQUEST,
        sender="test_script",
        receiver="analyst",
        session_id=session_id,
        board_id=board_id,
        payload={
            "task": {
                "type": "generate_sql",
                "description": "Получить все продажи за 2024 год с группировкой по регионам",
                "table_schema": {
                    "sales": {
                        "columns": ["id", "date", "region", "amount", "product"],
                        "types": ["integer", "date", "varchar", "decimal", "varchar"]
                    }
                },
                "database_type": "postgresql"
            },
            "context": {}
        }
    )
    
    logger.info("📤 Sending SQL generation task to Analyst Agent...")
    
    try:
        # Отправляем запрос и ждем ответ (timeout 20s)
        response = await message_bus.request_response(
            message=test_message,
            timeout=20
        )
        
        if response:
            logger.info("✅ Received response from Analyst Agent:")
            logger.info(f"Status: {response.payload.get('status')}")
            
            if response.payload.get('status') == 'success':
                result = response.payload.get('result', {})
                logger.info(f"\nGenerated SQL:")
                logger.info(f"{result.get('sql_query', 'N/A')}")
                logger.info(f"\nQuery type: {result.get('query_type', 'N/A')}")
                logger.info(f"Explanation: {result.get('explanation', 'N/A')}")
            else:
                error = response.payload.get('error', 'Unknown error')
                logger.error(f"❌ Analyst Agent failed: {error}")
        else:
            logger.error("❌ No response from Analyst Agent (timeout)")
    
    except asyncio.TimeoutError:
        logger.error("⏱️ Request timeout")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        # Останавливаем агент
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


async def main():
    """Запускает все тесты."""
    logger.info("🚀 Starting Agent Tests")
    logger.info("=" * 80)
    
    try:
        # Тест Planner Agent
        await test_planner_agent()
        
        # Небольшая пауза между тестами
        await asyncio.sleep(2)
        
        # Тест Analyst Agent
        await test_analyst_agent()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ All tests completed!")
        logger.info("=" * 80)
    
    except KeyboardInterrupt:
        logger.info("\n⚠️ Tests interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
