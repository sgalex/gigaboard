"""
Сложный тест адаптивного планирования.

Демонстрирует сценарии, где план ДОЛЖЕН корректироваться:
1. Большой объём данных требует фильтрации
2. Обнаружение новых аспектов требует дополнительных шагов
3. Недостаточность данных требует расширения поиска
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


async def scenario_1_large_dataset():
    """
    Сценарий 1: Найдено слишком много данных.
    
    Ожидаемая адаптация:
    - После SearchAgent: 50+ результатов
    - GigaChat должен добавить шаг фильтрации/приоритизации
    - AnalystAgent получит отфильтрованные данные
    """
    print("\n" + "=" * 100)
    print("[TEST] SCENARIO 1: Large dataset -> Filtering required")
    print("=" * 100 + "\n")
    
    engine = MultiAgentEngine(adaptive_planning=True)
    
    try:
        await engine.initialize()
        print("✅ Engine инициализирован\n")
        
        # Запрос, который вернёт много результатов
        request = """
        Найди последние новости о Python за январь 2026 года.
        Отбери самые важные и проанализируй основные темы.
        Создай краткий отчёт.
        """
        
        print(f"📝 ЗАПРОС:\n{request}\n")
        print("🎯 ОЖИДАНИЕ: SearchAgent найдёт 30+ результатов")
        print("             → GigaChat должен добавить шаг фильтрации/ранжирования\n")
        print("-" * 100)
        
        result = await engine.process_request(
            user_request=request,
            board_id="test_board",
            session_id="scenario_1"
        )
        
        # Анализ
        print("\n" + "=" * 100)
        print("📊 РЕЗУЛЬТАТЫ")
        print("=" * 100 + "\n")
        
        steps = len([k for k in result["results"].keys() if k.startswith("step_")])
        optimizations = [k for k in result["results"].keys() if k.startswith("optimization_")]
        
        print(f"Выполнено шагов: {steps}")
        print(f"Оптимизаций: {len(optimizations)}")
        print(f"Время: {result.get('execution_time', 0):.2f}s")
        print(f"Статус: {result.get('status')}\n")
        
        if optimizations:
            print("✅ АДАПТАЦИЯ СРАБОТАЛА!")
            print("-" * 100)
            for opt_key in optimizations:
                opt = result["results"][opt_key]
                print(f"\n{opt_key}:")
                print(f"  После шага: {opt.get('after_step')}")
                print(f"  Изменения: {opt.get('changes')}")
                
                opt_data = opt.get("optimization_data", {})
                if opt_data.get("changes"):
                    print(f"  Действия:")
                    for change in opt_data["changes"]:
                        action = change.get("action")
                        if action == "add_step":
                            print(f"    ➕ Добавлен шаг: {change.get('step', {}).get('agent')}")
                        elif action == "modify_step":
                            print(f"    ✏️ Изменён шаг: {change.get('step_id')}")
                        elif action == "remove_step":
                            print(f"    ➖ Удалён шаг: {change.get('step_id')}")
        else:
            print("⚠️ Адаптация не сработала (возможно, данных было мало)")
        
        # Проверяем объём данных
        print("\n" + "-" * 100)
        print("📦 ОБЪЁМ ДАННЫХ:\n")
        for key, value in result["results"].items():
            if key.startswith("step_") and "search" in key.lower():
                search_result = value
                result_count = search_result.get("result_count", 0)
                print(f"  SearchAgent нашёл: {result_count} результатов")
                if result_count > 20:
                    print(f"  ✅ Достаточно для демонстрации адаптации")
                else:
                    print(f"  ⚠️ Мало результатов для адаптации")
        
        return result
        
    finally:
        await engine.shutdown()
        print("\n✅ Ресурсы освобождены\n")


async def scenario_2_multistep_research():
    """
    Сценарий 2: Требуется углублённое исследование по нескольким аспектам.
    
    Ожидаемая адаптация:
    - После SearchAgent: обнаружены 3-5 связанных тем
    - GigaChat должен добавить отдельные шаги поиска для каждой темы
    - AnalystAgent получит обогащённые данные
    """
    print("\n" + "=" * 100)
    print("[TEST] SCENARIO 2: Related topics found -> Extended research")
    print("=" * 100 + "\n")
    
    engine = MultiAgentEngine(adaptive_planning=True)
    
    try:
        await engine.initialize()
        print("✅ Engine инициализирован\n")
        
        request = """
        Найди информацию о тенденциях в веб-разработке на 2026 год.
        Проанализируй основные направления и создай детальный отчёт.
        """
        
        print(f"📝 ЗАПРОС:\n{request}\n")
        print("🎯 ОЖИДАНИЕ: SearchAgent найдёт упоминания разных фреймворков/технологий")
        print("             → GigaChat должен добавить поиск по каждой технологии\n")
        print("-" * 100)
        
        result = await engine.process_request(
            user_request=request,
            board_id="test_board",
            session_id="scenario_2"
        )
        
        # Анализ
        print("\n" + "=" * 100)
        print("📊 РЕЗУЛЬТАТЫ")
        print("=" * 100 + "\n")
        
        initial_steps = len(result["plan"].get("plan", {}).get("steps", []))
        executed_steps = len([k for k in result["results"].keys() if k.startswith("step_")])
        optimizations = [k for k in result["results"].keys() if k.startswith("optimization_")]
        
        print(f"Исходный план: {initial_steps} шагов")
        print(f"Выполнено: {executed_steps} шагов")
        print(f"Добавлено шагов: {executed_steps - initial_steps}")
        print(f"Оптимизаций: {len(optimizations)}")
        print(f"Время: {result.get('execution_time', 0):.2f}s\n")
        
        if optimizations:
            print("✅ АДАПТИВНОЕ ПЛАНИРОВАНИЕ СРАБОТАЛО!")
            print("-" * 100)
            for opt_key in optimizations:
                opt = result["results"][opt_key]
                print(f"\n{opt_key} (после шага {opt.get('after_step')}):")
                print(f"  {opt.get('changes')}")
        else:
            print("⚠️ Оптимизация не понадобилась")
        
        return result
        
    finally:
        await engine.shutdown()
        print("\n✅ Ресурсы освобождены\n")


async def scenario_3_insufficient_data():
    """
    Сценарий 3: Недостаточно данных для анализа.
    
    Ожидаемая адаптация:
    - После SearchAgent: найдено 1-2 результата
    - GigaChat должен добавить дополнительные поиски с другими запросами
    - Или упростить анализ под малый объём данных
    """
    print("\n" + "=" * 100)
    print("[TEST] SCENARIO 3: Insufficient data -> Extended search or simplified analysis")
    print("=" * 100 + "\n")
    
    engine = MultiAgentEngine(adaptive_planning=True)
    
    try:
        await engine.initialize()
        print("✅ Engine инициализирован\n")
        
        # Специфичный запрос, который вернёт мало результатов
        request = """
        Найди статистику использования языка Julia в enterprise проектах за 2026 год.
        Проанализируй данные и создай отчёт.
        """
        
        print(f"📝 ЗАПРОС:\n{request}\n")
        print("🎯 ОЖИДАНИЕ: SearchAgent найдёт мало результатов (специфичная тема)")
        print("             → GigaChat должен добавить альтернативные поиски")
        print("             → Или упростить требования к анализу\n")
        print("-" * 100)
        
        result = await engine.process_request(
            user_request=request,
            board_id="test_board",
            session_id="scenario_3"
        )
        
        # Анализ
        print("\n" + "=" * 100)
        print("📊 РЕЗУЛЬТАТЫ")
        print("=" * 100 + "\n")
        
        steps = len([k for k in result["results"].keys() if k.startswith("step_")])
        optimizations = [k for k in result["results"].keys() if k.startswith("optimization_")]
        
        print(f"Выполнено шагов: {steps}")
        print(f"Оптимизаций: {len(optimizations)}\n")
        
        # Проверяем объём данных
        for key, value in result["results"].items():
            if key.startswith("step_") and value.get("agent") == "search":
                result_count = value.get("result_count", 0)
                print(f"SearchAgent нашёл: {result_count} результатов")
                if result_count < 5:
                    print("  → Мало данных, требуется адаптация!")
        
        if optimizations:
            print("\n✅ АДАПТАЦИЯ СРАБОТАЛА!")
            for opt_key in optimizations:
                opt = result["results"][opt_key]
                print(f"\n{opt_key}:")
                print(f"  {opt.get('changes')}")
        
        return result
        
    finally:
        await engine.shutdown()
        print("\n✅ Ресурсы освобождены\n")


async def main():
    """Запуск всех сложных сценариев."""
    print("\n" + "=" * 100)
    print("TESTING ADAPTIVE PLANNING: COMPLEX SCENARIOS")
    print("=" * 100)
    
    print("\n📋 Будут протестированы 3 сценария:")
    print("  1. Большой объём данных (50+ результатов)")
    print("  2. Обнаружение связанных тем (multi-aspect research)")
    print("  3. Недостаточно данных (требуется расширение)")
    print()
    
    results = []
    
    # Сценарий 1
    try:
        result1 = await scenario_1_large_dataset()
        results.append(("Сценарий 1", result1))
    except Exception as e:
        print(f"❌ Ошибка в сценарии 1: {e}")
        results.append(("Сценарий 1", None))
    
    await asyncio.sleep(2)
    
    # Сценарий 2
    try:
        result2 = await scenario_2_multistep_research()
        results.append(("Сценарий 2", result2))
    except Exception as e:
        print(f"❌ Ошибка в сценарии 2: {e}")
        results.append(("Сценарий 2", None))
    
    await asyncio.sleep(2)
    
    # Сценарий 3
    try:
        result3 = await scenario_3_insufficient_data()
        results.append(("Сценарий 3", result3))
    except Exception as e:
        print(f"❌ Ошибка в сценарии 3: {e}")
        results.append(("Сценарий 3", None))
    
    # Итоговая сводка
    print("\n" + "=" * 100)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("=" * 100 + "\n")
    
    print(f"{'Сценарий':<30} | {'Оптимизаций':<15} | {'Время':<15} | {'Статус':<15}")
    print("-" * 100)
    
    total_optimizations = 0
    for name, result in results:
        if result:
            opts = len([k for k in result["results"].keys() if k.startswith("optimization_")])
            time = result.get("execution_time", 0)
            status = result.get("status", "unknown")
            total_optimizations += opts
            print(f"{name:<30} | {opts:<15} | {time:<15.2f}s | {status:<15}")
        else:
            print(f"{name:<30} | {'ERROR':<15} | {'-':<15} | {'FAILED':<15}")
    
    print("\n" + "=" * 100)
    print(f"🎯 ВСЕГО ОПТИМИЗАЦИЙ: {total_optimizations}")
    print("=" * 100 + "\n")
    
    if total_optimizations > 0:
        print("✅ УСПЕХ! Адаптивное планирование продемонстрировано в действии!")
        print("\nАдаптация произошла в сложных сценариях, где:")
        print("  - Объём данных требовал корректировки")
        print("  - Обнаружены дополнительные аспекты для исследования")
        print("  - Недостаточность данных требовала адаптации плана")
    else:
        print("⚠️ Оптимизации не сработали в тестовых сценариях.")
        print("\nВозможные причины:")
        print("  - GigaChat решил, что планы оптимальны")
        print("  - Результаты не содержали достаточно информации для адаптации")
        print("  - Параметр temperature слишком консервативен (0.3)")
        print("\n💡 Рекомендации:")
        print("  - Увеличить temperature в _optimize_plan_after_step (до 0.5-0.7)")
        print("  - Добавить в prompt явные примеры когда нужна оптимизация")
        print("  - Использовать более сложные/амбициозные запросы")


if __name__ == "__main__":
    asyncio.run(main())
