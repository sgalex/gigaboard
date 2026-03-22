import pytest
from pydantic import ValidationError

from apps.backend.app.schemas.user_settings import AgentLLMOverrideItem


def test_runtime_options_schema_accepts_valid_ladder_and_task_overrides():
    item = AgentLLMOverrideItem.model_validate(
        {
            "agent_key": "planner",
            "llm_config_id": "11111111-1111-1111-1111-111111111111",
            "runtime_options": {
                "timeout_sec": 45,
                "max_retries": 1,
                "context_ladder": ["FULL", "compact"],
                "max_items": 30,
                "max_total_chars": 100000,
                "task_overrides": {
                    "replan": {
                        "timeout_sec": 60,
                        "context_ladder": ["compact", "minimal"],
                    }
                },
            },
        }
    )

    assert item.runtime_options is not None
    assert item.runtime_options.context_ladder == ["full", "compact"]
    assert item.runtime_options.task_overrides is not None
    assert item.runtime_options.task_overrides["replan"].context_ladder == ["compact", "minimal"]


def test_runtime_options_schema_rejects_invalid_ladder_level():
    with pytest.raises(ValidationError):
        AgentLLMOverrideItem.model_validate(
            {
                "agent_key": "planner",
                "llm_config_id": "11111111-1111-1111-1111-111111111111",
                "runtime_options": {
                    "context_ladder": ["full", "aggressive"],
                },
            }
        )
