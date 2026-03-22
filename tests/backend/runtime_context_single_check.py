import argparse
import glob
import json
import os
import uuid
import urllib.error
import urllib.request


BASE = "http://127.0.0.1:8000"
TRACE_DIR = "c:/Work/GigaBoard/apps/backend/logs/multi_agent_traces"


def req(method, path, data=None, token=None, timeout=180):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            return response.status, (json.loads(text) if text else {})
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8")
        try:
            return error.code, json.loads(text)
        except Exception:
            return error.code, {"detail": text}
    except Exception as error:
        return 599, {"detail": str(error)}


def bootstrap_user_project_board():
    email = f"ce_single_{uuid.uuid4().hex[:8]}@gigaboard.dev"
    username = "ce_single_" + uuid.uuid4().hex[:6]
    password = "testpass123"

    status, reg = req(
        "POST",
        "/api/v1/auth/register",
        {"email": email, "password": password, "username": username},
    )
    if status not in (200, 201):
        raise RuntimeError(f"register failed: {status} {reg}")
    token = reg["access_token"]

    status, project = req("POST", "/api/v1/projects", {"name": "CE Single Runtime"}, token)
    if status not in (200, 201):
        raise RuntimeError(f"project failed: {status} {project}")

    status, board = req(
        "POST",
        "/api/v1/boards",
        {"name": "CE Single Board", "project_id": project["id"]},
        token,
    )
    if status not in (200, 201):
        raise RuntimeError(f"board failed: {status} {board}")

    return token, board["id"], email


def find_trace(session_id):
    files = sorted(glob.glob(os.path.join(TRACE_DIR, "orchestrator_trace_*.jsonl")))
    if not files:
        return None
    found = None
    for path in files:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("session_id") == session_id:
                    found = item
    return found


def print_trace_summary(trace):
    if not trace:
        print("TRACE_FOUND false")
        return
    print("TRACE_FOUND true")
    print("TRACE_STATUS", trace.get("status"))
    for event in trace.get("events", []):
        if event.get("event") != "agent_call_start":
            continue
        details = event.get("details") or {}
        selection = details.get("context_selection") or {}
        if not selection:
            continue
        print(
            "TRACE_SELECTION",
            event.get("phase"),
            event.get("agent"),
            "task",
            details.get("task_type"),
            "budget",
            selection.get("budget_items"),
            selection.get("budget_chars"),
            "chat",
            selection.get("chat_history_before"),
            "->",
            selection.get("chat_history_after"),
            "results",
            selection.get("agent_results_before"),
            "->",
            selection.get("agent_results_after"),
        )
    run_finish = [e for e in trace.get("events", []) if e.get("event") == "run_finish"]
    if run_finish:
        details = run_finish[-1].get("details") or {}
        print(
            "TRACE_KPI",
            "ttfr_ms",
            details.get("time_to_first_result_ms"),
            "planner_error_streak_max",
            details.get("planner_error_streak_max"),
            "compaction",
            details.get("context_compaction_level"),
            "fallback",
            details.get("fallback_reason"),
            "validator_timeout_count",
            details.get("validator_timeout_count"),
            "validator_parse_fallback_count",
            details.get("validator_parse_fallback_count"),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        required=True,
        choices=["short", "long-context", "transform", "research-heavy"],
    )
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    token, board_id, email = bootstrap_user_project_board()

    long_context = {
        "chat_history": [
            {"role": "user", "content": "msg-" + str(i) + "-" + ("z" * 1200)}
            for i in range(25)
        ],
        "input_data_preview": {
            f"tbl_{i}": {
                "node_name": "node",
                "table_name": f"tbl_{i}",
                "row_count": 100,
                "columns": [{"name": f"c{j}", "type": "string"} for j in range(30)],
            }
            for i in range(6)
        },
        "catalog_data_preview": {
            f"cat_{i}": {
                "node_name": "node",
                "table_name": f"cat_{i}",
                "row_count": 200,
                "columns": [{"name": f"k{j}", "type": "number"} for j in range(20)],
            }
            for i in range(12)
        },
    }

    if args.scenario == "short":
        payload = {"message": "Ответь одной фразой: что ты умеешь в этой доске?"}
    elif args.scenario == "long-context":
        payload = {
            "message": "Сделай краткий обзор контекста и предложи 2 следующих шага.",
            "context": long_context,
        }
    elif args.scenario == "transform":
        payload = {
            "message": "Сгенерируй pandas-код: сгруппируй продажи по месяцам и посчитай total_amount."
        }
    else:
        payload = {
            "message": "Найди свежие источники по продажам электромобилей в РФ и дай краткий итог с 3 ссылками."
        }

    status, body = req("POST", f"/api/v1/boards/{board_id}/ai/chat", payload, token, timeout=args.timeout)
    session_id = body.get("session_id") if isinstance(body, dict) else None

    print("SCENARIO", args.scenario)
    print("HTTP_STATUS", status)
    print("USER_EMAIL", email)
    print("BOARD_ID", board_id)
    print("SESSION_ID", session_id)
    if isinstance(body, dict):
        print("RESPONSE_KEYS", list(body.keys()))
        if isinstance(body.get("response"), str):
            print("RESPONSE_PREVIEW", body["response"][:220].replace("\n", " "))

    if session_id:
        trace = find_trace(session_id)
        print_trace_summary(trace)


if __name__ == "__main__":
    main()
