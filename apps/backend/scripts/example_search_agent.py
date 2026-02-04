"""
Простой пример использования SearchAgent.
Демонстрирует базовые возможности поиска через DuckDuckGo.
"""
import asyncio
import logging
import sys
import os
from pathlib import Path
from uuid import uuid4

# Setup path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.redis import init_redis, close_redis
from app.core.config import settings
from app.services.multi_agent import AgentMessageBus, SearchAgent
from app.services.gigachat_service import GigaChatService

# Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def search_example():
    """Простой пример поиска."""
    
    # Инициализация
    logger.info("🔧 Инициализация...")
    await init_redis()
    
    gigachat = GigaChatService(
        api_key=settings.GIGACHAT_API_KEY,
        model=settings.GIGACHAT_MODEL,
        scope=settings.GIGACHAT_SCOPE,
    )
    
    message_bus = AgentMessageBus()
    await message_bus.connect()
    
    search_agent = SearchAgent(
        message_bus=message_bus,
        gigachat_service=gigachat
    )
    
    # Запуск агента
    agent_task = asyncio.create_task(search_agent.start_listening())
    await asyncio.sleep(1)
    logger.info("✅ SearchAgent готов\n")
    
    try:
        # Пример 1: Веб-поиск
        logger.info("=" * 60)
        logger.info("🔍 Пример 1: Веб-поиск 'Python FastAPI'")
        logger.info("=" * 60)
        
        task1 = {
            "type": "web_search",
            "query": "Python FastAPI",
            "max_results": 5
        }
        
        result1 = await message_bus.send_task_to_agent(
            agent_name="search",
            session_id=str(uuid4()),
            step_index=0,
            task=task1,
            timeout=30.0
        )
        
        logger.info(f"\n📊 Найдено результатов: {len(result1.get('results', []))}")
        logger.info(f"\n📝 Краткое резюме:")
        logger.info(f"{result1.get('summary', 'N/A')}\n")
        
        if result1.get('results'):
            logger.info("🔗 Топ-3 результата:")
            for i, res in enumerate(result1['results'][:3], 1):
                logger.info(f"  {i}. {res['title']}")
                logger.info(f"     {res['url']}\n")
        
        # Пример 2: Новости
        logger.info("\n" + "=" * 60)
        logger.info("📰 Пример 2: Новости об 'искусственный интеллект'")
        logger.info("=" * 60)
        
        task2 = {
            "type": "news_search",
            "query": "искусственный интеллект",
            "max_results": 3
        }
        
        result2 = await message_bus.send_task_to_agent(
            agent_name="search",
            session_id=str(uuid4()),
            step_index=0,
            task=task2,
            timeout=30.0
        )
        
        logger.info(f"\n📊 Найдено новостей: {len(result2.get('results', []))}")
        
        if result2.get('results'):
            logger.info("\n📰 Последние новости:")
            for i, news in enumerate(result2['results'], 1):
                logger.info(f"  {i}. {news['title']}")
                logger.info(f"     Дата: {news.get('date', 'N/A')}")
                logger.info(f"     Источник: {news.get('source', 'N/A')}\n")
        
        # Пример 3: Быстрый ответ
        logger.info("\n" + "=" * 60)
        logger.info("⚡ Пример 3: Быстрый ответ 'What is FastAPI?'")
        logger.info("=" * 60)
        
        task3 = {
            "type": "instant_answer",
            "query": "What is FastAPI?"
        }
        
        result3 = await message_bus.send_task_to_agent(
            agent_name="search",
            session_id=str(uuid4()),
            step_index=0,
            task=task3,
            timeout=30.0
        )
        
        if result3.get('answer'):
            logger.info(f"\n💡 Ответ: {result3['answer']}\n")
        else:
            logger.info(f"\n💡 Прямого ответа нет, найдено результатов: {len(result3.get('results', []))}\n")
        
        logger.info("=" * 60)
        logger.info("✅ Все примеры выполнены успешно!")
        logger.info("=" * 60)
        
    finally:
        # Cleanup
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        
        await message_bus.disconnect()
        await close_redis()


if __name__ == "__main__":
    asyncio.run(search_example())
