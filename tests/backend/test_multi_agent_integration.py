"""
Интеграционный тест Multi-Agent системы.

Проверяет взаимодействие всех 5 агентов:
- PlannerAgent - декомпозиция задач
- AnalystAgent - SQL запросы
- TransformationAgent - pandas преобразования
- ReporterAgent - HTML визуализации
- ResearcherAgent - внешние данные
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime

# Change to backend directory
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session_maker as AsyncSessionLocal
from app.core.redis import get_redis
from app.services.multi_agent import (
    AgentMessageBus,
    AgentSessionManager,
    PlannerAgent,
    AnalystAgent,
    TransformationAgent,
    ReporterAgent,
    ResearcherAgent,
)
from app.services.gigachat_service import GigaChatService
from app.models.agent_session import AgentSessionStatus

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiAgentIntegrationTest:
    """Интеграционный тест для Multi-Agent системы."""
    
    def __init__(self):
        self.redis = None
        self.db = None
        self.message_bus = None
        self.gigachat = None
        self.agents = {}
        
    async def setup(self):
        """Инициализация компонентов."""
        logger.info("🔧 Setting up Multi-Agent test environment...")
        
        # Redis
        self.redis = await get_redis()
        await self.redis.flushdb()  # Clean Redis
        logger.info("✅ Redis connected and cleared")
        
        # Database
        self.db = AsyncSessionLocal()
        logger.info("✅ Database session created")
        
        # GigaChat Service
        self.gigachat = GigaChatService(api_key="test_key")  # Mock key for testing
        logger.info("✅ GigaChat service initialized")
        
        # Message Bus
        self.message_bus = AgentMessageBus()
        logger.info("✅ Message Bus initialized")
        
        # Session Manager
        self.session_manager = AgentSessionManager(self.db)
        logger.info("✅ Session Manager initialized")
        
    async def start_agents(self):
        """Запустить всех агентов."""
        logger.info("🤖 Starting all 5 agents...")
        
        # Create agents
        self.agents = {
            "planner": PlannerAgent(
                agent_name="planner",
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            ),
            "analyst": AnalystAgent(
                agent_name="analyst",
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            ),
            "transformation": TransformationAgent(
                agent_name="transformation",
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            ),
            "reporter": ReporterAgent(
                agent_name="reporter",
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            ),
            "researcher": ResearcherAgent(
                agent_name="researcher",
                message_bus=self.message_bus,
                gigachat_service=self.gigachat
            ),
        }
        
        # Start listening tasks
        self.agent_tasks = []
        for name, agent in self.agents.items():
            task = asyncio.create_task(agent.start_listening())
            self.agent_tasks.append(task)
            logger.info(f"✅ {name.capitalize()}Agent started (Name: {agent.agent_name})")
        
        # Wait for agents to start
        await asyncio.sleep(0.5)
        logger.info("✅ All 5 agents are listening")
        
    async def test_planner_agent(self):
        """Тест 1: PlannerAgent - создание плана."""
        logger.info("\n" + "="*70)
        logger.info("TEST 1: PlannerAgent - Task Decomposition")
        logger.info("="*70)
        
        user_request = "Загрузи данные о продажах, рассчитай средний чек и создай график"
        
        session = await self.session_manager.create_session(
            user_id=uuid4(),
            board_id=uuid4(),
            user_message=user_request,
        )
        
        logger.info(f"📝 User Request: {user_request}")
        logger.info(f"🆔 Session ID: {session.id}")
        
        # Send request to Planner
        response = await self.agents["planner"].create_plan(
            session_id=session.id,
            user_request=user_request,
            context={"board_id": str(session.board_id)}
        )
        
        logger.info(f"\n📋 Plan Created:")
        logger.info(f"   Status: {response.get('status')}")
        logger.info(f"   Tasks: {len(response.get('tasks', []))}")
        
        if response.get("status") == "success":
            for i, task in enumerate(response.get("tasks", []), 1):
                logger.info(f"   {i}. [{task['agent']}] {task['description']}")
                logger.info(f"      Dependencies: {task.get('dependencies', [])}")
        
        return response
    
    async def test_analyst_agent(self):
        """Тест 2: AnalystAgent - генерация SQL."""
        logger.info("\n" + "="*70)
        logger.info("TEST 2: AnalystAgent - SQL Generation")
        logger.info("="*70)
        
        session = await self.session_manager.create_session(
            user_id=uuid4(),
            board_id=uuid4(),
            user_message="Generate SQL query",
        )
        
        # Mock schema
        schema = {
            "table_name": "sales",
            "columns": [
                {"name": "id", "type": "INTEGER"},
                {"name": "product_name", "type": "VARCHAR"},
                {"name": "price", "type": "DECIMAL"},
                {"name": "quantity", "type": "INTEGER"},
                {"name": "sale_date", "type": "DATE"},
            ]
        }
        
        query_description = "Calculate total revenue per product for last 30 days"
        
        logger.info(f"📝 Query: {query_description}")
        logger.info(f"🗄️  Schema: {schema['table_name']} with {len(schema['columns'])} columns")
        
        response = await self.agents["analyst"].generate_sql(
            session_id=session.id,
            query_description=query_description,
            schema=schema,
        )
        
        logger.info(f"\n📊 SQL Generated:")
        logger.info(f"   Status: {response.get('status')}")
        if response.get("status") == "success":
            logger.info(f"   SQL:\n{response.get('sql', 'N/A')}")
            logger.info(f"   Explanation: {response.get('explanation', 'N/A')[:100]}...")
        
        return response
    
    async def test_transformation_agent(self):
        """Тест 3: TransformationAgent - pandas код."""
        logger.info("\n" + "="*70)
        logger.info("TEST 3: TransformationAgent - Pandas Code Generation")
        logger.info("="*70)
        
        session = await self.session_manager.create_session(
            user_id=uuid4(),
            board_id=uuid4(),
            user_message="Transform data",
        )
        
        # Mock source schema
        source_schema = {
            "columns": ["product", "price", "quantity", "date"],
            "types": ["string", "float", "integer", "datetime"],
            "sample_data": [
                {"product": "Laptop", "price": 1200.0, "quantity": 5, "date": "2026-01-01"},
                {"product": "Mouse", "price": 25.0, "quantity": 50, "date": "2026-01-02"},
            ]
        }
        
        transformation_description = "Calculate revenue (price * quantity) and filter rows where revenue > 100"
        
        logger.info(f"📝 Transformation: {transformation_description}")
        logger.info(f"📊 Source columns: {', '.join(source_schema['columns'])}")
        
        response = await self.agents["transformation"].generate_transformation(
            session_id=session.id,
            description=transformation_description,
            source_schemas=[source_schema],
        )
        
        logger.info(f"\n🔄 Transformation Generated:")
        logger.info(f"   Status: {response.get('status')}")
        if response.get("status") == "success":
            logger.info(f"   Code:\n{response.get('code', 'N/A')}")
            logger.info(f"   Validation: {'✅ Valid' if response.get('validation', {}).get('is_valid') else '❌ Invalid'}")
            warnings = response.get('validation', {}).get('warnings', [])
            if warnings:
                logger.info(f"   Warnings: {warnings}")
        
        return response
    
    async def test_reporter_agent(self):
        """Тест 4: ReporterAgent - HTML визуализация."""
        logger.info("\n" + "="*70)
        logger.info("TEST 4: ReporterAgent - Visualization Generation")
        logger.info("="*70)
        
        session = await self.session_manager.create_session(
            user_id=uuid4(),
            board_id=uuid4(),
            user_message="Create chart",
        )
        
        # Mock data schema
        data_schema = {
            "columns": ["month", "revenue", "profit"],
            "types": ["string", "float", "float"],
            "sample_data": [
                {"month": "Jan", "revenue": 10000, "profit": 2000},
                {"month": "Feb", "revenue": 15000, "profit": 3000},
                {"month": "Mar", "revenue": 12000, "profit": 2500},
            ]
        }
        
        visualization_type = "Bar chart showing revenue and profit by month"
        
        logger.info(f"📝 Visualization: {visualization_type}")
        logger.info(f"📊 Data columns: {', '.join(data_schema['columns'])}")
        logger.info(f"📈 Rows: {len(data_schema['sample_data'])}")
        
        response = await self.agents["reporter"].create_visualization(
            session_id=session.id,
            visualization_type=visualization_type,
            data_schema=data_schema,
        )
        
        logger.info(f"\n📊 Visualization Generated:")
        logger.info(f"   Status: {response.get('status')}")
        if response.get("status") == "success":
            html_code = response.get('html', '')
            logger.info(f"   HTML length: {len(html_code)} characters")
            logger.info(f"   Validation: {'✅ Valid' if response.get('validation', {}).get('is_valid') else '❌ Invalid'}")
            issues = response.get('validation', {}).get('issues', [])
            if issues:
                logger.info(f"   Issues: {issues}")
        
        return response
    
    async def test_researcher_agent(self):
        """Тест 5: ResearcherAgent - получение данных."""
        logger.info("\n" + "="*70)
        logger.info("TEST 5: ResearcherAgent - External Data Fetching")
        logger.info("="*70)
        
        session = await self.session_manager.create_session(
            user_id=uuid4(),
            board_id=uuid4(),
            user_message="Fetch data from API",
        )
        
        # Test with JSONPlaceholder API (free test API)
        url = "https://jsonplaceholder.typicode.com/posts"
        params = {"_limit": "5"}
        
        logger.info(f"📝 API URL: {url}")
        logger.info(f"🔧 Parameters: {params}")
        
        response = await self.agents["researcher"].fetch_from_api(
            session_id=session.id,
            url=url,
            method="GET",
            params=params,
        )
        
        logger.info(f"\n🌐 Data Fetched:")
        logger.info(f"   Status: {response.get('status')}")
        if response.get("status") == "success":
            data = response.get('data', {})
            logger.info(f"   Content Type: {data.get('content_type')}")
            logger.info(f"   Rows: {len(data.get('data', []))}")
            schema = data.get('schema', {})
            logger.info(f"   Columns: {', '.join(schema.get('columns', []))}")
            logger.info(f"   Source: {data.get('source')}")
        
        return response
    
    async def test_message_bus_communication(self):
        """Тест 6: Взаимодействие через Message Bus."""
        logger.info("\n" + "="*70)
        logger.info("TEST 6: Message Bus Communication")
        logger.info("="*70)
        
        session = await self.session_manager.create_session(
            user_id=uuid4(),
            board_id=uuid4(),
            user_message="Test message bus",
        )
        
        # Test request_response pattern
        logger.info("📤 Sending request to AnalystAgent via Message Bus...")
        
        request_payload = {
            "session_id": str(session.id),
            "query_description": "Get total sales",
            "schema": {"table_name": "sales", "columns": [{"name": "amount", "type": "FLOAT"}]},
        }
        
        response = await self.message_bus.request_response(
            agent_type="analyst",
            task_type="generate_sql",
            payload=request_payload,
            timeout=10.0,
        )
        
        logger.info(f"\n📥 Response received:")
        logger.info(f"   Status: {response.get('status')}")
        logger.info(f"   Response time: < 10s")
        logger.info(f"   Has SQL: {'sql' in response}")
        
        return response
    
    async def run_all_tests(self):
        """Запустить все тесты."""
        logger.info("\n" + "🚀"*35)
        logger.info("MULTI-AGENT INTEGRATION TEST SUITE")
        logger.info("🚀"*35 + "\n")
        
        start_time = datetime.now()
        results = {}
        
        try:
            await self.setup()
            await self.start_agents()
            
            # Run all tests
            tests = [
                ("PlannerAgent", self.test_planner_agent),
                ("AnalystAgent", self.test_analyst_agent),
                ("TransformationAgent", self.test_transformation_agent),
                ("ReporterAgent", self.test_reporter_agent),
                ("ResearcherAgent", self.test_researcher_agent),
                ("MessageBus", self.test_message_bus_communication),
            ]
            
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    results[test_name] = {
                        "status": "✅ PASSED" if result.get("status") == "success" else "⚠️ PARTIAL",
                        "result": result
                    }
                except Exception as e:
                    logger.error(f"❌ {test_name} failed: {e}")
                    results[test_name] = {
                        "status": "❌ FAILED",
                        "error": str(e)
                    }
            
            # Summary
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info("\n" + "="*70)
            logger.info("TEST SUMMARY")
            logger.info("="*70)
            
            for test_name, result in results.items():
                logger.info(f"{result['status']} {test_name}")
            
            passed = sum(1 for r in results.values() if "✅" in r["status"])
            total = len(results)
            
            logger.info(f"\n📊 Results: {passed}/{total} tests passed")
            logger.info(f"⏱️  Duration: {duration:.2f}s")
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
        
        # Close ResearcherAgent HTTP client
        if "researcher" in self.agents:
            await self.agents["researcher"].__aexit__(None, None, None)
        
        # Close connections
        if self.db:
            await self.db.close()
        
        if self.redis:
            await self.redis.close()
        
        logger.info("✅ Cleanup completed")


async def main():
    """Главная функция."""
    test = MultiAgentIntegrationTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
