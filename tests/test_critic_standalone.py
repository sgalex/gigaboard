"""
Упрощённые standalone тесты CriticAgent.

Эти тесты можно запускать без полной инфраструктуры.
"""

import pytest
import sys
import os

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

pytestmark = pytest.mark.asyncio


# ============================================================
# Тест 1: Определение expected_outcome
# ============================================================

def test_expected_outcome_detection():
    """Тест определения expected_outcome из запроса (без async)."""
    # Прямой импорт только нужной функции
    from apps.backend.app.services.multi_agent.agents.critic import determine_expected_outcome
    
    test_cases = [
        ("Напиши код для парсинга CSV", "code_generation"),
        ("Сгенерируй Python скрипт", "code_generation"),
        ("Построй график продаж", "visualization"),
        ("Визуализируй данные", "visualization"),
        ("Трансформируй данные", "transformation"),
        ("Преобразуй таблицу", "transformation"),
        ("Найди информацию о Bitcoin", "research"),
        ("Расскажи о Python", "research"),
        ("Загрузи данные из API", "data_extraction"),
        ("Получи данные о погоде", "data_extraction"),
    ]
    
    print(f"\n{'='*60}")
    print(f"🧪 Тест: Определение expected_outcome")
    print(f"{'='*60}\n")
    
    results = []
    for request, expected in test_cases:
        outcome = determine_expected_outcome(request)
        status = "✅" if outcome == expected else "❌"
        print(f"{status} '{request[:45]}...' → {outcome} (ожидалось: {expected})")
        results.append(outcome == expected)
    
    print(f"\n📊 Результат: {sum(results)}/{len(results)} тестов пройдено")
    assert all(results), "Некоторые определения неверны"


# ============================================================
# Тест 2: Эвристическая валидация кода
# ============================================================

def test_critic_heuristic_validation_code():
    """Тест эвристической валидации наличия кода."""
    from apps.backend.app.services.multi_agent.agents.critic import CriticAgent
    from unittest.mock import MagicMock
    
    print(f"\n{'='*60}")
    print(f"🧪 Тест: Эвристическая валидация кода")
    print(f"{'='*60}\n")
    
    # Создаём CriticAgent с mock GigaChat
    mock_gigachat = MagicMock()
    critic = CriticAgent(message_bus=None, gigachat_service=mock_gigachat)
    
    # Тест 1: Есть transformation_code
    print("1️⃣ Тест: transformation_code присутствует")
    result1 = {
        "transformation": {
            "transformation_code": "import pandas as pd\ndf_result = df.groupby('col').sum()",
            "validation_status": "success"
        }
    }
    validation1 = critic._heuristic_validation("code_generation", result1, "напиши код")
    print(f"   Result: valid={validation1['valid']}, confidence={validation1.get('confidence', 0):.2f}")
    assert validation1["valid"] is True, "Должен принять transformation_code"
    
    # Тест 2: Есть code block
    print("\n2️⃣ Тест: code block присутствует")
    result2 = {
        "developer": {
            "message": "Вот код:\n```python\nimport pandas as pd\ndf = pd.read_csv('data.csv')\n```"
        }
    }
    validation2 = critic._heuristic_validation("code_generation", result2, "напиши код")
    print(f"   Result: valid={validation2['valid']}, confidence={validation2.get('confidence', 0):.2f}")
    assert validation2["valid"] is True, "Должен принять code block"
    
    # Тест 3: Только текст без кода
    print("\n3️⃣ Тест: только текст, нет кода")
    result3 = {
        "researcher": {
            "message": "Вот информация о парсинге CSV: используйте pandas.read_csv()"
        }
    }
    validation3 = critic._heuristic_validation("code_generation", result3, "напиши код")
    print(f"   Result: valid={validation3['valid']}, confidence={validation3.get('confidence', 0):.2f}")
    print(f"   Issues: {validation3.get('issues', [])}")
    assert validation3["valid"] is False, "Должен отклонить отсутствие кода"
    
    print(f"\n✅ Все эвристические проверки пройдены")


# ============================================================
# Тест 3: Валидация visualization
# ============================================================

def test_critic_heuristic_validation_visualization():
    """Тест эвристической валидации визуализации."""
    from apps.backend.app.services.multi_agent.agents.critic import CriticAgent
    from unittest.mock import MagicMock
    
    print(f"\n{'='*60}")
    print(f"🧪 Тест: Эвристическая валидация visualization")
    print(f"{'='*60}\n")
    
    mock_gigachat = MagicMock()
    critic = CriticAgent(message_bus=None, gigachat_service=mock_gigachat)
    
    # Тест 1: Есть widget_code
    print("1️⃣ Тест: widget_code с HTML")
    result1 = {
        "reporter": {
            "widget_code": "<!DOCTYPE html><html><body><script>...</script></body></html>",
            "widget_type": "chart"
        }
    }
    validation1 = critic._heuristic_validation("visualization", result1, "построй график")
    print(f"   Result: valid={validation1['valid']}, confidence={validation1.get('confidence', 0):.2f}")
    assert validation1["valid"] is True, "Должен принять widget_code"
    
    # Тест 2: Нет widget_code
    print("\n2️⃣ Тест: нет widget_code")
    result2 = {
        "analyst": {
            "insights": ["Тренд положительный", "Рост 10%"]
        }
    }
    validation2 = critic._heuristic_validation("visualization", result2, "построй график")
    print(f"   Result: valid={validation2['valid']}, confidence={validation2.get('confidence', 0):.2f}")
    assert validation2["valid"] is False, "Должен отклонить отсутствие visualization"
    
    print(f"\n✅ Валидация visualization пройдена")


# ============================================================
# Тест 4: Валидация transformation
# ============================================================

def test_critic_heuristic_validation_transformation():
    """Тест эвристической валидации transformation."""
    from apps.backend.app.services.multi_agent.agents.critic import CriticAgent
    from unittest.mock import MagicMock
    
    print(f"\n{'='*60}")
    print(f"🧪 Тест: Эвристическая валидация transformation")
    print(f"{'='*60}\n")
    
    mock_gigachat = MagicMock()
    critic = CriticAgent(message_bus=None, gigachat_service=mock_gigachat)
    
    # Тест 1: Есть df_result + pandas
    print("1️⃣ Тест: код с df_result и pandas")
    result1 = {
        "transformation": {
            "transformation_code": "import pandas as pd\ndf_result = df.groupby('category').sum()",
            "validation_status": "success"
        }
    }
    validation1 = critic._heuristic_validation("transformation", result1, "трансформируй данные")
    print(f"   Result: valid={validation1['valid']}, confidence={validation1.get('confidence', 0):.2f}")
    assert validation1["valid"] is True, "Должен принять transformation с df_result"
    
    # Тест 2: Есть pandas но нет df_result
    print("\n2️⃣ Тест: pandas есть, df_result нет")
    result2 = {
        "transformation": {
            "transformation_code": "import pandas as pd\ndf_processed = df.dropna()",
            "validation_status": "success"
        }
    }
    validation2 = critic._heuristic_validation("transformation", result2, "обработай данные")
    print(f"   Result: valid={validation2['valid']}, confidence={validation2.get('confidence', 0):.2f}")
    # Должен принять (есть pandas)
    assert validation2["valid"] is True
    
    # Тест 3: Нет pandas кода
    print("\n3️⃣ Тест: нет pandas кода")
    result3 = {
        "researcher": {
            "message": "Данные обработаны вручную"
        }
    }
    validation3 = critic._heuristic_validation("transformation", result3, "трансформируй")
    print(f"   Result: valid={validation3['valid']}, confidence={validation3.get('confidence', 0):.2f}")
    assert validation3["valid"] is False, "Должен отклонить отсутствие transformation"
    
    print(f"\n✅ Валидация transformation пройдена")


# ============================================================
# Тест 5: Валидация research (должен принимать текст)
# ============================================================

def test_critic_heuristic_validation_research():
    """Тест эвристической валидации research."""
    from apps.backend.app.services.multi_agent.agents.critic import CriticAgent
    from unittest.mock import MagicMock
    
    print(f"\n{'='*60}")
    print(f"🧪 Тест: Эвристическая валидация research")
    print(f"{'='*60}\n")
    
    mock_gigachat = MagicMock()
    critic = CriticAgent(message_bus=None, gigachat_service=mock_gigachat)
    
    # Тест 1: Достаточный текстовый ответ
    print("1️⃣ Тест: текстовый ответ > 100 символов")
    result1 = {
        "researcher": {
            "message": "Bitcoin — это децентрализованная криптовалюта, созданная в 2009 году " * 3
        }
    }
    validation1 = critic._heuristic_validation("research", result1, "расскажи о Bitcoin")
    print(f"   Result: valid={validation1['valid']}, confidence={validation1.get('confidence', 0):.2f}")
    assert validation1["valid"] is True, "Должен принять текстовый research"
    
    # Тест 2: Короткий ответ
    print("\n2️⃣ Тест: короткий ответ < 100 символов")
    result2 = {
        "search": {
            "message": "Найдено"
        }
    }
    validation2 = critic._heuristic_validation("research", result2, "найди информацию")
    print(f"   Result: valid={validation2['valid']}, confidence={validation2.get('confidence', 0):.2f}")
    # Может быть невалидным из-за малой длины
    
    print(f"\n✅ Валидация research пройдена")


# ============================================================
# Тест 6: ExpectedOutcome enum
# ============================================================

def test_expected_outcome_enum():
    """Тест enum ExpectedOutcome."""
    from apps.backend.app.services.multi_agent.agents.critic import ExpectedOutcome
    
    print(f"\n{'='*60}")
    print(f"🧪 Тест: ExpectedOutcome enum")
    print(f"{'='*60}\n")
    
    outcomes = [
        (ExpectedOutcome.CODE_GENERATION, "code_generation"),
        (ExpectedOutcome.DATA_EXTRACTION, "data_extraction"),
        (ExpectedOutcome.VISUALIZATION, "visualization"),
        (ExpectedOutcome.TRANSFORMATION, "transformation"),
        (ExpectedOutcome.RESEARCH, "research"),
    ]
    
    for enum_val, expected_str in outcomes:
        print(f"   {enum_val.name} = '{enum_val.value}' (ожидалось: '{expected_str}')")
        assert enum_val.value == expected_str
    
    print(f"\n✅ Все значения enum корректны")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
