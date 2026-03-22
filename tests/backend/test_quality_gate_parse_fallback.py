import asyncio

from apps.backend.app.services.multi_agent.agents.quality_gate import QualityGateAgent


def test_quality_gate_parse_fallback_is_fail_closed():
    raw = QualityGateAgent._parse_json("not a json payload")

    assert raw["valid"] is False
    assert raw["confidence"] == 0.0
    assert raw["message"] == "Parse error — default fail"
    assert isinstance(raw.get("issues"), list)
    assert raw["issues"][0]["severity"] == "critical"


def test_quality_gate_falls_back_to_heuristic_on_llm_parse_error(monkeypatch):
    agent = QualityGateAgent(
        message_bus=None,  # type: ignore[arg-type]
        gigachat_service=None,  # type: ignore[arg-type]
    )

    async def _fake_llm_validate(*args, **kwargs):
        return {
            "valid": False,
            "confidence": 0.0,
            "message": "Parse error — default fail",
            "issues": [{"severity": "critical", "message": "malformed"}],
        }

    monkeypatch.setattr(agent, "_llm_validate", _fake_llm_validate)

    payload = asyncio.run(
        agent.process_task(
            task={
                "user_request": "Дай краткий итог",
                "aggregated_result": {
                    "reporter": {
                        "status": "success",
                        "narrative": {
                            "text": "Краткий итог по данным. " * 20,
                        },
                    }
                },
            },
            context={},
        )
    )

    assert payload.status == "success"
    assert payload.validation is not None
    assert payload.validation.valid is True

