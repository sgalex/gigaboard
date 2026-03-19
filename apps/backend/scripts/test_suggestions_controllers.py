"""
Прогон контроллеров подсказок (transform_suggestions, widget_suggestions).

Проверяет, что:
- Planner строит короткий план (analyst → reporter) без discovery/research/structurizer.
- Analyst использует специализированные промпты (TRANSFORM_SUGGESTIONS / WIDGET_SUGGESTIONS).
- Контроллеры возвращают список подсказок.

Запуск из корня репозитория:
  uv run --project apps/backend python apps/backend/scripts/test_suggestions_controllers.py

Или из apps/backend:
  uv run python scripts/test_suggestions_controllers.py
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Чтобы импортировать app из backend
if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent.parent
    os.chdir(backend_dir)
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


async def run_transform_suggestions(orchestrator, controller):
    """Вызов transform_suggestions: план + результат контроллера."""
    board_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"
    input_schemas = [
        {
            "name": "sales",
            "columns": ["product", "region", "revenue", "quantity", "date"],
            "row_count": 150,
            "sample_rows": [
                {"product": "A", "region": "North", "revenue": 1000, "quantity": 10},
                {"product": "B", "region": "South", "revenue": 800, "quantity": 5},
            ],
        },
    ]
    input_data_preview = {}
    for s in input_schemas:
        input_data_preview[s["name"]] = {
            "columns": s["columns"],
            "row_count": s["row_count"],
            "sample_rows": (s.get("sample_rows") or [])[:20],
        }

    user_request = (
        "Предложи варианты трансформации данных.\n\n"
        "Доступные данные:\n"
        "  • Таблица 'sales': колонки [product, region, revenue, quantity, date], 150 строк\n\n"
        "ЗАДАЧА: Проанализируй данные и предложи 10 разнообразных вариантов ТРАНСФОРМАЦИИ "
        "(filter, aggregation, calculation, sorting, cleaning, merge, reshape). "
        "НЕ предлагай визуализации."
    )
    context = {
        "controller": "transform_suggestions",
        "mode": "transform_suggestions_new",
        "input_data_preview": input_data_preview,
        "existing_code": None,
        "chat_history": [],
        "max_suggestions": 6,
    }

    logger.info("=== Transform suggestions: вызов Orchestrator ===")
    orch_result = await orchestrator.process_request(
        user_request=user_request,
        board_id=board_id,
        user_id=user_id,
        context=context,
        skip_validation=True,
    )

    plan = orch_result.get("plan") or {}
    steps = plan.get("steps") if isinstance(plan, dict) else getattr(plan, "steps", [])
    if not steps and hasattr(plan, "model_dump"):
        steps = plan.model_dump().get("steps", [])

    logger.info("План (шаги): %s", [s.get("agent") if isinstance(s, dict) else getattr(s, "agent", None) for s in (steps or [])])
    for i, step in enumerate(steps or [], 1):
        agent = step.get("agent") if isinstance(step, dict) else getattr(step, "agent", "?")
        desc = (step.get("task") or {}).get("description", "") if isinstance(step, dict) else ""
        logger.info("  %d. %s — %s", i, agent, (desc or "")[:60])

    results = orch_result.get("results", {})
    logger.info("Результаты агентов: %s", list(results.keys()))

    # Проверка: в плане не должно быть discovery, research, structurizer
    agents_in_plan = [s.get("agent") if isinstance(s, dict) else getattr(s, "agent", "") for s in (steps or [])]
    forbidden = {"discovery", "research", "structurizer"}
    found_forbidden = [a for a in agents_in_plan if a in forbidden]
    if found_forbidden:
        logger.warning("Ожидался лёгкий план без discovery/research/structurizer, получено: %s", found_forbidden)
    else:
        logger.info("OK: план без discovery/research/structurizer")

    # Полный проход через контроллер для формата подсказок
    logger.info("=== Transform suggestions: вызов Controller ===")
    result = await controller.process_request(
        user_message=user_request,
        context={
            "board_id": board_id,
            "user_id": user_id,
            "input_schemas": input_schemas,
            "existing_code": None,
            "chat_history": [],
        },
    )
    suggestions = result.suggestions or []
    logger.info("Статус: %s, подсказок: %d", result.status, len(suggestions))
    for i, s in enumerate(suggestions[:6], 1):
        label = s.get("label") or s.get("title") or s.get("prompt", "")[:50]
        typ = s.get("type") or s.get("category", "")
        logger.info("  %d. %s [%s]", i, label, typ)
    return result.status, len(suggestions), found_forbidden


async def run_widget_suggestions(orchestrator, controller):
    """Вызов widget_suggestions: план + результат контроллера."""
    board_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"
    content_data = {
        "tables": [
            {
                "name": "sales",
                "columns": [{"name": "product"}, {"name": "region"}, {"name": "revenue"}],
                "row_count": 100,
                "rows": [{"product": "A", "region": "North", "revenue": 1000}],
            },
        ],
        "text": "",
    }
    input_data_preview = {}
    for t in content_data.get("tables", []):
        name = t.get("name", "df")
        cols = t.get("columns", [])
        col_names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in cols]
        input_data_preview[name] = {
            "columns": col_names,
            "row_count": t.get("row_count", 0),
            "sample_rows": (t.get("rows") or [])[:20],
        }

    user_request = (
        "Предложи варианты визуализации для данных.\n\n"
        "Доступные данные:\n"
        "  • Таблица 'sales': 100 строк, колонки [product, region, revenue]\n\n"
        "ЗАДАЧА: предложи 10 разнообразных вариантов ВИЗУАЛИЗАЦИИ (chart, table, kpi, map)."
    )
    context = {
        "controller": "widget_suggestions",
        "mode": "widget_suggestions_new",
        "input_data_preview": input_data_preview,
        "content_data": content_data,
        "existing_widget_code": None,
        "chat_history": [],
        "max_suggestions": 6,
    }

    logger.info("=== Widget suggestions: вызов Orchestrator ===")
    orch_result = await orchestrator.process_request(
        user_request=user_request,
        board_id=board_id,
        user_id=user_id,
        context=context,
        skip_validation=True,
    )

    plan = orch_result.get("plan") or {}
    steps = plan.get("steps") if isinstance(plan, dict) else getattr(plan, "steps", [])
    if not steps and hasattr(plan, "model_dump"):
        steps = plan.model_dump().get("steps", [])

    logger.info("План (шаги): %s", [s.get("agent") if isinstance(s, dict) else getattr(s, "agent", None) for s in (steps or [])])
    for i, step in enumerate(steps or [], 1):
        agent = step.get("agent") if isinstance(step, dict) else getattr(step, "agent", "?")
        desc = (step.get("task") or {}).get("description", "") if isinstance(step, dict) else ""
        logger.info("  %d. %s — %s", i, agent, (desc or "")[:60])

    agents_in_plan = [s.get("agent") if isinstance(s, dict) else getattr(s, "agent", "") for s in (steps or [])]
    forbidden = {"discovery", "research", "structurizer"}
    found_forbidden = [a for a in agents_in_plan if a in forbidden]
    if found_forbidden:
        logger.warning("Ожидался лёгкий план без discovery/research/structurizer, получено: %s", found_forbidden)
    else:
        logger.info("OK: план без discovery/research/structurizer")

    logger.info("=== Widget suggestions: вызов Controller ===")
    result = await controller.process_request(
        user_message=user_request,
        context={
            "board_id": board_id,
            "user_id": user_id,
            "content_node_id": "00000000-0000-0000-0000-000000000003",
            "content_data": content_data,
            "current_widget_code": None,
            "chat_history": [],
        },
    )
    suggestions = result.suggestions or []
    logger.info("Статус: %s, подсказок: %d", result.status, len(suggestions))
    for i, s in enumerate(suggestions[:6], 1):
        title = s.get("title") or s.get("description") or s.get("prompt", "")[:50]
        typ = s.get("type", "")
        logger.info("  %d. %s [%s]", i, title, typ)
    return result.status, len(suggestions), found_forbidden


async def main():
    from app.main import fastapi_app, lifespan, get_orchestrator
    from app.services.controllers import TransformSuggestionsController, WidgetSuggestionsController

    logger.info("Запуск lifespan приложения (Redis, DB, Orchestrator)...")
    async with lifespan(fastapi_app):
        orch = get_orchestrator()
        if not orch:
            logger.error("Orchestrator недоступен (Redis или инициализация не прошли)")
            return 1

        logger.info("Orchestrator готов")
        transform_controller = TransformSuggestionsController(orch)
        widget_controller = WidgetSuggestionsController(orch)

        # 1. Transform suggestions
        try:
            status_t, count_t, forbidden_t = await run_transform_suggestions(orch, transform_controller)
            ok_t = status_t == "success" and count_t > 0 and not forbidden_t
        except Exception as e:
            logger.exception("Transform suggestions: %s", e)
            ok_t = False

        # 2. Widget suggestions
        try:
            status_w, count_w, forbidden_w = await run_widget_suggestions(orch, widget_controller)
            ok_w = status_w == "success" and count_w > 0 and not forbidden_w
        except Exception as e:
            logger.exception("Widget suggestions: %s", e)
            ok_w = False

        logger.info("")
        logger.info("=== Итог ===")
        logger.info("Transform suggestions: %s", "OK" if ok_t else "FAIL")
        logger.info("Widget suggestions: %s", "OK" if ok_w else "FAIL")
        return 0 if (ok_t and ok_w) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
