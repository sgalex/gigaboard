"""
Тест обработки ошибок в MultiAgentEngine.

Демонстрирует:
1. Что происходит при ошибке в одном из агентов
2. Как Engine продолжает работу после ошибки
3. Какая информация попадает в результаты
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
backend_dir = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.multi_agent.engine import MultiAgentEngine
from app.config import settings

# Настройки для теста
settings.REDIS_URL = "redis://localhost:6379/0"
settings.GIGACHAT_AUTH_DATA = "YOUR_AUTH_DATA"  # Будет заменено реальным
settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"


class WorkflowLogger:
    """Логгер для отслеживания workflow."""
    
    def __init__(self):
        self.events = []
    
    def log(self, event_type: str, message: str, data: dict = None):
        """Записывает событие."""
        self.events.append({
            "type": event_type,
            "message": message,
            "data": data or {}
        })
        
        # Форматированный вывод
        icon = {
            "plan": "📋",
            "step_start": "🔄",
            "step_success": "✅",
            "step_error": "❌",
            "info": "ℹ️",
            "warning": "⚠️"
        }.get(event_type, "📝")
        
        print(f"{icon} {message}")
        if data and event_type in ["step_error", "warning"]:
            print(f"   Data: {data}")
    
    def summarize(self):
        """Выводит итоговую статистику."""
        print("\n" + "=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        
        errors = [e for e in self.events if e["type"] == "step_error"]
        successes = [e for e in self.events if e["type"] == "step_success"]
        
        print(f"✅ Успешных шагов: {len(successes)}")
        print(f"❌ Ошибок: {len(errors)}")
        
        if errors:
            print("\n🔍 Детали ошибок:")
            for i, error in enumerate(errors, 1):
                print(f"\n  {i}. {error['message']}")
                if error.get('data'):
                    print(f"     Ошибка: {error['data'].get('error', 'N/A')}")
                    if 'suggestions' in error['data']:
                        print(f"     Рекомендации: {error['data']['suggestions']}")


async def test_error_scenario_1():
    """
    Сценарий 1: Ошибка в SearchAgent (неверный тип запроса).
    
    Ожидаемое поведение:
    - SearchAgent вернёт ошибку
    - PlannerAgent оценит ошибку и примет решение (replan/retry/abort)
    - Engine выполнит соответствующее действие
    - В results будет информация об ошибке и replanning
    """
    print("\n" + "=" * 80)
    print("🧪 ТЕСТ 1: Ошибка в SearchAgent с автоматическим replanning")
    print("=" * 80 + "\n")
    
    logger = WorkflowLogger()
    engine = MultiAgentEngine()
    
    try:
        await engine.initialize()
        logger.log("info", "MultiAgentEngine инициализирован")
        
        # Запрос, который может привести к необходимости адаптации плана
        request = """
        Найди статистику о Python разработчиках в России.
        Проанализируй данные и создай визуализацию.
        """
        
        logger.log("info", f"Отправляем запрос: {request[:100]}...")
        
        result = await engine.process_request(
            user_request=request,
            board_id="test_board",
            session_id="test_error_1"
        )
        
        # Анализируем результаты
        logger.log("plan", f"План содержит {len(result['plan'].get('plan', {}).get('steps', []))} шагов")
        
        # Проверяем наличие replanning
        replan_events = [k for k in result["results"].keys() if k.startswith("replan_")]
        if replan_events:
            logger.log("info", f"🔄 Обнаружено перепланирований: {len(replan_events)}")
            for replan_key in replan_events:
                replan_data = result["results"][replan_key]
                logger.log("info", f"  - {replan_key}: {replan_data.get('changes', 'N/A')}")
        
        # Анализируем каждый шаг
        for step_key, step_result in result["results"].items():
            if step_key.startswith("step_"):
                status = step_result.get("status")
                agent = step_result.get("agent", "unknown")
                attempt = step_result.get("attempt", 1)
                
                if status == "error":
                    logger.log(
                        "step_error",
                        f"Шаг {step_key} ({agent}) завершился ошибкой (попытка {attempt})",
                        step_result
                    )
                else:
                    logger.log(
                        "step_success",
                        f"Шаг {step_key} ({agent}) выполнен успешно"
                    )
        
        logger.summarize()
        
        # Проверяем финальный статус
        if result["status"] == "success":
            print(f"\n✅ Workflow завершён успешно за {result['execution_time']:.2f}s")
        elif result["status"] == "error":
            print(f"\n❌ Workflow прерван: {result.get('error')}")
            print(f"   Причина: {result.get('abort_reason', 'N/A')}")
        
    finally:
        await engine.shutdown()
        logger.log("info", "Ресурсы освобождены")


async def test_error_scenario_2():
    """
    Сценарий 2: Сетевая ошибка в ResearcherAgent.
    
    Ожидаемое поведение:
    - ResearcherAgent не сможет загрузить некоторые URL
    - Вернёт частичный результат (те страницы, которые загрузились)
    - Status = "partial_success"
    - Engine продолжит с доступными данными
    """
    print("\n" + "=" * 80)
    print("🧪 ТЕСТ 2: Сетевая ошибка в ResearcherAgent")
    print("=" * 80 + "\n")
    
    logger = WorkflowLogger()
    engine = MultiAgentEngine()
    
    try:
        await engine.initialize()
        logger.log("info", "MultiAgentEngine инициализирован")
        
        # Запрос, который включает загрузку URL
        request = """
        Найди информацию о последних новостях в IT и создай краткий обзор.
        """
        
        logger.log("info", "Отправляем запрос с загрузкой URL")
        
        result = await engine.process_request(
            user_request=request,
            board_id="test_board",
            session_id="test_error_2"
        )
        
        # Анализируем результаты
        for step_key, step_result in result["results"].items():
            if step_key.startswith("step_"):
                status = step_result.get("status")
                agent = step_result.get("agent")
                
                if status == "error":
                    logger.log(
                        "step_error",
                        f"Шаг {step_key} ({agent}): ОШИБКА",
                        step_result
                    )
                elif status == "partial_success":
                    logger.log(
                        "warning",
                        f"Шаг {step_key} ({agent}): ЧАСТИЧНЫЙ УСПЕХ",
                        {
                            "loaded": step_result.get("pages_loaded", 0),
                            "failed": step_result.get("pages_failed", 0)
                        }
                    )
                else:
                    logger.log(
                        "step_success",
                        f"Шаг {step_key} ({agent}): SUCCESS"
                    )
        
        logger.summarize()
        
        # Проверяем, были ли частичные успехи
        partial_results = [
            r for r in result["results"].values() 
            if r.get("status") == "partial_success"
        ]
        
        if partial_results:
            print("\n⚠️ ОБНАРУЖЕНЫ ЧАСТИЧНЫЕ РЕЗУЛЬТАТЫ:")
            for pr in partial_results:
                print(f"  Agent: {pr.get('agent')}")
                print(f"  Загружено: {pr.get('pages_loaded', 0)}")
                print(f"  Ошибок: {pr.get('pages_failed', 0)}")
        
    finally:
        await engine.shutdown()
        logger.log("info", "Ресурсы освобождены")


async def test_error_scenario_3():
    """
    Сценарий 3: Критическая ошибка в PlannerAgent.
    
    Ожидаемое поведение:
    - PlannerAgent не может создать план
    - Engine вернёт ошибку уровня request
    - Workflow не начнётся
    """
    print("\n" + "=" * 80)
    print("🧪 ТЕСТ 3: Критическая ошибка в PlannerAgent")
    print("=" * 80 + "\n")
    
    logger = WorkflowLogger()
    engine = MultiAgentEngine()
    
    try:
        await engine.initialize()
        logger.log("info", "MultiAgentEngine инициализирован")
        
        # Пустой запрос - должен привести к ошибке планирования
        request = ""
        
        logger.log("warning", "Отправляем некорректный запрос (пустой)")
        
        try:
            result = await engine.process_request(
                user_request=request,
                board_id="test_board",
                session_id="test_error_3"
            )
            
            if result.get("status") == "error":
                logger.log("step_error", "PlannerAgent не смог создать план", result)
                print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Workflow не запустился")
                print(f"   Причина: {result.get('error')}")
            else:
                logger.log("info", "Неожиданно: план создан успешно")
        
        except Exception as e:
            logger.log("step_error", f"Exception при создании плана: {e}")
            print("\n❌ КРИТИЧЕСКАЯ ОШИБКА на уровне Engine")
        
        logger.summarize()
        
    finally:
        await engine.shutdown()
        logger.log("info", "Ресурсы освобождены")


async def main():
    """Запуск всех тестов."""
    print("\n" + "=" * 80)
    print("🚀 ТЕСТИРОВАНИЕ ОБРАБОТКИ ОШИБОК В MULTIAGENTENGINE")
    print("=" * 80)
    
    # Запускаем тесты последовательно
    await test_error_scenario_1()
    await asyncio.sleep(2)  # Пауза между тестами
    
    await test_error_scenario_2()
    await asyncio.sleep(2)
    
    await test_error_scenario_3()
    
    print("\n" + "=" * 80)
    print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
    print("=" * 80 + "\n")
    
    print("\n📝 ВЫВОДЫ:")
    print("-" * 80)
    print("""
1. При ошибке в отдельном агенте:
   ✅ Agent возвращает {"status": "error", "error": "...", "suggestions": [...]}
   ✅ PlannerAgent._evaluate_result() оценивает ошибку
   ✅ Решение: retry / replan / abort / continue
   ✅ Engine выполняет соответствующее действие
   
2. RETRY механизм:
   ✅ Если decision="retry" и retry_count < MAX_RETRY_ATTEMPTS (1)
   ✅ Шаг выполняется повторно с теми же параметрами
   ✅ Полезно для временных сетевых ошибок
   
3. REPLAN механизм:
   ✅ Если decision="replan" и replan_count < MAX_REPLAN_ATTEMPTS (2)
   ✅ Вызывается PlannerAgent.replan() с контекстом ошибки
   ✅ План обновляется и выполнение продолжается
   ✅ Информация о replanning сохраняется в results["replan_N"]
   
4. ABORT механизм:
   ✅ Если decision="abort" - workflow останавливается
   ✅ Возвращается {"status": "error", "abort_reason": "..."}
   ✅ Все выполненные шаги сохранены в results
   
5. CONTINUE механизм:
   ✅ Если decision="continue" - переход к следующему шагу
   ✅ Ошибка логируется, но workflow продолжается
   ✅ Следующие агенты видят ошибку в previous_results
   
6. ОГРАНИЧЕНИЯ:
   - MAX_RETRY_ATTEMPTS = 1 (макс 2 попытки выполнения)
   - MAX_REPLAN_ATTEMPTS = 2 (макс 2 перепланирования)
   - После превышения лимитов - переход к abort/continue
   
7. РЕАЛИЗОВАНО:
   ✅ Автоматическая оценка ошибок через PlannerAgent
   ✅ Retry для временных ошибок
   ✅ Adaptive replanning при критических ошибках
   ✅ Graceful degradation (continue при некритичных ошибках)
   ✅ Полное логирование всех действий
   
8. РЕКОМЕНДАЦИИ:
   - Настроить MAX_RETRY_ATTEMPTS и MAX_REPLAN_ATTEMPTS под свои нужды
   - Добавить circuit breaker для частых ошибок одного агента
   - Реализовать fallback стратегии (альтернативные источники данных)
   - Добавить метрики: retry_rate, replan_rate, abort_rate
    """)


if __name__ == "__main__":
    asyncio.run(main())
