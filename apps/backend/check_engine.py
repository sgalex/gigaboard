"""
Quick script to check MultiAgentEngine initialization status.
Run: uv run python apps/backend/check_engine.py
"""
import asyncio
from app.core.redis import init_redis, close_redis
from app.services.gigachat_service import GigaChatService
from app.services.multi_agent.engine import MultiAgentEngine
from app.core.config import settings

async def check():
    print("🔍 Checking MultiAgentEngine initialization...\n")
    
    # Check Redis
    print("1. Redis connection:")
    try:
        await init_redis()
        print("   ✅ Redis connected")
        redis_ok = True
    except Exception as e:
        print(f"   ❌ Redis failed: {e}")
        redis_ok = False
    
    # Check GigaChat
    print("\n2. GigaChat service:")
    gigachat_ok = False
    if settings.GIGACHAT_API_KEY:
        try:
            gigachat = GigaChatService(api_key=settings.GIGACHAT_API_KEY)
            print(f"   ✅ GigaChat initialized (model: {settings.GIGACHAT_MODEL})")
            gigachat_ok = True
        except Exception as e:
            print(f"   ❌ GigaChat failed: {e}")
    else:
        print("   ❌ GIGACHAT_API_KEY not set")
    
    # Check MultiAgentEngine
    print("\n3. MultiAgentEngine:")
    if redis_ok and gigachat_ok:
        try:
            engine = MultiAgentEngine(
                gigachat_api_key=settings.GIGACHAT_API_KEY,
                enable_agents=["suggestions"],
                adaptive_planning=False
            )
            await engine.initialize()
            
            print(f"   ✅ Engine initialized")
            print(f"   ✅ Agents: {list(engine.agents.keys())}")
            
            if "suggestions" in engine.agents:
                print("   ✅ WidgetSuggestionAgent available")
            else:
                print("   ❌ WidgetSuggestionAgent not found")
            
            await engine.shutdown()
        except Exception as e:
            print(f"   ❌ Engine initialization failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⏭️  Skipped (requires Redis + GigaChat)")
    
    # Cleanup
    if redis_ok:
        await close_redis()

if __name__ == "__main__":
    asyncio.run(check())
