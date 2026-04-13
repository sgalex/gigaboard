"""
Live-тест TransformCodex (Orchestrator → TransformCodexAgent):

  POST /api/v1/content-nodes/{id}/transform/preview
  POST /api/v1/content-nodes/{id}/transform-multiagent

Использование:
  uv run python tests/backend/runtime_transform_codex_check.py
  uv run python tests/backend/runtime_transform_codex_check.py --timeout 600

Требуется запущенный backend на http://127.0.0.1:8000 (см. run-backend.ps1).
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime

from runtime_context_single_check import (
    bootstrap_user_project_board,
    find_trace,
    print_trace_summary,
    req,
)


def _sales_content_payload(board_id: str) -> dict:
    tid = str(uuid.uuid4())
    return {
        "board_id": board_id,
        "content": {
            "text": "Данные о продажах по регионам за 2025 год",
            "tables": [
                {
                    "id": tid,
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
                        {
                            "region": "Москва",
                            "q1_sales": 1500,
                            "q2_sales": 1800,
                            "q3_sales": 1200,
                            "q4_sales": 2100,
                            "total": 6600,
                        },
                        {
                            "region": "Санкт-Петербург",
                            "q1_sales": 900,
                            "q2_sales": 1100,
                            "q3_sales": 800,
                            "q4_sales": 1300,
                            "total": 4100,
                        },
                        {
                            "region": "Новосибирск",
                            "q1_sales": 400,
                            "q2_sales": 500,
                            "q3_sales": 350,
                            "q4_sales": 600,
                            "total": 1850,
                        },
                    ],
                    "row_count": 3,
                    "column_count": 6,
                    "preview_row_count": 3,
                }
            ],
        },
        "lineage": {
            "operation": "manual",
            "source_node_id": None,
            "transformation_id": None,
            "parent_content_ids": [],
            "timestamp": datetime.now().isoformat(),
            "agent": None,
        },
        "metadata": {"name": "Runtime TransformCodex sales"},
        "position": {"x": 100, "y": 100},
    }


def _create_content_node(token: str, board_id: str) -> str:
    status, body = req(
        "POST",
        "/api/v1/content-nodes/",
        _sales_content_payload(board_id),
        token,
    )
    if status not in (200, 201):
        raise RuntimeError(f"content-nodes create failed: {status} {body}")
    return body["id"]


def _session_id_from_plan(body: dict) -> str | None:
    plan = body.get("agent_plan")
    if not isinstance(plan, dict):
        return None
    for key in ("session_id", "orchestrator_session_id"):
        sid = plan.get(key)
        if isinstance(sid, str) and sid:
            return sid
    meta = plan.get("metadata")
    if isinstance(meta, dict):
        sid = meta.get("session_id")
        if isinstance(sid, str) and sid:
            return sid
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="TransformCodex live check")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    token, board_id, email = bootstrap_user_project_board()
    content_id = _create_content_node(token, board_id)

    print("ENDPOINT_BASE", "/api/v1/content-nodes/{id}/transform*")
    print("USER_EMAIL", email)
    print("BOARD_ID", board_id)
    print("CONTENT_ID", content_id)
    print()

    # 1) preview (код без multiagent V2 полного пайплайна — см. роут preview)
    st1, b1 = req(
        "POST",
        f"/api/v1/content-nodes/{content_id}/transform/preview",
        {"prompt": "Отфильтруй строки, где total больше 2000"},
        token,
        timeout=args.timeout,
    )
    print("=== 1) transform/preview ===")
    print("HTTP_STATUS", st1)
    if isinstance(b1, dict):
        code = b1.get("code") or ""
        print("CODE_CHARS", len(code))
        if code:
            print("CODE_PREVIEW", code[:600].replace("\n", " "))
        print("PREVIEW_KEYS", sorted(b1.keys()))
    else:
        print("BODY", b1)
    print()

    # 2) transform-multiagent (TransformCodex через TransformationController)
    st2, b2 = req(
        "POST",
        f"/api/v1/content-nodes/{content_id}/transform-multiagent",
        {
            "user_prompt": (
                "Добавь столбец growth_rate = (q4_sales - q1_sales) / q1_sales * 100, "
                "округли до одного знака после запятой."
            ),
            "preview_only": True,
        },
        token,
        timeout=args.timeout,
    )
    print("=== 2) transform-multiagent (preview_only) ===")
    print("HTTP_STATUS", st2)
    if isinstance(b2, dict):
        print("MODE", b2.get("mode"))
        print("DESCRIPTION_CHARS", len(b2.get("description") or ""))
        code2 = b2.get("code") or ""
        print("CODE_CHARS", len(code2))
        if code2:
            print("CODE_PREVIEW", code2[:800].replace("\n", " "))
        print("RESPONSE_KEYS", sorted(b2.keys()))
        sid = _session_id_from_plan(b2)
        print("SESSION_ID_FROM_PLAN", sid)
        if sid:
            trace = find_trace(sid)
            print_trace_summary(trace)
    else:
        print("BODY", b2)


if __name__ == "__main__":
    main()
