"""
Live-тест Deep Research: POST /api/v1/research/chat → Orchestrator (research pipeline).

Использование:
  uv run python tests/backend/runtime_deep_research_check.py
  uv run python tests/backend/runtime_deep_research_check.py --message "..." --timeout 600

Трейс: apps/backend/logs/multi_agent_traces/orchestrator_trace_*.jsonl (session_id из ответа).
"""
from __future__ import annotations

import argparse
import sys
import uuid

# TRACE_DIR / find_trace / print_trace_summary — общий формат с runtime_context_single_check
from runtime_context_single_check import find_trace, print_trace_summary, req


def bootstrap_token() -> tuple[str, str]:
    email = f"ce_deep_{uuid.uuid4().hex[:8]}@gigaboard.dev"
    username = "ce_deep_" + uuid.uuid4().hex[:6]
    password = "testpass123"
    status, reg = req(
        "POST",
        "/api/v1/auth/register",
        {"email": email, "password": password, "username": username},
    )
    if status not in (200, 201):
        raise RuntimeError(f"register failed: {status} {reg}")
    return reg["access_token"], email


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep Research live check via /api/v1/research/chat")
    parser.add_argument(
        "--message",
        default="найди топ 10 популярных российских актеров в 2025 году",
        help="Запрос на исследование",
    )
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    token, email = bootstrap_token()
    payload = {"message": args.message}

    status, body = req("POST", "/api/v1/research/chat", payload, token, timeout=args.timeout)
    session_id = body.get("session_id") if isinstance(body, dict) else None

    print("ENDPOINT", "/api/v1/research/chat")
    print("HTTP_STATUS", status)
    print("USER_EMAIL", email)
    print("SESSION_ID", session_id)
    if isinstance(body, dict):
        print("RESPONSE_KEYS", sorted(body.keys()))
        if isinstance(body.get("narrative"), str):
            prev = body["narrative"][:400].replace("\n", " ")
            print("NARRATIVE_PREVIEW", prev)
        src = body.get("sources") or []
        print("SOURCES_COUNT", len(src))
        disc = body.get("discovered_resources") or []
        print("DISCOVERED_COUNT", len(disc))
        if body.get("execution_time_ms") is not None:
            print("EXECUTION_MS", body["execution_time_ms"])

    if session_id:
        trace = find_trace(session_id)
        print_trace_summary(trace)
    else:
        print("TRACE_SKIPPED no session_id", body)


if __name__ == "__main__":
    main()
