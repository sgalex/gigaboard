"""
Тест полного workflow с использованием MessageBus для коммуникации между агентами.

Проверяет:
- Передачу данных через AgentMessage
- Единый формат обмена данными
- Асинхронную коммуникацию через Redis
- Обработку TASK_REQUEST/TASK_RESULT сообщений
"""
import asyncio
import logging
import os
from uuid import uuid4

from app.core.redis import init_redis, close_redis
from app.services.gigachat_service import GigaChatService
from app.services.multi_agent.message_bus import AgentMessageBus
from app.services.multi_agent.message_types import MessageType, AgentMessage
from app.services.multi_agent.agents.planner import PlannerAgent
from app.services.multi_agent.agents.search import SearchAgent
from app.services.multi_agent.agents.analyst import AnalystAgent
from app.services.multi_agent.agents.reporter import ReporterAgent


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MessageBusWorkflowTest:
    """Тестирует полный workflow с использованием MessageBus."""
    
    def __init__(self):
        self.gigachat = None
        self.message_bus = None
        self.agents = {}
        
        # Для сбора результатов
        self.workflow_results = {}
        self.pending_messages = {}
        
    async def setup(self):
        """Инициализация всех компонентов."""
        logger.info("\n" + "=" * 80)
        logger.info("🔧 SETUP: MessageBus Workflow Test")
        logger.info("=" * 80 + "\n")
        
        # Redis
        await init_redis()
        logger.info("✅ Redis initialized")
        
        # GigaChat
        gigachat_key = os.getenv("GIGACHAT_API_KEY")
        if not gigachat_key:
            raise ValueError("GIGACHAT_API_KEY environment variable not set")
        self.gigachat = GigaChatService(api_key=gigachat_key)
        logger.info("✅ GigaChat initialized")
        
        # Message Bus
        self.message_bus = AgentMessageBus()
        await self.message_bus.connect()
        logger.info("✅ Message Bus connected")
        
        # Создаём агентов
        self.agents = {
            "planner": PlannerAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            ),
            "search": SearchAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            ),
            "analyst": AnalystAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            ),
            "reporter": ReporterAgent(
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            )
        }
        
        # Запускаем агентов (подписываемся на их каналы)
        for agent_name, agent in self.agents.items():
            await agent.start_listening()
            logger.info(f"✅ {agent_name.upper()} Agent listening")
        
        logger.info(f"✅ {len(self.agents)} agents initialized and listening\n")
        
    async def run_workflow(self):
        """Выполняет полный workflow через MessageBus."""
        
        logger.info("=" * 80)
        logger.info("🎬 STARTING MESSAGEBUS WORKFLOW")
        logger.info("=" * 80)
        
        session_id = f"session_{uuid4().hex[:8]}"
        board_id = f"board_{uuid4().hex[:8]}"
        
        user_request = "Найди статистику просмотра кино жителями Москвы и создай визуализацию"
        logger.info(f"\n💬 User Request: {user_request}\n")
        
        # ========== STEP 1: ORCHESTRATOR → PLANNER ==========
        logger.info("─" * 80)
        logger.info("📋 STEP 1: Sending USER_REQUEST to Planner")
        logger.info("─" * 80 + "\n")
        
        # Создаём сообщение для планировщика
        plan_request = AgentMessage(
            message_id=str(uuid4()),
            message_type=MessageType.TASK_REQUEST,
            sender="orchestrator",
            receiver="planner",
            session_id=session_id,
            board_id=board_id,
            payload={
                "task": {
                    "type": "create_plan",
                    "user_request": user_request,
                    "board_context": {
                        "nodes": [],
                        "edges": []
                    }
                },
                "context": {
                    "session_id": session_id,
                    "board_id": board_id
                }
            },
            requires_acknowledgement=False,
            timeout_seconds=60
        )
        
        logger.info(f"📤 Publishing TASK_REQUEST to planner (msg_id: {plan_request.message_id[:8]}...)")
        
        # Подписываемся на ответ от Planner ДО публикации сообщения
        plan_result_future = asyncio.Future()
        
        async def handle_plan_result(msg: AgentMessage):
            if msg.parent_message_id == plan_request.message_id:
                logger.info(f"📥 Received TASK_RESULT from {msg.sender}")
                plan_result_future.set_result(msg)
        
        # Подписываемся на ответы к orchestrator
        await self.message_bus.subscribe("orchestrator", handle_plan_result)
        
        # Публикуем запрос
        await self.message_bus.publish(plan_request)
        
        # Ждём результат с таймаутом
        try:
            plan_response = await asyncio.wait_for(plan_result_future, timeout=60.0)
            plan_result = plan_response.payload.get("result", {})
            
            if plan_result.get("status") == "success":
                steps = plan_result.get("steps", [])
                logger.info(f"✅ Plan received with {len(steps)} steps:")
                for i, step in enumerate(steps, 1):
                    logger.info(f"   {i}. {step.get('agent')} ({step.get('task', {}).get('type')})")
                logger.info("")
            else:
                logger.error(f"❌ Planning failed: {plan_result}")
                return
                
        except asyncio.TimeoutError:
            logger.error("❌ Timeout waiting for plan from Planner")
            return
        
        self.workflow_results["plan"] = plan_result
        
        # ========== STEP 2: ORCHESTRATOR → SEARCH ==========
        logger.info("─" * 80)
        logger.info("🔍 STEP 2: Sending TASK_REQUEST to SearchAgent")
        logger.info("─" * 80 + "\n")
        
        # Находим search step в плане
        steps = plan_result.get("steps", [])
        search_step = next((s for s in steps if s["agent"] == "search"), None)
        
        if not search_step:
            logger.error("❌ No search step in plan")
            return
        
        # Создаём сообщение для SearchAgent
        search_request = AgentMessage(
            message_id=str(uuid4()),
            message_type=MessageType.TASK_REQUEST,
            sender="orchestrator",
            receiver="search",
            session_id=session_id,
            board_id=board_id,
            payload={
                "task": search_step["task"],
                "context": {
                    "session_id": session_id,
                    "board_id": board_id
                }
            },
            requires_acknowledgement=False,
            timeout_seconds=90
        )
        
        logger.info(f"📤 Publishing TASK_REQUEST to search (msg_id: {search_request.message_id[:8]}...)")
        
        # Подписываемся на ответ от SearchAgent
        search_result_future = asyncio.Future()
        
        async def handle_search_result(msg: AgentMessage):
            if msg.parent_message_id == search_request.message_id:
                logger.info(f"📥 Received TASK_RESULT from {msg.sender}")
                search_result_future.set_result(msg)
        
        # Обновляем подписку orchestrator
        await self.message_bus.subscribe("orchestrator", handle_search_result)
        
        # Публикуем запрос
        await self.message_bus.publish(search_request)
        
        # Ждём результат
        try:
            search_response = await asyncio.wait_for(search_result_future, timeout=90.0)
            search_result = search_response.payload.get("result", {})
            
            if search_result.get("status") == "success":
                results_count = len(search_result.get("results", []))
                logger.info(f"✅ Search completed: {results_count} results found")
                
                if search_result.get("summary"):
                    logger.info(f"\n📝 Summary: {search_result['summary'][:200]}...\n")
            else:
                logger.error(f"❌ Search failed: {search_result}")
                
        except asyncio.TimeoutError:
            logger.error("❌ Timeout waiting for SearchAgent")
            return
        
        self.workflow_results["search"] = search_result
        
        # ========== STEP 3: ORCHESTRATOR → ANALYST ==========
        logger.info("─" * 80)
        logger.info("📊 STEP 3: Sending TASK_REQUEST to AnalystAgent")
        logger.info("─" * 80 + "\n")
        
        analyst_step = next((s for s in steps if s["agent"] == "analyst"), None)
        
        if not analyst_step:
            logger.error("❌ No analyst step in plan")
            return
        
        # Создаём сообщение для AnalystAgent с результатами поиска
        analyst_request = AgentMessage(
            message_id=str(uuid4()),
            message_type=MessageType.TASK_REQUEST,
            sender="orchestrator",
            receiver="analyst",
            session_id=session_id,
            board_id=board_id,
            payload={
                "task": analyst_step["task"],
                "context": {
                    "session_id": session_id,
                    "board_id": board_id,
                    "previous_results": {
                        "search": search_result
                    }
                }
            },
            requires_acknowledgement=False,
            timeout_seconds=60
        )
        
        logger.info(f"📤 Publishing TASK_REQUEST to analyst (msg_id: {analyst_request.message_id[:8]}...)")
        logger.info("📦 Including search results in context.previous_results")
        
        # Подписываемся на ответ от AnalystAgent
        analyst_result_future = asyncio.Future()
        
        async def handle_analyst_result(msg: AgentMessage):
            if msg.parent_message_id == analyst_request.message_id:
                logger.info(f"📥 Received TASK_RESULT from {msg.sender}")
                analyst_result_future.set_result(msg)
        
        await self.message_bus.subscribe("orchestrator", handle_analyst_result)
        
        # Публикуем запрос
        await self.message_bus.publish(analyst_request)
        
        # Ждём результат
        try:
            analyst_response = await asyncio.wait_for(analyst_result_future, timeout=60.0)
            analyst_result = analyst_response.payload.get("result", {})
            
            if analyst_result.get("status") == "success":
                insights = analyst_result.get("insights", [])
                logger.info(f"✅ Analysis completed: {len(insights)} insights generated\n")
            else:
                logger.warning(f"⚠️ Analysis returned: {analyst_result.get('status')}")
                
        except asyncio.TimeoutError:
            logger.error("❌ Timeout waiting for AnalystAgent")
            return
        
        self.workflow_results["analyst"] = analyst_result
        
        # ========== ИТОГИ ==========
        logger.info("\n" + "=" * 80)
        logger.info("✅ WORKFLOW COMPLETED")
        logger.info("=" * 80)
        
        self._print_summary()
        
    def _print_summary(self):
        """Выводит итоговую информацию о workflow."""
        logger.info("\n📊 WORKFLOW SUMMARY:\n")
        
        plan = self.workflow_results.get("plan", {})
        search = self.workflow_results.get("search", {})
        analyst = self.workflow_results.get("analyst", {})
        
        logger.info(f"   📋 Plan: {len(plan.get('steps', []))} steps")
        logger.info(f"   🔍 Search: {len(search.get('results', []))} results found")
        logger.info(f"   📊 Analysis: {analyst.get('status', 'N/A')}")
        logger.info("")
        
        logger.info("🎉 All agents communicated via MessageBus!")
        logger.info("✅ AgentMessage format used consistently")
        logger.info("✅ Asynchronous pub/sub communication verified")
        logger.info("")
        
    async def cleanup(self):
        """Очистка ресурсов."""
        logger.info("🧹 Cleaning up...")
        
        if self.message_bus:
            await self.message_bus.disconnect()
        
        await close_redis()
        
        logger.info("✅ Cleanup complete")


async def main():
    """Главная функция теста."""
    test = MessageBusWorkflowTest()
    
    try:
        await test.setup()
        await test.run_workflow()
    finally:
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
