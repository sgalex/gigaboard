"""
Тестовый скрипт для проверки интеграции GigaChat.

Запуск:
    python -m tests.test_gigachat_integration
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем корень backend в PYTHONPATH
backend_root = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_root))

from app.config import settings
from app.services.gigachat_service import GigaChatService


async def test_basic_completion():
    """Тест базового completion запроса."""
    print("=" * 60)
    print("Тест 1: Базовый completion запрос")
    print("=" * 60)
    
    if not settings.GIGACHAT_API_KEY:
        print("❌ GIGACHAT_API_KEY не установлен в .env файле")
        return False
    
    try:
        service = GigaChatService(
            api_key=settings.GIGACHAT_API_KEY,
            model=settings.GIGACHAT_MODEL,
            temperature=settings.GIGACHAT_TEMPERATURE,
            max_tokens=settings.GIGACHAT_MAX_TOKENS,
            scope=settings.GIGACHAT_SCOPE,
            verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        )
        print(f"✅ GigaChat сервис инициализирован (model: {settings.GIGACHAT_MODEL}, scope: {settings.GIGACHAT_SCOPE})")
        
        # Простой запрос
        messages = [
            {"role": "system", "content": "Ты помощник аналитика данных в GigaBoard."},
            {"role": "user", "content": "Привет! Расскажи в одном предложении, как ты можешь помочь с анализом данных?"}
        ]
        
        print("\n📤 Отправка запроса...")
        response = await service.chat_completion(messages)
        
        print("\n📥 Ответ от GigaChat:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        print(f"✅ Получен ответ ({len(response)} символов)")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def test_context_conversation():
    """Тест диалога с контекстом."""
    print("\n" + "=" * 60)
    print("Тест 2: Диалог с контекстом")
    print("=" * 60)
    
    if not settings.GIGACHAT_API_KEY:
        print("❌ GIGACHAT_API_KEY не установлен")
        return False
    
    try:
        service = GigaChatService(
            api_key=settings.GIGACHAT_API_KEY,
            model=settings.GIGACHAT_MODEL,
        )
        
        # Симуляция контекста доски
        board_context = {
            "board_name": "Анализ продаж Q4 2025",
            "data_nodes": [
                {"type": "sql_query", "name": "sales_data", "records": 15000},
                {"type": "csv_file", "name": "customer_segments.csv", "records": 500}
            ],
            "widget_nodes": [
                {"type": "bar_chart", "title": "Продажи по регионам"}
            ]
        }
        
        messages = [
            {
                "role": "system",
                "content": f"""Ты ИИ-ассистент в GigaBoard для анализа данных.
                
Контекст текущей доски:
- Название: {board_context['board_name']}
- Источники данных: {len(board_context['data_nodes'])} DataNode
- Визуализации: {len(board_context['widget_nodes'])} WidgetNode

Помогай пользователю анализировать данные и создавать визуализации."""
            },
            {
                "role": "user",
                "content": "Какие инсайты ты можешь извлечь из данных на доске?"
            }
        ]
        
        print("\n📤 Отправка запроса с контекстом доски...")
        response = await service.chat_completion(messages, temperature=0.8)
        
        print("\n📥 Ответ:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        print("✅ Тест пройден")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def test_streaming():
    """Тест streaming ответов."""
    print("\n" + "=" * 60)
    print("Тест 3: Streaming responses")
    print("=" * 60)
    
    if not settings.GIGACHAT_API_KEY:
        print("❌ GIGACHAT_API_KEY не установлен")
        return False
    
    try:
        service = GigaChatService(
            api_key=settings.GIGACHAT_API_KEY,
            model=settings.GIGACHAT_MODEL,
            scope=settings.GIGACHAT_SCOPE,
            verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        )
        
        messages = [
            {"role": "user", "content": "Перечисли 5 лучших практик визуализации данных. Будь краток."}
        ]
        
        print("\n📤 Запуск streaming запроса...")
        print("\n📥 Ответ (streaming):")
        print("-" * 60)
        
        chunks_received = 0
        async for chunk in service.chat_completion_stream(messages):
            print(chunk, end="", flush=True)
            chunks_received += 1
        
        print()
        print("-" * 60)
        print(f"✅ Получено {chunks_received} chunks")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def test_health_check():
    """Тест health check."""
    print("\n" + "=" * 60)
    print("Тест 4: Health Check")
    print("=" * 60)
    
    if not settings.GIGACHAT_API_KEY:
        print("❌ GIGACHAT_API_KEY не установлен")
        return False
    
    try:
        service = GigaChatService(
            api_key=settings.GIGACHAT_API_KEY,
            model=settings.GIGACHAT_MODEL,
            scope=settings.GIGACHAT_SCOPE,
            verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
        )
        
        print("\n🔍 Проверка доступности GigaChat API...")
        result = await service.health_check()
        
        print("\n📊 Результат:")
        print(f"  Status: {result['status']}")
        print(f"  Model: {result['model']}")
        
        if result['status'] == 'ok':
            print(f"  Response length: {result['response_length']} chars")
            print("✅ GigaChat API доступен")
            return True
        else:
            print(f"  Error: {result.get('error', 'Unknown')}")
            print("❌ GigaChat API недоступен")
            return False
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def main():
    """Запуск всех тестов."""
    print("\n" + "🚀 " * 20)
    print("GigaBoard - GigaChat Integration Tests")
    print("🚀 " * 20)
    
    print(f"\n⚙️  Конфигурация:")
    print(f"  API Key: {'✅ установлен' if settings.GIGACHAT_API_KEY else '❌ не установлен'}")
    print(f"  Model: {settings.GIGACHAT_MODEL}")
    print(f"  Scope: {settings.GIGACHAT_SCOPE}")
    print(f"  Temperature: {settings.GIGACHAT_TEMPERATURE}")
    print(f"  Max Tokens: {settings.GIGACHAT_MAX_TOKENS}")
    
    results = []
    
    # Запускаем тесты
    results.append(("Basic Completion", await test_basic_completion()))
    results.append(("Context Conversation", await test_context_conversation()))
    results.append(("Streaming", await test_streaming()))
    results.append(("Health Check", await test_health_check()))
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 Итоги тестирования")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name:<25} {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\n🎯 Результат: {total_passed}/{total_tests} тестов пройдено")
    
    if total_passed == total_tests:
        print("\n🎉 Все тесты успешно пройдены!")
        print("✅ GigaChat интеграция работает корректно")
    else:
        print(f"\n⚠️  {total_tests - total_passed} тестов не прошли")
        print("❌ Проверьте настройки и логи выше")


if __name__ == "__main__":
    asyncio.run(main())
