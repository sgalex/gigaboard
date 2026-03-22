import glob
import json
import os
from statistics import mean


TRACE_DIR = "c:/Work/GigaBoard/apps/backend/logs/multi_agent_traces"


def _latest_trace_file() -> str:
    files = sorted(glob.glob(os.path.join(TRACE_DIR, "orchestrator_trace_*.jsonl")))
    if not files:
        raise RuntimeError("trace files not found")
    return files[-1]


def main() -> None:
    path = _latest_trace_file()
    rows = [json.loads(x) for x in open(path, "r", encoding="utf-8") if x.strip()]
    if not rows:
        raise RuntimeError("trace file is empty")

    durations = []
    ttfr = []
    planner_streak = []
    validator_timeouts = 0
    validator_parse_fallbacks = 0

    for row in rows:
        durations.append((row.get("total_duration_ms") or 0) / 1000.0)
        run_finish = [e for e in row.get("events", []) if e.get("event") == "run_finish"]
        details = (run_finish[-1].get("details") or {}) if run_finish else {}
        if isinstance(details.get("time_to_first_result_ms"), int):
            ttfr.append(details["time_to_first_result_ms"])
        if isinstance(details.get("planner_error_streak_max"), int):
            planner_streak.append(details["planner_error_streak_max"])
        validator_timeouts += int(details.get("validator_timeout_count") or 0)
        validator_parse_fallbacks += int(details.get("validator_parse_fallback_count") or 0)

    print("TRACE_FILE", path)
    print("SESSIONS", len(rows))
    print("DURATION_AVG_S", round(mean(durations), 2))
    print("DURATION_MAX_S", round(max(durations), 2))
    print("TTFR_AVG_MS", int(mean(ttfr)) if ttfr else None)
    print("PLANNER_ERROR_STREAK_MAX", max(planner_streak) if planner_streak else 0)
    print("VALIDATOR_TIMEOUTS_TOTAL", validator_timeouts)
    print("VALIDATOR_PARSE_FALLBACKS_TOTAL", validator_parse_fallbacks)


if __name__ == "__main__":
    main()

