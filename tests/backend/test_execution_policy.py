from apps.backend.app.services.multi_agent.execution_policy import resolve_execution_policy


def test_execution_policy_planner_expand_step_defaults():
    policy = resolve_execution_policy("planner", "expand_step")
    assert policy.timeout_sec == 30
    assert policy.max_retries == 1
    assert policy.context_ladder[0] == "full"


def test_execution_policy_validator_validate_defaults():
    policy = resolve_execution_policy("validator", "validate")
    assert policy.timeout_sec == 40
    assert policy.max_retries == 1
    assert "compact" in policy.context_ladder


def test_execution_policy_runtime_options_override_env_and_defaults():
    policy = resolve_execution_policy(
        "planner",
        "expand_step",
        runtime_options={
            "timeout_sec": 99,
            "max_retries": 2,
            "context_ladder": ["minimal", "compact"],
        },
    )
    assert policy.timeout_sec == 99
    assert policy.max_retries == 2
    assert policy.context_ladder == ["minimal", "compact"]


def test_execution_policy_task_override_has_priority():
    policy = resolve_execution_policy(
        "planner",
        "replan",
        runtime_options={
            "timeout_sec": 40,
            "task_overrides": {
                "replan": {
                    "timeout_sec": 55,
                    "max_retries": 0,
                    "context_ladder": ["compact", "minimal"],
                }
            },
        },
    )
    assert policy.timeout_sec == 55
    assert policy.max_retries == 0
    assert policy.context_ladder == ["compact", "minimal"]

