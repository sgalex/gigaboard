"""
Интеграционные тесты Multi-Agent системы с CriticAgent.

Тестируем сценарии, где:
1. Пользователь запрашивает сбор данных из интернета
2. Конечная цель — получить Python код
3. CriticAgent валидирует результат

Запуск:
    pytest tests/test_multiagent_critic_integration.py -v -s
"""

import pytest
import asyncio
from typing import Dict, Any, List
from uuid import uuid4

# Этот тест требует работающего бэкенда с Redis и GigaChat
pytestmark = pytest.mark.asyncio


# ============================================================
# Тестовые сценарии
# ============================================================

TEST_SCENARIOS = [
    {
        "id": "crypto_price_visualization",
        "name": "Криптовалюта: сбор данных + код визуализации",
        "user_request": "Найди текущую цену Bitcoin в USD и напиши Python код для построения графика истории цен за последний месяц",
        "expected_outcome": "code_generation",
        "expected_agents": ["search", "researcher", "transformation"],
        "validation_checks": {
            "has_code": True,
            "code_contains": ["import", "plt", "plot", "bitcoin"],
            "has_data_reference": True
        },
        "critic_should_pass": True,
        "description": "Должен найти информацию о Bitcoin и сгенерировать код для визуализации"
    },
    
    {
        "id": "weather_data_analysis",
        "name": "Погода: сбор данных + код анализа",
        "user_request": "Собери данные о погоде в Москве за последнюю неделю и создай Python код для анализа температурных трендов",
        "expected_outcome": "code_generation",
        "expected_agents": ["search", "researcher", "transformation"],
        "validation_checks": {
            "has_code": True,
            "code_contains": ["pandas", "df", "temperature", "trend"],
            "has_df_result": True
        },
        "critic_should_pass": True,
        "description": "Должен собрать данные о погоде и создать код анализа"
    },
    
    {
        "id": "stock_market_parser",
        "name": "Акции: парсинг данных + код обработки",
        "user_request": "Найди информацию о топ-10 акциях S&P 500 и напиши код на Python для парсинга этих данных в DataFrame",
        "expected_outcome": "code_generation",
        "expected_agents": ["search", "researcher", "transformation"],
        "validation_checks": {
            "has_code": True,
            "code_contains": ["pandas", "pd.DataFrame", "S&P", "stock"],
            "has_df_result": True
        },
        "critic_should_pass": True,
        "description": "Должен найти данные об акциях и создать парсер"
    },
    
    {
        "id": "covid_statistics_code",
        "name": "COVID статистика: данные + код агрегации",
        "user_request": "Найди статистику COVID-19 по странам и создай Python код для расчёта топ-5 стран по количеству случаев",
        "expected_outcome": "code_generation",
        "expected_agents": ["search", "researcher", "transformation"],
        "validation_checks": {
            "has_code": True,
            "code_contains": ["df", "sort_values", "nlargest", "covid"],
            "has_df_result": True
        },
        "critic_should_pass": True,
        "description": "Должен найти COVID данные и создать код агрегации"
    },
    
    {
        "id": "exchange_rate_calculator",
        "name": "Курсы валют: API данные + код калькулятора",
        "user_request": "Найди текущие курсы валют USD/EUR/RUB и напиши Python код для конвертации между ними",
        "expected_outcome": "code_generation",
        "expected_agents": ["search", "researcher", "transformation"],
        "validation_checks": {
            "has_code": True,
            "code_contains": ["def", "convert", "rate", "currency"],
            "has_function_definition": True
        },
        "critic_should_pass": True,
        "description": "Должен найти курсы валют и создать функцию конвертации"
    },
    
    # Негативный сценарий: результат без кода (для проверки CriticAgent)
    {
        "id": "news_summary_only",
        "name": "НЕГАТИВНЫЙ: только резюме без кода",
        "user_request": "Найди последние новости о Python 3.12",
        "expected_outcome": "research",  # Не code_generation!
        "expected_agents": ["search", "researcher"],
        "validation_checks": {
            "has_code": False,
            "has_text_summary": True
        },
        "critic_should_pass": True,  # Для research текст приемлем
        "description": "Должен вернуть только текстовое резюме (валидно для research)"
    },
    
    # Сценарий для проверки работы CriticAgent с несоответствием
    {
        "id": "code_request_text_response",
        "name": "КРИТИК ТЕСТ: запрос кода, получен только текст",
        "user_request": "Напиши код на Python для расчёта факториала",
        "expected_outcome": "code_generation",
        "expected_agents": [],  # Мокированный результат
        "mock_result": {
            "researcher": {
                "message": "Факториал - это произведение всех натуральных чисел от 1 до n"
            }
        },
        "validation_checks": {
            "has_code": False
        },
        "critic_should_pass": False,  # Критик должен отклонить
        "description": "CriticAgent должен обнаружить отсутствие кода"
    }
]


# ============================================================
# Фикстуры
# ============================================================

@pytest.fixture
async def orchestrator():
    """Создаёт MultiAgentOrchestrator для тестов."""
    from apps.backend.app.services.multi_agent.orchestrator import MultiAgentOrchestrator
    from apps.backend.app.services.multi_agent.message_bus import AgentMessageBus
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from apps.backend.app.config import settings
    
    # Создаём async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True
    )
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        message_bus = AgentMessageBus()
        await message_bus.connect()
        
        orch = MultiAgentOrchestrator(db=session, message_bus=message_bus)
        
        yield orch
        
        await message_bus.disconnect()
        await engine.dispose()


@pytest.fixture
def test_user_id():
    """ID тестового пользователя."""
    return uuid4()


@pytest.fixture
def test_board_id():
    """ID тестовой доски."""
    return uuid4()


# ============================================================
# Утилиты
# ============================================================

def validate_code_result(result: Dict[str, Any], checks: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Валидирует результат на наличие кода.
    
    Returns:
        (success, errors)
    """
    errors = []
    
    # Проверка наличия кода
    if checks.get("has_code"):
        has_code = False
        result_str = str(result)
        
        # Ищем transformation_code, sql_query или code blocks
        if "transformation_code" in result_str or "sql_query" in result_str:
            has_code = True
        elif "```python" in result_str or "```sql" in result_str:
            has_code = True
        
        if not has_code:
            errors.append("Код не найден в результате")
    
    # Проверка содержимого кода
    if checks.get("code_contains"):
        result_str = str(result).lower()
        for expected in checks["code_contains"]:
            if expected.lower() not in result_str:
                errors.append(f"Ожидаемое содержимое '{expected}' не найдено в коде")
    
    # Проверка df_result
    if checks.get("has_df_result"):
        if "df_result" not in str(result):
            errors.append("df_result не найден в transformation_code")
    
    # Проверка функции
    if checks.get("has_function_definition"):
        if "def " not in str(result):
            errors.append("Определение функции (def) не найдено")
    
    # Проверка текстового резюме (для research)
    if checks.get("has_text_summary"):
        if "message" not in str(result) and "summary" not in str(result):
            errors.append("Текстовое резюме не найдено")
    
    return len(errors) == 0, errors


async def collect_full_response(generator):
    """Собирает полный ответ из async generator."""
    chunks = []
    async for chunk in generator:
        chunks.append(chunk)
    return "".join(chunks)


# ============================================================
# Тесты
# ============================================================

@pytest.mark.integration
@pytest.mark.parametrize("scenario", 
    [s for s in TEST_SCENARIOS if s["id"] not in ["code_request_text_response"]],
    ids=[s["id"] for s in TEST_SCENARIOS if s["id"] not in ["code_request_text_response"]]
)
async def test_multiagent_with_code_generation(
    orchestrator,
    test_user_id,
    test_board_id,
    scenario
):
    """
    Интеграционный тест: Multi-Agent обрабатывает запрос и генерирует код.
    """
    print(f"\n{'='*60}")
    print(f"🧪 Тест: {scenario['name']}")
    print(f"📝 Запрос: {scenario['user_request']}")
    print(f"🎯 Ожидаемый результат: {scenario['expected_outcome']}")
    print(f"{'='*60}\n")
    
    # Выполняем запрос через orchestrator
    response_generator = orchestrator.process_user_request(
        user_id=test_user_id,
        board_id=test_board_id,
        user_message=scenario["user_request"],
        selected_node_ids=None
    )
    
    # Собираем полный ответ
    full_response = await collect_full_response(response_generator)
    
    print(f"\n📊 Полный ответ ({len(full_response)} символов):")
    print(full_response[:500] + "..." if len(full_response) > 500 else full_response)
    
    # Валидация результата
    success, errors = validate_code_result(
        {"response": full_response},
        scenario["validation_checks"]
    )
    
    if not success:
        print(f"\n❌ Ошибки валидации:")
        for error in errors:
            print(f"   - {error}")
    else:
        print(f"\n✅ Валидация пройдена успешно")
    
    # Проверяем что CriticAgent упомянут в ответе (если валидация была)
    if "Валидация" in full_response or "confidence" in full_response.lower():
        print(f"\n🔍 CriticAgent был активирован")
    
    # Assertions
    if scenario["critic_should_pass"]:
        assert success, f"Тест провалился: {errors}"
    else:
        assert not success, "Тест должен был провалиться, но прошёл"


@pytest.mark.unit
async def test_critic_agent_rejects_missing_code():
    """
    Юнит-тест: CriticAgent отклоняет результат без кода, когда код требуется.
    """
    from apps.backend.app.services.multi_agent.agents.critic import CriticAgent, ExpectedOutcome
    from unittest.mock import MagicMock
    
    print(f"\n{'='*60}")
    print(f"🧪 Юнит-тест: CriticAgent отклоняет отсутствие кода")
    print(f"{'='*60}\n")
    
    # Создаём CriticAgent с моком GigaChat
    mock_gigachat = MagicMock()
    critic = CriticAgent(message_bus=None, gigachat_service=mock_gigachat)
    
    # Мокированный результат: только текст, без кода
    aggregated_result = {
        "researcher": {
            "message": "Факториал - это произведение всех натуральных чисел от 1 до n. "
                      "Например, 5! = 1 * 2 * 3 * 4 * 5 = 120"
        },
        "search": {
            "results": [{"title": "Факториал", "url": "https://example.com", "snippet": "..."}]
        }
    }
    
    # Валидация
    validation_result = await critic.validate(
        user_message="Напиши код на Python для расчёта факториала",
        aggregated_result=aggregated_result,
        expected_outcome=ExpectedOutcome.CODE_GENERATION.value
    )
    
    print(f"📋 Результат валидации:")
    print(f"   valid: {validation_result.get('valid')}")
    print(f"   confidence: {validation_result.get('confidence', 0):.2f}")
    
    if validation_result.get("issues"):
        print(f"   issues:")
        for issue in validation_result["issues"]:
            print(f"      - [{issue.get('severity')}] {issue.get('message')}")
    
    if validation_result.get("recommendations"):
        print(f"   recommendations:")
        for rec in validation_result["recommendations"]:
            print(f"      - {rec.get('description')}")
    
    # Assertions
    assert validation_result.get("valid") is False, "CriticAgent должен отклонить результат без кода"
    assert validation_result.get("confidence", 0) > 0.5, "Confidence должен быть достаточно высоким"
    
    # Проверяем наличие рекомендаций
    recommendations = validation_result.get("recommendations", [])
    assert len(recommendations) > 0, "Должны быть рекомендации по доработке"
    
    # Проверяем что рекомендуется добавить агента для генерации кода
    rec_text = str(recommendations).lower()
    assert "transformation" in rec_text or "developer" in rec_text or "code" in rec_text, \
        "Рекомендация должна упоминать добавление агента для генерации кода"
    
    print(f"\n✅ CriticAgent корректно отклонил результат без кода")


@pytest.mark.unit
async def test_critic_agent_accepts_valid_code():
    """
    Юнит-тест: CriticAgent принимает результат с валидным кодом.
    """
    from apps.backend.app.services.multi_agent.agents.critic import CriticAgent, ExpectedOutcome
    from unittest.mock import MagicMock
    
    print(f"\n{'='*60}")
    print(f"🧪 Юнит-тест: CriticAgent принимает валидный код")
    print(f"{'='*60}\n")
    
    # Создаём CriticAgent с моком GigaChat
    mock_gigachat = MagicMock()
    critic = CriticAgent(message_bus=None, gigachat_service=mock_gigachat)
    
    # Мокированный результат: код трансформации
    aggregated_result = {
        "transformation": {
            "transformation_code": """import pandas as pd
import numpy as np

# Расчёт факториала
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# Создаём таблицу с факториалами
numbers = list(range(1, 11))
factorials = [factorial(n) for n in numbers]

df_result = pd.DataFrame({
    'number': numbers,
    'factorial': factorials
})""",
            "description": "Расчёт факториалов от 1 до 10",
            "validation_status": "success"
        }
    }
    
    # Валидация
    validation_result = await critic.validate(
        user_message="Напиши код на Python для расчёта факториала",
        aggregated_result=aggregated_result,
        expected_outcome=ExpectedOutcome.CODE_GENERATION.value
    )
    
    print(f"📋 Результат валидации:")
    print(f"   valid: {validation_result.get('valid')}")
    print(f"   confidence: {validation_result.get('confidence', 0):.2f}")
    
    if not validation_result.get("valid"):
        print(f"   ❌ Неожиданное отклонение!")
        if validation_result.get("issues"):
            for issue in validation_result["issues"]:
                print(f"      - {issue}")
    
    # Assertions
    assert validation_result.get("valid") is True, "CriticAgent должен принять результат с кодом"
    assert validation_result.get("confidence", 0) >= 0.8, "Confidence должен быть высоким (>= 0.8)"
    
    print(f"\n✅ CriticAgent корректно принял результат с кодом")


# ============================================================
# Вспомогательные тесты для отладки
# ============================================================

@pytest.mark.debug
async def test_expected_outcome_detection():
    """Тест определения expected_outcome из запроса."""
    from apps.backend.app.services.multi_agent.agents.critic import determine_expected_outcome
    
    test_cases = [
        ("Напиши код для парсинга CSV", "code_generation"),
        ("Построй график продаж", "visualization"),
        ("Трансформируй данные", "transformation"),
        ("Найди информацию о Bitcoin", "research"),
        ("Загрузи данные из API", "data_extraction"),
    ]
    
    print(f"\n{'='*60}")
    print(f"🧪 Тест: Определение expected_outcome")
    print(f"{'='*60}\n")
    
    for request, expected in test_cases:
        outcome = determine_expected_outcome(request)
        status = "✅" if outcome == expected else "❌"
        print(f"{status} '{request[:40]}...' → {outcome} (ожидалось: {expected})")
        assert outcome == expected, f"Неверный outcome для '{request}'"
    
    print(f"\n✅ Все определения корректны")


if __name__ == "__main__":
    # Запуск отдельных тестов для быстрой отладки
    import sys
    
    print("Доступные тесты:")
    print("1. Интеграционные тесты (требуют Redis + GigaChat)")
    print("2. Юнит-тесты CriticAgent")
    print("3. Тест определения expected_outcome")
    print("\nДля запуска всех тестов:")
    print("   pytest tests/test_multiagent_critic_integration.py -v -s")
    print("\nДля запуска только юнит-тестов:")
    print("   pytest tests/test_multiagent_critic_integration.py -v -s -m unit")
