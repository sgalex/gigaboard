"""
Тест MultiAgentEngine - единого фасада для мультиагентной системы.
"""
import asyncio
import logging

from app.services.multi_agent import MultiAgentEngine


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_engine():
    """Тестирует MultiAgentEngine."""
    
    logger.info("\n" + "=" * 80)
    logger.info("🧪 TEST: MultiAgentEngine")
    logger.info("=" * 80 + "\n")
    
    # ========== ИНИЦИАЛИЗАЦИЯ ==========
    logger.info("📋 Creating engine...")
    engine = MultiAgentEngine()
    
    logger.info("🚀 Initializing...")
    await engine.initialize()
    
    logger.info(f"✅ Engine ready: {engine.ready}")
    logger.info(f"📊 Active agents: {', '.join(engine.list_agents())}\n")
    
    # ========== ОБРАБОТКА ЗАПРОСА ==========
    logger.info("─" * 80)
    logger.info("📤 Processing user request...")
    logger.info("─" * 80 + "\n")
    
    result = await engine.process_request(
        user_request="Найди статистику просмотра кино жителями Москвы и создай визуализацию",
        board_id="board_test_123",
        user_id="user_test_456",
        context={
            "board_context": {"nodes": [], "edges": []},
            "selected_node_ids": []
        }
    )
    
    # ========== РЕЗУЛЬТАТЫ ==========
    logger.info("\n" + "─" * 80)
    logger.info("📊 RESULTS")
    logger.info("─" * 80 + "\n")
    
    logger.info(f"Status: {result.get('status')}")
    logger.info(f"Session ID: {result.get('session_id')}")
    logger.info(f"Execution time: {result.get('execution_time', 0):.2f}s\n")
    
    if result.get("status") == "success":
        plan = result.get("plan", {})
        steps = plan.get("steps", [])
        logger.info(f"✅ Plan: {len(steps)} steps")
        for i, step in enumerate(steps, 1):
            logger.info(f"   {i}. {step.get('agent')} - {step.get('task', {}).get('type')}")
        logger.info("")
        
        results = result.get("results", {})
        logger.info(f"📦 Agent results:")
        for key, value in results.items():
            if key.startswith("step_") or key in ["search", "analyst", "reporter"]:
                status = value.get("status", "N/A") if isinstance(value, dict) else "N/A"
                logger.info(f"   - {key}: {status}")
        logger.info("")
        
        # Детали от SearchAgent
        if "search" in results:
            search = results["search"]
            if search.get("status") == "success":
                logger.info(f"🔍 Search results: {search.get('result_count', 0)} found")
                logger.info(f"   Summary: {search.get('summary', 'N/A')[:100]}...")
                logger.info("")
        
        # Детали от AnalystAgent
        if "analyst" in results:
            analyst = results["analyst"]
            if analyst.get("status") == "success":
                insights = analyst.get("insights", [])
                logger.info(f"📊 Analysis: {len(insights)} insights")
                if insights and isinstance(insights, list) and len(insights) > 0:
                    first_insight = insights[0]
                    if isinstance(first_insight, dict):
                        logger.info(f"   First insight: {first_insight.get('title', 'N/A')}")
                    else:
                        logger.info(f"   First insight: {first_insight}")
                logger.info("")
        
        # Детали от ReporterAgent
        if "reporter" in results:
            reporter = results["reporter"]
            if reporter.get("status") == "success":
                viz_type = reporter.get("visualization_type", "N/A")
                logger.info(f"📈 Visualization: {viz_type}")
                logger.info("")
        
        logger.info("✅ All steps completed successfully!")
    else:
        logger.error(f"❌ Request failed: {result.get('error')}")
    
    # ========== ЗАВЕРШЕНИЕ ==========
    logger.info("\n" + "─" * 80)
    logger.info("🛑 Shutting down...")
    logger.info("─" * 80 + "\n")
    
    await engine.shutdown()
    logger.info("✅ Test completed!\n")


if __name__ == "__main__":
    asyncio.run(test_engine())
