"""
Тест адаптивного планирования в MultiAgentEngine.

Демонстрирует как система автоматически корректирует план
на основе результатов выполнения каждого шага.
"""
import asyncio
import sys
import os
from pathlib import Path

# Setup path
backend_dir = Path(__file__).parent.parent / "apps" / "backend"
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from app.services.multi_agent import MultiAgentEngine
from app.core.config import settings

# Настройки уже в settings, не нужно переопределять


async def test_adaptive_planning():
    """
    Сценарий: Запрос требующий нескольких этапов обработки.
    
    Ожидаемое поведение:
    - После каждого успешного шага PlannerAgent анализирует результаты
    - Если результаты содержат новую информацию - план корректируется
    - Могут добавляться/удаляться/изменяться шаги
    """
    print("\n" + "=" * 80)
    print("🧪 ТЕСТ: Адаптивное планирование")
    print("=" * 80 + "\n")
    
    # Engine с включенным adaptive planning
    engine = MultiAgentEngine(adaptive_planning=True)
    
    try:
        await engine.initialize()
        print("✅ MultiAgentEngine инициализирован (adaptive_planning=True)")
        
        request = """
        Найди информацию о новостях в области искусственного интеллекта за 2026 год.
        Проанализируй основные тренды и создай визуализацию.
        """
        
        print(f"\n📝 Запрос: {request.strip()}\n")
        print("=" * 80)
        
        result = await engine.process_request(
            user_request=request,
            board_id="test_board",
            session_id="adaptive_test"
        )
        
        # Анализируем результаты
        print("\n" + "=" * 80)
        print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ")
        print("=" * 80 + "\n")
        
        # Исходный план
        initial_plan = result["plan"].get("plan", {})
        initial_steps_count = len(initial_plan.get("steps", []))
        print(f"📋 Исходный план: {initial_steps_count} шагов")
        
        # Проверяем оптимизации
        optimizations = [k for k in result["results"].keys() if k.startswith("optimization_")]
        
        if optimizations:
            print(f"\n🔄 ОБНАРУЖЕНО ОПТИМИЗАЦИЙ: {len(optimizations)}")
            print("-" * 80)
            
            for opt_key in optimizations:
                opt_data = result["results"][opt_key]
                after_step = opt_data.get("after_step")
                changes = opt_data.get("changes")
                
                print(f"\n  Оптимизация после шага {after_step}:")
                print(f"  Изменения: {changes}")
                
                opt_details = opt_data.get("optimization_data", {})
                if opt_details.get("changes"):
                    print(f"  Действия:")
                    for change in opt_details["changes"]:
                        action = change.get("action", "unknown")
                        print(f"    - {action}: {change}")
        else:
            print("\n✅ План не требовал корректировок (оптимален изначально)")
        
        # Проверяем replanning (при ошибках)
        replans = [k for k in result["results"].keys() if k.startswith("replan_")]
        if replans:
            print(f"\n🔄 REPLANNING (при ошибках): {len(replans)}")
            for replan_key in replans:
                replan_data = result["results"][replan_key]
                print(f"  - {replan_key}: {replan_data.get('changes', 'N/A')}")
        
        # Финальная статистика
        print("\n" + "=" * 80)
        print("📈 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80 + "\n")
        
        executed_steps = len([k for k in result["results"].keys() if k.startswith("step_")])
        errors = len([v for k, v in result["results"].items() if k.startswith("step_") and v.get("status") == "error"])
        
        print(f"  Исходный план: {initial_steps_count} шагов")
        print(f"  Выполнено шагов: {executed_steps}")
        print(f"  Ошибок: {errors}")
        print(f"  Оптимизаций: {len(optimizations)}")
        print(f"  Replanning: {len(replans)}")
        print(f"  Время выполнения: {result.get('execution_time', 0):.2f}s")
        print(f"  Финальный статус: {result.get('status')}")
        
        # Демонстрация разницы между шагами
        if optimizations:
            print("\n" + "=" * 80)
            print("📋 КАК МЕНЯЛСЯ ПЛАН")
            print("=" * 80 + "\n")
            
            print(f"Изначально планировалось {initial_steps_count} шагов")
            
            for i, opt_key in enumerate(optimizations, 1):
                opt_data = result["results"][opt_key]
                after_step = opt_data.get("after_step")
                print(f"\n{i}. После шага {after_step}:")
                print(f"   {opt_data.get('changes')}")
        
        return result
        
    finally:
        await engine.shutdown()
        print("\n✅ Ресурсы освобождены")


async def test_without_adaptive_planning():
    """
    Сценарий: Тот же запрос, но БЕЗ адаптивного планирования.
    
    Ожидаемое поведение:
    - План выполняется строго по исходному плану
    - Никаких оптимизаций не происходит
    """
    print("\n" + "=" * 80)
    print("🧪 ТЕСТ: БЕЗ адаптивного планирования (для сравнения)")
    print("=" * 80 + "\n")
    
    # Engine БЕЗ adaptive planning
    engine = MultiAgentEngine(adaptive_planning=False)
    
    try:
        await engine.initialize()
        print("✅ MultiAgentEngine инициализирован (adaptive_planning=False)")
        
        request = """
        Найди информацию о новостях в области искусственного интеллекта за 2026 год.
        Проанализируй основные тренды и создай визуализацию.
        """
        
        print(f"\n📝 Запрос: {request.strip()}\n")
        print("=" * 80)
        
        result = await engine.process_request(
            user_request=request,
            board_id="test_board",
            session_id="non_adaptive_test"
        )
        
        # Анализируем результаты
        print("\n" + "=" * 80)
        print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ")
        print("=" * 80 + "\n")
        
        initial_plan = result["plan"].get("plan", {})
        initial_steps_count = len(initial_plan.get("steps", []))
        
        optimizations = [k for k in result["results"].keys() if k.startswith("optimization_")]
        
        print(f"📋 План: {initial_steps_count} шагов")
        print(f"🔄 Оптимизаций: {len(optimizations)} (ожидалось 0)")
        print(f"⏱️ Время: {result.get('execution_time', 0):.2f}s")
        
        if len(optimizations) == 0:
            print("\n✅ План выполнен строго по изначальному плану (как и ожидалось)")
        else:
            print("\n⚠️ НЕОЖИДАННО: обнаружены оптимизации при adaptive_planning=False")
        
        return result
        
    finally:
        await engine.shutdown()
        print("\n✅ Ресурсы освобождены")


async def main():
    """Запуск всех тестов."""
    print("\n" + "=" * 80)
    print("🚀 ТЕСТИРОВАНИЕ АДАПТИВНОГО ПЛАНИРОВАНИЯ")
    print("=" * 80)
    
    print("\n📌 Демонстрация:")
    print("  1. С адаптивным планированием - план корректируется после каждого шага")
    print("  2. Без адаптивного планирования - план выполняется строго")
    print()
    
    # Тест 1: С адаптивным планированием
    result_adaptive = await test_adaptive_planning()
    
    await asyncio.sleep(2)
    
    # Тест 2: Без адаптивного планирования
    result_static = await test_without_adaptive_planning()
    
    # Сравнение
    print("\n" + "=" * 80)
    print("📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
    print("=" * 80 + "\n")
    
    adaptive_opts = len([k for k in result_adaptive["results"].keys() if k.startswith("optimization_")])
    static_opts = len([k for k in result_static["results"].keys() if k.startswith("optimization_")])
    
    adaptive_time = result_adaptive.get("execution_time", 0)
    static_time = result_static.get("execution_time", 0)
    
    print(f"{'Параметр':<30} | {'С адаптацией':<15} | {'Без адаптации':<15}")
    print("-" * 80)
    print(f"{'Оптимизаций':<30} | {adaptive_opts:<15} | {static_opts:<15}")
    print(f"{'Время выполнения':<30} | {adaptive_time:<15.2f}s | {static_time:<15.2f}s")
    
    time_overhead = adaptive_time - static_time
    if time_overhead > 0:
        print(f"\nОверхед адаптивного планирования: +{time_overhead:.2f}s (~{time_overhead * 100 / static_time:.1f}%)")
    
    print("\n" + "=" * 80)
    print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
    print("=" * 80 + "\n")
    
    print("📝 ВЫВОДЫ:")
    print("-" * 80)
    print("""
1. АДАПТИВНОЕ ПЛАНИРОВАНИЕ (adaptive_planning=True):
   ✅ План анализируется и корректируется после каждого успешного шага
   ✅ GigaChat оценивает результаты и предлагает оптимизации
   ✅ Могут добавляться/удаляться/изменяться шаги
   ⚠️ Добавляет ~200-500ms на анализ каждого шага
   ⚠️ Увеличивает количество вызовов GigaChat (стоимость)
   
2. СТАТИЧЕСКОЕ ПЛАНИРОВАНИЕ (adaptive_planning=False):
   ✅ Быстрее (нет оверхеда на анализ)
   ✅ Меньше вызовов GigaChat (экономия)
   ⚠️ План не адаптируется к результатам
   ⚠️ Может быть менее эффективен для сложных задач
   
3. КОГДА ИСПОЛЬЗОВАТЬ АДАПТИВНОЕ:
   - Сложные многошаговые задачи
   - Неопределённый объём данных
   - Когда качество важнее скорости
   - Исследовательские запросы
   
4. КОГДА ИСПОЛЬЗОВАТЬ СТАТИЧЕСКОЕ:
   - Простые предсказуемые задачи
   - Ограниченный бюджет API
   - Когда скорость критична
   - Повторяющиеся операции
    """)


if __name__ == "__main__":
    asyncio.run(main())
