"""
Тест адаптивного планирования Multi-Agent системы.

Сценарий: "Найди статистику просмотра кино жителями Москвы"

Workflow:
1. Planner понимает, что данных нет → создаёт задачу для SearchAgent
2. SearchAgent ищет в интернете
3. Planner получает результаты поиска → создаёт новый план для анализа
4. Analyst анализирует данные
5. Reporter создаёт визуализацию
"""
import asyncio
import logging
from datetime import datetime
import sys
import os
from pathlib import Path
from uuid import uuid4

# Setup path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session_maker
from app.core.redis import init_redis, close_redis
from app.core.config import settings
from app.services.multi_agent import (
    AgentMessageBus,
    MultiAgentOrchestrator,
    PlannerAgent,
    AnalystAgent,
    ReporterAgent,
    ResearcherAgent,
    SearchAgent,
)
from app.services.gigachat_service import GigaChatService

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class AdaptivePlanningTest:
    """Тест адаптивного планирования с SearchAgent."""
    
    def __init__(self):
        self.db = None
        self.message_bus = None
        self.orchestrator = None
        self.agents = {}
        self.agent_tasks = []
        
    async def setup(self):
        """Инициализация компонентов."""
        logger.info("=" * 80)
        logger.info("🔧 SETUP: Adaptive Planning Test")
        logger.info("=" * 80)
        
        try:
            # Database
            self.db = async_session_maker()
            logger.info("✅ Database session created")
            
            # Redis
            await init_redis()
            logger.info("✅ Redis connected")
            
            # GigaChat
            gigachat = GigaChatService(
                api_key=settings.GIGACHAT_API_KEY,
                model=settings.GIGACHAT_MODEL,
                temperature=settings.GIGACHAT_TEMPERATURE,
                max_tokens=settings.GIGACHAT_MAX_TOKENS,
                scope=settings.GIGACHAT_SCOPE,
                verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
            )
            logger.info("✅ GigaChat initialized")
            
            # Message Bus
            self.message_bus = AgentMessageBus()
            await self.message_bus.connect()
            logger.info("✅ Message Bus connected")
            
            # Agents
            self.agents["planner"] = PlannerAgent(
                message_bus=self.message_bus,
                gigachat_service=gigachat
            )
            
            self.agents["search"] = SearchAgent(
                message_bus=self.message_bus,
                gigachat_service=gigachat
            )
            
            self.agents["researcher"] = ResearcherAgent(
                message_bus=self.message_bus,
                gigachat_service=gigachat
            )
            
            self.agents["analyst"] = AnalystAgent(
                message_bus=self.message_bus,
                gigachat_service=gigachat
            )
            
            self.agents["reporter"] = ReporterAgent(
                message_bus=self.message_bus,
                gigachat_service=gigachat
            )
            
            logger.info(f"✅ {len(self.agents)} agents initialized")
            
            # Orchestrator
            self.orchestrator = MultiAgentOrchestrator(
                db=self.db,
                message_bus=self.message_bus
            )
            logger.info("✅ Orchestrator initialized")
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}", exc_info=True)
            raise
    
    async def start_agents(self):
        """Запуск агентов."""
        logger.info("\n🚀 Starting agents...")
        
        for name, agent in self.agents.items():
            task = asyncio.create_task(agent.start_listening())
            self.agent_tasks.append(task)
            logger.info(f"   🎧 {name.capitalize()}Agent listening...")
        
        # Даём агентам время подписаться
        await asyncio.sleep(2)
        logger.info("✅ All agents ready\n")
    
    async def run_test(self):
        """Запустить тест адаптивного планирования."""
        logger.info("=" * 80)
        logger.info("🎬 TEST: Adaptive Planning - Cinema Statistics in Moscow")
        logger.info("=" * 80)
        logger.info("")
        
        user_id = uuid4()
        board_id = uuid4()
        user_message = "Найди статистику просмотра кино жителями Москвы и создай визуализацию"
        
        logger.info(f"👤 User ID: {user_id}")
        logger.info(f"📋 Board ID: {board_id}")
        logger.info(f"💬 Request: {user_message}")
        logger.info("")
        logger.info("=" * 80)
        logger.info("🤖 STARTING MULTI-AGENT PROCESSING")
        logger.info("=" * 80)
        logger.info("")
        
        try:
            chunks = []
            async for chunk in self.orchestrator.process_user_request(
                user_id=user_id,
                board_id=board_id,
                user_message=user_message,
                chat_session_id=None,
                selected_node_ids=None,
            ):
                print(chunk, end="", flush=True)
                chunks.append(chunk)
            
            logger.info("\n")
            logger.info("=" * 80)
            logger.info("✅ TEST COMPLETED")
            logger.info("=" * 80)
            
            # Анализ результатов
            full_output = "".join(chunks)
            
            logger.info("\n📊 WORKFLOW ANALYSIS:")
            
            # Проверяем, был ли вызван SearchAgent
            if "SearchAgent" in full_output or "search" in full_output.lower():
                logger.info("✅ SearchAgent был задействован")
            else:
                logger.warning("⚠️ SearchAgent НЕ был задействован")
            
            # Проверяем последовательность агентов
            if "Шаг 1" in full_output:
                logger.info("✅ План был создан и выполнен")
            
            logger.info("")
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}", exc_info=True)
            raise
    
    async def cleanup(self):
        """Очистка ресурсов."""
        logger.info("\n🧹 Cleaning up...")
        
        try:
            # Остановить агентов
            for task in self.agent_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Закрыть Message Bus
            if self.message_bus:
                await self.message_bus.disconnect()
            
            # Закрыть Database
            if self.db:
                await self.db.close()
            
            # Закрыть Redis
            await close_redis()
            
            logger.info("✅ Cleanup complete")
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")


async def main():
    """Главная функция."""
    test = AdaptivePlanningTest()
    
    try:
        await test.setup()
        await test.start_agents()
        await test.run_test()
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
    finally:
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
