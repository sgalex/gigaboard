"""
Task-aware execution policies for Multi-Agent orchestration.

Policy controls:
- timeout per agent/task type
- max retries per agent/task type
- context compaction ladder per agent/task type
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .config import TimeoutConfig
from .message_types import MessageType
from .runtime_overrides import ladder_from_env, ma_int


def _safe_ladder_value(value: Any, default: List[str]) -> List[str]:
    if not isinstance(value, list):
        return default
    levels = [str(item).strip().lower() for item in value if str(item).strip()]
    valid = [lvl for lvl in levels if lvl in {"full", "compact", "minimal"}]
    return valid or default


def _safe_int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ExecutionPolicy:
    timeout_sec: int
    max_retries: int
    context_ladder: List[str]


_DEFAULT_RETRIES: Dict[str, int] = {
    "planner": 1,
    "reporter": 1,
    "validator": 0,
    "_default": 1,
}

_TASK_RETRIES: Dict[str, Dict[str, int]] = {
    "planner": {
        "create_plan": 1,
        "expand_step": 1,
        "revise_remaining": 1,
        "replan": 1,
    },
    "reporter": {"summarize": 1},
    "validator": {"validate": 1},
}

_DEFAULT_LADDERS: Dict[str, List[str]] = {
    "planner": ["full", "compact", "minimal"],
    "reporter": ["full", "compact"],
    "validator": ["full", "compact"],
    "_default": ["full", "compact"],
}

_TASK_TIMEOUTS: Dict[str, Dict[str, int]] = {
    "planner": {
        "create_plan": 30,
        "expand_step": 30,
        "revise_remaining": 35,
        "replan": 35,
    },
    "validator": {"validate": 40},
}


def _resolve_db_runtime_options(
    runtime_options: Optional[Dict[str, Any]],
    task_type: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(runtime_options, dict):
        return {}
    merged: Dict[str, Any] = {
        "timeout_sec": runtime_options.get("timeout_sec"),
        "max_retries": runtime_options.get("max_retries"),
        "context_ladder": runtime_options.get("context_ladder"),
    }
    task_overrides = runtime_options.get("task_overrides")
    if isinstance(task_overrides, dict) and task_type:
        task_specific = task_overrides.get(task_type)
        if isinstance(task_specific, dict):
            for key in ("timeout_sec", "max_retries", "context_ladder"):
                if key in task_specific:
                    merged[key] = task_specific.get(key)
    return merged


def resolve_execution_policy(
    agent_name: str,
    task_type: Optional[str],
    runtime_options: Optional[Dict[str, Any]] = None,
) -> ExecutionPolicy:
    default_timeout = TimeoutConfig.get_timeout(MessageType.TASK_REQUEST, agent_name)
    task_timeout = _TASK_TIMEOUTS.get(agent_name, {}).get(task_type or "", default_timeout)
    timeout_sec = ma_int(
        f"MULTI_AGENT_TIMEOUT_{agent_name.upper()}_{(task_type or 'DEFAULT').upper()}",
        task_timeout,
    )

    default_retries = _DEFAULT_RETRIES.get(agent_name, _DEFAULT_RETRIES["_default"])
    retries = _TASK_RETRIES.get(agent_name, {}).get(task_type or "", default_retries)
    max_retries = ma_int(
        f"MULTI_AGENT_RETRIES_{agent_name.upper()}_{(task_type or 'DEFAULT').upper()}",
        retries,
    )
    if max_retries < 0:
        max_retries = 0

    default_ladder = _DEFAULT_LADDERS.get(agent_name, _DEFAULT_LADDERS["_default"])
    context_ladder = ladder_from_env(
        f"MULTI_AGENT_CONTEXT_LADDER_{agent_name.upper()}_{(task_type or 'DEFAULT').upper()}",
        default_ladder,
    )

    # DB runtime_options in agent_llm_override имеют приоритет над env/default.
    db_options = _resolve_db_runtime_options(runtime_options, task_type)
    if "timeout_sec" in db_options and db_options.get("timeout_sec") is not None:
        timeout_sec = _safe_int_value(db_options.get("timeout_sec"), timeout_sec)
    if "max_retries" in db_options and db_options.get("max_retries") is not None:
        max_retries = _safe_int_value(db_options.get("max_retries"), max_retries)
    if "context_ladder" in db_options and db_options.get("context_ladder") is not None:
        context_ladder = _safe_ladder_value(db_options.get("context_ladder"), context_ladder)
    if max_retries < 0:
        max_retries = 0

    return ExecutionPolicy(
        timeout_sec=timeout_sec,
        max_retries=max_retries,
        context_ladder=context_ladder,
    )

