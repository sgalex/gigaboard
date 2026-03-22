from apps.backend.app.services.multi_agent.agents.planner import PlannerAgent


def test_extract_json_object_text_from_plain_json():
    text = '{"a": 1, "b": {"c": 2}}'
    extracted = PlannerAgent._extract_json_object_text(text)
    assert extracted == text


def test_extract_json_object_text_from_markdown_code_fence():
    text = "Some intro\n```json\n{\n  \"atomic\": true\n}\n```\nfooter"
    extracted = PlannerAgent._extract_json_object_text(text)
    assert extracted.startswith("{")
    assert '"atomic": true' in extracted


def test_extract_json_object_text_balances_braces_with_text_noise():
    text = (
        "Plan follows:\n"
        "{\n"
        "  \"remaining_steps\": [\n"
        "    {\"step_id\": \"1\", \"agent\": \"reporter\", \"task\": {\"description\": \"ok\"}, \"depends_on\": []}\n"
        "  ]\n"
        "}\n"
        "Thanks!"
    )
    extracted = PlannerAgent._extract_json_object_text(text)
    assert extracted.endswith("}")
    assert '"remaining_steps"' in extracted
