"""
Полноценное тестирование Multi-Agent системы через Message Bus.

Функционал:
- Реальные запросы к GigaChat API
- Работа через Redis Message Bus
- Детальное логирование каждого шага
- Сбор трейсов выполнения
- Сохранение результатов для анализа

Запуск:
    uv run python tests/test_multiagent_flow.py
    
    # Или только конкретный тест:
    uv run python tests/test_multiagent_flow.py --test crypto
    
    # С подробными логами:
    uv run python tests/test_multiagent_flow.py --verbose
"""

import asyncio
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import argparse
from uuid import uuid4

# Добавляем корневую директорию в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apps.backend.app.core.config import Settings
from apps.backend.app.services.gigachat_service import GigaChatService
from apps.backend.app.services.multi_agent.message_bus import AgentMessageBus
from apps.backend.app.services.multi_agent.message_types import MessageType, AgentMessage
from apps.backend.app.services.multi_agent.agents.planner import PlannerAgent
from apps.backend.app.services.multi_agent.agents.search import SearchAgent
from apps.backend.app.services.multi_agent.agents.researcher import ResearcherAgent
from apps.backend.app.services.multi_agent.agents.analyst import AnalystAgent
from apps.backend.app.services.multi_agent.agents.transformation import TransformationAgent
from apps.backend.app.services.multi_agent.agents.reporter import ReporterAgent
from apps.backend.app.services.multi_agent.agents.critic import CriticAgent, determine_expected_outcome


@dataclass
class TestCase:
    """Структура тест-кейса."""
    id: str
    name: str
    description: str
    user_message: str
    expected_outcome: str
    tags: List[str]


@dataclass
class ExecutionTrace:
    """Трейс выполнения теста."""
    test_id: str
    timestamp: str
    user_message: str
    session_id: str
    execution_plan: Dict[str, Any]
    steps_executed: List[Dict[str, Any]]
    agent_results: Dict[str, Any]
    validation_result: Dict[str, Any]
    status: str
    error: Optional[str] = None
    duration_ms: int = 0


class MultiAgentFlowTester:
    """Система тестирования Multi-Agent flow через Message Bus."""
    
    def __init__(self, output_dir: Optional[Path] = None, verbose: bool = False):
        self.output_dir = output_dir or Path("tests/flow_traces")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        self.setup_logging()
        
        self.test_cases = self.define_test_cases()
        self.execution_traces: List[ExecutionTrace] = []
        
        # Агенты
        self.agents: Dict[str, Any] = {}
        self.message_bus: Optional[AgentMessageBus] = None
        self.gigachat: Optional[GigaChatService] = None
        
    def setup_logging(self):
        """Настройка детального логирования."""
        log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        
        # Создаём уникальное имя файла лога
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.output_dir / f"test_run_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.DEBUG if self.verbose else logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file, mode='w', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("FlowTester")
        self.logger.info(f"Логи сохраняются в: {log_file}")
        
    def define_test_cases(self) -> List[TestCase]:
        """Определение тест-кейсов."""
        return [
            TestCase(
                id="tc001",
                name="Crypto Price + Visualization",
                description="Получить цену Bitcoin и построить график",
                user_message="Получи текущую цену Bitcoin в USD и построй график изменения цены за последнюю неделю",
                expected_outcome="visualization",
                tags=["crypto", "visualization", "api"]
            ),
            TestCase(
                id="tc002",
                name="Weather Data Analysis Code",
                description="Получить погоду и написать код для анализа",
                user_message="Получи погоду в Москве на неделю и напиши Python код для расчета средней температуры",
                expected_outcome="code_generation",
                tags=["weather", "code", "analysis"]
            ),
            TestCase(
                id="tc003",
                name="AI News Research",
                description="Найти новости об AI",
                user_message="Найди последние новости о достижениях в области больших языковых моделей",
                expected_outcome="research",
                tags=["research", "ai", "news"]
            ),
        ]
    
    async def initialize_system(self, settings: Settings):
        """Инициализация Message Bus и агентов."""
        self.logger.info("\n" + "="*80)
        self.logger.info("🚀 ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ")
        self.logger.info("="*80 + "\n")
        
        # Инициализация GigaChat
        self.gigachat = GigaChatService(
            api_key=settings.GIGACHAT_API_KEY,
            model=settings.GIGACHAT_MODEL,
            temperature=settings.GIGACHAT_TEMPERATURE,
            max_tokens=settings.GIGACHAT_MAX_TOKENS,
            verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
            scope=settings.GIGACHAT_SCOPE
        )
        self.logger.info(f"✅ GigaChat инициализирован: {settings.GIGACHAT_MODEL}")
        
        # Инициализация Message Bus
        self.message_bus = AgentMessageBus()
        await self.message_bus.connect()
        self.logger.info(f"✅ Message Bus подключен к Redis")
        
        # Инициализация агентов
        self.logger.info("\n🤖 Запуск агентов:")
        
        self.agents['planner'] = PlannerAgent(
            message_bus=self.message_bus,
            gigachat_service=self.gigachat
        )
        self.logger.info("   • PlannerAgent")
        
        self.agents['search'] = SearchAgent(
            message_bus=self.message_bus,
            gigachat_service=self.gigachat
        )
        self.logger.info("   • SearchAgent")
        
        self.agents['researcher'] = ResearcherAgent(
            message_bus=self.message_bus,
            gigachat_service=self.gigachat
        )
        self.logger.info("   • ResearcherAgent")
        
        self.agents['analyst'] = AnalystAgent(
            message_bus=self.message_bus,
            gigachat_service=self.gigachat
        )
        self.logger.info("   • AnalystAgent")
        
        self.agents['transformation'] = TransformationAgent(
            message_bus=self.message_bus,
            gigachat_service=self.gigachat
        )
        self.logger.info("   • TransformationAgent")
        
        self.agents['reporter'] = ReporterAgent(
            message_bus=self.message_bus,
            gigachat_service=self.gigachat
        )
        self.logger.info("   • ReporterAgent")
        
        self.agents['critic'] = CriticAgent(
            message_bus=self.message_bus,
            gigachat_service=self.gigachat
        )
        self.logger.info("   • CriticAgent")
        
        # Запуск агентов (подписка на сообщения)
        self.logger.info("\n📡 Подписка агентов на Message Bus...")
        for agent_name, agent in self.agents.items():
            await agent.start_listening()
            self.logger.info(f"   ✅ {agent_name}")
        
        # Даём время на запуск всех listen loops
        await asyncio.sleep(0.5)
        
        self.logger.info("\n✅ Система готова к работе\n")
    
    async def shutdown_system(self):
        """Остановка системы."""
        self.logger.info("\n🛑 Остановка системы...")
        
        # Отключение Message Bus (это автоматически остановит всех агентов)
        if self.message_bus:
            await self.message_bus.disconnect()
            self.logger.info("   ✅ Message Bus отключен (все агенты остановлены)")
    
    async def run_test_case(self, test_case: TestCase) -> ExecutionTrace:
        """Выполнить один тест-кейс."""
        self.logger.info("\n" + "="*80)
        self.logger.info(f"🧪 ТЕСТ: {test_case.name} ({test_case.id})")
        self.logger.info("="*80)
        self.logger.info(f"📝 Описание: {test_case.description}")
        self.logger.info(f"💬 Запрос: {test_case.user_message}")
        self.logger.info(f"🎯 Ожидаемый результат: {test_case.expected_outcome}")
        self.logger.info("")
        
        start_time = datetime.now()
        session_id = str(uuid4())
        board_id = str(uuid4())
        
        try:
            # Шаг 1: Запрос к Planner Agent
            self.logger.info("📋 Шаг 1: Запрос плана выполнения к PlannerAgent...")
            
            plan_request = AgentMessage(
                message_id=str(uuid4()),
                message_type=MessageType.TASK_REQUEST,
                sender="orchestrator",
                receiver="planner",
                session_id=session_id,
                board_id=board_id,
                payload={
                    "task": {
                        "type": "create_plan",
                        "user_request": test_case.user_message
                    },
                    "context": {}
                }
            )
            
            # Отправляем запрос и ждём ответ
            plan_response = await self.message_bus.request_response(
                plan_request,
                timeout=30.0
            )
            
            # Извлекаем план из результата
            result_payload = plan_response.payload
            if result_payload.get('status') == 'success':
                execution_plan = result_payload.get('result', {}).get('plan', {})
            else:
                # Ошибка создания плана
                error = result_payload.get('result', {}).get('error', 'Unknown error')
                self.logger.error(f"   ❌ Ошибка создания плана: {error}")
                execution_plan = {'steps': []}
            
            total_steps = len(execution_plan.get('steps', []))
            self.logger.info(f"   ✅ План получен: {total_steps} шагов")
            
            if self.verbose and total_steps > 0:
                self.logger.info(f"\n📋 План выполнения: {total_steps} шагов")
                for i, step in enumerate(execution_plan.get('steps', []), 1):
                    agent = step.get('agent')
                    task_desc = step.get('task', {}).get('description', 'N/A')
                    self.logger.debug(f"      Шаг {i}: {agent} - {task_desc}")
            
            # Шаг 2: Выполнение задач по плану
            self.logger.info("\n🔄 Шаг 2: Выполнение задач агентами...")
            
            agent_results = {}
            steps_executed = []
            
            for i, step in enumerate(execution_plan.get('steps', []), 1):
                agent_name = step.get('agent')  # FIXED: было agent_name
                task = step.get('task', {})
                task_description = task.get('description', 'N/A')  # FIXED: было step.get('task_description')
                
                self.logger.info(f"\n   📌 Шаг {i}/{total_steps}: {agent_name}")
                self.logger.info(f"      Задача: {task_description}")
                
                # Создаём задачу для агента
                task_request = AgentMessage(
                    message_id=str(uuid4()),
                    message_type=MessageType.TASK_REQUEST,
                    sender="orchestrator",
                    receiver=agent_name,
                    session_id=session_id,
                    board_id=board_id,
                    payload={
                        "task": task,
                        "context": {
                            "step_id": step.get('step_id'),
                            "depends_on": step.get('depends_on', [])
                        }
                    }
                )
                
                try:
                    # Отправляем и ждём результат
                    task_response = await self.message_bus.request_response(
                        task_request,
                        timeout=60.0
                    )
                    
                    agent_results[agent_name] = task_response.payload
                    
                    result_size = len(str(task_response.payload))
                    self.logger.info(f"      ✅ Результат получен ({result_size} символов)")
                    
                    steps_executed.append({
                        'step_index': i,
                        'agent_name': agent_name,
                        'task_description': task_description,
                        'has_output': True,
                        'output_size': result_size
                    })
                    
                    # Сохраняем результат в Redis для доступа других агентов
                    await self.message_bus.store_session_result(
                        session_id=session_id,
                        agent_name=agent_name,
                        result=task_response.payload
                    )
                    
                except asyncio.TimeoutError:
                    self.logger.warning(f"      ⚠️  Timeout при выполнении задачи {agent_name}")
                    steps_executed.append({
                        'step_index': i,
                        'agent_name': agent_name,
                        'task_description': task_description,
                        'has_output': False,
                        'output_size': 0
                    })
                except Exception as e:
                    self.logger.error(f"      ❌ Ошибка выполнения {agent_name}: {e}")
                    steps_executed.append({
                        'step_index': i,
                        'agent_name': agent_name,
                        'task_description': task_description,
                        'has_output': False,
                        'output_size': 0
                    })
            
            # Шаг 3: Валидация через CriticAgent
            self.logger.info("\n🔍 Шаг 3: Валидация результатов через CriticAgent...")
            
            expected_outcome = determine_expected_outcome(test_case.user_message)
            self.logger.info(f"   Определён expected_outcome: {expected_outcome}")
            
            validation_request = AgentMessage(
                message_id=str(uuid4()),
                message_type=MessageType.TASK_REQUEST,
                sender="orchestrator",
                receiver="critic",
                session_id=session_id,
                board_id=board_id,
                payload={
                    "task": {
                        "type": "validate_result",
                        "original_request": test_case.user_message,
                        "expected_outcome": expected_outcome,
                        "aggregated_result": agent_results,
                        "iteration": 1,
                        "max_iterations": 3
                    },
                    "context": {}
                }
            )
            
            validation_response = await self.message_bus.request_response(
                validation_request,
                timeout=30.0
            )
            
            validation_result = validation_response.payload
            valid = validation_result.get('valid', False)
            confidence = validation_result.get('confidence', 0)
            
            valid_emoji = "✅" if valid else "❌"
            self.logger.info(f"   {valid_emoji} Valid: {valid}, Confidence: {confidence}")
            
            # Создаём трейс
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            trace = ExecutionTrace(
                test_id=test_case.id,
                timestamp=start_time.isoformat(),
                user_message=test_case.user_message,
                session_id=session_id,
                execution_plan=execution_plan,
                steps_executed=steps_executed,
                agent_results=agent_results,
                validation_result=validation_result,
                status='success',
                duration_ms=duration_ms
            )
            
            self.log_execution_results(test_case, trace)
            
            return trace
            
        except Exception as e:
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            self.logger.error(f"❌ ОШИБКА выполнения теста {test_case.id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            trace = ExecutionTrace(
                test_id=test_case.id,
                timestamp=start_time.isoformat(),
                user_message=test_case.user_message,
                session_id=session_id,
                execution_plan={},
                steps_executed=[],
                agent_results={},
                validation_result={},
                status='error',
                error=str(e),
                duration_ms=duration_ms
            )
            
            return trace
    
    def log_execution_results(self, test_case: TestCase, trace: ExecutionTrace):
        """Детальное логирование результатов выполнения."""
        self.logger.info("\n" + "="*80)
        self.logger.info("📊 РЕЗУЛЬТАТЫ ВЫПОЛНЕНИЯ")
        self.logger.info("="*80 + "\n")
        
        self.logger.info(f"⏱️  Длительность: {trace.duration_ms}ms")
        self.logger.info(f"📈 Статус: {trace.status}")
        self.logger.info(f"🆔 Session ID: {trace.session_id}")
        
        if trace.error:
            self.logger.error(f"❌ Ошибка: {trace.error}")
        
        # План выполнения
        if trace.execution_plan:
            total_steps = len(trace.execution_plan.get('steps', []))
            self.logger.info(f"\n📋 План выполнения: {total_steps} шагов")
        
        # Шаги выполнения
        if trace.steps_executed:
            self.logger.info(f"\n🔄 Выполненные шаги:")
            for step in trace.steps_executed:
                agent = step['agent_name']
                has_output = "✅" if step['has_output'] else "❌"
                output_size = step['output_size']
                self.logger.info(f"   {step['step_index']}. [{agent}] {has_output} ({output_size} символов)")
        
        # Результаты агентов
        if trace.agent_results:
            self.logger.info(f"\n🤖 Результаты агентов ({len(trace.agent_results)} шт.):")
            for agent_name, result in trace.agent_results.items():
                result_size = len(str(result))
                self.logger.info(f"   • {agent_name}: {result_size} символов")
        
        # Валидация CriticAgent
        if trace.validation_result:
            val = trace.validation_result
            valid_emoji = "✅" if val.get('valid') else "❌"
            self.logger.info(f"\n🔍 Валидация CriticAgent: {valid_emoji}")
            self.logger.info(f"   Valid: {val.get('valid')}")
            self.logger.info(f"   Confidence: {val.get('confidence')}")
            
            if val.get('message'):
                self.logger.info(f"   Message: {val['message']}")
            
            if val.get('issues'):
                self.logger.info(f"\n   ⚠️  Issues ({len(val['issues'])}):")
                for issue in val['issues']:
                    severity = issue.get('severity', 'unknown')
                    message = issue.get('message', '')
                    self.logger.info(f"      [{severity}] {message}")
        
        self.logger.info("\n" + "="*80)
    
    async def run_all_tests(self, test_filter: Optional[str] = None):
        """Запустить все тесты или отфильтрованные."""
        self.logger.info("\n" + "="*80)
        self.logger.info("🚀 ЗАПУСК MULTI-AGENT FLOW ТЕСТИРОВАНИЯ")
        self.logger.info("="*80 + "\n")
        
        # Фильтрация тест-кейсов
        tests_to_run = self.test_cases
        if test_filter:
            tests_to_run = [
                tc for tc in self.test_cases
                if test_filter.lower() in tc.id.lower() or
                   test_filter.lower() in tc.name.lower() or
                   test_filter.lower() in tc.tags
            ]
            self.logger.info(f"🔍 Фильтр: {test_filter}")
            self.logger.info(f"📋 Будет выполнено: {len(tests_to_run)}/{len(self.test_cases)} тестов\n")
        
        if not tests_to_run:
            self.logger.error(f"❌ Не найдено тестов по фильтру: {test_filter}")
            return
        
        # Инициализация системы
        settings = Settings()
        
        if not settings.GIGACHAT_API_KEY:
            self.logger.error("❌ GIGACHAT_API_KEY не установлен в .env")
            return
        
        try:
            await self.initialize_system(settings)
            
            # Выполнение тестов
            for i, test_case in enumerate(tests_to_run, 1):
                self.logger.info(f"\n📍 Прогресс: {i}/{len(tests_to_run)}")
                
                trace = await self.run_test_case(test_case)
                self.execution_traces.append(trace)
                
                # Пауза между тестами
                if i < len(tests_to_run):
                    self.logger.info("\n⏸️  Пауза 5 секунд между тестами...")
                    await asyncio.sleep(5)
            
            # Сохранение результатов
            self.save_execution_traces()
            
        finally:
            await self.shutdown_system()
    
    def save_execution_traces(self):
        """Сохранение трейсов в файлы."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Сохранение в JSON
        traces_file = self.output_dir / f"traces_{timestamp}.json"
        with open(traces_file, 'w', encoding='utf-8') as f:
            traces_data = [asdict(trace) for trace in self.execution_traces]
            json.dump(traces_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"\n💾 Трейсы сохранены: {traces_file}")
        
        # Сохранение краткого отчёта
        report_file = self.output_dir / f"report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("ОТЧЁТ О ТЕСТИРОВАНИИ MULTI-AGENT FLOW\n")
            f.write("="*80 + "\n\n")
            
            for trace in self.execution_traces:
                f.write(f"Тест: {trace.test_id}\n")
                f.write(f"Статус: {trace.status}\n")
                f.write(f"Длительность: {trace.duration_ms}ms\n")
                f.write(f"Агенты: {list(trace.agent_results.keys())}\n")
                f.write(f"Валидация: {trace.validation_result.get('valid', 'N/A')}\n")
                f.write("-"*80 + "\n\n")
        
        self.logger.info(f"📄 Отчёт сохранён: {report_file}")
        self.logger.info(f"\n💡 Для анализа flow смотрите логи выше и JSON трейсы")


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description='Multi-Agent Flow Testing')
    parser.add_argument('--test', type=str, help='Фильтр тестов (ID, название или тег)')
    parser.add_argument('--verbose', action='store_true', help='Подробные логи')
    parser.add_argument('--output', type=str, help='Директория для результатов')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output) if args.output else None
    tester = MultiAgentFlowTester(output_dir=output_dir, verbose=args.verbose)
    
    await tester.run_all_tests(test_filter=args.test)


if __name__ == "__main__":
    asyncio.run(main())
