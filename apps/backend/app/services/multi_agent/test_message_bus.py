"""
Простой тест для Message Bus - проверка базовой функциональности.

Запуск:
    cd apps/backend
    python -m app.services.multi_agent.test_message_bus
"""
import asyncio
import sys
from uuid import uuid4
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.services.multi_agent.message_bus import AgentMessageBus
from app.services.multi_agent.message_types import MessageType, AgentMessage


async def test_basic_pub_sub():
    """Тест: базовая публикация и подписка."""
    print("\n=== Test 1: Basic Pub/Sub ===")
    
    # Создаём Message Bus
    bus = AgentMessageBus()
    await bus.connect()
    
    # Список полученных сообщений
    received_messages = []
    
    # Callback для получения сообщений
    async def handle_message(msg: AgentMessage):
        print(f"Agent 'planner' received: {msg.message_type} from {msg.sender}")
        received_messages.append(msg)
    
    # Подписываем агента
    await bus.subscribe("planner", handle_message)
    
    # Даём время на подписку
    await asyncio.sleep(0.5)
    
    # Публикуем сообщение
    message = AgentMessage(
        message_id=str(uuid4()),
        message_type=MessageType.TASK_REQUEST,
        sender="orchestrator",
        receiver="planner",
        session_id="test_session_1",
        board_id="test_board_1",
        payload={
            "task": "Create a bar chart",
            "data_node_id": "dn_123"
        }
    )
    
    await bus.publish(message)
    
    # Ждём получения
    await asyncio.sleep(0.5)
    
    # Проверяем
    assert len(received_messages) == 1, f"Expected 1 message, got {len(received_messages)}"
    assert received_messages[0].message_id == message.message_id
    
    print("✅ Test 1 passed: Message published and received")
    
    # Отключаемся
    await bus.disconnect()


async def test_multiple_agents():
    """Тест: несколько агентов получают сообщения."""
    print("\n=== Test 2: Multiple Agents ===")
    
    bus = AgentMessageBus()
    await bus.connect()
    
    # Счётчики для каждого агента
    planner_msgs = []
    researcher_msgs = []
    reporter_msgs = []
    
    async def planner_handler(msg: AgentMessage):
        print(f"Planner received: {msg.message_type}")
        planner_msgs.append(msg)
    
    async def researcher_handler(msg: AgentMessage):
        print(f"Researcher received: {msg.message_type}")
        researcher_msgs.append(msg)
    
    async def reporter_handler(msg: AgentMessage):
        print(f"Reporter received: {msg.message_type}")
        reporter_msgs.append(msg)
    
    # Подписываем всех агентов
    await bus.subscribe("planner", planner_handler)
    await bus.subscribe("researcher", researcher_handler)
    await bus.subscribe("reporter", reporter_handler)
    
    await asyncio.sleep(0.5)
    
    # Отправляем сообщения каждому агенту
    for agent in ["planner", "researcher", "reporter"]:
        message = AgentMessage(
            message_id=str(uuid4()),
            message_type=MessageType.TASK_REQUEST,
            sender="orchestrator",
            receiver=agent,
            session_id="test_session_2",
            board_id="test_board_2",
            payload={"task": f"Task for {agent}"}
        )
        await bus.publish(message)
    
    await asyncio.sleep(0.5)
    
    # Проверяем
    assert len(planner_msgs) == 1, "Planner should receive 1 message"
    assert len(researcher_msgs) == 1, "Researcher should receive 1 message"
    assert len(reporter_msgs) == 1, "Reporter should receive 1 message"
    
    print("✅ Test 2 passed: Multiple agents received their messages")
    
    await bus.disconnect()


async def test_message_history():
    """Тест: история сообщений сохраняется."""
    print("\n=== Test 3: Message History ===")
    
    bus = AgentMessageBus()
    await bus.connect()
    
    session_id = "test_session_3"
    
    # Отправляем несколько сообщений
    for i in range(5):
        message = AgentMessage(
            message_id=str(uuid4()),
            message_type=MessageType.TASK_PROGRESS,
            sender="researcher",
            receiver="orchestrator",
            session_id=session_id,
            board_id="test_board_3",
            payload={"progress": i * 20}
        )
        await bus.publish(message)
    
    await asyncio.sleep(0.5)
    
    # Получаем историю
    history = await bus.get_message_history(session_id, limit=10)
    
    print(f"History contains {len(history)} messages")
    for msg in history:
        print(f"  - {msg.message_type} from {msg.sender}")
    
    assert len(history) == 5, f"Expected 5 messages in history, got {len(history)}"
    
    print("✅ Test 3 passed: Message history stored correctly")
    
    await bus.disconnect()


async def test_stats():
    """Тест: статистика Message Bus."""
    print("\n=== Test 4: Statistics ===")
    
    bus = AgentMessageBus()
    await bus.connect()
    
    # Подписываем агента
    async def dummy_handler(msg: AgentMessage):
        pass
    
    await bus.subscribe("test_agent", dummy_handler)
    await asyncio.sleep(0.5)
    
    # Отправляем несколько сообщений
    for i in range(10):
        message = AgentMessage(
            message_id=str(uuid4()),
            message_type=MessageType.TASK_REQUEST,
            sender="orchestrator",
            receiver="test_agent",
            session_id="test_session_4",
            board_id="test_board_4",
            payload={"index": i}
        )
        await bus.publish(message)
    
    await asyncio.sleep(0.5)
    
    # Получаем статистику
    stats = await bus.get_stats()
    
    print("Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    assert stats["messages_sent"] >= 10, "Should have sent at least 10 messages"
    assert stats["messages_received"] >= 10, "Should have received at least 10 messages"
    
    print("✅ Test 4 passed: Statistics collected correctly")
    
    await bus.disconnect()


async def main():
    """Запуск всех тестов."""
    print("=" * 60)
    print("Message Bus Tests")
    print("=" * 60)
    
    try:
        await test_basic_pub_sub()
        await test_multiple_agents()
        await test_message_history()
        await test_stats()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
