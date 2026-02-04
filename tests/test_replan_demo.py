"""
Демонстрация механизма full replan после успешных шагов.
"""
import asyncio
import sys
import os
import logging

# Настраиваем логирование чтобы видеть решения GigaChat
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Добавляем путь к backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../apps/backend')))

from app.services.multi_agent.engine import MultiAgentEngine


async def test_replan_mechanism():
    """
    Тест демонстрирует:
    1. После каждого успешного шага GigaChat анализирует результаты
    2. Принимает решение о необходимости replan
    3. Если нужен replan, вызывается PlannerAgent.replan() с накопленными результатами
    """
    print("=" * 80)
    print("REPLAN MECHANISM DEMO")
    print("=" * 80)
    print()
    
    # Инициализируем Engine с adaptive_planning=True
    engine = MultiAgentEngine(adaptive_planning=True)
    await engine.initialize()
    
    print("[OK] Engine initialized with adaptive_planning=True")
    print()
    
    # Простой запрос, который должен вызвать replan
    # После первого шага (search) у нас будут результаты, которые могут повлиять на план
    request = """
    Find information about Python programming language.
    Then create a detailed analysis report.
    """
    
    print("REQUEST:")
    print(request)
    print()
    print("-" * 80)
    print("WATCH FOR: 'GigaChat replan decision' messages in logs")
    print("           These show whether GigaChat decided to replan or not")
    print("-" * 80)
    print()
    
    # Выполняем запрос
    result = await engine.process_request(
        board_id="test-board-1",
        user_request=request
    )
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"Status: {result.get('status')}")
    print(f"Executed steps: {result.get('steps_executed', 0)}")
    print(f"Errors: {result.get('errors', 0)}")
    print()
    
    # Проверяем, были ли replan
    replan_entries = [k for k in result.get('results', {}).keys() if k.startswith('replan_')]
    if replan_entries:
        print(f"[SUCCESS] Replanning occurred {len(replan_entries)} time(s):")
        for key in replan_entries:
            replan_info = result['results'][key]
            print(f"  - {key}: {replan_info.get('reason')}")
            print(f"    Steps: {replan_info.get('old_steps_count')} -> {replan_info.get('new_steps_count')}")
    else:
        print("[INFO] No replanning occurred")
        print("       GigaChat decided the initial plan was optimal")
    
    print()
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    
    await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(test_replan_mechanism())
