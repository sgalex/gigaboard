"""
Интеграционный тест Multi-Agent системы с реальным backend.

Требует запущенного backend (Redis + PostgreSQL).
Тестирует полный цикл: User Request → Planner → Agents → Response
"""
import asyncio
import logging
from uuid import uuid4, UUID
from datetime import datetime
import sys
import os
from pathlib import Path

# Setup path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session_maker
from app.core.redis import init_redis, get_redis, close_redis
from app.core.config import settings
from app.services.multi_agent import (
    AgentMessageBus,
    AgentSessionManager,
    MultiAgentOrchestrator,
    PlannerAgent,
    AnalystAgent,
    TransformationAgent,
    ReporterAgent,
    ResearcherAgent,
)
from app.services.gigachat_service import GigaChatService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealMultiAgentTest:
    """Тест с реальными компонентами."""
    
    def __init__(self):
        self.redis = None
        self.db = None
        self.message_bus = None
        self.gigachat = None
        self.orchestrator = None
        self.agents = {}
        self.agent_tasks = []
        
    async def setup(self):
        """Инициализация реальных компонентов."""
        logger.info("🔧 Setting up real Multi-Agent environment...")
        
        try:
            # Initialize Redis first
            await init_redis()
            logger.info("✅ Redis initialized")
            
            # Redis
            self.redis = await get_redis()
            logger.info("✅ Redis connected")
            
            # Database
            self.db = async_session_maker()
            logger.info("✅ Database session created")
            
            # GigaChat Service (читает из .env через settings)
            if not settings.GIGACHAT_API_KEY:
                logger.warning("⚠️  GIGACHAT_API_KEY not found in .env - tests will fail")
            
            self.gigachat = GigaChatService(api_key=settings.GIGACHAT_API_KEY)
            logger.info("✅ GigaChat service initialized")
            
            # Message Bus
            self.message_bus = AgentMessageBus()
            await self.message_bus.connect()
            logger.info("✅ Message Bus connected")
            
            # Orchestrator
            self.orchestrator = MultiAgentOrchestrator(
                db=self.db,
                message_bus=self.message_bus
            )
            logger.info("✅ Orchestrator created")
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}", exc_info=True)
            raise
    
    async def start_agents(self):
        """Запустить агентов в listening mode."""
        logger.info("🤖 Starting agents in listening mode...")
        
        try:
            # Create agents
            self.agents = {
                "planner": PlannerAgent(
                    message_bus=self.message_bus,
                    gigachat_service=self.gigachat,
                ),
                "analyst": AnalystAgent(
                    message_bus=self.message_bus,
                    gigachat_service=self.gigachat,
                ),
                "transformation": TransformationAgent(
                    message_bus=self.message_bus,
                    gigachat_service=self.gigachat,
                ),
                "reporter": ReporterAgent(
                    message_bus=self.message_bus,
                    gigachat_service=self.gigachat,
                ),
                "researcher": ResearcherAgent(
                    message_bus=self.message_bus,
                    gigachat_service=self.gigachat,
                ),
            }
            
            logger.info(f"✅ Created {len(self.agents)} agents")
            
            # Start listening tasks
            for name, agent in self.agents.items():
                task = asyncio.create_task(agent.start_listening())
                self.agent_tasks.append(task)
                logger.info(f"   🎧 {name.capitalize()}Agent listening...")
            
            # Wait for agents to initialize
            await asyncio.sleep(1)
            logger.info("✅ All agents ready")
            
        except Exception as e:
            logger.error(f"❌ Failed to start agents: {e}", exc_info=True)
            raise
    
    async def test_simple_request(self):
        """Тест простого запроса через Orchestrator."""
        logger.info("\n" + "="*70)
        logger.info("TEST: Simple User Request")
        logger.info("="*70)
        
        # Real test user and board IDs from database
        user_id = UUID('bba55118-52c1-4741-9eac-90c3674f9bcb')
        board_id = UUID('5e645575-49c6-4055-af14-533bfa2c772e')
        user_message = "Создай простой текстовый ответ"
        
        logger.info(f"📝 User: {user_message}")
        logger.info(f"🆔 User ID: {user_id}")
        logger.info(f"🆔 Board ID: {board_id}")
        
        try:
            logger.info("\n🚀 Sending request to Orchestrator...")
            
            chunks = []
            async for chunk in self.orchestrator.process_user_request(
                user_id=user_id,
                board_id=board_id,
                user_message=user_message,
            ):
                chunks.append(chunk)
                logger.info(f"   📨 {chunk.strip()}")
            
            logger.info(f"\n✅ Received {len(chunks)} response chunks")
            return True
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}", exc_info=True)
            return False
    
    async def test_multi_agent_request(self):
        """Тест сложного запроса с планированием."""
        logger.info("\n" + "="*70)
        logger.info("TEST: Multi-Agent Request with Planning")
        logger.info("="*70)
        
        # Real test user and board IDs from database
        user_id = UUID('bba55118-52c1-4741-9eac-90c3674f9bcb')
        board_id = UUID('5e645575-49c6-4055-af14-533bfa2c772e')
        user_message = "Проанализируй современные тенденции в инвестиционных стратегиях"
        
        logger.info(f"📝 User: {user_message}")
        logger.info(f"🆔 User ID: {user_id}")
        logger.info(f"🆔 Board ID: {board_id}")
        
        try:
            logger.info("\n🚀 Sending complex request to Orchestrator...")
            
            # Workflow log для отслеживания шагов
            workflow_log = []
            step_counter = 0
            current_agent = None
            agent_results = {}
            
            def log_step(step_type: str, message: str, data: dict = None):
                nonlocal step_counter
                step_counter += 1
                timestamp = asyncio.get_event_loop().time()
                
                log_entry = {
                    "step": step_counter,
                    "type": step_type,
                    "message": message,
                    "timestamp": timestamp,
                    "data": data or {}
                }
                workflow_log.append(log_entry)
                
                # Форматированный вывод
                logger.info(f"\n{'='*70}")
                logger.info(f"📍 STEP {step_counter}: {step_type.upper()}")
                logger.info(f"{'='*70}")
                logger.info(f"💬 {message}")
                if data:
                    for key, value in data.items():
                        if isinstance(value, dict) or isinstance(value, list):
                            import json
                            logger.info(f"   📊 {key}:")
                            logger.info(f"      {json.dumps(value, indent=6, ensure_ascii=False)[:500]}")
                        else:
                            logger.info(f"   📊 {key}: {value}")
                logger.info(f"{'='*70}\n")
            
            log_step("START", "Начало обработки запроса пользователя", {
                "user_message": user_message,
                "user_id": str(user_id),
                "board_id": str(board_id)
            })
            
            chunks = []
            chunk_count = 0
            plan_steps = []  # Для сбора шагов плана
            
            import re  # Импортируем re один раз в начале
            
            async for chunk in self.orchestrator.process_user_request(
                user_id=user_id,
                board_id=board_id,
                user_message=user_message,
            ):
                chunks.append(chunk)
                chunk_count += 1
                chunk_lower = chunk.lower().strip()
                
                # Логируем разные типы chunks
                if "план создан" in chunk_lower:
                    # Извлекаем количество шагов
                    match = re.search(r'(\d+)\s*шаг', chunk)
                    num_steps = match.group(1) if match else "N/A"
                    log_step("PLANNING", f"Planner Agent создал план выполнения", {
                        "plan_chunk": chunk.strip(),
                        "num_steps": num_steps
                    })
                    
                elif re.match(r'\s*\d+\.\s*\[', chunk):
                    # Это строка с деталями шага плана: "   1. [RESEARCHER] описание"
                    plan_steps.append(chunk.strip())
                    logger.info(f"   📝 {chunk.strip()}")
                    
                elif "тип:" in chunk_lower or "зависимости:" in chunk_lower:
                    # Детали шага
                    logger.info(f"      {chunk.strip()}")
                    
                elif "шаг" in chunk_lower and "agent:" in chunk_lower:
                    # Новый шаг выполнения
                    # Извлекаем agent name
                    agent_match = re.search(r'Agent:\s*(\w+)', chunk, re.IGNORECASE)
                    if agent_match:
                        current_agent = agent_match.group(1)
                    
                    # Извлекаем описание задачи
                    task_match = re.search(r'\d+/\d+:\s*(.+?)\s*\(Agent', chunk)
                    task_desc = task_match.group(1) if task_match else "Unknown task"
                    
                    log_step("AGENT_TASK", f"{current_agent or 'Unknown'} Agent начал выполнение задачи", {
                        "agent": current_agent or "Unknown",
                        "task": task_desc,
                        "raw_chunk": chunk.strip()
                    })
                    
                elif "задача" in chunk_lower and "выполнена" in chunk_lower:
                    # Задача выполнена
                    import re
                    task_num_match = re.search(r'Задача\s*(\d+)', chunk)
                    task_num = task_num_match.group(1) if task_num_match else "N/A"
                    
                    result_info = {
                        "task_number": task_num,
                        "agent": current_agent or "Unknown",
                        "status": "успешно" if "✅" in chunk else "с предупреждениями"
                    }
                    
                    if current_agent:
                        agent_results[current_agent] = result_info
                    
                    log_step("AGENT_RESULT", f"{current_agent or 'Unknown'} Agent завершил задачу", result_info)
                    
                elif "собираю результаты" in chunk_lower or "агрег" in chunk_lower:
                    log_step("AGGREGATION", "Orchestrator агрегирует результаты всех агентов", {
                        "agents_completed": list(agent_results.keys()),
                        "total_tasks": len(agent_results)
                    })
                    
                elif "обработка завершена" in chunk_lower:
                    log_step("FINALIZATION", "Финальный ответ сформирован", {
                        "total_agents_used": len(agent_results)
                    })
                else:
                    # Обычные chunks - только логируем без workflow
                    logger.info(f"   📨 Chunk #{chunk_count}: {chunk.strip()[:80]}...")
            
            log_step("COMPLETE", "Обработка запроса завершена", {
                "total_chunks": len(chunks),
                "total_workflow_steps": step_counter,
                "agents_used": list(agent_results.keys())
            })
            
            # Выводим summary workflow
            logger.info("\n" + "="*70)
            logger.info("📋 WORKFLOW SUMMARY")
            logger.info("="*70)
            for entry in workflow_log:
                logger.info(f"{entry['step']}. [{entry['type']}] {entry['message']}")
                if entry.get('data') and entry['type'] in ['AGENT_TASK', 'AGENT_RESULT']:
                    for key, val in entry['data'].items():
                        if key not in ['raw_chunk']:  # Скрываем raw_chunk в summary
                            logger.info(f"      • {key}: {val}")
            logger.info("="*70 + "\n")
            
            # Выводим детали плана, если он был создан
            if plan_steps:
                logger.info("\n" + "="*70)
                logger.info("📝 CREATED PLAN DETAILS")
                logger.info("="*70)
                for step in plan_steps:
                    logger.info(f"  {step}")
                logger.info("="*70 + "\n")
            
            # Выводим результаты каждого агента
            if agent_results:
                logger.info("\n" + "="*70)
                logger.info("🤖 AGENT RESULTS SUMMARY")
                logger.info("="*70)
                for agent, result in agent_results.items():
                    logger.info(f"\n👉 {agent.upper()} Agent:")
                    for key, val in result.items():
                        logger.info(f"   • {key}: {val}")
                logger.info("="*70 + "\n")
            
            logger.info(f"\n✅ Received {len(chunks)} response chunks")
            return True
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}", exc_info=True)
            return False
    
    async def test_planner_direct(self):
        """Тест прямого вызова PlannerAgent."""
        logger.info("\n" + "="*70)
        logger.info("TEST: Direct PlannerAgent Call")
        logger.info("="*70)
        
        session_id = uuid4()
        user_request = "Найди данные о погоде и построй прогноз"
        
        logger.info(f"📝 Request: {user_request}")
        logger.info(f"🆔 Session: {session_id}")
        
        try:
            planner = self.agents["planner"]
            
            result = await planner.process_task(
                task={
                    "type": "create_plan",
                    "user_request": user_request,
                },
                context={"board_id": str(uuid4())}
            )
            
            if result.get("status") == "success":
                plan = result.get("plan", {})
                steps = plan.get("steps", [])
                
                logger.info(f"\n✅ Plan created:")
                logger.info(f"   Plan ID: {plan.get('plan_id')}")
                logger.info(f"   Steps: {len(steps)}")
                
                for i, step in enumerate(steps, 1):
                    logger.info(f"   {i}. [{step['agent']}] {step['task']['description']}")
                
                return True
            else:
                logger.error(f"❌ Plan creation failed: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Test failed: {e}", exc_info=True)
            return False
    
    async def run_all_tests(self):
        """Запустить все тесты."""
        logger.info("\n" + "🚀"*35)
        logger.info("REAL MULTI-AGENT INTEGRATION TEST SUITE")
        logger.info("🚀"*35 + "\n")
        
        start_time = datetime.now()
        results = {}
        
        try:
            await self.setup()
            await self.start_agents()
            
            # Test 1: Direct PlannerAgent
            logger.info("\n" + "="*70)
            logger.info("Running Test 1/3: Direct PlannerAgent")
            logger.info("="*70)
            results["planner_direct"] = await self.test_planner_direct()
            await asyncio.sleep(2)
            
            # Test 2: Simple request
            logger.info("\n" + "="*70)
            logger.info("Running Test 2/3: Simple Request")
            logger.info("="*70)
            results["simple_request"] = await self.test_simple_request()
            await asyncio.sleep(2)
            
            # Test 3: Complex multi-agent request
            logger.info("\n" + "="*70)
            logger.info("Running Test 3/3: Multi-Agent Request")
            logger.info("="*70)
            results["multi_agent_request"] = await self.test_multi_agent_request()
            
            # Summary
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info("\n" + "="*70)
            logger.info("TEST SUMMARY")
            logger.info("="*70)
            
            for test_name, passed in results.items():
                status = "✅ PASSED" if passed else "❌ FAILED"
                logger.info(f"{status} {test_name}")
            
            passed = sum(1 for p in results.values() if p)
            total = len(results)
            
            logger.info(f"\n📊 Results: {passed}/{total} tests passed")
            logger.info(f"⏱️  Duration: {duration:.2f}s")
            
            if passed == total:
                logger.info("🎉 All tests passed!")
            else:
                logger.warning(f"⚠️  {total - passed} test(s) failed")
            
            logger.info("="*70)
            
        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}", exc_info=True)
        
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Очистка ресурсов."""
        logger.info("\n🧹 Cleaning up...")
        
        # Stop agents
        for task in self.agent_tasks:
            task.cancel()
        
        # Wait for cancellation
        if self.agent_tasks:
            await asyncio.gather(*self.agent_tasks, return_exceptions=True)
        
        # Close ResearcherAgent HTTP client
        if "researcher" in self.agents:
            try:
                await self.agents["researcher"].__aexit__(None, None, None)
            except:
                pass
        
        # Close Message Bus
        if self.message_bus:
            try:
                await self.message_bus.disconnect()
            except:
                pass
        
        # Close Database
        if self.db:
            try:
                await self.db.close()
            except:
                pass
        
        # Close Redis
        if self.redis:
            try:
                await self.redis.close()
            except:
                pass
        
        logger.info("✅ Cleanup completed")


async def main():
    """Главная функция."""
    test = RealMultiAgentTest()
    await test.run_all_tests()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
