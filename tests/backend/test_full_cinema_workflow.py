"""
Полный интеграционный тест: поиск статистики кино в Москве через Multi-Agent систему.

Workflow:
1. Planner создаёт план
2. SearchAgent ищет данные в интернете
3. AnalystAgent анализирует найденные данные
4. ReporterAgent создаёт рекомендацию визуализации
"""
import asyncio
import logging
import sys
import os
from pathlib import Path
import json

# Setup path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.redis import init_redis, close_redis
from app.core.config import settings
from app.services.multi_agent import AgentMessageBus, PlannerAgent, SearchAgent, AnalystAgent, ReporterAgent
from app.services.gigachat_service import GigaChatService

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CinemaWorkflowTest:
    """Интеграционный тест полного workflow."""
    
    def __init__(self):
        self.message_bus = None
        self.agents = {}
        self.agent_tasks = []
        self.workflow_results = {}
        
    async def setup(self):
        """Инициализация."""
        logger.info("\n" + "=" * 80)
        logger.info("🔧 SETUP: Full Cinema Workflow Test")
        logger.info("=" * 80 + "\n")
        
        # Redis
        await init_redis()
        logger.info("✅ Redis connected")
        
        # GigaChat
        gigachat = GigaChatService(
            api_key=settings.GIGACHAT_API_KEY,
            model=settings.GIGACHAT_MODEL,
            scope=settings.GIGACHAT_SCOPE,
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
        
        self.agents["analyst"] = AnalystAgent(
            message_bus=self.message_bus,
            gigachat_service=gigachat
        )
        
        self.agents["reporter"] = ReporterAgent(
            message_bus=self.message_bus,
            gigachat_service=gigachat
        )
        
        logger.info(f"✅ {len(self.agents)} agents initialized\n")
    
    async def run_workflow(self):
        """Запустить полный workflow."""
        user_request = "Найди статистику просмотра кино жителями Москвы и создай визуализацию"
        
        logger.info("=" * 80)
        logger.info("🎬 STARTING FULL CINEMA WORKFLOW")
        logger.info("=" * 80)
        logger.info(f"\n💬 User Request: {user_request}\n")
        
        try:
            # ========== STEP 1: PLANNER ==========
            logger.info("─" * 80)
            logger.info("📋 STEP 1: PLANNER - Creating execution plan")
            logger.info("─" * 80 + "\n")
            
            plan_task = {
                "type": "create_plan",
                "user_request": user_request
            }
            
            plan_result = await self.agents["planner"].process_task(plan_task, {})
            
            if plan_result.get("status") != "success":
                logger.error(f"❌ Planner failed: {plan_result}")
                return
            
            plan = plan_result.get("plan", {})
            steps = plan.get("steps", [])
            
            logger.info(f"✅ Plan created with {len(steps)} steps:")
            for i, step in enumerate(steps, 1):
                logger.info(f"   {i}. {step['agent']} ({step['task']['type']})")
            
            self.workflow_results["plan"] = plan
            logger.info("")
            
            # ========== STEP 2: SEARCH ==========
            logger.info("─" * 80)
            logger.info("🔍 STEP 2: SEARCH - Finding cinema statistics online")
            logger.info("─" * 80 + "\n")
            
            search_step = next((s for s in steps if s["agent"] == "search"), None)
            if not search_step:
                logger.error("❌ No search step found in plan!")
                return
            
            search_result = await self.agents["search"].process_task(
                search_step["task"],
                {}
            )
            
            if search_result.get("status") == "success":
                results_count = len(search_result.get("results", []))
                logger.info(f"✅ Search completed: {results_count} results found")
                
                if search_result.get("summary"):
                    logger.info(f"\n📝 Summary: {search_result['summary'][:200]}...\n")
                
                # Показываем топ результаты
                logger.info("🔗 Top search results:")
                for i, res in enumerate(search_result.get("results", [])[:3], 1):
                    logger.info(f"   {i}. {res.get('title', 'N/A')}")
                    logger.info(f"      {res.get('url', 'N/A')}\n")
            else:
                logger.warning(f"⚠️ Search returned: {search_result.get('status')}")
            
            self.workflow_results["search"] = search_result
            logger.info("")
            
            # ========== STEP 3: ANALYST ==========
            logger.info("─" * 80)
            logger.info("📊 STEP 3: ANALYST - Analyzing search results")
            logger.info("─" * 80 + "\n")
            
            analyst_step = next((s for s in steps if s["agent"] == "analyst"), None)
            if analyst_step:
                # Передаём данные из search через context.previous_results
                analyst_task = analyst_step["task"].copy()
                
                analyst_result = await self.agents["analyst"].process_task(
                    analyst_task,
                    {"previous_results": {"search": search_result}}
                )
                
                if analyst_result.get("status") == "completed":
                    insights = analyst_result.get("insights", [])
                    logger.info(f"✅ Analysis completed: {len(insights)} insights generated\n")
                    
                    logger.info("💡 Key Insights:")
                    for i, insight in enumerate(insights[:5], 1):
                        title = insight.get("title", "N/A")
                        logger.info(f"   {i}. {title}")
                    logger.info("")
                else:
                    logger.warning(f"⚠️ Analysis returned: {analyst_result.get('status')}")
                
                self.workflow_results["analyst"] = analyst_result
            else:
                logger.info("ℹ️ No analyst step in plan\n")
            
            # ========== STEP 4: REPORTER ==========
            logger.info("─" * 80)
            logger.info("📈 STEP 4: REPORTER - Creating visualization recommendation")
            logger.info("─" * 80 + "\n")
            
            reporter_step = next((s for s in steps if s["agent"] == "reporter"), None)
            if reporter_step:
                # Передаём результаты предыдущих шагов
                reporter_task = reporter_step["task"].copy()
                reporter_task["analysis_results"] = self.workflow_results.get("analyst")
                reporter_task["search_results"] = search_result
                
                reporter_result = await self.agents["reporter"].process_task(
                    reporter_task,
                    {
                        "previous_results": {
                            "search": search_result,
                            "analyst": self.workflow_results.get("analyst")
                        }
                    }
                )
                
                if reporter_result.get("status") == "completed":
                    widget_type = reporter_result.get("widget_type", "N/A")
                    description = reporter_result.get("description", "N/A")
                    
                    logger.info(f"✅ Visualization recommendation created")
                    logger.info(f"\n📊 Widget Type: {widget_type}")
                    logger.info(f"📝 Description: {description[:200]}...\n")
                else:
                    logger.warning(f"⚠️ Reporter returned: {reporter_result.get('status')}")
                
                self.workflow_results["reporter"] = reporter_result
            else:
                logger.info("ℹ️ No reporter step in plan\n")
            
            # ========== FINAL SUMMARY ==========
            logger.info("=" * 80)
            logger.info("✅ WORKFLOW COMPLETED SUCCESSFULLY")
            logger.info("=" * 80 + "\n")
            
            self._print_summary()
            
        except Exception as e:
            logger.error(f"\n❌ Workflow failed: {e}", exc_info=True)
    
    def _print_summary(self):
        """Вывести итоговую сводку."""
        logger.info("📊 WORKFLOW SUMMARY:")
        logger.info("")
        
        # Plan
        if "plan" in self.workflow_results:
            plan = self.workflow_results["plan"]
            logger.info(f"   📋 Plan: {len(plan.get('steps', []))} steps")
        
        # Search
        if "search" in self.workflow_results:
            search = self.workflow_results["search"]
            if search.get("status") == "success":
                logger.info(f"   🔍 Search: {len(search.get('results', []))} results found")
            else:
                logger.info(f"   🔍 Search: {search.get('status')}")
        
        # Analyst
        if "analyst" in self.workflow_results:
            analyst = self.workflow_results["analyst"]
            if analyst.get("status") == "completed":
                logger.info(f"   📊 Analysis: {len(analyst.get('insights', []))} insights")
            else:
                logger.info(f"   📊 Analysis: {analyst.get('status')}")
        
        # Reporter
        if "reporter" in self.workflow_results:
            reporter = self.workflow_results["reporter"]
            if reporter.get("status") == "completed":
                logger.info(f"   📈 Visualization: {reporter.get('widget_type', 'N/A')}")
            else:
                logger.info(f"   📈 Visualization: {reporter.get('status')}")
        
        logger.info("")
        logger.info("🎉 All agents executed successfully!")
        logger.info("")
    
    async def cleanup(self):
        """Очистка."""
        logger.info("🧹 Cleaning up...")
        
        if self.message_bus:
            await self.message_bus.disconnect()
        
        await close_redis()
        logger.info("✅ Cleanup complete\n")


async def main():
    """Главная функция."""
    test = CinemaWorkflowTest()
    
    try:
        await test.setup()
        await test.run_workflow()
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
    finally:
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
