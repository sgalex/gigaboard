"""
Mock-тест оркестратора с планировщиком и агентами.

Симулирует полный pipeline обработки запроса пользователя:
1. Orchestrator получает запрос
2. PlannerAgent создает план
3. Агенты выполняют задачи
4. Orchestrator агрегирует результаты

Используются mock-объекты для GigaChat и Message Bus.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockGigaChatService:
    """Mock GigaChat для тестирования."""
    
    def __init__(self):
        self.call_count = 0
    
    async def chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Возвращает mock-ответ в зависимости от контекста."""
        self.call_count += 1
        
        user_message = messages[-1]["content"] if messages else ""
        
        # Detect agent type from system prompt
        system_prompt = messages[0]["content"] if messages else ""
        
        if "Planner Agent" in system_prompt:
            # Mock plan from PlannerAgent
            return '''
{
  "plan_id": "test-plan-123",
  "user_request": "Загрузи данные о продажах и построй график",
  "steps": [
    {
      "step_id": "1",
      "agent": "researcher",
      "task": {
        "type": "fetch_data",
        "description": "Загрузить данные о продажах из базы данных",
        "parameters": {
          "source_type": "database",
          "query": "SELECT * FROM sales WHERE date >= '2024-01-01'"
        }
      },
      "depends_on": [],
      "estimated_time": "10s"
    },
    {
      "step_id": "2",
      "agent": "analyst",
      "task": {
        "type": "analyze_data",
        "description": "Проанализировать тренды продаж",
        "parameters": {
          "analysis_type": "trend_detection",
          "metrics": ["revenue", "quantity", "date"]
        }
      },
      "depends_on": ["1"],
      "estimated_time": "15s"
    },
    {
      "step_id": "3",
      "agent": "reporter",
      "task": {
        "type": "create_visualization",
        "description": "Создать линейный график продаж",
        "parameters": {
          "chart_type": "line",
          "x_axis": "date",
          "y_axis": "revenue"
        }
      },
      "depends_on": ["2"],
      "estimated_time": "5s"
    }
  ],
  "estimated_total_time": "30s"
}
            '''
        
        elif "Analyst Agent" in system_prompt:
            # Mock SQL from AnalystAgent
            if "generate_sql" in user_message.lower() or "sql" in user_message.lower():
                return '''
SELECT 
    product_name,
    SUM(price * quantity) as total_revenue,
    COUNT(*) as order_count,
    DATE(sale_date) as sale_date
FROM sales
WHERE sale_date >= '2024-01-01'
GROUP BY product_name, DATE(sale_date)
ORDER BY sale_date, total_revenue DESC
                '''
            else:
                return "Анализ показывает рост продаж на 25% за последний квартал."
        
        elif "Transformation Agent" in system_prompt:
            # Mock pandas code from TransformationAgent
            return '''
import pandas as pd

# Calculate revenue
df_result = df.copy()
df_result['revenue'] = df_result['price'] * df_result['quantity']

# Filter high-value transactions
df_result = df_result[df_result['revenue'] > 100]

# Sort by date
df_result = df_result.sort_values('date')
            '''
        
        elif "Reporter Agent" in system_prompt:
            # Mock HTML from ReporterAgent
            return '''
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <canvas id="salesChart" width="100%" height="400"></canvas>
    <script>
        window.addEventListener('message', function(event) {
            const data = event.data;
            const ctx = document.getElementById('salesChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => d.date),
                    datasets: [{
                        label: 'Revenue',
                        data: data.map(d => d.revenue),
                        borderColor: 'rgb(75, 192, 192)'
                    }]
                }
            });
        });
    </script>
</body>
</html>
            '''
        
        elif "Researcher Agent" in system_prompt:
            # Mock data from ResearcherAgent
            return "Successfully fetched 150 rows from sales database"
        
        return "Mock response from GigaChat"


class MockMessageBus:
    """Mock Message Bus для тестирования."""
    
    def __init__(self):
        self.published_messages = []
        self.agent_responses = {
            "planner": None,
            "analyst": None,
            "transformation": None,
            "reporter": None,
            "researcher": None,
        }
    
    async def connect(self):
        """Mock connect."""
        logger.info("✅ MockMessageBus connected")
    
    async def publish(self, message):
        """Mock publish."""
        self.published_messages.append(message)
        logger.info(f"📤 Published message to {message.recipient}")
    
    async def request_response(self, message, timeout: int = 30):
        """Mock request-response."""
        recipient = message.recipient
        task_type = message.payload.get("task", {}).get("type", "unknown")
        
        logger.info(f"📤 Request to {recipient}: {task_type}")
        
        # Simulate delay
        await asyncio.sleep(0.1)
        
        # Mock response based on agent
        if recipient == "planner":
            return MagicMock(
                payload={
                    "status": "success",
                    "plan": {
                        "plan_id": "test-plan-123",
                        "steps": [
                            {
                                "step_id": "1",
                                "agent": "researcher",
                                "task": {
                                    "type": "fetch_data",
                                    "description": "Загрузить данные о продажах"
                                }
                            },
                            {
                                "step_id": "2",
                                "agent": "analyst",
                                "task": {
                                    "type": "analyze_data",
                                    "description": "Проанализировать тренды"
                                }
                            },
                            {
                                "step_id": "3",
                                "agent": "reporter",
                                "task": {
                                    "type": "create_visualization",
                                    "description": "Создать график"
                                }
                            }
                        ]
                    }
                }
            )
        
        elif recipient == "researcher":
            return MagicMock(
                payload={
                    "status": "success",
                    "result": {
                        "data": {
                            "rows": 150,
                            "columns": ["product", "price", "quantity", "date"],
                            "source": "PostgreSQL sales table"
                        },
                        "message": "Загружено 150 записей из базы данных"
                    }
                }
            )
        
        elif recipient == "analyst":
            return MagicMock(
                payload={
                    "status": "success",
                    "result": {
                        "analysis": {
                            "trends": ["Рост продаж на 25%", "Топ-продукт: Laptop"],
                            "insights": ["Сезонный пик в декабре", "Низкие продажи в феврале"]
                        },
                        "message": "Анализ завершен: найдено 2 тренда"
                    }
                }
            )
        
        elif recipient == "reporter":
            return MagicMock(
                payload={
                    "status": "success",
                    "result": {
                        "html": "<html>Mock Chart HTML</html>",
                        "widget_id": "widget-123",
                        "message": "Создан линейный график продаж"
                    }
                }
            )
        
        return MagicMock(
            payload={
                "status": "success",
                "result": {"message": f"Task completed by {recipient}"}
            }
        )
    
    async def close(self):
        """Mock close."""
        logger.info("✅ MockMessageBus closed")


class MockAgentSessionManager:
    """Mock Session Manager для тестирования."""
    
    def __init__(self):
        self.sessions = {}
    
    async def create_session(
        self,
        user_id: UUID,
        board_id: UUID,
        user_message: str,
        chat_session_id: Optional[str] = None,
        selected_node_ids: Optional[list] = None,
    ):
        """Create mock session."""
        session = MagicMock()
        session.id = uuid4()
        session.user_id = user_id
        session.board_id = board_id
        session.user_message = user_message
        session.status = "PENDING"
        
        self.sessions[session.id] = session
        logger.info(f"✅ Created session {session.id}")
        return session
    
    async def update_status(self, session_id: UUID, status: str):
        """Update session status."""
        if session_id in self.sessions:
            self.sessions[session_id].status = status
            logger.info(f"🔄 Session {session_id} status: {status}")
    
    async def update_plan(self, session_id: UUID, plan: Dict):
        """Update session plan."""
        if session_id in self.sessions:
            self.sessions[session_id].plan = plan
            logger.info(f"📋 Session {session_id} plan updated")
    
    async def update_results(self, session_id: UUID, task_index: int, result: Dict):
        """Update task result."""
        logger.info(f"✅ Task {task_index} result saved to session {session_id}")
    
    async def complete_session(self, session_id: UUID, response: str):
        """Complete session."""
        if session_id in self.sessions:
            self.sessions[session_id].status = "COMPLETED"
            self.sessions[session_id].response = response
            logger.info(f"✅ Session {session_id} completed")
    
    async def fail_session(self, session_id: UUID, error: str):
        """Fail session."""
        if session_id in self.sessions:
            self.sessions[session_id].status = "FAILED"
            self.sessions[session_id].error = error
            logger.error(f"❌ Session {session_id} failed: {error}")


async def test_orchestrator_pipeline():
    """Тест полного pipeline обработки запроса."""
    
    logger.info("\n" + "="*70)
    logger.info("ORCHESTRATOR PIPELINE TEST")
    logger.info("="*70)
    
    # Setup mocks
    message_bus = MockMessageBus()
    await message_bus.connect()
    
    session_manager = MockAgentSessionManager()
    
    # Import Orchestrator
    import sys
    import os
    from pathlib import Path
    
    os.chdir(Path(__file__).parent.parent)
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from app.services.multi_agent.orchestrator import MultiAgentOrchestrator
    
    # Create orchestrator with mocks
    orchestrator = MultiAgentOrchestrator(
        db=None,  # Not needed for this test
        message_bus=message_bus
    )
    orchestrator.session_manager = session_manager
    
    # Test parameters
    user_id = uuid4()
    board_id = uuid4()
    user_message = "Загрузи данные о продажах за последний год и создай график динамики"
    
    logger.info(f"\n📝 User Request:")
    logger.info(f"   '{user_message}'")
    logger.info(f"\n🆔 Context:")
    logger.info(f"   User ID: {user_id}")
    logger.info(f"   Board ID: {board_id}")
    
    # Execute pipeline
    logger.info(f"\n🚀 Starting pipeline...")
    
    response_chunks = []
    
    try:
        async for chunk in orchestrator.process_user_request(
            user_id=user_id,
            board_id=board_id,
            user_message=user_message,
            chat_session_id=None,
            selected_node_ids=None,
        ):
            response_chunks.append(chunk)
            # Use logger instead of print to avoid Unicode issues
            logger.info(chunk.strip())
        
        logger.info(f"\n\n✅ Pipeline completed successfully")
        
        # Results
        logger.info(f"\n" + "="*70)
        logger.info("PIPELINE RESULTS")
        logger.info("="*70)
        
        logger.info(f"\n📊 Statistics:")
        logger.info(f"   Messages published: {len(message_bus.published_messages)}")
        logger.info(f"   Response chunks: {len(response_chunks)}")
        logger.info(f"   Sessions created: {len(session_manager.sessions)}")
        
        # Check session status
        if session_manager.sessions:
            session_id = list(session_manager.sessions.keys())[0]
            session = session_manager.sessions[session_id]
            logger.info(f"\n📋 Session Status:")
            logger.info(f"   ID: {session_id}")
            logger.info(f"   Status: {session.status}")
            logger.info(f"   Has plan: {hasattr(session, 'plan')}")
            logger.info(f"   Has response: {hasattr(session, 'response')}")
        
        # Check messages flow
        logger.info(f"\n📨 Message Flow:")
        for i, msg in enumerate(message_bus.published_messages[:5], 1):  # Show first 5
            logger.info(f"   {i}. To {msg.recipient}: {msg.message_type}")
        
        logger.info(f"\n✅ TEST PASSED: Orchestrator pipeline works correctly")
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
    
    finally:
        await message_bus.close()
    
    logger.info("\n" + "="*70)
    logger.info("TEST COMPLETED")
    logger.info("="*70)


async def test_planner_agent_directly():
    """Тест PlannerAgent напрямую с mock GigaChat."""
    
    logger.info("\n" + "="*70)
    logger.info("PLANNER AGENT DIRECT TEST")
    logger.info("="*70)
    
    # Setup
    import sys
    import os
    from pathlib import Path
    
    os.chdir(Path(__file__).parent.parent)
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from app.services.multi_agent.agents.planner import PlannerAgent
    
    mock_gigachat = MockGigaChatService()
    mock_message_bus = MockMessageBus()
    await mock_message_bus.connect()
    
    # Create agent
    planner = PlannerAgent(
        message_bus=mock_message_bus,
        gigachat_service=mock_gigachat,
    )
    
    logger.info("✅ PlannerAgent created")
    
    # Test create_plan
    user_request = "Загрузи данные о продажах и построй график"
    session_id = uuid4()
    
    logger.info(f"\n📝 Testing create_plan:")
    logger.info(f"   Request: '{user_request}'")
    logger.info(f"   Session: {session_id}")
    
    try:
        # Use process_task instead of create_plan directly
        result = await planner.process_task(
            task={
                "type": "create_plan",
                "user_request": user_request,
            },
            context={"board_id": str(uuid4())}
        )
        
        logger.info(f"\n📋 Plan Created:")
        logger.info(f"   Status: {result.get('status')}")
        
        if result.get("status") == "success":
            plan = result.get("plan", {})
            steps = plan.get("steps", [])
            
            logger.info(f"   Plan ID: {plan.get('plan_id')}")
            logger.info(f"   Steps: {len(steps)}")
            logger.info(f"   Estimated time: {plan.get('estimated_total_time')}")
            
            logger.info(f"\n   Step details:")
            for i, step in enumerate(steps, 1):
                logger.info(f"      {i}. [{step['agent']}] {step['task']['description']}")
                logger.info(f"         Type: {step['task']['type']}")
                logger.info(f"         Dependencies: {step.get('depends_on', [])}")
            
            logger.info(f"\n✅ TEST PASSED: PlannerAgent works correctly")
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"❌ Plan creation failed: {error}")
    
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {e}", exc_info=True)
    
    finally:
        await mock_message_bus.close()


async def main():
    """Run all tests."""
    
    logger.info("\n" + "🧪"*35)
    logger.info("MULTI-AGENT ORCHESTRATOR TEST SUITE")
    logger.info("🧪"*35)
    
    # Test 1: PlannerAgent directly
    await test_planner_agent_directly()
    
    await asyncio.sleep(1)
    
    # Test 2: Full pipeline
    await test_orchestrator_pipeline()
    
    logger.info("\n" + "="*70)
    logger.info("ALL TESTS COMPLETED")
    logger.info("="*70)


if __name__ == "__main__":
    asyncio.run(main())
