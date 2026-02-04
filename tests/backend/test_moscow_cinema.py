"""
Тест Multi-Agent системы: запрос "статистика просмотра кино жителями Москвы"
Генерирует подробный workflow log в markdown формате.
"""
import asyncio
import logging
from datetime import datetime
import sys
import os
import re
from pathlib import Path
from uuid import uuid4

# Setup path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session_maker
from app.core.redis import init_redis, get_redis, close_redis
from app.core.config import settings
from app.services.multi_agent import (
    AgentMessageBus,
    MultiAgentOrchestrator,
    PlannerAgent,
    AnalystAgent,
    TransformationAgent,
    ReporterAgent,
    ResearcherAgent,
    SearchAgent,
)
from app.services.gigachat_service import GigaChatService


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
        self.agent_results = {}
        self.plan_details = []
        self.start_time = None
        self.end_time = None
        self.user_request = ""
        
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
            "PLANNING": "💬",
            "AGENT_TASK": "🤖",
            "AGENT_RESULT": "✅",
            "ERROR": "❌",
            "AGGREGATION": "📊",
            "FINALIZATION": "🏁",
            "COMPLETE": "✨"
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
        
    def log_plan(self, plan_steps: list):
        """Логирование созданного плана."""
        self.plan_details = plan_steps
        self.log_step("PLANNING", f"План создан: {len(plan_steps)} шагов")
        
    def log_agent_result(self, agent_name: str, result: dict):
        """Логирование результата агента."""
        self.agent_results[agent_name] = result
        
    def finish(self):
        """Завершение выполнения."""
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        self.log_step("COMPLETE", f"Выполнение завершено за {duration:.2f}с")
        
    def to_markdown(self) -> str:
        """Генерация markdown отчёта."""
        md = []
        md.append("# 📊 Multi-Agent Workflow Report")
        md.append("")
        md.append(f"**Дата выполнения:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        md.append(f"**Запрос пользователя:** {self.user_request}")
        
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            md.append(f"**Время выполнения:** {duration:.2f} секунд")
        
        md.append("")
        md.append("---")
        md.append("")
        
        # Plan Details (в начале для лучшей читаемости)
        if self.plan_details:
            md.append("## 📋 Созданный План")
            md.append("")
            md.append(f"**Всего шагов в плане:** {len(self.plan_details)}")
            md.append("")
            
            for step in self.plan_details:
                step_num = step.get('step', '?')
                agent_name = step.get('agent', 'unknown').upper()
                description = step.get('description', 'Нет описания')
                task_type = step.get('type', 'unknown')
                dependencies = step.get('dependencies', [])
                
                md.append(f"### Шаг {step_num}: [{agent_name}]")
                md.append(f"**Задача:** {description}")
                md.append(f"**Тип:** `{task_type}`")
                if dependencies:
                    md.append(f"**Зависимости:** {', '.join(map(str, dependencies))}")
                else:
                    md.append(f"**Зависимости:** нет")
                md.append("")
            
            md.append("---")
            md.append("")
        
        # Workflow Steps
        md.append("## 🔄 Детальный Workflow")
        md.append("")
        
        for step in self.steps:
            timestamp = step["timestamp"].strftime('%H:%M:%S')
            step_type = step["type"]
            message = step["message"]
            
            # Emoji для типов
            emoji_map = {
                "START": "📍",
                "PLANNING": "🧠",
                "PLAN_STEP": "📋",
                "AGENT_TASK": "🤖",
                "AGENT_RESULT": "✅",
                "ERROR": "❌",
                "FINALIZATION": "🏁",
                "COMPLETE": "✨"
            }
            emoji = emoji_map.get(step_type, "📝")
            
            md.append(f"### {emoji} Step {step['number']}: {step_type}")
            md.append(f"**Время:** {timestamp}")
            md.append(f"**Описание:** {message}")
            
            if step['data']:
                md.append("")
                md.append("**Детали:**")
                for key, value in step['data'].items():
                    if key == "results" and isinstance(value, str) and len(value) > 200:
                        # Финальные результаты - показываем целиком
                        md.append(f"```")
                        md.append(value)
                        md.append(f"```")
                    elif isinstance(value, str) and len(value) > 300:
                        md.append(f"- **{key}:**")
                        md.append(f"  ```")
                        md.append(f"  {value[:300]}...")
                        md.append(f"  ```")
                    else:
                        md.append(f"- **{key}:** `{value}`")
            
            md.append("")
            md.append("---")
            md.append("")
        
        # Agent Results Summary
        if self.agent_results:
            md.append("## 🤖 Результаты Работы Агентов")
            md.append("")
            
            for agent_name, results in self.agent_results.items():
                md.append(f"### {agent_name.upper()} Agent")
                md.append("")
                
                if isinstance(results, dict):
                    task = results.get("task", "Нет описания задачи")
                    status = results.get("status", "unknown")
                    output = results.get("output", "Нет вывода")
                    
                    md.append(f"**Задача:** {task}")
                    md.append(f"**Статус:** {status}")
                    md.append("")
                    md.append("**Результат:**")
                    md.append(f"```")
                    if isinstance(output, str):
                        md.append(output[:1000])  # Первые 1000 символов
                    else:
                        md.append(str(output)[:1000])
                    md.append("```")
                else:
                    md.append(f"```")
                    md.append(str(results)[:1000])
                    md.append("```")
                
                md.append("")
        
        # Summary
        md.append("## 📈 Итоги")
        md.append("")
        md.append(f"- **Всего шагов выполнено:** {len(self.steps)}")
        md.append(f"- **Использовано агентов:** {len(self.agent_results)}")
        
        if self.plan_details:
            md.append(f"- **Шагов в плане:** {len(self.plan_details)}")
        
        if self.end_time:
            md.append(f"- **Статус:** ✅ Успешно завершено")
        else:
            md.append(f"- **Статус:** ⏳ В процессе выполнения")
        
        md.append("")
        
        return "\n".join(md)


class MoscowCinemaTest:
    """Тест для запроса о статистике кино в Москве."""
    
    def __init__(self):
        self.redis = None
        self.db = None
        self.message_bus = None
        self.orchestrator = None
        self.agents = {}
        self.agent_tasks = []
        self.workflow_logger = WorkflowLogger()
        
    async def setup(self):
        """Инициализация компонентов."""
        logger.info("🔧 Setting up test environment...")
        
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
            
            # GigaChat Service
            if not settings.GIGACHAT_API_KEY:
                logger.warning("⚠️  GIGACHAT_API_KEY not found in .env")
            
            gigachat = GigaChatService(api_key=settings.GIGACHAT_API_KEY)
            logger.info("✅ GigaChat Service initialized")
            
            # Message Bus
            self.message_bus = AgentMessageBus()
            await self.message_bus.connect()
            logger.info("✅ Message Bus connected")
            
            # Agents
            self.agents["planner"] = PlannerAgent(
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
            
            self.agents["transformation"] = TransformationAgent(
                message_bus=self.message_bus,
                gigachat_service=gigachat
            )
            
            self.agents["search"] = SearchAgent(
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
        logger.info("🚀 Starting agents...")
        
        for name, agent in self.agents.items():
            task = asyncio.create_task(agent.start_listening())
            self.agent_tasks.append(task)
            logger.info(f"   🎧 {name.capitalize()}Agent listening...")
        
        # Даём агентам время подписаться
        await asyncio.sleep(1)
        logger.info("✅ All agents ready")
        
    async def run_test(self, user_request: str):
        """Запуск теста с пользовательским запросом."""
        
        self.workflow_logger.start(user_request)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🎬 ЗАПРОС: {user_request}")
        logger.info(f"{'='*70}\n")
        
        session_id = str(uuid4())
        plan_steps = []
        current_step_index = 0
        all_chunks = []  # Сохраняем все чанки для отладки
        
        try:
            # Запуск Orchestrator
            from uuid import UUID
            user_id = UUID('bba55118-52c1-4741-9eac-90c3674f9bcb')
            board_id = UUID('5e645575-49c6-4055-af14-533bfa2c772e')
            
            async for chunk in self.orchestrator.process_user_request(
                user_id=user_id,
                board_id=board_id,
                user_message=user_request
            ):
                chunk_text = chunk.strip() if isinstance(chunk, str) else str(chunk)
                
                # Пропускаем пустые чанки
                if not chunk_text:
                    continue
                
                # Сохраняем все чанки
                all_chunks.append(chunk_text)
                
                # Детальное логирование каждого чанка
                logger.info(f"📨 Chunk [{len(chunk_text)} chars]: {chunk_text[:200]}{'...' if len(chunk_text) > 200 else ''}")
                
                # Парсинг событий из текстовых чанков
                message = chunk_text.lower()
                
                # Отладка: Проверяем есть ли в чанке финальная агрегация
                if "**researcher**" in message or "**analyst**" in message or "**reporter**" in message:
                    logger.info(f"🔍 ОБНАРУЖЕН ВОЗМОЖНЫЙ ФИНАЛЬНЫЙ ЧАНК!")
                    logger.info(f"🔍 Проверка двоеточия: '**researcher**:' in message = {'**researcher**:' in message}")
                    logger.info(f"🔍 Проверка двоеточия: '**analyst**:' in message = {'**analyst**:' in message}")
                    logger.info(f"🔍 Проверка двоеточия: '**reporter**:' in message = {'**reporter**:' in message}")
                
                # План создан
                if "план создан" in message or "plan created" in message:
                    match = re.search(r'(\d+)\s+шаг', message)
                    if match:
                        num_steps = match.group(1)
                        self.workflow_logger.log_step(
                            "PLANNING",
                            f"Planner Agent создал план с {num_steps} шагами",
                            num_steps=num_steps
                        )
                
                # Финальный результат (весь ответ в конце) - ПРОВЕРЯЕМ ПЕРВЫМ
                elif "**researcher**:" in message or "**analyst**:" in message or "**reporter**:" in message:
                    # Это финальная агрегация результатов - парсим детально
                    logger.info(f"📝 Финальный чанк получен, длина: {len(chunk_text)} символов")
                    logger.info(f"📝 Первые 300 символов: {chunk_text[:300]}")
                    
                    self.workflow_logger.log_step(
                        "FINALIZATION",
                        "Получена сводка результатов всех агентов",
                        results=chunk_text
                    )
                    
                    # Парсим результаты каждого агента из финального ответа
                    # Формат: **AgentName**: результат работы
                    agent_sections = re.split(r'\*\*(\w+)\*\*:', chunk_text, flags=re.IGNORECASE)
                    logger.info(f"📝 Найдено секций: {len(agent_sections)}")
                    
                    for i in range(1, len(agent_sections), 2):
                        if i + 1 < len(agent_sections):
                            agent_name = agent_sections[i].lower()
                            agent_output = agent_sections[i + 1].strip()
                            logger.info(f"📝 Парсинг результата агента: {agent_name} (длина: {len(agent_output)})")
                            
                            # Обновляем результат агента с реальным выводом
                            if agent_name in self.workflow_logger.agent_results:
                                self.workflow_logger.agent_results[agent_name]["output"] = agent_output
                                logger.info(f"✅ Результат агента {agent_name} обновлён")
                            else:
                                self.workflow_logger.log_agent_result(agent_name, {
                                    "task": "Финальная агрегация",
                                    "status": "completed",
                                    "output": agent_output
                                })
                                logger.info(f"✅ Создан новый результат для агента {agent_name}")
                
                # Детали шага плана (формат: ⚙️ Шаг 1/4: описание (Agent: researcher))
                elif "шаг" in message and "(agent:" in message:
                    # Парсим: "⚙️ Шаг 1/4: Find data about Moscow cinema viewing statistics (Agent: researcher)"
                    step_match = re.search(r'шаг\s+(\d+)/(\d+):\s*(.+?)\s*\(agent:\s*(\w+)\)', message, re.IGNORECASE)
                    if step_match:
                        step_num = step_match.group(1)
                        total_steps = step_match.group(2)
                        description = step_match.group(3).strip()
                        agent_name = step_match.group(4).strip()
                        
                        step_info = {
                            "step": int(step_num),
                            "agent": agent_name,
                            "description": description,
                            "type": "unknown",
                            "dependencies": []
                        }
                        plan_steps.append(step_info)
                        
                        self.workflow_logger.log_step(
                            "PLAN_STEP",
                            f"Шаг {step_num}/{total_steps}: {description}",
                            agent=agent_name,
                            description=description
                        )
                
                # Задача выполнена (формат: ✅ Задача 1 выполнена)
                elif "задача" in message and "выполнена" in message:
                    task_match = re.search(r'задача\s+(\d+)', message)
                    if task_match:
                        task_num = int(task_match.group(1))
                        # task_num это 1-based, а plan_steps это 0-based массив
                        step_index = task_num - 1
                        if 0 <= step_index < len(plan_steps):
                            step = plan_steps[step_index]
                            self.workflow_logger.log_step(
                                "AGENT_RESULT",
                                f"Задача {task_num} выполнена: {step['description']}",
                                agent=step['agent'],
                                task=step['description'],
                                result=chunk_text
                            )
                            # Сохраняем результат для детального отчёта
                            self.workflow_logger.log_agent_result(step['agent'], {
                                "task": step['description'],
                                "status": "completed",
                                "output": chunk_text
                            })
                        else:
                            # Если номер задачи не соответствует плану, логируем как есть
                            self.workflow_logger.log_step(
                                "AGENT_RESULT",
                                f"Задача {task_num} выполнена",
                                result=chunk_text
                            )
            
            # Завершение обработки чанков
            
            # Логируем план
            if plan_steps:
                self.workflow_logger.log_plan(plan_steps)
            
            self.workflow_logger.finish()
            
            logger.info(f"\n{'='*70}")
            logger.info("✅ Тест успешно завершён")
            logger.info(f"{'='*70}\n")
            
            # Сохраняем все чанки для отладки
            chunks_file = Path(__file__).parent.parent.parent.parent / "docs" / "workflow_logs" / "all_chunks.txt"
            with open(chunks_file, "w", encoding="utf-8") as f:
                for i, chunk in enumerate(all_chunks, 1):
                    f.write(f"=== CHUNK {i} ({len(chunk)} chars) ===\n")
                    f.write(chunk)
                    f.write("\n\n")
            logger.info(f"📄 Все чанки сохранены в: {chunks_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения: {e}", exc_info=True)
            self.workflow_logger.log_step("ERROR", f"Ошибка: {str(e)}", error=str(e))
            return False
    
    def save_report(self, filename: str | None = None):
        """Сохранение отчёта в markdown файл."""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"workflow_log_{timestamp}.md"
        
        # Путь к файлу
        logs_dir = Path(__file__).parent.parent.parent.parent / "docs" / "workflow_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = logs_dir / filename
        
        # Генерация markdown
        markdown_content = self.workflow_logger.to_markdown()
        
        # Сохранение
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        logger.info(f"\n📄 Workflow log сохранён: {filepath}")
        return filepath
    
    async def cleanup(self):
        """Очистка ресурсов."""
        logger.info("\n🧹 Cleaning up...")
        
        # Stop agents
        for task in self.agent_tasks:
            task.cancel()
        
        if self.agent_tasks:
            await asyncio.gather(*self.agent_tasks, return_exceptions=True)
        
        # Close connections
        if self.message_bus:
            try:
                await self.message_bus.disconnect()
            except:
                pass
        
        # Close Redis
        try:
            await close_redis()
        except:
            pass
        
        logger.info("✅ Cleanup complete")


async def main():
    """Главная функция."""
    
    test = MoscowCinemaTest()
    
    try:
        # Setup
        await test.setup()
        await test.start_agents()
        
        # Даём агентам время на подписку
        await asyncio.sleep(2)
        
        # Запуск теста
        user_request = "Найди данные о статистике просмотра кино жителями Москвы, проанализируй тренды и создай визуализацию с графиками по жанрам и временным периодам"
        success = await test.run_test(user_request)
        
        # Сохранение отчёта
        report_path = test.save_report("moscow_cinema_workflow.md")
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 Результат: {'✅ SUCCESS' if success else '❌ FAILED'}")
        logger.info(f"📄 Отчёт: {report_path}")
        logger.info(f"{'='*70}\n")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    
    finally:
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
