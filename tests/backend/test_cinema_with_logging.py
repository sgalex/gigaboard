"""
Тест полного cinema workflow с детальным логированием в MD файл.
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from app.core.redis import init_redis, close_redis
from app.services.gigachat_service import GigaChatService
from app.services.multi_agent.message_bus import AgentMessageBus
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


class CinemaWorkflowWithLogging:
    """Тестирует полный workflow с сохранением результатов в MD."""
    
    def __init__(self):
        self.gigachat = None
        self.message_bus = None
        self.agents = {}
        self.workflow_results = {}
        
        # MD лог файл
        self.md_log = []
        self.log_file = Path(__file__).parent / f"workflow_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
    def log_md(self, text: str, level: int = 0):
        """Добавляет текст в MD лог."""
        self.md_log.append(text)
        print(text)  # Также выводим в консоль
        
    async def setup(self):
        """Инициализация."""
        self.log_md("# Cinema Workflow Test Results\n")
        self.log_md(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_md("---\n")
        
        self.log_md("## Setup\n")
        
        await init_redis()
        self.log_md("✅ Redis initialized")
        
        self.gigachat = GigaChatService()
        self.log_md("✅ GigaChat initialized")
        
        self.message_bus = AgentMessageBus()
        await self.message_bus.connect()
        self.log_md("✅ Message Bus connected")
        
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
        
        self.log_md(f"✅ {len(self.agents)} agents initialized\n")
        
    async def run_workflow(self):
        """Выполняет workflow с детальным логированием."""
        
        self.log_md("## Workflow Execution\n")
        
        user_request = "Найди статистику просмотра кино жителями Москвы и создай визуализацию"
        self.log_md(f"**User Request**: {user_request}\n")
        
        # ========== STEP 1: PLANNER ==========
        self.log_md("### Step 1: Planner - Creating Execution Plan\n")
        
        plan_result = await self.agents["planner"].process_task(
            {
                "type": "create_plan",
                "user_request": user_request,
                "board_context": {"nodes": [], "edges": []}
            },
            {}
        )
        
        self.workflow_results["plan"] = plan_result
        
        if plan_result.get("status") == "success":
            steps = plan_result.get("steps", [])
            self.log_md(f"✅ **Plan created with {len(steps)} steps**:\n")
            
            for i, step in enumerate(steps, 1):
                agent = step.get("agent", "N/A")
                task_type = step.get("task", {}).get("type", "N/A")
                desc = step.get("description", "N/A")
                self.log_md(f"{i}. **{agent}** ({task_type}): {desc}")
            
            self.log_md("")
            self.log_md(f"**Reasoning**: {plan_result.get('reasoning', 'N/A')}\n")
        else:
            self.log_md(f"❌ **Planning failed**: {plan_result}\n")
            return
        
        # ========== STEP 2: SEARCH ==========
        self.log_md("### Step 2: SearchAgent - Finding Cinema Statistics\n")
        
        steps = plan_result.get("steps", [])
        search_step = next((s for s in steps if s["agent"] == "search"), None)
        
        if not search_step:
            self.log_md("❌ No search step in plan\n")
            return
        
        search_result = await self.agents["search"].process_task(
            search_step["task"],
            {}
        )
        
        self.workflow_results["search"] = search_result
        
        if search_result.get("status") == "success":
            results = search_result.get("results", [])
            self.log_md(f"✅ **Search completed**: {len(results)} results found\n")
            
            self.log_md("**Summary**:")
            self.log_md(f"> {search_result.get('summary', 'N/A')}\n")
            
            self.log_md("**Top Results**:\n")
            for i, res in enumerate(results[:5], 1):
                title = res.get("title", "N/A")
                url = res.get("url", "N/A")
                snippet = res.get("snippet", "")[:100]
                self.log_md(f"{i}. **{title}**")
                self.log_md(f"   - URL: {url}")
                if snippet:
                    self.log_md(f"   - Snippet: {snippet}...")
                self.log_md("")
        else:
            self.log_md(f"❌ **Search failed**: {search_result}\n")
        
        # ========== STEP 3: ANALYST ==========
        self.log_md("### Step 3: AnalystAgent - Analyzing Search Results\n")
        
        analyst_step = next((s for s in steps if s["agent"] == "analyst"), None)
        
        if not analyst_step:
            self.log_md("❌ No analyst step in plan\n")
            return
        
        analyst_task = analyst_step["task"].copy()
        
        analyst_result = await self.agents["analyst"].process_task(
            analyst_task,
            {"previous_results": {"search": search_result}}
        )
        
        self.workflow_results["analyst"] = analyst_result
        
        self.log_md(f"**Status**: {analyst_result.get('status', 'N/A')}\n")
        
        if analyst_result.get("status") == "success":
            insights = analyst_result.get("insights", [])
            self.log_md(f"✅ **Analysis completed**: {len(insights)} insights generated\n")
            
            if insights:
                self.log_md("**Insights**:\n")
                for i, insight in enumerate(insights[:10], 1):
                    title = insight.get("title", "N/A")
                    desc = insight.get("description", "N/A")
                    self.log_md(f"{i}. **{title}**")
                    self.log_md(f"   {desc}\n")
            
            stats = analyst_result.get("statistics", {})
            if stats:
                self.log_md("**Statistics**:")
                for key, value in stats.items():
                    self.log_md(f"- {key}: {value}")
                self.log_md("")
            
            recommendations = analyst_result.get("recommendations", [])
            if recommendations:
                self.log_md("**Recommendations**:")
                for rec in recommendations:
                    self.log_md(f"- {rec}")
                self.log_md("")
        else:
            self.log_md(f"⚠️ **Analysis status**: {analyst_result.get('status')}\n")
            
            # Логируем все поля результата для отладки
            self.log_md("**Debug - Full analyst result**:")
            self.log_md("```json")
            import json
            self.log_md(json.dumps(analyst_result, indent=2, ensure_ascii=False))
            self.log_md("```\n")
        
        # ========== STEP 4: REPORTER ==========
        self.log_md("### Step 4: ReporterAgent - Creating Visualization\n")
        
        reporter_step = next((s for s in steps if s["agent"] == "reporter"), None)
        
        if not reporter_step:
            self.log_md("❌ No reporter step in plan\n")
            return
        
        reporter_task = reporter_step["task"].copy()
        
        reporter_result = await self.agents["reporter"].process_task(
            reporter_task,
            {"previous_results": {
                "search": search_result,
                "analyst": analyst_result
            }}
        )
        
        self.workflow_results["reporter"] = reporter_result
        
        self.log_md(f"**Status**: {reporter_result.get('status', 'N/A')}\n")
        
        if reporter_result.get("status") == "success":
            viz_type = reporter_result.get("visualization_type", "N/A")
            self.log_md(f"✅ **Visualization created**: {viz_type}\n")
            
            widget = reporter_result.get("widget_node", {})
            if widget:
                html_len = len(widget.get("html", ""))
                css_len = len(widget.get("css", ""))
                js_len = len(widget.get("javascript", ""))
                self.log_md(f"**Widget Node**:")
                self.log_md(f"- HTML: {html_len} chars")
                self.log_md(f"- CSS: {css_len} chars")
                self.log_md(f"- JavaScript: {js_len} chars\n")
        else:
            self.log_md(f"⚠️ **Reporter status**: {reporter_result.get('status')}\n")
        
        # ========== SUMMARY ==========
        self.log_md("---\n")
        self.log_md("## Workflow Summary\n")
        
        self.log_md(f"- **Planner**: {len(plan_result.get('steps', []))} steps created")
        self.log_md(f"- **SearchAgent**: {len(search_result.get('results', []))} results found")
        self.log_md(f"- **AnalystAgent**: {analyst_result.get('status', 'N/A')}")
        self.log_md(f"- **ReporterAgent**: {reporter_result.get('status', 'N/A')}\n")
        
        self.log_md("✅ **All agents executed successfully!**\n")
        
    def save_log(self):
        """Сохраняет MD лог в файл."""
        content = "\n".join(self.md_log)
        self.log_file.write_text(content, encoding="utf-8")
        print(f"\n📝 Results saved to: {self.log_file}")
        
    async def cleanup(self):
        """Очистка."""
        if self.message_bus:
            await self.message_bus.disconnect()
        
        await close_redis()
        
        self.log_md("---")
        self.log_md("✅ Cleanup complete")


async def main():
    """Главная функция."""
    test = CinemaWorkflowWithLogging()
    
    try:
        await test.setup()
        await test.run_workflow()
    finally:
        await test.cleanup()
        test.save_log()


if __name__ == "__main__":
    asyncio.run(main())
