"""
Live-тест WidgetCodex (Orchestrator → WidgetCodexAgent):

  POST /api/v1/content-nodes/{id}/visualize-multiagent

Использование:
  uv run python tests/backend/runtime_widget_codex_check.py
  uv run python tests/backend/runtime_widget_codex_check.py --timeout 600

Требуется запущенный backend на http://127.0.0.1:8000.

Тот же тестовый ContentNode, что и в runtime_transform_codex_check (импорт фабрики ноды).
"""
from __future__ import annotations

import argparse
import sys

from runtime_context_single_check import bootstrap_user_project_board, find_trace, print_trace_summary, req
from runtime_transform_codex_check import _create_content_node


def main() -> None:
    parser = argparse.ArgumentParser(description="WidgetCodex live check (visualize-multiagent)")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    token, board_id, email = bootstrap_user_project_board()
    content_id = _create_content_node(token, board_id)

    print("ENDPOINT", "/api/v1/content-nodes/{id}/visualize-multiagent")
    print("USER_EMAIL", email)
    print("BOARD_ID", board_id)
    print("CONTENT_ID", content_id)
    print()

    st, body = req(
        "POST",
        f"/api/v1/content-nodes/{content_id}/visualize-multiagent",
        {
            "user_prompt": (
                "Построй гистограмму total продаж по регионам по таблице sales_2025. "
                "Используй Chart.js, подписи осей на русском."
            ),
        },
        token,
        timeout=args.timeout,
    )

    print("HTTP_STATUS", st)
    if not isinstance(body, dict):
        print("BODY", body)
        return

    wc = body.get("widget_code") or ""
    hc = body.get("html_code") or ""
    print("STATUS_FIELD", body.get("status"))
    print("WIDGET_NAME", body.get("widget_name"))
    print("WIDGET_TYPE", body.get("widget_type"))
    print("DESCRIPTION", (body.get("description") or "")[:400])
    print("WIDGET_CODE_CHARS", len(wc))
    print("HTML_CODE_CHARS", len(hc))
    primary = wc or hc
    if primary:
        prev = primary[:900].replace("\n", " ")
        print("CODE_PREVIEW", prev)
    else:
        print("CODE_PREVIEW (empty)")

    # Оркестратор пишет трейс по session_id внутри плана — HTTP ответ его не отдаёт;
    # ищем последнюю запись с controller widget / transformation в логе при необходимости вручную.
    sid = body.get("session_id")
    if isinstance(sid, str) and sid:
        print("SESSION_ID", sid)
        trace = find_trace(sid)
        print_trace_summary(trace)


if __name__ == "__main__":
    main()
