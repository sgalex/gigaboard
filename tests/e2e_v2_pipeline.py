"""
E2E тест Multi-Agent V2 Pipeline с реальным GigaChat.

Запуск: python tests/e2e_v2_pipeline.py

Требования:
- Backend запущен на http://localhost:8000
- PostgreSQL и Redis доступны
- GIGACHAT_API_KEY настроен в .env
"""

import asyncio
import json
import sys
import time
import os
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path

# Load backend .env BEFORE importing app config
from dotenv import load_dotenv
backend_env = Path(__file__).parent.parent / "apps" / "backend" / ".env"
load_dotenv(backend_env, override=True)

sys.path.insert(0, "apps/backend")

import requests

# ─── Config ──────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
TIMEOUT = 120  # seconds per AI request


# ═══════════════════════════════════════════════════════════════════
# Helper: создать JWT без auth endpoint
# ═══════════════════════════════════════════════════════════════════

def create_test_token() -> tuple[str, str, str]:
    """Create JWT token directly using app config. Returns (token, user_id, project_id)."""
    from app.core.config import settings
    import jwt as pyjwt

    # Use existing user
    user_id = "e5dc48c5-c575-48ee-b423-9b0c38881744"  # sgalex78@gmail.com
    project_id = "fab0812f-c40d-4b44-81d4-e72fd1378742"  # Гигапроект

    expires_at = datetime.utcnow() + timedelta(hours=24)
    payload = {
        "sub": user_id,
        "username": "e2e_tester",
        "exp": expires_at,
        "iat": datetime.utcnow(),
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, user_id, project_id


# ═══════════════════════════════════════════════════════════════════
# Helper: API calls
# ═══════════════════════════════════════════════════════════════════

def api(method: str, path: str, token: str, json_data=None, timeout=TIMEOUT):
    """Make authenticated API call."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}{path}"
    r = getattr(requests, method)(url, headers=headers, json=json_data, timeout=timeout)
    return r


def print_result(label: str, r, show_body=True):
    """Print response status and timing."""
    elapsed = r.elapsed.total_seconds()
    status_icon = "✅" if r.status_code < 400 else "❌"
    print(f"\n{status_icon} {label}: {r.status_code} ({elapsed:.1f}s)")
    if show_body and r.text:
        try:
            body = r.json()
            # Truncate large responses
            text = json.dumps(body, ensure_ascii=False, indent=2)
            if len(text) > 2000:
                text = text[:2000] + "\n... (truncated)"
            print(text)
        except Exception:
            print(r.text[:500])


# ═══════════════════════════════════════════════════════════════════
# Step 1: Setup — create board & content node
# ═══════════════════════════════════════════════════════════════════

def setup_test_data(token: str, project_id: str) -> tuple[str, str]:
    """Create test board + content node. Returns (board_id, content_node_id)."""
    print("\n" + "=" * 60)
    print("📦 SETUP: Creating test data")
    print("=" * 60)

    # Create board
    r = api("post", "/api/v1/boards", token, {
        "name": f"E2E Test Board {datetime.now().strftime('%H:%M')}",
        "description": "Автоматический E2E тест Multi-Agent V2",
        "project_id": project_id,
    })
    print_result("Create Board", r)
    assert r.status_code == 201, f"Failed to create board: {r.text}"
    board_id = r.json()["id"]

    # Create content node with test data
    r = api("post", "/api/v1/content-nodes/", token, {
        "board_id": board_id,
        "content": {
            "text": "Данные о продажах по регионам за 2025 год",
            "tables": [{
                "id": str(uuid4()),
                "name": "sales_2025",
                "columns": [
                    {"name": "region", "type": "string"},
                    {"name": "q1_sales", "type": "number"},
                    {"name": "q2_sales", "type": "number"},
                    {"name": "q3_sales", "type": "number"},
                    {"name": "q4_sales", "type": "number"},
                    {"name": "total", "type": "number"},
                ],
                "rows": [
                    {"region": "Москва", "q1_sales": 1500, "q2_sales": 1800, "q3_sales": 1200, "q4_sales": 2100, "total": 6600},
                    {"region": "Санкт-Петербург", "q1_sales": 900, "q2_sales": 1100, "q3_sales": 800, "q4_sales": 1300, "total": 4100},
                    {"region": "Новосибирск", "q1_sales": 400, "q2_sales": 500, "q3_sales": 350, "q4_sales": 600, "total": 1850},
                    {"region": "Екатеринбург", "q1_sales": 350, "q2_sales": 420, "q3_sales": 380, "q4_sales": 550, "total": 1700},
                    {"region": "Казань", "q1_sales": 280, "q2_sales": 310, "q3_sales": 290, "q4_sales": 400, "total": 1280},
                ],
                "row_count": 5,
                "column_count": 6,
                "preview_row_count": 5,
            }],
        },
        "lineage": {
            "operation": "manual",
            "source_node_id": None,
            "transformation_id": None,
            "parent_content_ids": [],
            "timestamp": datetime.now().isoformat(),
            "agent": None,
        },
        "metadata": {"name": "Продажи 2025"},
        "position": {"x": 100, "y": 100},
    })
    print_result("Create ContentNode", r)
    assert r.status_code == 201, f"Failed to create content node: {r.text}"
    content_id = r.json()["id"]

    print(f"\n📍 Board ID: {board_id}")
    print(f"📍 ContentNode ID: {content_id}")
    return board_id, content_id


# ═══════════════════════════════════════════════════════════════════
# Test 1: Transform Preview (code generation, no execution)
# ═══════════════════════════════════════════════════════════════════

def test_transform_preview(token: str, content_id: str):
    print("\n" + "=" * 60)
    print("🧪 TEST 1: Transform Preview (Code Generation)")
    print("   Prompt: 'Отфильтруй регионы с total > 2000'")
    print("=" * 60)

    r = api("post", f"/api/v1/content-nodes/{content_id}/transform/preview", token, {
        "prompt": "Отфильтруй регионы с total продаж больше 2000",
    })
    print_result("Transform Preview", r)

    if r.status_code == 200:
        data = r.json()
        code = data.get("code", "")
        print(f"\n📝 Generated Code ({len(code)} chars):")
        print(code[:500] if code else "(empty)")
        return data
    return None


# ═══════════════════════════════════════════════════════════════════
# Test 2: Transform MultiAgent (full V2 pipeline)
# ═══════════════════════════════════════════════════════════════════

def test_transform_multiagent(token: str, content_id: str):
    print("\n" + "=" * 60)
    print("🧪 TEST 2: Transform MultiAgent (Full V2 Pipeline)")
    print("   Prompt: 'Добавь столбец growth_rate = (q4 - q1) / q1 * 100'")
    print("=" * 60)

    r = api("post", f"/api/v1/content-nodes/{content_id}/transform-multiagent", token, {
        "user_prompt": "Добавь столбец growth_rate, который считается как (q4_sales - q1_sales) / q1_sales * 100, округли до 1 знака",
        "preview_only": True,
    })
    print_result("Transform MultiAgent", r)

    if r.status_code == 200:
        data = r.json()
        code = data.get("code", "")
        mode = data.get("mode", "unknown")
        print(f"\n📝 Mode: {mode}")
        print(f"📝 Generated Code ({len(code) if code else 0} chars):")
        print((code[:500] if code else "(no code — discussion mode)"))
        return data
    return None


# ═══════════════════════════════════════════════════════════════════
# Test 3: Visualize (Widget Generation)
# ═══════════════════════════════════════════════════════════════════

def test_visualize(token: str, content_id: str):
    print("\n" + "=" * 60)
    print("🧪 TEST 3: Visualize (Widget Generation)")
    print("   Prompt: 'Построй гистограмму total продаж по регионам'")
    print("=" * 60)

    r = api("post", f"/api/v1/content-nodes/{content_id}/visualize-multiagent", token, {
        "user_prompt": "Построй гистограмму total продаж по регионам. Используй Chart.js.",
    })
    print_result("Visualize MultiAgent", r)

    if r.status_code == 200:
        data = r.json()
        widget_code = data.get("widget_code") or data.get("html_code", "")
        print(f"\n📝 Widget Code ({len(widget_code) if widget_code else 0} chars):")
        print((widget_code[:500] if widget_code else "(no widget code)"))
        return data
    return None


# ═══════════════════════════════════════════════════════════════════
# Test 4: AI Assistant Chat
# ═══════════════════════════════════════════════════════════════════

def test_ai_chat(token: str, board_id: str):
    print("\n" + "=" * 60)
    print("🧪 TEST 4: AI Assistant Chat")
    print("   Message: 'Какие данные есть на этой доске?'")
    print("=" * 60)

    r = api("post", f"/api/v1/boards/{board_id}/ai/chat", token, {
        "message": "Какие данные есть на этой доске? Кратко опиши.",
    })
    print_result("AI Chat", r)

    if r.status_code == 200:
        data = r.json()
        response_text = data.get("response", "")
        print(f"\n💬 AI Response ({len(response_text)} chars):")
        print(response_text[:800])
        return data
    return None


# ═══════════════════════════════════════════════════════════════════
# Test 5: Transform Suggestions
# ═══════════════════════════════════════════════════════════════════

def test_transform_suggestions(token: str, content_id: str):
    print("\n" + "=" * 60)
    print("🧪 TEST 5: Transform Suggestions")
    print("=" * 60)

    r = api("post", f"/api/v1/content-nodes/{content_id}/analyze-transform-suggestions", token, {
        "chat_history": [],
        "current_code": None,
    })
    print_result("Transform Suggestions", r)

    if r.status_code == 200:
        data = r.json()
        suggestions = data.get("suggestions", [])
        print(f"\n💡 Suggestions ({len(suggestions)}):")
        for s in suggestions[:3]:
            print(f"  - [{s.get('category', '?')}] {s.get('label', s.get('prompt', '?'))}")
        return data
    return None


# ═══════════════════════════════════════════════════════════════════
# Test 6: Widget Suggestions
# ═══════════════════════════════════════════════════════════════════

def test_widget_suggestions(token: str, content_id: str):
    print("\n" + "=" * 60)
    print("🧪 TEST 6: Widget Suggestions")
    print("=" * 60)

    r = api("post", f"/api/v1/content-nodes/{content_id}/analyze-suggestions", token, {
        "chat_history": [],
        "max_suggestions": 3,
    })
    print_result("Widget Suggestions", r)

    if r.status_code == 200:
        data = r.json()
        suggestions = data.get("suggestions", [])
        print(f"\n💡 Suggestions ({len(suggestions)}):")
        for s in suggestions[:3]:
            print(f"  - [{s.get('type', '?')}] {s.get('title', '?')}: {s.get('description', '')[:80]}")
        return data
    return None


# ═══════════════════════════════════════════════════════════════════
# Test 7: Discussion mode (no code expected)
# ═══════════════════════════════════════════════════════════════════

def test_discussion_mode(token: str, content_id: str):
    print("\n" + "=" * 60)
    print("🧪 TEST 7: Discussion Mode (Narrative, no code)")
    print("   Prompt: 'Объясни, какие тренды видны в данных'")
    print("=" * 60)

    r = api("post", f"/api/v1/content-nodes/{content_id}/transform-multiagent", token, {
        "user_prompt": "Объясни, какие тренды видны в данных? Не генерируй код, просто проанализируй.",
        "preview_only": True,
    })
    print_result("Discussion Mode", r)

    if r.status_code == 200:
        data = r.json()
        mode = data.get("mode", "unknown")
        desc = data.get("description", "")
        print(f"\n📝 Mode: {mode}")
        print(f"📝 Narrative ({len(desc)} chars):")
        print(desc[:600] if desc else "(empty)")
        return data
    return None


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("🚀 GigaBoard E2E Test — Multi-Agent V2 Pipeline")
    print(f"   Backend: {BASE_URL}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check backend health
    try:
        r = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        health = r.json()
        print(f"\n✅ Backend healthy: DB={health.get('database')}, Redis={health.get('redis')}, GigaChat={health.get('gigachat')}")
    except Exception as e:
        print(f"\n❌ Backend not available: {e}")
        sys.exit(1)

    # Create auth token
    token, user_id, project_id = create_test_token()
    print(f"🔑 Token created for user {user_id[:8]}...")

    # Verify token works
    r = api("get", "/api/v1/boards", token)
    if r.status_code == 403:
        print("❌ Token rejected — check JWT_SECRET_KEY")
        sys.exit(1)
    print(f"✅ Auth works (boards: {r.status_code})")

    # Setup test data
    board_id, content_id = setup_test_data(token, project_id)

    # Run tests
    results = {}
    total_start = time.time()

    tests = [
        ("1_transform_preview", lambda: test_transform_preview(token, content_id)),
        ("2_transform_multiagent", lambda: test_transform_multiagent(token, content_id)),
        ("3_visualize", lambda: test_visualize(token, content_id)),
        ("4_ai_chat", lambda: test_ai_chat(token, board_id)),
        ("5_transform_suggestions", lambda: test_transform_suggestions(token, content_id)),
        ("6_widget_suggestions", lambda: test_widget_suggestions(token, content_id)),
        ("7_discussion_mode", lambda: test_discussion_mode(token, content_id)),
    ]

    for name, test_fn in tests:
        try:
            start = time.time()
            result = test_fn()
            elapsed = time.time() - start
            results[name] = {"status": "PASS" if result else "FAIL", "time": elapsed}
        except Exception as e:
            results[name] = {"status": "ERROR", "error": str(e)}
            print(f"\n❌ {name}: {e}")

    # Summary
    total_time = time.time() - total_start
    print("\n" + "=" * 60)
    print("📊 E2E TEST SUMMARY")
    print("=" * 60)
    for name, info in results.items():
        icon = "✅" if info["status"] == "PASS" else "❌"
        time_str = f"{info.get('time', 0):.1f}s" if "time" in info else "N/A"
        print(f"  {icon} {name}: {info['status']} ({time_str})")
    
    passed = sum(1 for v in results.values() if v["status"] == "PASS")
    total = len(results)
    print(f"\n  Total: {passed}/{total} passed in {total_time:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
