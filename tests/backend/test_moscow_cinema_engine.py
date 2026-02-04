"""
Тест Multi-Agent системы с использованием MultiAgentEngine:
Запрос "статистика просмотра кино жителями Москвы"
Генерирует подробный workflow log в markdown формате.
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

from app.services.multi_agent import MultiAgentEngine
from app.core.config import settings


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class WorkflowLogger:
    """Логгер для отслеживания workflow Multi-Agent системы."""
    
    def __init__(self):
        self.steps = []
        self.step_counter = 0
        self.start_time = None
        self.end_time = None
        self.user_request = ""
        self.plan = None
        self.results = {}
        
    def start(self, user_request: str):
        """Начало выполнения."""
        self.start_time = datetime.now()
        self.user_request = user_request
        self.log_step("START", f"Начало обработки запроса: {user_request}")
        
    def log_step(self, step_type: str, message: str, **data):
        """Логирование шага."""
        self.step_counter += 1
        step = {
            "number": self.step_counter,
            "type": step_type,
            "message": message,
            "timestamp": datetime.now(),
            "data": data
        }
        self.steps.append(step)
        
        # Emoji для разных типов
        emoji_map = {
            "START": "📍",
            "INIT": "🚀",
            "PLANNING": "💬",
            "SEARCH": "🔍",
            "RESEARCH": "🌐",
            "ANALYSIS": "📊",
            "VISUALIZATION": "📈",
            "COMPLETE": "✨",
            "ERROR": "❌"
        }
        emoji = emoji_map.get(step_type, "📝")
        
        logger.info(f"\n{emoji} STEP {self.step_counter}: {step_type}")
        logger.info(f"   {message}")
        
        if data:
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 200:
                    logger.info(f"   {key}: {value[:200]}...")
                else:
                    logger.info(f"   {key}: {value}")
        
        logger.info("-" * 70)
    
    def save_plan(self, plan_result: dict):
        """Сохранение плана выполнения."""
        plan = plan_result.get("plan", plan_result)
        self.plan = plan
        
        steps = plan.get("steps", [])
        step_descriptions = []
        for i, step in enumerate(steps, 1):
            agent = step.get("agent", "unknown")
            task_type = step.get("task", {}).get("type", "unknown")
            step_descriptions.append(f"{i}. {agent} - {task_type}")
        
        self.log_step(
            "PLANNING",
            f"План создан: {len(steps)} шагов",
            plan_id=plan.get("plan_id", "N/A"),
            steps="\n   ".join(step_descriptions)
        )
    
    def save_results(self, results: dict):
        """Сохранение результатов работы агентов."""
        self.results = results
        
        # SearchAgent
        if "search" in results:
            search = results["search"]
            if search.get("status") == "success":
                result_count = search.get("result_count", 0)
                summary = search.get("summary", "")
                self.log_step(
                    "SEARCH",
                    f"Поиск завершён: найдено {result_count} результатов",
                    summary=summary[:300] + "..." if len(summary) > 300 else summary
                )
        
        # AnalystAgent
        if "analyst" in results:
            analyst = results["analyst"]
            if analyst.get("status") == "success":
                insights = analyst.get("insights", [])
                insight_count = len(insights) if isinstance(insights, list) else 0
                
                if insight_count > 0 and isinstance(insights, list):
                    first_insight = insights[0]
                    if isinstance(first_insight, dict):
                        insight_text = f"{first_insight.get('title', 'N/A')}: {first_insight.get('description', 'N/A')[:200]}"
                    else:
                        insight_text = str(first_insight)[:200]
                else:
                    insight_text = "Нет инсайтов"
                
                self.log_step(
                    "ANALYSIS",
                    f"Анализ завершён: {insight_count} инсайтов",
                    first_insight=insight_text
                )
        
        # ResearcherAgent
        if "researcher" in results:
            researcher = results["researcher"]
            if researcher.get("status") == "success":
                pages_fetched = researcher.get("pages_fetched", 0)
                pages_failed = researcher.get("pages_failed", 0)
                total_bytes = researcher.get("total_content_bytes", 0)
                
                self.log_step(
                    "RESEARCH",
                    f"Загружено страниц: {pages_fetched}/{pages_fetched + pages_failed}",
                    total_content=f"{total_bytes:,} bytes",
                    failed=pages_failed
                )
        
        # ReporterAgent
        if "reporter" in results:
            reporter = results["reporter"]
            if reporter.get("status") == "success":
                visualization = reporter.get("visualization", {})
                viz_type = visualization.get("type", "N/A") if isinstance(visualization, dict) else "N/A"
                title = visualization.get("title", "N/A") if isinstance(visualization, dict) else "N/A"
                
                self.log_step(
                    "VISUALIZATION",
                    f"Визуализация создана: {viz_type}",
                    title=title
                )
    
    def finish(self, status: str, execution_time: float):
        """Завершение выполнения."""
        self.end_time = datetime.now()
        self.log_step(
            "COMPLETE",
            f"Workflow завершён: {status}",
            execution_time=f"{execution_time:.2f}s",
            total_steps=self.step_counter
        )
    
    def generate_markdown_report(self) -> str:
        """Генерация отчёта в Markdown."""
        lines = []
        lines.append("# 🎬 Multi-Agent Workflow Log")
        lines.append("")
        lines.append(f"**Дата выполнения:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Запрос пользователя:** {self.user_request}")
        lines.append("")
        
        # План
        if self.plan:
            lines.append("## 📋 План выполнения")
            lines.append("")
            lines.append(f"**Plan ID:** `{self.plan.get('plan_id', 'N/A')}`")
            lines.append("")
            
            steps = self.plan.get("steps", [])
            for i, step in enumerate(steps, 1):
                agent = step.get("agent", "unknown")
                task = step.get("task", {})
                task_type = task.get("type", "unknown")
                
                lines.append(f"### Шаг {i}: {agent}")
                lines.append(f"- **Тип задачи:** `{task_type}`")
                
                if "query" in task:
                    lines.append(f"- **Запрос:** {task['query']}")
                
                depends_on = step.get("depends_on", [])
                if depends_on:
                    lines.append(f"- **Зависит от шагов:** {', '.join(map(str, depends_on))}")
                
                lines.append("")
        
        # Результаты агентов
        lines.append("## 🤖 Результаты работы агентов")
        lines.append("")
        
        # SearchAgent
        if "search" in self.results:
            search = self.results["search"]
            lines.append("### 🔍 SearchAgent")
            lines.append("")
            lines.append(f"**Статус:** {search.get('status', 'N/A')}")
            
            if search.get("status") == "success":
                lines.append(f"**Найдено результатов:** {search.get('result_count', 0)}")
                lines.append(f"**Запрос:** {search.get('query', 'N/A')}")
                lines.append("")
                lines.append("**Краткое содержание:**")
                lines.append(f"```")
                lines.append(search.get('summary', 'N/A'))
                lines.append(f"```")
                lines.append("")
                
                results = search.get("results", [])
                if results:
                    lines.append("**Найденные источники:**")
                    for i, result in enumerate(results[:5], 1):
                        lines.append(f"{i}. [{result.get('title', 'N/A')}]({result.get('url', '#')})")
                        snippet = result.get('snippet', '')
                        if snippet:
                            lines.append(f"   > {snippet[:150]}...")
                    lines.append("")
        
        # ResearcherAgent
        if "researcher" in self.results:
            researcher = self.results["researcher"]
            lines.append("### 🌐 ResearcherAgent")
            lines.append("")
            lines.append(f"**Статус:** {researcher.get('status', 'N/A')}")
            
            if researcher.get("status") == "success":
                pages = researcher.get("pages", [])
                pages_fetched = researcher.get("pages_fetched", 0)
                pages_failed = researcher.get("pages_failed", 0)
                total_bytes = researcher.get("total_content_bytes", 0)
                
                lines.append(f"**Загружено страниц:** {pages_fetched}/{pages_fetched + pages_failed}")
                lines.append(f"**Всего контента:** {total_bytes:,} bytes")
                lines.append("")
                
                if pages:
                    lines.append("**Загруженные страницы:**")
                    lines.append("")
                    
                    for i, page in enumerate(pages, 1):
                        title = page.get('title', 'N/A')
                        url = page.get('url', '#')
                        content_length = len(page.get('content', ''))
                        
                        lines.append(f"#### {i}. [{title}]({url})")
                        lines.append("")
                        lines.append(f"- **URL:** {url}")
                        lines.append(f"- **Контент:** {content_length} символов")
                        lines.append(f"- **Тип:** {page.get('content_type', 'N/A')}")
                        lines.append("")
                        
                        # Показываем первые 300 символов контента
                        content = page.get('content', '')
                        if content:
                            lines.append("**Фрагмент содержимого:**")
                            lines.append("```")
                            lines.append(content[:300] + "..." if len(content) > 300 else content)
                            lines.append("```")
                            lines.append("")
                
                # Ошибки загрузки
                errors = researcher.get("errors", [])
                if errors:
                    lines.append("**Ошибки загрузки:**")
                    for error in errors:
                        lines.append(f"- `{error.get('url', 'N/A')}`: {error.get('error', 'Unknown error')}")
                    lines.append("")
        
        # AnalystAgent
        if "analyst" in self.results:
            analyst = self.results["analyst"]
            lines.append("### 📊 AnalystAgent")
            lines.append("")
            lines.append(f"**Статус:** {analyst.get('status', 'N/A')}")
            
            if analyst.get("status") == "success":
                insights = analyst.get("insights", [])
                insight_count = len(insights) if isinstance(insights, list) else 0
                lines.append(f"**Количество инсайтов:** {insight_count}")
                lines.append("")
                
                if insight_count > 0 and isinstance(insights, list):
                    lines.append("**Обнаруженные инсайты:**")
                    lines.append("")
                    
                    for i, insight in enumerate(insights, 1):
                        if isinstance(insight, dict):
                            lines.append(f"#### {i}. {insight.get('title', 'Без названия')}")
                            lines.append("")
                            lines.append(f"- **Тип:** {insight.get('type', 'N/A')}")
                            lines.append(f"- **Важность:** {insight.get('severity', 'N/A')}")
                            lines.append("")
                            
                            description = insight.get('description', '')
                            if description:
                                lines.append(f"**Описание:** {description}")
                                lines.append("")
                            
                            actions = insight.get('suggested_actions', [])
                            if actions:
                                lines.append("**Рекомендуемые действия:**")
                                for action in actions:
                                    lines.append(f"- {action}")
                                lines.append("")
                        else:
                            lines.append(f"{i}. {insight}")
                            lines.append("")
        
        # ReporterAgent
        if "reporter" in self.results:
            reporter = self.results["reporter"]
            lines.append("### 📈 ReporterAgent")
            lines.append("")
            lines.append(f"**Статус:** {reporter.get('status', 'N/A')}")
            
            if reporter.get("status") == "success":
                visualization = reporter.get("visualization", {})
                
                if isinstance(visualization, dict):
                    lines.append("")
                    lines.append(f"**Тип визуализации:** {visualization.get('type', 'N/A')}")
                    lines.append(f"**Название:** {visualization.get('title', 'N/A')}")
                    lines.append("")
                    
                    description = visualization.get('description', '')
                    if description:
                        lines.append(f"**Описание:** {description}")
                        lines.append("")
                    
                    config = visualization.get('config', {})
                    if config and isinstance(config, dict):
                        lines.append("**Конфигурация визуализации:**")
                        lines.append("```json")
                        import json
                        lines.append(json.dumps(config, indent=2, ensure_ascii=False))
                        lines.append("```")
                        lines.append("")
        
        # Общая статистика
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            lines.append("## ⏱️ Статистика выполнения")
            lines.append("")
            lines.append(f"**Время начала:** {self.start_time.strftime('%H:%M:%S')}")
            lines.append(f"**Время окончания:** {self.end_time.strftime('%H:%M:%S')}")
            lines.append(f"**Общее время выполнения:** {duration:.2f} секунд")
            lines.append(f"**Всего шагов:** {self.step_counter}")
            lines.append("")
        
        lines.append("---")
        lines.append("")
        lines.append("*Отчёт сгенерирован MultiAgentEngine*")
        
        return "\n".join(lines)
    
    def save_report_to_file(self, filename: str = None):
        """Сохранение отчёта в файл."""
        if not filename:
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            filename = f"workflow_log_moscow_cinema_{timestamp}.md"
        
        report = self.generate_markdown_report()
        
        # Сохраняем в папку tests
        output_path = Path(__file__).parent / filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        logger.info(f"\n✅ Отчёт сохранён: {output_path}")
        return output_path


async def test_moscow_cinema_workflow():
    """
    Тест: поиск статистики просмотра кино жителями Москвы
    с использованием MultiAgentEngine.
    """
    workflow_logger = WorkflowLogger()
    
    # Запрос пользователя
    user_request = "Найди статистику просмотра кино жителями Москвы и создай визуализацию с анализом данных"
    
    workflow_logger.start(user_request)
    
    try:
        # Инициализация MultiAgentEngine
        workflow_logger.log_step(
            "INIT",
            "Инициализация MultiAgentEngine"
        )
        
        engine = MultiAgentEngine(
            gigachat_api_key=settings.GIGACHAT_API_KEY
        )
        
        await engine.initialize()
        
        workflow_logger.log_step(
            "INIT",
            "Engine готов к работе",
            agents=", ".join(engine.list_agents())
        )
        
        # Выполнение запроса
        logger.info("\n" + "=" * 70)
        logger.info("НАЧАЛО ОБРАБОТКИ ЗАПРОСА")
        logger.info("=" * 70)
        
        result = await engine.process_request(
            user_request=user_request,
            board_id="board_test_moscow_cinema",
            user_id="user_test_123",
            context={
                "selected_node_ids": [],
                "board_context": {}
            }
        )
        
        logger.info("\n" + "=" * 70)
        logger.info("ОБРАБОТКА ЗАВЕРШЕНА")
        logger.info("=" * 70 + "\n")
        
        # Сохранение плана
        if "plan" in result:
            workflow_logger.save_plan(result["plan"])
        
        # Сохранение результатов
        if "results" in result:
            workflow_logger.save_results(result["results"])
        
        # Завершение
        execution_time = result.get("execution_time", 0)
        status = result.get("status", "unknown")
        
        workflow_logger.finish(status, execution_time)
        
        # Генерация и сохранение отчёта
        logger.info("\n" + "=" * 70)
        logger.info("ГЕНЕРАЦИЯ MARKDOWN ОТЧЁТА")
        logger.info("=" * 70 + "\n")
        
        report_path = workflow_logger.save_report_to_file()
        
        # Вывод краткой сводки
        logger.info("\n" + "=" * 70)
        logger.info("КРАТКАЯ СВОДКА")
        logger.info("=" * 70)
        logger.info(f"✅ Статус: {status}")
        logger.info(f"⏱️  Время выполнения: {execution_time:.2f}s")
        logger.info(f"📊 Всего шагов: {workflow_logger.step_counter}")
        logger.info(f"📄 Отчёт: {report_path}")
        logger.info("=" * 70 + "\n")
        
        # Shutdown
        await engine.shutdown()
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения: {e}", exc_info=True)
        workflow_logger.log_step("ERROR", f"Ошибка: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(test_moscow_cinema_workflow())
