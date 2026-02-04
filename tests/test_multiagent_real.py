"""
Реальное тестирование Multi-Agent системы с GigaChat API.

ВАЖНО: 
- Требуется GIGACHAT_API_KEY в .env
- Требуется запущенный Redis
- Делает реальные API вызовы к GigaChat

Запуск:
    uv run python tests/test_multiagent_real.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apps.backend.app.core.config import Settings
from apps.backend.app.services.gigachat_service import GigaChatService
from apps.backend.app.services.multi_agent.orchestrator import MultiAgentOrchestrator
from apps.backend.app.services.multi_agent.message_bus import AgentMessageBus


async def test_crypto_price_query():
    """
    Тест: Получить цену Bitcoin и визуализировать на графике.
    
    Ожидаемый результат:
    - SearchAgent найдёт информацию о цене BTC
    - ResearcherAgent может получить данные из API
    - ReporterAgent сгенерирует код виджета для графика
    - CriticAgent валидирует наличие visualization
    """
    print("\n" + "="*80)
    print("🧪 ТЕСТ 1: Цена криптовалюты + визуализация")
    print("="*80 + "\n")
    
    settings = Settings()
    
    if not settings.GIGACHAT_API_KEY:
        print("❌ GIGACHAT_API_KEY не установлен в .env")
        print("   Добавьте: GIGACHAT_API_KEY=your-api-key")
        return False
    
    print(f"✅ GigaChat API Key: {settings.GIGACHAT_API_KEY[:10]}...")
    print(f"✅ Model: {settings.GIGACHAT_MODEL}")
    print(f"✅ Redis URL: {settings.REDIS_URL}\n")
    
    # Инициализация
    gigachat_service = GigaChatService(
        api_key=settings.GIGACHAT_API_KEY,
        model=settings.GIGACHAT_MODEL,
        temperature=settings.GIGACHAT_TEMPERATURE,
        max_tokens=settings.GIGACHAT_MAX_TOKENS,
        verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        scope=settings.GIGACHAT_SCOPE
    )
    
    message_bus = AgentMessageBus(redis_url=settings.REDIS_URL)
    await message_bus.connect()
    
    orchestrator = MultiAgentOrchestrator(
        gigachat_service=gigachat_service,
        message_bus=message_bus
    )
    
    try:
        user_message = "Получи текущую цену Bitcoin в USD и построй график изменения цены за последние 7 дней"
        
        print(f"📝 Запрос пользователя:\n   {user_message}\n")
        print("⏳ Выполнение Multi-Agent задачи...\n")
        
        result = await orchestrator.process_user_message(
            user_message=user_message,
            context={}
        )
        
        print("\n" + "="*80)
        print("📊 РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ")
        print("="*80 + "\n")
        
        print(f"Status: {result.get('status')}")
        print(f"Message: {result.get('message', 'N/A')}")
        
        if result.get('execution_plan'):
            print(f"\n📋 План выполнения ({len(result['execution_plan'].get('steps', []))} шагов):")
            for i, step in enumerate(result['execution_plan'].get('steps', []), 1):
                print(f"   {i}. {step.get('agent_name')}: {step.get('task_description')[:60]}...")
        
        if result.get('agent_results'):
            print(f"\n🤖 Результаты агентов ({len(result['agent_results'])} агентов):")
            for agent_name, agent_result in result['agent_results'].items():
                print(f"\n   [{agent_name}]")
                # Показываем первые 200 символов
                result_str = str(agent_result)[:200]
                print(f"   {result_str}...")
        
        if result.get('validation'):
            print(f"\n✅ Валидация CriticAgent:")
            validation = result['validation']
            print(f"   Valid: {validation.get('valid')}")
            print(f"   Confidence: {validation.get('confidence')}")
            if validation.get('issues'):
                print(f"   Issues: {validation['issues']}")
            if validation.get('recommendations'):
                print(f"   Recommendations: {validation['recommendations']}")
        
        if result.get('final_result'):
            print(f"\n📦 Финальный результат:")
            final_str = str(result['final_result'])[:300]
            print(f"   {final_str}...")
        
        print("\n" + "="*80)
        
        # Проверяем, что задача выполнена успешно
        success = (
            result.get('status') == 'success' and
            result.get('validation', {}).get('valid') == True
        )
        
        if success:
            print("✅ ТЕСТ ПРОЙДЕН: Multi-Agent система работает корректно")
        else:
            print("⚠️  ТЕСТ НЕ ПРОЙДЕН: Проверьте результаты выше")
        
        return success
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await message_bus.disconnect()


async def test_weather_analysis():
    """
    Тест: Получить данные о погоде и написать код для анализа.
    
    Ожидаемый результат:
    - SearchAgent найдёт информацию о погоде
    - ResearcherAgent может получить данные из API
    - TransformationAgent сгенерирует код для анализа
    - CriticAgent валидирует наличие code_generation
    """
    print("\n" + "="*80)
    print("🧪 ТЕСТ 2: Погода + код для анализа")
    print("="*80 + "\n")
    
    settings = Settings()
    
    if not settings.GIGACHAT_API_KEY:
        print("❌ GIGACHAT_API_KEY не установлен")
        return False
    
    gigachat_service = GigaChatService(
        api_key=settings.GIGACHAT_API_KEY,
        model=settings.GIGACHAT_MODEL,
        temperature=settings.GIGACHAT_TEMPERATURE,
        max_tokens=settings.GIGACHAT_MAX_TOKENS,
        verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        scope=settings.GIGACHAT_SCOPE
    )
    
    message_bus = AgentMessageBus(redis_url=settings.REDIS_URL)
    await message_bus.connect()
    
    orchestrator = MultiAgentOrchestrator(
        gigachat_service=gigachat_service,
        message_bus=message_bus
    )
    
    try:
        user_message = "Получи погоду в Москве и напиши Python код для анализа температурного тренда"
        
        print(f"📝 Запрос: {user_message}\n")
        print("⏳ Выполнение...\n")
        
        result = await orchestrator.process_user_message(
            user_message=user_message,
            context={}
        )
        
        print(f"\nStatus: {result.get('status')}")
        
        if result.get('validation'):
            validation = result['validation']
            print(f"Valid: {validation.get('valid')}")
            print(f"Confidence: {validation.get('confidence')}")
        
        success = (
            result.get('status') == 'success' and
            result.get('validation', {}).get('valid') == True
        )
        
        if success:
            print("\n✅ ТЕСТ ПРОЙДЕН")
        else:
            print("\n⚠️  ТЕСТ НЕ ПРОЙДЕН")
        
        return success
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return False
        
    finally:
        await message_bus.disconnect()


async def test_simple_research():
    """
    Тест: Простой research-запрос без кода.
    
    Ожидаемый результат:
    - SearchAgent найдёт информацию
    - ResearcherAgent может дополнить
    - CriticAgent валидирует как research (без кода)
    """
    print("\n" + "="*80)
    print("🧪 ТЕСТ 3: Простой research-запрос")
    print("="*80 + "\n")
    
    settings = Settings()
    
    if not settings.GIGACHAT_API_KEY:
        print("❌ GIGACHAT_API_KEY не установлен")
        return False
    
    gigachat_service = GigaChatService(
        api_key=settings.GIGACHAT_API_KEY,
        model=settings.GIGACHAT_MODEL,
        temperature=settings.GIGACHAT_TEMPERATURE,
        max_tokens=settings.GIGACHAT_MAX_TOKENS,
        verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        scope=settings.GIGACHAT_SCOPE
    )
    
    message_bus = AgentMessageBus(redis_url=settings.REDIS_URL)
    await message_bus.connect()
    
    orchestrator = MultiAgentOrchestrator(
        gigachat_service=gigachat_service,
        message_bus=message_bus
    )
    
    try:
        user_message = "Найди информацию о последних новостях в области искусственного интеллекта"
        
        print(f"📝 Запрос: {user_message}\n")
        print("⏳ Выполнение...\n")
        
        result = await orchestrator.process_user_message(
            user_message=user_message,
            context={}
        )
        
        print(f"\nStatus: {result.get('status')}")
        
        if result.get('validation'):
            validation = result['validation']
            print(f"Valid: {validation.get('valid')}")
            print(f"Expected outcome: research")
        
        success = result.get('status') == 'success'
        
        if success:
            print("\n✅ ТЕСТ ПРОЙДЕН")
        else:
            print("\n⚠️  ТЕСТ НЕ ПРОЙДЕН")
        
        return success
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return False
        
    finally:
        await message_bus.disconnect()


async def main():
    """Запуск всех реальных тестов."""
    print("\n" + "="*80)
    print("🚀 РЕАЛЬНОЕ ТЕСТИРОВАНИЕ MULTI-AGENT СИСТЕМЫ")
    print("="*80)
    print("\nВыполняются реальные вызовы к GigaChat API и Redis")
    print("Это займёт некоторое время...\n")
    
    results = []
    
    # Тест 1: Crypto + Visualization
    try:
        result1 = await test_crypto_price_query()
        results.append(("Crypto + Visualization", result1))
    except Exception as e:
        print(f"❌ Тест 1 упал с ошибкой: {e}")
        results.append(("Crypto + Visualization", False))
    
    await asyncio.sleep(2)  # Пауза между тестами
    
    # Тест 2: Weather + Code
    try:
        result2 = await test_weather_analysis()
        results.append(("Weather + Code", result2))
    except Exception as e:
        print(f"❌ Тест 2 упал с ошибкой: {e}")
        results.append(("Weather + Code", False))
    
    await asyncio.sleep(2)
    
    # Тест 3: Simple Research
    try:
        result3 = await test_simple_research()
        results.append(("Simple Research", result3))
    except Exception as e:
        print(f"❌ Тест 3 упал с ошибкой: {e}")
        results.append(("Simple Research", False))
    
    # Итоговый отчёт
    print("\n" + "="*80)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("="*80 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n📈 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тестов не пройдено")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
