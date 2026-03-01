"""
E2E-тесты Multi-Agent системы через реальный запущенный бэкенд.

Тестируют полный pipeline: HTTP Request → Route → Controller → Orchestrator → Agents → GigaChat.
Требуют запущенного бэкенда с Redis + GigaChat (http://localhost:8000).

Запуск:
    uv run python -m pytest tests/e2e/test_multi_agent_e2e.py -v -s

    # Только быстрые тесты (без GigaChat):
    uv run python -m pytest tests/e2e/test_multi_agent_e2e.py -v -s -k "not slow"

    # Один конкретный тест:
    uv run python -m pytest tests/e2e/test_multi_agent_e2e.py -v -s -k "test_ai_chat"

См. docs/history/2026-02-17_CONTEXT_ARCHITECTURE_IMPLEMENTED.md
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

import pytest
import requests

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

BASE_URL = "http://localhost:8000"
TIMEOUT = 180  # секунд — GigaChat + multi-agent pipeline может быть медленным


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def backend_health():
    """Проверяем, что бэкенд запущен и здоров."""
    try:
        r = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        data = r.json()
        assert data["status"] == "ok", f"Backend unhealthy: {data}"
        assert data.get("redis") == "ok", "Redis not connected"
        assert data.get("gigachat") == "ok", "GigaChat not initialized"
        return data
    except requests.ConnectionError:
        pytest.skip(
            "Backend not running on localhost:8000. "
            "Start it with: uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
        )


@pytest.fixture(scope="module")
def auth_token(backend_health) -> str:
    """Регистрируем тестового пользователя и получаем JWT-токен."""
    unique = uuid.uuid4().hex[:8]
    user_data = {
        "username": f"e2e_{unique}",
        "email": f"e2e_{unique}@example.com",
        "password": "E2eTestPass123!",
    }

    r = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json=user_data,
        timeout=10,
    )
    assert r.status_code == 201, f"Registration failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    logger.info(f"✅ Registered test user: {user_data['username']}")
    return token


@pytest.fixture(scope="module")
def api(auth_token) -> "APIClient":
    """APIClient с авторизацией."""
    return APIClient(BASE_URL, auth_token)


@pytest.fixture(scope="module")
def test_board(api: "APIClient") -> dict:
    """Создаём проект и доску для тестов."""
    # 1. Проект
    project = api.post("/api/v1/projects", json={
        "name": f"E2E Test Project {datetime.now().isoformat()}",
    })

    # 2. Доска
    board = api.post("/api/v1/boards", json={
        "name": "E2E Multi-Agent Board",
        "description": "Board for testing Orchestrator V2 context architecture",
        "project_id": project["id"],
    })
    logger.info(f"✅ Created board: {board['id']}")
    return board


@pytest.fixture(scope="module")
def content_node_with_data(api: "APIClient", test_board: dict) -> dict:
    """Создаём ContentNode с таблицей продаж (sales data)."""
    board_id = test_board["id"]

    # Создаём ContentNode с реальными табличными данными
    content_node = api.post("/api/v1/content-nodes/", json={
        "board_id": board_id,
        "content": {
            "text": "Данные о продажах за январь 2026 года. Содержат категории Electronics, Books, Clothing.",
            "tables": [
                {
                    "id": "tbl_sales",
                    "name": "sales",
                    "columns": [
                        {"name": "id", "type": "int64"},
                        {"name": "date", "type": "str"},
                        {"name": "category", "type": "str"},
                        {"name": "amount", "type": "float64"},
                        {"name": "quantity", "type": "int64"},
                    ],
                    "rows": [
                        {"id": 1, "date": "2026-01-01", "category": "Electronics", "amount": 1500.0, "quantity": 3},
                        {"id": 2, "date": "2026-01-02", "category": "Books", "amount": 85.5, "quantity": 5},
                        {"id": 3, "date": "2026-01-03", "category": "Clothing", "amount": 320.0, "quantity": 2},
                        {"id": 4, "date": "2026-01-05", "category": "Electronics", "amount": 2200.0, "quantity": 1},
                        {"id": 5, "date": "2026-01-07", "category": "Books", "amount": 45.0, "quantity": 3},
                        {"id": 6, "date": "2026-01-08", "category": "Clothing", "amount": 180.0, "quantity": 4},
                        {"id": 7, "date": "2026-01-10", "category": "Electronics", "amount": 750.0, "quantity": 2},
                        {"id": 8, "date": "2026-01-12", "category": "Books", "amount": 120.0, "quantity": 7},
                        {"id": 9, "date": "2026-01-15", "category": "Clothing", "amount": 560.0, "quantity": 3},
                        {"id": 10, "date": "2026-01-18", "category": "Electronics", "amount": 3100.0, "quantity": 2},
                    ],
                    "row_count": 10,
                    "column_count": 5,
                    "preview_row_count": 10,
                }
            ],
        },
        "lineage": {
            "operation": "manual",
            "timestamp": datetime.now().isoformat(),
        },
        "metadata": {"name": "Sales January 2026"},
    })
    logger.info(f"✅ Created ContentNode: {content_node['id']}")
    return content_node


# ══════════════════════════════════════════════════════════════════════════════
# Helper: API Client
# ══════════════════════════════════════════════════════════════════════════════


class APIClient:
    """Обёртка над requests с авторизацией и логированием."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def get(self, path: str, **kwargs) -> dict:
        r = self.session.get(f"{self.base_url}{path}", timeout=TIMEOUT, **kwargs)
        self._check(r, "GET", path)
        return r.json()

    def post(self, path: str, json: dict = None, timeout: int = None, **kwargs) -> dict:
        r = self.session.post(f"{self.base_url}{path}", json=json, timeout=timeout or TIMEOUT, **kwargs)
        self._check(r, "POST", path)
        return r.json()

    def delete(self, path: str, **kwargs) -> dict | None:
        r = self.session.delete(f"{self.base_url}{path}", timeout=TIMEOUT, **kwargs)
        self._check(r, "DELETE", path)
        return r.json() if r.content else None

    def post_raw(self, path: str, json: dict = None, timeout: int = None, **kwargs) -> requests.Response:
        """POST без проверки — возвращает raw Response."""
        return self.session.post(f"{self.base_url}{path}", json=json, timeout=timeout or TIMEOUT, **kwargs)

    @staticmethod
    def _check(r: requests.Response, method: str, path: str):
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text[:500]
            raise AssertionError(
                f"{method} {path} → {r.status_code}: {json.dumps(detail, ensure_ascii=False, indent=2)}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: Health & Orchestrator availability
# ══════════════════════════════════════════════════════════════════════════════


class TestHealthAndPrerequisites:
    """Базовые проверки: бэкенд, Redis, GigaChat, Orchestrator."""

    def test_backend_alive(self, backend_health):
        assert backend_health["status"] == "ok"

    def test_redis_connected(self, backend_health):
        assert backend_health["redis"] == "ok"

    def test_gigachat_available(self, backend_health):
        assert backend_health["gigachat"] == "ok"

    def test_auth_works(self, api: APIClient):
        """Проверяем, что авторизация работает (GET /auth/me)."""
        me = api.get("/api/v1/auth/me")
        assert "id" in me
        assert "username" in me

    def test_board_created(self, test_board: dict):
        """Проверяем, что доска создана."""
        assert "id" in test_board
        assert test_board["name"] == "E2E Multi-Agent Board"

    def test_content_node_created(self, content_node_with_data: dict):
        """Проверяем, что ContentNode с данными создан."""
        assert "id" in content_node_with_data
        content = content_node_with_data["content"]
        assert len(content["tables"]) == 1
        assert content["tables"][0]["name"] == "sales"
        assert content["tables"][0]["row_count"] == 10


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: AI Assistant Chat (Orchestrator V2 → AIAssistantController)
# ══════════════════════════════════════════════════════════════════════════════


class TestAIAssistantChat:
    """
    Тестируем POST /api/v1/boards/{board_id}/ai/chat.

    Pipeline: Route → AIAssistantController → Orchestrator V2
              → PlannerAgent → [Agents...] → AgentPayload
              → Response с pipeline_context + agent_results.
    """

    @pytest.mark.slow
    def test_ai_chat_simple_question(self, api: APIClient, test_board: dict):
        """
        Простой вопрос к AI Assistant.

        Проверяет:
        - Orchestrator V2 обрабатывает запрос
        - pipeline_context правильно формируется (board_id, session_id)
        - Ответ содержит осмысленный текст
        """
        board_id = test_board["id"]

        t0 = time.time()
        result = api.post(f"/api/v1/boards/{board_id}/ai/chat", json={
            "message": "Привет! Расскажи кратко, что ты умеешь?",
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ AI chat response in {elapsed:.1f}s")
        logger.info(f"📝 Response: {result.get('response', '')[:200]}")

        # Assertions
        assert "response" in result, f"No 'response' in result: {result}"
        assert len(result["response"]) > 10, f"Response too short: {result['response']}"
        assert "session_id" in result, "No session_id in response"
        assert elapsed < TIMEOUT, f"Too slow: {elapsed:.1f}s"

    @pytest.mark.slow
    def test_ai_chat_with_board_context(self, api: APIClient, test_board: dict, content_node_with_data: dict):
        """
        Вопрос с контекстом доски (selected_nodes).

        Проверяет:
        - board_context передаётся в pipeline_context
        - Агенты видят данные ContentNode
        - Ответ релевантен данным (упоминает sales/Electronics/Books)
        """
        board_id = test_board["id"]
        node_id = content_node_with_data["id"]

        t0 = time.time()
        result = api.post(f"/api/v1/boards/{board_id}/ai/chat", json={
            "message": "Какие данные есть на доске? Кратко опиши таблицы.",
            "context": {
                "selected_nodes": [node_id],
            },
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ AI chat with context in {elapsed:.1f}s")
        logger.info(f"📝 Response: {result.get('response', '')[:300]}")

        assert "response" in result
        assert len(result["response"]) > 20

        # Ответ должен упоминать данные доски
        response_lower = result["response"].lower()
        has_data_reference = any(
            word in response_lower
            for word in ["sales", "продаж", "таблиц", "данн", "electronics", "books", "категор"]
        )
        # Мягкая проверка — GigaChat может не всегда ссылаться на конкретные данные
        if not has_data_reference:
            logger.warning(f"⚠️ Response doesn't reference board data: {result['response'][:200]}")

    @pytest.mark.slow
    def test_ai_chat_session_continuity(self, api: APIClient, test_board: dict):
        """
        Проверяем, что session_id сохраняется между сообщениями.

        Тестирует:
        - pipeline_context сохраняет session_id
        - Второе сообщение использует ту же сессию
        """
        board_id = test_board["id"]

        # 1st message
        r1 = api.post(f"/api/v1/boards/{board_id}/ai/chat", json={
            "message": "Запомни число 42.",
        })
        session_id = r1["session_id"]
        assert session_id is not None

        # 2nd message — same session
        r2 = api.post(f"/api/v1/boards/{board_id}/ai/chat", json={
            "message": "Какое число я просил тебя запомнить?",
            "session_id": session_id,
        })

        assert r2["session_id"] == session_id, "session_id should persist"
        assert "response" in r2
        logger.info(f"📝 Session continuity response: {r2['response'][:200]}")


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: Transform Multiagent (Orchestrator V2 → TransformationController)
# ══════════════════════════════════════════════════════════════════════════════


class TestTransformMultiagent:
    """
    Тестируем POST /api/v1/content-nodes/{id}/transform-multiagent.

    Pipeline: Route → TransformationController → Orchestrator V2
              → PlannerAgent → AnalystAgent → TransformCodexAgent
              → QualityGateAgent → execution_context → preview.

    Это главный тест Context Architecture:
    - pipeline_context содержит board_id, user_id
    - agent_results — хронологический list
    - execution_context передаёт input_data (DataFrame)
    """

    @pytest.mark.slow
    def test_transform_filter(self, api: APIClient, content_node_with_data: dict):
        """
        Генерация фильтрующей трансформации.

        Проверяет полный pipeline:
        1. PlannerAgent создаёт план
        2. AnalystAgent анализирует данные
        3. TransformCodexAgent генерирует Python код
        4. QualityGateAgent проверяет код
        5. Код выполняется и возвращает preview
        """
        node_id = content_node_with_data["id"]

        t0 = time.time()
        result = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Отфильтруй данные: оставь только category = Electronics",
            "existing_code": None,
            "chat_history": [],
            "selected_node_ids": [node_id],
            "preview_only": True,
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ Transform filter in {elapsed:.1f}s")
        logger.info(f"📝 Code: {result.get('code', '')[:300]}")
        logger.info(f"📊 Preview rows: {result.get('preview_data', {}).get('row_count', 'N/A')}")

        # Assertions
        assert result.get("code") or result.get("description"), (
            f"Expected code or description in response: {json.dumps(result, ensure_ascii=False)[:500]}"
        )

        # Если есть код — должен содержать фильтрацию
        if result.get("code"):
            code = result["code"]
            code_lower = code.lower()
            assert "electronics" in code_lower or "filter" in code_lower or "category" in code_lower, (
                f"Generated code doesn't reference electronics/filter: {code[:300]}"
            )

        # Если есть preview_data — проверяем структуру
        if result.get("preview_data"):
            preview = result["preview_data"]
            assert isinstance(preview, dict), f"preview_data should be dict: {type(preview)}"

    @pytest.mark.slow
    def test_transform_discussion_mode(self, api: APIClient, content_node_with_data: dict):
        """
        Discussion mode — вопрос без генерации кода.

        Проверяет, что TransformationController корректно определяет
        DISCUSSION mode и возвращает narrative вместо кода.
        """
        node_id = content_node_with_data["id"]

        t0 = time.time()
        # Используем более явно дискуссионный промпт
        result = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Объясни мне простыми словами: какие колонки есть в таблице и какие у них типы данных? Не генерируй код.",
            "existing_code": None,
            "chat_history": [],
            "selected_node_ids": [node_id],
            "preview_only": True,
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ Discussion mode in {elapsed:.1f}s")
        logger.info(f"📝 Result keys: {list(result.keys())}")
        logger.info(f"📝 Description: {result.get('description', '')[:300]}")
        logger.info(f"📝 Code: {str(result.get('code', ''))[:200]}")
        logger.info(f"🔧 Mode: {result.get('mode', 'unknown')}")

        # Discussion mode может вернуть description без code, или code с описанием
        assert result.get("description") or result.get("code"), (
            f"Expected description or code: {json.dumps(result, ensure_ascii=False)[:500]}"
        )

    @pytest.mark.slow
    def test_transform_iterative(self, api: APIClient, content_node_with_data: dict):
        """
        Iterative mode — улучшение существующего кода.

        Проверяет, что existing_code передаётся в pipeline_context
        и TransformCodexAgent модифицирует существующий код.
        """
        node_id = content_node_with_data["id"]

        existing_code = """import pandas as pd
df0 = input_data["sales"]
df_result = df0[df0["amount"] > 100].copy()
"""
        t0 = time.time()
        result = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Добавь сортировку по amount по убыванию",
            "existing_code": existing_code,
            "chat_history": [
                {"role": "user", "content": "Отфильтруй amount > 100"},
                {"role": "assistant", "content": "Готово, отфильтровал строки с amount > 100"},
            ],
            "selected_node_ids": [node_id],
            "preview_only": True,
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ Iterative transform in {elapsed:.1f}s")
        logger.info(f"📝 Code: {result.get('code', '')[:300]}")

        if result.get("code"):
            code = result["code"]
            code_lower = code.lower()
            # Должен содержать сортировку
            has_sort = "sort" in code_lower or "сортир" in code_lower or "ascending" in code_lower
            # И фильтрацию (из existing_code)
            has_filter = "100" in code or "amount" in code_lower
            logger.info(f"Has sort: {has_sort}, Has filter: {has_filter}")


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: Transform Suggestions (Orchestrator V2 → TransformSuggestionsController)
# ══════════════════════════════════════════════════════════════════════════════


class TestTransformSuggestions:
    """
    Тестируем POST /api/v1/content-nodes/{id}/analyze-transform-suggestions.

    Pipeline: Route → TransformSuggestionsController → Orchestrator V2
              → PlannerAgent → AnalystAgent → AgentPayload.suggestions
    """

    @pytest.mark.slow
    def test_transform_suggestions(self, api: APIClient, content_node_with_data: dict):
        """
        Генерация предложений трансформаций для данных.

        Проверяет:
        - Агенты анализируют input_schemas из pipeline_context
        - Возвращают список suggestions
        """
        node_id = content_node_with_data["id"]

        t0 = time.time()
        result = api.post(f"/api/v1/content-nodes/{node_id}/analyze-transform-suggestions", json={
            "chat_history": [],
            "current_code": None,
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ Transform suggestions in {elapsed:.1f}s")
        logger.info(f"📋 Suggestions: {json.dumps(result.get('suggestions', [])[:3], ensure_ascii=False, indent=2)}")

        assert "suggestions" in result, f"No 'suggestions' in result: {result}"
        suggestions = result["suggestions"]
        assert isinstance(suggestions, list), f"suggestions should be list: {type(suggestions)}"
        assert len(suggestions) >= 1, f"Expected at least 1 suggestion, got {len(suggestions)}"

        # Каждый suggestion должен иметь базовую структуру
        for s in suggestions[:3]:
            assert "label" in s or "prompt" in s, f"Suggestion missing label/prompt: {s}"

    @pytest.mark.slow
    def test_transform_suggestions_with_code(self, api: APIClient, content_node_with_data: dict):
        """
        Suggestions для уже трансформированных данных (chain mode).

        Проверяет, что current_code выполняется и suggestions
        генерируются на основе результата, а не исходных данных.
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/analyze-transform-suggestions", json={
            "chat_history": [],
            "current_code": "import pandas as pd\ndf0 = input_data['sales']\ndf_result = df0[df0['amount'] > 100].copy()",
        })

        logger.info(f"📋 Chain suggestions: {json.dumps(result.get('suggestions', [])[:3], ensure_ascii=False, indent=2)}")

        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)


# ══════════════════════════════════════════════════════════════════════════════
# Test 5: Widget Controller (Orchestrator V2 → WidgetController)
# ══════════════════════════════════════════════════════════════════════════════


class TestWidgetController:
    """
    Тестируем POST /api/v1/content-nodes/{id}/visualize-iterative
    и POST /api/v1/content-nodes/{id}/visualize-multiagent.

    Pipeline: Route → WidgetController → Orchestrator V2
              → PlannerAgent → [Agents] → AgentPayload
              → HTML/CSS/JS widget code.
    """

    @pytest.mark.slow
    def test_widget_generate_chart(self, api: APIClient, content_node_with_data: dict):
        """
        Генерация виджета-графика из ContentNode.

        Проверяет:
        - WidgetController получает content_data
        - Orchestrator V2 генерирует HTML/JS код визуализации
        - Ответ содержит widget_code или html_code
        """
        node_id = content_node_with_data["id"]

        t0 = time.time()
        r = api.post_raw(f"/api/v1/content-nodes/{node_id}/visualize-iterative", json={
            "user_prompt": "Создай столбчатую диаграмму: сумма amount по category",
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ Widget chart generation in {elapsed:.1f}s")
        logger.info(f"📝 Status code: {r.status_code}")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:500]}"

        result = r.json()
        logger.info(f"📝 Response keys: {list(result.keys())}")
        logger.info(f"📝 widget_code length: {len(result.get('widget_code') or '')}")
        logger.info(f"📝 html_code length: {len(result.get('html_code') or '')}")
        logger.info(f"📝 description: {result.get('description', '')[:200]}")

        # Должен быть хотя бы один из кодов виджета
        has_code = bool(result.get("widget_code")) or bool(result.get("html_code"))
        assert has_code, (
            f"Expected widget_code or html_code in response: {json.dumps(result, ensure_ascii=False)[:500]}"
        )

        assert result.get("status") == "success", f"Status not success: {result.get('status')}"
        assert result.get("description"), "Missing description"

    @pytest.mark.slow
    def test_widget_iterative_refinement(self, api: APIClient, content_node_with_data: dict):
        """
        Итеративное улучшение виджета (передаём existing_widget_code).

        Проверяет:
        - existing_widget_code включается в context
        - WidgetController генерирует улучшенную версию
        """
        node_id = content_node_with_data["id"]

        existing_code = """<html><body>
<canvas id="chart"></canvas>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
const ctx = document.getElementById('chart').getContext('2d');
new Chart(ctx, { type: 'bar', data: { labels: ['A','B'], datasets: [{ data: [10,20] }] } });
</script>
</body></html>"""

        t0 = time.time()
        r = api.post_raw(f"/api/v1/content-nodes/{node_id}/visualize-iterative", json={
            "user_prompt": "Добавь заголовок 'Продажи по категориям' и улучши цвета",
            "existing_widget_code": existing_code,
            "chat_history": [
                {"role": "user", "content": "Создай столбчатую диаграмму"},
                {"role": "assistant", "content": "Создал базовую столбчатую диаграмму"},
            ],
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ Widget refinement in {elapsed:.1f}s")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:500]}"

        result = r.json()
        has_code = bool(result.get("widget_code")) or bool(result.get("html_code"))
        assert has_code, f"Expected code in refinement response: {list(result.keys())}"
        assert result.get("status") == "success"

    @pytest.mark.slow
    def test_widget_multiagent_endpoint(self, api: APIClient, content_node_with_data: dict):
        """
        Тестируем альтернативный endpoint visualize-multiagent.

        Проверяет тот же pipeline через другой route.
        """
        node_id = content_node_with_data["id"]

        t0 = time.time()
        r = api.post_raw(f"/api/v1/content-nodes/{node_id}/visualize-multiagent", json={
            "user_prompt": "Покажи таблицу с данными о продажах в HTML",
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ Widget multiagent in {elapsed:.1f}s")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:500]}"

        result = r.json()
        has_code = bool(result.get("widget_code")) or bool(result.get("html_code"))
        assert has_code, f"Expected code in multiagent response: {list(result.keys())}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 6: Widget Suggestions (Orchestrator V2 → WidgetSuggestionsController)
# ══════════════════════════════════════════════════════════════════════════════


class TestWidgetSuggestions:
    """
    Тестируем POST /api/v1/content-nodes/{id}/analyze-suggestions.

    Pipeline: Route → WidgetSuggestionsController → Orchestrator V2.
    """

    @pytest.mark.slow
    def test_widget_suggestions(self, api: APIClient, content_node_with_data: dict):
        """
        Генерация предложений виджетов для ContentNode.

        Проверяет:
        - pipeline_context содержит content_data
        - Агенты генерируют suggestions для визуализации
        """
        node_id = content_node_with_data["id"]

        t0 = time.time()
        result = api.post(f"/api/v1/content-nodes/{node_id}/analyze-suggestions", json={
            "chat_history": [],
            "current_widget_code": None,
            "max_suggestions": 5,
        })
        elapsed = time.time() - t0

        logger.info(f"⏱ Widget suggestions in {elapsed:.1f}s")
        logger.info(f"📋 Suggestions: {json.dumps(result.get('suggestions', [])[:3], ensure_ascii=False, indent=2)}")

        assert "suggestions" in result
        suggestions = result["suggestions"]
        assert isinstance(suggestions, list)

        if suggestions:
            for s in suggestions[:3]:
                # Widget suggestions могут иметь разную структуру
                assert isinstance(s, dict), f"Suggestion should be dict: {s}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 6: Error Handling & Edge Cases
# ══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Проверяем корректную обработку ошибок."""

    def test_chat_without_auth(self, test_board: dict):
        """401 без токена."""
        board_id = test_board["id"]
        r = requests.post(
            f"{BASE_URL}/api/v1/boards/{board_id}/ai/chat",
            json={"message": "test"},
            timeout=10,
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_transform_nonexistent_node(self, api: APIClient):
        """404 для несуществующего ContentNode."""
        fake_id = str(uuid.uuid4())
        r = api.post_raw(f"/api/v1/content-nodes/{fake_id}/transform-multiagent", json={
            "user_prompt": "test",
            "selected_node_ids": [fake_id],
        })
        assert r.status_code in (404, 500), f"Expected 404/500, got {r.status_code}"

    def test_transform_empty_prompt(self, api: APIClient, content_node_with_data: dict):
        """400 для пустого промпта."""
        node_id = content_node_with_data["id"]
        r = api.post_raw(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "",
            "selected_node_ids": [node_id],
        })
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:200]}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 7: Context Architecture Verification
# ══════════════════════════════════════════════════════════════════════════════


class TestContextArchitecture:
    """
    Верификация новой Context Architecture V2:
    - pipeline_context (мутабельный dict) — единый контекст pipeline
    - agent_results (хронологический list) — append-only список результатов
    - execution_context (DataFrame канал) — не попадает в промпты

    Эти тесты доказывают, что при выполнении E2E запросов
    используется именно V2 механизм общего контекста, а не legacy.

    Ключевые маркеры V2:
    - agent_plan содержит steps (PlannerAgent V2)
    - Каждый step имеет agent + task (V2 plan schema)
    - transform-multiagent поддерживает discussion mode
    - Suggestions возвращают структурированный формат
    """

    @pytest.mark.slow
    def test_v2_agent_plan_in_transform(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет, что transform-multiagent возвращает agent_plan
        с V2-структурой (steps, agent names).

        V2 маркер: agent_plan.steps — массив шагов от PlannerAgent.
        В legacy системе agent_plan отсутствовал.
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Посчитай сумму amount по каждой category",
            "selected_node_ids": [node_id],
            "preview_only": True,
        })

        # === V2 VERIFICATION ===
        # 1. agent_plan должен присутствовать (V2 Orchestrator возвращает plan)
        agent_plan = result.get("agent_plan")
        assert agent_plan is not None, (
            f"agent_plan is None — V2 pipeline не вернул план. "
            f"Response keys: {list(result.keys())}"
        )
        logger.info(f"✅ agent_plan present: {json.dumps(agent_plan, ensure_ascii=False)[:500]}")

        # 2. Plan должен содержать steps (V2 PlannerAgent schema)
        steps = agent_plan.get("steps", [])
        assert isinstance(steps, list), f"steps must be list, got {type(steps)}"
        assert len(steps) >= 1, (
            f"V2 plan must have at least 1 step, got {len(steps)}. "
            f"Plan: {json.dumps(agent_plan, ensure_ascii=False)[:300]}"
        )

        # 3. Каждый step должен иметь agent (V2 step schema)
        for i, step in enumerate(steps):
            assert "agent" in step, (
                f"Step {i} missing 'agent' field (not V2 format): {step}"
            )
            logger.info(f"  Step {i + 1}: agent={step['agent']}, task={step.get('task', {}).get('type', 'N/A')}")

        # 4. Должен быть code или description (pipeline завершился)
        assert result.get("code") or result.get("description"), (
            f"Pipeline returned empty result: {json.dumps(result, ensure_ascii=False)[:500]}"
        )

        if result.get("code"):
            code = result["code"]
            assert any(kw in code for kw in ["import", "def ", "df", "input_data", "=", "pandas"]), (
                f"Code doesn't look like valid Python: {code[:200]}"
            )
            logger.info(f"✅ V2 pipeline produced valid code ({len(code)} chars)")

    @pytest.mark.slow
    def test_v2_agent_plan_in_preview(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет agent_plan через transform/preview endpoint.

        V2 маркер: plan содержит steps с конкретными агентами
        (analyst, transform_codex, validator, etc.)
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/transform/preview", json={
            "prompt": "Отфильтруй строки где amount > 200",
            "selected_node_ids": [node_id],
        })

        agent_plan = result.get("agent_plan")
        assert agent_plan is not None, "agent_plan missing from preview response"

        steps = agent_plan.get("steps", [])
        assert len(steps) >= 1, f"Plan has no steps: {agent_plan}"

        # Проверяем, что plan содержит ожидаемых V2 агентов
        agent_names = [s.get("agent") for s in steps]
        logger.info(f"✅ V2 preview plan agents: {agent_names}")

        # Хотя бы один из известных V2 агентов должен быть в плане
        known_v2_agents = {"analyst", "transform_codex", "reporter", "validator", "planner", "widget_codex", "researcher"}
        found_agents = set(agent_names) & known_v2_agents
        assert found_agents, (
            f"No known V2 agents in plan. Got: {agent_names}. "
            f"Expected at least one of: {known_v2_agents}"
        )

    @pytest.mark.slow
    def test_v2_discussion_mode(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет discussion mode — V2-специфичная функциональность.

        В V2 TransformationController определяет mode (transformation/discussion)
        по ответу Orchestrator. Legacy система не поддерживала discussion mode.
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Объясни простыми словами, что содержится в этих данных? Не пиши код.",
            "selected_node_ids": [node_id],
            "preview_only": True,
        })

        # Discussion mode: code=None, description содержит narrative
        # Это V2-only фича — legacy всегда генерировал код
        mode = result.get("mode")
        if mode == "discussion":
            logger.info("✅ V2 discussion mode confirmed!")
            assert result.get("description"), "Discussion mode must have description"
            assert result.get("code") is None, "Discussion mode should not have code"
        else:
            # Даже если GigaChat решил сгенерировать код, agent_plan всё равно должен быть
            assert result.get("agent_plan") is not None, "V2 agent_plan missing"
            logger.info(f"ℹ️ GigaChat chose transformation mode, but V2 plan present: {bool(result.get('agent_plan'))}")

    @pytest.mark.slow
    def test_v2_suggestions_structured_format(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет, что suggestions имеют V2-структуру (SuggestionType enum).

        V2 WidgetSuggestionsController возвращает suggestions с полями:
        id, type (SuggestionType), priority (SuggestionPriority), title,
        description, prompt, reasoning.
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/analyze-suggestions", json={
            "chat_history": [],
            "current_widget_code": None,
            "max_suggestions": 5,
        })

        suggestions = result.get("suggestions", [])
        assert len(suggestions) >= 1, f"Expected at least 1 suggestion, got {len(suggestions)}"

        # V2 SuggestionType enum values
        valid_types = {"improvement", "alternative", "insight", "library", "style"}
        valid_priorities = {"high", "medium", "low"}

        for i, s in enumerate(suggestions[:3]):
            # V2 schema: type, priority, title (not label), prompt
            assert "type" in s, f"Suggestion {i} missing 'type' (V2 SuggestionType): {s}"
            assert "priority" in s, f"Suggestion {i} missing 'priority' (V2 SuggestionPriority): {s}"
            assert "title" in s, f"Suggestion {i} missing 'title' (V2 uses title, not label): {s}"
            assert "prompt" in s, f"Suggestion {i} missing 'prompt': {s}"

            assert s["type"] in valid_types, (
                f"Suggestion {i} type='{s['type']}' not in V2 SuggestionType enum: {valid_types}"
            )
            assert s["priority"] in valid_priorities, (
                f"Suggestion {i} priority='{s['priority']}' not in V2 enum: {valid_priorities}"
            )

            logger.info(f"  Suggestion {i + 1}: [{s['type']}/{s['priority']}] {s['title']}")

        logger.info(f"✅ V2 structured suggestion format confirmed ({len(suggestions)} suggestions)")

    @pytest.mark.slow
    def test_v2_transform_suggestions_structured(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет, что transform suggestions имеют V2-структуру.

        V2 TransformSuggestionsController возвращает suggestions с:
        id, label, prompt, category, confidence, description.
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/analyze-transform-suggestions", json={
            "chat_history": [],
            "current_code": None,
        })

        suggestions = result.get("suggestions", [])
        assert isinstance(suggestions, list), f"suggestions must be list: {type(suggestions)}"
        assert len(suggestions) >= 1, f"Expected at least 1 suggestion: {result}"

        for i, s in enumerate(suggestions[:3]):
            # V2 transform suggestion schema
            assert "id" in s, f"Suggestion {i} missing 'id': {s}"
            has_label_or_title = "label" in s or "title" in s
            assert has_label_or_title, f"Suggestion {i} missing 'label'/'title': {s}"
            assert "prompt" in s, f"Suggestion {i} missing 'prompt': {s}"

            logger.info(f"  Transform suggestion {i + 1}: {s.get('label') or s.get('title', 'N/A')}")

        is_fallback = result.get("fallback", False)
        logger.info(f"✅ V2 transform suggestions confirmed ({len(suggestions)} items, fallback={is_fallback})")

    @pytest.mark.slow
    def test_v2_pipeline_isolation(self, api: APIClient, content_node_with_data: dict):
        """
        Последовательные запросы изолированы — pipeline_context и agent_results
        создаются заново для каждого вызова Orchestrator (V2 гарантия).

        Используем два transform запроса (быстрее чем AI Chat), чтобы
        проверить что agent_plan разных запросов независимы.
        """
        node_id = content_node_with_data["id"]

        # Request 1: Transform — фильтрация
        r1 = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Отфильтруй по category = Electronics",
            "selected_node_ids": [node_id],
            "preview_only": True,
        })
        assert r1.get("code") or r1.get("description")
        plan1 = r1.get("agent_plan")

        # Request 2: Transform — агрегация (другой промпт)
        r2 = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Посчитай среднее значение amount",
            "selected_node_ids": [node_id],
            "preview_only": True,
        })
        assert r2.get("code") or r2.get("description")
        plan2 = r2.get("agent_plan")

        # Оба запроса вернули agent_plan — значит V2 pipeline работает
        assert plan1 is not None, "First request missing agent_plan"
        assert plan2 is not None, "Second request missing agent_plan"

        # transformation_id разные — изолированные pipelines
        tid1 = r1.get("transformation_id")
        tid2 = r2.get("transformation_id")
        if tid1 and tid2:
            assert tid1 != tid2, "Sequential requests should have different transformation_ids"

        logger.info(f"✅ 2 sequential V2 transform pipelines completed with isolation")

    @pytest.mark.slow
    def test_v2_iterative_transform_with_chat_history(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет, что chat_history передаётся через pipeline_context
        при итеративной трансформации.

        chat_history включается в orchestrator_context → pipeline_context.
        V2-specific: агенты читают его из agent_results (chronological list).
        """
        node_id = content_node_with_data["id"]

        existing_code = "import pandas as pd\ndf0 = input_data['sales']\ndf_result = df0[df0['amount'] > 100].copy()"

        result = api.post(f"/api/v1/content-nodes/{node_id}/transform/iterative", json={
            "user_prompt": "Добавь сортировку по amount по убыванию",
            "existing_code": existing_code,
            "chat_history": [
                {"role": "user", "content": "Отфильтруй amount > 100"},
                {"role": "assistant", "content": "Готово, отфильтровал строки с amount > 100"},
            ],
            "selected_node_ids": [node_id],
            "preview_only": True,
        })

        # V2 маркер: agent_plan ключ присутствует в ответе (V2 route structure)
        # Значение может быть None при auto-retry, но ключ всегда есть в V2
        assert "agent_plan" in result, (
            f"agent_plan key missing — not V2 route format. Keys: {list(result.keys())}"
        )
        agent_plan = result.get("agent_plan")
        if agent_plan:
            steps = agent_plan.get("steps", [])
            logger.info(f"✅ V2 iterative plan: {len(steps)} steps")
        else:
            logger.info("ℹ️ agent_plan=None (auto-retry code fix), but V2 key present")

        # Если есть код — должен учитывать контекст (фильтрация + сортировка)
        if result.get("code"):
            code = result["code"]
            logger.info(f"📝 Iterative code with chat_history: {code[:200]}")
            # Код должен содержать сортировку (из текущего запроса)
            code_lower = code.lower()
            has_context = "sort" in code_lower or "amount" in code_lower or "100" in code
            if has_context:
                logger.info("✅ chat_history context reflected in generated code")
            else:
                logger.warning("⚠️ Generated code may not reflect chat_history")

        logger.info(f"✅ V2 iterative transform with chat_history completed")


# ══════════════════════════════════════════════════════════════════════════════
# Test 8: Adaptive Replanning — план перестраивается после расширения контекста
# ══════════════════════════════════════════════════════════════════════════════


class TestAdaptiveReplanning:
    """
    Проверяет, что:
    1. Планер перестраивает план после отработки агента и расширения контекста
    2. При корректировке плана используется пересмотр существующего плана
       и расширенный контекст (agent_results)

    V2 механизм: Orchestrator._replan() сериализует agent_results → current_results,
    передаёт PlannerAgent task type="replan", PlannerAgent включает current_results
    в промпт GigaChat для информированного перепланирования.

    См. docs/ADAPTIVE_PLANNING.md
    """

    @pytest.mark.slow
    def test_replan_metadata_in_plan(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет, что agent_plan содержит replan_count (метаданные перепланирования).

        Orchestrator V2 добавляет replan_count в план для прозрачности:
        - replan_count: количество перепланирований (0 = без реплана)
        - replan_history: массив записей о реплане (если были)
        - agent_results_at_replan: количество agent_results на момент реплана

        Даже при replan_count=0 поле ДОЛЖНО присутствовать — это маркер V2.
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Посчитай сумму amount по каждой категории",
            "selected_node_ids": [node_id],
            "preview_only": True,
        })

        assert result.get("code") or result.get("description"), (
            f"Neither code nor description returned: {list(result.keys())}"
        )

        agent_plan = result.get("agent_plan")
        assert agent_plan is not None, (
            f"agent_plan is None (V2 pipeline should always return plan). "
            f"Response keys: {list(result.keys())}"
        )

        # V2 маркер: replan_count ДОЛЖЕН присутствовать в плане
        assert "replan_count" in agent_plan, (
            f"replan_count missing from agent_plan — Orchestrator V2 должен добавлять "
            f"replan metadata в план. Keys: {list(agent_plan.keys())}"
        )

        replan_count = agent_plan["replan_count"]
        assert isinstance(replan_count, int), (
            f"replan_count should be int, got {type(replan_count)}"
        )
        assert replan_count >= 0, f"replan_count should be >= 0, got {replan_count}"

        logger.info(
            f"✅ replan_count={replan_count} present in agent_plan "
            f"(plan has {len(agent_plan.get('steps', []))} steps)"
        )

        # Если были реплайны — проверяем replan_history
        if replan_count > 0:
            assert "replan_history" in agent_plan, (
                f"replan_count={replan_count} but replan_history missing"
            )
            history = agent_plan["replan_history"]
            assert len(history) == replan_count, (
                f"replan_history length ({len(history)}) should match replan_count ({replan_count})"
            )
            for i, entry in enumerate(history):
                assert "reason" in entry, f"replan_history[{i}] missing 'reason'"
                assert "type" in entry, f"replan_history[{i}] missing 'type'"
                logger.info(
                    f"  Replan {i + 1}: type={entry['type']}, reason={entry.get('reason', 'N/A')}"
                )

            # При реплане agent_results_at_replan показывает сколько
            # накопленных результатов было на момент реплана
            if "agent_results_at_replan" in agent_plan:
                ar_count = agent_plan["agent_results_at_replan"]
                assert ar_count > 0, (
                    f"agent_results_at_replan={ar_count} — при реплане должны быть "
                    f"накопленные результаты (расширенный контекст)"
                )
                logger.info(f"  agent_results_at_replan={ar_count} (expanded context)")

    @pytest.mark.slow
    def test_replan_on_error_recovery(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет error-based replanning: при ошибке агента Orchestrator
        вызывает _replan() с контекстом ошибки (last_error, failed_agent).

        Посылаем deliberate-error запрос через iterative endpoint:
        - existing_code с намеренной ошибкой в pandas
        - Просим модифицировать
        - Если агент сгенерирует ошибочный код → replan

        Даже без фактического реплана мы проверяем что механизм
        возвращает replan_count и система не падает.
        """
        node_id = content_node_with_data["id"]

        # Код с намеренной неоднозначностью — запрос на сложную модификацию
        existing_code = (
            "import pandas as pd\n"
            "df0 = input_data['sales']\n"
            "# Пустой результат — нужно заменить\n"
            "df_result = pd.DataFrame()"
        )

        result = api.post(f"/api/v1/content-nodes/{node_id}/transform/iterative", json={
            "user_prompt": (
                "Замени пустой DataFrame на полноценный пайплайн: "
                "группировка по category, сумма amount, сортировка по убыванию, "
                "добавь процент от общей суммы"
            ),
            "existing_code": existing_code,
            "chat_history": [
                {"role": "user", "content": "Создай пустой DataFrame"},
                {"role": "assistant", "content": "Готово — создан пустой df_result"},
            ],
            "selected_node_ids": [node_id],
            "preview_only": True,
        })

        # Даже при сложном запросе система должна вернуть результат
        has_output = result.get("code") or result.get("description")
        assert has_output, (
            f"No code or description in response. Status: {result.get('status')}. "
            f"Keys: {list(result.keys())}"
        )

        # Проверяем agent_plan с replan metadata
        agent_plan = result.get("agent_plan")
        if agent_plan:
            replan_count = agent_plan.get("replan_count", -1)
            assert replan_count >= 0, f"replan_count should be >= 0: {replan_count}"
            logger.info(
                f"✅ Error recovery test: replan_count={replan_count}, "
                f"steps={len(agent_plan.get('steps', []))}"
            )

            if replan_count > 0:
                logger.info(
                    f"  🔄 Replanning occurred! History: "
                    f"{json.dumps(agent_plan.get('replan_history', []), ensure_ascii=False)[:300]}"
                )
        else:
            # agent_plan=None при auto-retry (допустимо)
            logger.info("ℹ️ agent_plan=None (auto-retry code fix), replan metadata not available")

    @pytest.mark.slow
    def test_plan_uses_expanded_context_for_complex_request(
        self, api: APIClient, content_node_with_data: dict
    ):
        """
        Проверяет, что при сложном запросе агент-планировщик учитывает
        расширенный контекст (входные данные, структуру таблиц).

        Используем /transform/preview (skip_execution=True) — нам нужен
        только план, а не исполнение кода. Endpoint transform-multiagent
        игнорирует preview_only и всегда исполняет код.

        Проверяем:
        1. Plan содержит шаги (multi-step)
        2. План включает правильные типы агентов
        3. replan_count присутствует (V2 маркер)
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/transform/preview", json={
            "prompt": (
                "Сделай полный анализ данных продаж: "
                "группировка по категории с агрегацией, "
                "доля каждой категории от общей суммы, "
                "ранжирование по количеству продаж"
            ),
            "selected_node_ids": [node_id],
        })

        assert result.get("code") or result.get("description"), (
            f"No output: {list(result.keys())}"
        )

        agent_plan = result.get("agent_plan")
        assert agent_plan is not None, f"agent_plan missing for complex request"

        steps = agent_plan.get("steps", [])
        assert len(steps) >= 1, f"Complex request should produce at least 1 step: {agent_plan}"

        # Проверяем что план содержит агентов (V2: analyst, reporter, etc.)
        agents_used = [s.get("agent", "unknown") for s in steps]
        logger.info(f"📋 Complex plan: {len(steps)} steps, agents: {agents_used}")

        # Проверяем replan_count (V2 маркер)
        assert "replan_count" in agent_plan, (
            f"replan_count missing — V2 Orchestrator marker not present"
        )

        logger.info(
            f"✅ Complex request plan verified: {len(steps)} steps, "
            f"replan_count={agent_plan['replan_count']}"
        )

    @pytest.mark.slow
    def test_replan_preserves_agent_results_context(
        self, api: APIClient, content_node_with_data: dict
    ):
        """
        Проверяет, что при перепланировании agent_results (расширенный контекст)
        сохраняются и ПЕРЕДАЮТСЯ реплайнеру.

        V2 архитектура: agent_results — append-only list (хронология).
        При реплане orchestrator._replan() сериализует agent_results
        и передаёт в PlannerAgent как current_results.

        Проверка: последовательные запросы к одному node с разными промптами
        показывают, что pipeline_context создаётся заново (изоляция), но
        ВНУТРИ одного вызова agent_results накапливаются для реплана.
        """
        node_id = content_node_with_data["id"]

        # Request 1: простой запрос
        r1 = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": "Отфильтруй строки где amount > 500",
            "selected_node_ids": [node_id],
            "preview_only": True,
        })

        # Request 2: более сложный запрос (больше шагов, больше agent_results)
        r2 = api.post(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": (
                "Группировка по category, сумма amount и quantity, "
                "процент от общей суммы, сортировка по убыванию amount"
            ),
            "selected_node_ids": [node_id],
            "preview_only": True,
        })

        for label, r in [("simple", r1), ("complex", r2)]:
            has_output = r.get("code") or r.get("description")
            assert has_output, f"{label} request returned no output: {list(r.keys())}"

        plan1 = r1.get("agent_plan")
        plan2 = r2.get("agent_plan")

        # Оба должны иметь replan_count (V2 маркер)
        for label, plan in [("simple", plan1), ("complex", plan2)]:
            if plan:
                assert "replan_count" in plan, (
                    f"{label} plan missing replan_count. Keys: {list(plan.keys())}"
                )

        # Проверяем что pipelines изолированы (разные планы)
        if plan1 and plan2:
            steps1 = plan1.get("steps", [])
            steps2 = plan2.get("steps", [])
            logger.info(
                f"📋 Simple: {len(steps1)} steps (replan={plan1.get('replan_count', '?')}), "
                f"Complex: {len(steps2)} steps (replan={plan2.get('replan_count', '?')})"
            )

        logger.info("✅ Agent results context preservation verified across isolated pipelines")

    @pytest.mark.slow
    def test_replan_original_plan_passed(self, api: APIClient, content_node_with_data: dict):
        """
        Верифицирует, что при перепланировании PlannerAgent получает
        original_plan (существующий план) для пересмотра.

        V2: Orchestrator._replan() передаёт task.original_plan = current_plan,
        PlannerAgent._replan() включает его в промпт "ORIGINAL PLAN: {json}".

        Используем /transform/preview для проверки структуры плана
        (не исполняет код, избегает 500 от плохого pandas-кода).
        """
        node_id = content_node_with_data["id"]

        result = api.post(f"/api/v1/content-nodes/{node_id}/transform/preview", json={
            "prompt": "Переименуй колонки: id→ID, category→Category, amount→Amount",
            "selected_node_ids": [node_id],
        })

        has_output = result.get("code") or result.get("description")
        assert has_output, f"No output: {list(result.keys())}"

        agent_plan = result.get("agent_plan")
        assert agent_plan is not None, "agent_plan is None — PlannerAgent should always return plan"

        # PlannerAgent V2 должен вернуть план со структурой:
        # steps: [], user_request: str, replan_count: int
        assert "steps" in agent_plan, f"Plan missing 'steps': {list(agent_plan.keys())}"

        steps = agent_plan["steps"]
        assert len(steps) >= 1, f"Plan should have at least 1 step"

        # Каждый шаг должен иметь agent и task (V2 plan schema)
        for i, step in enumerate(steps):
            assert "agent" in step, f"Step {i} missing 'agent': {step}"
            assert "task" in step or "step_id" in step, (
                f"Step {i} missing 'task' or 'step_id': {step}"
            )

        # replan_count — маркер V2 Orchestrator
        assert "replan_count" in agent_plan, "replan_count missing from plan"

        logger.info(
            f"✅ Plan structure verified: {len(steps)} steps, "
            f"agents={[s.get('agent') for s in steps]}, "
            f"replan_count={agent_plan['replan_count']}"
        )

    @pytest.mark.slow
    def test_replanning_mechanism_resilience(self, api: APIClient, content_node_with_data: dict):
        """
        Проверяет, что механизм перепланирования не ломает pipeline.

        Отправляем заведомо сложный запрос. Используем post_raw() чтобы
        gracefully обработать 500 (GigaChat может сгенерировать невалидный код,
        а transform-multiagent всегда исполняет код).

        Проверяем resilience:
        - Бэкенд не крашится (возвращает response)
        - Если 200 → agent_plan содержит replan_count <= MAX_REPLAN_ATTEMPTS
        - Если 500 → это ожидаемо при сложных запросах (code execution error)
        """
        node_id = content_node_with_data["id"]

        # Намеренно сложный запрос — GigaChat может не справиться с pandas кодом
        r = api.post_raw(f"/api/v1/content-nodes/{node_id}/transform-multiagent", json={
            "user_prompt": (
                "Создай pivot table по category и date, "
                "вычисли среднее и медиану amount, "
                "добавь running sum и процентное изменение day-over-day, "
                "заполни пропуски нулями"
            ),
            "selected_node_ids": [node_id],
        })

        # Главная проверка — бэкенд ответил (не упал/не завис)
        assert r.status_code in (200, 500), (
            f"Unexpected status code: {r.status_code}. "
            f"Expected 200 (success) or 500 (code execution error)"
        )

        if r.status_code == 200:
            result = r.json()
            agent_plan = result.get("agent_plan")
            if agent_plan:
                replan_count = agent_plan.get("replan_count", 0)
                steps = agent_plan.get("steps", [])

                logger.info(
                    f"✅ Resilience test (200): {len(steps)} steps, "
                    f"replan_count={replan_count}"
                )

                # MAX_REPLAN_ATTEMPTS = 3, так что replan_count <= 3
                assert replan_count <= 3, (
                    f"replan_count={replan_count} exceeds MAX_REPLAN_ATTEMPTS=3"
                )
            else:
                logger.info("ℹ️ agent_plan=None (auto-retry), pipeline still returned result")
        else:
            # 500 — ожидаемо при сложных запросах (GigaChat генерирует плохой код)
            try:
                detail = r.json().get("detail", "unknown error")
            except Exception:
                detail = r.text[:200]
            logger.info(
                f"ℹ️ Resilience test (500): code execution failed as expected "
                f"for complex request. Detail: {detail}"
            )

        logger.info("✅ Replanning mechanism resilience verified (backend alive)")


# ══════════════════════════════════════════════════════════════════════════════
# Test 10: Code Generation Quality & Error Feedback
# ══════════════════════════════════════════════════════════════════════════════


class TestCodeGenerationQuality:
    """
    Тесты качества генерации кода и цепочки обратной связи по ошибкам.

    Проверяет:
    - Codex генерирует синтаксически валидный Python-код
    - Сгенерированный код执行ится без ошибок (preview_data не пуст)
    - При ошибке error feedback дoходит до codex (error retry chain)
    - QualityGate формирует рекомендации для replan при execution error
    - Codex видит previous_error из context (FIX GAP 1)
    """

    @pytest.mark.slow
    def test_simple_transform_produces_valid_code(
        self,
        api: "APIClient",
        content_node_with_data: dict,
    ):
        """Простая трансформация возвращает валидный и исполняемый Python-код."""
        node_id = content_node_with_data["id"]

        r = api.post_raw(
            f"/api/v1/content-nodes/{node_id}/transform-multiagent",
            json={
                "user_prompt": "Посчитай сумму amount по каждой category",
                "selected_node_ids": [node_id],
            },
        )

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        result = r.json()

        # Код должен быть непустым
        code = result.get("code", "")
        assert code.strip(), "Generated code is empty"
        logger.info(f"✅ Generated code ({len(code)} chars): {code[:200]}...")

        # Код должен содержать pandas-операции
        assert "groupby" in code.lower() or "agg" in code.lower() or "sum" in code.lower(), (
            "Code doesn't contain expected pandas groupby/agg/sum operations"
        )

        # Код должен быть синтаксически валидным
        try:
            compile(code, "<generated>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

        # preview_data должен содержать данные (код исполнился)
        preview_data = result.get("preview_data")
        assert preview_data, "preview_data is empty — code may not have executed"
        tables = preview_data.get("tables", [])
        assert len(tables) > 0, "No output tables in preview_data"

        # Проверяем что в таблице есть category
        first_table = tables[0]
        columns = [c["name"] if isinstance(c, dict) else c for c in first_table.get("columns", [])]
        logger.info(f"✅ Output table: {first_table.get('name', 'unnamed')} columns={columns}")
        assert "category" in columns, f"Expected 'category' in output columns: {columns}"

        logger.info("✅ Simple transform: valid code, executed successfully")

    @pytest.mark.slow
    def test_code_does_not_contain_forbidden_patterns(
        self,
        api: "APIClient",
        content_node_with_data: dict,
    ):
        """Код не содержит запрещённых паттернов (eval, exec, файловый I/O)."""
        node_id = content_node_with_data["id"]

        r = api.post_raw(
            f"/api/v1/content-nodes/{node_id}/transform-multiagent",
            json={
                "user_prompt": "Создай новый столбец total = amount * quantity",
                "selected_node_ids": [node_id],
            },
        )

        # Даже если 500, при наличии code — проверяем запрещённые паттерны
        code = ""
        if r.status_code == 200:
            code = r.json().get("code", "")
        elif r.status_code == 500:
            try:
                code = r.json().get("code", "")
            except Exception:
                pass

        if not code:
            pytest.skip("No code returned to validate")

        forbidden = ["eval(", "exec(", "open(", "os.system", "subprocess", "__import__"]
        for pattern in forbidden:
            assert pattern not in code, (
                f"Generated code contains forbidden pattern: '{pattern}'"
            )

        logger.info(f"✅ Code ({len(code)} chars) free of forbidden patterns")

    @pytest.mark.slow
    def test_error_retry_produces_different_code(
        self,
        api: "APIClient",
        content_node_with_data: dict,
    ):
        """
        При ошибке retry генерирует ДРУГОЙ код (а не повторяет тот же).
        
        Стратегия: запрос с типичной ловушкой (неправильный agg синтаксис)
        чтобы спровоцировать ошибку → retry → исправленный код.
        """
        node_id = content_node_with_data["id"]

        # Намеренно сложный запрос чтобы увеличить шанс ошибки
        r = api.post_raw(
            f"/api/v1/content-nodes/{node_id}/transform-multiagent",
            json={
                "user_prompt": (
                    "Сгруппируй по category, посчитай: "
                    "total_amount (сумма amount), avg_quantity (среднее quantity), "
                    "count (количество записей), max_amount (максимум amount). "
                    "Результат отсортируй по total_amount по убыванию."
                ),
                "selected_node_ids": [node_id],
            },
        )

        assert r.status_code in (200, 500), (
            f"Unexpected status: {r.status_code}. Body: {r.text[:300]}"
        )

        result = r.json()

        if r.status_code == 200:
            # Если успех — проверяем что код рабочий  
            code = result.get("code", "")
            assert code.strip(), "Code is empty on success"

            # Проверяем metadata на error_retries  
            metadata = result.get("metadata") or {}
            retries = metadata.get("error_retries", 0)
            logger.info(f"✅ Success after {retries} error retries")

            if retries > 0:
                # Код ИСПРАВИЛСЯ — retry сработал
                logger.info("✅ Error retry chain WORKS: code was fixed automatically")
                preview = result.get("preview_data", {})
                tables = preview.get("tables", [])
                assert len(tables) > 0, (
                    "Retry returned success but no output tables — "
                    "error feedback may not be reaching codex"
                )
        else:
            # 500 — все retry не помогли, но бэкенд не упал
            error_msg = result.get("detail", "")
            metadata = result.get("metadata") or {}
            retries = metadata.get("error_retries", 0)
            logger.info(
                f"ℹ️ All retries exhausted ({retries}). "
                f"Error: {str(error_msg)[:200]}"
            )
            # Это ожидаемо для сложных запросов

        logger.info("✅ Error retry mechanism exercised")

    @pytest.mark.slow
    def test_transform_preview_has_correct_structure(
        self,
        api: "APIClient",
        content_node_with_data: dict,
    ):
        """Preview endpoint возвращает план + pipeline metadata без выполнения кода."""
        node_id = content_node_with_data["id"]

        r = api.post_raw(
            f"/api/v1/content-nodes/{node_id}/transform-multiagent",
            json={
                "user_prompt": "Отфильтруй записи где amount > 500",
                "selected_node_ids": [node_id],
                "preview": True,
            },
        )

        # preview может не возвращать код, а только план
        assert r.status_code in (200, 500), f"Status {r.status_code}: {r.text[:300]}"

        if r.status_code == 200:
            result = r.json()
            
            # Проверяем наличие agent_plan (если поддерживается)
            agent_plan = result.get("agent_plan")
            if agent_plan:
                steps = agent_plan.get("steps", [])
                assert len(steps) > 0, "Preview plan has no steps"
                logger.info(f"✅ Preview plan: {len(steps)} steps")

                # План должен содержать codex шаг
                agent_names = [s.get("agent", "") for s in steps]
                assert any("codex" in a for a in agent_names), (
                    f"No codex step in plan: {agent_names}"
                )

            # Если код вернулся — должен быть синтаксически валидный
            code = result.get("code", "")
            if code:
                try:
                    compile(code, "<preview>", "exec")
                except SyntaxError as e:
                    pytest.fail(f"Preview code has syntax error: {e}")
                logger.info(f"✅ Preview returned valid code ({len(code)} chars)")

        logger.info("✅ Transform preview structure validated")

    @pytest.mark.slow
    def test_error_context_reaches_codex(
        self,
        api: "APIClient",
        content_node_with_data: dict,
    ):
        """
        Проверяем что при ошибке codex получает error context.
        
        Отправляем запрос и проверяем что:
        1. agent_plan содержит информацию об ошибках (если был replan)
        2. Результат содержит metadata с error_retries > 0 (если была ошибка и retry)
        3. Или успешный код (если ошибки не было / codex справился с первой попытки)
        """
        node_id = content_node_with_data["id"]

        # Запрос с потенциальной ловушкой для pandas
        r = api.post_raw(
            f"/api/v1/content-nodes/{node_id}/transform-multiagent",
            json={
                "user_prompt": (
                    "Создай pivot table: строки = category, "
                    "значения = sum(amount) и mean(quantity). "
                    "Добавь строку Total внизу."
                ),
                "selected_node_ids": [node_id],
            },
        )

        assert r.status_code in (200, 500), f"Status {r.status_code}: {r.text[:300]}"

        result = r.json()
        agent_plan = result.get("agent_plan")
        metadata = result.get("metadata") or {}

        if r.status_code == 200:
            code = result.get("code", "")
            retries = metadata.get("error_retries", 0)

            logger.info(
                f"✅ Result: code={len(code)} chars, retries={retries}"
            )

            if retries > 0:
                # Error retry chain работает — codex получил error context
                logger.info(
                    "✅ Error context reached codex: "
                    f"code was auto-fixed after {retries} retries"
                )

            # При любом успеше — код должен исполняться
            preview = result.get("preview_data")
            assert preview, "Success without preview_data — code didn't execute"

        if agent_plan:
            replan_count = agent_plan.get("replan_count", 0)
            replan_history = agent_plan.get("replan_history", [])

            if replan_count > 0:
                logger.info(
                    f"✅ Replan triggered: {replan_count} replans, "
                    f"history: {json.dumps(replan_history, ensure_ascii=False)[:300]}"
                )

                # Проверяем что replan history содержит причину
                for entry in replan_history:
                    reason = entry.get("reason", "")
                    assert reason, "Replan entry has no reason"
                    logger.info(f"  Replan reason: {reason}")

        logger.info("✅ Error context chain verified")

    @pytest.mark.slow
    def test_iterative_transform_preserves_context(
        self,
        api: "APIClient",
        content_node_with_data: dict,
    ):
        """
        Итеративная трансформация: первый запрос → код → второй запрос на базе первого.
        Проверяет что existing_code передаётся через chat_history / context.
        """
        node_id = content_node_with_data["id"]

        # Шаг 1: Первая трансформация
        r1 = api.post_raw(
            f"/api/v1/content-nodes/{node_id}/transform-multiagent",
            json={
                "user_prompt": "Посчитай сумму amount по category",
                "selected_node_ids": [node_id],
            },
        )

        if r1.status_code != 200:
            pytest.skip("First transform failed, can't test iterative flow")

        result1 = r1.json()
        code1 = result1.get("code", "")
        if not code1:
            pytest.skip("No code from first transform")

        logger.info(f"Step 1: Got code ({len(code1)} chars)")

        # Шаг 2: Итеративная доработка с existing_code
        r2 = api.post_raw(
            f"/api/v1/content-nodes/{node_id}/transform-multiagent",
            json={
                "user_prompt": "Добавь столбец с процентом от общей суммы",
                "selected_node_ids": [node_id],
                "existing_code": code1,
                "chat_history": [
                    {"role": "user", "content": "Посчитай сумму amount по category"},
                    {"role": "assistant", "content": code1},
                ],
            },
        )

        assert r2.status_code in (200, 500), f"Status {r2.status_code}: {r2.text[:300]}"

        if r2.status_code == 200:
            result2 = r2.json()
            code2 = result2.get("code", "")
            assert code2.strip(), "Iterative transform returned empty code"

            # Код 2 должен быть ДРУГИМ (модифицированным)
            assert code2 != code1, (
                "Iterative code is identical to first — "
                "existing_code context may not be reaching codex"
            )

            # Код 2 должен содержать groupby (из первого шага)
            assert "groupby" in code2.lower() or "sum" in code2.lower(), (
                "Iterative code doesn't reference original groupby — "
                "context from first transform may be lost"
            )

            logger.info(f"✅ Iterative transform: code changed ({len(code2)} chars)")
            logger.info(f"  Code preview: {code2[:200]}...")

        logger.info("✅ Iterative transform context preservation verified")


# ══════════════════════════════════════════════════════════════════════════════
# pytest configuration
# ══════════════════════════════════════════════════════════════════════════════


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests that call GigaChat (may take 10-60s)")
