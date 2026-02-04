"""
Тест Search Agent: поиск информации в интернете через DuckDuckGo.
"""
import asyncio
import logging
from datetime import datetime
import sys
import os
from pathlib import Path
from uuid import uuid4

# Setup path
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.redis import init_redis, close_redis
from app.core.config import settings
from app.services.multi_agent import (
    AgentMessageBus,
    SearchAgent,
)
from app.services.gigachat_service import GigaChatService


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class SearchAgentTest:
    """Тест Search Agent."""
    
    def __init__(self):
        self.message_bus = None
        self.search_agent = None
        self.agent_task = None
        
    async def setup(self):
        """Инициализация компонентов."""
        logger.info("🔧 Setting up Search Agent test...")
        
        try:
            # Redis
            await init_redis()
            logger.info("✅ Redis connected")
            
            # GigaChat
            gigachat = GigaChatService(
                api_key=settings.GIGACHAT_API_KEY,
                model=settings.GIGACHAT_MODEL,
                temperature=settings.GIGACHAT_TEMPERATURE,
                max_tokens=settings.GIGACHAT_MAX_TOKENS,
                scope=settings.GIGACHAT_SCOPE,
                verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
            )
            logger.info("✅ GigaChat initialized")
            
            # Search Agent (без message bus для упрощённого теста)
            self.search_agent = SearchAgent(
                message_bus=None,  # Не нужен для прямых вызовов
                gigachat_service=gigachat
            )
            logger.info("✅ Search Agent initialized")
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}", exc_info=True)
            raise
    
    async def start_agent(self):
        """Запуск агента (для упрощённого теста не нужен listening)."""
        logger.info("✅ Search Agent готов к тестированию")
    
    async def test_web_search(self):
        """Тест веб-поиска."""
        logger.info("\n" + "="*80)
        logger.info("🔍 TEST 1: Web Search - 'Python programming language'")
        logger.info("="*80)
        
        task = {
            "type": "web_search",
            "query": "Python programming language",
            "max_results": 5
        }
        
        # Прямой вызов process_task для упрощённого теста
        result = await self.search_agent.process_task(task)
        
        logger.info(f"\n📊 RESULT:")
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Query: {result.get('query')}")
        logger.info(f"Results count: {len(result.get('results', []))}")
        
        if result.get('summary'):
            logger.info(f"\n📝 Summary:\n{result['summary']}")
        
        if result.get('results'):
            logger.info(f"\n🔗 Top results:")
            for i, res in enumerate(result['results'][:3], 1):
                logger.info(f"  {i}. {res.get('title')}")
                logger.info(f"     URL: {res.get('url')}")
                if res.get('snippet'):
                    logger.info(f"     Snippet: {res.get('snippet')[:100]}...")
        
        return result
    
    async def test_news_search(self):
        """Тест поиска новостей."""
        logger.info("\n" + "="*80)
        logger.info("📰 TEST 2: News Search - 'искусственный интеллект'")
        logger.info("="*80)
        
        task = {
            "type": "news_search",
            "query": "искусственный интеллект",
            "max_results": 5
        }
        
        # Прямой вызов process_task для упрощённого теста
        result = await self.search_agent.process_task(task)
        
        logger.info(f"\n📊 RESULT:")
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Query: {result.get('query')}")
        logger.info(f"News count: {len(result.get('results', []))}")
        
        if result.get('summary'):
            logger.info(f"\n📝 Summary:\n{result['summary']}")
        
        if result.get('results'):
            logger.info(f"\n📰 Latest news:")
            for i, news in enumerate(result['results'][:3], 1):
                logger.info(f"  {i}. {news.get('title')}")
                logger.info(f"     Date: {news.get('date')}")
                logger.info(f"     Source: {news.get('source')}")
                logger.info(f"     URL: {news.get('url')}")
        
        return result
    
    async def test_instant_answer(self):
        """Тест быстрого ответа."""
        logger.info("\n" + "="*80)
        logger.info("⚡ TEST 3: Instant Answer - 'What is the capital of France?'")
        logger.info("="*80)
        
        task = {
            "type": "instant_answer",
            "query": "What is the capital of France?"
        }
        
        # Прямой вызов process_task для упрощённого теста
        result = await self.search_agent.process_task(task)
        
        logger.info(f"\n📊 RESULT:")
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Query: {result.get('query')}")
        
        if result.get('answer'):
            logger.info(f"\n💡 Instant Answer: {result['answer']}")
        
        if result.get('results'):
            logger.info(f"\n🔗 Additional results: {len(result['results'])} found")
        
        return result
    
    async def cleanup(self):
        """Очистка ресурсов."""
        logger.info("\n🧹 Cleaning up...")
        
        try:
            # Закрыть Redis
            await close_redis()
            
            logger.info("✅ Cleanup complete")
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")


async def main():
    """Главная функция."""
    test = SearchAgentTest()
    
    try:
        # Setup
        await test.setup()
        
        # Запуск агента
        await test.start_agent()
        
        # Тесты
        await test.test_web_search()
        await asyncio.sleep(2)
        
        await test.test_news_search()
        await asyncio.sleep(2)
        
        await test.test_instant_answer()
        
        logger.info("\n" + "="*80)
        logger.info("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
    finally:
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
