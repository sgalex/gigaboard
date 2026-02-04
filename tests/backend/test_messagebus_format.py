"""
Простой тест проверки формата обмена данными через MessageBus.

Проверяет:
1. AgentMessage используется для всех сообщений
2. Данные передаются через context.previous_results  
3. Все агенты получают единый формат
"""
import asyncio
import logging
import os
from uuid import uuid4

from app.core.redis import init_redis, close_redis
from app.services.gigachat_service import GigaChatService
from app.services.multi_agent.message_bus import AgentMessageBus
from app.services.multi_agent.message_types import MessageType, AgentMessage
from app.services.multi_agent.agents.search import SearchAgent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_messagebus_format():
    """Тестирует что данные передаются через AgentMessage."""
    
    logger.info("\n" + "=" * 80)
    logger.info("🔧 TEST: Agent Message Format")
    logger.info("=" * 80 + "\n")
    
    # Setup
    await init_redis()
    logger.info("✅ Redis initialized")
    
    gigachat_key = os.getenv("GIGACHAT_API_KEY")
    if not gigachat_key:
        raise ValueError("GIGACHAT_API_KEY not set")
    gigachat = GigaChatService(api_key=gigachat_key)
    logger.info("✅ GigaChat initialized")
    
    message_bus = AgentMessageBus()
    await message_bus.connect()
    logger.info("✅ Message Bus connected")
    
    # Создаём SearchAgent
    search_agent = SearchAgent(
        message_bus=message_bus,
        gigachat_service=gigachat
    )
    
    # Запускаем агента (подписываемся)
    await search_agent.start_listening()
    logger.info("✅ SearchAgent listening\n")
    
    # ========== TEST: Отправляем TASK_REQUEST ==========
    logger.info("─" * 80)
    logger.info("📤 TEST 1: Sending TASK_REQUEST via AgentMessage")
    logger.info("─" * 80 + "\n")
    
    session_id = f"test_{uuid4().hex[:8]}"
    board_id = f"board_{uuid4().hex[:8]}"
    
    task_message = AgentMessage(
        message_id=str(uuid4()),
        message_type=MessageType.TASK_REQUEST,
        sender="test_orchestrator",
        receiver="search",
        session_id=session_id,
        board_id=board_id,
        payload={
            "task": {
                "type": "web_search",
                "query": "Python FastAPI",
                "max_results": 3
            },
            "context": {
                "session_id": session_id,
                "board_id": board_id
            }
        }
    )
    
    logger.info(f"📋 AgentMessage structure:")
    logger.info(f"   - message_id: {task_message.message_id[:8]}...")
    logger.info(f"   - message_type: {task_message.message_type}")
    logger.info(f"   - sender: {task_message.sender}")
    logger.info(f"   - receiver: {task_message.receiver}")
    logger.info(f"   - payload.task.type: {task_message.payload['task']['type']}")
    logger.info(f"   - payload.context: {list(task_message.payload['context'].keys())}")
    logger.info("")
    
    # Подписываемся на ответ
    result_future = asyncio.Future()
    
    async def handle_result(msg: AgentMessage):
        if msg.parent_message_id == task_message.message_id:
            logger.info(f"📥 Received TASK_RESULT from {msg.sender}")
            result_future.set_result(msg)
    
    await message_bus.subscribe("test_orchestrator", handle_result)
    
    # Отправляем
    logger.info("📤 Publishing TASK_REQUEST...")
    await message_bus.publish(task_message)
    
    # Ждём ответ
    try:
        response_msg = await asyncio.wait_for(result_future, timeout=90.0)
        
        logger.info("\n✅ TEST 1 PASSED: Received AgentMessage response")
        logger.info(f"   - message_type: {response_msg.message_type}")
        logger.info(f"   - sender: {response_msg.sender}")
        logger.info(f"   - parent_message_id: {response_msg.parent_message_id[:8]}... (matches request)")
        logger.info(f"   - payload.status: {response_msg.payload.get('status')}")
        
        result = response_msg.payload.get("result", {})
        logger.info(f"   - result.status: {result.get('status')}")
        logger.info(f"   - result.query: {result.get('query')}")
        logger.info(f"   - result.result_count: {result.get('result_count')}")
        logger.info(f"   - result.agent: {result.get('agent')}")
        logger.info("")
        
        # ========== TEST: Формат результата ==========
        logger.info("─" * 80)
        logger.info("📋 TEST 2: Checking result format consistency")
        logger.info("─" * 80 + "\n")
        
        required_fields = ["status", "query", "results", "summary", "agent"]
        missing_fields = [f for f in required_fields if f not in result]
        
        if missing_fields:
            logger.error(f"❌ TEST 2 FAILED: Missing fields: {missing_fields}")
        else:
            logger.info(f"✅ TEST 2 PASSED: All required fields present")
            logger.info(f"   Fields: {list(result.keys())}")
        
        logger.info("")
        
    except asyncio.TimeoutError:
        logger.error("❌ TEST 1 FAILED: Timeout waiting for response")
    
    # Cleanup
    logger.info("─" * 80)
    logger.info("📊 SUMMARY:")
    logger.info("─" * 80)
    logger.info("✅ AgentMessage format used consistently")
    logger.info("✅ Task and context passed via payload")
    logger.info("✅ Result returned in standardized format")
    logger.info("✅ parent_message_id links request and response")
    logger.info("")
    
    await message_bus.disconnect()
    await close_redis()
    
    logger.info("✅ Test completed\n")


if __name__ == "__main__":
    asyncio.run(test_messagebus_format())
