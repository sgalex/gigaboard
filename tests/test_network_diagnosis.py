"""
Диагностика network issue для SearchAgent и DuckDuckGo
"""

import asyncio
import sys
import os

# Добавляем путь к backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

import httpx
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

async def test_basic_connectivity():
    """Проверка базовой сетевой связности"""
    print("\n" + "="*80)
    print("🔍 NETWORK DIAGNOSIS - Basic Connectivity")
    print("="*80 + "\n")
    
    test_urls = [
        ("Google", "https://www.google.com"),
        ("Bing", "https://www.bing.com"),
        ("DuckDuckGo", "https://duckduckgo.com"),
        ("GitHub", "https://github.com"),
    ]
    
    for name, url in test_urls:
        print(f"\n🌐 Testing {name}: {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.get(url)
                print(f"   ✅ Status: {response.status_code}")
                print(f"   📊 Response size: {len(response.content)} bytes")
        except httpx.ConnectTimeout:
            print(f"   ❌ Connection timeout")
        except httpx.ConnectError as e:
            print(f"   ❌ Connection error: {e}")
        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {e}")


async def test_ddgs_import():
    """Проверка импорта ddgs пакета"""
    print("\n" + "="*80)
    print("📦 PACKAGE TEST - DDGS Import")
    print("="*80 + "\n")
    
    try:
        from ddgs import DDGS
        print("✅ ddgs package imported successfully")
        
        # Проверяем инициализацию с правильными параметрами (ddgs 9.x)
        client = DDGS(
            timeout=20,
            verify=True
        )
        print("✅ DDGS client initialized")
        print(f"   Type: {type(client)}")
        
        # Проверяем доступные методы
        methods = [m for m in dir(client) if not m.startswith('_')]
        print(f"   Available methods: {', '.join(methods[:10])}...")
        
        return client
    except ImportError as e:
        print(f"❌ Failed to import ddgs: {e}")
        return None
    except Exception as e:
        print(f"❌ Error initializing DDGS: {type(e).__name__}: {e}")
        return None


async def test_ddgs_search(client):
    """Тест реального поиска через ddgs"""
    if not client:
        print("\n⚠️ Skipping search test - no client available")
        return
    
    print("\n" + "="*80)
    print("🔎 SEARCH TEST - DuckDuckGo Search")
    print("="*80 + "\n")
    
    test_queries = [
        "Python programming",
        "Rust language",
    ]
    
    for query in test_queries:
        print(f"\n🔍 Searching: '{query}'")
        try:
            # Используем метод text() для текстового поиска
            results = client.text(query, max_results=5)
            
            if results:
                print(f"   ✅ Found {len(results)} results")
                for i, result in enumerate(results, 1):
                    print(f"\n   Result {i}:")
                    print(f"      Title: {result.get('title', 'N/A')[:60]}...")
                    print(f"      URL: {result.get('href', 'N/A')[:70]}...")
                    print(f"      Body: {result.get('body', 'N/A')[:80]}...")
            else:
                print(f"   ⚠️ No results returned")
                
        except AttributeError as e:
            print(f"   ❌ Method error: {e}")
            print(f"   Available methods: {[m for m in dir(client) if not m.startswith('_')]}")
        except Exception as e:
            print(f"   ❌ Search error: {type(e).__name__}: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")


async def test_httpx_with_headers():
    """Проверка HTTPX с различными headers"""
    print("\n" + "="*80)
    print("🔧 HTTPX TEST - Different User-Agents")
    print("="*80 + "\n")
    
    test_cases = [
        ("No User-Agent", {}),
        ("Mozilla", {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }),
        ("Python httpx", {
            "User-Agent": "python-httpx/0.28.1"
        }),
    ]
    
    test_url = "https://www.bing.com/search?q=test"
    
    for name, headers in test_cases:
        print(f"\n🧪 Testing with: {name}")
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False, headers=headers) as client:
                response = await client.get(test_url)
                print(f"   ✅ Status: {response.status_code}")
                print(f"   📊 Content-Length: {len(response.content)}")
        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {e}")


async def test_ssl_verification():
    """Проверка SSL с разными настройками"""
    print("\n" + "="*80)
    print("🔐 SSL TEST - Verification Settings")
    print("="*80 + "\n")
    
    test_url = "https://www.bing.com"
    
    for verify in [True, False]:
        print(f"\n🔒 Testing with verify={verify}")
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=verify) as client:
                response = await client.get(test_url)
                print(f"   ✅ Status: {response.status_code}")
        except httpx.ConnectError as e:
            print(f"   ❌ SSL/Connection Error: {e}")
        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {e}")


async def main():
    """Запуск всех диагностических тестов"""
    print("\n" + "="*80)
    print("🏥 NETWORK & SEARCH DIAGNOSTICS")
    print("="*80)
    
    # 1. Базовая связность
    await test_basic_connectivity()
    
    # 2. Импорт ddgs
    client = await test_ddgs_import()
    
    # 3. Поиск через ddgs
    await test_ddgs_search(client)
    
    # 4. HTTPX с разными headers
    await test_httpx_with_headers()
    
    # 5. SSL verification
    await test_ssl_verification()
    
    print("\n" + "="*80)
    print("✅ DIAGNOSTICS COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
