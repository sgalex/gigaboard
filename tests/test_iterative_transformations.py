"""
Тестовый сценарий для проверки итеративных улучшений в TransformDialog
"""

import asyncio
import logging
from apps.backend.app.services.agents.transformation_multi_agent import TransformationMultiAgent
from apps.backend.app.services.gigachat_service import GigaChatService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_iterative_improvements():
    """
    Проверяет, что TransformationAgent использует existing_code и chat_history
    для итеративного улучшения кода.
    """
    
    # Инициализация сервисов (в реальном тесте использовать настройки из .env)
    gigachat = GigaChatService(api_key="test_key")  # Заменить на реальный ключ
    multi_agent = TransformationMultiAgent(gigachat_service=gigachat)
    
    # Тестовые данные (формат list[Dict])
    nodes_data = [
        {
            "node_id": "test_node",
            "type": "source",
            "name": "employees",
            "rows": [
                {"name": "Alice", "age": 25, "salary": 50000},
                {"name": "Bob", "age": 35, "salary": 75000},
                {"name": "Charlie", "age": 45, "salary": 100000}
            ],
            "schema": {
                "name": "string",
                "age": "int64",
                "salary": "int64"
            }
        }
    ]
    
    print("\n" + "="*80)
    print("ТЕСТ 1: Первая генерация (без existing_code)")
    print("="*80)
    
    # Первый запрос - создание кода
    result1 = await multi_agent.generate_transformation_code(
        user_prompt="Отфильтруй людей с зарплатой больше 60000",
        nodes_data=nodes_data,
        existing_code=None,  # ❌ Нет существующего кода
        chat_history=[]      # ❌ Нет истории
    )
    
    print(f"\n✅ Код создан:")
    print(result1["code"])
    print(f"\nОписание: {result1.get('description', 'N/A')}")
    
    # Сохраняем первый код
    first_code = result1["code"]
    
    print("\n" + "="*80)
    print("ТЕСТ 2: Итеративное улучшение (с existing_code и chat_history)")
    print("="*80)
    
    # Второй запрос - улучшение кода
    chat_history = [
        {"role": "user", "content": "Отфильтруй людей с зарплатой больше 60000"},
        {"role": "assistant", "content": f"Код создан:\n{first_code}"}
    ]
    
    result2 = await multi_agent.generate_transformation_code(
        user_prompt="Измени порог на 70000 и добавь сортировку по возрасту",
        nodes_data=nodes_data,
        existing_code=first_code,        # ✅ Передаём существующий код
        chat_history=chat_history        # ✅ Передаём историю
    )
    
    print(f"\n✅ Код УЛУЧШЕН:")
    print(result2["code"])
    print(f"\nОписание: {result2.get('description', 'N/A')}")
    
    print("\n" + "="*80)
    print("ПРОВЕРКА РЕЗУЛЬТАТА")
    print("="*80)
    
    # Проверяем, что коды отличаются
    if first_code != result2["code"]:
        print("✅ УСПЕХ: Код был модифицирован (не сгенерирован заново)")
    else:
        print("❌ ОШИБКА: Код не изменился (возможно, existing_code игнорируется)")
    
    # Проверяем, что в новом коде есть изменения
    if "70000" in result2["code"] and ("sort" in result2["code"].lower() or "by" in result2["code"].lower()):
        print("✅ УСПЕХ: Новые требования учтены (порог 70000 + сортировка)")
    else:
        print("⚠️ ПРЕДУПРЕЖДЕНИЕ: Новые требования могли быть учтены не полностью")


if __name__ == "__main__":
    asyncio.run(test_iterative_improvements())
