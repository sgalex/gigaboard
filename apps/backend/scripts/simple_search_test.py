"""
Простой тест SearchAgent - прямой вызов методов без message bus.
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# Setup path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.redis import init_redis, close_redis
from app.core.config import settings
from app.services.gigachat_service import GigaChatService

# Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def simple_search_test():
    """Простой тест SearchAgent без message bus."""
    
    try:
        logger.info("🔧 Инициализация...")
        
        # Init Redis
        await init_redis()
        
        # Init GigaChat
        gigachat = GigaChatService(
            api_key=settings.GIGACHAT_API_KEY,
            model=settings.GIGACHAT_MODEL,
            scope=settings.GIGACHAT_SCOPE,
        )
        logger.info("✅ GigaChat инициализирован\n")
        
        # Import after setup
        from app.services.multi_agent.agents.search import SearchAgent
        
        # Create SearchAgent (нужен message_bus для init, но для прямых вызовов не используется)
        from app.services.multi_agent import AgentMessageBus
        message_bus = AgentMessageBus()
        await message_bus.connect()
        
        search_agent = SearchAgent(
            message_bus=message_bus,
            gigachat_service=gigachat
        )
        
        logger.info("=" * 60)
        logger.info("🔍 TEST 1: Веб-поиск 'Python FastAPI'")
        logger.info("=" * 60 + "\n")
        
        task1 = {
            "type": "web_search",
            "query": "Python FastAPI",
            "max_results": 3
        }
        
        result1 = await search_agent.process_task(task1)
        
        logger.info(f"📊 Статус: {result1.get('status')}")
        logger.info(f"📊 Найдено: {len(result1.get('results', []))} результатов\n")
        
        if result1.get('summary'):
            logger.info(f"📝 Краткое резюме:")
            logger.info(f"{result1['summary']}\n")
        
        if result1.get('results'):
            logger.info("🔗 Топ результаты:")
            for i, res in enumerate(result1['results'][:3], 1):
                logger.info(f"  {i}. {res.get('title', 'N/A')}")
                logger.info(f"     {res.get('url', 'N/A')}\n")
        
        logger.info("\n" + "=" * 60)
        logger.info("📰 TEST 2: Новости 'Python 3.12'")
        logger.info("=" * 60 + "\n")
        
        task2 = {
            "type": "news_search",
            "query": "Python 3.12",
            "max_results": 3
        }
        
        result2 = await search_agent.process_task(task2)
        
        logger.info(f"📊 Статус: {result2.get('status')}")
        logger.info(f"📰 Найдено: {len(result2.get('results', []))} новостей\n")
        
        if result2.get('results'):
            for i, news in enumerate(result2['results'], 1):
                logger.info(f"  {i}. {news.get('title', 'N/A')}")
                if news.get('date'):
                    logger.info(f"     Дата: {news['date']}")
                logger.info(f"     {news.get('url', 'N/A')}\n")
        
        logger.info("\n" + "=" * 60)
        logger.info("⚡ TEST 3: Быстрый ответ 'What is Python?'")
        logger.info("=" * 60 + "\n")
        
        task3 = {
            "type": "instant_answer",
            "query": "What is Python?"
        }
        
        result3 = await search_agent.process_task(task3)
        
        logger.info(f"📊 Статус: {result3.get('status')}")
        if result3.get('answer'):
            logger.info(f"💡 Ответ: {result3['answer']}\n")
        else:
            logger.info(f"💡 Прямого ответа нет")
            logger.info(f"📊 Найдено результатов: {len(result3.get('results', []))}\n")
        
        logger.info("=" * 60)
        logger.info("✅ Все тесты завершены успешно!")
        logger.info("=" * 60)
        
        # Cleanup
        await message_bus.disconnect()
        await close_redis()
        
    except Exception as e:
        logger.error(f"\n❌ Ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(simple_search_test())
