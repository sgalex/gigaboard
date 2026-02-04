"""
Тест извлечения данных AnalystAgent из реального контента
"""

import asyncio
import sys
import os
import json
from typing import Any, Optional

# Добавляем путь к backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.multi_agent.agents.analyst import AnalystAgent
from app.services.gigachat_service import GigaChatService
from app.services.multi_agent.message_bus import AgentMessageBus

# Минимальный контент для теста (из реального результата)
SAMPLE_RESEARCHER_DATA = {
    "status": "success",
    "pages": [
        {
            "url": "https://serokell.io/blog/rust-companies",
            "title": "9 Companies That Use Rust in Production",
            "content": """
9 Companies That Use Rust in Production

Dropbox uses Rust for parts of its file synchronization engine. 
Since the engine is highly concurrent, the team chose to rewrite it in Rust.
Rust's static types and heavy compile-time checks give it an advantage.

Coursera uses Rust for their programming assignments feature.
For security reasons, they needed to use a low-level language like Rust.
Rust offers complete immunity to certain classes of security vulnerabilities.

Figma rewrote their multiplayer syncing engine in Rust to improve performance.
We chose Rust because it combines best-in-class speed with low resource usage.

npm rewrote their main service in Rust because performance was becoming a bottleneck.
They rejected C and C++ since they didn't trust themselves with memory management.

Microsoft has been experimenting with integrating Rust into large C/C++ codebases.
For the last 12 years, around 70% of CVEs at Microsoft have been memory safety issues.

Cloudflare uses Rust in their core edge logic and as a replacement for C.
Their GitHub shows 18 open-source repositories that use Rust.

Discord ported pieces of their backend from Go to Rust to handle extreme concurrency.
Rust powers a system that handles billions of real-time messages per day.

Amazon Web Services (AWS) uses Rust for Firecracker - micro-VM technology.
Firecracker powers AWS Lambda and AWS Fargate.

Google uses Rust in Android Open Source Project for memory safety in low-level components.
            """,
            "status_code": 200
        },
        {
            "url": "https://benchmarksgame-team.pages.debian.net/benchmarksgame/fastest/rust-go.html",
            "title": "Rust vs Go - Benchmarks",
            "content": """
Rust vs Go Performance Comparison

Binary Trees: Rust 2.5x faster than Go
N-Body: Rust 1.8x faster than Go
Fannkuch-Redux: Rust 2.1x faster than Go
Spectral-Norm: Rust 1.5x faster than Go
Mandelbrot: Rust 2.0x faster than Go

Memory Usage:
Rust: 15MB average
Go: 45MB average (3x more due to garbage collector)

Rust consistently outperforms Go in CPU-intensive tasks.
Go's garbage collector adds overhead in tight loops.
            """
        }
    ],
    "pages_fetched": 2,
    "agent": "researcher"
}


async def test_extraction_with_logging():
    """Тест извлечения с подробным логированием"""
    print("\n" + "="*80)
    print("🧪 ANALYST EXTRACTION TEST")
    print("="*80 + "\n")
    
    # Инициализация
    print("🔧 Initializing AnalystAgent...")
    
    # Получаем API key из .env
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GIGACHAT_API_KEY")
    if not api_key:
        print("❌ GIGACHAT_API_KEY not found in .env")
        return
    
    gigachat = GigaChatService(api_key=api_key)
    
    # Создаем AgentMessageBus (без параметров)
    message_bus = AgentMessageBus()
    
    analyst = AnalystAgent(
        message_bus=message_bus,
        gigachat_service=gigachat
    )
    
    print("✅ AnalystAgent initialized\n")
    
    # Задача извлечения
    task = {
        "description": """extract structured data including:
- List of companies using Rust (name, use_case)
- Performance benchmarks (test_name, rust_time, go_time, speedup)
- Key insights about Rust adoption

Return as structured JSON with arrays."""
    }
    
    context = {
        "previous_results": {
            "researcher": SAMPLE_RESEARCHER_DATA
        }
    }
    
    # Проверяем prompt перед отправкой
    print("📝 Building prompt...")
    prompt = analyst._build_universal_prompt(task, context["previous_results"])
    
    print(f"\n📊 Prompt Statistics:")
    print(f"   Total length: {len(prompt)} characters")
    print(f"   Researcher data in prompt: {prompt.count('researcher')}")
    print(f"   Contains 'Dropbox': {'Yes' if 'Dropbox' in prompt else 'No'}")
    print(f"   Contains 'Binary Trees': {'Yes' if 'Binary Trees' in prompt else 'No'}")
    
    # Показываем первые и последние 500 символов промпта
    print(f"\n📄 Prompt Preview (first 500 chars):")
    print("-" * 80)
    print(prompt[:500])
    print("\n... [middle content] ...\n")
    print(f"\n📄 Prompt Preview (last 500 chars):")
    print("-" * 80)
    print(prompt[-500:])
    print("-" * 80)
    
    # Выполняем задачу
    print("\n🚀 Processing task...")
    result = await analyst.process_task(task, context)
    
    print("\n" + "="*80)
    print("📊 RESULT")
    print("="*80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Анализ результата
    print("\n" + "="*80)
    print("🔍 ANALYSIS")
    print("="*80)
    
    if result.get("status") == "success":
        print("✅ Status: SUCCESS")
        
        # Проверяем наличие данных
        has_companies = bool(result.get("companies") or result.get("company_usage"))
        has_benchmarks = bool(result.get("benchmarks") or result.get("benchmark_results"))
        has_insights = bool(result.get("insights") or result.get("message"))
        
        print(f"\n📊 Data Extracted:")
        print(f"   Companies: {'✅ Found' if has_companies else '❌ Missing'}")
        print(f"   Benchmarks: {'✅ Found' if has_benchmarks else '❌ Missing'}")
        print(f"   Insights: {'✅ Found' if has_insights else '❌ Missing'}")
        
        # Показываем детали
        if has_companies:
            companies = result.get("companies") or result.get("company_usage")
            if isinstance(companies, list):
                print(f"\n   Found {len(companies)} companies")
            elif isinstance(companies, dict):
                print(f"\n   Found companies: {list(companies.keys())[:5]}")
        
        if has_benchmarks:
            benchmarks = result.get("benchmarks") or result.get("benchmark_results")
            if isinstance(benchmarks, list):
                print(f"\n   Found {len(benchmarks)} benchmarks")
            elif isinstance(benchmarks, dict):
                print(f"\n   Found benchmarks: {list(benchmarks.keys())[:3]}")
        
    else:
        print(f"❌ Status: {result.get('status')}")
        print(f"   Error: {result.get('error', 'Unknown')}")
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_extraction_with_logging())
