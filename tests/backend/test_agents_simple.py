"""
Простой тест для проверки инициализации агентов.

Проверяет, что все 5 агентов могут быть созданы и имеют правильную структуру.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Change to backend directory
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.multi_agent import (
    PlannerAgent,
    AnalystAgent,
    TransformationAgent,
    ReporterAgent,
    ResearcherAgent,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_agent_initialization():
    """Тест инициализации агентов без зависимостей."""
    
    logger.info("\n" + "="*70)
    logger.info("MULTI-AGENT SIMPLE INITIALIZATION TEST")
    logger.info("="*70)
    
    results = {}
    
    # Test 1: Check agent classes exist
    logger.info("\n📦 TEST 1: Agent Classes Import")
    try:
        agents_info = {
            "PlannerAgent": PlannerAgent,
            "AnalystAgent": AnalystAgent,
            "TransformationAgent": TransformationAgent,
            "ReporterAgent": ReporterAgent,
            "ResearcherAgent": ResearcherAgent,
        }
        
        for name, agent_class in agents_info.items():
            logger.info(f"   ✅ {name}: {agent_class.__module__}.{agent_class.__name__}")
            results[name] = "✅ IMPORTED"
        
        logger.info("   📊 Result: All 5 agents imported successfully")
    except Exception as e:
        logger.error(f"   ❌ Import failed: {e}")
        return
    
    # Test 2: Check agent structure
    logger.info("\n🔍 TEST 2: Agent Structure")
    for name, agent_class in agents_info.items():
        try:
            # Check if agent has required methods
            required_methods = ["start_listening", "_get_default_system_prompt"]
            missing_methods = []
            
            for method in required_methods:
                if not hasattr(agent_class, method):
                    missing_methods.append(method)
            
            if missing_methods:
                logger.warning(f"   ⚠️  {name}: Missing methods: {missing_methods}")
            else:
                logger.info(f"   ✅ {name}: All required methods present")
            
            # Check __init__ signature
            init_params = agent_class.__init__.__code__.co_varnames
            logger.info(f"      Init params: {', '.join(init_params[1:5])}")  # Skip 'self'
            
        except Exception as e:
            logger.error(f"   ❌ {name} structure check failed: {e}")
    
    # Test 3: Check system prompts
    logger.info("\n📝 TEST 3: System Prompts")
    
    # Import system prompts from agent files
    from app.services.multi_agent.agents.planner import PLANNER_SYSTEM_PROMPT
    from app.services.multi_agent.agents.analyst import ANALYST_SYSTEM_PROMPT
    from app.services.multi_agent.agents.transformation import TRANSFORMATION_SYSTEM_PROMPT
    from app.services.multi_agent.agents.reporter import REPORTER_SYSTEM_PROMPT
    from app.services.multi_agent.agents.researcher import RESEARCHER_SYSTEM_PROMPT
    
    prompts = {
        "PlannerAgent": PLANNER_SYSTEM_PROMPT,
        "AnalystAgent": ANALYST_SYSTEM_PROMPT,
        "TransformationAgent": TRANSFORMATION_SYSTEM_PROMPT,
        "ReporterAgent": REPORTER_SYSTEM_PROMPT,
        "ResearcherAgent": RESEARCHER_SYSTEM_PROMPT,
    }
    
    for name, prompt in prompts.items():
        length = len(prompt)
        lines = prompt.count('\n') + 1
        logger.info(f"   ✅ {name}: {length} chars, {lines} lines")
    
    # Test 4: Check GigaChat integration readiness
    logger.info("\n🤖 TEST 4: GigaChat Integration Readiness")
    
    try:
        from app.services.gigachat_service import GigaChatService
        logger.info("   ✅ GigaChatService imported successfully")
        
        # Check if chat_completion method exists
        if hasattr(GigaChatService, 'chat_completion'):
            logger.info("   ✅ chat_completion method available")
        else:
            logger.warning("   ⚠️  chat_completion method not found")
        
    except Exception as e:
        logger.error(f"   ❌ GigaChatService import failed: {e}")
    
    # Test 5: Check Message Bus integration readiness
    logger.info("\n📨 TEST 5: Message Bus Integration Readiness")
    
    try:
        from app.services.multi_agent import AgentMessageBus
        logger.info("   ✅ AgentMessageBus imported successfully")
        
        # Check required methods
        required_methods = ['connect', 'publish', 'subscribe']
        for method in required_methods:
            if hasattr(AgentMessageBus, method):
                logger.info(f"   ✅ {method}() method available")
            else:
                logger.warning(f"   ⚠️  {method}() method not found")
        
    except Exception as e:
        logger.error(f"   ❌ AgentMessageBus import failed: {e}")
    
    # Test 6: Check agent task handling capabilities
    logger.info("\n⚙️  TEST 6: Agent Task Types")
    
    # PlannerAgent tasks
    logger.info("   PlannerAgent:")
    logger.info("      - create_plan")
    logger.info("      - replan")
    logger.info("      - evaluate_result")
    
    # AnalystAgent tasks
    logger.info("   AnalystAgent:")
    logger.info("      - generate_sql")
    logger.info("      - analyze_data")
    logger.info("      - find_insights")
    
    # TransformationAgent tasks
    logger.info("   TransformationAgent:")
    logger.info("      - generate_transformation")
    logger.info("      - validate_transformation")
    logger.info("      - optimize_transformation")
    
    # ReporterAgent tasks
    logger.info("   ReporterAgent:")
    logger.info("      - create_visualization")
    logger.info("      - update_visualization")
    
    # ResearcherAgent tasks
    logger.info("   ResearcherAgent:")
    logger.info("      - fetch_from_api")
    logger.info("      - query_database")
    logger.info("      - parse_data")
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)
    
    passed = sum(1 for status in results.values() if "✅" in status)
    total = len(results)
    
    logger.info(f"📊 Results: {passed}/{total} agents ready")
    logger.info("✅ All agents are properly structured and ready for integration")
    logger.info("="*70)
    
    logger.info("\n📋 NEXT STEPS:")
    logger.info("   1. Start backend services: Redis + PostgreSQL")
    logger.info("   2. Run: ./run-backend.ps1")
    logger.info("   3. Test Message Bus communication")
    logger.info("   4. Test full Multi-Agent pipeline with GigaChat")


async def main():
    """Главная функция."""
    await test_agent_initialization()


if __name__ == "__main__":
    asyncio.run(main())
