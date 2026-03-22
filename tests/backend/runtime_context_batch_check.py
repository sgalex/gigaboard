import json
import os
import uuid
import glob
import urllib.request
import urllib.error


BASE = "http://127.0.0.1:8000"
TRACE_DIR = "c:/Work/GigaBoard/apps/backend/logs/multi_agent_traces"


def req(method, path, data=None, token=None, timeout=120):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(
        BASE + path, data=body, headers=headers, method=method
    )
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


def register_and_bootstrap():
    email = f"ce_batch_{uuid.uuid4().hex[:8]}@gigaboard.dev"
    username = "ce_batch_" + uuid.uuid4().hex[:6]
    password = "testpass123"

    status, reg = req(
        "POST",
        "/api/v1/auth/register",
        {"email": email, "password": password, "username": username},
    )
    if status not in (200, 201):
        raise RuntimeError(f"register failed: {status} {reg}")
    token = reg["access_token"]

    status, project = req(
        "POST",
        "/api/v1/projects",
        {"name": "CE Batch Runtime Project", "description": "runtime batch checks"},
        token,
    )
    if status not in (200, 201):
        raise RuntimeError(f"project failed: {status} {project}")

    status, board = req(
        "POST",
        "/api/v1/boards",
        {
            "name": "CE Batch Runtime Board",
            "description": "runtime board",
            "project_id": project["id"],
        },
        token,
    )
    if status not in (200, 201):
        raise RuntimeError(f"board failed: {status} {board}")

    return token, board["id"], email


def find_trace_by_session(session_id):
    files = sorted(glob.glob(os.path.join(TRACE_DIR, "orchestrator_trace_*.jsonl")))
    if not files:
        return None
    found = None
    for path in files:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("session_id") == session_id:
                    found = obj
    return found


def summarize_trace(trace):
    if not trace:
        return {"trace_found": False}

    planner_calls = []
    selection_samples = []
    for event in trace.get("events", []):
        if event.get("event") != "agent_call_start":
            continue
        details = event.get("details") or {}
        selection = details.get("context_selection") or {}

        if event.get("agent") == "planner":
            planner_calls.append(
                {
                    "phase": event.get("phase"),
                    "task_type": details.get("task_type"),
                    "budget_items": selection.get("budget_items"),
                    "budget_chars": selection.get("budget_chars"),
                    "agent_results_before": selection.get("agent_results_before"),
                    "agent_results_after": selection.get("agent_results_after"),
                    "chat_before": selection.get("chat_history_before"),
                    "chat_after": selection.get("chat_history_after"),
                }
            )

        if selection:
            selection_samples.append(
                {
                    "agent": event.get("agent"),
                    "phase": event.get("phase"),
                    "task_type": details.get("task_type"),
                    "budget_items": selection.get("budget_items"),
                    "budget_chars": selection.get("budget_chars"),
                    "chat_before": selection.get("chat_history_before"),
                    "chat_after": selection.get("chat_history_after"),
                }
            )

    run_finish = [e for e in trace.get("events", []) if e.get("event") == "run_finish"]
    finish = run_finish[-1] if run_finish else {}
    finish_details = finish.get("details") or {}

    return {
        "trace_found": True,
        "status": trace.get("status"),
        "replan_count": finish_details.get("replan_count"),
        "planner_calls": planner_calls,
        "time_to_first_result_ms": finish_details.get("time_to_first_result_ms"),
        "planner_error_streak_max": finish_details.get("planner_error_streak_max"),
        "context_compaction_level": finish_details.get("context_compaction_level"),
        "fallback_reason": finish_details.get("fallback_reason"),
        "validator_timeout_count": finish_details.get("validator_timeout_count"),
        "validator_parse_fallback_count": finish_details.get("validator_parse_fallback_count"),
        "selection_samples_top5": selection_samples[:5],
        "events_count": trace.get("events_count"),
    }


def main():
    token, board_id, email = register_and_bootstrap()

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

    scenarios = [
        {
            "name": "ai_short",
            "kind": "ai",
            "payload": {"message": "Ответь одной фразой: что ты умеешь в этой доске?"},
        },
        {
            "name": "ai_long_context",
            "kind": "ai",
            "payload": {
                "message": "Сделай краткий обзор контекста и предложи 2 следующих шага.",
                "context": long_context,
            },
        },
        {
            "name": "ai_transform_request",
            "kind": "ai",
            "payload": {
                "message": "Сгенерируй pandas-код: сгруппируй продажи по месяцам и посчитай total_amount."
            },
        },
        {
            "name": "ai_research_heavy",
            "kind": "ai",
            "payload": {
                "message": "Найди свежие источники по продажам электромобилей в РФ и дай краткий итог с 3 ссылками."
            },
        },
    ]

    results = []
    for scenario in scenarios:
        path = (
            f"/api/v1/boards/{board_id}/ai/chat"
            if scenario["kind"] == "ai"
            else "/api/v1/research/chat"
        )
        status, body = req("POST", path, scenario["payload"], token, timeout=180)
        session_id = body.get("session_id") if isinstance(body, dict) else None

        item = {
            "scenario": scenario["name"],
            "http_status": status,
            "session_id": session_id,
            "response_keys": list(body.keys())[:10] if isinstance(body, dict) else [],
        }
        if isinstance(body, dict) and isinstance(body.get("response"), str):
            item["response_preview"] = body["response"][:180]

        if session_id:
            item["trace_summary"] = summarize_trace(find_trace_by_session(session_id))
        else:
            item["trace_summary"] = {"trace_found": False}

        results.append(item)

    print("BATCH_USER", email)
    print("BATCH_BOARD", board_id)
    print("BATCH_RESULTS_JSON_START")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("BATCH_RESULTS_JSON_END")


if __name__ == "__main__":
    main()
